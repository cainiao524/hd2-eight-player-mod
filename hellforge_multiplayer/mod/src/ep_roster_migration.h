#ifndef EP_ROSTER_MIGRATION_H
#define EP_ROSTER_MIGRATION_H
#include "ep_roster_owner.h"
#include "ep_commit_read_budget.h"
#include "ep_component33_storage.h"
enum {EP_ROSTER_MIGRATION_NONE,EP_ROSTER_MIGRATION_OK,EP_ROSTER_MIGRATION_ARGUMENT,
    EP_ROSTER_MIGRATION_READ,EP_ROSTER_MIGRATION_LAYOUT,EP_ROSTER_MIGRATION_IDENTITY,
    EP_ROSTER_MIGRATION_CHANGED,EP_ROSTER_MIGRATION_RESTORE};
typedef struct EpRosterMigrationResult {uint32_t status,read_bytes,restored,reserved;} EpRosterMigrationResult;
#ifdef __cplusplus
/* Internal stage owned by the joint coordinator. Fixed legacy four->eight
 * layout adapter, not configurable-capacity support. Current owner tickets
 * must already match the authoritative frozen session; never manufactures or
 * modifies tickets. Stable dense state only; pending admission is refused.
 * Only reads the supplied SDK and writes the owner's retained B allocation.
 * Source identity, exclusion and allocation lifetime are still caller duties. */
struct EpRosterMigrationSnapshot {
    uint64_t global;uint32_t invalid,reserved;
    uint8_t source[0x428],map[64];
    struct Entity {uint64_t address;uint32_t id,flags;} entities[4];
};
struct EpRosterMigrationStage {
    HfApi api;HfMod* mod;uint64_t owner;EpCommitReadBudget* budget;
    EpC33ResourceScopeView component;EpNativeRosterView view;
    EpRosterMigrationSnapshot source;
    uint8_t before[EP_NATIVE_ROSTER_BYTES],after[EP_NATIVE_ROSTER_BYTES];
    bool dirty;EpRosterMigrationResult result;
};
/* Called only within the exact owner's native scope. False is ordinary
 * validation failure; SEH propagates to the coordinator's existing boundary. */
bool ep_roster_migration_stage(EpRosterMigrationStage*);
bool ep_roster_migration_check(EpRosterMigrationStage*);
bool ep_roster_migration_intact(EpRosterMigrationStage*);
/* Restore even after owner quarantine, while its outer scope still excludes
 * access. Coordinator must catch SEH independently and keep UNSAFE frozen. */
int ep_roster_migration_restore(void*);
#endif
#endif
