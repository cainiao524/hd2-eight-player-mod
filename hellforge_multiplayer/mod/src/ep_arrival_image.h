#ifndef EP_ARRIVAL_IMAGE_H
#define EP_ARRIVAL_IMAGE_H
#include "ep_property_code.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_ARRIVAL_IMAGE_MAX 2024u
typedef struct EpArrivalAddresses {
    uint64_t game_base,code_address,roster_address,storage_address,reject_address;
} EpArrivalAddresses;
typedef struct EpArrivalImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint8_t data[EP_ARRIVAL_IMAGE_MAX];
} EpArrivalImage;
/* Saved 6054F0 state update, including original GS handler forwarding.
 * Explicit bindings only. No automatic publication, character creation,
 * resource allocation or identity resolution is implied by this API. */
EpPropertyResult ep_arrival_image_build(const EpArrivalAddresses*,EpArrivalImage*);
EpPropertyResult ep_arrival_code_prepare(const HfApi*,HfMod*,const EpArrivalAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
