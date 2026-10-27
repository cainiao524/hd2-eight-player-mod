#ifndef EP_LOADOUT_ROUTES_H
#define EP_LOADOUT_ROUTES_H
#include "ep_loadout_call.h"
#include "ep_multiplayer_loadout_commit.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {EP_LOADOUT_ROUTES_PREPARING=1,EP_LOADOUT_ROUTES_READY,EP_LOADOUT_ROUTES_COMMITTING,
      EP_LOADOUT_ROUTES_ACTIVE,EP_LOADOUT_ROUTES_QUARANTINED,EP_LOADOUT_ROUTES_CLEANING,EP_LOADOUT_ROUTES_CLEANUP};
typedef struct EpLoadoutRoutesInfo {
    uint64_t handle,loadout,roster_owner;
    uint32_t state,prepared,publish_attempts,published,retained,active,switching;
} EpLoadoutRoutesInfo;
/* Own all 55 gate contexts, code handles and one shared control in stable module
 * storage. Requires one imported RETAINED eight-slot loadout and its exact common
 * owner. Refuses a second group for the same game. No game access/publication.
 * Caller exclusively manages the loadout and retains policy.context throughout
 * every possible native call; this API does not own that external context.
 * No caller-visible individual code handles or independent latch/activation.
 * Failure with a nonzero handle retains cleanup work: retry cancel. */
int ep_loadout_routes_prepare(const HfApi*,HfMod*,uint64_t loadout,uint64_t roster_owner,
    const EpRosterCallPolicy*,EpLoadoutRoutesInfo*);
int ep_loadout_routes_info(HfMod*,uint64_t,EpLoadoutRoutesInfo*);
/* Only before permanent code retention/publication, including failed prepare.
 * Exposed or retained groups cannot be freed, detached, rebound or retried after
 * unsafe failure. Screen destruction/recreation is still a separate protocol. */
int ep_loadout_routes_cancel(HfMod*,uint64_t);
/* Explicit combined publication and roster/component/UI commit. Existing core
 * groups must already be published on OLD and share this exact owner/game.
 * Caller still supplies and validates whole-engine exclusion, native ABI and
 * targets, authenticated identities, screen/managers/pointee lifetime, all other
 * direct writers and lifecycle routing. Nothing here discovers these sources.
 *
 * begin drains execution before entering the shared UI barrier. validate runs
 * under that barrier and the common owner, refreshes current and satisfies the
 * underlying joint guard contract. Only after it succeeds are ALL gates retained
 * together and published via SDK hook_ex. The barrier stays raised through all
 * SDK calls, core migration/windows and widget initialization. NEW activates one
 * UI control before end(NEW); after end returns healthy, clears the barrier while
 * the owner is still held. Same-thread entry during staging/end is forbidden.
 *
 * A completely restored OLD transaction leaves all published gates on OLD and
 * permits retry without publishing again. Publication failure, a missing SDK
 * next pointer, unsafe rollback or callback fault instead seals the whole group,
 * retains every context/image, faults the owner and reports end(UNSAFE) once.
 * A throwing end is never called twice. NEW data/latches are never rolled back
 * after UI initialization. UNSAFE must keep external exclusion held. End must not
 * resume execution and then throw; the caller owns the exclusion implementation.
 *
 * current remains caller-owned and is consumed after validate. Imported/retained
 * source bytes must still match that snapshot; no refresh of retained sources is
 * invented. SDK read accounting remains the existing 64 KiB shared budget, which
 * excludes external guard and native accesses. This is an explicit integration
 * API, not auto-installation, a complete lifecycle or runtime/multiplayer proof. */
int ep_loadout_routes_commit(const HfApi*,HfMod*,uint64_t routes,uint64_t roster_group,
    uint64_t component_entries,const EpLoadoutSourceSnapshot* current,
    const EpC33EntryCommitGuard*,int32_t hook_priority,EpMultiplayerLoadoutCommitResult*);
#ifdef __cplusplus
}
#endif
#endif
