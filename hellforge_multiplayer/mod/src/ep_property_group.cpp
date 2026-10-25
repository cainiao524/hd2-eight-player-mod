/* C-compatible for tests against the actual HellForge loader. */
#include "ep_property_group.h"
#include "ep_property_gate.h"
#include <windows.h>
#include <string.h>
typedef struct EpPropertyGroup {
    HfMod* owner;
    uint64_t handle;
    volatile LONG active;
    uint32_t state,attempts;
    uintptr_t targets[2];
    uint64_t code[2];
} EpPropertyGroup;
static EpPropertyGroup epGroups[EP_PROPERTY_GROUP_SLOTS];
static SRWLOCK epGroupLock=SRWLOCK_INIT;
static uint64_t epGroupSequence;
static EpPropertyGroup* EpGroupFind(HfMod* owner,uint64_t id)
{
    if (owner && id) for (unsigned i=0;i<EP_PROPERTY_GROUP_SLOTS;i++)
        if (epGroups[i].owner==owner && epGroups[i].handle==id) return &epGroups[i];
    return NULL;
}
static void EpGroupInfo(EpPropertyGroup* g,EpPropertyGroupInfo* out)
{
    memset(out,0,sizeof(*out)); out->handle=g->handle; out->state=g->state;
    out->active=(uint32_t)InterlockedCompareExchange(&g->active,0,0); out->published_attempts=g->attempts;
    for (unsigned i=0;i<2;i++) ep_session_code_info(g->owner,g->code[i],&out->code[i]);
}
int ep_property_group_info(HfMod* owner,uint64_t id,EpPropertyGroupInfo* out)
{
    int ok=0; if (!out) return 0; memset(out,0,sizeof(*out));
    AcquireSRWLockShared(&epGroupLock); EpPropertyGroup* g=EpGroupFind(owner,id);
    if (g) { EpGroupInfo(g,out); ok=1; }
    ReleaseSRWLockShared(&epGroupLock); return ok;
}
/* Called with the group lock. Exposed gates can still read their latch/next. */
static int EpGroupCancel(EpPropertyGroup* g)
{
    int ok=1;
    for (unsigned i=0;i<2;i++) if (g->code[i]) {
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
int ep_property_group_prepare(const HfApi* api,HfMod* owner,const EpPropertyGroupBindings* input,EpPropertyGroupInfo* out)
{
    EpPropertyGroupBindings bindings; EpPropertyGroup* g=NULL; int ok=1;
    if (!out) return 0;
    if (input) bindings=*input;
    memset(out,0,sizeof(*out)); if (!input || !owner) return 0;
    AcquireSRWLockExclusive(&epGroupLock);
    if (epGroupSequence!=UINT64_MAX) for (unsigned i=0;i<EP_PROPERTY_GROUP_SLOTS;i++) if (!epGroups[i].handle) {
        g=&epGroups[i]; g->owner=owner; g->handle=++epGroupSequence; g->state=EP_GROUP_PREPARING; break;
    }
    ReleaseSRWLockExclusive(&epGroupLock); if (!g) return 0;
    for (unsigned i=0;i<2;i++) {
        EpSessionCodeInfo allocation; EpPropertyGateImage image;
        EpPropertyAddresses a={bindings.game_base,0,bindings.roster_address,bindings.property_address,bindings.reject[i]};
        if (!ep_session_code_reserve(api,owner,bindings.desired_code[i],i ? 484 : 756,&allocation)) { ok=0; break; }
        AcquireSRWLockExclusive(&epGroupLock); g->code[i]=allocation.handle; ReleaseSRWLockExclusive(&epGroupLock);
        a.code_address=allocation.base;
        if (ep_property_gate_build(i+1,&a,(uintptr_t)&g->active,allocation.next_pointer,&image)!=EP_PROPERTY_OK ||
            (bindings.reject[1-i]>=allocation.base && bindings.reject[1-i]<allocation.base+image.bytes) ||
            !ep_session_code_seal_table(owner,allocation.handle,image.data,image.bytes,image.table_offset,2)) { ok=0; break; }
    }
    AcquireSRWLockExclusive(&epGroupLock);
    if (ok) {
        g->targets[0]=(uintptr_t)bindings.game_base+0x60C640; g->targets[1]=(uintptr_t)bindings.game_base+0x60C890;
        g->state=EP_GROUP_PREPARED;
    } else EpGroupCancel(g);
    if (g->handle) EpGroupInfo(g,out);
    ReleaseSRWLockExclusive(&epGroupLock); return ok;
}
int ep_property_group_publish(HfMod* owner,uint64_t id,int32_t priority)
{
    int ok=1;
    AcquireSRWLockExclusive(&epGroupLock); EpPropertyGroup* g=EpGroupFind(owner,id);
    if (!g || g->state!=EP_GROUP_PREPARED) { ReleaseSRWLockExclusive(&epGroupLock); return 0; }
    g->state=EP_GROUP_PUBLISHING; ReleaseSRWLockExclusive(&epGroupLock);
    for (unsigned i=0;i<2;i++) {
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
int ep_property_group_commit(HfMod* owner,uint64_t id,const EpPropertyCommitGuard* guard)
{
    EpPropertyCommitGuard copy; void* lease=NULL; int entered,ok=0;
    if (!guard || !guard->begin || !guard->validate || !guard->end) return 0;
    copy=*guard;
    AcquireSRWLockExclusive(&epGroupLock); EpPropertyGroup* g=EpGroupFind(owner,id);
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
int ep_property_group_cancel(HfMod* owner,uint64_t id)
{
    int ok=0; AcquireSRWLockExclusive(&epGroupLock); EpPropertyGroup* g=EpGroupFind(owner,id);
    if (g && (g->state==EP_GROUP_PREPARED || g->state==EP_GROUP_READY || g->state==EP_GROUP_FAILED || g->state==EP_GROUP_CANCELLED)) ok=EpGroupCancel(g);
    ReleaseSRWLockExclusive(&epGroupLock); return ok;
}
