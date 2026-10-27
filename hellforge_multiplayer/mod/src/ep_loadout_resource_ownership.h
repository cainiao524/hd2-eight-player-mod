#ifndef EP_LOADOUT_RESOURCE_OWNERSHIP_H
#define EP_LOADOUT_RESOURCE_OWNERSHIP_H
#include "ep_loadout_resource_owner.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_RESOURCE_OWNERSHIP_BYTES 8192u
typedef EpLoadoutResourceOwnerAddresses EpLoadoutResourceOwnershipAddresses;
typedef struct EpLoadoutResourceOwnershipImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t settle,promote,demote;
    uint8_t data[EP_LOADOUT_RESOURCE_OWNERSHIP_BYTES];
} EpLoadoutResourceOwnershipImage;
/* Saved 66C100 pending settlement, 66C300 promotion, 66C590 demotion.
 * Settlement routes each pending object through the owned promotion entry:
 * the original forward-copy order could overwrite its identity when the
 * owned prefix was smaller than the already-published set. Promotion swaps
 * object/row/replicated-state values, updates both hash ordinals, clears the
 * new owned phase and increments +C exactly once. Inactive phase rows retain
 * native unused-slot semantics; demotion swaps all four banks and decrements
 * +C. The final settlement publishes +8 = +4 only after processing pending
 * objects. Header +0 retains native behavior; it is not adjusted here.
 * Caller retains owner/hash/scratch-service backing, excludes mutation,
 * supplies pending-owned objects, and keeps native object ownership flags
 * consistent with callback ordering. Promotion targets must be outside the
 * owned prefix; demotion targets must be inside. These entries do not alter
 * object ownership flags or establish engine callback routing/retention.
 * No game access, hooks, activation or verified multiplayer behavior. */
EpPropertyResult ep_loadout_resource_ownership_build(const EpLoadoutResourceOwnershipAddresses*,EpLoadoutResourceOwnershipImage*);
EpPropertyResult ep_loadout_resource_ownership_prepare(const HfApi*,HfMod*,const EpLoadoutResourceOwnershipAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
