#ifndef EP_LOADOUT_CONTROL_H
#define EP_LOADOUT_CONTROL_H
#include "ep_loadout_consumers.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_CONTROL_BYTES 8192u
typedef struct EpLoadoutControlAddresses {
    EpLoadoutConsumerAddresses common;
    uint64_t mode,input,edit,return_screen,ready_flag,blocked_flag;
} EpLoadoutControlAddresses;
typedef struct EpLoadoutControlImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t leave,screen_input,reset_selection;
    uint8_t data[EP_LOADOUT_CONTROL_BYTES];
} EpLoadoutControlImage;
/* Full saved 146B190 leave, 146D370 screen input, 1470700 selection reset.
 * Three mode calls bind the same group's mode, and navigation/edit calls bind
 * its interaction image. Local roster flags/components and the dense peer
 * scan and both flag queries use the same B storage as frame/update/prompt. Leave cleanup covers capacity widgets, with native
 * branch-specific unwind saves preserved. State/event/input-queue limits
 * retain their native meanings. The first widget remains the local widget.
 * The return action binds the shared state image. Engine services, source/owner
 * exclusion and external screen-input callers still require routing/review
 * before publication. Preparation never executes, installs or hooks code,
 * reads a game, or proves gameplay/service capacities. */
EpPropertyResult ep_loadout_control_build(const EpLoadoutControlAddresses*,EpLoadoutControlImage*);
EpPropertyResult ep_loadout_control_prepare(const HfApi*,HfMod*,const EpLoadoutControlAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
