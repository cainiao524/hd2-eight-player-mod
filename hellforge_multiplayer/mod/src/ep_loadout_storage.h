#ifndef EP_LOADOUT_STORAGE_H
#define EP_LOADOUT_STORAGE_H
#include "ep_loadout_group.h"
#ifdef __cplusplus
extern "C" {
#endif

enum {EP_LOADOUT_STORAGE_SLOTS=3};
typedef enum EpLoadoutStorageResult {
    EP_LOADOUT_STORAGE_OK,EP_LOADOUT_STORAGE_ARGUMENT,EP_LOADOUT_STORAGE_POINTER,
    EP_LOADOUT_STORAGE_CONFLICT,EP_LOADOUT_STORAGE_RESERVE,EP_LOADOUT_STORAGE_GROUP,
    EP_LOADOUT_STORAGE_STATE,EP_LOADOUT_STORAGE_RETAIN_FAILED,EP_LOADOUT_STORAGE_CLEANUP,
    EP_LOADOUT_STORAGE_SOURCE,EP_LOADOUT_STORAGE_COUNTS,EP_LOADOUT_STORAGE_STALE,
    EP_LOADOUT_STORAGE_SCOPE,EP_LOADOUT_STORAGE_NATIVE_FAILED
} EpLoadoutStorageResult;
enum {EP_LOADOUT_STORAGE_PREPARING=1,EP_LOADOUT_STORAGE_PREPARED,
      EP_LOADOUT_STORAGE_RETAINING,EP_LOADOUT_STORAGE_RETAINED,
      EP_LOADOUT_STORAGE_CLEANING,EP_LOADOUT_STORAGE_CLEANUP_REQUIRED,
      EP_LOADOUT_STORAGE_INITIALIZING,EP_LOADOUT_STORAGE_UI_MIGRATED,
      EP_LOADOUT_STORAGE_QUARANTINED};
enum {EP_LOADOUT_INIT_NONE,EP_LOADOUT_INIT_CHECKING,EP_LOADOUT_INIT_RETAINING,
      EP_LOADOUT_INIT_CONSTRUCTING,EP_LOADOUT_INIT_REPLACING,EP_LOADOUT_INIT_DONE};
enum {EP_LOADOUT_SCREEN_NONE,EP_LOADOUT_SCREEN_LIVE,EP_LOADOUT_SCREEN_CLEANED,
      EP_LOADOUT_SCREEN_PARKED,EP_LOADOUT_SCREEN_REBUILDING};

typedef struct EpLoadoutStorageBindings {
    EpLoadoutGroupAddresses group;
    uint64_t desired_arena; /* zero lets Windows choose an owned RW allocation */
    uint32_t local_network_index,invalid_resource_id;
} EpLoadoutStorageBindings;

typedef struct EpLoadoutStorageInfo {
    uint64_t handle,arena,initialization_owner;
    uint32_t bytes,capacity,state,group_result,sources_imported;
    uint32_t initialization_step,owner_result;
    EpLoadoutGroupAddresses binding;
    EpLoadoutGroup group;
    uint64_t screen_manager;
    uint32_t screen_phase;
} EpLoadoutStorageInfo;

enum {EP_LOADOUT_NATIVE_CAPACITY=4,EP_LOADOUT_RECORD_SOURCE_OFFSET=0x948,
      EP_LOADOUT_RECORD_SOURCE_BYTES=0x234,EP_LOADOUT_RESOURCE_SOURCE_OFFSET=0x11d18,
      EP_LOADOUT_RESOURCE_SOURCE_BYTES=4*0x4c,EP_LOADOUT_OWNER_SOURCE_BYTES=0x118};
typedef struct EpLoadoutSourceSnapshot {
    uint64_t game,record_manager,global_record_manager,countdown_manager,global_countdown_manager,
             resource_owner,global_resource_owner;
    /* Exact owned byte copies, not addresses to be read by this API:
     * record manager [948,B7C), countdown manager [11D18,11E48), owner [0,118).
     * Record status/equipment source windows overlap; capture the whole window
     * once, preserving that relationship when projecting into separate banks. */
    uint8_t record_window[EP_LOADOUT_RECORD_SOURCE_BYTES];
    uint8_t resources[EP_LOADOUT_RESOURCE_SOURCE_BYTES];
    uint8_t owner[EP_LOADOUT_OWNER_SOURCE_BYTES];
} EpLoadoutSourceSnapshot;

/* Owns twelve disjoint data banks and the linked 22-image group. In input.group,
 * records/widgets, both maps, record actors/equipment/status, countdown resources
 * and resource-owner objects/phases/rows/states MUST be zero. They are derived
 * from one page-rounded RW arena, with capacity-sized rows and 16-byte alignment.
 * Maps start FF except local -> slot zero; resource IDs use invalid_resource_id;
 * all other new storage is zero. No supplied numerical address is dereferenced.
 *
 * This initially creates FRESH backing. import_sources below can stage eight
 * source banks; it does not construct widgets or clone game resources.
 * Existing state must be coherently imported and native widgets
 * constructed before use. External screen/managers/hash backing/roster B and
 * their ownership remain caller obligations. One fixed screen address per game
 * is allowed; the coordinated screen routes below retain and reuse it.
 *
 * Internal code handles belong exclusively to this storage owner. Do not cancel,
 * publish, retain or invoke them independently. PREPARED is not callable game
 * state. Never expose entries or data before whole-group retention and the
 * separate source/exclusion/initialization/publication gates are satisfied.
 * No game discovery, reads, source writes, hooks, installation or activation. */
EpLoadoutStorageResult ep_loadout_storage_prepare(const HfApi*,HfMod*,const EpLoadoutStorageBindings*,EpLoadoutStorageInfo*);
/* Same owned UI allocation with update/action bound to the roster's exact
 * confirmed-peer bank. Copies the binding, never copies/allocates/frees the
 * bank. Its native owner and records must be retained and all writers excluded
 * by the same session owner. Rejects aliases with the whole UI arena, external
 * sources and code reservation windows before writing initialization bytes.
 * Other UI families still require conversion before real activation. */
EpLoadoutStorageResult ep_loadout_storage_prepare_peers(const HfApi*,HfMod*,const EpLoadoutStorageBindings*,const EpPlayerJoinPeers*,EpLoadoutStorageInfo*);
/* Stable PREPARED/RETAINED/UI_MIGRATED metadata only. A legacy allocation
 * returns success with all-zero fields; stale/foreign/transient handles fail. */
int ep_loadout_storage_peer_binding(HfMod*,uint64_t,EpPlayerJoinPeers*);
int ep_loadout_storage_info(HfMod*,uint64_t,EpLoadoutStorageInfo*);
/* PREPARED and capacity >=4 only: validate the captured global identities and
 * resource-owner 0<=prefix<=published<=total<=4 and auxiliary count <=4.
 * Copy ALL FOUR legacy slots, including inactive opaque data, without changing
 * source ordinal. Stage actors/equipment/status, countdown resources and owner
 * objects/phases/rows/states together. New rows are zero, with invalid resource
 * IDs from prepare. Re-import replaces the entire unexposed source baseline.
 * Invalid input changes neither target bytes nor the prior import baseline.
 *
 * Caller supplies coherent owned copies under exclusion; no source pointer is
 * followed. Header/hash/pointees remain external, with their existing ownership.
 * Captured owner header is checked for counts, NOT hash/pointee/flag consistency.
 * Native source producers must be redirected and external hash/object state
 * validated separately. No screen records/maps/widgets are copied or constructed.
 * Successful import proves byte staging only, not gameplay-ready state. */
EpLoadoutStorageResult ep_loadout_storage_import_sources(HfMod*,uint64_t,const EpLoadoutSourceSnapshot*);
/* Before exposure only. Cancel discards ALL code first, then the arena. Failed
 * cleanup retains backing and a retryable handle, exposing no callable entries.
 * Stale/foreign handles cannot reclaim a later allocation. */
EpLoadoutStorageResult ep_loadout_storage_cancel(HfMod*,uint64_t);
/* Permanently retains the entire code set, module and arena as one owner.
 * Failure keeps PREPARED and cancellable; success forbids cancellation even if
 * later publication fails. Caller must exclude every old/new call throughout
 * the eventual coordinated publication. Retention only proves lifetime, not
 * source freshness, coherent imported state, native ABI or multiplayer readiness.
 * No hook/target is installed and no native game function is invoked.
 * Once sources were imported, this legacy retain call refuses them; use the
 * snapshot-aware variant below, so stale source/target bytes cannot bypass it. */
EpLoadoutStorageResult ep_loadout_storage_retain(HfMod*,uint64_t);
/* Imported owners only. Compare a caller-provided current coherent snapshot
 * against the import baseline and compare all eight complete target banks
 * (including initialized new rows) before retaining. Caller MUST hold exclusion
 * over source and target reads/writes/calls through eventual publication.
 * No live read, scope acquisition, source/header write or automatic publication.
 * This does not check screen state, external hash contents or pointed-to data;
 * a future activation path must close those additional freshness/lifetime gates.
 * Mismatch remains PREPARED, cancellable and eligible for a fresh import. */
EpLoadoutStorageResult ep_loadout_storage_retain_sources(HfMod*,uint64_t,const EpLoadoutSourceSnapshot* current);

/* EXPLICIT native invocation, never called by Mod init/prepare/import/retain.
 * Requires an ALREADY ACTIVE native call scope of roster_owner with the same
 * game/roster/B binding. Caller must additionally exclude/drain every old/new
 * and unhooked engine call, retain screen/managers/pointees, validate native
 * targets and rejection policy, and supply the current coherent owned snapshot.
 * The roster lock alone does not establish those engine guarantees.
 *
 * From PREPARED or RETAINED, check source/target freshness, retain all 22 images,
 * construct fresh record/widget banks, then migrate records/maps and replace
 * four inline roots. Calls occur without the storage lock. UI_MIGRATED means
 * these two calls returned; it is NOT activation, refresh or source redirection.
 * Keep engine exclusion until the caller completes every publication gate.
 *
 * Source/binding/retention rejection before native work preserves the original
 * state for correction. Any native exception, nested owner failure, or recursive
 * initialization quarantines both owners and keeps all backing; no retry,
 * cancellation, automatic release or rollback. The caller must retain exclusion
 * on failure and must NOT report an OLD rollback after partial UI mutation.
 * C++ exceptions and longjmp are unsupported. No discovery, sampling or hooks.
 * ep_multiplayer_loadout_commit coordinates these calls with the existing
 * roster/component commit; external UI routing remains a caller obligation. */
EpLoadoutStorageResult ep_loadout_storage_initialize_in_scope(HfMod*,uint64_t handle,
    uint64_t roster_owner,const EpLoadoutSourceSnapshot* current);
/* Bound storage requires the coordinator's current roster peer binding;
 * legacy initialization refuses a bound bank. Mismatch is SOURCE before any
 * retention, constructor, replacement or storage state change. The expected
 * value comes from the claimed roster group under the common exclusion, not
 * from UI metadata alone. An all-zero expected value is the legacy binding. */
EpLoadoutStorageResult ep_loadout_storage_initialize_peers_in_scope(HfMod*,uint64_t handle,
    uint64_t roster_owner,const EpLoadoutSourceSnapshot* current,const EpPlayerJoinPeers* expected);
/* Coordinator failure AFTER an initialization attempt, including a later
 * end(NEW) fault. Requires the exact recorded owner's still-held native scope
 * (healthy or faulted). Quarantines that owner and this generation, hides
 * entries, retains all backing and never releases the external exclusion.
 * Idempotent for the same owner; no standalone/out-of-scope recovery API. */
int ep_loadout_storage_quarantine_in_scope(HfMod*,uint64_t handle,uint64_t roster_owner);

/* Successful NEW setup/exit return only, while the call bridge still holds the
 * exact owner. Resource release/reset alone never authorizes screen reuse. */
int ep_loadout_storage_screen_return_in_scope(HfMod*,uint64_t handle,uint64_t roster_owner,uint32_t native_rva);
/* Selected screen kind 11 only. Saved 25480438 dispatch evidence:
 * 14984E0 -> 1498AE1 allocates/zeros 2739D0, calls 14A17E0, stores manager+B0;
 * 14966E0 -> 1496AFB calls 1467B90; 14AC340 -> 14AC4E9 frees then clears B0.
 * 14971C0 only hides a stacked screen; it is NOT this deallocation boundary.
 *
 * NEW 14AC340 retains the exact cleaned screen allocation instead of freeing
 * it, clears B0, and parks it. NEW 14984E0 requires that same manager's B0==0;
 * zeroes the retained screen and its four UI banks, runs the full relocated
 * constructor once, then publishes B0. All eight shared source banks and all
 * sealed code remain allocated and bound at the same addresses. Both maps
 * start FF; subsequent normal setup assigns the CURRENT local player.
 *
 * Requires all 62 routes, the common owner and complete external engine
 * exclusion/lifetime coverage. No independent call may free this allocation,
 * and no rebinding to another screen/manager is supported. No re-import, extra
 * widget attachment, allocator hook or code rewriting occurs. Native failures
 * or recursive requests quarantine the owner; partial construction is never
 * published or retried. The retained screen is released only at process exit.
 * Explicit native invocation only; never auto-called by Mod init. */
EpLoadoutStorageResult ep_loadout_storage_screen_in_scope(HfMod*,uint64_t handle,uint64_t roster_owner,
    uint32_t native_rva,uint64_t screen_manager);

#ifdef __cplusplus
}
#endif
#endif
