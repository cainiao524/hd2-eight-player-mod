// Standalone synthetic fixture ONLY. Never linked into a gameplay payload.
#include "ep_capacity_control.h"
static EP_NATIVE_BRIDGE fixture{};
static EP_CONTROL_ENVIRONMENT env{};
static UINT32 native_limit = 4, commits = 0, rollbacks = 0, leases = 0;
static bool fail_commit = false, fail_rollback = false;
static BYTE bytes[]{0x90,0x90};
static EP_BRIDGE_SITE site{0, bytes, sizeof(bytes)};
static EP_BRIDGE_STATUS __cdecl retain(void*) { ++leases; return EP_BRIDGE_OK; }
static void __cdecl release(void*) { --leases; }
static EP_BRIDGE_STATUS __cdecl player(void*,UINT64,UINT64,UINT8) { return EP_BRIDGE_OK; }
static EP_BRIDGE_STATUS __cdecl allocate(void*,UINT64,UINT64,UINT8* out) {
    for (UINT8 i=0;i<native_limit;++i) if (!fixture.sidecar.slots[i].state) { *out=i; return EP_BRIDGE_OK; }
    return EP_BRIDGE_NO_SLOT;
}
static EP_BRIDGE_STATUS __cdecl release_index(void*,UINT64,UINT64,UINT8,UINT32) { return EP_BRIDGE_OK; }
static BOOL __cdecl inspect(void*, EP_CONTROL_ENVIRONMENT* out) { *out=env; return TRUE; }
static BOOL __cdecl commit(void*,const EP_CAPACITY_CONTRACT*,const EP_CAPACITY_CONTRACT* after) {
    ++commits; native_limit=after->effective_max_players; return !fail_commit;
}
static BOOL __cdecl rollback(void*, const EP_CAPACITY_CONTRACT* before) {
    ++rollbacks; if(fail_rollback)return FALSE; native_limit=before->effective_max_players; return TRUE;
}
extern "C" __declspec(dllexport) UINT32 fixture_start() {
    if(fixture.magic)return EP_CTL_BUSY;
    env={1,TRUE,TRUE,TRUE,TRUE,FALSE,TRUE,TRUE};
    native_limit=4; commits=rollbacks=leases=0; fail_commit=fail_rollback=false;
    EP_CAPACITY_CONTRACT c{};
    c.version=1;c.build=EP_CAPACITY_BUILD;c.configured_max_players=4;
    c.peer_capacity=c.roster_capacity=c.entity_capacity=c.resource_capacity=c.network_capacity=c.verified_capacity=8;
    c.quiescent=TRUE;c.allow_join_in_progress=c.require_same_mod_version=TRUE;
    EP_BRIDGE_CONFIG config{};
    config.steam_build=EP_CAPACITY_BUILD; config.game_module=reinterpret_cast<HMODULE>(bytes);
    config.sites=&site;config.site_count=1;config.owner=&env;config.capacity=&c;
    config.confirm_peer=player;config.create_player=player;config.remove_player=player;
    config.retain_owner=retain;config.release_owner=release;
    config.allocate_index=allocate;config.release_index=release_index;
    if(ep_bridge_init(&fixture,&config)!=EP_BRIDGE_OK || ep_bridge_preflight(&fixture)!=EP_BRIDGE_OK)return 100;
    EP_CONTROL_PROVIDER p{sizeof(p),1,inspect,commit,rollback};
    return ep_control_bind(&fixture,&p);
}
extern "C" __declspec(dllexport) UINT32 fixture_stop() {
    auto result=ep_control_unbind(); if(result!=EP_CTL_OK)return result;
    for(UINT8 i=0;i<EP_SIDECAR_CAPACITY;++i) {
        const auto& s=fixture.sidecar.slots[i];
        if(s.state) { EP_BRIDGE_ADMISSION a{s.peer_id,s.resource_handle,{i,{0,0,0},s.generation}};
            if(ep_bridge_depart(&fixture,a)!=EP_BRIDGE_OK)return 101; }
    }
    return ep_bridge_destroy(&fixture);
}
extern "C" __declspec(dllexport) UINT32 fixture_boundary(UINT32 b) { return ep_control_boundary(static_cast<EP_CAPACITY_APPLY_MODE>(b)); }
extern "C" __declspec(dllexport) UINT32 fixture_submit(UINT32 requested, UINT32 mode) {
    EP_CONTROL_SNAPSHOT snapshot{};
    const auto observed=ep_control_snapshot(&snapshot,sizeof(snapshot));
    if (observed!=EP_CTL_OK && observed!=EP_CTL_ROLLBACK_REQUIRED) return observed;
    EP_CONTROL_REQUEST request{};
    request.size=sizeof(request);request.abi=EP_CONTROL_ABI;
    request.binding_epoch=snapshot.binding_epoch;request.authority_epoch=snapshot.authority_epoch;
    request.expected_generation=snapshot.capacity.generation;
    request.config.version=EP_CAPACITY_CONTRACT_VERSION;request.config.build=EP_CAPACITY_BUILD;
    request.config.configured_max_players=requested;request.config.allow_join_in_progress=TRUE;
    request.config.require_same_mod_version=TRUE;request.config.apply_mode=static_cast<EP_CAPACITY_APPLY_MODE>(mode);
    return ep_control_submit(&request,sizeof(request));
}
extern "C" __declspec(dllexport) UINT32 fixture_admit(UINT32 n) { EP_BRIDGE_ADMISSION a{};return ep_bridge_admit(&fixture,n+1,n+100,&a); }
extern "C" __declspec(dllexport) void fixture_flags(UINT32 host,UINT32 compatible,UINT32 quiet,UINT32 mission,UINT32 epoch_value) {
    env.host_authority=host;env.client_compatible=compatible;env.quiescent=quiet;env.mission_active=mission;env.authority_epoch=epoch_value;
}
extern "C" __declspec(dllexport) void fixture_fail(UINT32 commit_fail,UINT32 rollback_fail) { fail_commit=commit_fail!=0;fail_rollback=rollback_fail!=0; }
extern "C" __declspec(dllexport) UINT32 fixture_value(UINT32 id) {
    return id==0?native_limit:id==1?fixture.sidecar.capacity:id==2?commits:id==3?rollbacks:id==4?leases:fixture.sidecar.active_count;
}
