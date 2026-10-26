#ifndef EP_LOADOUT_REFRESH_H
#define EP_LOADOUT_REFRESH_H
#include "ep_loadout_consumers.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_REFRESH_BYTES 8192u
typedef struct EpLoadoutRefreshAddresses {
    EpLoadoutConsumerAddresses common;
    uint64_t close_entry;
} EpLoadoutRefreshAddresses;
typedef struct EpLoadoutRefreshImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,handler_offset;
    uint8_t data[EP_LOADOUT_REFRESH_BYTES];
} EpLoadoutRefreshImage;
/* Complete saved 146E9D0 refresh, three native fragments, own switch table
 * and chained GS unwind. All player traversal, animation and record pointers
 * use the shared capacity/storage. Preserve the native four-choice/category
 * meanings of EBP; only each actual player counter changes.
 * The nested close_entry belongs to the same group's interactions image;
 * numerical validation is not proof of sibling ownership or contents.
 * Native control hierarchy/resource ABI and record-index semantics remain.
 * Requires owner/exclusion through all nested calls. No discovery, game
 * access, hooks or automatic invocation. Other writers, identity changes,
 * layout and runtime validation still gate actual publication. */
EpPropertyResult ep_loadout_refresh_build(const EpLoadoutRefreshAddresses*,EpLoadoutRefreshImage*);
EpPropertyResult ep_loadout_refresh_prepare(const HfApi*,HfMod*,const EpLoadoutRefreshAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
