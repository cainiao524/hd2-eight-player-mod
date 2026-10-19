-- HD2-Addon: mods/cainiao/hd2_party_api_probe
--
-- Read-only runtime binding probe for the PartyWin API path inferred from the
-- fixed-build CreateNewNetwork call shape.  It never calls an export, follows
-- a returned object, writes memory, or installs a hook.

local ffi_ok, ffi = pcall(require, 'ffi')
local S = rawget(_G, 'HD2Scanner')
local scanner_reader = type(S) == 'table' and S.version == 1 and
    type(S.api) == 'table' and type(S.api.read) == 'function' and S.api.read or nil
if not scanner_reader then
    pcall(function() require('mods/junze/hd2_scanner') end)
    S = rawget(_G, 'HD2Scanner')
    scanner_reader = type(S) == 'table' and S.version == 1 and
        type(S.api) == 'table' and type(S.api.read) == 'function' and S.api.read or nil
end

local log_dir = (os.getenv('LOCALAPPDATA') or '.') .. '/CowboyBingus/Helldivers2/Logs'
local log_file = io.open(log_dir .. '/HD2PartyApiProbe.log', 'a')
local function report(message)
    if log_file then
        log_file:write(os.date('%Y-%m-%d %H:%M:%S ') .. tostring(message) .. '\n')
        log_file:flush()
    end
end

report('START read_only=true party_api_probe=20261011')
if not ffi_ok then report('REFUSE ffi_unavailable') return end

pcall(ffi.cdef, [[
    void *GetModuleHandleA(const char *name);
    void *GetCurrentProcess(void);
    int ReadProcessMemory(void *process, const void *address, void *buffer,
                          size_t size, size_t *read_size);
]])
local kernel_ok, kernel = pcall(ffi.load, 'kernel32')
if not kernel_ok then report('REFUSE kernel32_unavailable') return end

local read_mem = scanner_reader
if not read_mem then
    local process_ok, process = pcall(kernel.GetCurrentProcess)
    if process_ok and process ~= nil then
        read_mem = function(address, size)
            if type(address) ~= 'number' or address <= 0 or size <= 0 or size > 0x1000000 then
                return nil
            end
            local buffer = ffi.new('uint8_t[?]', size)
            local copied = ffi.new('size_t[1]', 0)
            local ok = pcall(kernel.ReadProcessMemory, process,
                ffi.cast('const void *', address), buffer, size, copied)
            if ok and tonumber(copied[0]) == size then
                return ffi.string(buffer, size)
            end
            return nil
        end
        report('READER self_process_read_only=true')
    end
end
if not read_mem then
    report('REFUSE read_api_unavailable')
    return
end

local function module_base(name)
    local handle = kernel.GetModuleHandleA(name)
    if handle == nil then return nil end
    return tonumber(ffi.cast('uint64_t', handle))
end

local function u64_le(value)
    local out = {}
    for i = 1, 8 do
        out[i] = string.char(value % 256)
        value = math.floor(value / 256)
    end
    return table.concat(out)
end

local function u64_num(data)
    if type(data) ~= 'string' or #data < 8 then return nil end
    local function u32(offset)
        local a, b, c, d = data:byte(offset + 1, offset + 4)
        if not d then return nil end
        return a + b * 256 + c * 65536 + d * 16777216
    end
    local lo, hi = u32(0), u32(4)
    if not lo or not hi then return nil end
    return lo + hi * 4294967296
end

local function i32_num(data, offset)
    if type(data) ~= 'string' or #data < offset + 4 then return nil end
    local a, b, c, d = data:byte(offset + 1, offset + 4)
    local value = a + b * 256 + c * 65536 + d * 16777216
    if value >= 2147483648 then value = value - 4294967296 end
    return value
end

local function hex_bytes(data)
    if type(data) ~= 'string' then return 'nil' end
    return (data:gsub('.', function(c) return string.format('%02X', string.byte(c)) end))
end

-- Export RVAs are read from the fixed PartyWin.dll export table on disk and
-- are used only as runtime address/version pins.
local PARTY_EXPORTS = {
    { name = 'PartyCreateNewNetwork', rva = 0x15720 },
    { name = 'PartyConnectToNetwork', rva = 0x14FE0 },
    { name = 'PartyNetworkAuthenticateLocalUser', rva = 0x1BC80 },
    { name = 'PartyNetworkCreateEndpoint', rva = 0x1C050 },
    { name = 'PartyNetworkLeaveNetwork', rva = 0x1E640 },
    { name = 'PartyNetworkKickUser', rva = 0x1E500 },
    { name = 'PartyNetworkRemoveLocalUser', rva = 0x1E7F0 },
    { name = 'PartyCleanup', rva = 0x14DC0 },
    { name = 'PartyNetworkGetNetworkConfiguration', rva = 0x1DB30 },
    { name = 'PartyNetworkGetNetworkDescriptor', rva = 0x1DCD0 },
    { name = 'PartyNetworkSetCustomContext', rva = 0x1EBF0 },
    { name = 'PartyStartProcessingStateChanges', rva = 0x1FEE0 },
    { name = 'PartyFinishProcessingStateChanges', rva = 0x193C0 },
    { name = 'PartyDoWork', rva = 0x17350 },
}

-- These are the unresolved indirect-call slots recorded by the saved
-- 0x8E1370/0x8E1970 code windows.  Reading the slot is safe; calling it is
-- deliberately outside this probe.
local GAME_INDIRECT_SLOTS = {
    { rva = 0x13F6DB8, label = 'create_network_candidate' },
    { rva = 0x13F6EF8, label = 'async_or_state_candidate' },
    { rva = 0x13F6DF0, label = 'authenticate_or_state_candidate' },
    { rva = 0x13F6C30, label = 'create_endpoint_candidate' },
    { rva = 0x13F6F70, label = 'connect_network_candidate' },
    { rva = 0x13F7030, label = 'auth_network_candidate' },
}

-- Named imports are captured as runtime pointer pins only.  Reading the IAT
-- does not prove that the protected call sites use these imports.
local GAME_IAT_SLOTS = {
    { rva = 0x29617D8, label = 'PartyNetworkSetCustomContext' },
    { rva = 0x29617E8, label = 'PFLobbySendInvite' },
}

-- Live windows for the previously saved create/follow-on call shape.  These
-- are bounded reads only; no indirect call target is invoked or interpreted
-- as an ABI from bytes alone.
local GAME_CALLSITE_WINDOWS = {
    { rva = 0x8E1370, label = 'create_network_callsite' },
    { rva = 0x8E1970, label = 'follow_on_callsite' },
}

-- The live create window calls the TLS/helper at 0x8E25B0 and then loads
-- rcx from the qword returned by its 0x8E25D0 fallback path.  This is a
-- bounded data read to test whether that holder currently contains a
-- PartyWin-side manager pointer; it is never dereferenced as an object and
-- never called.
local GAME_GLOBAL_POINTERS = {
    { rva = 0x27CED10, label = 'party_manager_holder_candidate' },
}

local state = { frame = 0, pending = false, submitted = false, completed = false, round = 0 }

local function scan_direct_calls(label, address, code, image_base)
    if type(code) ~= 'string' or #code < 5 then return end
    local seen = {}
    local count = 0
    for offset = 0, #code - 5 do
        if string.byte(code, offset + 1) == 0xE8 then
            local displacement = i32_num(code, offset + 1)
            if displacement then
                local target = address + offset + 5 + displacement
                if target >= image_base and target < image_base + 0x4000000 and not seen[target] then
                    seen[target] = true
                    count = count + 1
                    report(string.format('CALL_TARGET label=%s at=0x%X target=0x%X code128=%s',
                        label, address + offset, target, hex_bytes(read_mem(target, 128))))
                    if count >= 8 then return end
                end
            end
        end
    end
end

local function scan_rip_indirects(label, address, code, image_base, party_base, playfab_base)
    if type(code) ~= 'string' or #code < 6 then return end
    local seen = {}
    local count = 0
    for offset = 0, #code - 6 do
        local op = string.byte(code, offset + 1)
        local op2 = string.byte(code, offset + 2)
        if op == 0xFF and (op2 == 0x15 or op2 == 0x25) then
            local displacement = i32_num(code, offset + 2)
            if displacement then
                local slot = address + offset + 6 + displacement
                if not seen[slot] then
                    seen[slot] = true
                    count = count + 1
                    local raw = read_mem(slot, 8)
                    local target = u64_num(raw)
                    local in_party = target and target >= party_base and target < party_base + 0x400000 or false
                    local in_playfab = target and target >= playfab_base and target < playfab_base + 0x400000 or false
                    local in_exe = target and target >= image_base and target < image_base + 0x4000000 or false
                    report(string.format(
                        'RIP_INDIRECT label=%s kind=%s at=0x%X slot=0x%X target=%s in_party=%s in_playfab=%s in_exe=%s raw=%s',
                        label, op2 == 0x15 and 'call' or 'jmp', address + offset, slot,
                        target and string.format('0x%X', target) or 'nil', tostring(in_party),
                        tostring(in_playfab), tostring(in_exe), hex_bytes(raw)))
                    if count >= 128 then return end
                end
            end
        end
    end
end

local function follow_jump_chain(label, start_address, image_base, party_base, playfab_base)
    local current = start_address
    for depth = 0, 3 do
        local code = read_mem(current, 256)
        report(string.format('HOP label=%s depth=%d address=0x%X code256=%s',
            label, depth, current, hex_bytes(code)))
        if type(code) ~= 'string' or #code < 6 then return end
        local code_window = read_mem(current, 0x1000)
        report(string.format('HOP_WINDOW label=%s depth=%d address=0x%X size=0x1000 code4096=%s',
            label, depth, current, hex_bytes(code_window)))
        scan_rip_indirects(label .. '_d' .. tostring(depth), current, code_window,
            image_base, party_base, playfab_base)
        scan_direct_calls(label .. '_d' .. tostring(depth), current, code, image_base)
        local op = string.byte(code, 1)
        local op2 = string.byte(code, 2)
        if op == 0xE9 then
            local displacement = i32_num(code, 1)
            if not displacement then return end
            current = current + 5 + displacement
        elseif op == 0xFF and op2 == 0x25 then
            local displacement = i32_num(code, 2)
            if not displacement then return end
            local slot = current + 6 + displacement
            local raw = read_mem(slot, 8)
            local next_address = u64_num(raw)
            report(string.format('HOP_INDIRECT label=%s depth=%d slot=0x%X target=%s raw=%s',
                label, depth, slot, next_address and string.format('0x%X', next_address) or 'nil', hex_bytes(raw)))
            if not next_address then return end
            current = next_address
        else
            return
        end
    end
end

local function begin_scan()
    if state.pending or state.completed then return end
    local game = module_base('game.dll')
    local party = module_base('PartyWin.dll')
    local playfab = module_base('PlayFabMultiplayerWin.dll')
    local exe = module_base('helldivers2.exe')
    if not game or not party or not playfab or not exe then
        report(string.format('WAIT modules game=%s party=%s playfab=%s exe=%s',
            tostring(game), tostring(party), tostring(playfab), tostring(exe)))
        return
    end

    local patterns = {}
    for _, export in ipairs(PARTY_EXPORTS) do
        export.address = party + export.rva
        patterns[#patterns + 1] = {
            key = 'party_' .. export.name,
            bytes = u64_le(export.address),
        }
    end

    state.round = state.round + 1
    local request_id = 'hd2_party_api_probe_20261011_' .. tostring(state.round)
    report(string.format('MODULES game_base=0x%X party_base=0x%X playfab_base=0x%X exe_base=0x%X',
        game, party, playfab, exe))
    for _, iat in ipairs(GAME_IAT_SLOTS) do
        local iat_address = exe + iat.rva
        local raw = read_mem(iat_address, 8)
        local target = u64_num(raw)
        local in_party = target and target >= party and target < party + 0x400000 or false
        local in_playfab = target and target >= playfab and target < playfab + 0x400000 or false
        local in_exe = target and target >= exe and target < exe + 0x4000000 or false
        report(string.format('EXE_IAT rva=0x%X label=%s address=0x%X target=%s in_party=%s in_playfab=%s in_exe=%s raw=%s code64=%s',
            iat.rva, iat.label, iat_address, target and string.format('0x%X', target) or 'nil',
            tostring(in_party), tostring(in_playfab), tostring(in_exe), hex_bytes(raw),
            target and hex_bytes(read_mem(target, 64)) or 'nil'))
    end
    -- The six candidate slots are close together in the protected image.  A
    -- bounded neighborhood capture preserves table context without scanning
    -- or interpreting unrelated process memory.
    local table_address = exe + 0x13F6C00
    report(string.format('EXE_SLOT_TABLE_WINDOW address=0x%X size=0x480 bytes=%s',
        table_address, hex_bytes(read_mem(table_address, 0x480))))
    for _, pointer in ipairs(GAME_GLOBAL_POINTERS) do
        local address = exe + pointer.rva
        local raw = read_mem(address, 8)
        local target = u64_num(raw)
        local in_party = target and target >= party and target < party + 0x400000 or false
        local in_playfab = target and target >= playfab and target < playfab + 0x400000 or false
        local in_exe = target and target >= exe and target < exe + 0x4000000 or false
        report(string.format(
            'EXE_GLOBAL_POINTER rva=0x%X label=%s address=0x%X target=%s in_party=%s in_playfab=%s in_exe=%s raw=%s target_code64=%s',
            pointer.rva, pointer.label, address, target and string.format('0x%X', target) or 'nil',
            tostring(in_party), tostring(in_playfab), tostring(in_exe), hex_bytes(raw),
            target and hex_bytes(read_mem(target, 64)) or 'nil'))
    end
    for _, window in ipairs(GAME_CALLSITE_WINDOWS) do
        local address = exe + window.rva
        report(string.format('EXE_CALLSITE_WINDOW rva=0x%X label=%s address=0x%X size=0x1000 code4096=%s',
            window.rva, window.label, address, hex_bytes(read_mem(address, 0x1000))))
    end
    for _, slot in ipairs(GAME_INDIRECT_SLOTS) do
        -- The saved 0x8E1370/0x8E1970 windows are in helldivers2.exe, not
        -- game.dll.  Keep the two module bases separate so this read cannot
        -- silently turn into a wrong-module observation.
        local slot_address = exe + slot.rva
        local raw = read_mem(slot_address, 8)
        local target = u64_num(raw)
        local in_party = target and target >= party and target < party + 0x400000 or false
        local in_exe = target and target >= exe and target < exe + 0x4000000 or false
        local target_code = target and read_mem(target, 512) or nil
        report(string.format('EXE_SLOT rva=0x%X label=%s address=0x%X target=%s in_party=%s in_exe=%s raw=%s code512=%s',
            slot.rva, slot.label, slot_address, target and string.format('0x%X', target) or 'nil',
            tostring(in_party), tostring(in_exe), hex_bytes(raw), hex_bytes(target_code)))
        if target then follow_jump_chain(slot.label, target, exe, party, playfab) end
    end

    -- The direct slot/code capture above is the authoritative part of this
    -- revision.  The first revision used a full-memory export-pointer scan;
    -- that result is retained in its earlier log, while this run avoids a
    -- second multi-minute scan and preserves the live callee windows needed
    -- for offline disassembly.
    for _, export in ipairs(PARTY_EXPORTS) do
        export.address = party + export.rva
        report(string.format('EXPORT name=%s rva=0x%X address=0x%X code64=%s',
            export.name, export.rva, export.address, hex_bytes(read_mem(export.address, 64))))
    end
    report('STATUS read_only=true calls=false writes=false hooks=false')
    report('DONE read_only=true no_calls=true no_writes=true hooks_installed=false direct_slot_capture=true')
    state.completed = true
    state.submitted = true
end

local previous_update = update
update = function(...)
    local a, b, c = previous_update and previous_update(...)
    state.frame = state.frame + 1
    if state.frame == 120 then pcall(begin_scan) end
    return a, b, c
end

local previous_shutdown = shutdown
shutdown = function(...)
    if log_file then
        report('SHUTDOWN read_only=true submitted=' .. tostring(state.submitted) ..
            ' completed=' .. tostring(state.completed))
        log_file:close()
    end
    if previous_shutdown then return previous_shutdown(...) end
end

report('LOADED waits_for_frame_120')
