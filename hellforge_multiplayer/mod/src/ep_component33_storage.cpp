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
static int C33StorageCancel(C33Storage* s)
{
    if (s->info.family.handle) {
        if (!ep_component33_family_cancel(s->owner,s->info.family.handle)) { s->info.state=EP_C33_STORAGE_CLEANUP_REQUIRED;return 0; }
        memset(&s->info.family,0,sizeof(s->info.family));
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
EpC33StorageResult ep_component33_storage_prepare(const HfApi* api,HfMod* owner,const EpC33StorageBindings* bindings,const EpC33Snapshot* input,EpC33StorageInfo* out)
{
    if (!out) return EP_C33_STORAGE_ARGUMENT;
    EpC33StorageBindings b={};EpC33Snapshot snap={};if (bindings) b=*bindings;if (input) snap=*input;
    memset(out,0,sizeof(*out));if (!owner || !bindings || !input) return EP_C33_STORAGE_ARGUMENT;
    EpC33Migration migrated;auto result=ep_component33_migrate_snapshot(&snap,&migrated);if (result!=EP_C33_STORAGE_OK) return result;
    SYSTEM_INFO system;GetSystemInfo(&system);
    if (b.desired_storage && !C33Address(b.desired_storage,EP_COMPONENT33_STORAGE_BYTES,system.dwAllocationGranularity)) return EP_C33_STORAGE_POINTER;
    C33Storage* s=nullptr;AcquireSRWLockExclusive(&c33StorageLock);
    for (const auto& other:c33Storage) if (other.info.handle &&
        snap.component_address<other.snapshot.component_address+EP_C33_SOURCE_BYTES && other.snapshot.component_address<snap.component_address+EP_C33_SOURCE_BYTES) {
        ReleaseSRWLockExclusive(&c33StorageLock);return EP_C33_STORAGE_CONFLICT;
    }
    if (c33StorageSequence!=UINT64_MAX) for (auto& other:c33Storage) if (!other.info.handle) {
        s=&other;s->owner=owner;s->snapshot=snap;s->info.handle=++c33StorageSequence;s->info.state=EP_C33_STORAGE_PREPARING;break;
    }
    ReleaseSRWLockExclusive(&c33StorageLock);if (!s) return EP_C33_STORAGE_RESERVE;
    void* storage=VirtualAlloc((void*)b.desired_storage,EP_COMPONENT33_STORAGE_BYTES,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    if (!storage) result=EP_C33_STORAGE_RESERVE;
    else {
        AcquireSRWLockExclusive(&c33StorageLock);s->info.storage_address=(uintptr_t)storage;s->info.storage_bytes=EP_COMPONENT33_STORAGE_BYTES;ReleaseSRWLockExclusive(&c33StorageLock);
        if (!C33Address((uintptr_t)storage,EP_COMPONENT33_STORAGE_BYTES,16) || (b.desired_storage && (uintptr_t)storage!=b.desired_storage)) result=EP_C33_STORAGE_POINTER;
        else {
            memcpy(storage,migrated.data,sizeof(migrated.data));
            EpComponent33FamilyBindings f={};f.game_base=b.game_base;f.component_address=snap.component_address;f.storage_address=(uintptr_t)storage;f.reject_address=b.reject_address;
            memcpy(f.desired_code,b.desired_code,sizeof(f.desired_code));EpComponent33FamilyInfo family={};
            auto fr=ep_component33_family_prepare(api,owner,&f,&family);
            AcquireSRWLockExclusive(&c33StorageLock);s->info.family=family;s->info.family_result=fr;ReleaseSRWLockExclusive(&c33StorageLock);
            if (fr!=EP_PROPERTY_OK) result=EP_C33_STORAGE_FAMILY;
        }
    }
    AcquireSRWLockExclusive(&c33StorageLock);
    if (result==EP_C33_STORAGE_OK) s->info.state=EP_C33_STORAGE_PREPARED;
    else if (!C33StorageCancel(s)) result=EP_C33_STORAGE_CLEANUP;
    if (s->info.handle) C33StorageInfo(s,out);
    ReleaseSRWLockExclusive(&c33StorageLock);return result;
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
EpC33StorageResult ep_component33_storage_retain(HfMod* owner,uint64_t id,const EpC33Snapshot* current)
{
    if (!current) return EP_C33_STORAGE_ARGUMENT;
    EpC33Snapshot copy=*current;EpC33Migration migrated;auto result=ep_component33_migrate_snapshot(&copy,&migrated);
    if (result!=EP_C33_STORAGE_OK) return result;
    AcquireSRWLockExclusive(&c33StorageLock);auto* s=C33StorageFind(owner,id);
    if (!s || s->info.state!=EP_C33_STORAGE_PREPARED) result=EP_C33_STORAGE_STATE;
    else if (!C33SameSnapshot(s->snapshot,copy) || memcmp((void*)(uintptr_t)s->info.storage_address,migrated.data,sizeof(migrated.data))) result=EP_C33_STORAGE_STALE;
    else if (!ep_component33_family_retain(owner,s->info.family.handle)) result=EP_C33_STORAGE_FAMILY;
    else s->info.state=EP_C33_STORAGE_RETAINED;
    ReleaseSRWLockExclusive(&c33StorageLock);return result;
}
