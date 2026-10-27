#ifndef EP_PLAYER_JOIN_RESULT_H
#define EP_PLAYER_JOIN_RESULT_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum EpPlayerJoinStatus {
    EP_JOIN_OK,EP_JOIN_CAPACITY,EP_JOIN_RESOURCE,EP_JOIN_RECORD_BUSY,EP_JOIN_MAP_FULL,
    EP_JOIN_OWNER_FULL,EP_JOIN_CLEANED,EP_JOIN_BINDING,EP_JOIN_DUPLICATE,
    EP_JOIN_LAYOUT,EP_JOIN_READ_LIMIT,EP_JOIN_POSTCONDITION,EP_JOIN_FAULT,
    EP_JOIN_NOT_ATTEMPTED
};
enum EpPlayerJoinOutcome {
    EP_JOIN_OUTCOME_NOT_ATTEMPTED,EP_JOIN_OUTCOME_CREATED,
    EP_JOIN_OUTCOME_RECOVERY_REQUIRED,EP_JOIN_OUTCOME_UNSAFE
};
enum {EP_JOIN_RESULT_ENCLOSING_SCOPE=1};
typedef struct EpPlayerJoinResult {
    uint64_t owner,epoch,route,sequence,client,request_peer;
    uint32_t status,owner_status,read_bytes,outcome,flags;
} EpPlayerJoinResult;
/* One notice after an owned NEW join returns (including skipped creation), or
 * an owned join cannot finish safely. Successful OLD calls do not emit it.
 * The value is stack-owned: copy it before returning. client/request_peer are
 * original opaque arguments, NOT authenticated player identity or ownership.
 * epoch is zero if no owner view was acquired. owner_status uses
 * EpRosterOwnerResult. A created resource is not full multiplayer readiness.
 *
 * RECOVERY_REQUIRED means creation was rejected before mutation or its normal
 * failure was cleaned up. Earlier ClientSynchronizer/network changes were NOT
 * rolled back: NEVER replay the original join from this notice. A native
 * session recovery/rejoin path must establish a fresh attempt first. UNSAFE
 * never permits an automatic retry. NOT_ATTEMPTED is not successful creation.
 *
 * Runs before the existing owner failure policy. No throw, blocking, engine
 * calls, owner reentry or retaining pointers; queue a value for the upper layer.
 * ENCLOSING_SCOPE means the enclosing native call is still in flight: even
 * CREATED remains provisional until that scope and session are revalidated.
 * Consumers must discard notices for replaced owners/session epochs.
 * NEW attempts receive an increasing sequence under the owner lock, scoped to
 * the opaque route value. Delivery can be reordered after the lock is released;
 * do not replace a newer notice with an older sequence. Zero means execution
 * was blocked before a NEW attempt was selected, not an older completed join.
 */
typedef void (*EpPlayerJoinNotice)(void*,const EpPlayerJoinResult*);
#ifdef __cplusplus
}
#endif
#endif
