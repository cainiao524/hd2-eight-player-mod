#ifndef EP_HOST_REMOVAL_H
#define EP_HOST_REMOVAL_H
#include "ep_host_lifecycle.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {EP_HOST_LARGE_LOOKUP_ENTRY=0,EP_HOST_REMOVE_DATA_ENTRY=1,EP_HOST_REMOVE_DISPATCH_ENTRY=2};
typedef struct EpHostRemovalImage {
    uint32_t bytes,table_offset,function_count,entry[3];
    uint8_t data[4096];
} EpHostRemovalImage;
/* One immutable image: native 108B560 large-record lookup, 108B6B0 removal,
 * 108D190 removal dispatch. The dispatcher calls this image's own guarded
 * removal body, not the old four-record helper. All use the exact same banks.
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
 * Current 1C0h per-task records still have only physical room for five primary
 * QWORDs before +38h and twelve secondary 20h entries after +40h. Bounds checks
 * prevent crossing those fields; these are NOT negotiated protocol limits or
 * evidence that eight-recipient task payloads fit. Task/protocol expansion,
 * remaining migration/pending consumers and coordinated bank import/activation
 * are still required. This candidate does not claim complete host migration.
 *
 * Numeric build/prepare only: no game reads, data import, hooks or activation.
 * Retain this shared image before exposing any of its three entry gates.
 * Reject must not return; effects before late failure require quarantine.
 */
EpPropertyResult ep_host_removal_build(const EpHostLifecycleAddresses*,EpHostRemovalImage*);
EpPropertyResult ep_host_removal_prepare(const HfApi*,HfMod*,const EpHostLifecycleAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
