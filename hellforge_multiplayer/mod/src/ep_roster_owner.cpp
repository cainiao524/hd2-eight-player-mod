/* C-compatible so tests can include the real patched loader in the same TU. */
#include "ep_roster_owner.h"
#include <windows.h>
#include <string.h>
typedef struct EpRosterOwner {
    HfMod* mod;
    uint64_t handle, revision;
    SRWLOCK lock;
    volatile LONG closing;
    uint32_t refs, fault, generations[8];
    EpNativeRosterView view;
    EpRosterMemory memory;
} EpRosterOwner;
static EpRosterOwner epOwners[EP_ROSTER_OWNER_SLOTS];
static SRWLOCK epOwnersLock = SRWLOCK_INIT;
static CONDITION_VARIABLE epOwnersDrained = CONDITION_VARIABLE_INIT;
static uint64_t epOwnerSequence;
#ifdef __cplusplus
static thread_local EpRosterOwner* epOwnerScope;
extern "C" int EpOwnerInvoke(int (*callback)(void*),void* context,int* fault);
#else
static _Thread_local EpRosterOwner* epOwnerScope;
int EpOwnerInvoke(int (*callback)(void*),void* context,int* fault);
#endif
/* The pinned HellForge compiler does not enable Microsoft __try syntax. This
 * small, statically registered SEH frame uses its normal GNU assembler support.
 * Windows unwinds the callback before reaching the landing pad. Saved fault
 * pointer is outside the callee's 32-byte shadow area; stack stays aligned.
 * The NOP keeps the return PC inside the scope's exclusive end boundary.
 * No global VEH, longjmp, extra compiler flags or game exception hooks. */
__asm__(
    ".text\n.p2align 4\n.globl EpOwnerInvoke\n.seh_proc EpOwnerInvoke\n"
    "EpOwnerInvoke:\nsubq $56,%rsp\n.seh_stackalloc 56\n.seh_endprologue\n"
    "movq %r8,32(%rsp)\nmovq %rcx,%rax\nmovq %rdx,%rcx\n"
    ".Lep_owner_call:\ncall *%rax\nnop\n.Lep_owner_call_end:\n"
    "addq $56,%rsp\nret\n"
    ".Lep_owner_fault:\nmovq 32(%rsp),%rcx\nmovl $1,(%rcx)\nxorl %eax,%eax\naddq $56,%rsp\nret\n"
    ".seh_handler __C_specific_handler,@except\n.seh_handlerdata\n.long 1\n"
    ".rva .Lep_owner_call,.Lep_owner_call_end\n.long 1\n.rva .Lep_owner_fault\n.text\n.seh_endproc\n");
static int OwnerRange(uintptr_t a, size_t n, size_t alignment)
{ return a >= 0x10000 && a <= (UINT64_C(1)<<47)-n && !(a%alignment); }
static int OwnerOverlap(uintptr_t a, size_t n, uintptr_t b, size_t m)
{ return a < b+m && b < a+n; }
static int OwnerTickets(const EpNativeRosterView* v)
{
    if (v->ticket_count>8) return 0;
    for (unsigned i=0;i<v->ticket_count;i++) {
        const EpNativeTicket* t=&v->tickets[i];
        if (!t->peer || !t->player || !t->generation || t->epoch!=v->epoch || t->network_index>=8 || t->reserved) return 0;
        for (unsigned j=0;j<i;j++) if (t->peer==v->tickets[j].peer || t->player==v->tickets[j].player ||
            t->network_index==v->tickets[j].network_index) return 0;
    }
    return 1;
}
static EpRosterOwner* OwnerFind(HfMod* mod, uint64_t id)
{
    if (id) for (unsigned i=0;i<EP_ROSTER_OWNER_SLOTS;i++)
        if (epOwners[i].handle==id && (!mod || epOwners[i].mod==mod)) return &epOwners[i];
    return NULL;
}
static EpRosterOwner* OwnerAcquire(HfMod* mod, uint64_t id)
{
    if (epOwnerScope) return NULL;
    AcquireSRWLockExclusive(&epOwnersLock);
    EpRosterOwner* o=OwnerFind(mod,id);
    if (o && !o->closing && o->refs!=UINT32_MAX) o->refs++; else o=NULL;
    ReleaseSRWLockExclusive(&epOwnersLock);
    if (o) { AcquireSRWLockExclusive(&o->lock); epOwnerScope=o; }
    return o;
}
static void OwnerRelease(EpRosterOwner* o)
{
    epOwnerScope=NULL;
    ReleaseSRWLockExclusive(&o->lock);
    AcquireSRWLockExclusive(&epOwnersLock);
    o->refs--; if (!o->refs) WakeAllConditionVariable(&epOwnersDrained);
    ReleaseSRWLockExclusive(&epOwnersLock);
}
EpRosterOwnerResult ep_roster_owner_create(HfMod* mod, const EpNativeRosterView* initial,
    const EpRosterMemory* memory, uint64_t* handle)
{
    if (handle) *handle=0;
    if (!mod || !initial || !memory || !memory->read || !handle) return EP_OWNER_ARGUMENT;
    if (epOwnerScope) return EP_OWNER_REENTRANT;
    EpNativeRosterView v=*initial;
    if (!v.epoch || v.build!=25480438 || v.lease || !OwnerRange(v.game,0x347CEF8,4096) ||
        !OwnerRange(v.roster,0x428,8) || !OwnerRange(v.storage,0x680,16) ||
        OwnerOverlap(v.roster,0x428,v.storage,0x680)) return EP_OWNER_ARGUMENT;
    if (!OwnerTickets(&v)) return EP_OWNER_IDENTITY;
    memset(v.tickets+v.ticket_count,0,(8-v.ticket_count)*sizeof(v.tickets[0]));
    EpRosterOwnerResult result=EP_OWNER_EXHAUSTED;
    AcquireSRWLockExclusive(&epOwnersLock);
    for (unsigned i=0;i<EP_ROSTER_OWNER_SLOTS;i++) if (epOwners[i].handle) {
        const EpNativeRosterView* other=&epOwners[i].view;
        if (v.game==other->game || OwnerOverlap(v.roster,0x428,other->roster,0x428) ||
            OwnerOverlap(v.roster,0x428,other->storage,0x680) || OwnerOverlap(v.storage,0x680,other->roster,0x428) ||
            OwnerOverlap(v.storage,0x680,other->storage,0x680)) {
            ReleaseSRWLockExclusive(&epOwnersLock); return EP_OWNER_CONFLICT;
        }
    }
    if (epOwnerSequence!=UINT64_MAX) for (unsigned i=0;i<EP_ROSTER_OWNER_SLOTS;i++) if (!epOwners[i].handle) {
        EpRosterOwner* o=&epOwners[i];
        o->mod=mod; o->handle=++epOwnerSequence; o->revision=1; o->view=v; o->memory=*memory;
        for (unsigned j=0;j<v.ticket_count;j++) o->generations[v.tickets[j].network_index]=v.tickets[j].generation;
        *handle=o->handle; result=EP_OWNER_OK; break;
    }
    ReleaseSRWLockExclusive(&epOwnersLock); return result;
}
EpRosterOwnerResult ep_roster_owner_info(HfMod* mod, uint64_t id, EpRosterOwnerInfo* out)
{
    if (out) memset(out,0,sizeof(*out));
    if (!out || !mod || !id) return EP_OWNER_ARGUMENT;
    if (epOwnerScope) return EP_OWNER_REENTRANT;
    EpRosterOwner* o=OwnerAcquire(mod,id); if (!o) return EP_OWNER_UNAVAILABLE;
    out->handle=o->handle; out->epoch=o->view.epoch; out->revision=o->revision;
    out->fault=o->fault; out->ticket_count=o->view.ticket_count;
    OwnerRelease(o); return EP_OWNER_OK;
}
static int OwnerTransition(EpRosterOwner* o, const EpNativeRosterView* v)
{
    if (!OwnerTickets(v)) return 0;
    for (unsigned i=0;i<v->ticket_count;i++) {
        const EpNativeTicket* t=&v->tickets[i]; const EpNativeTicket* old=NULL;
        for (unsigned j=0;j<o->view.ticket_count;j++)
            if (o->view.tickets[j].network_index==t->network_index) old=&o->view.tickets[j];
        if (old && old->peer==t->peer && old->player==t->player) {
            if (t->generation!=old->generation) return 0;
        } else if (t->generation<=o->generations[t->network_index]) return 0;
    }
    return 1;
}
typedef struct EpOwnerMutationCall {EpRosterMutation callback;void* context;const EpNativeRosterView* view;} EpOwnerMutationCall;
static int OwnerMutationCall(void* context)
{ EpOwnerMutationCall* call=(EpOwnerMutationCall*)context;return call->callback(call->context,call->view); }
EpRosterOwnerResult ep_roster_owner_mutate(HfMod* mod, uint64_t id, uint64_t revision,
    const EpRosterIdentitySet* next, EpRosterMutation mutate, void* context)
{
    if (!mod || !id || !revision || !mutate) return EP_OWNER_ARGUMENT;
    if (epOwnerScope) return EP_OWNER_REENTRANT;
    EpRosterIdentitySet identity; if (next) identity=*next;
    EpRosterOwner* o=OwnerAcquire(mod,id); if (!o) return EP_OWNER_UNAVAILABLE;
    EpRosterOwnerResult result=EP_OWNER_OK;
    {
        EpNativeRosterView candidate=o->view;
        if (InterlockedCompareExchange(&o->closing,0,0)) result=EP_OWNER_UNAVAILABLE;
        else if (o->fault) result=EP_OWNER_FAULTED;
        else if (revision!=o->revision) result=EP_OWNER_STALE;
        else if (o->revision==UINT64_MAX) result=EP_OWNER_EXHAUSTED;
        else {
            if (next) {
                candidate.ticket_count=identity.count;
                memcpy(candidate.tickets,identity.tickets,sizeof(candidate.tickets));
            }
            if (!OwnerTransition(o,&candidate)) result=EP_OWNER_IDENTITY;
            else {
                int fault=0;
                /* Catch SEH here: no exception may leak through a loader's
                 * provider callback and strand its own reader lock. */
                EpOwnerMutationCall call={mutate,context,&o->view};
                int completed=EpOwnerInvoke(OwnerMutationCall,&call,&fault)==1;
                if (fault) result=EP_OWNER_CALLBACK_FAULT;
                if (!completed) {
                    if (result==EP_OWNER_OK) result=EP_OWNER_CALLBACK_FAILED;
                    o->fault=(uint32_t)result;
                } else {
                    memset(candidate.tickets+candidate.ticket_count,0,(8-candidate.ticket_count)*sizeof(candidate.tickets[0]));
                    /* Binding/epoch fields are immutable: create's conflict
                     * scan reads them under the registry lock, not this lock. */
                    o->view.ticket_count=candidate.ticket_count;
                    memcpy(o->view.tickets,candidate.tickets,sizeof(candidate.tickets));o->revision++;
                    for (unsigned i=0;i<candidate.ticket_count;i++)
                        o->generations[candidate.tickets[i].network_index]=candidate.tickets[i].generation;
                }
            }
        }
    }
    OwnerRelease(o);
    return result;
}
static int OwnerBegin(void* context, uintptr_t game, EpNativeRosterView* out)
{
    EpRosterOwner* o=(EpRosterOwner*)context;
    if (epOwnerScope!=o || o->fault || o->view.game!=game) return 0;
    *out=o->view; out->lease=o; return 1;
}
static int OwnerRead(void* context, void* lease, uintptr_t a, void* out, size_t n)
{
    EpRosterOwner* o=(EpRosterOwner*)context;
    return epOwnerScope==o && lease==o && o->memory.read(o->memory.context,a,out,n)==1;
}
static void OwnerEnd(void* context, void* lease) { (void)context; (void)lease; }
typedef struct EpOwnerSnapshotCall {EpRosterOwner* owner;uintptr_t game;EpHfRosterSnapshot* out;EpNativeRosterStatus result;} EpOwnerSnapshotCall;
static int OwnerSnapshotCall(void* context)
{
    EpOwnerSnapshotCall* call=(EpOwnerSnapshotCall*)context;
    EpNativeRosterSource source={call->owner,OwnerBegin,OwnerRead,OwnerEnd};
    call->result=ep_native_roster_snapshot(&source,call->game,call->out);return 1;
}
static EpNativeRosterStatus OwnerSnapshot(HfMod* mod, uint64_t id, uintptr_t game, EpHfRosterSnapshot* out)
{
    if (out) memset(out,0,sizeof(*out));
    if (!out || !id) return EP_NATIVE_ARGUMENT;
    EpRosterOwner* o=OwnerAcquire(mod,id); if (!o) return EP_NATIVE_UNAVAILABLE;
    EpNativeRosterStatus result=EP_NATIVE_UNAVAILABLE;
    {
        if (!o->fault && !InterlockedCompareExchange(&o->closing,0,0)) {
            EpOwnerSnapshotCall call={o,game,out,EP_NATIVE_UNAVAILABLE};int fault=0;
            EpOwnerInvoke(OwnerSnapshotCall,&call,&fault);result=call.result;
            if (fault) {
                o->fault=EP_OWNER_CALLBACK_FAULT; result=EP_NATIVE_READ_FAILED; memset(out,0,sizeof(*out));
            }
        }
    }
    OwnerRelease(o);
    return result;
}
EpNativeRosterStatus ep_roster_owner_snapshot(HfMod* mod, uint64_t id, uintptr_t game, EpHfRosterSnapshot* out)
{
    if (!mod) { if (out) memset(out,0,sizeof(*out)); return EP_NATIVE_ARGUMENT; }
    return OwnerSnapshot(mod,id,game,out);
}
static int OwnerProviderRead(void* context, uintptr_t game, EpHfRosterSnapshot* out)
{ return OwnerSnapshot(NULL,(uint64_t)(uintptr_t)context,game,out)==EP_NATIVE_OK; }
EpRosterOwnerResult ep_roster_owner_provider(HfMod* mod, uint64_t id, EpHfRosterProvider* out)
{
    if (out) memset(out,0,sizeof(*out));
    if (!out || !mod || !id) return EP_OWNER_ARGUMENT;
    if (epOwnerScope) return EP_OWNER_REENTRANT;
    EpRosterOwner* o=OwnerAcquire(mod,id); if (!o) return EP_OWNER_UNAVAILABLE;
    EpRosterOwnerResult result=EP_OWNER_OK;
    if (o->fault) result=EP_OWNER_FAULTED;
    else {
        out->size=sizeof(*out); out->version=EP_HF_ROSTER_VERSION; out->capacity=8;
        out->context=(void*)(uintptr_t)id; out->read=OwnerProviderRead;
    }
    OwnerRelease(o); return result;
}
EpRosterOwnerResult ep_roster_owner_close(HfMod* mod, uint64_t id)
{
    if (!mod || !id) return EP_OWNER_ARGUMENT;
    if (epOwnerScope) return EP_OWNER_REENTRANT;
    AcquireSRWLockExclusive(&epOwnersLock); EpRosterOwner* o=OwnerFind(mod,id);
    if (!o || o->closing) { ReleaseSRWLockExclusive(&epOwnersLock); return EP_OWNER_UNAVAILABLE; }
    InterlockedExchange(&o->closing,1);
    while (o->refs) SleepConditionVariableSRW(&epOwnersDrained,&epOwnersLock,INFINITE,0);
    memset(o,0,sizeof(*o));
    ReleaseSRWLockExclusive(&epOwnersLock); return EP_OWNER_OK;
}
