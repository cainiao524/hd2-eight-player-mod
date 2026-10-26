#ifndef EP_COMPONENT33_RESOURCES_H
#define EP_COMPONENT33_RESOURCES_H
#include "ep_component33_consumers.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_C33_RESOURCE_MIN=128, EP_C33_RESOURCE_MAX=65536, EP_C33_RESOURCE_WINDOWS=48 };
enum { EP_RESOURCE_OK=0, EP_RESOURCE_ARGUMENT, EP_RESOURCE_CAPACITY, EP_RESOURCE_STATE,
       EP_RESOURCE_OVERLAP, EP_RESOURCE_REL32, EP_RESOURCE_SERVICE, EP_RESOURCE_CALLBACK_STATE };
enum { EP_RESOURCE_DISPOSE=1,EP_RESOURCE_LOAD=2,EP_RESOURCE_BATCH_MAX=384 };
typedef struct EpC33ResourceBinding { uint64_t address;uint32_t capacity,reserved; } EpC33ResourceBinding;
typedef struct EpC33ResourceEntry { uint64_t key,references; } EpC33ResourceEntry;
typedef struct EpC33ResourceSnapshot {
    uint32_t seed,reserved;uint64_t queued;
    EpC33ResourceEntry entries[128];uint64_t queue[128];
} EpC33ResourceSnapshot;
typedef struct EpC33ResourceWindow { uint32_t rva,bytes;uint8_t expected[16],replacement[16]; } EpC33ResourceWindow;
typedef struct EpC33ResourcePlan { uint32_t count,reserved;EpC33ResourceWindow windows[EP_C33_RESOURCE_WINDOWS]; } EpC33ResourcePlan;
/* Layout: original-compatible 32-byte header, u64 count, 8 reserved bytes,
 * capacity u64 queue entries, then capacity 16-byte hash buckets. The address
 * is numeric: these APIs never dereference it. All supplied buffers are local
 * caller-owned storage. Admission must receive the COMPLETE prospective key
 * list (including repeated acquisitions) before any callback/mutation, under
 * whole-call exclusion. Reference-count overflow is refused. It discards
 * only zero-reference, nonqueued keys; failure preserves the live buffer.
 * No allocator, resource service, game access, publication or ownership
 * transfer occurs. Scratch is disposable and must not alias any input.
 * Allocation/lifetime, coherent snapshots, reentrancy, callback failures and
 * safe timing of original global resets remain the integrating owner's job. */
uint32_t ep_c33_resource_bytes(uint32_t capacity);
int ep_c33_resource_migrate(const EpC33ResourceBinding*,const EpC33ResourceSnapshot*,void*,uint32_t);
int ep_c33_resource_validate(const EpC33ResourceBinding*,const void*,uint32_t);
int ep_c33_resource_reserve(const EpC33ResourceBinding*,void*,uint32_t,const uint64_t*,uint32_t,void*,uint32_t);
/* Executes an ALREADY ADMITTED acquisition: immediate release of every key
 * in the first sequence, then acquisition of the second sequence. Repeated
 * keys retain their order. A queued zero-reference key is removed by swap-last
 * instead of LOAD; reaching zero during release calls DISPOSE, as flag=0 in
 * the saved acquire -> release call. Services must not mutate this arena or
 * reenter; 1 means completed, any other return stops the sequence. Scratch
 * protects against service-side arena mutations. Refusal before execution is
 * atomic; service failure after execution starts is NOT rollback. The owning
 * shared scope must quarantine failures/SEH. Numeric binding is not followed;
 * p and scratch are explicit owned buffers. No source/package lookup occurs. */
typedef int (*EpC33ResourceService)(void*,uint32_t operation,uint64_t key);
int ep_c33_resource_execute(const EpC33ResourceBinding*,void* p,uint32_t bytes,
    const uint64_t* release_keys,uint32_t release_count,const uint64_t* acquire_keys,uint32_t acquire_count,
    void* scratch,uint32_t scratch_bytes,EpC33ResourceService,void* context);
/* Standalone RELEASE: immediate (deferred=0) uses DISPOSE at each transition
 * to zero. Deferred (1) appends that key exactly once, without any service.
 * Deferred changes are staged in scratch and committed together. Existing
 * zero keys, queue order and unused bytes are preserved, not rehashed. This
 * does not drain/reset the queue or transfer embedded resource ownership. */
int ep_c33_resource_release(const EpC33ResourceBinding*,void* p,uint32_t bytes,
    const uint64_t* keys,uint32_t count,uint32_t deferred,void* scratch,uint32_t scratch_bytes,
    EpC33ResourceService,void* context);
/* Eligible UPDATE queue tail. Caller must first establish the original gate
 * and hold exclusive ownership. Calls DISPOSE in queue order, then clears
 * the ENTIRE queue storage and count, preserving all reference buckets.
 * Empty queues are untouched. Failure leaves the queue intact, including
 * already serviced keys: quarantine and never automatically retry. */
int ep_c33_resource_drain(const EpC33ResourceBinding*,void* p,uint32_t bytes,
    void* scratch,uint32_t scratch_bytes,EpC33ResourceService,void* context);
/* Explicit opt-in emission. Every consumer, its RELEASE dependency, and all
 * returned original-code windows must share the same arena. Never publish
 * just a subset. The opt-in storage/family resource APIs own/bind this arena;
 * the legacy family prepare API retains its original resource bindings. */
int ep_c33_resource_consumer(uint32_t,const EpC33ConsumerAddresses*,const EpC33ResourceBinding*,EpComponent33Image*);
int ep_c33_resource_windows(uint64_t game_base,const EpC33ResourceBinding*,uint64_t reset_address,EpC33ResourcePlan*);
#ifdef __cplusplus
}
#endif
#endif
