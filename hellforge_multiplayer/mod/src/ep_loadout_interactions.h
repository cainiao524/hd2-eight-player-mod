#ifndef EP_LOADOUT_INTERACTIONS_H
#define EP_LOADOUT_INTERACTIONS_H
#include "ep_loadout_consumers.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_INTERACTION_BYTES 8192u
typedef struct EpLoadoutInteractionAddresses {
    EpLoadoutConsumerAddresses common;
    uint64_t refresh_entry;
} EpLoadoutInteractionAddresses;
typedef struct EpLoadoutInteractionImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t input,edit,close;
    uint8_t data[EP_LOADOUT_INTERACTION_BYTES];
} EpLoadoutInteractionImage;
/* Saved 146D9B0 input, 146E0A0 edit and 146F3B0 edit-close. All calls between
 * these bodies use this image, and their native switch table is owned here.
 * Same lifecycle/maps/roster binding as the rest of the loadout group.
 * Focus cycles through capacity (including 5/6/7), skipping native disabled
 * widgets; index and roster bounds precede every relocated array access.
 * Four internal equipment choices, local widget zero, category/event enums,
 * menu hierarchy, resource service calls and their ABI remain unchanged.
 * Input selection is still a UI slot. The caller must preserve identity while
 * maps change, hold the same owner/exclusion across native callbacks, and
 * validate all original targets before a future publication.
 * 146E9D0 calls use the sibling refresh_entry from the same prepared group.
 * Packet/other map writers and layout still need routing. This group is
 * preparation, not an enabled UI. Never call while a sibling is discarded. */
EpPropertyResult ep_loadout_interactions_build(const EpLoadoutInteractionAddresses*,EpLoadoutInteractionImage*);
EpPropertyResult ep_loadout_interactions_prepare(const HfApi*,HfMod*,const EpLoadoutInteractionAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
