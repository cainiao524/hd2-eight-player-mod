/* One exit -> park -> reopen -> setup -> failed-reopen flow. Real storage,
 * owner, call bridge, session allocator, published gates and Windows SEH.
 * Screen/group bodies and SDK publication are explicit test doubles; every
 * dereferenced address belongs to this disposable process. No game access. */
#include "ep_loadout_call.h"
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vector>
#define NEED(x) do {if (!(x)) {fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);exit(1);}} while (0)
extern "C" int EpOwnerInvoke(int (*)(void*),void*,int*);
static HfMod* mod=(HfMod*)(uintptr_t)0x9189;
static uint64_t owner,storage,screen;
static uint64_t manager[32];
static EpLoadoutStorageInfo binding;
static EpLoadoutSourceSnapshot source;
static EpLoadoutCallControl control;
static EpLoadoutCallContext contexts[4];
static EpSessionCodeInfo gates[4];
static unsigned initialized,attached,constructed,exited,configured,old_calls,policies;
static bool fail_constructor;
struct Bank {uint64_t address;uint32_t bytes;std::vector<unsigned char> expected;};
static Bank banks[8];
static const char* Build() {return "25480438";}
static int ReadForbidden(void*,uintptr_t,void*,size_t) {NEED(false);return 0;}
static void Held() {NEED(ep_roster_owner_native_status(mod,owner)==EP_OWNER_OK);}
static EpLoadoutStorageInfo Info()
{EpLoadoutStorageInfo out={};NEED(ep_loadout_storage_info(mod,storage,&out));return out;}
static void SameSources()
{for (const auto& b:banks) NEED(!memcmp((void*)(uintptr_t)b.address,b.expected.data(),b.bytes));}
static void Filled(uint64_t address,uint32_t bytes,unsigned char value)
{const auto* p=(const unsigned char*)(uintptr_t)address;for (uint32_t i=0;i<bytes;i++) NEED(p[i]==value);}
static void* Initialize(void* at) {Held();NEED((uintptr_t)at==screen);initialized++;return at;}
static void Attach(void* at) {Held();NEED((uintptr_t)at==screen);attached++;}
static void* Construct(void* at)
{
    Held();NEED((uintptr_t)at==screen && !manager[0xb0/8]);
    NEED(Info().screen_phase==EP_LOADOUT_SCREEN_REBUILDING);constructed++;
    const auto& b=binding.binding.setup.common;const auto& l=b.lifecycle;
    Filled(screen,EP_LOADOUT_SCREEN_BYTES,0);
    Filled(l.records,8*EP_LOADOUT_RECORD_BYTES,0);Filled(l.widgets,8*EP_LOADOUT_WIDGET_BYTES,0);
    Filled(b.forward_map,32,0xff);Filled(b.inverse_map,32,0xff);SameSources();
    for (unsigned i=0;i<8;i++) *(uint32_t*)(uintptr_t)(l.records+i*EP_LOADOUT_RECORD_BYTES)=0x100+i;
    if (fail_constructor) RaiseException(0xe04c4405,0,0,nullptr);
    return at;
}
static void Exit(void* at)
{
    Held();NEED((uintptr_t)at==screen);exited++;
    // Preserve the CURRENT post-cleanup contents, not the initial import.
    for (auto& b:banks) {
        memset((void*)(uintptr_t)b.address,0x30+exited,b.bytes);
        b.expected.assign(b.bytes,(unsigned char)(0x30+exited));
    }
}
static void Setup(void* at)
{
    Held();NEED((uintptr_t)at==screen);configured++;
    const auto& b=binding.binding.setup.common;
    // Fresh maps stay unmapped until setup learns the current local index 7.
    Filled(b.forward_map,32,0xff);Filled(b.inverse_map,32,0xff);
    ((uint32_t*)(uintptr_t)b.forward_map)[7]=0;((uint32_t*)(uintptr_t)b.inverse_map)[0]=7;
}
static uint64_t Original(void* at,uint32_t kind)
{Held();NEED(at==manager && kind==12);old_calls++;return 0xabc;}
static int Hook(HfMod* at_mod,uintptr_t,void*,void** next,int32_t)
{NEED(at_mod==mod);*next=(void*)&Original;return 0;}
static void Failure(void*,uint32_t rva,EpRosterOwnerResult result,EpRosterCallFrame* frame)
{NEED(rva==0x14984e0 && result!=EP_OWNER_OK && frame->status==result);policies++;}
EpPropertyResult ep_loadout_group_prepare(const HfApi* api,HfMod* at_mod,const EpLoadoutGroupAddresses*,EpLoadoutGroup* out)
{
    *out={};out->capacity=8;out->state=EP_LOADOUT_GROUP_READY;
    out->construct_banks=(uintptr_t)&Initialize;out->replace_widgets=(uintptr_t)&Attach;
    out->constructor=(uintptr_t)&Construct;out->exit_screen=(uintptr_t)&Exit;out->setup=(uintptr_t)&Setup;
    // Retention is real, but these placeholder images are never native bodies.
    uint8_t image[20]={0xc3,0,0,0,1};const uint32_t row[]={0,1,4};memcpy(image+8,row,sizeof(row));
    for (auto& code:out->code) {
        NEED(ep_session_code_reserve(api,at_mod,0,sizeof(image),&code));
        NEED(ep_session_code_seal(at_mod,code.handle,image,sizeof(image),8));
        NEED(ep_session_code_info(at_mod,code.handle,&code));
    }
    return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_group_discard(HfMod*,EpLoadoutGroup*) {NEED(false);return EP_PROPERTY_OK;}
int ep_loadout_maps_initialize(EpLoadoutMaps* out,uint32_t capacity,uint32_t local)
{NEED(capacity==8 && local==0);memset(out,0xff,sizeof(*out));out->network_to_slot[0]=0;out->slot_to_network[0]=0;return 1;}
static int Activate(void*,const EpNativeRosterView*)
{
    NEED(ep_loadout_storage_initialize_in_scope(mod,storage,owner,&source)==EP_LOADOUT_STORAGE_OK);
    control.active=1;return 1;
}
static int RefuseEarly(void*,const EpNativeRosterView*)
{
    NEED(ep_loadout_storage_screen_in_scope(mod,storage,owner,0x14ac340,(uintptr_t)manager)==EP_LOADOUT_STORAGE_STATE);
    NEED(manager[0xb0/8]==screen);return 1;
}
static int RefuseStale(void*,const EpNativeRosterView*)
{
    manager[0xb0/8]=screen;
    NEED(ep_loadout_storage_screen_in_scope(mod,storage,owner,0x14984e0,(uintptr_t)manager)==EP_LOADOUT_STORAGE_STALE);
    NEED(Info().screen_phase==EP_LOADOUT_SCREEN_PARKED && !constructed);manager[0xb0/8]=0;return 1;
}
using Factory=uint64_t (*)(void*,uint32_t);
using ScreenCall=void (*)(void*);
static int FailedReopen(void*) {((Factory)gates[2].base)(manager,11);NEED(false);return 1;}
int main()
{
    HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;
    screen=(uintptr_t)VirtualAlloc(nullptr,EP_LOADOUT_SCREEN_BYTES,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);NEED(screen);
    EpLoadoutStorageBindings input={};auto& a=input.group;auto& l=a.setup.common.lifecycle;
    l={0x180000000,0,screen,0,0,0x191000000,8,0};
    a.setup.common.roster=0x260000000;a.setup.common.roster_storage=0x260010000;
    a.record_source.manager=0x2a0000000;a.countdown_source.manager=0x2b0000000;
    a.resource_owner_source.owner=0x2c0000000;input.invalid_resource_id=0xffffffff;
    uint64_t* fields[]={&a.lifecycle_code,&a.consumers_code,&l.code,&a.interactions_code,&a.refresh_code,
        &a.records_code,&a.frame_code,&a.mode_code,&a.control_code,&a.state_code,&a.prompt_code,&a.countdown_code,
        &a.resources_code,&a.resource_owner_code,&a.resource_tick_code,&a.resource_events_code,&a.resource_ownership_code,
        &a.resource_sync_code,&a.resource_signals_code,&a.resource_actions_code,&a.resource_main_code,&a.resource_update_code};
    for (unsigned i=0;i<EP_LOADOUT_GROUP_CODE_COUNT;i++) *fields[i]=0x190000000+i*0x10000;
    NEED(ep_loadout_storage_prepare(&api,mod,&input,&binding)==EP_LOADOUT_STORAGE_OK);storage=binding.handle;
    source.game=l.game;source.record_manager=source.global_record_manager=a.record_source.manager;
    source.countdown_manager=source.global_countdown_manager=a.countdown_source.manager;
    source.resource_owner=source.global_resource_owner=a.resource_owner_source.owner;
    NEED(ep_loadout_storage_import_sources(mod,storage,&source)==EP_LOADOUT_STORAGE_OK);
    NEED(ep_loadout_storage_retain_sources(mod,storage,&source)==EP_LOADOUT_STORAGE_OK);
    EpNativeRosterView view={};view.game=l.game;view.roster=a.setup.common.roster;view.storage=a.setup.common.roster_storage;
    view.epoch=1;view.build=25480438;EpRosterMemory memory={nullptr,ReadForbidden};
    NEED(ep_roster_owner_create(mod,&view,&memory,&owner)==EP_OWNER_OK);
    const uint32_t rvas[]={0x1467b90,0x1466170,0x14984e0,0x14ac340};EpRosterCallPolicy policy={Failure,nullptr,nullptr};
    for (unsigned i=0;i<4;i++) {
        NEED(ep_loadout_call_prepare(&api,mod,storage,owner,rvas[i],&control,&policy,0,&contexts[i],&gates[i]));
        NEED(ep_session_code_publish(mod,gates[i].handle,contexts[i].target,0));
    }
    manager[0xb0/8]=screen;
    NEED(((Factory)gates[2].base)(manager,12)==0xabc && old_calls==1);
    NEED(ep_roster_owner_call(mod,owner,1,Activate,nullptr)==EP_OWNER_OK && initialized==1 && attached==1);
    binding=Info();const auto& b=binding.binding;const auto& c=b.setup.common;
    const uint64_t addresses[]={b.record_source.actors,b.record_source.equipment,b.record_source.status,
        b.countdown_source.resources,b.resource_owner_source.objects,b.resource_owner_source.phases,
        b.resource_owner_source.rows,b.resource_owner_source.states};
    const uint32_t strides[]={8,0x40,0x44,0x4c,8,12,20,4};
    for (unsigned i=0;i<8;i++) {banks[i].address=addresses[i];banks[i].bytes=8*strides[i];}
    memset((void*)(uintptr_t)screen,0xa5,EP_LOADOUT_SCREEN_BYTES);
    memset((void*)(uintptr_t)c.lifecycle.records,0xa5,8*EP_LOADOUT_RECORD_BYTES);
    memset((void*)(uintptr_t)c.lifecycle.widgets,0xa5,8*EP_LOADOUT_WIDGET_BYTES);
    NEED(ep_loadout_storage_screen_in_scope(mod,storage,owner,0x14ac340,(uintptr_t)manager)==EP_LOADOUT_STORAGE_SCOPE);
    NEED(ep_roster_owner_call(mod,owner,0,RefuseEarly,nullptr)==EP_OWNER_OK);
    ((ScreenCall)gates[0].base)((void*)(uintptr_t)screen);
    NEED(Info().screen_phase==EP_LOADOUT_SCREEN_CLEANED && exited==1);
    ((Factory)gates[3].base)(manager,11);
    NEED(!manager[0xb0/8] && Info().screen_phase==EP_LOADOUT_SCREEN_PARKED && old_calls==1);SameSources();
    NEED(ep_roster_owner_call(mod,owner,0,RefuseStale,nullptr)==EP_OWNER_OK);
    NEED(((Factory)gates[2].base)(manager,12)==0xabc && old_calls==2 && !manager[0xb0/8]);
    NEED(((Factory)gates[2].base)(manager,11)==screen && manager[0xb0/8]==screen);
    NEED(Info().screen_phase==EP_LOADOUT_SCREEN_LIVE && constructed==1 && initialized==1 && attached==1);
    ((ScreenCall)gates[1].base)((void*)(uintptr_t)screen);
    NEED(configured==1 && ((uint32_t*)(uintptr_t)c.inverse_map)[0]==7);SameSources();
    ((ScreenCall)gates[0].base)((void*)(uintptr_t)screen);((Factory)gates[3].base)(manager,11);
    fail_constructor=true;int fault=0;NEED(!EpOwnerInvoke(FailedReopen,nullptr,&fault) && fault);
    NEED(constructed==2 && policies==1 && !manager[0xb0/8] && old_calls==2);
    NEED(Info().state==EP_LOADOUT_STORAGE_QUARANTINED);SameSources();
    MEMORY_BASIC_INFORMATION region={};
    NEED(VirtualQuery((void*)(uintptr_t)screen,&region,sizeof(region)) && region.State==MEM_COMMIT);
    NEED(VirtualQuery((void*)(uintptr_t)binding.arena,&region,sizeof(region)) && region.State==MEM_COMMIT);
    puts("{\"passed\":true,\"scope\":\"one screen exit/reopen/setup/fault flow\",\"native_bodies\":\"test doubles\",\"game_access\":false,\"runtime_verified\":false}");
    return 0;
}
