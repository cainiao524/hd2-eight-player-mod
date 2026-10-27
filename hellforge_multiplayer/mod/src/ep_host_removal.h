#ifndef EP_HOST_REMOVAL_H
#define EP_HOST_REMOVAL_H
#include "ep_host_lifecycle.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {EP_HOST_LARGE_LOOKUP_ENTRY=0,EP_HOST_REMOVE_DATA_ENTRY=1,EP_HOST_REMOVE_DISPATCH_ENTRY=2,
      EP_HOST_TASK_ADD_ENTRY=3,EP_HOST_TASK_CONNECT_ENTRY=4,EP_HOST_TASK_ACK_ENTRY=5};
typedef struct EpHostRemovalImage {
    uint32_t bytes,table_offset,function_count,entry[6];
    uint8_t data[4096];
} EpHostRemovalImage;
/* One immutable image: native 108B560 task lookup, 108B6B0 removal,
 * 108D190 removal dispatch, 108A350 member registration, 108D3B0 pair creation
 * and 108D5E0 pair acknowledgment. Calls between these bodies stay inside this
 * image's guarded entries. All use the exact same banks and task layout.
 * Host+0/metadata stay in place. Whole calls and returned pointers require
 * the same owner lease and lifetime as the other host lifecycle candidates.
 *
 * Every configured large record is searched/cleaned. Native swap-removal of
 * all duplicate IDs and complete 32-byte secondary entries is preserved; a
 * record with no primary IDs is cleared in full. Host ID/state/timer and the
 * flag selected by network index are cleared using the native semantics.
 * Both dispatch loops cover capacity; serialized reason size remains FOUR
 * bytes, independently of loop count. Native callbacks/services are retained.
 *
 * Private task records hold capacity primary IDs and capacity*(capacity-1)
 * ordered pairs, preserving full 32-byte entries and acknowledgment sequence.
 * Duplicate pair updates work even when the pair list is full. New members or
 * pairs reject before their out-of-bounds store; empty-record clear writes to
 * the actual bank, never through the old small stack temporary. Other pending/
 * protocol consumers and coordinated import/activation still need conversion.
 *
 * Numeric build/prepare only: no game reads, data import, hooks or activation.
 * Retain this shared image before exposing any of its six entry gates.
 * Reject must not return; effects before late failure require quarantine.
 */
EpPropertyResult ep_host_removal_build(const EpHostLifecycleAddresses*,EpHostRemovalImage*);
EpPropertyResult ep_host_removal_prepare(const HfApi*,HfMod*,const EpHostLifecycleAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
