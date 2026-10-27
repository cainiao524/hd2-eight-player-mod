#ifndef EP_MULTIPLAYER_COMMIT_H
#define EP_MULTIPLAYER_COMMIT_H
#include "ep_component33_resource_entries.h"
#include "ep_roster_migration.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpMultiplayerCommitResult {
    uint32_t outcome,roster_claimed;
    EpC33MigrationCommitResult component_migration;
    EpRosterMigrationResult roster_migration;
    uint32_t total_read_bytes;
} EpMultiplayerCommitResult;
/* Joint activation of the 18 roster and 25 component33 entries. Both groups
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
/* Fresh stable four-slot roster -> eight-slot B, in the same transaction.
 * Uses api.read for global roster/invalid ID, S[0..428), an external 8x8 map
 * (or its exact inline S+90 backing), and up to four entity +8/+14 DWORDs.
 * Captures twice before staging and once after validate; verifies map bijection,
 * partitions and the current owner's authoritative tickets before writing B.
 * When prepared with prepare_owned_peers, also migrates that exact confirmed-
 * peer bank: global owner at game+347CEF0, count at client+C8, and four complete
 * 32-byte records at client+D0. Confirms count/peer/network-index bijection to
 * current tickets, preserves old record bytes/order and zeroes new capacity.
 * Pending/mismatched sessions refuse migration. No index is derived from rank.
 * SDK reads across ALL migrations/windows share one hard 64 KiB budget.
 * Repeated reads detect changes, not exclusion. Guard's independent reads and
 * direct accesses to retained owned backups are outside this SDK accounting.
 * On OLD/UNSAFE before activation, restores roster B before external end;
 * failed restoration keeps the lease and quarantines. End faults after NEW
 * retain NEW data/latches. Guard must NOT mutate any owned buffer, including
 * the bound peer bank. Peer restore faults do not prevent roster restoration.
 * Guard still supplies engine freeze, current authenticated tickets/epoch,
 * other subsystem/capacity readiness and original source identity/lifetime.
 * No native roster/module discovery, ticket invention, installation or auto
 * binding; this is still the legacy eight-slot adapter, not a larger capacity. */
int ep_multiplayer_commit_migrated(const HfApi*,HfMod*,uint64_t roster_group,uint64_t component_entries,
    const EpC33EntryCommitGuard*,EpMultiplayerCommitResult*);
#ifdef __cplusplus
}
#endif
#endif
