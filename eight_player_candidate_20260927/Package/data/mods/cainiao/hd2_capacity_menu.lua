-- HD2-Addon: mods/cainiao/hd2_capacity_menu
--
-- Host-facing menu adapter.  It only stages a validated capacity request and
-- forwards it to HD2CapacityBridge when that bridge has passed its native
-- preflight.  Without the bridge the page remains visible for diagnostics but
-- cannot claim that the game capacity changed.

local CONTRACT = require('mods/cainiao/hd2_capacity_contract')
local MOD_NAME = 'Player Capacity'
local IDS = {
    preset = 'hd2.capacity.preset',
    max_players = 'hd2.capacity.max_players',
    allow_join = 'hd2.capacity.allow_join_in_progress',
    same_version = 'hd2.capacity.require_same_mod_version',
    apply_mode = 'hd2.capacity.apply_mode',
}

local PRESET_CHOICES = {'Original: 4', '5 Players', '8 Players', '12 Players', '16 Players', 'Custom'}
local APPLY_CHOICES = {'Next Lobby', 'Next Mission', 'Restart Required'}
local registered = false
local last_applied
local state

local function bridge()
    local value = rawget(_G, 'HD2CapacityBridge')
    return type(value) == 'table' and value or nil
end

local function log(message)
    local b = bridge()
    if b and type(b.log) == 'function' then pcall(b.log, message) end
    local runtime = rawget(_G, 'hd2')
    if runtime and type(runtime.log) == 'function' then pcall(runtime.log, message) end
end

local function refresh_state()
    local b = bridge()
    if b and type(b.get_snapshot) == 'function' then
        local ok, snapshot = pcall(b.get_snapshot)
        if ok and type(snapshot) == 'table' then
            local valid = CONTRACT.validate(snapshot)
            if valid.accepted then state = snapshot end
        end
    end
    if not state then
        local created, result = CONTRACT.new_state({
            authority = 'client',
            verified_capacity = 4,
            peer_capacity = 4,
            roster_capacity = 4,
            entity_capacity = 4,
            resource_capacity = 4,
            network_capacity = 4,
        })
        if created then state = created else log('capacity state unavailable: ' .. tostring(result.reason)) end
    end
    return state
end

local function status_text()
    local current = refresh_state()
    local b = bridge()
    local compatible = nil
    if b and type(b.client_compatible) == 'function' then
        local ok, value = pcall(b.client_compatible)
        if ok then compatible = value == true end
    end
    if not current then return 'Config Status: Rejected (state unavailable)' end
    return CONTRACT.status(current, compatible)
end

local function values(mom)
    local preset = mom.get(IDS.preset)
    local custom = mom.get(IDS.max_players)
    local preset_name = PRESET_CHOICES[tonumber(preset) or 1] or PRESET_CHOICES[1]
    local apply_index = tonumber(mom.get(IDS.apply_mode)) or 1
    local apply_names = {'next_lobby', 'next_mission', 'restart_required'}
    return {
        preset = preset_name,
        max_players = custom,
        allow_join_in_progress = mom.get(IDS.allow_join) == true,
        require_same_mod_version = mom.get(IDS.same_version) == true,
        apply_mode = apply_names[apply_index] or 'next_lobby',
    }
end

local function restore(mom)
    if not last_applied then return end
    mom.set(IDS.preset, last_applied.preset_index)
    mom.set(IDS.max_players, last_applied.max_players)
    mom.set(IDS.allow_join, last_applied.allow_join_in_progress)
    mom.set(IDS.same_version, last_applied.require_same_mod_version)
    mom.set(IDS.apply_mode, last_applied.apply_mode_index)
end

local function submit(mom, changed_id, changed_value)
    local current = refresh_state()
    if not current then restore(mom) return false end
    local request = values(mom)
    if changed_id == IDS.preset then request.preset = PRESET_CHOICES[tonumber(changed_value) or 1] end
    if changed_id == IDS.max_players then request.max_players = changed_value end
    if changed_id == IDS.allow_join then request.allow_join_in_progress = changed_value == true end
    if changed_id == IDS.same_version then request.require_same_mod_version = changed_value == true end
    if changed_id == IDS.apply_mode then
        request.apply_mode = ({'next_lobby', 'next_mission', 'restart_required'})[tonumber(changed_value) or 1]
    end
    local b = bridge()
    if not b or type(b.stage_config) ~= 'function' or type(b.apply_config) ~= 'function' then
        log('capacity request rejected: native bridge is not ready')
        restore(mom)
        return false
    end
    local ok, staged = pcall(b.stage_config, request)
    if not ok or type(staged) ~= 'table' or staged.accepted ~= true then
        log('capacity request rejected: ' .. tostring(ok and staged and staged.reason or 'bridge_error'))
        restore(mom)
        return false
    end
    local ok_apply, applied = pcall(b.apply_config)
    if not ok_apply or type(applied) ~= 'table' or applied.accepted ~= true then
        log('capacity request rollback: ' .. tostring(ok_apply and applied and applied.reason or 'bridge_error'))
        restore(mom)
        return false
    end
    refresh_state()
    last_applied = {
        preset_index = mom.get(IDS.preset),
        max_players = mom.get(IDS.max_players),
        allow_join_in_progress = mom.get(IDS.allow_join),
        require_same_mod_version = mom.get(IDS.same_version),
        apply_mode_index = mom.get(IDS.apply_mode),
    }
    return true
end

local function register()
    if registered then return end
    local mom = rawget(_G, 'ModOptionsMenu')
    if not mom or mom.api ~= 1 or type(mom.register_option) ~= 'function' then return end
    local description = function() return status_text() end
    local ok, reason
    ok, reason = mom.register_option(IDS.preset, {
        type = 'choice', label = 'Preset', mod = MOD_NAME, choices = PRESET_CHOICES,
        default = 1, description = description,
    })
    if not ok then log('Player Capacity preset registration failed: ' .. tostring(reason)) return end
    ok, reason = mom.register_option(IDS.max_players, {
        type = 'slider', label = 'Max Players', mod = MOD_NAME,
        min = 1, max = 16, step = 1, default = 4, description = description,
    })
    if not ok then log('Player Capacity max registration failed: ' .. tostring(reason)) return end
    ok, reason = mom.register_option(IDS.allow_join, {
        type = 'toggle', label = 'Allow Join In Progress', mod = MOD_NAME,
        default = true, description = description,
    })
    if not ok then log('Player Capacity join registration failed: ' .. tostring(reason)) return end
    ok, reason = mom.register_option(IDS.same_version, {
        type = 'toggle', label = 'Require Same Mod Version', mod = MOD_NAME,
        default = true, description = description,
    })
    if not ok then log('Player Capacity version registration failed: ' .. tostring(reason)) return end
    ok, reason = mom.register_option(IDS.apply_mode, {
        type = 'choice', label = 'Apply Mode', mod = MOD_NAME,
        choices = APPLY_CHOICES, default = 1, description = description,
    })
    if not ok then log('Player Capacity apply registration failed: ' .. tostring(reason)) return end

    mom.on_change(IDS.preset, function(value) submit(mom, IDS.preset, value) end)
    mom.on_change(IDS.max_players, function(value) submit(mom, IDS.max_players, value) end)
    mom.on_change(IDS.allow_join, function(value) submit(mom, IDS.allow_join, value) end)
    mom.on_change(IDS.same_version, function(value) submit(mom, IDS.same_version, value) end)
    mom.on_change(IDS.apply_mode, function(value) submit(mom, IDS.apply_mode, value) end)
    registered = true
    last_applied = {
        preset_index = mom.get(IDS.preset), max_players = mom.get(IDS.max_players),
        allow_join_in_progress = mom.get(IDS.allow_join),
        require_same_mod_version = mom.get(IDS.same_version),
        apply_mode_index = mom.get(IDS.apply_mode),
    }
    log('Player Capacity menu registered; native bridge remains authoritative.')
end

local previous_update = rawget(_G, 'update')
update = function(dt)
    pcall(register)
    if type(previous_update) == 'function' then return previous_update(dt) end
end

return {
    ids = IDS,
    status = status_text,
    register = register,
}
