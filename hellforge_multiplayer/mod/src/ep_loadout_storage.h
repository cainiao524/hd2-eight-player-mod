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
    EP_LOADOUT_STORAGE_STATE,EP_LOADOUT_STORAGE_RETAIN_FAILED,EP_LOADOUT_STORAGE_CLEANUP
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
    uint32_t bytes,capacity,state,group_result;
    EpLoadoutGroupAddresses binding;
    EpLoadoutGroup group;
} EpLoadoutStorageInfo;

/* Owns twelve disjoint data banks and the linked 22-image group. In input.group,
 * records/widgets, both maps, record actors/equipment/status, countdown resources
 * and resource-owner objects/phases/rows/states MUST be zero. They are derived
 * from one page-rounded RW arena, with capacity-sized rows and 16-byte alignment.
 * Maps start FF except local -> slot zero; resource IDs use invalid_resource_id;
 * all other new storage is zero. No supplied numerical address is dereferenced.
 *
 * This is FRESH backing, not migration, native widget construction or a clone of
 * game resources. Existing state must be coherently imported and native widgets
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
/* Before exposure only. Cancel discards ALL code first, then the arena. Failed
 * cleanup retains backing and a retryable handle, exposing no callable entries.
 * Stale/foreign handles cannot reclaim a later allocation. */
EpLoadoutStorageResult ep_loadout_storage_cancel(HfMod*,uint64_t);
/* Permanently retains the entire code set, module and arena as one owner.
 * Failure keeps PREPARED and cancellable; success forbids cancellation even if
 * later publication fails. Caller must exclude every old/new call throughout
 * the eventual coordinated publication. Retention only proves lifetime, not
 * source freshness, coherent imported state, native ABI or multiplayer readiness.
 * No hook/target is installed and no native game function is invoked. */
EpLoadoutStorageResult ep_loadout_storage_retain(HfMod*,uint64_t);

#ifdef __cplusplus
}
#endif
#endif
