#ifndef EP_DEPARTURE_IMAGE_H
#define EP_DEPARTURE_IMAGE_H
#include "ep_property_code.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_DEPARTURE_IMAGE_MAX 2712u
typedef struct EpDepartureAddresses {
    uint64_t game_base,code_address,roster_address,storage_address,getter_code_address,reject_address;
} EpDepartureAddresses;
typedef struct EpDepartureImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint8_t data[EP_DEPARTURE_IMAGE_MAX];
} EpDepartureImage;
/* Saved 605950 pre-removal callbacks, with thirteen chained body fragments.
 * getter_code_address identifies the shared 606AD0 getter BODY. This image is
 * prepared independently or as entry 15 with the same-group getter body.
 * Explicit numeric bindings only. No game discovery or automatic publication.
 * Original callback effects and player-count resources remain external contracts. */
EpPropertyResult ep_departure_image_build(const EpDepartureAddresses*,EpDepartureImage*);
EpPropertyResult ep_departure_code_prepare(const HfApi*,HfMod*,const EpDepartureAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
