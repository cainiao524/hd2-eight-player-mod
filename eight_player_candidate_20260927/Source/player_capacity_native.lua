-- Only calls our size/version checked API. Never reads a game pointer or RVA,
-- installs a hook, loads an uninstalled plugin, or registers game callbacks.
local M = {}
local ffi = require('ffi')
if not pcall(ffi.typeof, 'hd2capctl1_snapshot') then
    ffi.cdef [[
    typedef struct { unsigned int version, build, configured_max_players, effective_max_players,
        peer_capacity, roster_capacity, entity_capacity, resource_capacity, network_capacity,
        verified_capacity, joined_players, generation;
        int allow_join_in_progress, require_same_mod_version, mission_active, quiescent;
        unsigned int apply_mode; } hd2capctl1_contract;
    typedef struct { unsigned int version, build, configured_max_players;
        int allow_join_in_progress, require_same_mod_version; unsigned int apply_mode; } hd2capctl1_config;
    typedef struct { unsigned int size, abi, binding_epoch, authority_epoch, expected_generation;
        hd2capctl1_config config; } hd2capctl1_request;
    typedef struct { unsigned int size, abi, status, binding_epoch, authority_epoch,
        host_authority, client_compatible, pending, last_result;
        hd2capctl1_contract capacity; hd2capctl1_config pending_config; } hd2capctl1_snapshot;
    typedef unsigned int (__cdecl *hd2capctl1_uint_fn)(void);
    typedef unsigned int (__cdecl *hd2capctl1_snapshot_fn)(hd2capctl1_snapshot*, unsigned int);
    typedef unsigned int (__cdecl *hd2capctl1_submit_fn)(const hd2capctl1_request*, unsigned int);
    int GetModuleHandleExA(unsigned long flags, const char* name, void** out);
    void* GetProcAddress(void* module, const char* name);
    int FreeLibrary(void* module);
    ]]
end
local reasons = {[0]='ready', 'native_provider_unbound', 'native_busy', 'native_abi_mismatch',
    'native_not_ready', 'host_authority_required', 'stale_session_or_generation',
    'invalid_capacity_request', 'native_commit_rejected', 'pending', 'native_rollback_required'}
local modes = {'next_lobby', 'next_mission', 'restart_required'}
local keys = {'configured_max_players','effective_max_players','peer_capacity','roster_capacity',
    'entity_capacity','resource_capacity','network_capacity','verified_capacity','joined_players','generation'}
local function failure(code) return {accepted=false, reason=reasons[code] or 'native_error', code=code} end
local function config(raw)
    return {configured_max_players=tonumber(raw.configured_max_players),
        allow_join_in_progress=raw.allow_join_in_progress==1,
        require_same_mod_version=raw.require_same_mod_version==1,
        apply_mode=modes[tonumber(raw.apply_mode)+1]}
end
-- Injectable function table for standalone DLL tests. The game entry below
-- resolves only the installed plugin which is already loaded.
function M.from_api(api, keepalive)
    if api.abi() ~= 1 or api.snapshot_size() ~= ffi.sizeof('hd2capctl1_snapshot') or
        api.request_size() ~= ffi.sizeof('hd2capctl1_request') then return nil, failure(3) end
    local out = ffi.new('hd2capctl1_snapshot[1]')
    local request = ffi.new('hd2capctl1_request[1]')
    local instance = {keepalive=keepalive}
    function instance.snapshot()
        local code = tonumber(api.snapshot(out, ffi.sizeof(out)))
        if code ~= 0 then return nil, failure(code) end
        local s = out[0]
        if s.size ~= ffi.sizeof(out) or s.abi ~= 1 or s.capacity.version ~= 1 or
            s.capacity.build ~= 25480438 then return nil, failure(3) end
        local current = config(s.capacity)
        for _, key in ipairs(keys) do current[key] = tonumber(s.capacity[key]) end
        current.binding_epoch=tonumber(s.binding_epoch); current.authority_epoch=tonumber(s.authority_epoch)
        current.authority=s.host_authority==1 and 'host' or 'client'
        current.client_compatible=s.client_compatible==1
        current.mission_active=s.capacity.mission_active==1; current.quiescent=s.capacity.quiescent==1
        current.pending=s.pending==1 and config(s.pending_config) or nil
        current.last_result=tonumber(s.last_result)
        return current
    end
    function instance.submit(current, desired)
        local r=request[0]
        r.size=ffi.sizeof(request); r.abi=1; r.binding_epoch=current.binding_epoch
        r.authority_epoch=current.authority_epoch; r.expected_generation=current.generation
        r.config.version=1; r.config.build=25480438
        r.config.configured_max_players=desired.max_players
        r.config.allow_join_in_progress=desired.allow_join_in_progress and 1 or 0
        r.config.require_same_mod_version=desired.require_same_mod_version and 1 or 0
        local mode
        for i, name in ipairs(modes) do if name==desired.apply_mode then mode=i-1 end end
        if mode==nil then return failure(7) end
        r.config.apply_mode=mode
        local code=tonumber(api.submit(request, ffi.sizeof(request)))
        if code==9 then return {accepted=true,reason='pending',code=code} end
        return failure(code)
    end
    return instance
end
function M.connect()
    local windows=ffi.load('kernel32')
    local handle=ffi.new('void*[1]')
    if windows.GetModuleHandleExA(0, 'eight_player_pluginw64_release.dll', handle)==0 then
        return nil, {accepted=false,reason='native_plugin_not_loaded'}
    end
    -- Keep a module reference while FFI function pointers can still be used.
    local owned=ffi.gc(ffi.cast('void*',handle[0]), windows.FreeLibrary)
    local api={}
    for _, row in ipairs({{'abi','ep_control_abi','hd2capctl1_uint_fn'},
        {'snapshot_size','ep_control_snapshot_size','hd2capctl1_uint_fn'},
        {'request_size','ep_control_request_size','hd2capctl1_uint_fn'},
        {'snapshot','ep_control_snapshot','hd2capctl1_snapshot_fn'},
        {'submit','ep_control_submit','hd2capctl1_submit_fn'}}) do
        local address=windows.GetProcAddress(owned,row[2])
        if address==nil then return nil,failure(3) end
        api[row[1]]=ffi.cast(row[3],address)
    end
    return M.from_api(api,owned)
end
return M
