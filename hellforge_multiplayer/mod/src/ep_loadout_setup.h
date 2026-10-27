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
    uint32_t bytes,code_bytes,unwind_offset,table_offset,handler_offset,placements_offset,attach_widgets;
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
 * parent ancestry walk and attachment), copied per-slot placements, GS frame
 * and cookie checks. It does NOT reset maps, resolve the local player, rebuild
 * nonplayer controls or run the full screen setup/refresh. It intentionally
 * updates the ready parent's hierarchy flag at screen+2820 and invokes native
 * attachment services; it is not a side-effect-free layout operation.
 *
 * The parent at screen+2820 must already be constructed/configured. Caller must
 * exclude all old/new UI calls, retain all backing and validate parent/ancestor
 * lifetime. Remove any legacy widgets from this parent first, preserving their
 * lifetimes until no references remain. Never attach twice or to a live mixture
 * of old/new children. Construction, detachment, maps/data migration, setup,
 * refresh and publication must form one guarded activation. Faults can leave
 * partial hierarchy changes: quarantine and keep backing; no automatic retry.
 * This entry alone does not transfer old ownership or activate multiplayer. */
/* Cancellable READY image, including owned positions and handler thunk. */
EpPropertyResult ep_loadout_setup_prepare(const HfApi*,HfMod*,const EpLoadoutSetupAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
