#include "ep_loadout_storage.h"
#include <windows.h>
#include <string.h>

namespace {
struct Storage {
    HfMod* mod;
    uint64_t game,screen;
    EpLoadoutStorageInfo info;
};
Storage slots[EP_LOADOUT_STORAGE_SLOTS];
SRWLOCK storage_lock=SRWLOCK_INIT;
uint64_t sequence;
bool pointer(uint64_t at,uint64_t bytes,uint64_t alignment=1)
{return at>=0x10000 && at<(UINT64_C(1)<<47) && bytes<=(UINT64_C(1)<<47)-at && !(at%alignment);}
bool overlap(uint64_t a,uint64_t n,uint64_t b,uint64_t m)
{return a<b+m && b<a+n;}
Storage* find(HfMod* mod,uint64_t handle)
{
    if (mod && handle) for (auto& slot:slots) if (slot.mod==mod && slot.info.handle==handle) return &slot;
    return nullptr;
}
void info(const Storage& slot,EpLoadoutStorageInfo* out)
{
    *out=slot.info;
    if (out->state!=EP_LOADOUT_STORAGE_PREPARED && out->state!=EP_LOADOUT_STORAGE_RETAINED) {
        out->binding={};out->group={};
    }
}
// Every consumer binding is assigned from these same twelve intervals.
uint32_t bind_banks(EpLoadoutGroupAddresses& a,uint64_t arena)
{
    auto& l=a.setup.common.lifecycle;auto& s=a.record_source;auto& r=a.resource_owner_source;
    uint64_t* addresses[]={&l.records,&l.widgets,&a.setup.common.forward_map,&a.setup.common.inverse_map,
        &s.actors,&s.equipment,&s.status,&a.countdown_source.resources,&r.objects,&r.phases,&r.rows,&r.states};
    const uint32_t n=l.capacity;
    const uint32_t lengths[]={n*EP_LOADOUT_RECORD_BYTES,n*EP_LOADOUT_WIDGET_BYTES,32,32,
        n*8,n*0x40,n*0x44,n*0x4c,n*8,n*12,n*20,n*4};
    uint32_t bytes=0;
    for (unsigned i=0;i<12;i++) {bytes=(bytes+15)&~15u;*addresses[i]=arena+bytes;bytes+=lengths[i];}
    return bytes;
}
bool empty_banks(const EpLoadoutGroupAddresses& a)
{
    const auto& l=a.setup.common.lifecycle;const auto& s=a.record_source;const auto& r=a.resource_owner_source;
    return !(l.records || l.widgets || a.setup.common.forward_map || a.setup.common.inverse_map ||
        s.actors || s.equipment || s.status || a.countdown_source.resources || r.objects || r.phases || r.rows || r.states);
}
bool arena_disjoint(const EpLoadoutGroupAddresses& a,uint64_t arena,uint32_t bytes)
{
    const auto& c=a.setup.common;const auto& l=c.lifecycle;
    const uint64_t external[][2]={{l.game,0x4000000},{l.screen,EP_LOADOUT_SCREEN_BYTES},{l.reject,1},
        {c.roster,0xe8},{c.roster_storage,0x680},{a.record_source.manager,0x948},
        {a.countdown_source.manager,0x13000},{a.resource_owner_source.owner,0x118}};
    for (const auto& range:external) if (!pointer(range[0],range[1]) || overlap(arena,bytes,range[0],range[1])) return false;
    const uint64_t code[]={a.lifecycle_code,a.consumers_code,l.code,a.interactions_code,a.refresh_code,
        a.records_code,a.frame_code,a.mode_code,a.control_code,a.state_code,a.prompt_code,a.countdown_code,
        a.resources_code,a.resource_owner_code,a.resource_tick_code,a.resource_events_code,a.resource_ownership_code,
        a.resource_sync_code,a.resource_signals_code,a.resource_actions_code,a.resource_main_code,a.resource_update_code};
    static_assert(sizeof(code)/sizeof(*code)==EP_LOADOUT_GROUP_CODE_COUNT,"Complete code intervals");
    // Exact code reservations start on Windows allocation-granularity boundaries.
    // Keep the complete 64 KiB reservation window clear, including page padding.
    for (auto base:code) if (!pointer(base,EP_SESSION_CODE_MAX_BYTES) || overlap(arena,bytes,base,EP_SESSION_CODE_MAX_BYTES)) return false;
    return true;
}
void initialize(const EpLoadoutStorageBindings& b,const EpLoadoutGroupAddresses& a)
{
    EpLoadoutMaps maps;ep_loadout_maps_initialize(&maps,a.setup.common.lifecycle.capacity,b.local_network_index);
    memcpy((void*)(uintptr_t)a.setup.common.forward_map,maps.network_to_slot,32);
    memcpy((void*)(uintptr_t)a.setup.common.inverse_map,maps.slot_to_network,32);
    for (uint32_t i=0;i<a.setup.common.lifecycle.capacity;i++)
        memcpy((void*)(uintptr_t)(a.countdown_source.resources+i*0x4c),&b.invalid_resource_id,4);
}
}

int ep_loadout_storage_info(HfMod* mod,uint64_t handle,EpLoadoutStorageInfo* out)
{
    if (!out) return 0;*out={};
    AcquireSRWLockShared(&storage_lock);auto* slot=find(mod,handle);
    if (slot) info(*slot,out);
    ReleaseSRWLockShared(&storage_lock);return slot!=nullptr;
}

EpLoadoutStorageResult ep_loadout_storage_prepare(const HfApi* api,HfMod* mod,const EpLoadoutStorageBindings* input,EpLoadoutStorageInfo* out)
{
    if (!out) return EP_LOADOUT_STORAGE_ARGUMENT;
    EpLoadoutStorageBindings b={};if (input) b=*input;*out={};
    auto a=b.group;const auto& l=a.setup.common.lifecycle;
    if (!input || !api || !mod || !empty_banks(a) || l.reserved || !l.capacity ||
        l.capacity>EP_LOADOUT_LIFECYCLE_LIMIT || b.local_network_index>=l.capacity) return EP_LOADOUT_STORAGE_ARGUMENT;
    SYSTEM_INFO system;GetSystemInfo(&system);
    uint32_t bytes=bind_banks(a,0);bytes=(bytes+system.dwPageSize-1)/system.dwPageSize*system.dwPageSize;
    if (!pointer(l.game,0x4000000,4096) || !pointer(l.screen,EP_LOADOUT_SCREEN_BYTES,8) ||
        (b.desired_arena && (!pointer(b.desired_arena,bytes,system.dwAllocationGranularity) || !arena_disjoint(a,b.desired_arena,bytes))))
        return EP_LOADOUT_STORAGE_POINTER;
    Storage* slot=nullptr;
    AcquireSRWLockExclusive(&storage_lock);
    for (const auto& other:slots) if (other.info.handle && (other.game==l.game || overlap(other.screen,EP_LOADOUT_SCREEN_BYTES,l.screen,EP_LOADOUT_SCREEN_BYTES))) {
        ReleaseSRWLockExclusive(&storage_lock);return EP_LOADOUT_STORAGE_CONFLICT;
    }
    if (sequence!=UINT64_MAX) for (auto& candidate:slots) if (!candidate.info.handle) {
        slot=&candidate;slot->mod=mod;slot->game=l.game;slot->screen=l.screen;
        slot->info.handle=++sequence;slot->info.state=EP_LOADOUT_STORAGE_PREPARING;slot->info.capacity=l.capacity;break;
    }
    ReleaseSRWLockExclusive(&storage_lock);
    if (!slot) return EP_LOADOUT_STORAGE_RESERVE;
    // No storage lock across SDK build checks or executable image preparation.
    // PREPARING cannot be cancelled/retained and exposes no data/code bindings.
    EpLoadoutStorageInfo prepared={};prepared.handle=slot->info.handle;prepared.capacity=l.capacity;
    auto result=EP_LOADOUT_STORAGE_OK;
    void* arena=VirtualAlloc((void*)(uintptr_t)b.desired_arena,bytes,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    if (!arena) result=EP_LOADOUT_STORAGE_RESERVE;
    else {
        prepared.arena=(uintptr_t)arena;prepared.bytes=bytes;
        if (!pointer(prepared.arena,bytes,16) || (b.desired_arena && prepared.arena!=b.desired_arena) || !arena_disjoint(a,prepared.arena,bytes))
            result=EP_LOADOUT_STORAGE_POINTER;
        else {
            bind_banks(a,prepared.arena);initialize(b,a);
            prepared.group_result=ep_loadout_group_prepare(api,mod,&a,&prepared.group);
            if (prepared.group_result!=EP_PROPERTY_OK) result=EP_LOADOUT_STORAGE_GROUP;
            else {prepared.binding=a;prepared.state=EP_LOADOUT_STORAGE_PREPARED;}
        }
    }
    if (result!=EP_LOADOUT_STORAGE_OK) {
        // Failed group cleanup must retain the arena, even before publication.
        if (prepared.group.state==EP_LOADOUT_GROUP_CLEANUP || (arena && !VirtualFree(arena,0,MEM_RELEASE))) {
            prepared.state=EP_LOADOUT_STORAGE_CLEANUP_REQUIRED;result=EP_LOADOUT_STORAGE_CLEANUP;
        }
    }
    AcquireSRWLockExclusive(&storage_lock);
    if (result==EP_LOADOUT_STORAGE_OK || result==EP_LOADOUT_STORAGE_CLEANUP) {slot->info=prepared;info(*slot,out);}
    else *slot={};
    ReleaseSRWLockExclusive(&storage_lock);return result;
}

EpLoadoutStorageResult ep_loadout_storage_cancel(HfMod* mod,uint64_t handle)
{
    AcquireSRWLockExclusive(&storage_lock);auto* slot=find(mod,handle);
    if (!slot || (slot->info.state!=EP_LOADOUT_STORAGE_PREPARED && slot->info.state!=EP_LOADOUT_STORAGE_CLEANUP_REQUIRED)) {
        ReleaseSRWLockExclusive(&storage_lock);return EP_LOADOUT_STORAGE_STATE;
    }
    auto pending=slot->info;slot->info.state=EP_LOADOUT_STORAGE_CLEANING;
    ReleaseSRWLockExclusive(&storage_lock);
    bool removed=ep_loadout_group_discard(mod,&pending.group)==EP_PROPERTY_OK;
    if (removed && pending.arena) removed=VirtualFree((void*)(uintptr_t)pending.arena,0,MEM_RELEASE)!=0;
    AcquireSRWLockExclusive(&storage_lock);
    if (removed) *slot={};
    else {pending.state=EP_LOADOUT_STORAGE_CLEANUP_REQUIRED;slot->info=pending;}
    ReleaseSRWLockExclusive(&storage_lock);
    return removed ? EP_LOADOUT_STORAGE_OK : EP_LOADOUT_STORAGE_CLEANUP;
}

EpLoadoutStorageResult ep_loadout_storage_retain(HfMod* mod,uint64_t handle)
{
    AcquireSRWLockExclusive(&storage_lock);auto* slot=find(mod,handle);
    if (!slot || slot->info.state!=EP_LOADOUT_STORAGE_PREPARED) {
        ReleaseSRWLockExclusive(&storage_lock);return EP_LOADOUT_STORAGE_STATE;
    }
    uint64_t handles[EP_LOADOUT_GROUP_CODE_COUNT];
    for (unsigned i=0;i<EP_LOADOUT_GROUP_CODE_COUNT;i++) handles[i]=slot->info.group.code[i].handle;
    slot->info.state=EP_LOADOUT_STORAGE_RETAINING;
    ReleaseSRWLockExclusive(&storage_lock);
    int retained=ep_session_code_retain_set(mod,handles,EP_LOADOUT_GROUP_CODE_COUNT);
    AcquireSRWLockExclusive(&storage_lock);
    slot->info.state=retained ? EP_LOADOUT_STORAGE_RETAINED : EP_LOADOUT_STORAGE_PREPARED;
    if (retained) for (auto& code:slot->info.group.code) {code.state=EP_CODE_RETAINED;code.pinned=1;}
    ReleaseSRWLockExclusive(&storage_lock);
    return retained ? EP_LOADOUT_STORAGE_OK : EP_LOADOUT_STORAGE_RETAIN_FAILED;
}
