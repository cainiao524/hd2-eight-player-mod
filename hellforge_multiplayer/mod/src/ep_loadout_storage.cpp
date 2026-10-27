#include "ep_loadout_storage.h"
#include "ep_roster_owner.h"
#include <windows.h>
#include <string.h>

namespace {
struct Storage {
    HfMod* mod;
    uint64_t game,screen;
    EpLoadoutStorageInfo info;
    uint32_t invalid_resource_id;
    EpLoadoutSourceSnapshot source;
    EpPlayerJoinPeers peers;
};
Storage slots[EP_LOADOUT_STORAGE_SLOTS];
SRWLOCK storage_lock=SRWLOCK_INIT;
uint64_t sequence;
struct Initialization;
thread_local Initialization* initializing;
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
    if (out->state!=EP_LOADOUT_STORAGE_PREPARED && out->state!=EP_LOADOUT_STORAGE_RETAINED &&
        out->state!=EP_LOADOUT_STORAGE_UI_MIGRATED) {
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
bool arena_disjoint(const EpLoadoutGroupAddresses& a,uint64_t arena,uint32_t bytes,const EpPlayerJoinPeers* peers)
{
    const auto& c=a.setup.common;const auto& l=c.lifecycle;
    const uint64_t external[][2]={{l.game,0x4000000},{l.screen,EP_LOADOUT_SCREEN_BYTES},{l.reject,1},
        {c.roster,0xe8},{c.roster_storage,0x680},{a.record_source.manager,0xb7c},
        {a.countdown_source.manager,0x13000},{a.resource_owner_source.owner,0x118}};
    if (peers && ep_loadout_consumers_peer_span(peers,arena,bytes)!=EP_PROPERTY_OK) return false;
    for (const auto& range:external) {
        if (!pointer(range[0],range[1]) || overlap(arena,bytes,range[0],range[1]) ||
            (peers && ep_loadout_consumers_peer_span(peers,range[0],(uint32_t)range[1])!=EP_PROPERTY_OK)) return false;
    }
    const uint64_t code[]={a.lifecycle_code,a.consumers_code,l.code,a.interactions_code,a.refresh_code,
        a.records_code,a.frame_code,a.mode_code,a.control_code,a.state_code,a.prompt_code,a.countdown_code,
        a.resources_code,a.resource_owner_code,a.resource_tick_code,a.resource_events_code,a.resource_ownership_code,
        a.resource_sync_code,a.resource_signals_code,a.resource_actions_code,a.resource_main_code,a.resource_update_code};
    static_assert(sizeof(code)/sizeof(*code)==EP_LOADOUT_GROUP_CODE_COUNT,"Complete code intervals");
    // Exact code reservations start on Windows allocation-granularity boundaries.
    // Keep the complete 64 KiB reservation window clear, including page padding.
    for (auto base:code) if (!pointer(base,EP_SESSION_CODE_MAX_BYTES) || overlap(arena,bytes,base,EP_SESSION_CODE_MAX_BYTES) ||
        (peers && ep_loadout_consumers_peer_span(peers,base,EP_SESSION_CODE_MAX_BYTES)!=EP_PROPERTY_OK)) return false;
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
uint32_t u32(const uint8_t* bytes) {uint32_t v;memcpy(&v,bytes,4);return v;}
EpLoadoutStorageResult validate_source(const Storage& slot,const EpLoadoutSourceSnapshot& s)
{
    const auto& b=slot.info.binding;
    if (slot.info.capacity<EP_LOADOUT_NATIVE_CAPACITY || s.game!=slot.game ||
        s.record_manager!=b.record_source.manager || s.global_record_manager!=s.record_manager ||
        s.countdown_manager!=b.countdown_source.manager || s.global_countdown_manager!=s.countdown_manager ||
        s.resource_owner!=b.resource_owner_source.owner || s.global_resource_owner!=s.resource_owner)
        return EP_LOADOUT_STORAGE_SOURCE;
    const auto auxiliary=u32(s.owner),total=u32(s.owner+4),published=u32(s.owner+8),prefix=u32(s.owner+12);
    // 66C100 publishes pending registrations without updating +0; do not
    // incorrectly require that auxiliary counter to bound published/total.
    if (auxiliary>4 || total>4 || published>total || prefix>published)
        return EP_LOADOUT_STORAGE_COUNTS;
    return EP_LOADOUT_STORAGE_OK;
}
struct SourceBank {uint64_t target;const uint8_t* source;uint32_t stride;bool resource;};
void source_banks(const Storage& slot,const EpLoadoutSourceSnapshot& s,SourceBank (&banks)[8])
{
    const auto& a=slot.info.binding;const auto& r=a.resource_owner_source;
    banks[0]={a.record_source.actors,s.record_window,8,false};
    banks[1]={a.record_source.equipment,s.record_window+(0xa7c-EP_LOADOUT_RECORD_SOURCE_OFFSET),0x40,false};
    banks[2]={a.record_source.status,s.record_window+(0x994-EP_LOADOUT_RECORD_SOURCE_OFFSET),0x44,false};
    banks[3]={a.countdown_source.resources,s.resources,0x4c,true};
    banks[4]={r.objects,s.owner+0x68,8,false};banks[5]={r.phases,s.owner+0x88,12,false};
    banks[6]={r.rows,s.owner+0xb8,20,false};banks[7]={r.states,s.owner+0x108,4,false};
}
bool source_equal(const EpLoadoutSourceSnapshot& a,const EpLoadoutSourceSnapshot& b)
{
    // Compare captured fields, never ABI padding or addresses of the copies.
    return a.game==b.game && a.record_manager==b.record_manager && a.global_record_manager==b.global_record_manager &&
        a.countdown_manager==b.countdown_manager && a.global_countdown_manager==b.global_countdown_manager &&
        a.resource_owner==b.resource_owner && a.global_resource_owner==b.global_resource_owner &&
        !memcmp(a.record_window,b.record_window,sizeof(a.record_window)) &&
        !memcmp(a.resources,b.resources,sizeof(a.resources)) && !memcmp(a.owner,b.owner,sizeof(a.owner));
}
bool target_equal(const Storage& slot)
{
    SourceBank banks[8];source_banks(slot,slot.source,banks);
    const uint8_t zero[0x4c]={};
    for (const auto& bank:banks) {
        const auto* target=(const uint8_t*)(uintptr_t)bank.target;
        if (memcmp(target,bank.source,4*bank.stride)) return false;
        for (unsigned row=4;row<slot.info.capacity;row++) {
            const auto* p=target+row*bank.stride;
            if (bank.resource) {
                if (u32(p)!=slot.invalid_resource_id || memcmp(p+4,zero,bank.stride-4)) return false;
            } else if (memcmp(p,zero,bank.stride)) return false;
        }
    }
    return true;
}
struct Initialization {
    Storage* slot;
    uint64_t owner;
    const EpLoadoutSourceSnapshot* current;
    EpLoadoutStorageResult result;
    uint32_t original_state;
    bool reentered;
};
void initialization_step(Storage& slot,uint32_t step)
{
    AcquireSRWLockExclusive(&storage_lock);slot.info.initialization_step=step;
    ReleaseSRWLockExclusive(&storage_lock);
}
bool initialization_healthy(const Initialization& call)
{return !call.reentered && ep_roster_owner_native_status(call.slot->mod,call.owner)==EP_OWNER_OK;}
int initialize_owned(void* context,const EpNativeRosterView* view)
{
    auto& call=*(Initialization*)context;auto& slot=*call.slot;
    const auto& binding=slot.info.binding.setup.common;
    if (view->game!=slot.game || view->roster!=binding.roster || view->storage!=binding.roster_storage) {
        call.result=EP_LOADOUT_STORAGE_SOURCE;return 1;
    }
    // The caller's snapshot and our owned banks are read under the nested
    // owner's SEH boundary, with no storage lock that an exception could strand.
    const auto current=*call.current;
    if (!source_equal(current,slot.source) || !target_equal(slot)) {
        call.result=EP_LOADOUT_STORAGE_STALE;return 1;
    }
    if (call.original_state==EP_LOADOUT_STORAGE_PREPARED) {
        initialization_step(slot,EP_LOADOUT_INIT_RETAINING);
        uint64_t handles[EP_LOADOUT_GROUP_CODE_COUNT];
        for (unsigned i=0;i<EP_LOADOUT_GROUP_CODE_COUNT;i++) handles[i]=slot.info.group.code[i].handle;
        if (!ep_session_code_retain_set(slot.mod,handles,EP_LOADOUT_GROUP_CODE_COUNT)) {
            call.result=EP_LOADOUT_STORAGE_RETAIN_FAILED;return 1;
        }
        AcquireSRWLockExclusive(&storage_lock);
        for (auto& code:slot.info.group.code) {code.state=EP_CODE_RETAINED;code.pinned=1;}
        ReleaseSRWLockExclusive(&storage_lock);
    }
    call.result=EP_LOADOUT_STORAGE_NATIVE_FAILED;
    if (!initialization_healthy(call)) return 0;
    initialization_step(slot,EP_LOADOUT_INIT_CONSTRUCTING);
    auto construct=(void*(*)(void*))(uintptr_t)slot.info.group.construct_banks;
    if (construct((void*)(uintptr_t)slot.screen)!=(void*)(uintptr_t)slot.screen || !initialization_healthy(call)) return 0;
    initialization_step(slot,EP_LOADOUT_INIT_REPLACING);
    auto replace=(void(*)(void*))(uintptr_t)slot.info.group.replace_widgets;
    replace((void*)(uintptr_t)slot.screen);
    if (!initialization_healthy(call)) return 0;
    initialization_step(slot,EP_LOADOUT_INIT_DONE);
    call.result=EP_LOADOUT_STORAGE_OK;return 1;
}
}

int ep_loadout_storage_info(HfMod* mod,uint64_t handle,EpLoadoutStorageInfo* out)
{
    if (!out) return 0;*out={};
    AcquireSRWLockShared(&storage_lock);auto* slot=find(mod,handle);
    if (slot) info(*slot,out);
    ReleaseSRWLockShared(&storage_lock);return slot!=nullptr;
}

static EpLoadoutStorageResult prepare(const HfApi* api,HfMod* mod,const EpLoadoutStorageBindings* input,const EpPlayerJoinPeers* peers,EpLoadoutStorageInfo* out)
{
    if (!out) return EP_LOADOUT_STORAGE_ARGUMENT;
    EpLoadoutStorageBindings b={};if (input) b=*input;*out={};
    auto a=b.group;const auto& l=a.setup.common.lifecycle;
    if (!input || !api || !mod || !empty_banks(a) || l.reserved || !l.capacity ||
        l.capacity>EP_LOADOUT_LIFECYCLE_LIMIT || b.local_network_index>=l.capacity) return EP_LOADOUT_STORAGE_ARGUMENT;
    if (peers && (peers->capacity!=l.capacity ||
        ep_loadout_consumers_peer_span(peers,l.game,0x4000000)!=EP_PROPERTY_OK)) return EP_LOADOUT_STORAGE_ARGUMENT;
    SYSTEM_INFO system;GetSystemInfo(&system);
    uint32_t bytes=bind_banks(a,0);bytes=(bytes+system.dwPageSize-1)/system.dwPageSize*system.dwPageSize;
    if (!pointer(l.game,0x4000000,4096) || !pointer(l.screen,EP_LOADOUT_SCREEN_BYTES,8) ||
        (b.desired_arena && (!pointer(b.desired_arena,bytes,system.dwAllocationGranularity) || !arena_disjoint(a,b.desired_arena,bytes,peers))))
        return EP_LOADOUT_STORAGE_POINTER;
    Storage* slot=nullptr;
    AcquireSRWLockExclusive(&storage_lock);
    for (const auto& other:slots) if (other.info.handle && (other.game==l.game || overlap(other.screen,EP_LOADOUT_SCREEN_BYTES,l.screen,EP_LOADOUT_SCREEN_BYTES))) {
        ReleaseSRWLockExclusive(&storage_lock);return EP_LOADOUT_STORAGE_CONFLICT;
    }
    if (sequence!=UINT64_MAX) for (auto& candidate:slots) if (!candidate.info.handle) {
        slot=&candidate;slot->mod=mod;slot->game=l.game;slot->screen=l.screen;slot->invalid_resource_id=b.invalid_resource_id;
        if (peers) slot->peers=*peers;
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
        if (!pointer(prepared.arena,bytes,16) || (b.desired_arena && prepared.arena!=b.desired_arena) || !arena_disjoint(a,prepared.arena,bytes,peers))
            result=EP_LOADOUT_STORAGE_POINTER;
        else {
            bind_banks(a,prepared.arena);initialize(b,a);
            prepared.group_result=peers ? ep_loadout_group_prepare_peers(api,mod,&a,peers,&prepared.group) : ep_loadout_group_prepare(api,mod,&a,&prepared.group);
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

EpLoadoutStorageResult ep_loadout_storage_prepare(const HfApi* api,HfMod* mod,const EpLoadoutStorageBindings* input,EpLoadoutStorageInfo* out)
{return prepare(api,mod,input,nullptr,out);}
EpLoadoutStorageResult ep_loadout_storage_prepare_peers(const HfApi* api,HfMod* mod,const EpLoadoutStorageBindings* input,const EpPlayerJoinPeers* peers,EpLoadoutStorageInfo* out)
{
    if (!peers) {if (out) *out={};return EP_LOADOUT_STORAGE_ARGUMENT;}
    const auto binding=*peers;return prepare(api,mod,input,&binding,out);
}
int ep_loadout_storage_peer_binding(HfMod* mod,uint64_t handle,EpPlayerJoinPeers* out)
{
    if (!out) return 0;*out={};
    AcquireSRWLockShared(&storage_lock);const auto* slot=find(mod,handle);
    const bool valid=slot && (slot->info.state==EP_LOADOUT_STORAGE_PREPARED ||
        slot->info.state==EP_LOADOUT_STORAGE_RETAINED || slot->info.state==EP_LOADOUT_STORAGE_UI_MIGRATED);
    if (valid) *out=slot->peers;
    ReleaseSRWLockShared(&storage_lock);return valid;
}

EpLoadoutStorageResult ep_loadout_storage_import_sources(HfMod* mod,uint64_t handle,const EpLoadoutSourceSnapshot* input)
{
    if (!input) return EP_LOADOUT_STORAGE_ARGUMENT;
    // Caller owns a stable readable snapshot. Copy before writing any target,
    // including when that owned snapshot happens to alias the unexposed arena.
    const auto source=*input;
    AcquireSRWLockExclusive(&storage_lock);auto* slot=find(mod,handle);
    if (!slot || slot->info.state!=EP_LOADOUT_STORAGE_PREPARED) {
        ReleaseSRWLockExclusive(&storage_lock);return EP_LOADOUT_STORAGE_STATE;
    }
    const auto result=validate_source(*slot,source);
    if (result==EP_LOADOUT_STORAGE_OK) {
        SourceBank banks[8];source_banks(*slot,source,banks);
        // All validation precedes the first write. No callbacks/publication or
        // allocation can fail between the eight writes and baseline assignment.
        for (const auto& bank:banks) {
            auto* target=(uint8_t*)(uintptr_t)bank.target;
            memcpy(target,bank.source,4*bank.stride);
            memset(target+4*bank.stride,0,(slot->info.capacity-4)*bank.stride);
            if (bank.resource) for (unsigned row=4;row<slot->info.capacity;row++)
                memcpy(target+row*bank.stride,&slot->invalid_resource_id,4);
        }
        slot->source=source;slot->info.sources_imported=1;
    }
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

static EpLoadoutStorageResult retain(HfMod* mod,uint64_t handle,const EpLoadoutSourceSnapshot* current)
{
    AcquireSRWLockExclusive(&storage_lock);auto* slot=find(mod,handle);
    if (!slot || slot->info.state!=EP_LOADOUT_STORAGE_PREPARED) {
        ReleaseSRWLockExclusive(&storage_lock);return EP_LOADOUT_STORAGE_STATE;
    }
    if (bool(current)!=bool(slot->info.sources_imported)) {
        ReleaseSRWLockExclusive(&storage_lock);return EP_LOADOUT_STORAGE_SOURCE;
    }
    if (current) {
        const auto source=*current;
        if (!source_equal(source,slot->source) || !target_equal(*slot)) {
            ReleaseSRWLockExclusive(&storage_lock);return EP_LOADOUT_STORAGE_STALE;
        }
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

EpLoadoutStorageResult ep_loadout_storage_retain(HfMod* mod,uint64_t handle)
{return retain(mod,handle,nullptr);}
EpLoadoutStorageResult ep_loadout_storage_retain_sources(HfMod* mod,uint64_t handle,const EpLoadoutSourceSnapshot* current)
{return current ? retain(mod,handle,current) : EP_LOADOUT_STORAGE_ARGUMENT;}

static EpLoadoutStorageResult initialize_in_scope(HfMod* mod,uint64_t handle,
    uint64_t owner,const EpLoadoutSourceSnapshot* current,const EpPlayerJoinPeers* expected)
{
    // Even a swallowed recursive request must stop the outer native sequence.
    if (initializing) {initializing->reentered=true;return EP_LOADOUT_STORAGE_STATE;}
    if (!mod || !handle || !owner || !current) return EP_LOADOUT_STORAGE_ARGUMENT;
    if (ep_roster_owner_native_status(mod,owner)!=EP_OWNER_OK) return EP_LOADOUT_STORAGE_SCOPE;
    AcquireSRWLockExclusive(&storage_lock);auto* slot=find(mod,handle);
    if (!slot || (slot->info.state!=EP_LOADOUT_STORAGE_PREPARED && slot->info.state!=EP_LOADOUT_STORAGE_RETAINED)) {
        ReleaseSRWLockExclusive(&storage_lock);return EP_LOADOUT_STORAGE_STATE;
    }
    const EpPlayerJoinPeers unbound={};
    if (!slot->info.sources_imported || !ep_loadout_peers_equal(&slot->peers,expected ? expected : &unbound)) {
        ReleaseSRWLockExclusive(&storage_lock);return EP_LOADOUT_STORAGE_SOURCE;
    }
    Initialization call={slot,owner,current,EP_LOADOUT_STORAGE_NATIVE_FAILED,slot->info.state,false};
    slot->info.initialization_owner=owner;
    slot->info.state=EP_LOADOUT_STORAGE_INITIALIZING;
    slot->info.initialization_step=EP_LOADOUT_INIT_CHECKING;slot->info.owner_result=EP_OWNER_OK;
    ReleaseSRWLockExclusive(&storage_lock);
    initializing=&call;
    const auto owner_result=ep_roster_owner_call(mod,owner,1,initialize_owned,&call);
    initializing=nullptr;
    AcquireSRWLockExclusive(&storage_lock);
    slot->info.owner_result=owner_result;
    if (owner_result!=EP_OWNER_OK) {
        slot->info.state=EP_LOADOUT_STORAGE_QUARANTINED;call.result=EP_LOADOUT_STORAGE_NATIVE_FAILED;
    } else if (call.result==EP_LOADOUT_STORAGE_OK) {
        slot->info.state=EP_LOADOUT_STORAGE_UI_MIGRATED;slot->info.screen_phase=EP_LOADOUT_SCREEN_LIVE;
    }
    else slot->info.state=call.original_state;
    ReleaseSRWLockExclusive(&storage_lock);return call.result;
}

EpLoadoutStorageResult ep_loadout_storage_initialize_in_scope(HfMod* mod,uint64_t handle,uint64_t owner,const EpLoadoutSourceSnapshot* current)
{return initialize_in_scope(mod,handle,owner,current,nullptr);}
EpLoadoutStorageResult ep_loadout_storage_initialize_peers_in_scope(HfMod* mod,uint64_t handle,uint64_t owner,const EpLoadoutSourceSnapshot* current,const EpPlayerJoinPeers* expected)
{
    if (!expected) return EP_LOADOUT_STORAGE_ARGUMENT;
    const auto binding=*expected;return initialize_in_scope(mod,handle,owner,current,&binding);
}

static int quarantine_owner(void*,const EpNativeRosterView*) {return 0;}
int ep_loadout_storage_quarantine_in_scope(HfMod* mod,uint64_t handle,uint64_t owner)
{
    const auto status=ep_roster_owner_native_status(mod,owner);
    if (status!=EP_OWNER_OK && status!=EP_OWNER_FAULTED) return 0;
    AcquireSRWLockExclusive(&storage_lock);auto* slot=find(mod,handle);
    if (!slot || slot->info.initialization_owner!=owner ||
        (slot->info.state!=EP_LOADOUT_STORAGE_PREPARED && slot->info.state!=EP_LOADOUT_STORAGE_RETAINED &&
         slot->info.state!=EP_LOADOUT_STORAGE_UI_MIGRATED && slot->info.state!=EP_LOADOUT_STORAGE_QUARANTINED)) {
        ReleaseSRWLockExclusive(&storage_lock);return 0;
    }
    slot->info.state=EP_LOADOUT_STORAGE_QUARANTINED;
    if (!slot->info.owner_result) slot->info.owner_result=EP_OWNER_CALLBACK_FAILED;
    ReleaseSRWLockExclusive(&storage_lock);
    if (status==EP_OWNER_OK) ep_roster_owner_call(mod,owner,0,quarantine_owner,nullptr);
    return 1;
}

int ep_loadout_storage_screen_return_in_scope(HfMod* mod,uint64_t handle,uint64_t owner,uint32_t rva)
{
    if ((rva!=0x1466170 && rva!=0x1467b90) || ep_roster_owner_native_status(mod,owner)!=EP_OWNER_OK) return 0;
    AcquireSRWLockExclusive(&storage_lock);auto* slot=find(mod,handle);
    const bool valid=slot && slot->info.state==EP_LOADOUT_STORAGE_UI_MIGRATED &&
        slot->info.initialization_owner==owner && (slot->info.screen_phase==EP_LOADOUT_SCREEN_LIVE ||
        slot->info.screen_phase==EP_LOADOUT_SCREEN_CLEANED);
    if (valid) slot->info.screen_phase=rva==0x1467b90 ? EP_LOADOUT_SCREEN_CLEANED : EP_LOADOUT_SCREEN_LIVE;
    ReleaseSRWLockExclusive(&storage_lock);return valid;
}
namespace {
struct ScreenChange {Storage* slot;uint64_t owner,manager;uint32_t rva;EpLoadoutStorageResult result;bool recursive;};
thread_local ScreenChange* changing_screen;
int change_screen(void* opaque,const EpNativeRosterView* view)
{
    auto& call=*(ScreenChange*)opaque;auto& slot=*call.slot;const auto& a=slot.info.binding;
    const auto& b=a.setup.common;const auto& l=b.lifecycle;
    if (view->game!=slot.game || view->roster!=b.roster || view->storage!=b.roster_storage) {
        call.result=EP_LOADOUT_STORAGE_SOURCE;return 1;
    }
    // These are explicit native accesses, protected by the nested owner SEH
    // frame. Never hold storage_lock across a pointer access or native call.
    auto* field=(uint64_t*)(uintptr_t)(call.manager+0xb0);
    if (call.rva==0x14ac340) {
        if (*field!=slot.screen) {call.result=EP_LOADOUT_STORAGE_STALE;return 1;}
        *field=0;
        AcquireSRWLockExclusive(&storage_lock);
        slot.info.screen_manager=call.manager;slot.info.screen_phase=EP_LOADOUT_SCREEN_PARKED;
        ReleaseSRWLockExclusive(&storage_lock);
    } else {
        if (*field) {call.result=EP_LOADOUT_STORAGE_STALE;return 1;}
        AcquireSRWLockExclusive(&storage_lock);slot.info.screen_phase=EP_LOADOUT_SCREEN_REBUILDING;
        ReleaseSRWLockExclusive(&storage_lock);
        memset((void*)(uintptr_t)slot.screen,0,EP_LOADOUT_SCREEN_BYTES);
        memset((void*)(uintptr_t)l.records,0,slot.info.capacity*EP_LOADOUT_RECORD_BYTES);
        memset((void*)(uintptr_t)l.widgets,0,slot.info.capacity*EP_LOADOUT_WIDGET_BYTES);
        memset((void*)(uintptr_t)b.forward_map,0xff,32);memset((void*)(uintptr_t)b.inverse_map,0xff,32);
        const auto construct=(void*(*)(void*))(uintptr_t)slot.info.group.constructor;
        if (construct((void*)(uintptr_t)slot.screen)!=(void*)(uintptr_t)slot.screen || call.recursive ||
            ep_roster_owner_native_status(slot.mod,call.owner)!=EP_OWNER_OK || *field) return 0;
        *field=slot.screen;
        AcquireSRWLockExclusive(&storage_lock);slot.info.screen_phase=EP_LOADOUT_SCREEN_LIVE;
        ReleaseSRWLockExclusive(&storage_lock);
    }
    call.result=EP_LOADOUT_STORAGE_OK;return 1;
}
}
EpLoadoutStorageResult ep_loadout_storage_screen_in_scope(HfMod* mod,uint64_t handle,uint64_t owner,
    uint32_t rva,uint64_t manager)
{
    if (changing_screen) {changing_screen->recursive=true;return EP_LOADOUT_STORAGE_STATE;}
    if (!mod || !handle || !owner || (rva!=0x14984e0 && rva!=0x14ac340)) return EP_LOADOUT_STORAGE_ARGUMENT;
    if (!pointer(manager,0xb8,8)) return EP_LOADOUT_STORAGE_POINTER;
    if (ep_roster_owner_native_status(mod,owner)!=EP_OWNER_OK) return EP_LOADOUT_STORAGE_SCOPE;
    AcquireSRWLockExclusive(&storage_lock);auto* slot=find(mod,handle);
    const bool valid=slot && slot->info.state==EP_LOADOUT_STORAGE_UI_MIGRATED &&
        slot->info.initialization_owner==owner && slot->info.group.constructor &&
        !overlap(manager,0xb8,slot->screen,EP_LOADOUT_SCREEN_BYTES) &&
        !overlap(manager,0xb8,slot->info.arena,slot->info.bytes) &&
        (!slot->info.screen_manager || slot->info.screen_manager==manager) &&
        slot->info.screen_phase==(rva==0x14ac340 ? EP_LOADOUT_SCREEN_CLEANED : EP_LOADOUT_SCREEN_PARKED);
    ReleaseSRWLockExclusive(&storage_lock);
    if (!valid) return EP_LOADOUT_STORAGE_STATE;
    ScreenChange call={slot,owner,manager,rva,EP_LOADOUT_STORAGE_NATIVE_FAILED,false};changing_screen=&call;
    const auto result=ep_roster_owner_call(mod,owner,1,change_screen,&call);changing_screen=nullptr;
    if (result!=EP_OWNER_OK || call.recursive) {
        ep_loadout_storage_quarantine_in_scope(mod,handle,owner);return EP_LOADOUT_STORAGE_NATIVE_FAILED;
    }
    return call.result;
}
