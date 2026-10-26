#include "ep_loadout_group.h"
EpPropertyResult ep_loadout_group_discard(HfMod* mod,EpLoadoutGroup* out)
{
    if (!mod || !out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutGroup remaining={};
    for (unsigned i=12;i--;) if (out->code[i].handle && !ep_session_code_discard(mod,out->code[i].handle)) {
        remaining.code[i]=out->code[i];remaining.state=EP_LOADOUT_GROUP_CLEANUP;
    }
    *out=remaining;return remaining.state ? EP_PROPERTY_CLEANUP : EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_group_prepare(const HfApi* api,HfMod* mod,const EpLoadoutGroupAddresses* input,EpLoadoutGroup* out)
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
    const uint64_t bases[]={l.code,c.lifecycle.code,a.setup.common.lifecycle.code,a.interactions_code,a.refresh_code,a.records_code,a.frame_code,a.mode_code,a.control_code,a.state_code,a.prompt_code,a.countdown_code};
    const uint32_t spans[]={8192,8192,8192,8192,8192,8192,EP_LOADOUT_FRAME_BYTES,EP_LOADOUT_MODE_BYTES,EP_LOADOUT_CONTROL_BYTES,EP_LOADOUT_STATE_BYTES,EP_LOADOUT_PROMPT_BYTES,EP_LOADOUT_COUNTDOWN_BYTES};
    EpLoadoutCountdownAddresses countdown_binding={records_binding,a.countdown_source,0,0};
    for (unsigned i=0;i<12;i++) {
        if (!bases[i] || bases[i]>=(UINT64_C(1)<<47)-spans[i]) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (bases[i]<bases[j]+spans[j] && bases[j]<bases[i]+spans[i]) return EP_PROPERTY_OVERLAP;
        records_binding.common.lifecycle.code=bases[i];
        countdown_binding.records=records_binding;
        result=ep_loadout_countdown_validate_span(&countdown_binding,spans[i]);if (result!=EP_PROPERTY_OK) return result;
    }
    records_binding.common.lifecycle.code=a.records_code;
    EpLoadoutImage life={};EpLoadoutConsumerImage consumers={};EpLoadoutSetupImage setup={};
    EpLoadoutInteractionImage interactions={};
    EpLoadoutRefreshImage refresh={};
    EpLoadoutRecordsImage records={};
    EpLoadoutFrameImage frame={};
    EpLoadoutModeImage mode={};
    EpLoadoutControlImage control={};
    EpLoadoutStateImage state={};EpLoadoutPromptImage prompt={};EpLoadoutCountdownImage countdown={};
    EpLoadoutConsumerAddresses prompt_binding=a.setup.common;prompt_binding.lifecycle.code=a.prompt_code;
    result=ep_loadout_prompt_build(&prompt_binding,&prompt);if (result!=EP_PROPERTY_OK) return result;
    result=ep_loadout_consumers_build(&c,a.prompt_code+prompt.ready_flag,&consumers);if (result!=EP_PROPERTY_OK) return result;
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
        a.interactions_code+interactions.input,a.interactions_code+interactions.edit,a.state_code+state.return_screen,a.prompt_code+prompt.ready_flag,a.prompt_code+prompt.blocked_flag};
    control_binding.common.lifecycle.code=a.control_code;
    result=ep_loadout_control_build(&control_binding,&control);if (result!=EP_PROPERTY_OK) return result;
    // Both cycle anchors are first guarded entries, verified before prepare.
    if (control.leave || state.return_screen) return EP_PROPERTY_ARGUMENT;
    result=ep_loadout_lifecycle_build(&l,a.state_code+state.change,&life);if (result!=EP_PROPERTY_OK) return result;
    countdown_binding.records=records_binding;countdown_binding.records.common.lifecycle.code=a.countdown_code;
    countdown_binding.context_action=a.state_code+state.context_action;countdown_binding.transition=l.code+life.transition;
    result=ep_loadout_countdown_build(&countdown_binding,&countdown);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutFrameAddresses frame_binding={records_binding,a.records_code,c.lifecycle.code+consumers.update,c.lifecycle.code+consumers.lookup,a.mode_code+mode.open,a.control_code+control.leave,a.state_code+state.change,a.state_code+state.return_screen,a.prompt_code+prompt.update,a.prompt_code+prompt.ready_flag,a.prompt_code+prompt.blocked_flag,a.countdown_code+countdown.update};
    frame_binding.records.common.lifecycle.code=a.frame_code;
    result=ep_loadout_frame_build(&frame_binding,&frame);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutGroup group={};
    result=ep_loadout_lifecycle_prepare(api,mod,&l,a.state_code+state.change,&group.code[0]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_consumers_prepare(api,mod,&c,a.prompt_code+prompt.ready_flag,&group.code[1]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_setup_prepare(api,mod,&a.setup,&group.code[2]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_interactions_prepare(api,mod,&interaction_binding,&group.code[3]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_refresh_prepare(api,mod,&refresh_binding,&group.code[4]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_records_prepare(api,mod,&records_binding,&group.code[5]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_frame_prepare(api,mod,&frame_binding,&group.code[6]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_mode_prepare(api,mod,&mode_binding,&group.code[7]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_control_prepare(api,mod,&control_binding,&group.code[8]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_state_prepare(api,mod,&state_binding,&group.code[9]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_prompt_prepare(api,mod,&prompt_binding,&group.code[10]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_countdown_prepare(api,mod,&countdown_binding,&group.code[11]);
    if (result!=EP_PROPERTY_OK) {
        if (ep_loadout_group_discard(mod,&group)!=EP_PROPERTY_OK) {*out=group;return EP_PROPERTY_CLEANUP;}
        return result==EP_PROPERTY_CLEANUP ? EP_PROPERTY_SEAL : result;
    }
    group.constructor=group.code[0].base+life.constructor;group.release=group.code[0].base+life.release;
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
    group.state_change=group.code[9].base+state.change;group.return_screen=group.code[9].base+state.return_screen;
    group.context_action=group.code[9].base+state.context_action;group.state_tick=group.code[9].base+state.tick;
    group.prompt=group.code[10].base+prompt.update;group.selection_prompt=group.code[10].base+prompt.selection;
    group.active_prompt=group.code[10].base+prompt.active;
    group.ready_flag=group.code[10].base+prompt.ready_flag;group.blocked_flag=group.code[10].base+prompt.blocked_flag;
    group.countdown=group.code[11].base+countdown.update;group.resource_lookup=group.code[11].base+countdown.resource_lookup;
    group.reset_timers=group.code[11].base+countdown.reset_timers;
    group.capacity=l.capacity;group.state=EP_LOADOUT_GROUP_READY;*out=group;return EP_PROPERTY_OK;
}
