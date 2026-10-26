#ifndef EP_COMPONENT33_CONSUMERS_H
#define EP_COMPONENT33_CONSUMERS_H
#include "ep_component33_image.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_C33_UPDATE=1, EP_C33_ACQUIRE=2, EP_C33_DEFER=3, EP_C33_RELEASE=4 };
typedef struct EpC33ConsumerAddresses {
    uint64_t game_base,code_address,component_address,storage_address,release_address,reject_address;
} EpC33ConsumerAddresses;
/* Numeric emission only. RCX=S for every entry. UPDATE retains XMM1;
 * ACQUIRE/DEFER retain the entity-owner argument RDX. RELEASE takes ordinal
 * EDX and the deferred-disposal flag R8B. Internal calls bind to this family's
 * RELEASE image. Full saved bodies, original external callbacks and reference
 * table/queue behavior are retained; only S array addresses are redirected.
 * All active IDs are checked by bounded original map probing before writes.
 * Caller owns complete call exclusion, readable objects and all resource
 * lifetimes. The original resource hash table and 128-entry deferred queue
 * are NOT enlarged or made transactional here. Queue admission, stale/null
 * resource returns, remaining inline consumers, reentrancy and publication
 * remain blockers. A callback failure can leave original partial effects.
 * Refusal must not return into a containing frame. Never activate alone. */
EpPropertyResult ep_component33_consumer_build(uint32_t,const EpC33ConsumerAddresses*,EpComponent33Image*);
uint32_t ep_component33_consumer_bytes(uint32_t);
#ifdef __cplusplus
}
#endif
#endif
