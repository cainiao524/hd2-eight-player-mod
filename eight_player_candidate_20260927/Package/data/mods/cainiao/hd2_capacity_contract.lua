-- Configurable player-capacity contract for the HD2 addon.
--
-- This module is deliberately independent from the game process.  It is the
-- common validation layer used by the menu, diagnostics and the native bridge
-- adapter.  A native adapter must provide the real Session/Party capacities
-- before a state can be marked executable.

local M = {}

local MAX_DIAGNOSTICS = 256
local MAX_GENERATION = 9007199254740991
local PRESETS = {4, 5, 8, 12, 16}
local PRESET_NAMES = {
    [4] = "Original: 4",
    [5] = "5 Players",
    [8] = "8 Players",
    [12] = "12 Players",
    [16] = "16 Players",
}

local SPEC = {
    schema_version = 1,
    build = 25480438,
    exe_sha256 = "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06",
    game_dll_sha256 = "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cdd0d1813c718f51e",
    max_verified_players = 4,
    hard_storage_limit = 16,
}

local function copy(value, seen)
    if type(value) ~= "table" then return value end
    seen = seen or {}
    if seen[value] then return seen[value] end
    local result = {}
    seen[value] = result
    for key, item in pairs(value) do result[copy(key, seen)] = copy(item, seen) end
    return result
end

local function integer(value, lo, hi)
    return type(value) == "number" and value == math.floor(value)
        and value >= lo and value <= hi
end

local function result(status, reason, fields)
    local out = {status = status, accepted = status == "accepted", reason = reason}
    if fields then for key, value in pairs(fields) do out[key] = value end end
    return out
end

local function reject(reason, fields) return result("rejected", reason, fields) end
local function accept(reason, fields) return result("accepted", reason, fields) end

local function min_capacity(capacities)
    local effective = SPEC.hard_storage_limit
    for _, key in ipairs({
        "configured_max_players", "peer_capacity", "roster_capacity",
        "entity_capacity", "resource_capacity", "network_capacity",
        "verified_capacity",
    }) do
        local value = capacities[key]
        if not integer(value, 1, SPEC.hard_storage_limit) then return nil, key end
        if value < effective then effective = value end
    end
    return effective
end

function M.spec()
    return copy(SPEC)
end

function M.presets()
    local out = {}
    for index, value in ipairs(PRESETS) do
        out[index] = {value = value, label = PRESET_NAMES[value]}
    end
    return out
end

function M.preset_value(preset, custom_value)
    if preset == "Custom" or preset == "custom" then
        return custom_value
    end
    if type(preset) == "number" then return preset end
    if type(preset) == "string" then
        for _, value in ipairs(PRESETS) do
            if preset == PRESET_NAMES[value] or preset == tostring(value) then return value end
        end
    end
    return nil
end

function M.validate_profile(profile)
    if type(profile) ~= "table" then return reject("profile_not_table") end
    if profile.schema_version ~= SPEC.schema_version or profile.build ~= SPEC.build then
        return reject("profile_mismatch", {field = "schema_or_build"})
    end
    for _, key in ipairs({"exe_sha256", "game_dll_sha256"}) do
        if type(profile[key]) ~= "string" or string.lower(profile[key]) ~= SPEC[key] then
            return reject("profile_mismatch", {field = key})
        end
    end
    return accept("profile_match")
end

function M.validate_capacity_fields(fields)
    if type(fields) ~= "table" then return reject("capacity_fields_not_table") end
    local verified = fields.verified_capacity or SPEC.max_verified_players
    if not integer(verified, 1, SPEC.hard_storage_limit) then
        return reject("verified_capacity_invalid")
    end
    if not integer(fields.configured_max_players, 1, verified) then
        return reject("configured_capacity_invalid", {maximum = verified})
    end
    local effective, missing = min_capacity({
        configured_max_players = fields.configured_max_players,
        peer_capacity = fields.peer_capacity,
        roster_capacity = fields.roster_capacity,
        entity_capacity = fields.entity_capacity,
        resource_capacity = fields.resource_capacity,
        network_capacity = fields.network_capacity,
        verified_capacity = verified,
    })
    if not effective then return reject("component_capacity_invalid", {field = missing}) end
    local joined_players = fields.joined_players or 0
    if not integer(joined_players, 0, SPEC.hard_storage_limit) then
        return reject("joined_players_invalid")
    end
    if effective < joined_players then
        return reject("joined_players_exceed_capacity", {effective = effective})
    end
    return accept("capacity_valid", {effective_max_players = effective, verified_capacity = verified})
end

local function state_shape(state)
    if type(state) ~= "table" or type(state.profile) ~= "table" then return reject("state_not_table") end
    local profile = M.validate_profile(state.profile)
    if not profile.accepted then return profile end
    if not integer(state.generation, 0, MAX_GENERATION) then return reject("generation_invalid") end
    if state.authority ~= "host" and state.authority ~= "client" then return reject("authority_invalid") end
    if type(state.mission_active) ~= "boolean" or type(state.quiescent) ~= "boolean" then
        return reject("lifecycle_flags_invalid")
    end
    if not integer(state.joined_players, 0, SPEC.hard_storage_limit) then
        return reject("joined_players_invalid")
    end
    return M.validate_capacity_fields(state)
end

function M.new_state(options)
    options = options or {}
    local profile = options.profile or SPEC
    local profile_result = M.validate_profile(profile)
    if not profile_result.accepted then return nil, profile_result end
    local verified = options.verified_capacity or SPEC.max_verified_players
    if not integer(verified, 1, SPEC.hard_storage_limit) then return nil, reject("verified_capacity_invalid") end
    local configured = options.configured_max_players or math.min(4, verified)
    local fields = {
        configured_max_players = configured,
        peer_capacity = options.peer_capacity or verified,
        roster_capacity = options.roster_capacity or verified,
        entity_capacity = options.entity_capacity or verified,
        resource_capacity = options.resource_capacity or verified,
        network_capacity = options.network_capacity or verified,
        verified_capacity = verified,
        joined_players = options.joined_players or 0,
    }
    local valid = M.validate_capacity_fields(fields)
    if not valid.accepted then return nil, valid end
    local state = copy(fields)
    state.profile = copy(SPEC)
    state.generation = 0
    state.authority = options.authority or "host"
    state.mission_active = options.mission_active == true
    state.quiescent = options.quiescent ~= false
    state.allow_join_in_progress = options.allow_join_in_progress ~= false
    state.require_same_mod_version = options.require_same_mod_version ~= false
    state.apply_mode = options.apply_mode or "next_lobby"
    state.pending = nil
    state.diagnostics = {}
    return state, accept("state_created", {effective_max_players = valid.effective_max_players})
end

function M.record(state, layer, event, status, reason, fields)
    if type(state) ~= "table" or type(state.diagnostics) ~= "table" then return false end
    local item = {layer = layer, event = event, status = status, reason = reason}
    if fields then for key, value in pairs(fields) do item[key] = value end end
    state.diagnostics[#state.diagnostics + 1] = item
    while #state.diagnostics > MAX_DIAGNOSTICS do table.remove(state.diagnostics, 1) end
    return true
end

function M.effective(state)
    local valid = state_shape(state)
    if not valid.accepted then return nil, valid end
    return valid.effective_max_players, valid
end

function M.stage(state, request)
    local valid = state_shape(state)
    if not valid.accepted then return valid end
    if state.authority ~= "host" then return reject("host_authority_required") end
    if type(request) ~= "table" then return reject("request_not_table") end
    local configured = M.preset_value(request.preset, request.max_players)
    if not integer(configured, 1, state.verified_capacity) then
        M.record(state, "menu", "stage", "rejected", "configured_capacity_invalid")
        return reject("configured_capacity_invalid", {maximum = state.verified_capacity})
    end
    local pending = copy(state)
    pending.pending = nil
    pending.configured_max_players = configured
    if request.allow_join_in_progress ~= nil then pending.allow_join_in_progress = request.allow_join_in_progress == true end
    if request.require_same_mod_version ~= nil then pending.require_same_mod_version = request.require_same_mod_version == true end
    if request.apply_mode ~= nil then pending.apply_mode = request.apply_mode end
    local capacity = M.validate_capacity_fields(pending)
    if not capacity.accepted then
        M.record(state, "menu", "stage", "rejected", capacity.reason)
        return capacity
    end
    if state.mission_active and configured < state.configured_max_players then
        M.record(state, "menu", "stage", "rejected", "mission_capacity_cannot_decrease")
        return reject("mission_capacity_cannot_decrease")
    end
    if state.mission_active and configured > state.configured_max_players
        and (pending.apply_mode ~= "next_mission" or not state.quiescent) then
        M.record(state, "menu", "stage", "rejected", "live_increase_requires_quiescence")
        return reject("live_increase_requires_quiescence")
    end
    state.pending = pending
    M.record(state, "menu", "stage", "accepted", "pending", {effective_max_players = capacity.effective_max_players})
    return accept("pending", {effective_max_players = capacity.effective_max_players})
end

function M.apply(state, reservation)
    local valid = state_shape(state)
    if not valid.accepted then return valid end
    if state.authority ~= "host" then return reject("host_authority_required") end
    if state.pending == nil then return accept("no_pending_change", {effective_max_players = valid.effective_max_players}) end
    local pending = state.pending
    if state.mission_active and pending.configured_max_players > state.configured_max_players then
        if type(reservation) ~= "table" or reservation.ready ~= true or reservation.quiescent ~= true then
            M.record(state, "capacity", "apply", "rejected", "reservation_not_ready")
            return reject("reservation_not_ready")
        end
    end
    local capacity = M.validate_capacity_fields(pending)
    if not capacity.accepted then
        state.pending = nil
        M.record(state, "capacity", "apply", "rejected", capacity.reason)
        return capacity
    end
    local generation = state.generation + 1
    if generation > MAX_GENERATION then return reject("generation_exhausted") end
    for key, value in pairs(pending) do
        if key ~= "pending" and key ~= "diagnostics" and key ~= "generation" then state[key] = copy(value) end
    end
    state.generation = generation
    state.pending = nil
    M.record(state, "capacity", "apply", "accepted", "applied", {
        generation = generation, effective_max_players = capacity.effective_max_players,
    })
    return accept("applied", {generation = generation, effective_max_players = capacity.effective_max_players})
end

function M.metadata(state, mod_version, fingerprints)
    local valid = state_shape(state)
    if not valid.accepted then return nil, valid end
    local effective = valid.effective_max_players
    return {
        schema_version = SPEC.schema_version,
        build = SPEC.build,
        mod_version = mod_version or "unknown",
        fingerprints = copy(fingerprints or {}),
        configured_max_players = state.configured_max_players,
        effective_max_players = effective,
        peer_capacity = state.peer_capacity,
        roster_capacity = state.roster_capacity,
        entity_capacity = state.entity_capacity,
        resource_capacity = state.resource_capacity,
        network_capacity = state.network_capacity,
        allow_join_in_progress = state.allow_join_in_progress,
        require_same_mod_version = state.require_same_mod_version,
        generation = state.generation,
    }, accept("metadata_ready")
end

function M.validate_metadata(local_metadata, remote_metadata)
    if type(local_metadata) ~= "table" or type(remote_metadata) ~= "table" then
        return reject("metadata_not_table")
    end
    for _, key in ipairs({"schema_version", "build", "mod_version", "configured_max_players", "effective_max_players"}) do
        if local_metadata[key] ~= remote_metadata[key] then return reject("metadata_mismatch", {field = key}) end
    end
    if local_metadata.require_same_mod_version and local_metadata.mod_version ~= remote_metadata.mod_version then
        return reject("mod_version_mismatch")
    end
    if local_metadata.effective_max_players < 1 then return reject("effective_capacity_invalid") end
    return accept("metadata_compatible")
end

function M.status(state, client_compatible)
    local effective, valid = M.effective(state)
    if not effective then return "Config Status: Rejected (" .. tostring(valid.reason) .. ")" end
    local status = state.pending and "Pending" or "Applied"
    local compatible = client_compatible == nil and "Unknown" or (client_compatible and "Compatible" or "Incompatible")
    return string.format(
        "Configured Limit: %d | Joined Players: %d / %d | Available Slots: %d | Effective Limit: %d | Host Authority: %s | Client Compatibility: %s | Config Status: %s",
        state.configured_max_players, state.joined_players, effective,
        math.max(0, effective - state.joined_players), effective,
        state.authority == "host" and "Enabled" or "Read Only", compatible, status)
end

function M.validate(state)
    return state_shape(state)
end

function M.snapshot(state)
    local valid = state_shape(state)
    if not valid.accepted then return nil, valid end
    local out = copy(state)
    out.profile = copy(SPEC)
    out.diagnostics = copy(state.diagnostics)
    out.game_integration = false
    out.multiplayer_verified = false
    out.effective_max_players = valid.effective_max_players
    return out, accept("snapshot_ready")
end

return M
