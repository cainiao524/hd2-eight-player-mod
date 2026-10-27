/* Actual routes, call gates, allocator, both joint coordinators and owner/SEH.
 * SDK target patching, core migrations and UI storage/native initialization are
 * fixtures. One focused OLD retry -> NEW flow, plus partial SDK exposure failure.
 * No game paths, native game calls, process inspection or automatic loader. */
#include "ep_loadout_routes.h"
#include "ep_roster_group_transition.h"
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#define NEED(x) do {if (!(x)) {fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);exit(1);}} while (0)
extern "C" int EpOwnerInvoke(int (*)(void*),void*,int*);
static HfMod* mod=(HfMod*)(uintptr_t)0x9186;
struct Fixture {
    EpLoadoutStorageInfo storage;
    uint64_t owner,routes;
    unsigned hooks,ends,end_outcome,initializes,old_calls,new_calls,roster_data,component_data;
    bool lease,roster_barrier,roster_active,component_active,reject_after_validate,fail_publish;
    double (*frame)(double);
};
static Fixture* f;
static const char* Build() {return "25480438";}
static int ReadForbidden(void*,uintptr_t,void*,size_t) {NEED(false);return 0;}
static int SdkReadForbidden(uintptr_t,void*,size_t) {NEED(false);return 1;}
static void Failure(void*,uint32_t,EpRosterOwnerResult,EpRosterCallFrame*) {NEED(false);}
static double OldFrame(double value)
{NEED(ep_roster_owner_native_status(mod,f->owner)==EP_OWNER_OK);f->old_calls++;return value;}
static double NewFrame(double value)
{NEED(ep_roster_owner_native_status(mod,f->owner)==EP_OWNER_OK);f->new_calls++;return value+100;}
static void UnexpectedBody() {NEED(false);}
static EpLoadoutRoutesInfo Routes()
{EpLoadoutRoutesInfo out={};NEED(ep_loadout_routes_info(mod,f->routes,&out));return out;}
static int Hook(HfMod* at_mod,uintptr_t at,void* detour,void** next,int32_t priority)
{
    NEED(at_mod==mod && priority==7 && f->lease && f->roster_barrier);
    const auto r=Routes();NEED(r.state==EP_LOADOUT_ROUTES_COMMITTING && r.switching && !r.active && r.retained);
    NEED(ep_roster_owner_native_status(mod,f->owner)==EP_OWNER_OK);
    f->hooks++;
    if (at==f->storage.binding.setup.common.lifecycle.game+0x1468320) {
        *next=(void*)&OldFrame;f->frame=(double (*)(double))detour;
    } else *next=(void*)&UnexpectedBody;
    // Report failure AFTER exposing SDK's next slot: all images/contexts must
    // stay retained, and the partial set must never resume OLD or become NEW.
    return f->fail_publish && f->hooks==4 ? 1 : 0;
}
int ep_loadout_storage_info(HfMod* at_mod,uint64_t handle,EpLoadoutStorageInfo* out)
{NEED(at_mod==mod && handle==f->storage.handle);*out=f->storage;return 1;}
EpLoadoutStorageResult ep_loadout_storage_initialize_in_scope(HfMod* at_mod,uint64_t handle,uint64_t owner,const EpLoadoutSourceSnapshot* current)
{
    NEED(at_mod==mod && handle==f->storage.handle && owner==f->owner && current->game==f->storage.binding.setup.common.lifecycle.game);
    const auto r=Routes();NEED(r.switching && !r.active && r.published==EP_LOADOUT_CALL_COUNT);
    NEED(f->lease && f->roster_barrier && f->roster_active && f->component_active && !f->initializes);
    f->initializes++;f->storage.state=EP_LOADOUT_STORAGE_UI_MIGRATED;f->storage.initialization_owner=owner;return EP_LOADOUT_STORAGE_OK;
}
int ep_loadout_storage_quarantine_in_scope(HfMod* at_mod,uint64_t handle,uint64_t owner)
{
    NEED(at_mod==mod && handle==f->storage.handle && owner==f->owner);
    if (f->storage.initialization_owner!=owner) return 0;
    f->storage.state=EP_LOADOUT_STORAGE_QUARANTINED;f->storage.group={};return 1;
}
int ep_component33_resource_entries_transaction_binding(HfMod* at_mod,uint64_t component,uint64_t* owner,uint64_t* game)
{
    NEED(at_mod==mod && component==22);if (f->component_active) return 0;
    *owner=f->owner;*game=f->storage.binding.setup.common.lifecycle.game;return 1;
}
int ep_component33_resource_entries_transaction_view(HfMod*,uint64_t,EpC33ResourceScopeView* out)
{*out={};out->game=f->storage.binding.setup.common.lifecycle.game;return 1;}
int ep_roster_group_transition_claim(HfMod*,uint64_t group,uint64_t owner,uint64_t game,EpRosterGroupTransition* out)
{NEED(group==17 && owner==f->owner && game==f->storage.binding.setup.common.lifecycle.game);*out={group,1,owner};return 1;}
int ep_roster_group_transition_enter(HfMod*,const EpRosterGroupTransition*)
{NEED(f->lease && Routes().switching);f->roster_barrier=true;return 1;}
int ep_roster_group_transition_activate(HfMod*,const EpRosterGroupTransition*)
{NEED(f->lease && f->roster_barrier && f->component_active);f->roster_active=true;return 1;}
int ep_roster_group_transition_finish(HfMod*,const EpRosterGroupTransition*,uint32_t outcome)
{f->roster_barrier=outcome==EP_ROSTER_TRANSITION_UNSAFE;return 1;}
bool ep_roster_migration_stage(EpRosterMigrationStage* stage)
{NEED(f->lease && Routes().switching);stage->dirty=true;f->roster_data=8;return true;}
bool ep_roster_migration_check(EpRosterMigrationStage*) {return f->roster_data==8;}
bool ep_roster_migration_intact(EpRosterMigrationStage*) {return f->roster_data==8;}
int ep_roster_migration_restore(void*) {f->roster_data=4;return 1;}
struct CoreCall {EpC33EntryCommitGuard guard;void* lease;uint32_t outcome;};
static int CoreValidate(void* p) {auto& c=*(CoreCall*)p;return c.guard.validate(c.guard.context,c.lease);}
static int CoreEnd(void* p) {auto& c=*(CoreCall*)p;c.guard.end(c.guard.context,c.lease,c.outcome);return 1;}
static int CoreUnderOwner(void* p,const EpNativeRosterView*)
{
    auto& c=*(CoreCall*)p;int fault=0;
    if (EpOwnerInvoke(CoreValidate,p,&fault) && !fault && !f->reject_after_validate) {
        f->component_active=true;f->component_data=8;c.outcome=EP_C33_COMMIT_NEW;
    } else c.outcome=fault ? EP_C33_COMMIT_UNSAFE : EP_C33_COMMIT_OLD;
    int end_fault=0;const int ended=EpOwnerInvoke(CoreEnd,&c,&end_fault);return ended && !fault && !end_fault;
}
int ep_component33_resource_entries_commit_budgeted(HfMod* at_mod,uint64_t component,const EpC33EntryCommitGuard* guard,
    EpCommitReadBudget* budget,EpC33MigrationCommitResult* out)
{
    NEED(at_mod==mod && component==22 && budget->used<=EP_COMMIT_READ_LIMIT);*out={};
    CoreCall c={*guard,nullptr,EP_C33_COMMIT_OLD};NEED(guard->begin(guard->context,&c.lease));
    const auto result=ep_roster_owner_call(mod,f->owner,1,CoreUnderOwner,&c);
    return result==EP_OWNER_OK && c.outcome==EP_C33_COMMIT_NEW;
}
static int Begin(void*,void** lease) {NEED(!f->lease);f->lease=true;*lease=f;return 1;}
static int Validate(void* snapshot,void* lease)
{
    NEED(lease==f && f->lease && f->roster_barrier && Routes().switching);
    NEED(!f->initializes && !f->roster_active && !f->component_active);
    ((EpLoadoutSourceSnapshot*)snapshot)->game=f->storage.binding.setup.common.lifecycle.game;return 1;
}
static void End(void*,void* lease,uint32_t outcome)
{
    NEED(lease==f && f->lease);f->ends++;f->end_outcome=outcome;const auto r=Routes();NEED(r.switching);
    if (outcome==EP_C33_COMMIT_NEW) {
        NEED(r.active && r.published==EP_LOADOUT_CALL_COUNT && f->initializes==1 && f->roster_active && f->component_active);
        NEED(f->storage.state==EP_LOADOUT_STORAGE_UI_MIGRATED);f->lease=false;
    } else if (outcome==EP_C33_COMMIT_OLD) {
        NEED(!r.active && r.published==EP_LOADOUT_CALL_COUNT && !f->initializes && !f->roster_active && !f->component_active && f->roster_data==4);
        f->lease=false;
    } else {
        NEED(outcome==EP_C33_COMMIT_UNSAFE && !r.active && r.state==EP_LOADOUT_ROUTES_QUARANTINED);
        NEED(f->hooks==4 && r.publish_attempts==4 && r.published==3 && !f->initializes);
        NEED(ep_roster_owner_native_status(mod,f->owner)==EP_OWNER_FAULTED);
    }
}
static void Run(bool fail_publish)
{
    Fixture fixture={};f=&fixture;f->fail_publish=fail_publish;f->roster_data=f->component_data=4;
    const uint64_t shift=fail_publish ? 0x100000000 : 0;
    auto& s=f->storage;auto& b=s.binding.setup.common;
    s.handle=1+fail_publish;s.capacity=8;s.sources_imported=1;s.state=EP_LOADOUT_STORAGE_RETAINED;
    b.lifecycle.game=0x180000000+shift;b.roster=0x260000000+shift;b.roster_storage=0x260010000+shift;
#define EP_LOADOUT_CALL(member,rva,stack,chain) s.group.member=(uintptr_t)&UnexpectedBody;
#include "ep_loadout_call_entries.inc"
#undef EP_LOADOUT_CALL
    s.group.frame=(uintptr_t)&NewFrame;
    EpNativeRosterView view={};view.game=b.lifecycle.game;view.roster=b.roster;view.storage=b.roster_storage;view.epoch=1;view.build=25480438;
    EpRosterMemory memory={nullptr,ReadForbidden};NEED(ep_roster_owner_create(mod,&view,&memory,&f->owner)==EP_OWNER_OK);
    HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;api.read=SdkReadForbidden;
    EpRosterCallPolicy policy={Failure,nullptr};EpLoadoutRoutesInfo routes={};
    NEED(ep_loadout_routes_prepare(&api,mod,s.handle,f->owner,&policy,&routes));f->routes=routes.handle;
    NEED(routes.prepared==EP_LOADOUT_CALL_COUNT && routes.state==EP_LOADOUT_ROUTES_READY && !routes.retained && !f->hooks);
    EpLoadoutSourceSnapshot current={};EpC33EntryCommitGuard guard={&current,Begin,Validate,End};EpMultiplayerLoadoutCommitResult result={};
    if (!fail_publish) {
        f->reject_after_validate=true;
        NEED(!ep_loadout_routes_commit(&api,mod,f->routes,17,22,&current,&guard,7,&result));
        routes=Routes();NEED(routes.state==EP_LOADOUT_ROUTES_READY && !routes.switching && routes.retained && routes.published==EP_LOADOUT_CALL_COUNT);
        NEED(!f->lease && f->ends==1 && f->end_outcome==EP_C33_COMMIT_OLD && f->hooks==EP_LOADOUT_CALL_COUNT && !f->initializes);
        NEED(f->frame(11.25)==11.25 && f->old_calls==1 && !f->new_calls);
        f->reject_after_validate=false;f->ends=0;
    }
    const int ok=ep_loadout_routes_commit(&api,mod,f->routes,17,22,&current,&guard,7,&result);
    routes=Routes();NEED(ok==!fail_publish && f->ends==1 && result.multiplayer.total_read_bytes==0);
    NEED(routes.retained && !ep_loadout_routes_cancel(mod,f->routes));
    EpRosterOwnerInfo owner={};NEED(ep_roster_owner_info(mod,f->owner,&owner)==EP_OWNER_OK);
    if (fail_publish) {
        NEED(result.multiplayer.outcome==EP_C33_COMMIT_UNSAFE && routes.state==EP_LOADOUT_ROUTES_QUARANTINED && routes.switching);
        NEED(f->lease && owner.fault && !f->initializes && !f->roster_active && !f->component_active && f->roster_data==4);
    } else {
        NEED(result.multiplayer.outcome==EP_C33_COMMIT_NEW && routes.state==EP_LOADOUT_ROUTES_ACTIVE && routes.active && !routes.switching);
        NEED(!f->lease && !owner.fault && f->hooks==EP_LOADOUT_CALL_COUNT && f->roster_data==8 && f->component_data==8);
        NEED(f->frame(11.25)==111.25 && f->old_calls==1 && f->new_calls==1);
    }
}
int main()
{
    Run(false);Run(true);
    puts("{\"passed\":true,\"scope\":\"grouped UI publication, OLD retry, joint NEW activation and partial SDK exposure quarantine\",\"migrations_and_native_bodies\":\"test doubles\",\"game_access\":false,\"runtime_verified\":false}");
    return 0;
}
