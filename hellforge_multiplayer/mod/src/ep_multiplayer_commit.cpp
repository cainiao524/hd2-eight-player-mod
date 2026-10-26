#include "ep_multiplayer_commit.h"
#include "ep_roster_group_transition.h"
#include <windows.h>
extern "C" int EpOwnerInvoke(int (*)(void*),void*,int*);
static_assert(EP_ROSTER_TRANSITION_OLD==int(EP_C33_COMMIT_OLD) && EP_ROSTER_TRANSITION_NEW==int(EP_C33_COMMIT_NEW) &&
    EP_ROSTER_TRANSITION_UNSAFE==int(EP_C33_COMMIT_UNSAFE),"joint outcome protocol");
struct JointCommit {
    HfMod* mod;EpRosterGroupTransition roster;EpC33EntryCommitGuard guard;
    void* lease;uint32_t outcome;bool ended;
};
static int EnterJointOwner(void* p,const EpNativeRosterView*)
{auto* c=(JointCommit*)p;return ep_roster_group_transition_enter(c->mod,&c->roster);}
static void JointAbort()
{RaiseException(0xe04333d1,EXCEPTION_NONCONTINUABLE,0,nullptr);}
static int JointBegin(void* p,void** lease)
{
    auto* c=(JointCommit*)p;int entered=c->guard.begin(c->guard.context,lease);
    if (entered && *lease && ep_roster_owner_call(c->mod,c->roster.storage_owner,0,EnterJointOwner,c)!=EP_OWNER_OK) JointAbort();
    return entered;
}
static int JointValidate(void* p,void* lease)
{auto* c=(JointCommit*)p;return c->guard.validate(c->guard.context,lease);}
static int JointExternalEnd(void* p)
{auto* c=(JointCommit*)p;c->guard.end(c->guard.context,c->lease,c->outcome);return 1;}
static void JointEnd(void* p,void* lease,uint32_t outcome)
{
    auto* c=(JointCommit*)p;c->ended=true;c->lease=lease;c->outcome=outcome;
    if (outcome==EP_C33_COMMIT_NEW && !ep_roster_group_transition_activate(c->mod,&c->roster)) c->outcome=EP_C33_COMMIT_UNSAFE;
    // An invalid/throwing begin may not have entered the barrier. Seal that
    // path BEFORE notifying end(UNSAFE), even if the owner is already closed.
    bool finished=c->outcome==EP_C33_COMMIT_UNSAFE && ep_roster_group_transition_finish(c->mod,&c->roster,c->outcome);
    int fault=0;if (!EpOwnerInvoke(JointExternalEnd,c,&fault) || fault) c->outcome=EP_C33_COMMIT_UNSAFE;
    if (ep_roster_owner_native_status(c->mod,c->roster.storage_owner)!=EP_OWNER_OK) c->outcome=EP_C33_COMMIT_UNSAFE;
    if (!finished && !ep_roster_group_transition_finish(c->mod,&c->roster,c->outcome)) {
        c->outcome=EP_C33_COMMIT_UNSAFE;ep_roster_group_transition_finish(c->mod,&c->roster,c->outcome);
    }
    if (c->outcome==EP_C33_COMMIT_UNSAFE) JointAbort();
}
int ep_multiplayer_commit(HfMod* mod,uint64_t roster,uint64_t component,const EpC33EntryCommitGuard* guard,EpMultiplayerCommitResult* out)
{
    if (!out) return 0;*out={};
    if (!guard || !guard->begin || !guard->validate || !guard->end || ep_roster_owner_in_scope()) return 0;
    uint64_t owner=0,game=0;if (!ep_component33_resource_entries_transaction_binding(mod,component,&owner,&game)) return 0;
    JointCommit c={mod,{},*guard,nullptr,EP_C33_COMMIT_OLD,false};
    if (!ep_roster_group_transition_claim(mod,roster,owner,game,&c.roster)) return 0;
    out->roster_claimed=1;EpC33EntryCommitGuard wrapped={&c,JointBegin,JointValidate,JointEnd};
    int ok=ep_component33_resource_entries_commit_migrated(mod,component,&wrapped,&out->component_migration);
    if (!c.ended && !ep_roster_group_transition_finish(mod,&c.roster,EP_ROSTER_TRANSITION_OLD)) c.outcome=EP_C33_COMMIT_UNSAFE;
    out->outcome=c.outcome;return ok && c.outcome==EP_C33_COMMIT_NEW;
}
