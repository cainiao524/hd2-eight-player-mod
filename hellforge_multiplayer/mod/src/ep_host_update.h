#ifndef EP_HOST_UPDATE_H
#define EP_HOST_UPDATE_H
#include "ep_host_lifecycle.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpHostUpdateAddresses {
    EpHostLifecycleAddresses host;
    uint64_t ids,remove_data,remove_dispatch,begin_peer,accept_peer,complete_peer,advance_phase;
} EpHostUpdateAddresses;
typedef struct EpHostUpdateImage {
    uint32_t bytes,table_offset,function_count,handler_offset,body_offset;
    uint8_t data[8192];
} EpHostUpdateImage;
/* Complete saved 108A440 host update candidate. Peers, ordered task pairs,
 * pending rows and client IDs use the same owner's expanded banks. Metadata,
 * 8-entry invitation tables, protocol field widths and native services retain
 * their semantics. Pending transfer/serialization uses all bounded member IDs;
 * an exhausted task bank defers the request without sending success/clearing it.
 *
 * Per-call scratch grows the fixed allocation from 358h to 558h. RBP remains
 * RSP+100h, old locals/nonvolatile saves stay fixed relative to RSP, new count/
 * ID and timer buffers occupy +3A0..+41F. Cookie moves to +538h, above them;
 * the exact unwind/GS profile describes this changed frame (not the old one).
 * Native descriptor allocator size/alignment and top-level field counts stay
 * unchanged; their capacities already exceed the expanded counted payloads.
 *
 * ids binds client+18's external capacity-sized QWORD bank. Helper bindings
 * retain original ABI: 108B6B0 remove_data, 108D190 remove_dispatch, 1089400
 * begin_peer, 108C760 accept_peer, 108D9F0 complete_peer, 108D840 advance_phase.
 * They MUST be retained same-owner expanded implementations before exposure,
 * not raw original four-slot functions or a generic success stub. Several
 * helper conversions and packet decoding are still required for activation.
 * Every call requires one exclusive owner lease covering helpers and banks.
 * Reject is nonreturning; late failures quarantine, with no partial replay.
 * Numeric build/prepare only: no game reads, installs, hooks or activation.
 */
EpPropertyResult ep_host_update_build(const EpHostUpdateAddresses*,EpHostUpdateImage*);
EpPropertyResult ep_host_update_prepare(const HfApi*,HfMod*,const EpHostUpdateAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
