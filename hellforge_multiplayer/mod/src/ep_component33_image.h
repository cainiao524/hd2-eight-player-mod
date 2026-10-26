#ifndef EP_COMPONENT33_IMAGE_H
#define EP_COMPONENT33_IMAGE_H
#include "ep_property_image.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_COMPONENT33_MOVER=1, EP_COMPONENT33_APPEND=2, EP_COMPONENT33_DENSE=3,
       EP_COMPONENT33_REMOVE=4, EP_COMPONENT33_ENTER=5, EP_COMPONENT33_LEAVE=6,
       EP_COMPONENT33_PROPERTY=7, EP_COMPONENT33_RESET=8,
       EP_COMPONENT33_DIRECT_DENSE=9, EP_COMPONENT33_DIRECT_APPEND=10,
       EP_COMPONENT33_DIRECT_REMOVE=11, EP_COMPONENT33_RESET_CONTROL=12,
       EP_COMPONENT33_RESET_DENSE=13,
       EP_COMPONENT33_MAX_IMAGE=4096, EP_COMPONENT33_STORAGE_BYTES=0x490 };
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
 * not implemented here. Classification helper images retain entity-in-RDX ABI;
 * their registered callback wrappers move RCX to RDX before the tail jump.
 * PROPERTY: RDX=entity, R9=descriptor base, entry RSP+0x28=count pointer,
 * entry RSP+0x30=list pointer. Appends four 16-byte descriptors; the pinned
 * caller has 128 slots and admission requires count<=124. RESET: RCX=S,
 * RDX=entity. Its original wrapper performs further global resets outside
 * this helper image. Initialization follows map ordinals after classification;
 * property allocation failure may leave a partial secondary record.
 * DIRECT_DENSE/APPEND/REMOVE use entity RDX; DIRECT_DENSE uses R8=flags.
 * DIRECT_REMOVE retains EAX=[entity+0x10]. RESET_CONTROL retains DL and writes
 * S[1]; DL==0 also clears dense primary offsets 0..43 and 48..79. RESET_DENSE
 * writes offsets 0..43 and sets S[0]=1. Batch admission checks every active
 * identity through bounded original hash probing before any writes.
 * These images must not be activated on their own. */
EpPropertyResult ep_component33_image_build(uint32_t kind,const EpComponent33Addresses*,EpComponent33Image*);
#ifdef __cplusplus
}
#endif
#endif
