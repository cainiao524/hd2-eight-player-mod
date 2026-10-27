/* Focused owner sequencing test. Real storage/roster owner + Windows SEH;
 * group preparation, retention and native bodies below are test doubles.
 * No generated image, game process, game path or native game body is accessed.
 * Native constructor/replacement bodies have their separate emulator flow. */
#include "ep_loadout_storage.h"
#include "ep_roster_owner.h"
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NEED(x) do {if (!(x)) {fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);exit(1);}} while (0)
struct Fixture {
    HfMod* mod;
    uint64_t owner,storage,screen;
    EpLoadoutSourceSnapshot source;
    EpLoadoutStorageResult result;
    unsigned mode,constructed,replaced,retains;
    bool reject_retain,retained;
};
static Fixture* active;
static uint64_t next_code;
static int ReadForbidden(void*,uintptr_t,void*,size_t) {NEED(false);return 0;}
static void* Construct(void* screen)
{
    auto& f=*active;NEED((uintptr_t)screen==f.screen && f.retained && !f.constructed && !f.replaced);
    f.constructed++;
    EpLoadoutStorageInfo info={};NEED(ep_loadout_storage_info(f.mod,f.storage,&info));
    NEED(info.state==EP_LOADOUT_STORAGE_INITIALIZING && info.initialization_step==EP_LOADOUT_INIT_CONSTRUCTING);
    NEED(!info.group.construct_banks && !info.binding.setup.common.lifecycle.records);
    NEED(ep_loadout_storage_cancel(f.mod,f.storage)==EP_LOADOUT_STORAGE_STATE);
    if (f.mode==2) {
        // A native service swallows recursive refusal; outer initialization
        // still must quarantine and must never reach replacement.
        NEED(ep_loadout_storage_initialize_in_scope(f.mod,f.storage,f.owner,&f.source)==EP_LOADOUT_STORAGE_STATE);
    }
    return screen;
}
static void Replace(void* screen)
{
    auto& f=*active;NEED((uintptr_t)screen==f.screen && f.retained && f.constructed==1 && !f.replaced);
    f.replaced++;
    if (f.mode==1) RaiseException(0xe0421001,0,0,nullptr);
}
// These minimal dependencies keep this test about the new owned sequence.
EpPropertyResult ep_loadout_group_prepare(const HfApi*,HfMod*,const EpLoadoutGroupAddresses* a,EpLoadoutGroup* out)
{
    *out={};out->capacity=a->setup.common.lifecycle.capacity;out->state=EP_LOADOUT_GROUP_READY;
    out->construct_banks=(uintptr_t)&Construct;out->replace_widgets=(uintptr_t)&Replace;
    for (auto& code:out->code) {code.handle=++next_code;code.state=EP_CODE_READY;}
    return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_group_discard(HfMod*,EpLoadoutGroup*) {NEED(false);return EP_PROPERTY_OK;}
int ep_session_code_retain_set(HfMod* mod,const uint64_t* ids,uint32_t count)
{
    auto& f=*active;NEED(mod==f.mod && count==EP_LOADOUT_GROUP_CODE_COUNT && !f.retained && !f.constructed);
    for (unsigned i=0;i<count;i++) {NEED(ids[i]);for (unsigned j=0;j<i;j++) NEED(ids[i]!=ids[j]);}
    f.retains++;
    if (f.reject_retain) return 0;
    f.retained=true;return 1;
}
int ep_loadout_maps_initialize(EpLoadoutMaps* out,uint32_t capacity,uint32_t local)
{
    NEED(capacity==8 && local==0);memset(out,0xff,sizeof(*out));
    out->network_to_slot[local]=0;out->slot_to_network[0]=local;return 1;
}
static int Initialize(void* context,const EpNativeRosterView*)
{
    auto& f=*(Fixture*)context;
    f.result=ep_loadout_storage_initialize_in_scope(f.mod,f.storage,f.owner,&f.source);
    return 1; // Failed nested owner health must propagate even if ignored here.
}
static void Run(unsigned mode)
{
    Fixture f={};active=&f;f.mode=mode;f.mod=(HfMod*)(uintptr_t)0x9183;
    const uint64_t shift=(uint64_t)mode*0x100000000;
    EpLoadoutStorageBindings input={};auto& a=input.group;auto& l=a.setup.common.lifecycle;
    l={0x180000000+shift,0,0x220000000+shift,0,0,0x191000000+shift,8,0};f.screen=l.screen;
    a.setup.common.roster=0x260000000+shift;a.setup.common.roster_storage=0x260010000+shift;
    a.record_source.manager=0x2a0000000+shift;a.countdown_source.manager=0x2b0000000+shift;
    a.resource_owner_source.owner=0x2c0000000+shift;input.invalid_resource_id=0xffffffff;
    uint64_t* fields[]={&a.lifecycle_code,&a.consumers_code,&l.code,&a.interactions_code,&a.refresh_code,
        &a.records_code,&a.frame_code,&a.mode_code,&a.control_code,&a.state_code,&a.prompt_code,&a.countdown_code,
        &a.resources_code,&a.resource_owner_code,&a.resource_tick_code,&a.resource_events_code,&a.resource_ownership_code,
        &a.resource_sync_code,&a.resource_signals_code,&a.resource_actions_code,&a.resource_main_code,&a.resource_update_code};
    for (unsigned i=0;i<EP_LOADOUT_GROUP_CODE_COUNT;i++) *fields[i]=0x190000000+shift+i*0x10000;
    HfApi api={};EpLoadoutStorageInfo info={};
    NEED(ep_loadout_storage_prepare(&api,f.mod,&input,&info)==EP_LOADOUT_STORAGE_OK);f.storage=info.handle;
    f.source.game=l.game;f.source.record_manager=f.source.global_record_manager=a.record_source.manager;
    f.source.countdown_manager=f.source.global_countdown_manager=a.countdown_source.manager;
    f.source.resource_owner=f.source.global_resource_owner=a.resource_owner_source.owner;
    NEED(ep_loadout_storage_import_sources(f.mod,f.storage,&f.source)==EP_LOADOUT_STORAGE_OK);
    EpNativeRosterView view={};view.game=l.game;view.roster=a.setup.common.roster;view.storage=a.setup.common.roster_storage;
    view.epoch=1;view.build=25480438;EpRosterMemory memory={nullptr,ReadForbidden};
    NEED(ep_roster_owner_create(f.mod,&view,&memory,&f.owner)==EP_OWNER_OK);
    NEED(ep_loadout_storage_initialize_in_scope(f.mod,f.storage,f.owner,&f.source)==EP_LOADOUT_STORAGE_SCOPE);
    if (!mode) {
        f.source.record_window[1]=7;
        NEED(ep_roster_owner_call(f.mod,f.owner,1,Initialize,&f)==EP_OWNER_OK && f.result==EP_LOADOUT_STORAGE_STALE);
        NEED(!f.retains && !f.constructed);f.source.record_window[1]=0;f.reject_retain=true;
        NEED(ep_roster_owner_call(f.mod,f.owner,1,Initialize,&f)==EP_OWNER_OK && f.result==EP_LOADOUT_STORAGE_RETAIN_FAILED);
        NEED(ep_loadout_storage_info(f.mod,f.storage,&info) && info.state==EP_LOADOUT_STORAGE_PREPARED);
        f.reject_retain=false;
    }
    auto result=ep_roster_owner_call(f.mod,f.owner,1,Initialize,&f);
    NEED(ep_loadout_storage_info(f.mod,f.storage,&info));
    NEED(f.retained && f.constructed==1 && f.replaced==(mode==2 ? 0u : 1u));
    if (!mode) {
        NEED(result==EP_OWNER_OK && f.result==EP_LOADOUT_STORAGE_OK);
        NEED(info.state==EP_LOADOUT_STORAGE_UI_MIGRATED && info.initialization_step==EP_LOADOUT_INIT_DONE);
        for (const auto& code:info.group.code) NEED(code.pinned && code.state==EP_CODE_RETAINED);
        NEED(ep_roster_owner_call(f.mod,f.owner,1,Initialize,&f)==EP_OWNER_OK && f.result==EP_LOADOUT_STORAGE_STATE);
    } else {
        NEED(result==EP_OWNER_FAULTED && f.result==EP_LOADOUT_STORAGE_NATIVE_FAILED);
        NEED(info.state==EP_LOADOUT_STORAGE_QUARANTINED && !info.group.construct_banks && !info.binding.setup.common.lifecycle.records);
        NEED(info.initialization_step==(mode==1 ? EP_LOADOUT_INIT_REPLACING : EP_LOADOUT_INIT_CONSTRUCTING));
        NEED(info.owner_result==(mode==1 ? EP_OWNER_CALLBACK_FAULT : EP_OWNER_CALLBACK_FAILED));
        NEED(ep_roster_owner_call(f.mod,f.owner,1,Initialize,&f)==EP_OWNER_FAULTED);
    }
    NEED(ep_loadout_storage_cancel(f.mod,f.storage)==EP_LOADOUT_STORAGE_STATE);
    MEMORY_BASIC_INFORMATION region={};
    NEED(VirtualQuery((void*)(uintptr_t)info.arena,&region,sizeof(region)) && region.State==MEM_COMMIT);
    // Fixtures deliberately leave retained/quarantined arenas alive until this
    // disposable test process exits, just like the production lifetime rule.
}
int main()
{
    Run(0);Run(1);Run(2);
    puts("{\"passed\":true,\"scope\":\"owned initialization order, SEH and reentry\",\"native_bodies\":\"test doubles\",\"game_access\":false,\"runtime_verified\":false}");
}
