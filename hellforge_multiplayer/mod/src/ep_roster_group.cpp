/* C-compatible for tests against the actual HellForge loader. */
#include "ep_roster_group.h"
#include "ep_roster_gate.h"
#include <windows.h>
#include <string.h>
typedef struct EpRosterGroup {
    HfMod* owner;
    uint64_t handle;
    volatile LONG active;
    uint32_t state,attempts;
    uintptr_t targets[EP_ROSTER_ENTRIES];
    uint64_t code[EP_ROSTER_ENTRIES];
} EpRosterGroup;
static EpRosterGroup epGroups[EP_ROSTER_GROUP_SLOTS];
static SRWLOCK epGroupLock=SRWLOCK_INIT;
static uint64_t epGroupSequence;
static EpRosterGroup* EpGroupFind(HfMod* owner,uint64_t id)
{
    if (owner && id) for (unsigned i=0;i<EP_ROSTER_GROUP_SLOTS;i++)
        if (epGroups[i].owner==owner && epGroups[i].handle==id) return &epGroups[i];
    return NULL;
}
static void EpGroupInfo(EpRosterGroup* g,EpRosterGroupInfo* out)
{
    memset(out,0,sizeof(*out)); out->handle=g->handle; out->state=g->state;
    out->active=(uint32_t)InterlockedCompareExchange(&g->active,0,0); out->published_attempts=g->attempts;
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) ep_session_code_info(g->owner,g->code[i],&out->code[i]);
}
int ep_roster_group_info(HfMod* owner,uint64_t id,EpRosterGroupInfo* out)
{
    int ok=0; if (!out) return 0; memset(out,0,sizeof(*out));
    AcquireSRWLockShared(&epGroupLock); EpRosterGroup* g=EpGroupFind(owner,id);
    if (g) { EpGroupInfo(g,out); ok=1; }
    ReleaseSRWLockShared(&epGroupLock); return ok;
}
/* Called with the group lock. Exposed gates can still read their latch/next. */
static int EpGroupCancel(EpRosterGroup* g)
{
    int ok=1;
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) if (g->code[i]) {
        EpSessionCodeInfo info;
        if (!ep_session_code_info(g->owner,g->code[i],&info)) { ok=0; continue; }
        if (!info.pinned) {
            if (ep_session_code_discard(g->owner,g->code[i])) g->code[i]=0;
            else ok=0;
        }
    }
    if (ok && !g->attempts) memset(g,0,sizeof(*g));
    else g->state=ok ? EP_GROUP_CANCELLED : EP_GROUP_FAILED;
    return ok;
}
int ep_roster_group_prepare(const HfApi* api,HfMod* owner,const EpRosterGroupBindings* input,EpRosterGroupInfo* out)
{
    EpRosterGroupBindings bindings; EpRosterGroup* g=NULL; int ok=1;
    if (!out) return 0;
    if (input) bindings=*input;
    memset(out,0,sizeof(*out)); if (!input || !owner) return 0;
    if (!bindings.storage_address || (bindings.storage_address&15) || bindings.storage_address>(UINT64_C(1)<<47)-0x680) return 0;
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++)
        if (bindings.reject[i]>=bindings.storage_address && bindings.reject[i]<bindings.storage_address+0x680) return 0;
    AcquireSRWLockExclusive(&epGroupLock);
    if (epGroupSequence!=UINT64_MAX) for (unsigned i=0;i<EP_ROSTER_GROUP_SLOTS;i++) if (!epGroups[i].handle) {
        g=&epGroups[i]; g->owner=owner; g->handle=++epGroupSequence; g->state=EP_GROUP_PREPARING; break;
    }
    ReleaseSRWLockExclusive(&epGroupLock); if (!g) return 0;
    EpSessionCodeInfo allocations[EP_ROSTER_ENTRIES]={{0}};
    /* Allocate every entry before binding insert/remove to our mover body. */
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {
        EpRosterGateLayout layout; ep_roster_gate_layout(i+1,&layout);
        if (!ep_session_code_reserve(api,owner,bindings.desired_code[i],layout.image_bytes,&allocations[i])) { ok=0; break; }
        AcquireSRWLockExclusive(&epGroupLock); g->code[i]=allocations[i].handle; ReleaseSRWLockExclusive(&epGroupLock);
    }
    /* Sealing protects complete committed pages, including image padding.
     * No storage, rejection path or next slot may occupy that padding. */
    SYSTEM_INFO system;GetSystemInfo(&system);
    for (unsigned i=0;ok && i<EP_ROSTER_ENTRIES;i++) {
        for (unsigned j=0;j<EP_ROSTER_ENTRIES;j++) {
            uintptr_t base=allocations[j].base;
            uint32_t bytes=(allocations[j].bytes+system.dwPageSize-1)/system.dwPageSize*system.dwPageSize;
            uintptr_t next=allocations[j].next_pointer;
            if ((bindings.reject[i]>=base && bindings.reject[i]<base+bytes) ||
                (bindings.reject[i]>=next && bindings.reject[i]<next+8) ||
                (bindings.roster_address<base+bytes && base<bindings.roster_address+0x428) ||
                (bindings.storage_address<base+bytes && base<bindings.storage_address+0x680) ||
                (allocations[i].base<next+8 && next<allocations[i].base+allocations[i].bytes)) ok=0;
        }
        if (bindings.reject[i]>=(uintptr_t)&g->active && bindings.reject[i]<(uintptr_t)&g->active+4) ok=0;
    }
    for (unsigned i=0;ok && i<EP_ROSTER_ENTRIES;i++) {
        EpRosterGateImage image;
        EpInsertAddresses a={bindings.game_base,allocations[i].base,bindings.roster_address,bindings.storage_address,
            allocations[EP_ROSTER_MOVER-1].base+32,bindings.reject[i]};
        if (ep_roster_gate_build(i+1,&a,(uintptr_t)&g->active,allocations[i].next_pointer,&image)!=EP_PROPERTY_OK ||
            !ep_session_code_seal_table(owner,g->code[i],image.data,image.bytes,image.table_offset,image.function_count)) ok=0;
    }
    AcquireSRWLockExclusive(&epGroupLock);
    if (ok) {
        for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {
            EpRosterGateLayout layout;ep_roster_gate_layout(i+1,&layout);
            g->targets[i]=(uintptr_t)bindings.game_base+layout.original_rva;
        }
        g->state=EP_GROUP_PREPARED;
    } else EpGroupCancel(g);
    if (g->handle) EpGroupInfo(g,out);
    ReleaseSRWLockExclusive(&epGroupLock); return ok;
}
int ep_roster_group_publish(HfMod* owner,uint64_t id,int32_t priority)
{
    int ok=1;
    AcquireSRWLockExclusive(&epGroupLock); EpRosterGroup* g=EpGroupFind(owner,id);
    if (!g || g->state!=EP_GROUP_PREPARED) { ReleaseSRWLockExclusive(&epGroupLock); return 0; }
    g->state=EP_GROUP_PUBLISHING; ReleaseSRWLockExclusive(&epGroupLock);
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {
        int published=ep_session_code_publish(owner,g->code[i],g->targets[i],priority);
        EpSessionCodeInfo info;
        AcquireSRWLockExclusive(&epGroupLock);
        if (ep_session_code_info(owner,g->code[i],&info) && info.pinned) g->attempts++;
        ReleaseSRWLockExclusive(&epGroupLock);
        if (!published) { ok=0; break; }
    }
    AcquireSRWLockExclusive(&epGroupLock); g->state=ok ? EP_GROUP_READY : EP_GROUP_FAILED;
    ReleaseSRWLockExclusive(&epGroupLock); return ok;
}
int ep_roster_group_commit(HfMod* owner,uint64_t id,const EpPropertyCommitGuard* guard)
{
    EpPropertyCommitGuard copy; void* lease=NULL; int entered,ok=0;
    if (!guard || !guard->begin || !guard->validate || !guard->end) return 0;
    copy=*guard;
    AcquireSRWLockExclusive(&epGroupLock); EpRosterGroup* g=EpGroupFind(owner,id);
    if (!g || g->state!=EP_GROUP_READY) { ReleaseSRWLockExclusive(&epGroupLock); return 0; }
    g->state=EP_GROUP_COMMITTING; ReleaseSRWLockExclusive(&epGroupLock);
    entered=copy.begin(copy.context,&lease);
    if (entered && lease) ok=copy.validate(copy.context,lease)!=0;
    AcquireSRWLockExclusive(&epGroupLock);
    if (ok) InterlockedExchange(&g->active,1);
    ReleaseSRWLockExclusive(&epGroupLock);
    if (entered) copy.end(copy.context,lease,ok);
    AcquireSRWLockExclusive(&epGroupLock); g->state=ok ? EP_GROUP_ACTIVE : EP_GROUP_READY;
    ReleaseSRWLockExclusive(&epGroupLock);
    return ok;
}
int ep_roster_group_cancel(HfMod* owner,uint64_t id)
{
    int ok=0; AcquireSRWLockExclusive(&epGroupLock); EpRosterGroup* g=EpGroupFind(owner,id);
    if (g && (g->state==EP_GROUP_PREPARED || g->state==EP_GROUP_READY || g->state==EP_GROUP_FAILED || g->state==EP_GROUP_CANCELLED)) ok=EpGroupCancel(g);
    ReleaseSRWLockExclusive(&epGroupLock); return ok;
}
