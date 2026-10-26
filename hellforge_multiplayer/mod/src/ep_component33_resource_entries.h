#ifndef EP_COMPONENT33_RESOURCE_ENTRIES_H
#define EP_COMPONENT33_RESOURCE_ENTRIES_H
#include "ep_component33_resource_provider.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_C33_RESOURCE_ENTRY_COUNT=3, EP_C33_RESOURCE_ENTRY_GROUPS=4,
    EP_C33_ENTRIES_PREPARING=1,EP_C33_ENTRIES_PREPARED,EP_C33_ENTRIES_CLEANUP_REQUIRED,EP_C33_ENTRIES_RETAINED };
#define EP_C33_RESOURCE_ENTRY_ABORT 0xe0433301u
/* Must not return into the original caller after refusal/partial effects.
 * May terminate or raise a noncontinuable SEH to a proved outer boundary;
 * no C++ exceptions, longjmp or owner reentry. If it returns, dispatch raises
 * EP_C33_RESOURCE_ENTRY_ABORT instead of inventing a successful return value.
 * Context and callback code must survive the permanently retained entry set. */
typedef void (*EpC33ResourceEntryReject)(void*,uint32_t kind,const EpC33ResourceProviderResult*);
typedef struct EpC33ResourceEntryBindings {
    uint64_t storage,roster_owner;
    uintptr_t desired_code[EP_C33_RESOURCE_ENTRY_COUNT];
    EpC33ResourceEntryReject reject;void* reject_context;
} EpC33ResourceEntryBindings;
typedef struct EpC33ResourceEntriesInfo {
    uint64_t handle;uint32_t state,reserved;
    /* ACQUIRE 6656C0, DEFER 665940, RELEASE 6659E0, in this order. */
    uint64_t targets[EP_C33_RESOURCE_ENTRY_COUNT];
    EpSessionCodeInfo code[EP_C33_RESOURCE_ENTRY_COUNT];
} EpC33ResourceEntriesInfo;
/* Owns three leaf Win64 argument bridges and their immutable dispatch data.
 * ACQUIRE/DEFER: RCX=S, RDX=object. RELEASE: RCX=S, EDX=ordinal, R8B=flag;
 * only the low byte controls deferred release. The bridges tail-call a
 * compiler-unwindable dispatcher, which keeps selection/effects inside the
 * same roster owner and commits at most one outer revision. Invalid receiver,
 * unavailable source, native fault or reentry aborts and quarantines the call.
 *
 * Requires retained component/resource storage. Preparation binds it to the
 * nonreusable roster owner, allocates/seals code and copies SDK callbacks.
 * No SDK reads, engine functions, hooks or installation are performed during
 * preparation. That permanent storage binding survives cancellation/failure.
 * Cancel only before exposure; retain ALL three entries before a coordinated
 * publisher exposes any entry/window. No auto-registration or partial
 * publisher is supplied. PREPARED code must never be invoked or exposed.
 * UPDATE, its internal calls, original reset wrappers and all other writers
 * still need coordinated routing. Native service/callee semantics and real
 * multiplayer remain unverified. These entries are not a read-only sampler. */
int ep_component33_resource_entries_prepare(const HfApi*,HfMod*,const EpC33ResourceEntryBindings*,EpC33ResourceEntriesInfo*);
int ep_component33_resource_entries_info(HfMod*,uint64_t,EpC33ResourceEntriesInfo*);
int ep_component33_resource_entries_retain(HfMod*,uint64_t);
int ep_component33_resource_entries_cancel(HfMod*,uint64_t);
#ifdef __cplusplus
}
#endif
#endif
