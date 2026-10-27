/* Saved 1465820 wrapper, with ONLY its call/jump operands redirected to owned
 * gates. Real bridge, allocator, owner and Windows unwind; cleanup/setup/storage
 * are fixtures. No game process, installed file, native game helper or loader.
 * One OLD -> NEW reset flow with a queued caller and a cleanup failure. */
#include "ep_loadout_call.h"
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#define NEED(x) do {if (!(x)) {fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);exit(1);}} while (0)
extern "C" int EpOwnerInvoke(int (*)(void*),void*,int*);
static HfMod* mod=(HfMod*)(uintptr_t)0x9187;
static uint64_t owner;
static EpLoadoutStorageInfo storage;
static EpLoadoutCallControl control;
static EpLoadoutCallContext contexts[4];
static EpSessionCodeInfo gates[4],wrapper;
static unsigned old_release,new_release,old_setup,new_setup,alternate,policies,stage;
static bool queue_call,fail_release;
static HANDLE requested,started,completed;
static volatile LONG queued;
static const uintptr_t screen=0x220000000;
using Rebuild=uint64_t (*)(uintptr_t);
static Rebuild rebuild;
static const char* Build() {return "25480438";}
static int ReadForbidden(void*,uintptr_t,void*,size_t) {NEED(false);return 0;}
static void Held(uintptr_t at)
{NEED(at==screen && ep_roster_owner_native_status(mod,owner)==EP_OWNER_OK);}
static void OldRelease(uintptr_t at) {Held(at);NEED(!stage);old_release++;stage=1;}
static uint64_t OldSetup(uintptr_t at) {Held(at);NEED(stage==1);old_setup++;stage=0;return 0x5e704;}
static void NewRelease(uintptr_t at)
{
    Held(at);NEED(!stage);new_release++;stage=2;
    if (fail_release) RaiseException(0xe04c4404,0,0,nullptr);
    if (queue_call) {
        NEED(SetEvent(requested) && WaitForSingleObject(started,2000)==WAIT_OBJECT_0);
        NEED(WaitForSingleObject(completed,0)==WAIT_TIMEOUT);
    }
}
static uint64_t NewSetup(uintptr_t at)
{
    Held(at);NEED(stage==2 && !queued && WaitForSingleObject(completed,0)==WAIT_TIMEOUT);
    new_setup++;stage=0;return 0x5e708;
}
static void Alternate(uintptr_t at) {Held(at);NEED(!stage);alternate++;}
static int Hook(HfMod* at_mod,uintptr_t at,void*,void** next,int32_t)
{
    NEED(at_mod==mod);
    switch (at-storage.binding.setup.common.lifecycle.game) {
    case 0x1467330:*next=(void*)&OldRelease;break;
    case 0x1467720:*next=(void*)&Alternate;break;
    case 0x1466170:*next=(void*)&OldSetup;break;
    case 0x1465820:*next=(void*)wrapper.base;break;
    default:NEED(false);
    }
    return 0;
}
int ep_loadout_storage_info(HfMod* at_mod,uint64_t handle,EpLoadoutStorageInfo* out)
{NEED(at_mod==mod && handle==storage.handle);*out=storage;return 1;}
// Screen lifecycle is outside this older focused fixture.
int ep_loadout_storage_screen_return_in_scope(HfMod*,uint64_t,uint64_t,uint32_t) {return 1;}
EpLoadoutStorageResult ep_loadout_storage_screen_in_scope(HfMod*,uint64_t,uint64_t,uint32_t,uint64_t)
{NEED(false);return EP_LOADOUT_STORAGE_STATE;}
int ep_loadout_storage_quarantine_in_scope(HfMod* at_mod,uint64_t handle,uint64_t at_owner)
{
    NEED(at_mod==mod && handle==storage.handle && at_owner==owner && storage.initialization_owner==owner);
    const auto status=ep_roster_owner_native_status(mod,owner);NEED(status==EP_OWNER_OK || status==EP_OWNER_FAULTED);
    storage.state=EP_LOADOUT_STORAGE_QUARANTINED;storage.group={};storage.binding={};return 1;
}
static void Failure(void*,uint32_t rva,EpRosterOwnerResult result,EpRosterCallFrame* frame)
{NEED((rva==0x1467330 || rva==0x1465820) && result!=EP_OWNER_OK && frame->status==result);policies++;}
static int Activate(void*,const EpNativeRosterView*)
{
    Held(screen);storage.state=EP_LOADOUT_STORAGE_UI_MIGRATED;storage.screen_phase=EP_LOADOUT_SCREEN_LIVE;storage.initialization_owner=owner;
    InterlockedExchange((volatile LONG*)&control.active,1);return 1;
}
static int Queued(void*,const EpNativeRosterView*)
{Held(screen);NEED(stage==0 && new_setup==1);InterlockedIncrement(&queued);return 1;}
static DWORD WINAPI Worker(void*)
{
    NEED(WaitForSingleObject(requested,2000)==WAIT_OBJECT_0 && SetEvent(started));
    NEED(ep_roster_owner_call(mod,owner,0,Queued,nullptr)==EP_OWNER_OK && SetEvent(completed));return 0;
}
static int FaultedRebuild(void*) {rebuild(screen);NEED(false);return 1;}
static void Relative(uint8_t* output,uintptr_t after,uintptr_t target)
{const int64_t delta=(int64_t)target-after;NEED(delta>=INT32_MIN && delta<=INT32_MAX);const auto rel=(int32_t)delta;memcpy(output,&rel,4);}
int main()
{
    HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;
    storage.handle=1;storage.capacity=8;storage.state=EP_LOADOUT_STORAGE_RETAINED;storage.sources_imported=1;
    auto& b=storage.binding.setup.common;b.lifecycle.game=0x180000000;b.lifecycle.screen=screen;
    b.roster=0x260000000;b.roster_storage=0x260010000;
    EpNativeRosterView view={};view.game=b.lifecycle.game;view.roster=b.roster;view.storage=b.roster_storage;view.epoch=1;view.build=25480438;
    EpRosterMemory memory={nullptr,ReadForbidden};NEED(ep_roster_owner_create(mod,&view,&memory,&owner)==EP_OWNER_OK);
    storage.group.release=(uintptr_t)&NewRelease;storage.group.alternate_release=(uintptr_t)&Alternate;
    storage.group.setup=(uintptr_t)&NewSetup;
    const uint32_t rvas[]={0x1467330,0x1467720,0x1466170,0x1465820};EpRosterCallPolicy policy={Failure,nullptr};
    for (unsigned i=0;i<4;i++) {
        NEED(ep_loadout_call_prepare(&api,mod,storage.handle,owner,rvas[i],&control,&policy,0,&contexts[i],&gates[i]));
        NEED(contexts[i].route==(i==3));
    }
    // Exact saved 1465820..146583B and its unwind bytes from the workspace
    // capture. Only rel32 operands change; no target calls game memory.
    const uint8_t saved[]={0x40,0x53,0x48,0x83,0xec,0x20,0x48,0x8b,0xd9,0xe8,0x02,0x1b,0,0,
        0x48,0x8b,0xcb,0x48,0x83,0xc4,0x20,0x5b,0xe9,0x35,0x09,0,0};
    const uint8_t unwind[]={1,6,2,0,6,0x32,2,0x30};
    uint8_t image[52]={};memcpy(image,saved,sizeof(saved));memcpy(image+32,unwind,sizeof(unwind));
    const uint32_t row[]={0,sizeof(saved),32};memcpy(image+40,row,sizeof(row));
    NEED(ep_session_code_reserve(&api,mod,0,sizeof(image),&wrapper));
    Relative(image+10,wrapper.base+14,gates[0].base);Relative(image+23,wrapper.base+27,gates[2].base);
    NEED(ep_session_code_seal(mod,wrapper.handle,image,sizeof(image),40));
    NEED(ep_session_code_retain_set(mod,&wrapper.handle,1));
    for (unsigned i=0;i<4;i++) NEED(ep_session_code_publish(mod,gates[i].handle,contexts[i].target,0));
    rebuild=(Rebuild)gates[3].base;
    NEED(rebuild(screen)==0x5e704 && old_release==1 && old_setup==1 && !new_release && !new_setup);
    NEED(ep_roster_owner_call(mod,owner,1,Activate,nullptr)==EP_OWNER_OK);
    requested=CreateEventA(nullptr,TRUE,FALSE,nullptr);started=CreateEventA(nullptr,TRUE,FALSE,nullptr);
    completed=CreateEventA(nullptr,TRUE,FALSE,nullptr);NEED(requested && started && completed);
    queue_call=true;HANDLE worker=CreateThread(nullptr,0,Worker,nullptr,0,nullptr);NEED(worker);
    NEED(rebuild(screen)==0x5e708 && new_release==1 && new_setup==1);
    NEED(WaitForSingleObject(worker,2000)==WAIT_OBJECT_0 && WaitForSingleObject(completed,0)==WAIT_OBJECT_0 && queued==1);
    NEED(CloseHandle(worker) && CloseHandle(requested) && CloseHandle(started) && CloseHandle(completed));queue_call=false;
    ((void(*)(uintptr_t))gates[1].base)(screen);NEED(alternate==1 && !stage);
    fail_release=true;int fault=0;NEED(!EpOwnerInvoke(FaultedRebuild,nullptr,&fault) && fault);
    EpRosterOwnerInfo status={};NEED(ep_roster_owner_info(mod,owner,&status)==EP_OWNER_OK && status.fault);
    NEED(storage.state==EP_LOADOUT_STORAGE_QUARANTINED && policies==2 && !ep_roster_owner_in_scope());
    NEED(new_release==2 && new_setup==1 && old_release==1 && old_setup==1);
    puts("{\"passed\":true,\"scope\":\"saved reset wrapper, routed cleanup/setup, whole-call ownership and fault short circuit\",\"cleanup_setup_and_storage\":\"test doubles\",\"game_access\":false,\"runtime_verified\":false}");
    return 0;
}
