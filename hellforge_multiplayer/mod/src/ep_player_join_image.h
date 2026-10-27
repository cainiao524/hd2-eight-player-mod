#ifndef EP_PLAYER_JOIN_IMAGE_H
#define EP_PLAYER_JOIN_IMAGE_H
#include "ep_property_image.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {EP_PLAYER_JOIN_MAX_BYTES=4096};
typedef struct EpPlayerJoinImage {
    uint32_t bytes,table_offset,function_count,handler_offset,creation_target_offset;
    uint8_t data[EP_PLAYER_JOIN_MAX_BYTES];
} EpPlayerJoinImage;
/* Saved ClientSynchronizer 1085D70, register arguments only. The confirmed
 * local peer's NETWORK INDEX (not ordinal) is compared unsigned against
 * capacity 4..8; invalid sentinels retain the original fallback. All other
 * client state, resource metadata, handle/FDC140/608B60 calls and ready-helper
 * conditions remain native on success. A failed checked creation skips success
 * and ready helpers and restores all saved registers before the native exit.
 * Original six-fragment unwind/GS topology retained; the added continuation
 * chains to the fully established accepted-branch frame.
 *
 * Numeric emission only. The owned roster group supplies the whole-call scope
 * and migrates this gate with the roster. Integration must also migrate
 * component/resource/UI plus authenticated admission before NEW. Bind the
 * checked creation entry at creation_target_offset BEFORE sealing; the zero
 * placeholder is deliberately not executable. Native ready alone is not
 * evidence of a created avatar. See ep_player_join_call.h for failure scope.
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
