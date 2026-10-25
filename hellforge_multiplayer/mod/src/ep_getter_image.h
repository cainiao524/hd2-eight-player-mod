#ifndef EP_GETTER_IMAGE_H
#define EP_GETTER_IMAGE_H
#include "ep_property_image.h"
#include "ep_session_code.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpGetterAddresses {
    uint64_t game_base,code_address,roster_address,storage_address,reject_address;
} EpGetterAddresses;
/* Uses the complete 0x680-byte B storage, not a standalone property array.
 * Only numeric inputs are processed. Return the full property DWORD; do not
 * clamp a network index to ordinal. No automatic binding or publication. */
EpPropertyResult ep_getter_image_build(const EpGetterAddresses*,EpPropertyImage*);
/* READY remains cancellable. CLEANUP retains its handle for discard retry. */
EpPropertyResult ep_getter_code_prepare(const HfApi*,HfMod*,const EpGetterAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
