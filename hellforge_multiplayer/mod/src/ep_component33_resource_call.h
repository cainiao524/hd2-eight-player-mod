#ifndef EP_COMPONENT33_RESOURCE_CALL_H
#define EP_COMPONENT33_RESOURCE_CALL_H
#include "ep_component33_storage.h"
#include "ep_roster_owner.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_C33_ACQUIRE_GROUPS=6,EP_C33_ACQUIRE_ROWS=64,EP_C33_ACQUIRE_PACKAGE_BYTES=0x3030,EP_C33_ACQUIRE_KEYS=384 };
/* Snapshot of ONE selected acquisition's complete package plus the six
 * resolved unsigned thresholds. Group tag at +800, stride 808; rows have
 * key at +0, inclusive upper/lower values at +10/+14, stride 20 (hex).
 * Values must correspond to each nonzero tag and the SAME selected entity.
 * No lookup callback, numeric address dereference or source read here. */
typedef struct EpC33AcquireSnapshot {
    uint8_t package[EP_C33_ACQUIRE_PACKAGE_BYTES];
    uint32_t thresholds[EP_C33_ACQUIRE_GROUPS];
} EpC33AcquireSnapshot;
typedef struct EpC33AcquireDemand { uint32_t count,reserved;uint64_t keys[EP_C33_ACQUIRE_KEYS]; } EpC33AcquireDemand;
int ep_component33_acquire_demand(const EpC33AcquireSnapshot*,EpC33AcquireDemand*);

enum { EP_C33_CALL_OK=0,EP_C33_CALL_ARGUMENT,EP_C33_CALL_OWNER,EP_C33_CALL_STORAGE,
       EP_C33_CALL_MEMORY,EP_C33_CALL_SNAPSHOT,EP_C33_CALL_CAPACITY,EP_C33_CALL_RESOURCE_STATE,
       EP_C33_CALL_REENTRANT,EP_C33_CALL_SOURCE_CHANGED,EP_C33_CALL_SERVICE };
typedef struct EpC33ResourceCallResult {
    uint32_t status,owner_result,demand_count,executed;
} EpC33ResourceCallResult;
/* Called under the SAME exclusive native scope as managed roster calls.
 * collect is read-only: 1 supplies a coherent complete snapshot, 2 means no
 * selected entity (no operation), 0 is a retryable unavailable snapshot.
 * It must resolve package/thresholds BEFORE release/load/service effects.
 * execute receives the exact collected snapshot/demand and admitted live
 * arena. It must consume that selection, not independently re-resolve it.
 * Returning 0 or SEH from execute quarantines the shared owner; NO rollback.
 * No C++ exceptions, longjmp, management reentry or nested resource calls.
 * All game writers/readers still require routing and real provider/service
 * binding. This API neither installs a hook nor implements those providers. */
typedef struct EpC33ResourceAcquireOps {
    void* context;
    int (*collect)(void*,const EpC33ResourceScopeView*,EpC33AcquireSnapshot*);
    int (*execute)(void*,const EpC33ResourceScopeView*,const EpC33AcquireSnapshot*,const EpC33AcquireDemand*);
} EpC33ResourceAcquireOps;
/* A retained resource storage owner is required. Scratch is internally owned
 * and freed even after a callback SEH. Capacity/snapshot refusals leave arena
 * and roster revision unchanged. Success advances one outer revision, also
 * when nested inside another managed roster call. Reentry is quarantined.
 * Binding to a roster owner is permanent; closing/recreating that owner does
 * not authorize reuse of this storage. Native game instruction bodies are
 * never invoked by this module itself; execute is an explicit integration. */
int ep_component33_resource_acquire_call(HfMod*,uint64_t storage,uint64_t roster_owner,const EpC33ResourceAcquireOps*,EpC33ResourceCallResult*);
/* Built-in executor replaces the unrestricted execute callback with the
 * captured release/acquire reference algorithm. collect supplies ONE package
 * used for both phases; release visits all nonzero keys of enabled groups,
 * acquisition uses the admitted threshold-filtered demand. No second lookup.
 * service receives DISPOSE/LOAD and a key, returns 1 only after completion.
 * It must not mutate the arena. A false return, SEH, reentry or nested owner
 * fault stops further service calls and quarantines without compensation.
 * Production collection/service ABI and original entry routing are explicit
 * missing integrations, not provided by this API or automatically installed. */
typedef struct EpC33ResourceServiceOps {
    void* context;
    int (*collect)(void*,const EpC33ResourceScopeView*,EpC33AcquireSnapshot*);
    int (*service)(void*,const EpC33ResourceScopeView*,uint32_t operation,uint64_t key);
} EpC33ResourceServiceOps;
int ep_component33_resource_acquire_services_call(HfMod*,uint64_t storage,uint64_t roster_owner,const EpC33ResourceServiceOps*,EpC33ResourceCallResult*);
/* Standalone release under the SAME owner/reentry guard and lifetime. collect
 * supplies only the package; thresholds are ignored. No acquire reservation
 * or rehash occurs. deferred=1 queues zero transitions without calling service
 * (which may be null); deferred=0 requires the usual DISPOSE callback. */
int ep_component33_resource_release_services_call(HfMod*,uint64_t storage,uint64_t roster_owner,
    uint32_t deferred,const EpC33ResourceServiceOps*,EpC33ResourceCallResult*);
#ifdef __cplusplus
}
#endif
#endif
