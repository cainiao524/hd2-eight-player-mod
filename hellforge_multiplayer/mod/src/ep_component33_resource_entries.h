#ifndef EP_COMPONENT33_RESOURCE_ENTRIES_H
#define EP_COMPONENT33_RESOURCE_ENTRIES_H
#include "ep_component33_resource_provider.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_C33_RESOURCE_ENTRY_COUNT=4, EP_C33_RESOURCE_ENTRY_GROUPS=4, EP_C33_RESOURCE_DRAIN=5, EP_C33_RESOURCE_REFRESH=6, EP_C33_RESOURCE_LEAVE=7,
    EP_C33_ENTRIES_PREPARING=1,EP_C33_ENTRIES_PREPARED,EP_C33_ENTRIES_CLEANUP_REQUIRED,EP_C33_ENTRIES_RETAINED };
#define EP_C33_RESOURCE_ENTRY_ABORT 0xe0433301u
enum { EP_C33_CORE_ENTRY_COUNT=14, EP_C33_CORE_REJECT_BASE=0x100 };
enum { EP_C33_CALLER_ENTRY_COUNT=3, EP_C33_CALLER_REJECT_BASE=0x200 };
enum { EP_C33_PUBLISH_ENTRIES=25, EP_C33_ROUTE_REJECT_BASE=0x300,
    EP_C33_PUBLISH_DISABLED=0, EP_C33_PUBLISH_PREPARED, EP_C33_PUBLISHING,
    EP_C33_PUBLISH_READY, EP_C33_COMMITTING, EP_C33_PUBLISH_ACTIVE, EP_C33_PUBLISH_FAILED };
enum { EP_C33_COMMIT_OLD, EP_C33_COMMIT_NEW, EP_C33_COMMIT_UNSAFE };
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
    uint64_t leave_target;
    EpSessionCodeInfo leave_entry,leave_body;
    uint64_t core_targets[EP_C33_CORE_ENTRY_COUNT];
    EpSessionCodeInfo core_entries[EP_C33_CORE_ENTRY_COUNT];
    uint64_t caller_targets[EP_C33_CALLER_ENTRY_COUNT];
    EpSessionCodeInfo caller_entries[EP_C33_CALLER_ENTRY_COUNT];
    EpComponent33OwnerPatch owner_window;
    EpComponent33ReaderWindow reader_windows[2];
    uint32_t publication_state,published_attempts,active,commit_outcome;
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
typedef struct EpC33LeaveEntryConfig {
    EpC33RefreshEntryConfig refresh;
    uintptr_t desired_entry,desired_body;
} EpC33LeaveEntryConfig;
typedef struct EpC33CoreEntryConfig {
    EpC33LeaveEntryConfig leave;
    uintptr_t desired_entries[EP_C33_CORE_ENTRY_COUNT];
} EpC33CoreEntryConfig;
typedef struct EpC33CallerEntryConfig {
    EpC33CoreEntryConfig core;
    uintptr_t desired_entries[EP_C33_CALLER_ENTRY_COUNT];
} EpC33CallerEntryConfig;
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
/* Includes B51DE0 (object in RCX, flags in EDX) and its entire registry walk
 * with the eleven refresh/lifecycle/resource images. The tag-7C path calls
 * this group's exact managed DEFER. Other component dispatch, flags, engine
 * calls and switch tables remain intact. The shared owner covers all arms;
 * mark one outer write revision because other tags can write directly.
 * No rollback or retry after partial effects. Reentry from any whole entry
 * or resource callback, source failure or SEH aborts and quarantines.
 * Raw registry reads and other native arms/callee internals are outside SDK
 * accounting; EACH DEFER keeps its provider 64 KiB budget. Registry lifetime,
 * other callbacks' semantics/lock ordering, coordinated publication and all
 * remaining writers still require integration. Replace the whole B51DE0
 * entry and omit its old interior getter/release windows. Preparation does
 * not read game state or install hooks. Earlier APIs leave leave fields zero. */
int ep_component33_resource_entries_prepare_leave(const HfApi*,HfMod*,const EpC33ResourceEntryBindings*,const EpC33LeaveEntryConfig*,EpC33ResourceEntriesInfo*);
/* Includes owned whole-call bridges for the retained family's fourteen core
 * images, indexed by EP_COMPONENT33_* - 1. The original register/return ABI
 * is forwarded, including PROPERTY's two stack arguments. Body addresses
 * come exclusively from the SAME storage family; no arbitrary body binding.
 * Shared ownership precedes native reads/writes; one outer revision covers
 * nested writes. Different core kinds may nest under the same owner (up to
 * the existing owner depth bound). Same-kind cycles, other group entry and
 * resource-service callback entry are refused before body execution.
 * Uses rejection kind EP_C33_CORE_REJECT_BASE + EP_COMPONENT33_*; rejection
 * cannot return. Native guard/SEH faults quarantine the owner and restore TLS.
 * The extra fourteen bridges retain/cancel with all thirteen lifecycle images;
 * the already retained storage family supplies their permanent bodies.
 * Targets are original helper entries, not callback-table slots: classification
 * and PROPERTY wrappers keep their existing argument transforms. RESET's two
 * whole wrappers still use the controlled reset route. Do not publish legacy
 * family bodies/interior resource windows alongside these replacements.
 * The owner inline promotion and two creation/reset reader windows, outside
 * writers/callback lifetimes, complete exclusion during publication and actual
 * installation remain integration requirements. No SDK reads or hooks occur
 * during preparation. Core native loads have no SDK sampling/read budget. */
int ep_component33_resource_entries_prepare_core(const HfApi*,HfMod*,const EpC33ResourceEntryBindings*,const EpC33CoreEntryConfig*,EpC33ResourceEntriesInfo*);
/* Adds complete original caller scopes: 576CF0 (RCX=owning object with S at
 * +3CA0), ADDC10 (RCX=creation object), B62210 (batch creation). The saved
 * callers take no stack arguments. Forward registers/returns through the same
 * Win64 frame, invoking the current SDK next pointer of this exact entry.
 * No supplied alternate body, no copied 42 KiB owner, no guessed GS metadata.
 * The SDK retains the original caller's frame/unwind and other chain nodes.
 * Missing next, foreign S, wrong owner object, cycles or SEH abort/quarantine.
 * Check S's global binding under the owner BEFORE any original caller effect.
 * The entire call marks one outer write revision. Same-group distinct callers
 * may nest; core/lifecycle calls made by them share this owner. Entry FROM a
 * core/lifecycle/resource callback is refused. Original partial effects are
 * not rolled back and engine lock ordering/callback semantics remain unproved.
 *
 * The three bridges retain/cancel with the other 27 images. The three window
 * plans come only from the same retained family: inline promotion and the two
 * creation pointer/reset windows. Their direct bodies run inside these caller
 * scopes, not independently. Publishing integration MUST exclude/drain every
 * old/new caller while installing all replacements, windows and migrated data;
 * installing only these scopes is not an activation protocol. The SDK next
 * slots must be populated before any entry is exposed to execution. No hooks,
 * writes/reads of game memory, or fingerprint checks occur in preparation.
 * Native loads (including the global check) have no SDK sampling budget.
 * Earlier APIs leave caller/window fields zero. Runtime remains unverified. */
int ep_component33_resource_entries_prepare_callers(const HfApi*,HfMod*,const EpC33ResourceEntryBindings*,const EpC33CallerEntryConfig*,EpC33ResourceEntriesInfo*);
/* Opt-in transactional routing for all 25 external entries. Each leaf has a
 * common OLD/NEW selector and its existing managed leaf at base+32. No extra
 * code allocations: the same thirty images retain together. UPDATE's private
 * guard moves from +32 to +64, with all body references adjusted. DRAIN stays
 * internal/unpublished. Every OLD call forwards all ABI registers/returns and
 * PROPERTY's two stack arguments through its own CURRENT SDK next pointer,
 * under the shared owner. NEW selection happens only inside the owner lock.
 * Requires api.write; prepare/retain do not call it or any SDK read/hook.
 * Legacy preparation APIs retain their original unmanaged-publication contract. */
int ep_component33_resource_entries_prepare_transaction(const HfApi*,HfMod*,const EpC33ResourceEntryBindings*,const EpC33CallerEntryConfig*,EpC33ResourceEntriesInfo*);
/* Requires retained transactional entries. Publish all 25 via SDK 13 hook_ex;
 * this is a runtime operation, never sampling. All remain OLD, including on
 * partial publication failure. No retries/detach/free after an attempted hook.
 * SDK must populate next before exposing a node (as in the pinned loader).
 * Preflight target build/ABI and external code lifetimes before this call. */
int ep_component33_resource_entries_publish(HfMod*,uint64_t,int32_t priority);
typedef struct EpC33EntryCommitGuard {
    void* context;
    /* Exclude/drain ALL affected old/new execution, including unhooked code
     * and calls that selected OLD earlier. No failure/SEH after acquiring a
     * lease without returning it. No C++ exceptions/longjmp in callbacks. */
    int (*begin)(void*,void** lease);
    /* Runs under the roster owner. Establish fresh coherent S/B/resource data,
     * ownership transfer, every related subsystem/capacity and external writer
     * exclusion. Retention alone does not prove freshness: maintain exclusion
     * since migration, or restage/validate the owned data before returning 1.
     * Do not install these three windows or execute any entry while staging.
     * The provider/guard is responsible for source identity and data rollback. */
    int (*validate)(void*,void* lease);
    /* OLD: rollback staged data before releasing exclusion. NEW: commit data
     * and release only when all other subsystem switches are coherent. UNSAFE:
     * NEVER resume affected execution; keep exclusion or terminate at a proved
     * outer boundary. Outcome is an enum, NOT a boolean. Must not throw. */
    void (*end)(void*,void* lease,uint32_t outcome);
} EpC33EntryCommitGuard;
/* Checks all three original windows before staging, then installs/verifies all
 * replacement bytes under the owner and external lease, finally flips one
 * latch. On write failure restore/verify every attempted window in reverse
 * order, including the failing write. SDK/guard SEH or failed restoration
 * quarantines the owner and reports UNSAFE; never resumes a mixed layout.
 * Ordinary validated rollback leaves OLD and allows commit retry. Callback
 * failure after activation leaves the latch NEW and owner quarantined.
 * SDK read_code requests cover only these 98 window bytes per pass; guard
 * reads/engine loads are outside that accounting. No fingerprint receipts.
 * This is not a production freeze/data provider, cross-subsystem coordinator,
 * automatic initialization, or proof of real multiplayer/UI operation. */
int ep_component33_resource_entries_commit(HfMod*,uint64_t,const EpC33EntryCommitGuard*);
enum { EP_C33_MIGRATION_NONE,EP_C33_MIGRATION_OK,EP_C33_MIGRATION_READ,
    EP_C33_MIGRATION_LAYOUT,EP_C33_MIGRATION_SNAPSHOT,EP_C33_MIGRATION_RESOURCES,
    EP_C33_MIGRATION_CHANGED,EP_C33_MIGRATION_ALLOCATION,EP_C33_MIGRATION_RESTORE,
    EP_C33_MIGRATION_ARGUMENT };
typedef struct EpC33MigrationCommitResult { uint32_t status,read_bytes,restored,reserved; } EpC33MigrationCommitResult;
/* Opt-in SDK-backed activation with fresh OLD-layout migration. begin must
 * exclude/drain all original/global writers and retain that lease through end.
 * Under the shared owner: collect S, entity identity/flags, original resource
 * descriptor/table and active queue twice; validate/migrate into owned B/arena;
 * then call validate for the OTHER subsystem/data/identity requirements. That
 * callback must not mutate B/arena or invoke resource services/managed entries.
 * Recollect sources after validate, then install the three windows and switch.
 * All SDK requests made here, including code/failures/restoration, share a
 * 64 KiB limit. Guard callbacks' own accesses are outside this budget.
 * Source reads: global S/invalid ID, S[0..2b8), up to four entity +8/+14 u32s;
 * game+3798180 descriptor (28), its 128x16 table, game+348ba88 queue count,
 * and up to 128 u64s at game+3797550. No game/module/process discovery.
 * Only owned B/arena are written during migration; S/old globals are preserved.
 * OLD restores both owned buffers BEFORE end(OLD); unsafe restoration reports
 * UNSAFE and quarantines. NEW transfers access through the common latch, not
 * resource constructors/destructors. No LOAD/DISPOSE calls or shallow-clone
 * ownership claim. Direct managed entry/service use before activation is not
 * allowed. Source identity/lifetimes, full exclusion, other capacity switches
 * and engine ABI preflight remain guard responsibilities. Repeated reads detect
 * drift; they do not establish exclusion. Runtime/game/UI remain unverified.
 * status describes migration, not overall commit success; inspect return and
 * commit_outcome too. restored bits: 1=B, 2=arena, 0=no data restoration.
 * No automatic invocation: this API requires explicit runtime authorization. */
int ep_component33_resource_entries_commit_migrated(HfMod*,uint64_t,const EpC33EntryCommitGuard*,EpC33MigrationCommitResult*);
int ep_component33_resource_entries_info(HfMod*,uint64_t,EpC33ResourceEntriesInfo*);
int ep_component33_resource_entries_retain(HfMod*,uint64_t);
int ep_component33_resource_entries_cancel(HfMod*,uint64_t);
#ifdef __cplusplus
}
#endif
#endif
