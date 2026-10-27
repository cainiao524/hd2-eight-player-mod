#ifndef EP_CLIENT_DEPARTURE_H
#define EP_CLIENT_DEPARTURE_H
#include "ep_client_disconnect.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpClientDepartureAddresses {
    EpClientDisconnectAddresses client;
    uint64_t ready,ids,history,metadata,slots,ready_finish;
} EpClientDepartureAddresses;
typedef struct EpClientDepartureImage {
    uint32_t bytes,table_offset,function_count,body_offset;
    uint8_t data[4096];
} EpClientDepartureImage;
/* Whole saved 1087540, original RCX=client/RDX=host/R8=member/R9D=reason.
 * Relocates confirmed peers, readiness (+40), IDs (+18), history (+88),
 * metadata (+150), and the separate global 347CD78 object's +8 table of
 * 24-byte slots. slots points directly to its first record, not the object.
 * Counts stay at client+C8/+38/+10/+80; every loaded count is bounded.
 * Complete 32/16/8/16-byte records move together in native removal order.
 * The original fixed-capacity history search still controls metadata clearing
 * by matching ordinal AFTER counted history removal, including stale tail IDs.
 * Do not invent a different cleanup condition or remap that ordinal by member.
 * Slot removal clears only its ID. Other slot bytes, native callbacks and the
 * owner's fixed 64-entry event ring remain unchanged.
 *
 * ready MUST equal ep_client_metadata.ready / ep_host_migration.pairs;
 * ids/history MUST equal migration/update bindings, and metadata MUST equal
 * ep_client_metadata.metadata / ep_host_accept.metadata. ready_finish must be
 * the retained same-owner EP_METADATA_READY_FINISH entry, never native 1086B70.
 * This replaces the confirmed-only EP_CLIENT_PEER_REMOVE research candidate.
 * Other slot-table consumers, reset/update callers and publication still need
 * coordinated binding; this numeric candidate does not activate anything.
 * Hold one exclusive owner lease for whole calls and native callbacks. Reject
 * is nonreturning; effects before late rejection require quarantine, no replay.
 */
EpPropertyResult ep_client_departure_build(const EpClientDepartureAddresses*,EpClientDepartureImage*);
EpPropertyResult ep_client_departure_prepare(const HfApi*,HfMod*,const EpClientDepartureAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
