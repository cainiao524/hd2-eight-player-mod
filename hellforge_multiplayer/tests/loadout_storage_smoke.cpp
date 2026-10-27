#include "ep_loadout_storage.h"
#include <windows.h>
#include <stdio.h>
#include <string.h>

static unsigned hooks;
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {++hooks;return 1;}
static bool require(bool ok,const char* message)
{if (!ok) fprintf(stderr,"%s\n",message);return ok;}
#define NEED(condition,message) do {if (!require((condition),(message))) return 1;} while (0)
static bool free_region(uint64_t address)
{MEMORY_BASIC_INFORMATION memory={};return VirtualQuery((void*)(uintptr_t)address,&memory,sizeof(memory)) && memory.State==MEM_FREE;}
static uint32_t word(uint64_t address)
{uint32_t value;memcpy(&value,(const void*)(uintptr_t)address,4);return value;}
static bool zero(uint64_t address,unsigned bytes)
{for (unsigned i=0;i<bytes;i++) if (*(const uint8_t*)(uintptr_t)(address+i)) return false;return true;}

int main()
{
    HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;
    auto* mod=(HfMod*)(uintptr_t)0x9183;auto* foreign=(HfMod*)(uintptr_t)0x9184;
    EpLoadoutStorageBindings input={};auto& a=input.group;auto& l=a.setup.common.lifecycle;
    // Numerical fixture addresses only: game/screen/managers are never mapped.
    const uint64_t code=0x190000000;
    l={0x180000000,code+0x30000,0x220000000,0,0,code+0x100000,8,0};
    a.setup.common.roster=0x260000000;a.setup.common.roster_storage=0x260010000;
    a.record_source.manager=0x2a0000000;a.countdown_source.manager=0x2b0000000;a.resource_owner_source.owner=0x2c0000000;
    uint64_t* code_fields[]={&a.lifecycle_code,&a.consumers_code,&l.code,&a.interactions_code,&a.refresh_code,
        &a.records_code,&a.frame_code,&a.mode_code,&a.control_code,&a.state_code,&a.prompt_code,&a.countdown_code,
        &a.resources_code,&a.resource_owner_code,&a.resource_tick_code,&a.resource_events_code,&a.resource_ownership_code,
        &a.resource_sync_code,&a.resource_signals_code,&a.resource_actions_code,&a.resource_main_code,&a.resource_update_code};
    const uint32_t offsets[]={0x40000,0,0x30000,0x50000,0x60000,0x70000,0x80000,0x90000,0xa0000,0xb0000,
        0xc0000,0xd0000,0xe0000,0xf0000,0x110000,0x120000,0x130000,0x140000,0x150000,0x160000,0x170000,0x180000};
    for (unsigned i=0;i<EP_LOADOUT_GROUP_CODE_COUNT;i++) *code_fields[i]=code+offsets[i];
    for (unsigned i=0;i<8;i++) a.setup.placements[i]={(float)i*3,111,0.5f,0,0.5f,0};
    input.desired_arena=0x2d0000000;input.local_network_index=7;input.invalid_resource_id=0xffffffff;

    EpLoadoutStorageInfo first={};
    NEED(ep_loadout_storage_prepare(&api,mod,&input,&first)==EP_LOADOUT_STORAGE_OK,"Fresh storage preparation failed");
    NEED(first.state==EP_LOADOUT_STORAGE_PREPARED && first.capacity==8 && first.arena==input.desired_arena && !hooks,"Preparation state or authority changed");
    const auto& b=first.binding;const auto& s=b.record_source;const auto& r=b.resource_owner_source;
    const uint64_t banks[][2]={{b.setup.common.lifecycle.records,8*EP_LOADOUT_RECORD_BYTES},{b.setup.common.lifecycle.widgets,8*EP_LOADOUT_WIDGET_BYTES},
        {b.setup.common.forward_map,32},{b.setup.common.inverse_map,32},{s.actors,8*8},{s.equipment,8*0x40},
        {s.status,8*0x44},{b.countdown_source.resources,8*0x4c},{r.objects,8*8},{r.phases,8*12},{r.rows,8*20},{r.states,8*4}};
    for (unsigned i=0;i<12;i++) {
        NEED(banks[i][0]>=first.arena && banks[i][0]+banks[i][1]<=first.arena+first.bytes && !(banks[i][0]%16),"Bank escaped its owned arena or lost alignment");
        for (unsigned j=0;j<i;j++) NEED(banks[i][0]>=banks[j][0]+banks[j][1] || banks[j][0]>=banks[i][0]+banks[i][1],"Expanded banks overlap");
    }
    for (unsigned i=0;i<8;i++) {
        NEED(word(b.setup.common.forward_map+i*4)==(i==7 ? 0u : 0xffffffffu) &&
             word(b.setup.common.inverse_map+i*4)==(i==0 ? 7u : 0xffffffffu),"Initial local-player mapping changed");
        NEED(word(b.countdown_source.resources+i*0x4c)==0xffffffffu,"Unused resource row looks allocated");
    }
    NEED(word(r.states+7*4)==0 && word(s.status+7*0x44)==0 && word(s.equipment+7*0x40)==0,"New bank tail was not zeroed");
    uint8_t* last_widget=(uint8_t*)(uintptr_t)(b.setup.common.lifecycle.widgets+8*EP_LOADOUT_WIDGET_BYTES-1);
    *last_widget=0x7a;
    NEED(first.group.resource_tick==first.group.update_resource_states && first.group.state==EP_LOADOUT_GROUP_READY,"Storage did not use the linked group");
    EpLoadoutStorageInfo duplicate={};
    NEED(ep_loadout_storage_prepare(&api,foreign,&input,&duplicate)==EP_LOADOUT_STORAGE_CONFLICT && !duplicate.handle,"A second owner claimed the same game banks");
    NEED(ep_loadout_storage_cancel(foreign,first.handle)==EP_LOADOUT_STORAGE_STATE && *last_widget==0x7a,"Foreign owner released shared backing");
    NEED(ep_loadout_storage_cancel(mod,first.handle)==EP_LOADOUT_STORAGE_OK,"Pre-publication cancellation failed");
    NEED(!ep_loadout_storage_info(mod,first.handle,&duplicate) && free_region(first.arena),"Cancelled storage is still reachable");
    for (const auto& image:first.group.code) NEED(free_region(image.base),"Cancellation left a code allocation behind");

    // Same preparation transaction retried after cancellation, then committed
    // to permanent lifetime. This exercises no game or engine callback.
    EpLoadoutStorageInfo retained={};
    NEED(ep_loadout_storage_prepare(&api,mod,&input,&retained)==EP_LOADOUT_STORAGE_OK && retained.handle!=first.handle,"Retry reused a stale owner handle");
    NEED(*last_widget==0,"Retry exposed the cancelled widget contents");
    NEED(ep_loadout_storage_cancel(mod,first.handle)==EP_LOADOUT_STORAGE_STATE,"Stale cancellation affected the new owner");
    EpLoadoutSourceSnapshot snapshot={};snapshot.game=l.game;
    snapshot.record_manager=snapshot.global_record_manager=a.record_source.manager;
    snapshot.countdown_manager=snapshot.global_countdown_manager=a.countdown_source.manager;
    snapshot.resource_owner=snapshot.global_resource_owner=a.resource_owner_source.owner;
    for (unsigned i=0;i<sizeof(snapshot.record_window);i++) snapshot.record_window[i]=(uint8_t)(i*29+3);
    for (unsigned i=0;i<sizeof(snapshot.resources);i++) snapshot.resources[i]=(uint8_t)(i*17+5);
    for (unsigned i=0x10;i<sizeof(snapshot.owner);i++) snapshot.owner[i]=(uint8_t)(i*13+7);
    // Four registered, three published, two prefix rows. +0 may be less than
    // published after pending publication; it is not a dense count bound.
    const uint32_t counts[]={1,4,3,2};memcpy(snapshot.owner,counts,sizeof(counts));
    const auto original=snapshot;auto invalid=snapshot;invalid.global_record_manager+=8;
    NEED(ep_loadout_storage_import_sources(mod,retained.handle,&invalid)==EP_LOADOUT_STORAGE_SOURCE &&
         zero(retained.binding.record_source.actors,8*8),"Foreign source identity changed target data");
    NEED(ep_loadout_storage_import_sources(mod,retained.handle,&snapshot)==EP_LOADOUT_STORAGE_OK,"Source staging failed");
    NEED(ep_loadout_storage_info(mod,retained.handle,&retained) && retained.sources_imported,"Missing import state");
    const auto& imported=retained.binding;const auto& owner=imported.resource_owner_source;
    const struct {uint64_t target;const uint8_t* source;unsigned stride;} imported_banks[]={
        {imported.record_source.actors,snapshot.record_window,8},
        {imported.record_source.equipment,snapshot.record_window+0x134,0x40},
        {imported.record_source.status,snapshot.record_window+0x4c,0x44},
        {imported.countdown_source.resources,snapshot.resources,0x4c},
        {owner.objects,snapshot.owner+0x68,8},{owner.phases,snapshot.owner+0x88,12},
        {owner.rows,snapshot.owner+0xb8,20},{owner.states,snapshot.owner+0x108,4}};
    for (const auto& bank:imported_banks) {
        NEED(!memcmp((const void*)(uintptr_t)bank.target,bank.source,4*bank.stride),"Legacy source ordinal or opaque data changed");
        for (unsigned i=4;i<8;i++) {
            if (bank.target==imported.countdown_source.resources)
                NEED(word(bank.target+i*bank.stride)==input.invalid_resource_id && zero(bank.target+i*bank.stride+4,bank.stride-4),"New resource row was not initialized");
            else NEED(zero(bank.target+i*bank.stride,bank.stride),"New source row inherited old data");
        }
    }
    NEED(!memcmp(snapshot.record_window,original.record_window,sizeof(snapshot.record_window)) &&
         !memcmp(snapshot.resources,original.resources,sizeof(snapshot.resources)) &&
         !memcmp(snapshot.owner,original.owner,sizeof(snapshot.owner)),"Import mutated its source copies");
    NEED(zero(imported.setup.common.lifecycle.records,8*EP_LOADOUT_RECORD_BYTES) &&
         zero(imported.setup.common.lifecycle.widgets,8*EP_LOADOUT_WIDGET_BYTES) &&
         word(imported.setup.common.inverse_map)==7,"Source import fabricated native UI state");
    invalid=snapshot;const uint32_t too_many=5;memcpy(invalid.owner+4,&too_many,4);
    NEED(ep_loadout_storage_import_sources(mod,retained.handle,&invalid)==EP_LOADOUT_STORAGE_COUNTS &&
         !memcmp((const void*)(uintptr_t)owner.objects,snapshot.owner+0x68,32),"Rejected import corrupted the previous baseline");
    NEED(ep_loadout_storage_retain(mod,retained.handle)==EP_LOADOUT_STORAGE_SOURCE,"Legacy retain bypassed imported-source checking");
    invalid=snapshot;invalid.resources[0]^=1;
    NEED(ep_loadout_storage_retain_sources(mod,retained.handle,&invalid)==EP_LOADOUT_STORAGE_STALE,"Changed source was retained");
    auto* tail=(uint8_t*)(uintptr_t)(owner.rows+7*20);*tail=0x51;
    NEED(ep_loadout_storage_retain_sources(mod,retained.handle,&snapshot)==EP_LOADOUT_STORAGE_STALE,"Changed target was retained");
    NEED(ep_loadout_storage_import_sources(foreign,retained.handle,&snapshot)==EP_LOADOUT_STORAGE_STATE && *tail==0x51,"Foreign importer wrote the arena");
    // Refresh replaces the eight banks together; it also repairs an unexposed
    // modified tail. The new source baseline must be used by retention.
    snapshot.resources[0]^=1;
    NEED(ep_loadout_storage_import_sources(mod,retained.handle,&snapshot)==EP_LOADOUT_STORAGE_OK && !*tail,"Fresh import did not replace the entire baseline");
    NEED(ep_loadout_storage_retain_sources(mod,retained.handle,&original)==EP_LOADOUT_STORAGE_STALE,"Old import baseline was retained after refresh");
    NEED(ep_loadout_storage_retain_sources(mod,retained.handle,&snapshot)==EP_LOADOUT_STORAGE_OK,"Whole-group source-aware retention failed");
    NEED(ep_loadout_storage_info(mod,retained.handle,&retained) && retained.state==EP_LOADOUT_STORAGE_RETAINED,"Retained owner state missing");
    for (const auto& image:retained.group.code) {
        EpSessionCodeInfo actual={};
        NEED(ep_session_code_info(mod,image.handle,&actual) && actual.pinned && actual.state==EP_CODE_RETAINED,"A linked image remained cancellable");
    }
    NEED(ep_loadout_storage_cancel(mod,retained.handle)==EP_LOADOUT_STORAGE_STATE && !free_region(retained.arena),"Retained backing was released");
    NEED(ep_loadout_storage_import_sources(mod,retained.handle,&snapshot)==EP_LOADOUT_STORAGE_STATE,"Retained source banks remained mutable through import API");
    NEED(word(retained.binding.setup.common.inverse_map)==7 && !hooks,"Retention changed data or installed a hook");
    puts("{\"passed\":true,\"scope\":\"one owned loadout source import/refresh/retain flow\",\"game_access\":false,\"runtime_verified\":false}");
    return 0;
}
