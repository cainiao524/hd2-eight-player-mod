-- HD2 eight-player admission contract.
-- No FFI, process reads, network calls, hooks, allocation calls or installation.

local M = {}
local MAX_GENERATION = 9007199254740991
local MAX_DIAGNOSTICS = 256

local SPEC = {
    build = 25480438,
    exe_sha256 = "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06",
    game_dll_sha256 = "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e",
    logical_max_players = 8,
    storage_slots = 8,
    first_network_index = 0,
    last_network_index = 7,
}

local function integer(value, lo, hi)
    return type(value) == "number" and value == math.floor(value)
        and value >= lo and value <= hi
end

local function identity(value)
    return type(value) == "string" and #value > 0 and #value <= 256
end

local function copy(value, seen)
    if type(value) ~= "table" then return value end
    seen = seen or {}
    if seen[value] then return seen[value] end
    local out = {}
    seen[value] = out
    for key, item in pairs(value) do out[copy(key, seen)] = copy(item, seen) end
    return out
end

local function reject(reason, fields)
    local out = {status = "rejected", accepted = false, reason = reason}
    if fields then for key, value in pairs(fields) do out[key] = value end end
    return out
end

local function accepted(reason, fields)
    local out = {status = "accepted", accepted = true, reason = reason}
    if fields then for key, value in pairs(fields) do out[key] = value end end
    return out
end

function M.spec()
    return copy(SPEC)
end

function M.validate_profile(profile)
    if type(profile) ~= "table" then return reject("profile_not_table") end
    for key, expected in pairs(SPEC) do
        if type(profile[key]) ~= type(expected) or profile[key] ~= expected then
            return reject("profile_mismatch", {field = key, expected = expected})
        end
    end
    return accepted("profile_match")
end

function M.validate_network_index(index)
    if type(index) ~= "number" or index ~= math.floor(index) then
        return reject("network_index_not_integer", {index = index})
    end
    if index < SPEC.first_network_index or index > SPEC.last_network_index then
        return reject("network_index_out_of_range", {index = index})
    end
    return accepted("network_index_valid", {index = index})
end

function M.validate_count(count)
    if type(count) ~= "number" or count ~= math.floor(count) then
        return reject("count_not_integer", {count = count})
    end
    if count < 0 or count > SPEC.logical_max_players then
        return reject("count_out_of_range", {count = count, maximum = SPEC.logical_max_players})
    end
    return accepted("count_valid", {count = count})
end

function M.new_state(profile)
    if profile == nil then profile = M.spec() end
    local result = M.validate_profile(profile)
    if not result.accepted then return nil, result end
    local state = {
        profile = copy(SPEC),
        generation = 0,
        slots = {},
        by_network_index = {},
        diagnostics = {},
    }
    for ordinal = 0, SPEC.storage_slots - 1 do state.slots[ordinal + 1] = nil end
    return state, accepted("state_created", {generation = 0})
end

function M.record(state, layer, event, result, reason, fields)
    if type(state) ~= "table" or type(state.diagnostics) ~= "table" then return false end
    local item = {layer = layer, event = event, result = result, reason = reason}
    if fields then for key, value in pairs(fields) do item[key] = value end end
    state.diagnostics[#state.diagnostics + 1] = item
    while #state.diagnostics > MAX_DIAGNOSTICS do table.remove(state.diagnostics, 1) end
    return true
end

local function guard_record(record)
    if type(record) ~= "table" then return reject("record_not_table") end
    if not identity(record.peer_id) then return reject("peer_id_missing") end
    local result = M.validate_network_index(record.network_index)
    if not result.accepted then return result end
    if record.resource_handle ~= nil then return reject("resource_requires_confirmation") end
    return accepted("record_valid")
end

local function state_valid(state)
    if type(state) ~= "table" or type(state.slots) ~= "table"
        or type(state.by_network_index) ~= "table"
        or type(state.diagnostics) ~= "table"
        or type(state.generation) ~= "number"
        or not integer(state.generation, 0, MAX_GENERATION) then
        return reject("state_not_table")
    end
    local profile_result = M.validate_profile(state.profile)
    if not profile_result.accepted then return profile_result end
    local count, map_count, active_count = 0, 0, 0
    local seen_indices, seen_peers, seen_tokens, seen_handles = {}, {}, {}, {}
    for key in pairs(state.slots) do
        if type(key) ~= "number" or not integer(key, 1, SPEC.storage_slots) then
            return reject("state_slots_shape_invalid")
        end
    end
    for ordinal = 0, SPEC.storage_slots - 1 do
        local entry = state.slots[ordinal + 1]
        if entry ~= nil then
            count = count + 1
            if type(entry) ~= "table" or entry.ordinal ~= ordinal then return reject("ordinal_mismatch") end
            if not identity(entry.peer_id) then return reject("peer_id_missing") end
            local index_result = M.validate_network_index(entry.network_index)
            if not index_result.accepted then return index_result end
            if state.by_network_index[entry.network_index] ~= ordinal then
                return reject("index_ordinal_mismatch")
            end
            if seen_indices[entry.network_index] or seen_peers[entry.peer_id] then
                return reject("duplicate_identity")
            end
            if not integer(entry.generation, 1, state.generation) or seen_tokens[entry.generation] then
                return reject("generation_token_invalid")
            end
            if entry.phase ~= "pending" and entry.phase ~= "active" then
                return reject("phase_invalid")
            end
            if entry.phase == "pending" and entry.resource_handle ~= nil then
                return reject("pending_has_resource")
            end
            if entry.phase == "active" and not identity(entry.resource_handle) then
                return reject("resource_handle_missing")
            end
            if entry.phase == "active" then
                if seen_handles[entry.resource_handle] then return reject("duplicate_resource_handle") end
                seen_handles[entry.resource_handle] = true
                active_count = active_count + 1
            end
            seen_indices[entry.network_index], seen_peers[entry.peer_id] = true, true
            seen_tokens[entry.generation] = true
        end
    end
    for index, ordinal in pairs(state.by_network_index) do
        map_count = map_count + 1
        if not integer(index, 0, 7) or not integer(ordinal, 0, 7)
            or state.slots[ordinal + 1] == nil
            or state.slots[ordinal + 1].network_index ~= index then
            return reject("index_ordinal_mismatch")
        end
    end
    if count ~= map_count then return reject("occupied_count_mismatch") end
    local diagnostics_count = 0
    for key in pairs(state.diagnostics) do
        if not integer(key, 1, MAX_DIAGNOSTICS) then return reject("diagnostics_invalid") end
        diagnostics_count = math.max(diagnostics_count, key)
    end
    for key = 1, diagnostics_count do
        if state.diagnostics[key] == nil then return reject("diagnostics_invalid") end
        if type(state.diagnostics[key]) ~= "table" then return reject("diagnostics_invalid") end
    end
    return accepted("state_valid", {occupied_count = count, active_count = active_count})
end

local function free_ordinal(state)
    for ordinal = 0, SPEC.storage_slots - 1 do
        if state.slots[ordinal + 1] == nil then return ordinal end
    end
    return nil
end

function M.insert(state, record)
    local valid = state_valid(state)
    if not valid.accepted then return reject(valid.reason) end
    local guarded = guard_record(record)
    if not guarded.accepted then
        M.record(state, "roster", "reserve", "rejected", guarded.reason)
        return guarded
    end
    local index = record.network_index
    if state.by_network_index[index] ~= nil then
        local result = reject("duplicate_network_index")
        M.record(state, "roster", "reserve", "rejected", result.reason)
        return result
    end
    for ordinal_check = 0, SPEC.storage_slots - 1 do
        local entry = state.slots[ordinal_check + 1]
        if entry ~= nil and entry.peer_id == record.peer_id then
            local result = reject("duplicate_peer_id")
            M.record(state, "roster", "reserve", "rejected", result.reason)
            return result
        end
    end
    local ordinal = free_ordinal(state)
    if ordinal == nil then return reject("no_free_storage_slot") end
    if state.generation >= MAX_GENERATION then return reject("generation_exhausted") end
    local token = state.generation + 1
    local entry = {peer_id = record.peer_id, network_index = index, ordinal = ordinal,
        resource_handle = nil, generation = token, phase = "pending"}
    state.slots[ordinal + 1] = entry
    state.by_network_index[index] = ordinal
    state.generation = token
    M.record(state, "roster", "reserve", "accepted", "reserved", {ordinal = ordinal, generation = token})
    return accepted("reserved", {ordinal = ordinal, generation = token})
end

local function lookup_internal(state, index)
    local valid = state_valid(state)
    if not valid.accepted then return valid end
    local index_result = M.validate_network_index(index)
    if not index_result.accepted then return index_result end
    local ordinal = state.by_network_index[index]
    if ordinal == nil then return reject("network_index_missing") end
    local entry = state.slots[ordinal + 1]
    if entry == nil or entry.network_index ~= index then return reject("index_ordinal_mismatch") end
    return accepted("found", {ordinal = ordinal, entry = entry})
end

function M.lookup(state, index)
    local found = lookup_internal(state, index)
    if found.accepted then found.entry = copy(found.entry) end
    return found
end

local function token_entry(state, index, expected_generation)
    if not integer(expected_generation, 1, MAX_GENERATION) then return reject("stale_generation") end
    local found = lookup_internal(state, index)
    if not found.accepted then return found end
    if found.entry.generation ~= expected_generation then return reject("stale_generation") end
    return found
end

function M.remove(state, index, expected_generation)
    if type(state) ~= "table" or type(state.generation) ~= "number"
        or not integer(state.generation, 0, MAX_GENERATION) then
        return reject("generation_exhausted")
    end
    if state.generation >= MAX_GENERATION then return reject("generation_exhausted") end
    local found = token_entry(state, index, expected_generation)
    if not found.accepted then
        M.record(state, "roster", "remove", "rejected", found.reason)
        return found
    end
    local ordinal = found.ordinal
    state.slots[ordinal + 1] = nil
    state.by_network_index[index] = nil
    state.generation = state.generation + 1
    M.record(state, "roster", "remove", "accepted", "hole_preserved", {ordinal = ordinal})
    return accepted("removed", {ordinal = ordinal, generation = state.generation})
end

function M.bind_resource(state, index, resource_handle, expected_generation)
    if type(state) ~= "table" or type(state.generation) ~= "number"
        or not integer(state.generation, 0, MAX_GENERATION) then
        return reject("generation_exhausted")
    end
    if state.generation >= MAX_GENERATION then return reject("generation_exhausted") end
    local found = token_entry(state, index, expected_generation)
    if not found.accepted then
        M.record(state, "resource", "confirm", "rejected", found.reason)
        return found
    end
    if not identity(resource_handle) then return reject("resource_handle_missing") end
    for ordinal = 0, SPEC.storage_slots - 1 do
        local entry = state.slots[ordinal + 1]
        if entry ~= nil and entry.resource_handle == resource_handle then
            return reject("duplicate_resource_handle")
        end
    end
    if found.entry.phase ~= "pending" then return reject("already_confirmed") end
    found.entry.resource_handle = resource_handle
    found.entry.phase = "active"
    state.generation = state.generation + 1
    M.record(state, "resource", "confirm", "accepted", "confirmed", {ordinal = found.ordinal})
    return accepted("confirmed", {ordinal = found.ordinal, generation = state.generation})
end

function M.validate(state)
    return state_valid(state)
end

function M.snapshot(state)
    local valid = state_valid(state)
    if not valid.accepted then return nil, valid end
    local entries = {}
    for ordinal = 0, SPEC.storage_slots - 1 do
        local entry = state.slots[ordinal + 1]
        if entry ~= nil then entries[#entries + 1] = copy(entry) end
    end
    local active_count = 0
    for _, entry in ipairs(entries) do if entry.phase == "active" then active_count = active_count + 1 end end
    return {profile = copy(SPEC), generation = state.generation,
        occupied_count = #entries, active_count = active_count, entries = entries,
        diagnostics = copy(state.diagnostics), game_integration = false,
        multiplayer_verified = false}, accepted("snapshot_ready")
end

return M
