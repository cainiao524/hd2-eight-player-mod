/* Real two-layer joint coordinators, loadout storage and roster owner/SEH.
 * Core migration/windows and native UI bodies are test doubles; this focused
 * flow establishes ordering/quarantine, not real native/UI/multiplayer behavior.
 * Reuse fixture setup, but do not run its separate initialization test suite. */
#define main LoadoutInitializationStandaloneMain
#include "loadout_initialization_smoke.cpp"
#undef main
#include "ep_multiplayer_loadout_commit.h"
#include "ep_roster_group_transition.h"
extern "C" int EpOwnerInvoke(int (*)(void*),void*,int*);
struct JointFixture {
    bool lease,roster_barrier,roster_active,component_active,reject_validate;
    unsigned mode,ends,ended_outcome,roster_data,component_data,roster_restores;
    EpLoadoutSourceSnapshot current;
};
static JointFixture* joint;
static void ConstructOrder()
{NEED(joint->lease && joint->roster_barrier && joint->roster_active && joint->component_active && !joint->ends);}
int ep_component33_resource_entries_transaction_binding(HfMod* mod,uint64_t component,uint64_t* owner,uint64_t* game)
{
    NEED(mod==active->mod && component==22);if (joint->component_active) return 0;
    *owner=active->owner;*game=active->source.game;return 1;
}
int ep_component33_resource_entries_transaction_view(HfMod*,uint64_t,EpC33ResourceScopeView* out)
{*out={};out->game=active->source.game;return 1;}
int ep_roster_group_transition_claim(HfMod*,uint64_t group,uint64_t owner,uint64_t game,EpRosterGroupTransition* out)
{
    NEED(group==17 && owner==active->owner && game==active->source.game && !joint->roster_active);
    *out={group,1,owner};return 1;
}
int ep_roster_group_transition_enter(HfMod*,const EpRosterGroupTransition*)
{NEED(joint->lease);joint->roster_barrier=true;return 1;}
int ep_roster_group_transition_activate(HfMod*,const EpRosterGroupTransition*)
{NEED(joint->lease && joint->roster_barrier && joint->component_active);joint->roster_active=true;return 1;}
int ep_roster_group_transition_finish(HfMod*,const EpRosterGroupTransition*,uint32_t outcome)
{joint->roster_barrier=outcome==EP_ROSTER_TRANSITION_UNSAFE;return 1;}
bool ep_roster_migration_stage(EpRosterMigrationStage* stage)
{NEED(joint->lease);stage->dirty=true;joint->roster_data=8;return true;}
bool ep_roster_migration_check(EpRosterMigrationStage*) {return joint->roster_data==8;}
bool ep_roster_migration_intact(EpRosterMigrationStage*) {return joint->roster_data==8;}
int ep_roster_migration_restore(void*) {joint->roster_data=4;joint->roster_restores++;return 1;}
struct CoreCall {EpC33EntryCommitGuard guard;void* lease;uint32_t outcome;};
static int CoreValidate(void* p) {auto& c=*(CoreCall*)p;return c.guard.validate(c.guard.context,c.lease);}
static int CoreEnd(void* p) {auto& c=*(CoreCall*)p;c.guard.end(c.guard.context,c.lease,c.outcome);return 1;}
static int CoreUnderOwner(void* p,const EpNativeRosterView*)
{
    auto& c=*(CoreCall*)p;int fault=0;
    if (EpOwnerInvoke(CoreValidate,p,&fault) && !fault) {
        joint->component_active=true;joint->component_data=8;c.outcome=EP_C33_COMMIT_NEW;
    } else c.outcome=fault ? EP_C33_COMMIT_UNSAFE : EP_C33_COMMIT_OLD;
    int end_fault=0;const int ended=EpOwnerInvoke(CoreEnd,&c,&end_fault);
    return ended && !fault && !end_fault;
}
int ep_component33_resource_entries_commit_budgeted(HfMod* mod,uint64_t component,const EpC33EntryCommitGuard* guard,
    EpCommitReadBudget* budget,EpC33MigrationCommitResult* out)
{
    NEED(component==22 && budget && budget->used<=EP_COMMIT_READ_LIMIT);*out={};
    CoreCall call={*guard,nullptr,EP_C33_COMMIT_OLD};NEED(guard->begin(guard->context,&call.lease));
    const auto result=ep_roster_owner_call(mod,active->owner,1,CoreUnderOwner,&call);
    return result==EP_OWNER_OK && call.outcome==EP_C33_COMMIT_NEW;
}
static int Begin(void*,void** lease) {NEED(!joint->lease);joint->lease=true;*lease=joint;return 1;}
static int Validate(void*,void* lease)
{
    NEED(lease==joint && joint->lease && joint->roster_barrier && !joint->roster_active && !joint->component_active);
    NEED(!active->constructed && !active->replaced);
    // This fresh copy is supplied only under the common owner's frozen scope.
    // The wrapper must not have copied the deliberately stale argument earlier.
    joint->current=active->source;return !joint->reject_validate;
}
static void End(void*,void* lease,uint32_t outcome)
{
    NEED(lease==joint && joint->lease);joint->ends++;joint->ended_outcome=outcome;
    EpLoadoutStorageInfo info={};NEED(ep_loadout_storage_info(active->mod,active->storage,&info));
    if (outcome==EP_C33_COMMIT_OLD) {
        NEED(!active->constructed && !joint->roster_active && !joint->component_active && joint->roster_data==4);
        NEED(info.state==EP_LOADOUT_STORAGE_PREPARED);joint->lease=false;
    } else if (outcome==EP_C33_COMMIT_NEW) {
        NEED(joint->roster_active && joint->component_active && active->constructed==1 && active->replaced==1);
        NEED(info.state==EP_LOADOUT_STORAGE_UI_MIGRATED);
        if (joint->mode==2) RaiseException(0xe0421002,0,0,nullptr);
        joint->lease=false;
    } else {
        NEED(outcome==EP_C33_COMMIT_UNSAFE && info.state==EP_LOADOUT_STORAGE_QUARANTINED);
        NEED(joint->roster_active && joint->component_active && joint->roster_data==8);
        NEED(ep_roster_owner_native_status(active->mod,active->owner)==EP_OWNER_FAULTED);
    }
}
static int SdkReadForbidden(uintptr_t,void*,size_t) {NEED(false);return 1;}
static void RunJoint(unsigned mode)
{
    Fixture fixture={};Setup(fixture,mode);fixture.mode=mode==1 ? 1 : 0;
    JointFixture j={};joint=&j;j.mode=mode;j.roster_data=j.component_data=4;
    fixture.check_construct=ConstructOrder;
    HfApi api={};api.size=sizeof(api);api.version=13;api.read=SdkReadForbidden;
    EpC33EntryCommitGuard guard={nullptr,Begin,Validate,End};EpMultiplayerLoadoutCommitResult result={};
    if (!mode) {
        j.reject_validate=true;
        NEED(!ep_multiplayer_loadout_commit(&api,fixture.mod,17,22,fixture.storage,&j.current,&guard,&result));
        NEED(!result.loadout_attempted && result.multiplayer.outcome==EP_C33_COMMIT_OLD && !j.lease && j.ends==1);
        j.reject_validate=false;j.ends=0;j.roster_restores=0;
    }
    j.current={}; // validate, not the pre-begin argument, establishes freshness.
    const bool ok=ep_multiplayer_loadout_commit(&api,fixture.mod,17,22,fixture.storage,&j.current,&guard,&result)!=0;
    NEED(ok==(mode==0) && result.loadout_attempted && j.ends==1 && !j.roster_restores);
    NEED(j.roster_active && j.component_active && j.roster_data==8 && j.component_data==8);
    EpRosterOwnerInfo owner={};NEED(ep_roster_owner_info(fixture.mod,fixture.owner,&owner)==EP_OWNER_OK);
    if (!mode) {
        NEED(result.multiplayer.outcome==EP_C33_COMMIT_NEW && result.loadout_state==EP_LOADOUT_STORAGE_UI_MIGRATED);
        NEED(result.loadout_result==EP_LOADOUT_STORAGE_OK && !j.lease && !j.roster_barrier && !owner.fault);
    } else {
        NEED(result.multiplayer.outcome==EP_C33_COMMIT_UNSAFE && result.loadout_state==EP_LOADOUT_STORAGE_QUARANTINED);
        NEED(j.lease && j.roster_barrier && owner.fault);
        NEED(j.ended_outcome==(mode==1 ? EP_C33_COMMIT_UNSAFE : EP_C33_COMMIT_NEW));
        NEED(result.loadout_result==(mode==1 ? EP_LOADOUT_STORAGE_NATIVE_FAILED : EP_LOADOUT_STORAGE_OK));
        NEED(!ep_loadout_storage_quarantine_in_scope(fixture.mod,fixture.storage,fixture.owner)); // outside scope
    }
    NEED(ep_loadout_storage_cancel(fixture.mod,fixture.storage)==EP_LOADOUT_STORAGE_STATE);
}
int main()
{
    RunJoint(0);RunJoint(1);RunJoint(2);
    puts("{\"passed\":true,\"scope\":\"joint loadout ordering and late-failure quarantine\",\"core_migration_and_native_bodies\":\"test doubles\",\"game_access\":false,\"runtime_verified\":false}");
}
