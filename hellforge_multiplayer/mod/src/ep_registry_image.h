#ifndef EP_REGISTRY_IMAGE_H
#define EP_REGISTRY_IMAGE_H
#include "ep_property_code.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_REGISTRY_IMAGE_MAX 1836u
typedef struct EpRegistryAddresses {
    uint64_t game_base,code_address,roster_address,storage_address,helper_code_address,reject_address;
} EpRegistryAddresses;
typedef struct EpRegistryImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint8_t data[EP_REGISTRY_IMAGE_MAX];
} EpRegistryImage;
/* kind 1 = B54E00 registry writer; kind 2 = 606520 associated-ID reader.
 * For kind 1, helper_code_address is the same binding's association BODY,
 * not an independently switched entry. Kind 2 ignores this field.
 * Explicit numeric bindings only; never discovers/installs/reads the game.
 * Other-tag callbacks and late rejection effects retain external contracts. */
EpPropertyResult ep_registry_image_build(uint32_t,const EpRegistryAddresses*,EpRegistryImage*);
EpPropertyResult ep_registry_code_prepare(const HfApi*,HfMod*,uint32_t,const EpRegistryAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
