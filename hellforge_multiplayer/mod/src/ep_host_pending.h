#ifndef EP_HOST_PENDING_H
#define EP_HOST_PENDING_H
#include "ep_host_lifecycle.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpHostPendingAddresses {
    EpHostLifecycleAddresses host;
    uint64_t remove_data;
} EpHostPendingAddresses;
typedef struct EpHostPendingImage {
    uint32_t bytes,table_offset,function_count,handler_offset,body_offset;
    uint8_t data[8192];
} EpHostPendingImage;
/* Saved native 108BC70, with its original calling convention, six unwind
 * fragments, policy checks, error replies and GS cookie. Host/confirmed/flag/
 * pending references use the same owner's external banks. Native slot zero
 * remains reserved for the host; all later slots participate in admission.
 * The existing 8-entry invitation tables and 32-entry key ring are unrelated
 * to player capacity and keep their original format and bounds.
 *
 * R9 must point to an immutable DECODED count/reserved/IDs span of at least
 * 8+8*capacity bytes. Count is bounded before any member read. The transport's
 * decoder and shared activation still need conversion; never call
 * this gate on a four-member decoder allocation containing a larger count.
 * Stack arguments and protocol field widths retain their original ABI.
 *
 * Retain remove_data from EP_HOST_REMOVE_DATA_ENTRY of the same owner's
 * shared task image before exposing this entry. All banks, request storage
 * and helper images require a whole-call exclusive owner lease. Queue-full
 * preflight rejects before peer edits; impossible late failure quarantines
 * the owner through a nonreturning reject target. No partial replay.
 * Numeric preparation only: no game reads, import, hooks or activation.
 */
EpPropertyResult ep_host_pending_build(const EpHostPendingAddresses*,EpHostPendingImage*);
EpPropertyResult ep_host_pending_prepare(const HfApi*,HfMod*,const EpHostPendingAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
