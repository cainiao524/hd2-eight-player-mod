#ifndef EP_MOVER_IMAGE_H
#define EP_MOVER_IMAGE_H
#include "ep_property_image.h"
#include "ep_session_code.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpMoverAddresses {
    uint64_t game_base,code_address,roster_address,storage_address,reject_address;
} EpMoverAddresses;
/* Uses the complete 0x680-byte B storage, not a standalone property array.
 * Only numeric inputs are processed. Move all four arrays and update the
 * pre-existing entity map; equal ordinals remain a no-op, including invalid ones. No automatic binding or publication. */
EpPropertyResult ep_mover_image_build(const EpMoverAddresses*,EpPropertyImage*);
/* READY remains cancellable. CLEANUP retains its handle for discard retry. */
EpPropertyResult ep_mover_code_prepare(const HfApi*,HfMod*,const EpMoverAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
