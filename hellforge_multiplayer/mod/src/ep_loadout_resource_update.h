#ifndef EP_LOADOUT_RESOURCE_UPDATE_H
#define EP_LOADOUT_RESOURCE_UPDATE_H
#include "ep_loadout_resource_owner.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_RESOURCE_UPDATE_BYTES 8192u
typedef EpLoadoutResourceOwnerAddresses EpLoadoutResourceUpdateAddresses;
typedef struct EpLoadoutResourceUpdateImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count,update;
    uint8_t data[EP_LOADOUT_RESOURCE_UPDATE_BYTES];
} EpLoadoutResourceUpdateImage;
/* Saved 66B090 owned-state update and published-object processing, RCX owner,
 * XMM1 delta. Phases, states, objects and published rows use shared banks;
 * transform publication scans capacity resources and bounds the destination
 * ordinal before calling services. Resource tails and native event IDs remain.
 * A missing catalog key skips catalog effects after restoring native aliases;
 * a missing state-4 timer property preserves its effect flag and skips expiry.
 * These are partial-progress semantics, not rollback of earlier notifications.
 * Native catalog indices, 22 effect categories, SIMD batch width and four
 * property-hash buckets retain their distinct meanings. Caller validates and
 * retains their allocations, service targets/ABI, returned transforms, native
 * queues and objects, and excludes mutation throughout the complete call.
 * No physical object creation, original hooks, activation or runtime proof. */
EpPropertyResult ep_loadout_resource_update_build(const EpLoadoutResourceUpdateAddresses*,EpLoadoutResourceUpdateImage*);
EpPropertyResult ep_loadout_resource_update_prepare(const HfApi*,HfMod*,const EpLoadoutResourceUpdateAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
