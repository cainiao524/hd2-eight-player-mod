#ifndef EP_MULTIPLAYER_LOADOUT_COMMIT_H
#define EP_MULTIPLAYER_LOADOUT_COMMIT_H
#include "ep_multiplayer_commit.h"
#include "ep_loadout_storage.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpMultiplayerLoadoutCommitResult {
    EpMultiplayerCommitResult multiplayer;
    uint32_t loadout_attempted,loadout_result,loadout_state,initialization_step;
} EpMultiplayerLoadoutCommitResult;
/* Explicit joint roster/component migration plus owned loadout initialization.
 * The eight-slot legacy adapter requires an eight-slot imported PREPARED or
 * RETAINED loadout bound to the SAME game/roster/B owner. No automatic invocation,
 * game discovery, installation or sampling. Management is caller-exclusive:
 * never cancel/reimport/initialize/share this loadout during the transaction.
 *
 * guard.begin/validate have the normal full-engine exclusion requirements.
 * validate must fill/refresh the caller-owned current snapshot under that
 * exclusion and validate all native targets, screen/manager/pointee lifetimes,
 * UI source producers and routing requirements before returning success.
 * current must remain readable and coherent through end; it is intentionally
 * consumed AFTER validate, not copied before begin. Snapshot collection is
 * caller-supplied: no extra SDK reads are introduced here. The existing shared
 * 64 KiB SDK budget still excludes guard callbacks and native engine accesses.
 *
 * OLD rollback never invokes UI. On NEW, both core latches/data are switched
 * before the initializer retains/constructs/migrates/replaces UI, all under the
 * same owner and external lease. Only then is guard.end(NEW) called. That end
 * still owes all UI entry/source-writer routing and other subsystem switches
 * before releasing exclusion; UI_MIGRATED alone is not runtime readiness.
 *
 * Any initialization refusal/fault after the core switch becomes UNSAFE:
 * preserve NEW core data/latches, quarantine loadout/common owner and notify
 * end(UNSAFE) exactly once. Never roll back partially constructed UI. A fault
 * or swallowed nested failure in end(NEW) also quarantines loadout, without
 * calling end a second time. End must not throw or resume execution before its
 * obligations are complete. No UI hooks/provider/freeze implementation here;
 * fifth-player gameplay, native UI and full multiplayer remain unverified. */
int ep_multiplayer_loadout_commit(const HfApi*,HfMod*,uint64_t roster_group,
    uint64_t component_entries,uint64_t loadout,const EpLoadoutSourceSnapshot* current,
    const EpC33EntryCommitGuard*,EpMultiplayerLoadoutCommitResult*);
#ifdef __cplusplus
}
#endif
#endif
