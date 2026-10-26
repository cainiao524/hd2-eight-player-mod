#ifndef EP_MULTIPLAYER_COMMIT_H
#define EP_MULTIPLAYER_COMMIT_H
#include "ep_component33_resource_entries.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpMultiplayerCommitResult {
    uint32_t outcome,roster_claimed;
    EpC33MigrationCommitResult component_migration;
} EpMultiplayerCommitResult;
/* Joint activation of the 17 roster and 25 component33 entries. Both groups
 * must already be fully published on OLD and bound to the exact same owner
 * and game. Reserves roster management, drains external execution once, and
 * bars same-thread roster entry throughout staging/end as well as component33.
 * Fresh component33 migration/window rollback are the existing implementation.
 * After successful windows/data validation, switches BOTH groups under the
 * common owner before calling end(NEW); no routed call can observe one NEW
 * and the other OLD. Metadata queries are not an atomic two-group snapshot.
 * Safe OLD failure restores component33 before guard.end rolls back the other
 * staged data. Unsafe callbacks/rollback quarantine BOTH paths and keep the
 * external lease. End faults after NEW preserve both latches, never retry.
 *
 * Guard.validate STILL owes current roster migration/identities, capacity and
 * other subsystems; no fake tickets or engine freeze are supplied. The guard
 * must exclude all unhooked/old paths, including calls selected before begin.
 * The component's 64 KiB SDK budget excludes guard callbacks' own accesses.
 * The caller must own the activation lifecycle: do not concurrently commit a
 * member via its standalone API or share it between different joint pairs.
 * The initial READY binding query is observational, not a reservation of two
 * independent management APIs. Competing calls for this same roster are
 * rejected by its claim; component commit still checks/reserves its own READY.
 * Publication is not performed here. No automatic initialization/game access;
 * explicit runtime authorization and engine preflight remain required. Real
 * fifth-player gameplay, native UI and eight-account operation are unverified. */
int ep_multiplayer_commit(HfMod*,uint64_t roster_group,uint64_t component_entries,
    const EpC33EntryCommitGuard*,EpMultiplayerCommitResult*);
#ifdef __cplusplus
}
#endif
#endif
