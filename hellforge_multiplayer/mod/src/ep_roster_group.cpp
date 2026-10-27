/* C-compatible for tests against the actual HellForge loader. */
#include "ep_roster_group.h"
#include "ep_player_join_call.h"
#include "ep_roster_group_transition.h"
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
    uint64_t storage_owner;
    EpRosterCallContext calls[EP_ROSTER_ENTRIES];
    volatile LONG switching;
    uint64_t transition;
} EpRosterGroup;
static EpRosterGroup epGroups[EP_ROSTER_GROUP_SLOTS];
static SRWLOCK epGroupLock=SRWLOCK_INIT;
static uint64_t epGroupSequence;
static uint64_t epTransitionSequence;
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
    out->storage_owner=g->storage_owner;
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
static int EpGroupPrepare(const HfApi* api,HfMod* owner,const EpRosterGroupBindings* input,uint64_t storage_owner,
    const EpRosterCallPolicy* policy,EpRosterGroupInfo* out)
{
    EpRosterGroupBindings bindings; EpRosterGroup* g=NULL; int ok=1;
    if (!out) return 0;
    if (input) bindings=*input;
    memset(out,0,sizeof(*out)); if (!input || !owner) return 0;
    if (storage_owner && (!policy || !policy->failure || ep_roster_owner_check_binding(owner,storage_owner,
        bindings.game_base,bindings.roster_address,bindings.storage_address)!=EP_OWNER_OK)) return 0;
    if (!bindings.storage_address || (bindings.storage_address&15) || bindings.storage_address>(UINT64_C(1)<<47)-0x680) return 0;
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++)
        if (bindings.reject[i]>=bindings.storage_address && bindings.reject[i]<bindings.storage_address+0x680) return 0;
    uintptr_t groups=(uintptr_t)epGroups,groups_end=groups+sizeof(epGroups);
    if ((bindings.roster_address<groups_end && groups<bindings.roster_address+0x428) ||
        (bindings.storage_address<groups_end && groups<bindings.storage_address+0x680)) return 0;
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) if (bindings.reject[i]>=groups && bindings.reject[i]<groups_end) return 0;
    AcquireSRWLockExclusive(&epGroupLock);
    if (epGroupSequence!=UINT64_MAX) for (unsigned i=0;i<EP_ROSTER_GROUP_SLOTS;i++) if (!epGroups[i].handle) {
        g=&epGroups[i]; g->owner=owner; g->handle=++epGroupSequence; g->state=EP_GROUP_PREPARING;
        g->storage_owner=storage_owner;break;
    }
    ReleaseSRWLockExclusive(&epGroupLock); if (!g) return 0;
    EpSessionCodeInfo allocations[EP_ROSTER_ENTRIES]={{0}};
    /* Allocate every entry before binding its internal mover, association or getter body. */
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
        if (i+1==EP_ROSTER_REGISTRY_UPDATE) a.move_code_address=allocations[EP_ROSTER_ASSOCIATION-1].base+32;
        if (i+1==EP_ROSTER_DEPARTURE) a.move_code_address=allocations[EP_ROSTER_GETTER-1].base+32;
        if (ep_roster_gate_build(i+1,&a,(uintptr_t)&g->active,allocations[i].next_pointer,&image)!=EP_PROPERTY_OK) {ok=0;break;}
        if (i+1==EP_ROSTER_PLAYER_JOIN) {
            uint32_t thunk;memcpy(&thunk,image.data+image.table_offset+8*12,4);
            uintptr_t checked=ep_player_join_creation_entry();memcpy(image.data+thunk+2,&checked,8);
        }
        if (storage_owner) {
            EpRosterCallContext* c=&g->calls[i];
            c->mod=owner;c->owner=storage_owner;c->game=bindings.game_base;c->roster=bindings.roster_address;c->storage=bindings.storage_address;
            c->active=(volatile int32_t*)&g->active;c->next_pointer=allocations[i].next_pointer;c->body=allocations[i].base+32;
            c->kind=i+1;c->policy=*policy;
            c->switching=(volatile int32_t*)&g->switching;
            if (!ep_roster_call_prefix(c,image.data)) {ok=0;break;}
        }
        if (i+1==EP_ROSTER_PLAYER_JOIN) {
            uint32_t handler;memcpy(&handler,image.data+image.table_offset+9*12,4);
            const EpSessionGsCheck gs={1,handler,(uintptr_t)bindings.game_base+0x21044a0};
            if (!ep_session_code_seal_player_join(owner,g->code[i],image.data,image.bytes,image.table_offset,&gs)) ok=0;
        } else if (i+1==EP_ROSTER_STATE_UPDATE) {
            const EpSessionGsCheck gs={2,1952,(uintptr_t)bindings.game_base+0x21044a0};
            if (!ep_session_code_seal_gs_table(owner,g->code[i],image.data,image.bytes,image.table_offset,image.function_count,&gs)) ok=0;
        } else if (!ep_session_code_seal_table(owner,g->code[i],image.data,image.bytes,image.table_offset,image.function_count)) ok=0;
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
int ep_roster_group_prepare(const HfApi* api,HfMod* mod,const EpRosterGroupBindings* b,EpRosterGroupInfo* out)
{return EpGroupPrepare(api,mod,b,0,NULL,out);}
int ep_roster_group_prepare_owned(const HfApi* api,HfMod* mod,const EpRosterGroupBindings* b,uint64_t storage_owner,
    const EpRosterCallPolicy* policy,EpRosterGroupInfo* out)
{
    if (!storage_owner) {if(out) memset(out,0,sizeof(*out));return 0;}
    return EpGroupPrepare(api,mod,b,storage_owner,policy,out);
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
typedef struct EpOwnedCommit {EpRosterGroup* group;EpPropertyCommitGuard guard;void* lease;int committed,ended;} EpOwnedCommit;
static int EpValidateUnderOwner(void* context,const EpNativeRosterView* view)
{
    (void)view;EpOwnedCommit* c=(EpOwnedCommit*)context;
    c->committed=c->guard.validate(c->guard.context,c->lease)!=0;return 1;
}
static int EpCommitUnderOwner(void* context,const EpNativeRosterView* view)
{
    EpOwnedCommit* c=(EpOwnedCommit*)context;EpRosterGroup* g=c->group;
    if (view->game!=g->calls[0].game || view->roster!=g->calls[0].roster || view->storage!=g->calls[0].storage) return 0;
    /* Validation faults unwind to an inherited scope, so the outer lease is
     * still held when end receives committed=0. */
    if (ep_roster_owner_call(g->owner,g->storage_owner,1,EpValidateUnderOwner,c)!=EP_OWNER_OK) c->committed=0;
    if (c->committed) InterlockedExchange(&g->active,1);
    c->ended=1;c->guard.end(c->guard.context,c->lease,c->committed);return 1;
}
int ep_roster_group_commit(HfMod* owner,uint64_t id,const EpPropertyCommitGuard* guard)
{
    EpPropertyCommitGuard copy; void* lease=NULL; int entered,ok=0;
    if (!guard || !guard->begin || !guard->validate || !guard->end) return 0;
    copy=*guard;
    AcquireSRWLockExclusive(&epGroupLock); EpRosterGroup* g=EpGroupFind(owner,id);
    if (!g || g->state!=EP_GROUP_READY || (g->storage_owner && ep_roster_owner_in_scope())) { ReleaseSRWLockExclusive(&epGroupLock); return 0; }
    g->state=EP_GROUP_COMMITTING; ReleaseSRWLockExclusive(&epGroupLock);
    entered=copy.begin(copy.context,&lease);
    if (g->storage_owner) {
        EpOwnedCommit c={g,copy,lease,0,0};
        if (entered && lease) ok=ep_roster_owner_call(owner,g->storage_owner,1,EpCommitUnderOwner,&c)==EP_OWNER_OK && c.committed;
        if (entered && !c.ended) copy.end(copy.context,lease,0);
        AcquireSRWLockExclusive(&epGroupLock);
        /* If end unexpectedly faults after activation, never permit cancel or
         * retry as an inactive group. The quarantined owner blocks body calls. */
        g->state=InterlockedCompareExchange(&g->active,0,0) ? EP_GROUP_ACTIVE : EP_GROUP_READY;
        ReleaseSRWLockExclusive(&epGroupLock);return ok;
    }
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
static EpRosterGroup* TransitionFind(HfMod* mod,const EpRosterGroupTransition* token)
{
    EpRosterGroup* g=token ? EpGroupFind(mod,token->group) : NULL;
    return g && token->sequence && g->transition==token->sequence && g->storage_owner==token->storage_owner && g->state==EP_GROUP_COMMITTING ? g : NULL;
}
static int TransitionNextReady(EpRosterGroup* g)
{
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {
        EpSessionCodeInfo code;
        if (!ep_session_code_info(g->owner,g->code[i],&code) || !code.pinned || !g->calls[i].next_pointer ||
            !InterlockedCompareExchangePointer((void* volatile*)g->calls[i].next_pointer,NULL,NULL)) return 0;
    }
    return 1;
}
int ep_roster_group_transition_claim(HfMod* mod,uint64_t id,uint64_t owner,uint64_t game,EpRosterGroupTransition* out)
{
    if (!out) return 0;memset(out,0,sizeof(*out));if (!owner || ep_roster_owner_in_scope()) return 0;
    AcquireSRWLockExclusive(&epGroupLock);EpRosterGroup* g=EpGroupFind(mod,id);
    int ok=g && g->state==EP_GROUP_READY && g->storage_owner==owner && g->calls[0].game==game &&
        !g->active && !g->switching && !g->transition && epTransitionSequence!=UINT64_MAX && TransitionNextReady(g);
    if (ok) {
        g->transition=++epTransitionSequence;g->state=EP_GROUP_COMMITTING;
        out->group=id;out->sequence=g->transition;out->storage_owner=owner;
    }
    ReleaseSRWLockExclusive(&epGroupLock);return ok;
}
int ep_roster_group_transition_enter(HfMod* mod,const EpRosterGroupTransition* token)
{
    if (!token || ep_roster_owner_native_status(mod,token->storage_owner)!=EP_OWNER_OK) return 0;
    AcquireSRWLockExclusive(&epGroupLock);EpRosterGroup* g=TransitionFind(mod,token);
    int ok=g && !g->active && !g->switching && TransitionNextReady(g);
    if (ok) InterlockedExchange(&g->switching,1);
    ReleaseSRWLockExclusive(&epGroupLock);return ok;
}
int ep_roster_group_transition_activate(HfMod* mod,const EpRosterGroupTransition* token)
{
    if (!token || ep_roster_owner_native_status(mod,token->storage_owner)!=EP_OWNER_OK) return 0;
    AcquireSRWLockExclusive(&epGroupLock);EpRosterGroup* g=TransitionFind(mod,token);
    int ok=g && g->switching && !g->active;
    if (ok) InterlockedExchange(&g->active,1);
    ReleaseSRWLockExclusive(&epGroupLock);return ok;
}
int ep_roster_group_transition_finish(HfMod* mod,const EpRosterGroupTransition* token,uint32_t outcome)
{
    if (!token || outcome>EP_ROSTER_TRANSITION_UNSAFE) return 0;
    AcquireSRWLockExclusive(&epGroupLock);EpRosterGroup* g=TransitionFind(mod,token);int ok=g!=NULL;
    if (ok && outcome!=EP_ROSTER_TRANSITION_UNSAFE) {
        if (g->switching && ep_roster_owner_native_status(mod,g->storage_owner)!=EP_OWNER_OK) ok=0;
        if ((outcome==EP_ROSTER_TRANSITION_NEW)!=(g->active!=0)) ok=0;
    }
    if (ok) {
        g->state=g->active ? EP_GROUP_ACTIVE : outcome==EP_ROSTER_TRANSITION_UNSAFE ? EP_GROUP_FAILED : EP_GROUP_READY;
        InterlockedExchange(&g->switching,outcome==EP_ROSTER_TRANSITION_UNSAFE ? 1 : 0);g->transition=0;
    }
    ReleaseSRWLockExclusive(&epGroupLock);return ok;
}
