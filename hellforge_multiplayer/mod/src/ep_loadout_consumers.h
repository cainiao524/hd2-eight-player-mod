#ifndef EP_LOADOUT_CONSUMERS_H
#define EP_LOADOUT_CONSUMERS_H
#include "ep_loadout_lifecycle.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_CONSUMER_BYTES 8192u
typedef struct EpLoadoutMaps {
    uint32_t network_to_slot[EP_LOADOUT_LIFECYCLE_LIMIT];
    uint32_t slot_to_network[EP_LOADOUT_LIFECYCLE_LIMIT];
} EpLoadoutMaps;
typedef struct EpLoadoutConsumerAddresses {
    EpLoadoutAddresses lifecycle;
    uint64_t forward_map,inverse_map,roster,roster_storage;
} EpLoadoutConsumerAddresses;
typedef struct EpLoadoutConsumerImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t update,lookup,action;
    uint8_t data[EP_LOADOUT_CONSUMER_BYTES];
} EpLoadoutConsumerImage;
/* Initialize caller-owned maps before any native entry can observe them.
 * Slot zero stays local; FF means no mapping. Failed arguments do not write.
 * Do not reset/rebind while a screen or callback is live. No identity lookup,
 * allocation, game access, hook publication or automatic initialization. */
int ep_loadout_maps_initialize(EpLoadoutMaps*,uint32_t capacity,uint32_t local_network);
/* Saved 146C2F0 update, complete chained 1470650 record lookup and 14719F0
 * action. Use EXACTLY the lifecycle's screen/records/widgets/capacity, plus
 * the shared roster owner's header and B storage (E8=>B, 2C8=>B+3C0,
 * 3A8=>B+580). Calls to 1470650 stay inside this prepared image.
 * All native widget callbacks, float/stack arguments, nested four equipment
 * choices and the separate original 9F8 peer bank remain native. That peer
 * bank's four-entry scan is NOT widened without its own storage migration.
 * Network and UI indices are independently bounded. Player actions also
 * require the inverse map to match. The update's eight activity bytes use
 * the existing +38..3F stack gap; outgoing arguments end at +30. Unwind
 * code offsets and chained parents follow the relocated instruction ends.
 * Caller must retain/exclude all sources and writers for each complete call,
 * validate build/targets and synchronize with the roster owner. The rejection
 * target must not return from either an entry guard or a live native frame.
 * 1466170 setup is supplied by ep_loadout_setup using these same maps.
 * Still required: other UI consumers/map writers, verified layouts,
 * authoritative identity/lifetime binding and common activation. This is
 * not an installable or runtime-verified UI package. */
EpPropertyResult ep_loadout_consumers_build(const EpLoadoutConsumerAddresses*,EpLoadoutConsumerImage*);
/* Shared numerical binding validation; does not dereference any address. */
EpPropertyResult ep_loadout_consumers_validate(const EpLoadoutConsumerAddresses*);
EpPropertyResult ep_loadout_consumers_validate_span(const EpLoadoutConsumerAddresses*,uint32_t code_bytes);
/* Numerical, 16-byte-aligned sibling entry, outside this code/data binding.
 * Proves no ownership/identity or target contents. Group preparation supplies
 * links from the actual sibling image offsets and holds their common lifetime. */
EpPropertyResult ep_loadout_consumers_validate_link(const EpLoadoutConsumerAddresses*,uint64_t entry);
/* Cancellable READY allocation only; does not execute any candidate entry.
 * CLEANUP retains the returned handle for discard retry. */
EpPropertyResult ep_loadout_consumers_prepare(const HfApi*,HfMod*,const EpLoadoutConsumerAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
