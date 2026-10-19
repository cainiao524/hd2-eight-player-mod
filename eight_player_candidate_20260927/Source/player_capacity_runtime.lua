-- HD2Runtime supplies mod-owned diagnostics; our native API is the capacity
-- writer. No hd2.patch to a guessed player-count field is performed.
local CONTRACT=require('mods/cainiao/hd2_capacity_contract')
local M={}
local MODES={next_lobby=true,next_mission=true,restart_required=true}
local function failure(reason)
    return {accepted=false,reason=reason}
end
function M.new(native, runtime)
    if type(native)~='table' or type(native.snapshot)~='function' or type(native.submit)~='function' then
        return nil,failure('native_api_invalid')
    end
    if type(runtime)~='table' or type(runtime.mod)~='function' then
        return nil,failure('hd2runtime_api_invalid')
    end
    local mod=runtime.mod('mods/cainiao/hd2_capacity_menu')
    if type(mod)~='table' or type(mod.log)~='function' then
        return nil,failure('hd2runtime_mod_log_unavailable')
    end
    local self={}
    function self.log(message) mod:log(message) end
    function self.get_snapshot()
        local current,err=native.snapshot()
        if not current then return nil,err end
        if type(current)~='table' then return nil,failure('native_snapshot_invalid') end
        current.profile=CONTRACT.spec()
        local valid=CONTRACT.validate(current)
        if not valid.accepted then return nil,valid end
        if current.effective_max_players~=valid.effective_max_players then
            return nil,{accepted=false,reason='native_effective_capacity_mismatch'}
        end
        return current
    end
    function self.submit_config(request)
        if type(request)~='table' then return failure('request_not_table') end
        if type(request.allow_join_in_progress)~='boolean' or
            type(request.require_same_mod_version)~='boolean' then
            return failure('configuration_flags_invalid')
        end
        if type(request.apply_mode)~='string' or not MODES[request.apply_mode] then
            return failure('apply_mode_invalid')
        end
        local current,err=self.get_snapshot()
        if not current then return err or failure('native_snapshot_failed') end
        if current.authority~='host' then return {accepted=false,reason='host_authority_required'} end
        local value=CONTRACT.preset_value(request.preset,request.max_players)
        if type(value)~='number' or value~=math.floor(value) or value<1 or value>current.verified_capacity then
            return {accepted=false,reason='configured_capacity_invalid'}
        end
        if type(request.allow_join_in_progress)~='boolean' or type(request.require_same_mod_version)~='boolean' then
            return {accepted=false,reason='configuration_flags_invalid'}
        end
        local desired={max_players=value,allow_join_in_progress=request.allow_join_in_progress,
            require_same_mod_version=request.require_same_mod_version,apply_mode=request.apply_mode}
        local result=native.submit(current,desired)
        if type(result)~='table' or type(result.accepted)~='boolean' or type(result.reason)~='string' then
            self.log('capacity request rejected: native_submit_invalid')
            return failure('native_submit_invalid')
        end
        self.log('capacity request: '..tostring(result.reason)..' limit='..value..' generation='..current.generation)
        return result
    end
    return self
end
function M.connect()
    local ok,runtime=pcall(require,'mods/skyeshade/hd2runtime')
    if not ok or type(runtime)~='table' or type(runtime.mod)~='function' then
        return nil,{reason='hd2runtime_unavailable'}
    end
    local loaded,native_module=pcall(require,'mods/cainiao/hd2_capacity_native')
    if not loaded or type(native_module)~='table' or type(native_module.connect)~='function' then
        return nil,failure('native_ffi_unavailable')
    end
    local called,native,err=pcall(native_module.connect)
    if not called then return nil,{reason='native_connection_failed'} end
    if not native then return nil,err or failure('native_provider_unbound') end
    return M.new(native,runtime)
end
return M
