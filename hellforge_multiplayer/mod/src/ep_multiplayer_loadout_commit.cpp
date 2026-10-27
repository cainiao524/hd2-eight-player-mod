#include "ep_multiplayer_loadout_commit.h"
#include "ep_roster_group.h"
#include <windows.h>
extern "C" int EpOwnerInvoke(int (*)(void*),void*,int*);
namespace {
struct LoadoutCommit {
    HfMod* mod;uint64_t loadout,owner;
    const EpLoadoutSourceSnapshot* current;
    EpC33EntryCommitGuard guard;EpMultiplayerLoadoutCommitResult* result;
    void* lease;uint32_t outcome;bool unsafe;
    EpPlayerJoinPeers peers;
};
int begin(void* context,void** lease)
{auto& c=*(LoadoutCommit*)context;return c.guard.begin(c.guard.context,lease);}
int validate(void* context,void* lease)
{auto& c=*(LoadoutCommit*)context;return c.guard.validate(c.guard.context,lease);}
int initialize(void* context)
{
    auto& c=*(LoadoutCommit*)context;c.result->loadout_attempted=1;
    c.result->loadout_result=ep_loadout_storage_initialize_peers_in_scope(c.mod,c.loadout,c.owner,c.current,&c.peers);
    return c.result->loadout_result==EP_LOADOUT_STORAGE_OK;
}
int external_end(void* context)
{auto& c=*(LoadoutCommit*)context;c.guard.end(c.guard.context,c.lease,c.outcome);return 1;}
void end(void* context,void* lease,uint32_t outcome)
{
    auto& c=*(LoadoutCommit*)context;c.lease=lease;c.outcome=outcome;
    if (outcome==EP_C33_COMMIT_NEW) {
        int fault=0;
        if (!EpOwnerInvoke(initialize,&c,&fault) || fault) {
            c.unsafe=true;c.outcome=EP_C33_COMMIT_UNSAFE;
            ep_loadout_storage_quarantine_in_scope(c.mod,c.loadout,c.owner);
        }
    }
    int fault=0;
    if (!EpOwnerInvoke(external_end,&c,&fault) || fault ||
        (c.result->loadout_attempted && ep_roster_owner_native_status(c.mod,c.owner)!=EP_OWNER_OK)) c.unsafe=true;
    if (c.unsafe) {
        if (c.result->loadout_attempted) ep_loadout_storage_quarantine_in_scope(c.mod,c.loadout,c.owner);
        // The original coordinator catches this after both core latches have
        // switched. It seals both paths and retains NEW data, never OLD rollback.
        RaiseException(0xe04333d2,EXCEPTION_NONCONTINUABLE,0,nullptr);
    }
}
}
int ep_multiplayer_loadout_commit(const HfApi* api,HfMod* mod,uint64_t roster,
    uint64_t component,uint64_t loadout,const EpLoadoutSourceSnapshot* current,
    const EpC33EntryCommitGuard* guard,EpMultiplayerLoadoutCommitResult* out)
{
    if (!out) return 0;*out={};out->loadout_result=EP_LOADOUT_STORAGE_STATE;
    if (!api || api->version!=13 || api->size<sizeof(HfApi) || !api->read || !current || !guard ||
        !guard->begin || !guard->validate || !guard->end || ep_roster_owner_in_scope()) return 0;
    EpLoadoutStorageInfo info={};uint64_t owner=0,game=0;
    if (!ep_loadout_storage_info(mod,loadout,&info)) return 0;
    out->loadout_state=info.state;out->initialization_step=info.initialization_step;
    if ((info.state!=EP_LOADOUT_STORAGE_PREPARED && info.state!=EP_LOADOUT_STORAGE_RETAINED) ||
        info.capacity!=EP_NATIVE_ROSTER_CAPACITY || !info.sources_imported ||
        !ep_component33_resource_entries_transaction_binding(mod,component,&owner,&game)) return 0;
    const auto& b=info.binding.setup.common;
    if (b.lifecycle.game!=game || ep_roster_owner_check_binding(mod,owner,game,b.roster,b.roster_storage)!=EP_OWNER_OK) return 0;
    EpPlayerJoinPeers ui_peers={},roster_peers={};
    if (!ep_loadout_storage_peer_binding(mod,loadout,&ui_peers)) return 0;
    ep_roster_group_peer_binding(mod,roster,&roster_peers);
    if (!ep_loadout_peers_equal(&ui_peers,&roster_peers)) {
        out->loadout_result=EP_LOADOUT_STORAGE_SOURCE;return 0;
    }
    LoadoutCommit c={mod,loadout,owner,current,*guard,out,nullptr,EP_C33_COMMIT_OLD,false,roster_peers};
    EpC33EntryCommitGuard wrapped={&c,begin,validate,end};
    const int ok=ep_multiplayer_commit_migrated(api,mod,roster,component,&wrapped,&out->multiplayer);
    if (ep_loadout_storage_info(mod,loadout,&info)) {
        out->loadout_state=info.state;out->initialization_step=info.initialization_step;
    }
    return ok && !c.unsafe && out->loadout_attempted && out->loadout_result==EP_LOADOUT_STORAGE_OK &&
        out->loadout_state==EP_LOADOUT_STORAGE_UI_MIGRATED;
}
