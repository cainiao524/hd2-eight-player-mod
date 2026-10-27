#ifndef EP_LOADOUT_SETUP_H
#define EP_LOADOUT_SETUP_H
#include "ep_loadout_consumers.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_SETUP_BYTES 8192u
typedef struct EpLoadoutPlacement {
    float offset_x,offset_y,anchor_x,anchor_y,pivot_x,pivot_y;
} EpLoadoutPlacement;
typedef struct EpLoadoutSetupAddresses {
    EpLoadoutConsumerAddresses common;
    EpLoadoutPlacement placements[EP_LOADOUT_LIFECYCLE_LIMIT];
} EpLoadoutSetupAddresses;
typedef struct EpLoadoutSetupImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,handler_offset,placements_offset,attach_widgets,replace_widgets;
    uint8_t data[EP_LOADOUT_SETUP_BYTES];
} EpLoadoutSetupImage;
/* Full saved 1466170 setup: original controls, hierarchy, local-user lookup,
 * state initialization and +130 GS-cookie check. Every configured player
 * widget uses the lifecycle allocation; both eight-entry maps reset to FF,
 * then the valid local network index maps to slot zero. Unknown/out-of-range
 * local index follows the native missing-local-user branch without indexing.
 * Positions are COPIED into the sealed image; finite pixel offsets and
 * normalized anchor/pivot pairs are required for each configured slot.
 * Native widget dimensions/fonts and inner equipment enums remain unchanged.
 * This does not design/verify screen fit, pagination or input navigation.
 * Do not use with original four-slot consumers or foreign lifecycle storage.
 * Caller owes constructed controls, all-source exclusion, authoritative
 * identity/ownership, source/target validation and complete publication.
 * No target discovery, game access, installation or automatic entry calls. */
EpPropertyResult ep_loadout_setup_build(const EpLoadoutSetupAddresses*,EpLoadoutSetupImage*);
/* attach_widgets is an isolated void(screen) entry for newly CONSTRUCTED,
 * unattached banks. It keeps the original player loop (including nested flags,
 * parent child-list walk and attachment), copied per-slot placements, GS frame
 * and cookie checks. It does NOT reset maps, resolve the local player, rebuild
 * nonplayer controls or run the full screen setup/refresh. It intentionally
 * updates the ready parent's hierarchy flag at screen+2820 and invokes native
 * attachment services; it is not a side-effect-free layout operation.
 *
 * The parent at screen+2820 must already be constructed/configured. Caller must
 * exclude all old/new UI calls, retain all backing and validate parent/child
 * lifetime. Remove any legacy widgets from this parent first, preserving their
 * lifetimes until no references remain. Never attach twice or to a live mixture
 * of old/new children. Construction, detachment, maps/data migration, setup,
 * refresh and publication must form one guarded activation. Faults can leave
 * partial hierarchy changes: quarantine and keep backing; no automatic retry.
 * This entry alone does not transfer old ownership or activate multiplayer. */
/* replace_widgets is void(screen), for the FIRST four-inline -> expanded-bank
 * replacement, capacity 4..8. Under the same exclusion/lifetime requirements:
 * first check both native four-entry maps (FF or mutually matching indices),
 * local network -> slot zero, and valid/FF cached record index. Also check
 * the complete ordered parent child-list (up to 4096 nodes), its
 * backpointers, membership of all four old roots, and zero sibling/parent links
 * on every new root. Failure reaches reject before any write/call/frame save.
 * Readable valid source pointers remain a caller precondition, not guaranteed
 * by those numerical/list checks. Fresh construction itself is not detected.
 *
 * After successful preflight, value-copy all four inline 9F0-byte records to
 * the fresh network-indexed bank; retain the constructor's rows 4..capacity-1.
 * Copy the four original forward/inverse map entries, including holes, and
 * initialize entries 4..7 to FF. Never reorder records by UI slot or change
 * the source records/maps or screen's local/cache fields. These are opaque
 * native value copies, NOT deep copies: every referenced descriptor/resource
 * must retain its original lifetime; external references are not retargeted.
 * Caller must already have run construct_banks under the same exclusion;
 * running it after this migration would overwrite imported record fields.
 *
 * Then calls native 144C9F0(parent,old,false) for each original inline widget,
 * recomputes the parent child flag and invokes this image's attach_widgets.
 * Other parent children stay attached. Native detach invalidates rendering
 * and clears activation flags down detached subtrees; it does not execute
 * the destructive cleanup branch. Preserve old widgets/children/resources;
 * detachment is NOT release, cloning, ownership transfer or cancellation.
 * Any fault after preflight can leave a partial data/hierarchy switch: quarantine
 * with ALL backing retained, never retry or free automatically. Repeated calls
 * after a successful replacement reject because the old roots are absent.
 * External references, pointed-to ownership, refresh, source producer hooks
 * and final publication still require coordinated activation. No automatic invocation. */
/* Cancellable READY image, including owned positions and handler thunk. */
EpPropertyResult ep_loadout_setup_prepare(const HfApi*,HfMod*,const EpLoadoutSetupAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
