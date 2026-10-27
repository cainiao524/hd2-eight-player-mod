#ifndef EP_LOADOUT_MODE_H
#define EP_LOADOUT_MODE_H
#include "ep_loadout_consumers.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_MODE_BYTES 8192u
typedef struct EpLoadoutModeImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,handler_offset,mode,open;
    uint8_t data[EP_LOADOUT_MODE_BYTES];
} EpLoadoutModeImage;
/* Full saved 1470D90 mode switch and 146F510 open wrapper, sharing the
 * screen, widget storage, roster and forward/inverse maps of the group.
 * Per-player notification, visibility and animation loops use capacity;
 * event argument type 4 is unchanged. Local indices require a matching
 * inverse mapping. Native GS frame, chain parents and services are retained.
 * The frame binds this open wrapper; the control image binds calls at
 * 146B2E2,146D543 and 146D866. Native notification/resource service capacities
 * and lifetimes (including 139C970), layout, source exclusion and publication
 * remain prerequisites. This only builds/prepares owned code, never calls it
 * or discovers, reads, installs, hooks or starts a game. */
EpPropertyResult ep_loadout_mode_build(const EpLoadoutConsumerAddresses*,EpLoadoutModeImage*);
/* Shared confirmed-peer variant; use the same retained bank and exclusion as
 * the roster and all sibling UI families. Group preparation binds these calls. */
EpPropertyResult ep_loadout_mode_build_peers(const EpLoadoutConsumerAddresses*,const EpPlayerJoinPeers*,EpLoadoutModeImage*);
EpPropertyResult ep_loadout_mode_prepare(const HfApi*,HfMod*,const EpLoadoutConsumerAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
