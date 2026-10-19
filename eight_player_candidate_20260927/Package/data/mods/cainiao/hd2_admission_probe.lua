-- HD2-Addon: mods/cainiao/hd2_admission_probe
--
-- Read-only diagnostic consumer for the already installed HD2Scanner service.
-- It scans for runtime pointers to the statically identified admission sites
-- and records the result.  It never calls, patches, or claims any of them.

local ffi_ok, ffi = pcall(require, 'ffi')
local S = rawget(_G, 'HD2Scanner')
if type(S) ~= 'table' or S.version ~= 1 or type(S.scan_request) ~= 'function' then
    pcall(function() require('mods/junze/hd2_scanner') end)
    S = rawget(_G, 'HD2Scanner')
end

local base_dir = (os.getenv('LOCALAPPDATA') or '.') .. '/CowboyBingus/Helldivers2/Logs'
local log_file = io.open(base_dir .. '/HD2AdmissionRegistryProbe.log', 'a')
local function report(message)
    if log_file then
        log_file:write(os.date('%Y-%m-%d %H:%M:%S ') .. tostring(message) .. '\n')
        log_file:flush()
    end
end

report('START read_only=true scanner_probe=20261011 registry_marker=true')
if not ffi_ok then
    report('REFUSE ffi_unavailable')
    return
end
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
if not kernel_ok then
    report('REFUSE kernel32_unavailable')
    return
end

local function game_base()
    local handle = kernel.GetModuleHandleA('game.dll')
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

local function u32_le(value)
    local out = {}
    for i = 1, 4 do
        out[i] = string.char(value % 256)
        value = math.floor(value / 256)
    end
    return table.concat(out)
end

local function hex_bytes(data)
    if type(data) ~= 'string' then return 'nil' end
    return (data:gsub('.', function(c) return string.format('%02X', string.byte(c)) end))
end

local TARGETS = {
    { key = 'ptr_receiver',   rva = 0xBABA80,  label = 'receiver_entry' },
    { key = 'ptr_client_insert', rva = 0xB90B20, label = 'client_insert' },
    { key = 'ptr_platform_consumer', rva = 0x1093590, label = 'platform_consumer' },
    { key = 'ptr_platform_state', rva = 0x10937A0, label = 'platform_state' },
    { key = 'ptr_registration', rva = 0x1094680, label = 'registration_body' },
    { key = 'ptr_unregistration', rva = 0x1094710, label = 'unregistration' },
    { key = 'ptr_dispatch', rva = 0xBC2D10, label = 'selector_dispatch' },
    { key = 'ptr_callback_table', rva = 0x214C2E0, label = 'callback_table' },
}

local state = { frame = 0, pending = false, submitted = false, completed = false, round = 0 }

local function scanner_status()
    if type(S.status) ~= 'function' then return 'status_api_unavailable' end
    local ok, status = pcall(S.status)
    if not ok or type(status) ~= 'table' then return 'status_read_failed' end
    return string.format('state=%s rounds=%s regions=%s reads=%s',
        tostring(status.state), tostring(status.rounds), tostring(status.regions), tostring(status.reads))
end

local function begin_scan()
    if state.pending or state.completed then return end
    local base = game_base()
    if not base then
        report('WAIT game_dll_not_loaded')
        return
    end

    local patterns = {
        { key = 'event_hash', bytes = u32_le(0x4804FCF4) },
        { key = 'rpc_marker', bytes = 'rpc_from_host_peer_c' },
    }
    for _, target in ipairs(TARGETS) do
        target.address = base + target.rva
        patterns[#patterns + 1] = { key = target.key, bytes = u64_le(target.address) }
    end

    state.round = state.round + 1
    local id = 'hd2_admission_probe_20261010_' .. tostring(state.round)
    local ok, why = S.scan_request{
        id = id,
        patterns = patterns,
        budget = 8 * 1024 * 1024,
        on_done = function(hits)
            state.pending = false
            if type(hits) ~= 'table' then
                report('DONE invalid_result')
                return
            end
            for _, target in ipairs(TARGETS) do
                local list = hits[target.key] or {}
                report(string.format('HIT key=%s label=%s rva=0x%X address=0x%X count=%d',
                    target.key, target.label, target.rva, target.address, #list))
                for index, address in ipairs(list) do
                    local context = S.api.read(address - 8, 24)
                    report(string.format('  occurrence=%d at=0x%X context=%s',
                        index, address, hex_bytes(context)))
                end
            end
            local hash_hits = hits.event_hash or {}
            report(string.format('HIT key=event_hash value=0x4804FCF4 count=%d', #hash_hits))
            for index, address in ipairs(hash_hits) do
                local context = S.api.read(address - 16, 48)
                report(string.format('  occurrence=%d at=0x%X context=%s',
                    index, address, hex_bytes(context)))
            end
            local marker_hits = hits.rpc_marker or {}
            local data_markers = {}
            report(string.format('HIT key=rpc_marker value=rpc_from_host_peer_c count=%d', #marker_hits))
            for index, address in ipairs(marker_hits) do
                local first = S.api.read(address - 32, 128)
                local second = S.api.read(address - 32, 128)
                local event_offsets = {}
                local event_address = nil
                if type(first) == 'string' then
                    for offset = 0, #first - 4 do
                        if first:sub(offset + 1, offset + 4) == u32_le(0x4804FCF4) then
                            event_offsets[#event_offsets + 1] = string.format('0x%X', offset)
                            if not event_address then event_address = address - 32 + offset end
                        end
                    end
                end
                report(string.format('  marker_occurrence=%d at=0x%X stable=%s event_offsets=%s context=%s',
                    index, address, tostring(first == second), table.concat(event_offsets, ','), hex_bytes(first)))
                if #event_offsets > 0 and first == second and event_address then
                    data_markers[#data_markers + 1] = {
                        marker = address, record = address - 32, event = event_address
                    }
                end
            end
            if #data_markers == 0 then
                report('STATUS ' .. scanner_status())
                report('DONE read_only=true no_calls=true no_writes=true')
                state.completed = true
            else
                local pointer_patterns = {}
                local pointer_targets = {}
                for index, item in ipairs(data_markers) do
                    pointer_targets[#pointer_targets + 1] = {
                        key = 'ptr_to_record_' .. tostring(index), label = 'record', address = item.record
                    }
                    pointer_targets[#pointer_targets + 1] = {
                        key = 'ptr_to_event_hash_' .. tostring(index), label = 'event_hash', address = item.event
                    }
                    pointer_patterns[#pointer_patterns + 1] = {
                        key = pointer_targets[#pointer_targets - 1].key, bytes = u64_le(item.record)
                    }
                    pointer_patterns[#pointer_patterns + 1] = {
                        key = pointer_targets[#pointer_targets].key, bytes = u64_le(item.event)
                    }
                end
                local pointer_ok, pointer_why = S.scan_request{
                    id = 'hd2_admission_registry_refs_20261011_' .. tostring(state.round),
                    patterns = pointer_patterns,
                    budget = 8 * 1024 * 1024,
                    on_done = function(pointer_hits)
                        state.pending = false
                        if type(pointer_hits) ~= 'table' then
                            report('REFUSE pointer_scan_invalid_result')
                            return
                        end
                        for _, target in ipairs(pointer_targets) do
                            local list = pointer_hits[target.key] or {}
                            report(string.format('HIT key=%s label=%s target=0x%X count=%d',
                                target.key, target.label, target.address, #list))
                            for occurrence, pointer_at in ipairs(list) do
                                local first = S.api.read(pointer_at - 16, 64)
                                local second = S.api.read(pointer_at - 16, 64)
                                report(string.format('  pointer_occurrence=%d at=0x%X stable=%s context=%s',
                                    occurrence, pointer_at, tostring(first == second), hex_bytes(first)))
                            end
                        end
                        report('STATUS ' .. scanner_status())
                        report('DONE read_only=true no_calls=true no_writes=true')
                        state.completed = true
                    end,
                }
                if pointer_ok then
                    state.pending = true
                    report(string.format('POINTER_REQUEST markers=%d %s', #data_markers, scanner_status()))
                else
                    report('REFUSE pointer_scan=' .. tostring(pointer_why))
                    report('STATUS ' .. scanner_status())
                    report('DONE read_only=true no_calls=true no_writes=true')
                    state.completed = true
                end
            end
        end,
    }
    if ok then
        state.pending = true
        state.submitted = true
        report(string.format('REQUEST id=%s game_base=0x%X targets=%d %s',
            id, base, #TARGETS, scanner_status()))
    else
        report('REFUSE scan_request=' .. tostring(why))
    end
end

local previous_update = update
update = function(...)
    local a, b, c = previous_update and previous_update(...)
    state.frame = state.frame + 1
    if state.frame == 120 or state.frame == 1800 then
        pcall(begin_scan)
    end
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
