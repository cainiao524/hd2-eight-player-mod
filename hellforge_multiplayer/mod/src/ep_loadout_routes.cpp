#include "ep_loadout_routes.h"
#include <windows.h>
extern "C" int EpOwnerInvoke(int (*)(void*),void*,int*);
namespace {
struct Routes {
    HfMod* mod;uint64_t game;
    EpLoadoutRoutesInfo info;
    EpLoadoutCallControl control;
    EpLoadoutCallContext calls[EP_LOADOUT_CALL_COUNT];
    uint64_t code[EP_LOADOUT_CALL_COUNT];
};
Routes groups[EP_LOADOUT_STORAGE_SLOTS];
SRWLOCK lock=SRWLOCK_INIT;
uint64_t sequence;
Routes* find(HfMod* mod,uint64_t id)
{if (mod && id) for (auto& g:groups) if (g.mod==mod && g.info.handle==id) return &g;return nullptr;}
void info(Routes& g,EpLoadoutRoutesInfo* out)
{
    *out=g.info;out->active=InterlockedCompareExchange((volatile LONG*)&g.control.active,0,0);
    out->switching=InterlockedCompareExchange((volatile LONG*)&g.control.switching,0,0);
}
// Caller has claimed PREPARING/CLEANING; no gate has been exposed or retained.
// Do not hold our lock across allocator/SDK/owner/storage callbacks.
int discard(Routes& g,EpLoadoutRoutesInfo* out=nullptr)
{
    bool ok=true;
    for (unsigned i=EP_LOADOUT_CALL_COUNT;i--;) if (g.code[i]) {
        if (ep_session_code_discard(g.mod,g.code[i])) g.code[i]=0;else ok=false;
    }
    AcquireSRWLockExclusive(&lock);
    if (ok) g={};else g.info.state=EP_LOADOUT_ROUTES_CLEANUP;
    if (out) info(g,out);
    ReleaseSRWLockExclusive(&lock);return ok;
}
struct Commit {
    Routes* group;EpC33EntryCommitGuard guard;int32_t priority;
    void* lease;uint32_t outcome;bool entered,ended,unsafe,activated;
};
int fail_owner(void*,const EpNativeRosterView*) {return 0;}
void quarantine(Commit& c)
{
    auto& g=*c.group;c.unsafe=true;
    InterlockedExchange((volatile LONG*)&g.control.switching,1);
    AcquireSRWLockExclusive(&lock);g.info.state=EP_LOADOUT_ROUTES_QUARANTINED;ReleaseSRWLockExclusive(&lock);
    // Prior to initialization storage has no recorded initializing owner, so
    // its quarantine API may refuse. The common owner and all gates still seal.
    const auto state=ep_roster_owner_native_status(g.mod,g.info.roster_owner);
    if (state==EP_OWNER_OK || state==EP_OWNER_FAULTED) {
        ep_loadout_storage_quarantine_in_scope(g.mod,g.info.loadout,g.info.roster_owner);
        if (ep_roster_owner_native_status(g.mod,g.info.roster_owner)==EP_OWNER_OK)
            ep_roster_owner_call(g.mod,g.info.roster_owner,0,fail_owner,nullptr);
    }
}
void abort_commit() {RaiseException(0xe04c4403,EXCEPTION_NONCONTINUABLE,0,nullptr);}
int enter(void* opaque,const EpNativeRosterView* view)
{
    auto& c=*(Commit*)opaque;auto& g=*c.group;
    if (view->game!=g.game) return 0;
    InterlockedExchange((volatile LONG*)&g.control.switching,1);c.entered=true;return 1;
}
int begin(void* opaque,void** lease)
{
    auto& c=*(Commit*)opaque;auto& g=*c.group;
    const int ok=c.guard.begin(c.guard.context,lease);
    if (ok && *lease && ep_roster_owner_call(g.mod,g.info.roster_owner,0,enter,&c)!=EP_OWNER_OK) {
        quarantine(c);abort_commit();
    }
    return ok;
}
int validate(void* opaque,void* lease)
{
    auto& c=*(Commit*)opaque;auto& g=*c.group;
    if (!c.entered || ep_roster_owner_native_status(g.mod,g.info.roster_owner)!=EP_OWNER_OK) {
        quarantine(c);abort_commit();return 0;
    }
    if (!c.guard.validate(c.guard.context,lease)) return 0;
    if (ep_roster_owner_native_status(g.mod,g.info.roster_owner)!=EP_OWNER_OK) {
        quarantine(c);abort_commit();return 0;
    }
    if (g.info.published==EP_LOADOUT_CALL_COUNT) return 1; // safe OLD retry
    if (!g.info.retained) {
        if (!ep_session_code_retain_set(g.mod,g.code,EP_LOADOUT_CALL_COUNT)) return 0;
        AcquireSRWLockExclusive(&lock);g.info.retained=1;ReleaseSRWLockExclusive(&lock);
    }
    for (unsigned i=0;i<EP_LOADOUT_CALL_COUNT;i++) {
        // Record an attempt BEFORE SDK code can expose a hook or raise SEH.
        AcquireSRWLockExclusive(&lock);g.info.publish_attempts++;ReleaseSRWLockExclusive(&lock);
        if (!ep_session_code_publish(g.mod,g.code[i],g.calls[i].target,c.priority) ||
            !InterlockedCompareExchangePointer((void* volatile*)g.calls[i].next_pointer,nullptr,nullptr) ||
            ep_roster_owner_native_status(g.mod,g.info.roster_owner)!=EP_OWNER_OK) {
            quarantine(c);abort_commit();return 0;
        }
        AcquireSRWLockExclusive(&lock);g.info.published++;ReleaseSRWLockExclusive(&lock);
    }
    return 1;
}
int external_end(void* opaque)
{auto& c=*(Commit*)opaque;c.guard.end(c.guard.context,c.lease,c.outcome);return 1;}
void end(void* opaque,void* lease,uint32_t outcome)
{
    auto& c=*(Commit*)opaque;auto& g=*c.group;c.ended=true;c.lease=lease;c.outcome=outcome;
    EpLoadoutStorageInfo storage={};
    const bool healthy=ep_roster_owner_native_status(g.mod,g.info.roster_owner)==EP_OWNER_OK;
    if (c.unsafe || !healthy || outcome==EP_C33_COMMIT_UNSAFE || !c.entered ||
        !ep_loadout_storage_info(g.mod,g.info.loadout,&storage)) c.outcome=EP_C33_COMMIT_UNSAFE;
    else if (outcome==EP_C33_COMMIT_NEW) {
        if (storage.state!=EP_LOADOUT_STORAGE_UI_MIGRATED || storage.initialization_owner!=g.info.roster_owner ||
            !g.info.retained || g.info.published!=EP_LOADOUT_CALL_COUNT) c.outcome=EP_C33_COMMIT_UNSAFE;
        else {InterlockedExchange((volatile LONG*)&g.control.active,1);c.activated=true;}
    } else if (outcome!=EP_C33_COMMIT_OLD || storage.state!=EP_LOADOUT_STORAGE_RETAINED ||
               g.control.active || (g.info.publish_attempts && g.info.published!=EP_LOADOUT_CALL_COUNT))
        c.outcome=EP_C33_COMMIT_UNSAFE;
    if (c.outcome==EP_C33_COMMIT_UNSAFE) quarantine(c);
    int fault=0;
    if (!EpOwnerInvoke(external_end,&c,&fault) || fault ||
        ep_roster_owner_native_status(g.mod,g.info.roster_owner)!=EP_OWNER_OK) quarantine(c);
    if (c.unsafe) {abort_commit();return;}
    // The outer core coordinator still holds the owner through its own barriers.
    // A thread resumed by end must acquire that owner before reaching any body.
    InterlockedExchange((volatile LONG*)&g.control.switching,0);
}
}
int ep_loadout_routes_info(HfMod* mod,uint64_t id,EpLoadoutRoutesInfo* out)
{
    if (!out) return 0;*out={};AcquireSRWLockShared(&lock);auto* g=find(mod,id);
    if (g) info(*g,out);ReleaseSRWLockShared(&lock);return g!=nullptr;
}
int ep_loadout_routes_prepare(const HfApi* api,HfMod* mod,uint64_t loadout,uint64_t owner,
    const EpRosterCallPolicy* policy,EpLoadoutRoutesInfo* out)
{
    if (!out) return 0;*out={};EpLoadoutStorageInfo storage={};
    if (!api || !mod || !policy || !policy->failure || ep_roster_owner_in_scope() ||
        !ep_loadout_storage_info(mod,loadout,&storage) || storage.state!=EP_LOADOUT_STORAGE_RETAINED ||
        !storage.sources_imported || storage.capacity!=EP_NATIVE_ROSTER_CAPACITY) return 0;
    const auto& b=storage.binding.setup.common;
    if (ep_roster_owner_check_binding(mod,owner,b.lifecycle.game,b.roster,b.roster_storage)!=EP_OWNER_OK) return 0;
    const auto saved=*policy;Routes* g=nullptr;AcquireSRWLockExclusive(&lock);
    for (const auto& other:groups) if (other.info.handle && other.game==b.lifecycle.game) {
        ReleaseSRWLockExclusive(&lock);return 0;
    }
    if (sequence!=UINT64_MAX) for (auto& candidate:groups) if (!candidate.info.handle) {
        g=&candidate;g->mod=mod;g->game=b.lifecycle.game;g->info.handle=++sequence;
        g->info.loadout=loadout;g->info.roster_owner=owner;g->info.state=EP_LOADOUT_ROUTES_PREPARING;break;
    }
    ReleaseSRWLockExclusive(&lock);if (!g) return 0;
    bool ok=true;
    for (unsigned i=0;i<EP_LOADOUT_CALL_COUNT;i++) {
        EpLoadoutCallLayout layout={};EpSessionCodeInfo code={};
        ok=ep_loadout_call_layout(i,&layout) &&
            ep_loadout_call_prepare(api,mod,loadout,owner,layout.rva,&g->control,&saved,0,&g->calls[i],&code);
        g->code[i]=code.handle;if (!ok) break;
        AcquireSRWLockExclusive(&lock);g->info.prepared++;ReleaseSRWLockExclusive(&lock);
    }
    if (!ok) {discard(*g,out);return 0;}
    AcquireSRWLockExclusive(&lock);if (ok) g->info.state=EP_LOADOUT_ROUTES_READY;
    if (g->info.handle) info(*g,out);ReleaseSRWLockExclusive(&lock);return ok;
}
int ep_loadout_routes_cancel(HfMod* mod,uint64_t id)
{
    if (ep_roster_owner_in_scope()) return 0;
    AcquireSRWLockExclusive(&lock);auto* g=find(mod,id);
    if (!g || g->info.retained || g->info.publish_attempts ||
        (g->info.state!=EP_LOADOUT_ROUTES_READY && g->info.state!=EP_LOADOUT_ROUTES_CLEANUP)) {
        ReleaseSRWLockExclusive(&lock);return 0;
    }
    g->info.state=EP_LOADOUT_ROUTES_CLEANING;ReleaseSRWLockExclusive(&lock);return discard(*g);
}
int ep_loadout_routes_commit(const HfApi* api,HfMod* mod,uint64_t id,uint64_t roster,uint64_t component,
    const EpLoadoutSourceSnapshot* current,const EpC33EntryCommitGuard* guard,int32_t priority,
    EpMultiplayerLoadoutCommitResult* out)
{
    if (!out) return 0;*out={};
    if (!api || !current || !guard || !guard->begin || !guard->validate || !guard->end || ep_roster_owner_in_scope()) return 0;
    uint64_t owner=0,game=0;
    if (!ep_component33_resource_entries_transaction_binding(mod,component,&owner,&game)) return 0;
    AcquireSRWLockExclusive(&lock);auto* g=find(mod,id);
    if (!g || g->info.state!=EP_LOADOUT_ROUTES_READY || g->info.roster_owner!=owner || g->game!=game) {
        ReleaseSRWLockExclusive(&lock);return 0;
    }
    g->info.state=EP_LOADOUT_ROUTES_COMMITTING;ReleaseSRWLockExclusive(&lock);
    Commit c={g,*guard,priority,nullptr,EP_C33_COMMIT_OLD,false,false,false,false};
    EpC33EntryCommitGuard wrapped={&c,begin,validate,end};
    const int ok=ep_multiplayer_loadout_commit(api,mod,roster,component,g->info.loadout,current,&wrapped,out);
    if (c.unsafe || out->multiplayer.outcome==EP_C33_COMMIT_UNSAFE || (c.entered && !c.ended) ||
        (c.activated && !ok)) quarantine(c);
    const bool committed=ok && c.activated && c.ended && !c.unsafe;
    AcquireSRWLockExclusive(&lock);
    g->info.state=c.unsafe ? EP_LOADOUT_ROUTES_QUARANTINED : committed ? EP_LOADOUT_ROUTES_ACTIVE : EP_LOADOUT_ROUTES_READY;
    ReleaseSRWLockExclusive(&lock);return committed;
}
