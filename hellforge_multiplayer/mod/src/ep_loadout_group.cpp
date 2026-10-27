#include "ep_loadout_group.h"
#include <limits.h>
#include <string.h>
namespace {
using SealGs=int (*)(HfMod*,uint64_t,const void*,uint32_t,uint32_t,const EpSessionGsCheck*);
struct PreparedImage {
    uint8_t* data;
    uint32_t bytes,code_bytes,table,count,handler,gs_index;
    SealGs seal_gs;
};
template<class T> PreparedImage image_view(T& image)
{return {image.data,image.bytes,image.code_bytes,image.table_offset,(image.bytes-image.table_offset)/12,0,0,nullptr};}
template<class T> PreparedImage image_view(T& image,SealGs seal,uint32_t index=1)
{
    PreparedImage view=image_view(image);view.handler=image.handler_offset;view.gs_index=index;view.seal_gs=seal;return view;
}
struct EpLoadoutLocalLink {uint32_t source,target,offset,next,rva,entry;};
#include "ep_loadout_links_template.h"
bool function_entry(const PreparedImage& image,uint32_t entry)
{
    for (uint32_t i=0;i<image.count;i++) {
        uint32_t begin=0;memcpy(&begin,image.data+image.table+i*12,4);
        if (begin==entry) return true;
    }
    return false;
}
EpPropertyResult link_images(PreparedImage* images,const uint64_t* bases,uint64_t game,
                             uint32_t old_update,uint32_t update)
{
    for (const auto& link:ep_loadout_local_links) {
        if (link.source>=EP_LOADOUT_GROUP_CODE_COUNT || link.target>=EP_LOADOUT_GROUP_CODE_COUNT) return EP_PROPERTY_ARGUMENT;
        auto& from=images[link.source];const auto& to=images[link.target];
        if (!link.offset || link.next!=link.offset+4 || link.next>from.code_bytes || from.data[link.offset-1]!=0xe8 ||
            link.entry>=to.code_bytes || !function_entry(to,link.entry)) return EP_PROPERTY_ARGUMENT;
        int32_t old=0;memcpy(&old,from.data+link.offset,4);
        if ((int64_t)bases[link.source]+link.next+old!=(int64_t)game+link.rva) return EP_PROPERTY_ARGUMENT;
        int64_t delta=(int64_t)bases[link.target]+link.entry-((int64_t)bases[link.source]+link.next);
        if (delta<INT32_MIN || delta>INT32_MAX) return EP_PROPERTY_REL32;
        int32_t relative=(int32_t)delta;memcpy(from.data+link.offset,&relative,4);
    }
    // Keep the legacy tick address callable, but use ONE state-update body.
    // A frame-free tail jump fits inside its existing leaf guard/unwind row.
    auto& tick=images[14];const auto& canonical=images[21];
    if (old_update>tick.code_bytes || tick.code_bytes-old_update<5 ||
        !function_entry(tick,old_update) || !function_entry(canonical,update) ||
        tick.data[old_update]!=0x49 || tick.data[old_update+1]!=0xbb) return EP_PROPERTY_ARGUMENT;
    uint32_t guard_end=0,unwind=0;
    memcpy(&guard_end,tick.data+tick.table+4,4);memcpy(&unwind,tick.data+tick.table+8,4);
    const uint8_t leaf[]={1,0,0,0};
    if (old_update || guard_end<5 || unwind>tick.table || tick.table-unwind<4 ||
        memcmp(tick.data+unwind,leaf,sizeof(leaf))) return EP_PROPERTY_ARGUMENT;
    int64_t delta=(int64_t)bases[21]+update-((int64_t)bases[14]+old_update+5);
    if (delta<INT32_MIN || delta>INT32_MAX) return EP_PROPERTY_REL32;
    int32_t relative=(int32_t)delta;tick.data[old_update]=0xe9;memcpy(tick.data+old_update+1,&relative,4);
    return EP_PROPERTY_OK;
}
}
EpPropertyResult ep_loadout_group_discard(HfMod* mod,EpLoadoutGroup* out)
{
    if (!mod || !out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutGroup remaining={};
    for (unsigned i=EP_LOADOUT_GROUP_CODE_COUNT;i--;) if (out->code[i].handle && !ep_session_code_discard(mod,out->code[i].handle)) {
        remaining.code[i]=out->code[i];remaining.state=EP_LOADOUT_GROUP_CLEANUP;
    }
    *out=remaining;return remaining.state ? EP_PROPERTY_CLEANUP : EP_PROPERTY_OK;
}
static EpPropertyResult prepare(const HfApi* api,HfMod* mod,const EpLoadoutGroupAddresses* input,const EpPlayerJoinPeers* peers,EpLoadoutGroup* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutGroupAddresses a={};if (input) a=*input;*out={};
    if (!input || !mod) return EP_PROPERTY_ARGUMENT;
    EpLoadoutAddresses l=a.setup.common.lifecycle;l.code=a.lifecycle_code;
    EpLoadoutConsumerAddresses c=a.setup.common;c.lifecycle.code=a.consumers_code;
    EpLoadoutInteractionAddresses interaction_binding={a.setup.common,a.refresh_code};interaction_binding.common.lifecycle.code=a.interactions_code;
    EpLoadoutRefreshAddresses refresh_binding={a.setup.common,0};refresh_binding.common.lifecycle.code=a.refresh_code;
    EpLoadoutRecordsAddresses records_binding={a.setup.common,a.record_source};
    EpLoadoutConsumerAddresses mode_binding=a.setup.common;mode_binding.lifecycle.code=a.mode_code;
    EpLoadoutConsumerAddresses life_binding=a.setup.common;life_binding.lifecycle.code=l.code;
    EpPropertyResult result=ep_loadout_consumers_validate(&life_binding);if (result!=EP_PROPERTY_OK) return result;
    const uint64_t bases[]={l.code,c.lifecycle.code,a.setup.common.lifecycle.code,a.interactions_code,a.refresh_code,a.records_code,a.frame_code,a.mode_code,a.control_code,a.state_code,a.prompt_code,a.countdown_code,a.resources_code,a.resource_owner_code,a.resource_tick_code,a.resource_events_code,a.resource_ownership_code,a.resource_sync_code,a.resource_signals_code,a.resource_actions_code,a.resource_main_code,a.resource_update_code};
    const uint32_t spans[]={8192,8192,8192,8192,8192,8192,EP_LOADOUT_FRAME_BYTES,EP_LOADOUT_MODE_BYTES,EP_LOADOUT_CONTROL_BYTES,EP_LOADOUT_STATE_BYTES,EP_LOADOUT_PROMPT_BYTES,EP_LOADOUT_COUNTDOWN_BYTES,EP_LOADOUT_RESOURCES_BYTES,EP_LOADOUT_RESOURCE_OWNER_BYTES,EP_LOADOUT_RESOURCE_TICK_BYTES,EP_LOADOUT_RESOURCE_EVENTS_BYTES,EP_LOADOUT_RESOURCE_OWNERSHIP_BYTES,EP_LOADOUT_RESOURCE_SYNC_BYTES,EP_LOADOUT_RESOURCE_SIGNALS_BYTES,EP_LOADOUT_RESOURCE_ACTIONS_BYTES,EP_LOADOUT_RESOURCE_MAIN_BYTES,EP_LOADOUT_RESOURCE_UPDATE_BYTES};
    EpLoadoutCountdownAddresses countdown_binding={records_binding,a.countdown_source,0,0};
    EpLoadoutResourceOwnerAddresses owner_binding={records_binding,a.countdown_source,a.resource_owner_source};
    for (unsigned i=0;i<EP_LOADOUT_GROUP_CODE_COUNT;i++) {
        if (!bases[i] || bases[i]>=(UINT64_C(1)<<47)-spans[i]) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (bases[i]<bases[j]+spans[j] && bases[j]<bases[i]+spans[i]) return EP_PROPERTY_OVERLAP;
        records_binding.common.lifecycle.code=bases[i];
        countdown_binding.records=records_binding;
        owner_binding.records=records_binding;
        result=ep_loadout_resource_owner_validate_span(&owner_binding,spans[i]);if (result!=EP_PROPERTY_OK) return result;
    }
    if (peers) {
        if (peers->capacity!=l.capacity) return EP_PROPERTY_ARGUMENT;
        for (unsigned i=0;i<EP_LOADOUT_GROUP_CODE_COUNT;i++) {
            result=ep_loadout_consumers_peer_span(peers,bases[i],spans[i]);if (result!=EP_PROPERTY_OK) return result;
        }
        const auto& r=a.record_source;const auto& o=a.resource_owner_source;const uint32_t n=l.capacity;
        const uint64_t extra[][2]={{r.manager,0xb7c},{r.actors,n*8},{r.equipment,n*0x40},{r.status,n*0x44},
            {a.countdown_source.manager,0x13000},{a.countdown_source.resources,n*0x4c},
            {o.owner,0x118},{o.objects,n*8},{o.phases,n*12},{o.rows,n*20},{o.states,n*4}};
        for (const auto& range:extra) {
            result=ep_loadout_consumers_peer_span(peers,range[0],(uint32_t)range[1]);if (result!=EP_PROPERTY_OK) return result;
        }
    }
    records_binding.common.lifecycle.code=a.records_code;
    EpLoadoutImage life={};EpLoadoutConsumerImage consumers={};EpLoadoutSetupImage setup={};
    EpLoadoutInteractionImage interactions={};
    EpLoadoutRefreshImage refresh={};
    EpLoadoutRecordsImage records={};
    EpLoadoutFrameImage frame={};
    EpLoadoutModeImage mode={};
    EpLoadoutControlImage control={};
    EpLoadoutStateImage state={};EpLoadoutPromptImage prompt={};EpLoadoutCountdownImage countdown={};EpLoadoutResourcesImage resources={};EpLoadoutResourceOwnerImage resource_owner={};EpLoadoutResourceTickImage resource_tick={};EpLoadoutResourceEventsImage resource_events={};EpLoadoutResourceOwnershipImage resource_ownership={};EpLoadoutResourceSyncImage resource_sync={};EpLoadoutResourceSignalsImage resource_signals={};EpLoadoutResourceActionsImage resource_actions={};EpLoadoutResourceMainImage resource_main={};EpLoadoutResourceUpdateImage resource_update={};
    EpLoadoutConsumerAddresses prompt_binding=a.setup.common;prompt_binding.lifecycle.code=a.prompt_code;
    result=ep_loadout_prompt_build(&prompt_binding,&prompt);if (result!=EP_PROPERTY_OK) return result;
    result=peers ? ep_loadout_consumers_build_peers(&c,a.prompt_code+prompt.ready_flag,peers,&consumers) : ep_loadout_consumers_build(&c,a.prompt_code+prompt.ready_flag,&consumers);if (result!=EP_PROPERTY_OK) return result;
    result=ep_loadout_setup_build(&a.setup,&setup);if (result!=EP_PROPERTY_OK) return result;
    result=ep_loadout_interactions_build(&interaction_binding,&interactions);if (result!=EP_PROPERTY_OK) return result;
    refresh_binding.close_entry=a.interactions_code+interactions.close;
    result=ep_loadout_refresh_build(&refresh_binding,&refresh);if (result!=EP_PROPERTY_OK) return result;
    result=ep_loadout_records_build(&records_binding,&records);if (result!=EP_PROPERTY_OK) return result;
    result=ep_loadout_mode_build(&mode_binding,&mode);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutStateAddresses state_binding={a.setup.common,a.mode_code+mode.open,a.control_code};
    state_binding.common.lifecycle.code=a.state_code;
    result=ep_loadout_state_build(&state_binding,&state);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutControlAddresses control_binding={a.setup.common,a.mode_code+mode.mode,
        a.interactions_code+interactions.input,a.interactions_code+interactions.edit,a.state_code+state.return_screen,a.prompt_code+prompt.ready_flag,a.prompt_code+prompt.blocked_flag,a.record_source};
    control_binding.common.lifecycle.code=a.control_code;
    result=ep_loadout_control_build(&control_binding,&control);if (result!=EP_PROPERTY_OK) return result;
    // Both cycle anchors are first guarded entries, verified before prepare.
    if (control.leave || state.return_screen) return EP_PROPERTY_ARGUMENT;
    result=ep_loadout_lifecycle_build(&l,a.state_code+state.change,&life);if (result!=EP_PROPERTY_OK) return result;
    countdown_binding.records=records_binding;countdown_binding.records.common.lifecycle.code=a.countdown_code;
    countdown_binding.context_action=a.state_code+state.context_action;countdown_binding.transition=l.code+life.transition;
    result=ep_loadout_countdown_build(&countdown_binding,&countdown);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutResourcesAddresses resources_binding={records_binding,a.countdown_source,a.countdown_code+countdown.resource_lookup};
    resources_binding.records.common.lifecycle.code=a.resources_code;
    result=ep_loadout_resources_build(&resources_binding,&resources);if (result!=EP_PROPERTY_OK) return result;
    owner_binding.records.common.lifecycle.code=a.resource_owner_code;
    result=ep_loadout_resource_owner_build(&owner_binding,&resource_owner);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutResourceTickAddresses tick_binding=owner_binding;tick_binding.records.common.lifecycle.code=a.resource_tick_code;
    result=ep_loadout_resource_tick_build(&tick_binding,&resource_tick);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutResourceEventsAddresses events_binding=owner_binding;events_binding.records.common.lifecycle.code=a.resource_events_code;
    result=ep_loadout_resource_events_build(&events_binding,&resource_events);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutResourceOwnershipAddresses ownership_binding=owner_binding;ownership_binding.records.common.lifecycle.code=a.resource_ownership_code;
    result=ep_loadout_resource_ownership_build(&ownership_binding,&resource_ownership);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutResourceSyncAddresses sync_binding=owner_binding;sync_binding.records.common.lifecycle.code=a.resource_sync_code;
    result=ep_loadout_resource_sync_build(&sync_binding,&resource_sync);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutResourceSignalsAddresses signals_binding=owner_binding;signals_binding.records.common.lifecycle.code=a.resource_signals_code;
    result=ep_loadout_resource_signals_build(&signals_binding,&resource_signals);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutResourceActionsAddresses actions_binding=owner_binding;actions_binding.records.common.lifecycle.code=a.resource_actions_code;
    result=ep_loadout_resource_actions_build(&actions_binding,&resource_actions);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutResourceMainAddresses main_binding={owner_binding,a.resource_actions_code+resource_actions.reset};
    main_binding.owner.records.common.lifecycle.code=a.resource_main_code;
    result=ep_loadout_resource_main_build(&main_binding,&resource_main);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutResourceUpdateAddresses update_binding=owner_binding;update_binding.records.common.lifecycle.code=a.resource_update_code;
    result=ep_loadout_resource_update_build(&update_binding,&resource_update);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutFrameAddresses frame_binding={records_binding,a.records_code,c.lifecycle.code+consumers.update,c.lifecycle.code+consumers.lookup,a.mode_code+mode.open,a.control_code+control.leave,a.state_code+state.change,a.state_code+state.return_screen,a.prompt_code+prompt.update,a.prompt_code+prompt.ready_flag,a.prompt_code+prompt.blocked_flag,a.countdown_code+countdown.update};
    frame_binding.records.common.lifecycle.code=a.frame_code;
    result=ep_loadout_frame_build(&frame_binding,&frame);if (result!=EP_PROPERTY_OK) return result;
    PreparedImage images[]={image_view(life,ep_session_code_seal_loadout_transition,7),image_view(consumers),
        image_view(setup,ep_session_code_seal_loadout_setup),image_view(interactions),
        image_view(refresh,ep_session_code_seal_loadout_refresh),image_view(records,ep_session_code_seal_loadout_records),
        image_view(frame,ep_session_code_seal_loadout_frame),image_view(mode,ep_session_code_seal_loadout_mode),
        image_view(control),image_view(state,ep_session_code_seal_loadout_state,5),image_view(prompt),image_view(countdown),
        image_view(resources),image_view(resource_owner),image_view(resource_tick),image_view(resource_events),
        image_view(resource_ownership),image_view(resource_sync),image_view(resource_signals),image_view(resource_actions),
        image_view(resource_main,ep_session_code_seal_loadout_resource_main),image_view(resource_update)};
    static_assert(sizeof(images)/sizeof(*images)==EP_LOADOUT_GROUP_CODE_COUNT,"Complete group binding");
    result=link_images(images,bases,l.game,resource_tick.update,resource_update.update);
    if (result!=EP_PROPERTY_OK) return result;
    // Seal the linked images themselves. Rebuilding them in per-image prepare
    // would discard these links and silently restore original four-slot calls.
    EpLoadoutGroup group={};
    for (unsigned i=0;i<EP_LOADOUT_GROUP_CODE_COUNT && result==EP_PROPERTY_OK;i++) {
        const auto& image=images[i];auto& code=group.code[i];
        if (!ep_session_code_reserve(api,mod,(uintptr_t)bases[i],image.bytes,&code)) {result=EP_PROPERTY_RESERVE;break;}
        const EpSessionGsCheck gs={image.gs_index,image.handler,l.game+0x21044a0};
        int sealed=image.seal_gs ? image.seal_gs(mod,code.handle,image.data,image.bytes,image.table,&gs) :
            ep_session_code_seal_table(mod,code.handle,image.data,image.bytes,image.table,image.count);
        EpSessionCodeInfo ready={};
        if (!sealed || !ep_session_code_info(mod,code.handle,&ready)) result=EP_PROPERTY_SEAL;
        else code=ready; // retain the reserved handle if querying READY fails
    }
    if (result!=EP_PROPERTY_OK) {
        if (ep_loadout_group_discard(mod,&group)!=EP_PROPERTY_OK) {*out=group;return EP_PROPERTY_CLEANUP;}
        return result==EP_PROPERTY_CLEANUP ? EP_PROPERTY_SEAL : result;
    }
    group.constructor=group.code[0].base+life.constructor;group.release=group.code[0].base+life.release;
    group.construct_banks=group.code[0].base+life.construct_banks;
    group.attach_widgets=group.code[2].base+setup.attach_widgets;
    group.replace_widgets=group.code[2].base+setup.replace_widgets;
    group.alternate_release=group.code[0].base+life.alternate_release;group.transition=group.code[0].base+life.transition;
    group.update=group.code[1].base+consumers.update;group.lookup=group.code[1].base+consumers.lookup;
    group.action=group.code[1].base+consumers.action;group.setup=group.code[2].base;
    group.input=group.code[3].base+interactions.input;group.edit=group.code[3].base+interactions.edit;
    group.close=group.code[3].base+interactions.close;
    group.refresh=group.code[4].base;
    group.sync_records=group.code[5].base;
    group.frame=group.code[6].base+frame.frame;group.local_update=group.code[6].base+frame.local_update;
    group.mode=group.code[7].base+mode.mode;group.open_mode=group.code[7].base+mode.open;
    group.leave=group.code[8].base+control.leave;group.screen_input=group.code[8].base+control.screen_input;
    group.reset_selection=group.code[8].base+control.reset_selection;
    group.commit_selection=group.code[8].base+control.commit_selection;
    group.exit_screen=group.code[8].base+control.exit_screen;
    group.state_change=group.code[9].base+state.change;group.return_screen=group.code[9].base+state.return_screen;
    group.context_action=group.code[9].base+state.context_action;group.state_tick=group.code[9].base+state.tick;
    group.prompt=group.code[10].base+prompt.update;group.selection_prompt=group.code[10].base+prompt.selection;
    group.active_prompt=group.code[10].base+prompt.active;
    group.ready_flag=group.code[10].base+prompt.ready_flag;group.blocked_flag=group.code[10].base+prompt.blocked_flag;
    group.countdown=group.code[11].base+countdown.update;group.resource_lookup=group.code[11].base+countdown.resource_lookup;
    group.reset_timers=group.code[11].base+countdown.reset_timers;
    group.resource_write=group.code[12].base+resources.write;group.resource_ordinal=group.code[12].base+resources.ordinal;
    group.resource_transform=group.code[12].base+resources.transform;group.player_value=group.code[12].base+resources.player_value;
    group.assign_resources=group.code[12].base+resources.assign;
    group.insert_resource_object=group.code[13].base+resource_owner.insert;group.enqueue_resource_object=group.code[13].base+resource_owner.enqueue;
    group.move_resource_object=group.code[13].base+resource_owner.move;group.remove_resource_object=group.code[13].base+resource_owner.remove;
    group.resource_tick=group.code[21].base+resource_update.update;group.any_resource_ready=group.code[14].base+resource_tick.any_ready;
    group.resource_slot_ready=group.code[14].base+resource_tick.slot_ready;
    group.initialize_resource=group.code[15].base+resource_events.initialize;group.publish_resource=group.code[15].base+resource_events.publish;
    group.settle_resource_objects=group.code[16].base+resource_ownership.settle;group.promote_resource_object=group.code[16].base+resource_ownership.promote;
    group.demote_resource_object=group.code[16].base+resource_ownership.demote;
    group.emit_initial_resource_state=group.code[17].base+resource_sync.emit_initial;group.receive_resource_state=group.code[17].base+resource_sync.receive;
    group.finish_resource=group.code[18].base+resource_signals.finish;group.reset_resource_effect=group.code[18].base+resource_signals.reset_effect;
    group.activate_resource=group.code[19].base+resource_actions.activate;group.reset_resource_phases=group.code[19].base+resource_actions.reset;
    group.complete_resource=group.code[19].base+resource_actions.complete;
    group.resource_main_update=group.code[20].base+resource_main.update;group.query_resource_object=group.code[20].base+resource_main.query;
    group.update_resource_states=group.code[21].base+resource_update.update;
    group.capacity=l.capacity;group.state=EP_LOADOUT_GROUP_READY;*out=group;return EP_PROPERTY_OK;
}

EpPropertyResult ep_loadout_group_prepare(const HfApi* api,HfMod* mod,const EpLoadoutGroupAddresses* a,EpLoadoutGroup* out)
{return prepare(api,mod,a,nullptr,out);}
EpPropertyResult ep_loadout_group_prepare_peers(const HfApi* api,HfMod* mod,const EpLoadoutGroupAddresses* a,const EpPlayerJoinPeers* peers,EpLoadoutGroup* out)
{
    if (!peers) {if (out) *out={};return EP_PROPERTY_ARGUMENT;}
    const auto binding=*peers;return prepare(api,mod,a,&binding,out);
}
