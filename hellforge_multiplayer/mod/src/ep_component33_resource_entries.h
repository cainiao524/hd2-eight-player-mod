#ifndef EP_COMPONENT33_RESOURCE_ENTRIES_H
#define EP_COMPONENT33_RESOURCE_ENTRIES_H
#include "ep_component33_resource_provider.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_C33_RESOURCE_ENTRY_COUNT=4, EP_C33_RESOURCE_ENTRY_GROUPS=4, EP_C33_RESOURCE_DRAIN=5, EP_C33_RESOURCE_REFRESH=6,
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
    /* ACQUIRE 6656C0, DEFER 665940, RELEASE 6659E0; DRAIN has target=0.
     * DRAIN is an internal helper, never an original hook address. */
    uint64_t targets[EP_C33_RESOURCE_ENTRY_COUNT];
    EpSessionCodeInfo code[EP_C33_RESOURCE_ENTRY_COUNT];
    uint64_t update_target;
    EpSessionCodeInfo update_entry,update_body;
    uint64_t reset_targets[2];
    EpSessionCodeInfo reset_entries[2],reset_body;
    uint64_t refresh_target;
    EpSessionCodeInfo refresh_entry,refresh_body;
} EpC33ResourceEntriesInfo;
typedef struct EpC33UpdateEntryConfig { uintptr_t desired_entry,desired_body; } EpC33UpdateEntryConfig;
typedef struct EpC33LifecycleEntryConfig {
    EpC33UpdateEntryConfig update;
    uintptr_t reset_entries[2],reset_body;
} EpC33LifecycleEntryConfig;
typedef struct EpC33RefreshEntryConfig {
    EpC33LifecycleEntryConfig lifecycle;
    uintptr_t desired_entry,desired_body;
} EpC33RefreshEntryConfig;
/* Owns four leaf Win64 argument bridges and their immutable dispatch data.
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
 * DRAIN accepts RCX=S only from an existing healthy native owner scope.
 * Use it with update_drain_build while holding writes=1 across the complete
 * UPDATE frame. It rejects out-of-scope use before SDK access or effects.
 * Cancel only before exposure; retain ALL four entries before a coordinated
 * publisher exposes any entry/window. No auto-registration or partial
 * publisher is supplied. PREPARED code must never be invoked or exposed.
 * Original callbacks, reset wrappers and all other writers still need
 * coordinated routing. Native service/callee semantics and real
 * multiplayer remain unverified. These entries are not a read-only sampler. */
int ep_component33_resource_entries_prepare(const HfApi*,HfMod*,const EpC33ResourceEntryBindings*,EpC33ResourceEntriesInfo*);
/* Includes UPDATE 664520: RCX=S, XMM1=float delta. Owns its whole-call entry
 * and routed body in the SAME lifetime transaction as all four resource
 * bridges. Requires placements allowing the saved rel32 targets. Its private
 * guard refusal bridge lies at update_entry.base+32 and cannot return.
 *
 * UPDATE holds this owner across its complete frame, marks one outer write
 * revision and rejects recursion or entry from a resource callback before
 * body execution. All SEH exits clear dispatch TLS and quarantine the owner;
 * the rejection policy runs after the owner call unwinds. Other saved engine
 * callbacks are retained, not audited or made rollback-safe by this API.
 * Uncoordinated original writers, callbacks that swallow faults, safe RESET
 * and complete publication remain obligations of the integration. No hook
 * is installed and no SDK reads occur during preparation. Legacy prepare
 * leaves update_target/update_entry/update_body zero. */
int ep_component33_resource_entries_prepare_update(const HfApi*,HfMod*,const EpC33ResourceEntryBindings*,const EpC33UpdateEntryConfig*,EpC33ResourceEntriesInfo*);
/* Adds both global RESET wrappers to the UPDATE/resource lifetime set:
 * 51ADE0 takes entity in RCX; 664210 takes entity in RDX (RCX ignored).
 * Both run the bound eight-slot per-entity 664430 body under the same owner,
 * then reset ONLY an idle resource arena. Live references or queued keys
 * preserve all arena bytes, allowing another player's reset without dropping
 * existing claims. Idle reset keeps capacity and restores seed=2. No unload
 * or forced teardown is inferred from the original unconditional clear.
 * Validation precedes per-entity writes; body guard/SEH faults abort and
 * quarantine. Reentry from UPDATE/RESET or a resource callback is refused.
 * The three additional images are retained/cancelled with the other six.
 * Publication MUST replace both whole wrappers and omit their old interior
 * resource/reset windows; those windows would reintroduce unconditional
 * clearing. Other writers/callbacks and coordinated publication still remain.
 * Legacy prepare/prepare_update leave all reset fields zero. Preparation does
 * not access game memory; invoking retained entries is an explicit runtime
 * operation, not sampling. Original raw-pointer ABI preconditions still apply. */
int ep_component33_resource_entries_prepare_lifecycle(const HfApi*,HfMod*,const EpC33ResourceEntryBindings*,const EpC33LifecycleEntryConfig*,EpC33ResourceEntriesInfo*);
/* Includes B5E710 (RCX=object) and its registry traversal in the SAME lifetime
 * transaction as all nine lifecycle/resource images. The entire traversal
 * holds this owner; nonempty tag-7C rows call the exact owned ACQUIRE entry.
 * A foreign S is refused before SDK/service effects. No active matching row
 * causes no resource write/revision; successful acquisitions commit one outer
 * revision. Reentry, source/callback faults and capacity refusal abort the
 * traversal and quarantine; already completed prior rows are not rolled back.
 * Registry/raw-pointer lifetimes and exclusion of external registry writers
 * remain integration requirements. SDK reads within EACH acquisition retain
 * the provider's 64 KiB ceiling; original native registry loads are not SDK
 * reads. Engine function internals remain outside that counter.
 * A publisher must supersede every B5E710 interior getter/release/resource
 * window when replacing this whole entry. Other registry callers, including
 * B51DE0, are unchanged. No hook, source read, or install occurs in prepare.
 * Existing prepare APIs leave all refresh fields zero. */
int ep_component33_resource_entries_prepare_refresh(const HfApi*,HfMod*,const EpC33ResourceEntryBindings*,const EpC33RefreshEntryConfig*,EpC33ResourceEntriesInfo*);
int ep_component33_resource_entries_info(HfMod*,uint64_t,EpC33ResourceEntriesInfo*);
int ep_component33_resource_entries_retain(HfMod*,uint64_t);
int ep_component33_resource_entries_cancel(HfMod*,uint64_t);
#ifdef __cplusplus
}
#endif
#endif
