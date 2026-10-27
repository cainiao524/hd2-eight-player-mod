#ifndef EP_ROSTER_MIGRATION_H
#define EP_ROSTER_MIGRATION_H
#include "ep_roster_owner.h"
#include "ep_commit_read_budget.h"
#include "ep_component33_storage.h"
#include "ep_player_join_image.h"
enum {EP_ROSTER_MIGRATION_NONE,EP_ROSTER_MIGRATION_OK,EP_ROSTER_MIGRATION_ARGUMENT,
    EP_ROSTER_MIGRATION_READ,EP_ROSTER_MIGRATION_LAYOUT,EP_ROSTER_MIGRATION_IDENTITY,
    EP_ROSTER_MIGRATION_CHANGED,EP_ROSTER_MIGRATION_RESTORE};
typedef struct EpRosterMigrationResult {
    uint32_t status,read_bytes,restored,reserved;
    /* Included in read_bytes; zero when no peer bank is bound. Staged/restored
     * describe data only and do not imply successful activation. */
    uint32_t peer_count,peer_staged,peer_restored;
} EpRosterMigrationResult;
#ifdef __cplusplus
/* Internal stage owned by the joint coordinator. Fixed legacy four->eight
 * layout adapter, not configurable-capacity support. Current owner tickets
 * must already match the authoritative frozen session; never manufactures or
 * modifies tickets. Stable dense state only; pending admission is refused.
 * Only reads the supplied SDK and writes retained B and the optional peer bank.
 * Source identity, exclusion and allocation lifetime are still caller duties. */
struct EpRosterMigrationSnapshot {
    uint64_t global;uint32_t invalid,reserved;
    uint8_t source[0x428],map[64];
    struct Entity {uint64_t address;uint32_t id,flags;} entities[4];
    struct Peers {uint64_t global;uint32_t count,reserved;uint8_t records[128];} peers;
};
struct EpRosterMigrationStage {
    HfApi api;HfMod* mod;uint64_t owner;EpCommitReadBudget* budget;
    EpC33ResourceScopeView component;EpNativeRosterView view;
    EpRosterMigrationSnapshot source;
    uint8_t before[EP_NATIVE_ROSTER_BYTES],after[EP_NATIVE_ROSTER_BYTES];
    EpPlayerJoinPeers peers;
    uint8_t peer_before[256],peer_after[256];
    bool dirty,peer_dirty;EpRosterMigrationResult result;
};
/* Numeric bindings only, under a brief owner scope; no source reads or writes.
 * Call before ANY component staging to reject peer/source/allocation aliases.
 * Stage repeats this check under the joint exclusion lease. Zero peer client
 * retains the older roster-only adapter. */
bool ep_roster_migration_prepare(EpRosterMigrationStage*);
/* Called only within the exact owner's native scope. False is ordinary
 * validation failure; SEH propagates to the coordinator's existing boundary. */
bool ep_roster_migration_stage(EpRosterMigrationStage*);
bool ep_roster_migration_check(EpRosterMigrationStage*);
bool ep_roster_migration_intact(EpRosterMigrationStage*);
/* Restore both banks even if one restoration faults, after owner quarantine
 * if necessary, while its outer scope still excludes access. Coordinator must
 * catch SEH and keep UNSAFE frozen. No source/count/global writes are made. */
int ep_roster_migration_restore(void*);
#endif
#endif
