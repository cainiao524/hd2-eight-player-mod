#ifndef EP_LOADOUT_GROUP_H
#define EP_LOADOUT_GROUP_H
#include "ep_loadout_setup.h"
#include "ep_loadout_interactions.h"
#include "ep_loadout_refresh.h"
#include "ep_loadout_records.h"
#include "ep_loadout_frame.h"
#include "ep_loadout_mode.h"
#include "ep_loadout_control.h"
#include "ep_loadout_state.h"
#include "ep_loadout_prompt.h"
#include "ep_loadout_countdown.h"
#include "ep_loadout_resources.h"
#include "ep_loadout_resource_owner.h"
#include "ep_loadout_resource_tick.h"
#include "ep_loadout_resource_events.h"
#include "ep_loadout_resource_ownership.h"
#include "ep_loadout_resource_sync.h"
#include "ep_loadout_resource_signals.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpLoadoutGroupAddresses {
    EpLoadoutSetupAddresses setup;
    uint64_t lifecycle_code,consumers_code,interactions_code,refresh_code;
    EpLoadoutRecordSource record_source;
    uint64_t records_code,frame_code,mode_code,control_code,state_code,prompt_code,countdown_code;
    EpLoadoutCountdownSource countdown_source;
    uint64_t resources_code,resource_owner_code;
    EpLoadoutResourceOwnerSource resource_owner_source;
    uint64_t resource_tick_code,resource_events_code,resource_ownership_code,resource_sync_code,resource_signals_code;
} EpLoadoutGroupAddresses;
enum {EP_LOADOUT_GROUP_CODE_COUNT=19};
enum {EP_LOADOUT_GROUP_EMPTY,EP_LOADOUT_GROUP_READY,EP_LOADOUT_GROUP_CLEANUP};
typedef struct EpLoadoutGroup {
    EpSessionCodeInfo code[EP_LOADOUT_GROUP_CODE_COUNT]; /* lifecycle, consumers, setup, interactions, refresh, records, frame, mode, control, state, prompt, countdown, resources, resource owner, resource tick, resource events, resource ownership, resource sync, resource signals */
    uint64_t constructor,release,alternate_release,transition,setup,update,lookup,action;
    uint64_t input,edit,close,refresh,sync_records,frame,local_update,mode,open_mode,leave,screen_input,reset_selection,state_change,return_screen,context_action,state_tick,prompt,selection_prompt,active_prompt,ready_flag,blocked_flag,countdown,resource_lookup,reset_timers;
    uint64_t resource_write,resource_ordinal,resource_transform,player_value,assign_resources;
    uint64_t insert_resource_object,enqueue_resource_object,move_resource_object,remove_resource_object;
    uint64_t resource_tick,any_resource_ready,resource_slot_ready;
    uint64_t initialize_resource,publish_resource;
    uint64_t settle_resource_objects,promote_resource_object,demote_resource_object;
    uint64_t emit_initial_resource_state,receive_resource_state,finish_resource,reset_resource_effect;
    uint32_t capacity,state;
} EpLoadoutGroup;
/* Prepare all fifty-three native entries from ONE screen/storage/map/capacity
 * binding. The nineteen desired code bases must be explicit and nonoverlapping.
 * The independent record-source banks must be disjoint from every image.
 * Input -> refresh -> close, control -> mode/navigation/edit/return, lifecycle -> state and
 * frame -> local/sync/update/lookup/mode/leave/state/return/prompt/countdown links are
 * derived from these same images. Frame, update and input flag queries also
 * bind the shared prompt image. Countdown, resource writer/ordinal/transform and assignment share the new bank.
 * Resource registration/move/removal and update/ready queries use one owner and four disjoint banks.
 * Initial state emission, reception and completion/effect callbacks share those banks.
 * Pending settlement and ownership switches also share these banks and hash ordinals.
 * Initialization and transform callbacks share those banks; names are capacity-bound.
 * Assignment uses countdown lookup; transform uses the owned ordinal/player-value entries. The frame allocation has a 16 KiB span.
 * The state timer calls control.leave and context action calls mode.open;
 * these cyclic links are prepared together and must share lifetime.
 * Only owned code allocations are made; data still belongs to the caller.
 * All images must reach READY before callable addresses are returned. Partial
 * preparation discards in reverse order; failed cleanup retains only handles
 * and exposes no callable entries. Retry group_discard for CLEANUP.
 * No initialization, original writes, retention/pinning, hooks or activation.
 * Complete routing of remaining native callees and record_source producers,
 * layout/navigation and source/owner validation are
 * prerequisites to a future common publication; READY is not that gate. */
EpPropertyResult ep_loadout_group_prepare(const HfApi*,HfMod*,const EpLoadoutGroupAddresses*,EpLoadoutGroup*);
EpPropertyResult ep_loadout_group_discard(HfMod*,EpLoadoutGroup*);
#ifdef __cplusplus
}
#endif
#endif
