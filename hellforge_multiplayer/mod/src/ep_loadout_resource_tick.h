#ifndef EP_LOADOUT_RESOURCE_TICK_H
#define EP_LOADOUT_RESOURCE_TICK_H
#include "ep_loadout_resource_owner.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_RESOURCE_TICK_BYTES 8192u
typedef EpLoadoutResourceOwnerAddresses EpLoadoutResourceTickAddresses;
typedef struct EpLoadoutResourceTickImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t update,any_ready,slot_ready;
    uint8_t data[EP_LOADOUT_RESOURCE_TICK_BYTES];
} EpLoadoutResourceTickImage;
/* Complete saved 66B090 update, 663240 any-ready and 663310 slot-ready.
 * These entries share the registered owner object/phase/row/state sidecars
 * and countdown resource bank. All four owner counts and queried ordinals
 * are bounded. Missing hash entries return false/skip; corrupt dense indexes
 * reject. Native state 4, 45 effect types, 22 effect channels, four hash
 * buckets and native catalog/actor services are not player-capacity limits.
 * The effect switch and type selector tables live in this same code image.
 * Caller retains initialized owner/hash/phase/row banks, resource transforms,
 * engine/catalog/effect backing and excludes mutation across native callbacks.
 * Registration alone does not establish these fields or additional physical
 * resources. Their initialization/publication and remaining owner consumers
 * need routing before common publication. No hooks or runtime verification. */
EpPropertyResult ep_loadout_resource_tick_build(const EpLoadoutResourceTickAddresses*,EpLoadoutResourceTickImage*);
EpPropertyResult ep_loadout_resource_tick_prepare(const HfApi*,HfMod*,const EpLoadoutResourceTickAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
