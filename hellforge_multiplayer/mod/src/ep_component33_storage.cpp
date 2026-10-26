#include "ep_component33_storage.h"
#include <windows.h>
#include <string.h>
static uint32_t C33U32(const uint8_t* p) { uint32_t v;memcpy(&v,p,4);return v; }
static uint64_t C33U64(const uint8_t* p) { uint64_t v;memcpy(&v,p,8);return v; }
static bool C33Address(uint64_t p,uint64_t n,uint64_t align)
{ return p>=0x10000 && p<=(UINT64_C(1)<<47)-n && !(p%align); }
EpC33StorageResult ep_component33_migrate_snapshot(const EpC33Snapshot* input,EpC33Migration* out)
{
    if (!out) return EP_C33_STORAGE_ARGUMENT;
    EpC33Snapshot s={};if (input) s=*input;
    memset(out,0,sizeof(*out));if (!input) return EP_C33_STORAGE_ARGUMENT;
    if (!C33Address(s.component_address,EP_C33_SOURCE_BYTES,8) || s.global_component!=s.component_address) return EP_C33_STORAGE_POINTER;
    const uint8_t* p=s.component;uint32_t t=C33U32(p+8),d=C33U32(p+12),prefix=C33U32(p+16);
    if (t>4 || d>t || prefix>d || s.entity_count!=t) return EP_C33_STORAGE_COUNTS;
    if (C33U64(p+0x58)!=s.component_address+0x14 || C33U32(p+0x60)!=8 || C33U32(p+0x64)) return EP_C33_STORAGE_MAP;
    uint32_t occupied=0,ordinals=0,seed=C33U32(p+0x68);
    for (unsigned b=0;b<8;b++) {
        uint32_t id=C33U32(p+0x14+8*b),ordinal=C33U32(p+0x18+8*b);
        if (!id) continue;
        if (id==s.invalid_entity_id || ordinal>=t || (ordinals&(1u<<ordinal))) return EP_C33_STORAGE_MAP;
        ordinals|=1u<<ordinal;occupied++;
    }
    if (occupied!=t) return EP_C33_STORAGE_MAP;
    for (unsigned i=0;i<t;i++) {
        uint64_t address=C33U64(p+0x70+8*i);const EpC33EntitySnapshot* entity=nullptr;
        if (!C33Address(address,0x18,1)) return EP_C33_STORAGE_IDENTITY;
        for (unsigned j=0;j<t;j++) {
            if (s.entities[j].address==address) { if (entity) return EP_C33_STORAGE_IDENTITY;entity=&s.entities[j]; }
            for (unsigned k=0;k<j;k++) if (s.entities[j].address==s.entities[k].address || s.entities[j].id==s.entities[k].id) return EP_C33_STORAGE_IDENTITY;
        }
        if (!entity || !entity->id || entity->id==s.invalid_entity_id) return EP_C33_STORAGE_IDENTITY;
        unsigned bucket=(entity->id*seed)&7;bool found=false;
        for (unsigned n=0;n<8;n++,bucket=(bucket+1)&7) {
            uint32_t id=C33U32(p+0x14+bucket*8);
            if (!id) break;
            if (id==entity->id) { found=C33U32(p+0x18+bucket*8)==i;break; }
        }
        if (!found) return EP_C33_STORAGE_MAP;
        if (i<d && ((entity->flags&1)!=unsigned(i<prefix))) return EP_C33_STORAGE_FLAGS;
    }
    /* Deliberately preserve inactive old slots and every opaque resource bit. */
    memcpy(out->data,p+0x70,4*8);memcpy(out->data+0x40,p+0x90,4);
    memcpy(out->data+0x50,p+0x98,4*0x50);memcpy(out->data+0x2d0,p+0x1d8,4*0x38);
    return EP_C33_STORAGE_OK;
}
struct C33Storage {
    HfMod* owner;
    EpC33StorageInfo info;
    EpC33Snapshot snapshot;
    uint64_t game_base;
    bool resource_mode;
    EpC33ResourceSnapshot resource_snapshot;
    EpC33ResourceStorageInfo resources;
    uint64_t resource_scope_owner;
};
static C33Storage c33Storage[EP_C33_FAMILY_SLOTS];
static SRWLOCK c33StorageLock=SRWLOCK_INIT;
static uint64_t c33StorageSequence;
static C33Storage* C33StorageFind(HfMod* owner,uint64_t id)
{
    if (owner && id) for (auto& s:c33Storage) if (s.owner==owner && s.info.handle==id) return &s;
    return nullptr;
}
static void C33StorageInfo(C33Storage* s,EpC33StorageInfo* out)
{
    *out=s->info;
    if (out->family.handle) ep_component33_family_info(s->owner,out->family.handle,&out->family);
}
int ep_component33_storage_info(HfMod* owner,uint64_t id,EpC33StorageInfo* out)
{
    if (!out) return 0;memset(out,0,sizeof(*out));
    AcquireSRWLockShared(&c33StorageLock);auto* s=C33StorageFind(owner,id);
    if (s) C33StorageInfo(s,out);
    ReleaseSRWLockShared(&c33StorageLock);return s!=nullptr;
}
int ep_component33_storage_resources(HfMod* owner,uint64_t id,EpC33ResourceStorageInfo* out)
{
    if (!out) return 0;memset(out,0,sizeof(*out));
    AcquireSRWLockShared(&c33StorageLock);auto* s=C33StorageFind(owner,id);int ok=s && s->resource_mode;
    if (ok) {
        *out=s->resources;EpC33FamilyResources r={};
        if ((s->info.state==EP_C33_STORAGE_PREPARED || s->info.state==EP_C33_STORAGE_RETAINED) &&
            s->info.family.handle && ep_component33_family_resources(owner,s->info.family.handle,&r)) out->windows=r.windows;
    }
    ReleaseSRWLockShared(&c33StorageLock);return ok;
}
int ep_component33_storage_resource_scope(HfMod* owner,uint64_t id,uint64_t roster_owner,uint64_t game,EpC33ResourceScopeView* out)
{
    if (!out) return 0;memset(out,0,sizeof(*out));if (!roster_owner) return 0;
    AcquireSRWLockExclusive(&c33StorageLock);auto* s=C33StorageFind(owner,id);
    int ok=s && s->resource_mode && s->info.state==EP_C33_STORAGE_RETAINED && s->game_base==game &&
        (!s->resource_scope_owner || s->resource_scope_owner==roster_owner);
    if (ok) {
        s->resource_scope_owner=roster_owner;out->game=game;out->component=s->snapshot.component_address;
        out->storage=s->info.storage_address;out->resources=s->resources.binding;
    }
    ReleaseSRWLockExclusive(&c33StorageLock);return ok;
}
static int C33StorageCancel(C33Storage* s)
{
    if (s->info.family.handle) {
        if (!ep_component33_family_cancel(s->owner,s->info.family.handle)) { s->info.state=EP_C33_STORAGE_CLEANUP_REQUIRED;return 0; }
        memset(&s->info.family,0,sizeof(s->info.family));
    }
    if (s->resources.binding.address) {
        if (!VirtualFree((void*)(uintptr_t)s->resources.binding.address,0,MEM_RELEASE)) { s->info.state=EP_C33_STORAGE_CLEANUP_REQUIRED;return 0; }
        memset(&s->resources,0,sizeof(s->resources));
    }
    if (s->info.storage_address && !VirtualFree((void*)(uintptr_t)s->info.storage_address,0,MEM_RELEASE)) {
        s->info.state=EP_C33_STORAGE_CLEANUP_REQUIRED;return 0;
    }
    memset(s,0,sizeof(*s));return 1;
}
int ep_component33_storage_cancel(HfMod* owner,uint64_t id)
{
    int ok=0;AcquireSRWLockExclusive(&c33StorageLock);auto* s=C33StorageFind(owner,id);
    if (s && (s->info.state==EP_C33_STORAGE_PREPARED || s->info.state==EP_C33_STORAGE_CLEANUP_REQUIRED)) ok=C33StorageCancel(s);
    ReleaseSRWLockExclusive(&c33StorageLock);return ok;
}
static bool C33StorageOverlap(uint64_t a,uint64_t n,uint64_t b,uint64_t m) { return a<b+m && b<a+n; }
static int C33ResourceSnapshotValid(const EpC33ResourceSnapshot* s)
{
    alignas(8) uint8_t check[48+24*128];EpC33ResourceBinding b={0x10000,128,0};
    return ep_c33_resource_migrate(&b,s,check,sizeof(check))==EP_RESOURCE_OK;
}
static EpC33StorageResult C33StoragePrepare(const HfApi* api,HfMod* owner,const EpC33StorageBindings* bindings,const EpC33Snapshot* input,
    const EpC33ResourceStorageConfig* config,const EpC33ResourceSnapshot* resource,EpC33StorageInfo* out)
{
    if (!out) return EP_C33_STORAGE_ARGUMENT;
    EpC33StorageBindings b={};EpC33Snapshot snap={};if (bindings) b=*bindings;if (input) snap=*input;
    memset(out,0,sizeof(*out));if (!owner || !bindings || !input) return EP_C33_STORAGE_ARGUMENT;
    EpC33Migration migrated;auto result=ep_component33_migrate_snapshot(&snap,&migrated);if (result!=EP_C33_STORAGE_OK) return result;
    SYSTEM_INFO system;GetSystemInfo(&system);
    uint32_t arena_bytes=0,resource_page=0;
    if (config) {
        arena_bytes=ep_c33_resource_bytes(config->capacity);
        if (!arena_bytes || config->reserved || !resource || !C33ResourceSnapshotValid(resource)) return EP_C33_STORAGE_RESOURCES;
        resource_page=(arena_bytes+system.dwPageSize-1)/system.dwPageSize*system.dwPageSize;
        if (config->desired_address && !C33Address(config->desired_address,2*resource_page,system.dwAllocationGranularity)) return EP_C33_STORAGE_POINTER;
        if (!C33Address(b.game_base,0x4000000,4096)) return EP_C33_STORAGE_POINTER;
    }
    if (b.desired_storage && !C33Address(b.desired_storage,EP_COMPONENT33_STORAGE_BYTES,system.dwAllocationGranularity)) return EP_C33_STORAGE_POINTER;
    C33Storage* s=nullptr;AcquireSRWLockExclusive(&c33StorageLock);
    for (const auto& other:c33Storage) if (other.info.handle && (((config || other.resource_mode) && other.game_base==b.game_base) ||
        (snap.component_address<other.snapshot.component_address+EP_C33_SOURCE_BYTES && other.snapshot.component_address<snap.component_address+EP_C33_SOURCE_BYTES))) {
        ReleaseSRWLockExclusive(&c33StorageLock);return EP_C33_STORAGE_CONFLICT;
    }
    if (c33StorageSequence!=UINT64_MAX) for (auto& other:c33Storage) if (!other.info.handle) {
        s=&other;s->owner=owner;s->snapshot=snap;s->game_base=b.game_base;s->resource_mode=config!=nullptr;
        if (resource) s->resource_snapshot=*resource;
        s->info.handle=++c33StorageSequence;s->info.state=EP_C33_STORAGE_PREPARING;break;
    }
    ReleaseSRWLockExclusive(&c33StorageLock);if (!s) return EP_C33_STORAGE_RESERVE;
    void* storage=VirtualAlloc((void*)b.desired_storage,EP_COMPONENT33_STORAGE_BYTES,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    if (!storage) result=EP_C33_STORAGE_RESERVE;
    else {
        AcquireSRWLockExclusive(&c33StorageLock);s->info.storage_address=(uintptr_t)storage;s->info.storage_bytes=EP_COMPONENT33_STORAGE_BYTES;ReleaseSRWLockExclusive(&c33StorageLock);
        if (!C33Address((uintptr_t)storage,EP_COMPONENT33_STORAGE_BYTES,16) || (b.desired_storage && (uintptr_t)storage!=b.desired_storage)) result=EP_C33_STORAGE_POINTER;
        else {
            memcpy(storage,migrated.data,sizeof(migrated.data));
            if (config) {
                void* arena=VirtualAlloc((void*)config->desired_address,2*resource_page,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
                if (!arena) result=EP_C33_STORAGE_RESERVE;
                else {
                    EpC33ResourceStorageInfo r={};r.binding={(uintptr_t)arena,config->capacity,0};r.arena_bytes=arena_bytes;r.allocation_bytes=2*resource_page;
                    AcquireSRWLockExclusive(&c33StorageLock);s->resources=r;ReleaseSRWLockExclusive(&c33StorageLock);
                    uint64_t at=(uintptr_t)arena;
                    if (!C33Address(at,r.allocation_bytes,16) || (config->desired_address && at!=config->desired_address)) result=EP_C33_STORAGE_POINTER;
                    else if (C33StorageOverlap(at,r.allocation_bytes,b.game_base,0x4000000) ||
                        C33StorageOverlap(at,r.allocation_bytes,snap.component_address,EP_C33_SOURCE_BYTES) ||
                        C33StorageOverlap(at,r.allocation_bytes,b.reject_address,1) ||
                        C33StorageOverlap(at,r.allocation_bytes,(uintptr_t)c33Storage,sizeof(c33Storage))) result=EP_C33_STORAGE_POINTER;
                    else if (ep_c33_resource_migrate(&r.binding,resource,arena,arena_bytes)!=EP_RESOURCE_OK) result=EP_C33_STORAGE_RESOURCES;
                    else {
                        void* baseline=(uint8_t*)arena+resource_page;memcpy(baseline,arena,arena_bytes);DWORD previous;
                        if (!VirtualProtect(baseline,resource_page,PAGE_READONLY,&previous)) result=EP_C33_STORAGE_RESOURCES;
                    }
                }
            }
            EpComponent33FamilyBindings f={};f.game_base=b.game_base;f.component_address=snap.component_address;f.storage_address=(uintptr_t)storage;f.reject_address=b.reject_address;
            memcpy(f.desired_code,b.desired_code,sizeof(f.desired_code));EpComponent33FamilyInfo family={};
            if (result==EP_C33_STORAGE_OK) {
                auto fr=config ? ep_component33_family_prepare_resources(api,owner,&f,&s->resources.binding,&family) : ep_component33_family_prepare(api,owner,&f,&family);
                AcquireSRWLockExclusive(&c33StorageLock);s->info.family=family;s->info.family_result=fr;ReleaseSRWLockExclusive(&c33StorageLock);
                if (fr!=EP_PROPERTY_OK) result=EP_C33_STORAGE_FAMILY;
            }
        }
    }
    AcquireSRWLockExclusive(&c33StorageLock);
    if (result==EP_C33_STORAGE_OK) s->info.state=EP_C33_STORAGE_PREPARED;
    else if (!C33StorageCancel(s)) result=EP_C33_STORAGE_CLEANUP;
    if (s->info.handle) C33StorageInfo(s,out);
    ReleaseSRWLockExclusive(&c33StorageLock);return result;
}
EpC33StorageResult ep_component33_storage_prepare(const HfApi* api,HfMod* owner,const EpC33StorageBindings* b,const EpC33Snapshot* s,EpC33StorageInfo* out)
{ return C33StoragePrepare(api,owner,b,s,nullptr,nullptr,out); }
EpC33StorageResult ep_component33_storage_prepare_resources(const HfApi* api,HfMod* owner,const EpC33StorageBindings* b,const EpC33Snapshot* s,
    const EpC33ResourceStorageConfig* config,const EpC33ResourceSnapshot* resource,EpC33StorageInfo* out)
{
    if (!config || !resource) { if (out) memset(out,0,sizeof(*out));return EP_C33_STORAGE_ARGUMENT; }
    EpC33ResourceStorageConfig copy=*config;EpC33ResourceSnapshot snapshot=*resource;
    return C33StoragePrepare(api,owner,b,s,&copy,&snapshot,out);
}
static bool C33SameSnapshot(const EpC33Snapshot& a,const EpC33Snapshot& b)
{
    if (a.component_address!=b.component_address || a.global_component!=b.global_component || a.invalid_entity_id!=b.invalid_entity_id ||
        a.entity_count!=b.entity_count || memcmp(a.component,b.component,EP_C33_SOURCE_BYTES)) return false;
    for (unsigned i=0;i<a.entity_count;i++) {
        bool found=false;
        for (unsigned j=0;j<b.entity_count;j++) if (a.entities[i].address==b.entities[j].address && a.entities[i].id==b.entities[j].id && a.entities[i].flags==b.entities[j].flags) found=true;
        if (!found) return false;
    }
    return true;
}
static EpC33StorageResult C33StorageRetain(HfMod* owner,uint64_t id,const EpC33Snapshot* current,const EpC33ResourceSnapshot* resource)
{
    if (!current) return EP_C33_STORAGE_ARGUMENT;
    EpC33Snapshot copy=*current;EpC33Migration migrated;auto result=ep_component33_migrate_snapshot(&copy,&migrated);
    if (result!=EP_C33_STORAGE_OK) return result;
    if (resource && !C33ResourceSnapshotValid(resource)) return EP_C33_STORAGE_RESOURCES;
    AcquireSRWLockExclusive(&c33StorageLock);auto* s=C33StorageFind(owner,id);
    if (!s || s->info.state!=EP_C33_STORAGE_PREPARED) result=EP_C33_STORAGE_STATE;
    else if (s->resource_mode!=(resource!=nullptr)) result=EP_C33_STORAGE_ARGUMENT;
    else if (!C33SameSnapshot(s->snapshot,copy) || memcmp((void*)(uintptr_t)s->info.storage_address,migrated.data,sizeof(migrated.data))) result=EP_C33_STORAGE_STALE;
    else if (resource && (s->resource_snapshot.seed!=resource->seed || s->resource_snapshot.queued!=resource->queued ||
        memcmp(s->resource_snapshot.entries,resource->entries,sizeof(resource->entries)) ||
        memcmp(s->resource_snapshot.queue,resource->queue,(size_t)resource->queued*8) ||
        memcmp((void*)(uintptr_t)s->resources.binding.address,(void*)(uintptr_t)(s->resources.binding.address+s->resources.allocation_bytes/2),s->resources.arena_bytes))) result=EP_C33_STORAGE_STALE;
    else if (!ep_component33_family_retain(owner,s->info.family.handle)) result=EP_C33_STORAGE_FAMILY;
    else s->info.state=EP_C33_STORAGE_RETAINED;
    ReleaseSRWLockExclusive(&c33StorageLock);return result;
}
EpC33StorageResult ep_component33_storage_retain(HfMod* owner,uint64_t id,const EpC33Snapshot* current)
{ return C33StorageRetain(owner,id,current,nullptr); }
EpC33StorageResult ep_component33_storage_retain_resources(HfMod* owner,uint64_t id,const EpC33Snapshot* current,const EpC33ResourceSnapshot* resource)
{
    if (!resource) return EP_C33_STORAGE_ARGUMENT;
    EpC33ResourceSnapshot copy=*resource;return C33StorageRetain(owner,id,current,&copy);
}
