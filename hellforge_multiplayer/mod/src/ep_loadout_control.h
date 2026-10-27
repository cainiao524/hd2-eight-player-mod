#ifndef EP_LOADOUT_CONTROL_H
#define EP_LOADOUT_CONTROL_H
#include "ep_loadout_records.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_CONTROL_BYTES 8192u
typedef struct EpLoadoutControlAddresses {
    EpLoadoutConsumerAddresses common;
    uint64_t mode,input,edit,return_screen,ready_flag,blocked_flag;
    EpLoadoutRecordSource source;
} EpLoadoutControlAddresses;
typedef struct EpLoadoutControlImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t leave,screen_input,reset_selection,commit_selection,exit_screen;
    uint8_t data[EP_LOADOUT_CONTROL_BYTES];
} EpLoadoutControlImage;
/* Full saved 146B190 leave, 146D370 screen input, 1470700 selection reset.
 * Also 1467790 selection commit and the complete 1467B90 screen exit. Selected
 * records are network-indexed with bounds checks; local widgets stay in slot
 * zero, equipment rows use the source hash ordinal, and roster flag writes use
 * B's dense property array. Never interchange these three index domains.
 * Exit -> selection commit stays within this image. The common group links
 * its timer reset, phase reset and resource cleanup to their owned entries.
 * Actor lists/timer rows and event/replication services retain the native ABI
 * and require external backing/lifetime validation, just as countdown does.
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
