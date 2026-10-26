#ifndef EP_LOADOUT_STATE_H
#define EP_LOADOUT_STATE_H
#include "ep_loadout_consumers.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_STATE_BYTES 8192u
typedef struct EpLoadoutStateAddresses {
    EpLoadoutConsumerAddresses common;
    uint64_t open_mode,leave;
} EpLoadoutStateAddresses;
typedef struct EpLoadoutStateImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,handler_offset;
    uint32_t return_screen,change,context_action,tick;
    uint8_t data[EP_LOADOUT_STATE_BYTES];
} EpLoadoutStateImage;
/* Complete saved 1470740 return, 146AC60 state change, 14708D0 context
 * action and 146ABC0 timer dispatch. Return is entry zero for control links.
 * Widget loops/selected records use capacity and common storage; the selected
 * record is bounded again after each native callback. Local flags and component
 * IDs use the roster owner's B storage. State 0..6 dispatch and state 7's
 * default arm keep their captured delays; equipment category 1/3/4 remains.
 * Tick calls the bound leave entry and tail-calls the guarded state entry.
 * Context action uses the group's mode-open entry. These cycles require the
 * full group lifetime. Native resource services, external callers, state/record
 * writers, owner exclusion and publication remain prerequisites. Preparation
 * never discovers, reads, runs, installs or hooks a game. */
EpPropertyResult ep_loadout_state_build(const EpLoadoutStateAddresses*,EpLoadoutStateImage*);
EpPropertyResult ep_loadout_state_prepare(const HfApi*,HfMod*,const EpLoadoutStateAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
