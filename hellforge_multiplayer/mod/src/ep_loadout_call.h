#ifndef EP_LOADOUT_CALL_H
#define EP_LOADOUT_CALL_H
#include "ep_loadout_storage.h"
#include "ep_roster_call.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {EP_LOADOUT_CALL_COUNT=62};
enum {EP_LOADOUT_ROUTE_BODY,EP_LOADOUT_ROUTE_CHAIN,EP_LOADOUT_ROUTE_CREATE,EP_LOADOUT_ROUTE_PARK};
typedef struct EpLoadoutCallLayout {uint32_t rva,stack_arguments,route;} EpLoadoutCallLayout;
typedef struct EpLoadoutCallControl {volatile int32_t active,switching;} EpLoadoutCallControl;
typedef struct EpLoadoutCallContext {
    HfMod* mod;
    uint64_t owner,loadout,game,roster,storage;
    uintptr_t body,target,next_pointer;
    uint32_t rva,stack_arguments,route;
    EpLoadoutCallControl* control;
    EpRosterCallPolicy policy; /* failure's kind argument is the native RVA */
} EpLoadoutCallContext;
int ep_loadout_call_layout(uint32_t index,EpLoadoutCallLayout*);
/* Prepare one SDK-publishable leaf gate for the named saved-build entry.
 * Derives its native target and relocated body from the retained loadout owner;
 * callers cannot provide an arbitrary body/argument count. The 62-entry catalog
 * includes both resource cleanup bodies and 1465820's cleanup -> setup wrapper.
 * That scope-only wrapper follows SDK's original chain in BOTH modes, owning the
 * entire call/return through its two separately routed children. Its body field
 * anchors the retained setup entry, not an alternative wrapper implementation.
 * Activate it only with both child gates published using this same control and
 * owner; ep_loadout_routes_commit publishes the complete catalog together.
 * Preserve native cleanup conditions/order; these are not terminal generation
 * transitions. Factory 14984E0 and deallocator 14AC340 route screen kind 11
 * through the retained-screen storage protocol; other kinds follow SDK next.
 * The raw constructor itself is never hooked. 66BDA0 forwards two incoming stack slots;
 * the others use register arguments. Same native XMM/integer return frame as
 * the roster bridge, with registered Windows unwind metadata throughout.
 *
 * context and control must occupy stable caller-owned memory for every exposed
 * gate's lifetime. All gates for one loadout MUST share one control, initialized
 * {0,0}. No independent entry activation. Control writes require the same owner
 * scope and full engine exclusion: set switching before staging, initialize via
 * the joint coordinator, set active=1 only after all source/UI routing is ready,
 * then clear switching before releasing exclusion. Use atomic control writes.
 * Never revert to OLD after UI mutation. This API supplies no freeze/provider.
 *
 * OLD calls follow the live SDK next slot only while storage is RETAINED; NEW
 * requires UI_MIGRATED under the exact initializing owner. Both routes own the
 * whole native call; staged/unknown/quarantined state is refused. Different
 * nested entries inherit that scope; same-entry recursion is quarantined even
 * if an engine callback swallows failure. Failure invokes the explicit policy,
 * then raises a noncontinuable SEH if it returns; no invented success value.
 * Nonlocal C++ exceptions/longjmp and throwing/reentrant policies are unsupported.
 *
 * This prepares/seals code only: no SDK hook, game read or native game call.
 * Publish with ep_session_code_publish at context.target only after all native
 * ABI/target/lifetime/exclusion gates. All external paths, remaining direct
 * writers, lifecycle and coordinated publication still need closure. On prepare
 * failure, a nonzero code.handle means cleanup failed; keep context and retry
 * discard. Never expose, move or edit context after preparation/publication. */
int ep_loadout_call_prepare(const HfApi*,HfMod*,uint64_t loadout,uint64_t roster_owner,
    uint32_t native_rva,EpLoadoutCallControl*,const EpRosterCallPolicy*,uintptr_t desired_code,
    EpLoadoutCallContext* context,EpSessionCodeInfo* code);
#ifdef __cplusplus
}
#endif
#endif
