-- HD2-Addon: mods/cainiao/hd2_session_vtable_probe
--
-- Read-only runtime capture of the already observed GameSession vtable.
-- It locates the fixed-build vtable by its ASLR-adjusted pointer entries and
-- reads bounded code windows for lifecycle slots.  It never calls a slot.

local ffi_ok, ffi = pcall(require, 'ffi')
local S = rawget(_G, 'HD2Scanner')
if type(S) ~= 'table' or S.version ~= 1 or type(S.scan_request) ~= 'function' then
    pcall(function() require('mods/junze/hd2_scanner') end)
    S = rawget(_G, 'HD2Scanner')
end

local log_dir = (os.getenv('LOCALAPPDATA') or '.') .. '/CowboyBingus/Helldivers2/Logs'
local log_file = io.open(log_dir .. '/HD2SessionVtableProbe.log', 'a')
local function report(message)
    if log_file then
        log_file:write(os.date('%Y-%m-%d %H:%M:%S ') .. tostring(message) .. '\n')
        log_file:flush()
    end
end

report('START read_only=true build=25480438 vtable_probe=20261011')
if not ffi_ok then report('REFUSE ffi_unavailable') return end
if type(S) ~= 'table' or S.version ~= 1 or type(S.scan_request) ~= 'function' then
    report('REFUSE hd2scanner_unavailable')
    return
end
if type(S.api) ~= 'table' or type(S.api.read) ~= 'function' then
    report('REFUSE hd2scanner_read_api_unavailable')
    return
end

pcall(ffi.cdef, [[
    void *GetModuleHandleA(const char *name);
]])
local kernel_ok, kernel = pcall(ffi.load, 'kernel32')
if not kernel_ok then report('REFUSE kernel32_unavailable') return end

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

local function hex_bytes(data)
    if type(data) ~= 'string' then return 'nil' end
    return (data:gsub('.', function(c) return string.format('%02X', string.byte(c)) end))
end

local function u64_num(data, offset)
    local function u32(o)
        local a, b, c, d = data:byte(o + 1, o + 4)
        if not d then return nil end
        return a + b * 256 + c * 65536 + d * 16777216
    end
    local lo, hi = u32(offset), u32(offset + 4)
    if not lo or not hi then return nil end
    return lo + hi * 4294967296
end

-- RVA list from the fixed-build read-only live vtable capture.  The values are
-- version gates only; their generic SDK labels are deliberately not inferred.
local VTABLE_RVAS = {
    0x29D330, 0x296BD0, 0x28F020, 0x28F200, 0x296200, 0x28F340,
    0x2939B0, 0x291110, 0x2928F0, 0x28F2A0, 0x292B60, 0x28F9C0,
    0x292C10, 0x292BD0, 0x292BE0, 0x292BF0, 0x292C60, 0x292C20,
    0x292CB0, 0x292CC0, 0x292CD0, 0x292D10, 0x296AB0, 0x292DF0,
    0x292EB0, 0x292F10, 0x293140, 0x292F60, 0x292FC0, 0x296C80,
    0x297BB0, 0x297AA0, 0x297B30, 0x297B70, 0x290040, 0x297BE0,
    0x297DA0, 0x298A00, 0x2987E0, 0x29AA70, 0x290950, 0x290BE0,
}
local EXE_IMAGE_SIZE = 0x39E8000
local CRITICAL = {
    [0x18] = 'make_host', [0x20] = 'shutdown_host', [0x30] = 'migrate_host',
    [0x38] = 'disconnect_from_host', [0x40] = 'add_peer', [0x48] = 'peer',
    [0x50] = 'num_peers', [0x88] = 'remove_peer', [0x90] = 'leave',
}

local CHUNKS = {}
for start = 1, #VTABLE_RVAS, 8 do
    local stop = math.min(#VTABLE_RVAS, start + 7)
    CHUNKS[#CHUNKS + 1] = { start = start - 1, stop = stop, offset = (start - 1) * 8 }
end

local state = { frame = 0, pending = false, completed = false, round = 0, object_runs = 0, vtable = nil, base = nil, next_object_frame = 0x7FFFFFFF }
local function begin_object_scan(vtable, base)
    if state.pending or state.object_runs >= 2 then return end
    state.object_runs = state.object_runs + 1
    local object_run = state.object_runs
    local request_id = 'hd2_session_object_probe_20261011_' .. tostring(state.round) .. '_r' .. tostring(object_run)
    local ok, why = S.scan_request{
        id = request_id,
        patterns = {{ key = 'vtable_pointer', bytes = u64_le(vtable) }},
        budget = 8 * 1024 * 1024,
        on_done = function(hits)
            state.pending = false
            local list = (type(hits) == 'table' and hits.vtable_pointer) or {}
            report(string.format('OBJECT_HITS run=%d count=%d vtable=0x%X', object_run, #list, vtable))
            for index, address in ipairs(list) do
                local window = S.api.read(address - 32, 0x420)
                report(string.format('OBJECT occurrence=%d pointer_at=0x%X object_candidate=0x%X context=%s',
                    index, address, address, hex_bytes(window)))
            end
            report(string.format('OBJECT_DONE run=%d read_only=true no_calls=true no_writes=true semantic_claims=false', object_run))
            if object_run >= 2 then
                state.completed = true
            else
                state.next_object_frame = state.frame + 900
            end
        end,
    }
    if ok then
        state.pending = true
        report(string.format('OBJECT_REQUEST id=%s vtable=0x%X game_base=0x%X', request_id, vtable, base))
    else
        report('OBJECT_REFUSE scan_request=' .. tostring(why))
        if object_run >= 2 then state.completed = true end
    end
end

local function begin_scan()
    if state.pending or state.completed then return end
    local base = module_base('helldivers2.exe')
    if not base then report('WAIT helldivers2_exe_not_loaded') return end

    local patterns = {}
    for index, chunk in ipairs(CHUNKS) do
        local bytes = {}
        for i = chunk.start + 1, chunk.stop do bytes[#bytes + 1] = u64_le(base + VTABLE_RVAS[i]) end
        patterns[index] = { key = 'chunk_' .. tostring(index), bytes = table.concat(bytes) }
    end

    state.round = state.round + 1
    local request_id = 'hd2_session_vtable_probe_20261011_' .. tostring(state.round)
    local ok, why = S.scan_request{
        id = request_id,
        patterns = patterns,
        budget = 8 * 1024 * 1024,
        on_done = function(hits)
            state.pending = false
            if type(hits) ~= 'table' then report('DONE invalid_result') return end
            local candidates = {}
            for index, chunk in ipairs(CHUNKS) do
                for _, address in ipairs(hits['chunk_' .. tostring(index)] or {}) do
                    local candidate = address - chunk.offset
                    local row = candidates[candidate]
                    if not row then row = { coverage = {}, count = 0 } candidates[candidate] = row end
                    if not row.coverage[index] then row.coverage[index] = true row.count = row.count + 1 end
                end
            end

            local complete = {}
            for candidate, row in pairs(candidates) do
                local in_exe = candidate >= base and candidate < base + EXE_IMAGE_SIZE
                report(string.format('CANDIDATE base=0x%X chunks=%d/%d in_exe=%s',
                    candidate, row.count, #CHUNKS, tostring(in_exe)))
                if row.count == #CHUNKS and in_exe then complete[#complete + 1] = candidate end
            end
            if #complete ~= 1 then
                report('REFUSE unique_vtable=' .. tostring(#complete))
                state.completed = true
                return
            end

            local vtable = complete[1]
            state.vtable = vtable
            state.base = base
            local raw = S.api.read(vtable, #VTABLE_RVAS * 8)
            local expected = {}
            for _, rva in ipairs(VTABLE_RVAS) do expected[#expected + 1] = u64_le(base + rva) end
            expected = table.concat(expected)
            if raw ~= expected then
                report('REFUSE vtable_readback_mismatch')
                state.completed = true
                return
            end
            report(string.format('VTABLE base=0x%X slots=%d game_base=0x%X', vtable, #VTABLE_RVAS, base))
            for slot = 0, (#VTABLE_RVAS - 1) * 8, 8 do
                local target = u64_num(raw, slot)
                if CRITICAL[slot] then
                    local code = target and S.api.read(target, 128) or nil
                    report(string.format('CODE slot=0x%X role=%s target=0x%X rva=0x%X bytes=%s',
                        slot, CRITICAL[slot], target or 0, (target and (target - base) or 0), hex_bytes(code)))
                end
            end
            report('VTABLE_DONE read_only=true no_calls=true no_writes=true semantic_claims=false')
            begin_object_scan(vtable, base)
        end,
    }
    if ok then
        state.pending = true
        report(string.format('REQUEST id=%s game_base=0x%X chunks=%d', request_id, base, #CHUNKS))
    else
        report('REFUSE scan_request=' .. tostring(why))
    end
end

local previous_update = update
update = function(...)
    local a, b, c = previous_update and previous_update(...)
    state.frame = state.frame + 1
    if state.frame == 120 then pcall(begin_scan) end
    if state.frame >= state.next_object_frame and state.vtable and not state.pending and state.object_runs < 2 then
        pcall(function() begin_object_scan(state.vtable, state.base) end)
        state.next_object_frame = 0x7FFFFFFF
    end
    return a, b, c
end

local previous_shutdown = shutdown
shutdown = function(...)
    if log_file then
        report('SHUTDOWN completed=' .. tostring(state.completed))
        log_file:close()
    end
    if previous_shutdown then return previous_shutdown(...) end
end

report('LOADED waits_for_frame_120')
