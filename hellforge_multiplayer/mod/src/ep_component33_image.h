#ifndef EP_COMPONENT33_IMAGE_H
#define EP_COMPONENT33_IMAGE_H
#include "ep_property_image.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_COMPONENT33_MOVER=1, EP_COMPONENT33_APPEND=2, EP_COMPONENT33_DENSE=3,
       EP_COMPONENT33_REMOVE=4, EP_COMPONENT33_MAX_IMAGE=4096, EP_COMPONENT33_STORAGE_BYTES=0x490 };
typedef struct EpComponent33Addresses {
    uint64_t game_base,code_address,component_address,storage_address,move_code_address,reject_address;
} EpComponent33Addresses;
typedef struct EpComponent33Image {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint8_t data[EP_COMPONENT33_MAX_IMAGE];
} EpComponent33Image;
/* Numeric byte emission only; no dereference, allocation, hook or publication.
 * Component header and inline eight-bucket map retain their original address.
 * B: pointers+0, bytes+0x40, primary+0x50, secondary+0x2d0; capacity eight.
 * Caller owns coherent counts/map/entity flags, readable records, storage
 * lifetime, synchronization and a non-returning refusal path for interior
 * frames. Remaining component33 writers/readers and creation rollback are
 * not implemented here. These images must not be activated on their own. */
EpPropertyResult ep_component33_image_build(uint32_t kind,const EpComponent33Addresses*,EpComponent33Image*);
#ifdef __cplusplus
}
#endif
#endif
