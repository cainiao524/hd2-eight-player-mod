#ifndef EP_HOST_PHASE_H
#define EP_HOST_PHASE_H
#include "ep_host_lifecycle.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {EP_HOST_ADVANCE_ENTRY=0,EP_HOST_COMPLETE_ENTRY=1};
typedef struct EpHostPhaseAddresses {
    EpHostLifecycleAddresses host;
    uint64_t task_lookup;
} EpHostPhaseAddresses;
typedef struct EpHostPhaseImage {
    uint32_t bytes,table_offset,function_count,entry[2],handler_offset;
    uint8_t data[4096];
} EpHostPhaseImage;
/* Whole saved 108D840 phase notification and 108D9F0 completion bodies, with
 * mutual calls directed to this image's guarded entries. Bind task_lookup to
 * the retained, same-owner EP_HOST_LARGE_LOOKUP_ENTRY from ep_host_removal.
 * Bind update.advance_phase / update.complete_peer to these two entries.
 *
 * All peer scans and ordered pairs use the shared expanded banks. Native
 * phase values, scalar widths and field counts remain fixed. The two resource
 * streams still use 64-item batches, their original cursor fields, flow control
 * and completion callbacks. Those resource limits are not player capacities.
 * The original fixed frames, GS cookie and chained unwind data are retained.
 * Missing peers/tasks or oversized pair counts reject, rather than continuing
 * through a null pointer or reading beyond the shared bank.
 *
 * An exclusive owner lease must cover the entire call and retained helper;
 * reject is nonreturning and partial effects require quarantine, not replay.
 * Native resource/transport services must be correctly bound before exposure.
 * Packet decoding, acceptance and coordinated activation remain separate.
 * Numeric build/prepare only: no game reads, hooks, import or activation.
 */
EpPropertyResult ep_host_phase_build(const EpHostPhaseAddresses*,EpHostPhaseImage*);
EpPropertyResult ep_host_phase_prepare(const HfApi*,HfMod*,const EpHostPhaseAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
