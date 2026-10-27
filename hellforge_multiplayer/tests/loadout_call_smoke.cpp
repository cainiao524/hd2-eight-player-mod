/* One real owner/session allocator/Windows ABI+SEH flow. Storage state, SDK
 * hooking and native bodies are explicit fixtures; no loader/game access. */
#include "ep_loadout_call.h"
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

#define NEED(x) do {if (!(x)) {fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);exit(1);}} while (0)
extern "C" int EpOwnerInvoke(int (*)(void*),void*,int*);
static HfMod* mod=(HfMod*)(uintptr_t)0x9185;
static uint64_t owner;
static EpLoadoutStorageInfo storage;
static EpLoadoutCallControl control;
static EpLoadoutCallContext contexts[EP_LOADOUT_CALL_COUNT];
static EpSessionCodeInfo gates[EP_LOADOUT_CALL_COUNT];
static unsigned hooks,old_frames,new_frames,old_emissions,new_emissions,policies,quarantines,completed;
static bool fail_native;
using Frame=double (*)(uint64_t,double,uint64_t,uint64_t);
using Emit=uint64_t (*)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
static Frame frame_gate;
static Emit emit_gate;
static const char* Build() {return "25480438";}
static int ReadForbidden(void*,uintptr_t,void*,size_t) {NEED(false);return 0;}
static void UnexpectedBody() {NEED(false);}
static void Held() {NEED(ep_roster_owner_native_status(mod,owner)==EP_OWNER_OK);}
static double OldFrame(uint64_t a,double b,uint64_t c,uint64_t d)
{Held();old_frames++;NEED(a==3 && b==2.25 && c==4 && d==5);return a+b+c+d;}
static uint64_t CheckSix(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f)
{Held();NEED(a==1 && b==2 && c==3 && d==4 && e==50 && f==60);return a+b+c+d+e+f;}
static uint64_t OldEmit(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f)
{old_emissions++;return 1000+CheckSix(a,b,c,d,e,f);}
static uint64_t NewEmit(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f)
{
    new_emissions++;const auto value=CheckSix(a,b,c,d,e,f);
    if (fail_native) RaiseException(0xe04c4402,0,0,nullptr);
    return value;
}
static double NewFrame(uint64_t a,double b,uint64_t c,uint64_t d)
{
    Held();new_frames++;NEED(a==3 && b==2.25 && c==4 && d==5);
    const auto result=emit_gate(1,2,3,4,50,60);Held();completed++;
    return a+b+c+d+result;
}
static int Hook(HfMod* at_mod,uintptr_t at,void* detour,void** next,int32_t)
{
    NEED(at_mod==mod && next && detour);hooks++;
    if (at==storage.binding.setup.common.lifecycle.game+0x1468320) {*next=(void*)&OldFrame;frame_gate=(Frame)detour;}
    else if (at==storage.binding.setup.common.lifecycle.game+0x66BDA0) {*next=(void*)&OldEmit;emit_gate=(Emit)detour;}
    else *next=(void*)&UnexpectedBody;
    return 0; // A fixture assigns SDK's live next pointer; no target is touched.
}
int ep_loadout_storage_info(HfMod* at_mod,uint64_t handle,EpLoadoutStorageInfo* out)
{NEED(at_mod==mod && handle==storage.handle && out);*out=storage;return 1;}
// Screen lifecycle is outside this older focused fixture.
int ep_loadout_storage_screen_return_in_scope(HfMod*,uint64_t,uint64_t,uint32_t) {return 1;}
EpLoadoutStorageResult ep_loadout_storage_screen_in_scope(HfMod*,uint64_t,uint64_t,uint32_t,uint64_t)
{NEED(false);return EP_LOADOUT_STORAGE_STATE;}
int ep_loadout_storage_quarantine_in_scope(HfMod* at_mod,uint64_t handle,uint64_t at_owner)
{
    NEED(at_mod==mod && handle==storage.handle && at_owner==owner && storage.initialization_owner==owner);
    const auto status=ep_roster_owner_native_status(mod,owner);NEED(status==EP_OWNER_OK || status==EP_OWNER_FAULTED);
    quarantines++;storage.state=EP_LOADOUT_STORAGE_QUARANTINED;storage.group={};storage.binding={};return 1;
}
static void Failure(void*,uint32_t rva,EpRosterOwnerResult result,EpRosterCallFrame* frame)
{NEED((rva==0x66BDA0 || rva==0x1468320) && result!=EP_OWNER_OK && frame->status==result);policies++;}
static int Activate(void*,const EpNativeRosterView*)
{
    Held();InterlockedExchange((volatile LONG*)&control.switching,1);
    // Only the route's required state is simulated. Real widget/core migration
    // is outside this one-flow bridge test and cannot be inferred from it.
    storage.state=EP_LOADOUT_STORAGE_UI_MIGRATED;storage.screen_phase=EP_LOADOUT_SCREEN_LIVE;storage.initialization_owner=owner;
    InterlockedExchange((volatile LONG*)&control.active,1);
    InterlockedExchange((volatile LONG*)&control.switching,0);return 1;
}
static int FaultedFrame(void*) {frame_gate(3,2.25,4,5);NEED(false);return 1;}
int main()
{
    HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;
    storage.handle=1;storage.capacity=8;storage.state=EP_LOADOUT_STORAGE_RETAINED;storage.sources_imported=1;
    auto& b=storage.binding.setup.common;b.lifecycle.game=0x180000000;b.roster=0x260000000;b.roster_storage=0x260010000;
    EpNativeRosterView view={};view.game=b.lifecycle.game;view.roster=b.roster;view.storage=b.roster_storage;view.epoch=1;view.build=25480438;
    const EpRosterMemory memory={nullptr,ReadForbidden};NEED(ep_roster_owner_create(mod,&view,&memory,&owner)==EP_OWNER_OK);
#define EP_LOADOUT_CALL(member,rva,stack,chain) storage.group.member=(uintptr_t)&UnexpectedBody;
#include "ep_loadout_call_entries.inc"
#undef EP_LOADOUT_CALL
    storage.group.frame=(uintptr_t)&NewFrame;storage.group.emit_initial_resource_state=(uintptr_t)&NewEmit;
    // A loadout's 22 bodies and a roster's 17 bodies already consume 39 slots,
    // before component33. All new gates must coexist past the old limit 68.
    EpSessionCodeInfo occupied[22+17]={};
    for (auto& code:occupied) NEED(ep_session_code_reserve(&api,mod,0,48,&code));
    EpRosterCallPolicy policy={Failure,nullptr};
    for (unsigned i=0;i<EP_LOADOUT_CALL_COUNT;i++) {
        EpLoadoutCallLayout layout={};NEED(ep_loadout_call_layout(i,&layout));
        NEED(ep_loadout_call_prepare(&api,mod,storage.handle,owner,layout.rva,&control,&policy,0,&contexts[i],&gates[i]));
        NEED(gates[i].registered && gates[i].state==EP_CODE_READY && !hooks);
    }
    for (unsigned i=0;i<EP_LOADOUT_CALL_COUNT;i++)
        NEED(ep_session_code_publish(mod,gates[i].handle,contexts[i].target,0));
    NEED(hooks==EP_LOADOUT_CALL_COUNT && frame_gate && emit_gate);
    NEED(frame_gate(3,2.25,4,5)==14.25 && emit_gate(1,2,3,4,50,60)==1120);
    NEED(old_frames==1 && old_emissions==1 && !new_frames && !new_emissions && !policies);
    NEED(ep_roster_owner_call(mod,owner,1,Activate,nullptr)==EP_OWNER_OK);
    NEED(frame_gate(3,2.25,4,5)==134.25 && completed==1 && new_frames==1 && new_emissions==1);
    fail_native=true;int fault=0;NEED(!EpOwnerInvoke(FaultedFrame,nullptr,&fault) && fault);
    EpRosterOwnerInfo status={};NEED(ep_roster_owner_info(mod,owner,&status)==EP_OWNER_OK && status.fault);
    NEED(storage.state==EP_LOADOUT_STORAGE_QUARANTINED && !storage.group.frame && quarantines==2 && policies==2);
    NEED(!ep_roster_owner_in_scope() && completed==1 && new_frames==2 && new_emissions==2 && old_frames==1 && old_emissions==1);
    for (auto& code:occupied) NEED(ep_session_code_discard(mod,code.handle));
    puts("{\"passed\":true,\"scope\":\"loadout OLD/NEW bridge, nested float and six-argument calls, SEH quarantine\",\"storage_and_native_bodies\":\"test doubles\",\"game_access\":false,\"runtime_verified\":false}");
    return 0;
}
