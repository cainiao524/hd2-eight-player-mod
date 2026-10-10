-- HD2-Addon: mods/cainiao/hd2_capacity_menu
local CONTRACT=require('mods/cainiao/hd2_capacity_contract')
local RUNTIME=require('mods/cainiao/hd2_capacity_runtime')
local MOD_NAME,MOD_ID='Player Capacity','cainiao.player_capacity'
local IDS={preset='hd2.capacity.preset',max_players='hd2.capacity.max_players',
    allow_join='hd2.capacity.allow_join_in_progress',same_version='hd2.capacity.require_same_mod_version',
    apply_mode='hd2.capacity.apply_mode'}
local CHOICES={'Original: 4','5 Players','8 Players','12 Players','16 Players','Custom'}
local MODES={'next_lobby','next_mission','restart_required'}
local registered,dirty=false,false
local service,last_error,last_valid
local registered_ids={}
local function snapshot()
    if not service then
        local ok,value,err=pcall(RUNTIME.connect)
        if ok then service=value;last_error=err and err.reason or nil else last_error='runtime_connection_failed' end
    end
    if not service then return nil end
    local ok,current,err=pcall(service.get_snapshot)
    if ok and current then return current end
    last_error=ok and err and err.reason or 'native_snapshot_failed'
    return nil -- Never reuse a stale host snapshot after a native failure.
end
local function note(message) if service then pcall(service.log,message) end end
local function status_text()
    local current=snapshot()
    if not current then
        return 'Configured Limit: Unknown | Joined Players: Unknown | Available Slots: Unknown | Effective Limit: Unknown | Host Authority: Unknown | Client Compatibility: Unknown | Config Status: Rejected ('..tostring(last_error)..')'
    end
    local text=CONTRACT.status(current,current.client_compatible)
    if last_error then text=text:gsub('Config Status: .*','Config Status: Rejected ('..last_error..')') end
    return text
end
local function settings(current)
    local value=current and (current.pending or current) or {configured_max_players=4,
        allow_join_in_progress=true,require_same_mod_version=true,apply_mode='next_lobby'}
    local preset=6
    for i,n in ipairs({4,5,8,12,16}) do if n==value.configured_max_players then preset=i end end
    local mode=1;for i,n in ipairs(MODES) do if n==value.apply_mode then mode=i end end
    return {[IDS.preset]=preset,[IDS.max_players]=value.configured_max_players,
        [IDS.allow_join]=value.allow_join_in_progress,[IDS.same_version]=value.require_same_mod_version,[IDS.apply_mode]=mode}
end
local function sync(mom,current)
    last_valid=settings(current)
    for _,id in pairs(IDS) do mom.set(id,last_valid[id]) end -- set does not invoke callbacks
end
local function flush()
    if not dirty or not registered then return end
    dirty=false
    local mom=rawget(_G,'ModOptionsMenu')
    local current=snapshot()
    if not current or not service then sync(mom,nil);return end
    local request={preset=CHOICES[mom.get(IDS.preset)],max_players=mom.get(IDS.max_players),
        allow_join_in_progress=mom.get(IDS.allow_join),require_same_mod_version=mom.get(IDS.same_version),
        apply_mode=MODES[mom.get(IDS.apply_mode)]}
    local ok,result=pcall(service.submit_config,request)
    if not ok or type(result)~='table' or result.accepted~=true then
        last_error=ok and type(result)=='table' and result.reason or 'native_submit_failed'
        sync(mom,current);note('capacity request rejected: '..tostring(last_error));return
    end
    last_error=nil
    sync(mom,snapshot() or current)
end
local function register()
    if registered then return end
    local mom=rawget(_G,'ModOptionsMenu')
    if not mom or mom.api~=1 or type(mom.register_option)~='function' or
        type(mom.get)~='function' or type(mom.set)~='function' or type(mom.on_change)~='function' then return end
    local current=snapshot()
    local verified=current and current.verified_capacity or CONTRACT.spec().max_verified_players
    local specs={
        {IDS.preset,{type='choice',label='Preset',choices=CHOICES,default=1}},
        {IDS.max_players,{type='slider',label='Max Players',min=1,max=math.max(2,verified),step=1,default=math.min(4,verified)}},
        {IDS.allow_join,{type='toggle',label='Allow Join In Progress',default=true}},
        {IDS.same_version,{type='toggle',label='Require Same Mod Version',default=true}},
        {IDS.apply_mode,{type='choice',label='Apply Mode',choices={'Next Lobby','Next Mission','Restart Required'},default=1}},
    }
    for _,row in ipairs(specs) do
        local id,spec=row[1],row[2]
        if not registered_ids[id] then
            spec.mod=MOD_NAME;spec.mod_id=MOD_ID;spec.description=status_text
            local ok,why=mom.register_option(id,spec)
            if not ok then last_error='menu_registration_failed';note(tostring(why));return end
            registered_ids[id]=true
        end
    end
    for _,id in pairs(IDS) do mom.on_change(id,function() dirty=true end) end
    sync(mom,current) -- Applied state belongs to the host/native contract.
    registered=true
end
local previous_update=rawget(_G,'update')
update=function(...)
    pcall(register);pcall(flush)
    if type(previous_update)=='function' then return previous_update(...) end
end
local loader=rawget(_G,'CowboyBingusModLoader')
if loader and loader.capabilities and loader.capabilities.after_startup then loader.after_startup(register) end
return {ids=IDS,status=status_text,register=register,flush=flush}
