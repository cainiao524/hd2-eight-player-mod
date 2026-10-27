#ifndef EP_PLAYER_JOIN_IMAGE_H
#define EP_PLAYER_JOIN_IMAGE_H
#include "ep_property_image.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {EP_PLAYER_JOIN_MAX_BYTES=4096};
enum {EP_PLAYER_JOIN_PEER_GATE_BYTES=3740};
typedef struct EpPlayerJoinPeers {
    uint64_t client,bank;
    uint32_t capacity,reserved;
} EpPlayerJoinPeers;
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
/* Shared confirmed-peer bank variant. Checks the saved global owner against
 * client-162C8, bounds count and each lookup, and reads the NETWORK INDEX from
 * bank+ordinal*32+14. Does not derive the index from the ordinal. Invalid index
 * keeps the native fallback; foreign owner/excess count calls nonreturning
 * reject under the original frame. Creation/ready behavior stays unchanged.
 *
 * All writers/readers, client lifetime, migration and whole-call exclusion must
 * use the same bank/capacity before activation. In particular these numeric
 * bindings do not allocate or migrate data. Original inline data is not read
 * by this local-peer lookup. The older emitter is an inline-layout research
 * image; increasing its capacity alone never redirects confirmed-peer storage.
 */
EpPropertyResult ep_player_join_peer_gate_build(uint64_t game,uint64_t code,uint64_t control,uint64_t next,
    uint64_t reject,const EpPlayerJoinPeers*,EpPlayerJoinImage*);
#ifdef __cplusplus
}
#endif
#endif
