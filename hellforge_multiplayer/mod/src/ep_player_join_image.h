#ifndef EP_PLAYER_JOIN_IMAGE_H
#define EP_PLAYER_JOIN_IMAGE_H
#include "ep_property_image.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {EP_PLAYER_JOIN_MAX_BYTES=4096};
typedef struct EpPlayerJoinImage {
    uint32_t bytes,table_offset,function_count,handler_offset;
    uint8_t data[EP_PLAYER_JOIN_MAX_BYTES];
} EpPlayerJoinImage;
/* Saved ClientSynchronizer 1085D70, register arguments only. The confirmed
 * local peer's NETWORK INDEX (not ordinal) is compared unsigned against
 * capacity 4..8; invalid sentinels retain the original fallback. All other
 * client state, resource metadata, handle/FDC140/608B60 calls and ready-helper
 * conditions remain native. Original six-fragment unwind/GS topology retained.
 *
 * Numeric emission only. The owned roster group supplies the whole-call scope
 * and migrates this gate with the roster. Integration must also migrate
 * component/resource/UI plus authenticated admission before NEW. No preflight/rollback of the complete
 * FDC140 creation transaction is supplied here; resource failure is not
 * converted into success, nor is native ready evidence of a created avatar.
 * No game reads, writes, calls, hooks, discovery or automatic activation. */
EpPropertyResult ep_player_join_image_build(uint64_t game,uint64_t code,uint32_t capacity,EpPlayerJoinImage*);
/* Candidate OLD/NEW gate: OLD follows a live SDK next-pointer slot, NEW enters
 * this image at +32. Prefix is replaceable by an owning call bridge before
 * sealing only. control/next point to caller-owned stable cells; no dereference.
 * This alone is not an activation API. */
EpPropertyResult ep_player_join_gate_build(uint64_t game,uint64_t code,uint64_t control,uint64_t next,
    uint32_t capacity,EpPlayerJoinImage*);
#ifdef __cplusplus
}
#endif
#endif
