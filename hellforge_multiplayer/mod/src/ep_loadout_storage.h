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
    EP_LOADOUT_STORAGE_SOURCE,EP_LOADOUT_STORAGE_COUNTS,EP_LOADOUT_STORAGE_STALE
} EpLoadoutStorageResult;
enum {EP_LOADOUT_STORAGE_PREPARING=1,EP_LOADOUT_STORAGE_PREPARED,
      EP_LOADOUT_STORAGE_RETAINING,EP_LOADOUT_STORAGE_RETAINED,
      EP_LOADOUT_STORAGE_CLEANING,EP_LOADOUT_STORAGE_CLEANUP_REQUIRED};

typedef struct EpLoadoutStorageBindings {
    EpLoadoutGroupAddresses group;
    uint64_t desired_arena; /* zero lets Windows choose an owned RW allocation */
    uint32_t local_network_index,invalid_resource_id;
} EpLoadoutStorageBindings;

typedef struct EpLoadoutStorageInfo {
    uint64_t handle,arena;
    uint32_t bytes,capacity,state,group_result,sources_imported;
    EpLoadoutGroupAddresses binding;
    EpLoadoutGroup group;
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
 * their ownership remain caller obligations. One binding generation per game
 * is allowed; recreating/rebinding a screen is not implemented by this API.
 *
 * Internal code handles belong exclusively to this storage owner. Do not cancel,
 * publish, retain or invoke them independently. PREPARED is not callable game
 * state. Never expose entries or data before whole-group retention and the
 * separate source/exclusion/initialization/publication gates are satisfied.
 * No game discovery, reads, source writes, hooks, installation or activation. */
EpLoadoutStorageResult ep_loadout_storage_prepare(const HfApi*,HfMod*,const EpLoadoutStorageBindings*,EpLoadoutStorageInfo*);
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

#ifdef __cplusplus
}
#endif
#endif
