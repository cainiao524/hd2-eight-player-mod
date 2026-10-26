#ifndef EP_COMPONENT33_RESOURCES_H
#define EP_COMPONENT33_RESOURCES_H
#include "ep_component33_consumers.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_C33_RESOURCE_MIN=128, EP_C33_RESOURCE_MAX=65536, EP_C33_RESOURCE_WINDOWS=48 };
enum { EP_RESOURCE_OK=0, EP_RESOURCE_ARGUMENT, EP_RESOURCE_CAPACITY, EP_RESOURCE_STATE,
       EP_RESOURCE_OVERLAP, EP_RESOURCE_REL32 };
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
