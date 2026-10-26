#include "ep_loadout_group.h"
EpPropertyResult ep_loadout_group_discard(HfMod* mod,EpLoadoutGroup* out)
{
    if (!mod || !out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutGroup remaining={};
    for (unsigned i=8;i--;) if (out->code[i].handle && !ep_session_code_discard(mod,out->code[i].handle)) {
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
    const uint64_t bases[]={l.code,c.lifecycle.code,a.setup.common.lifecycle.code,a.interactions_code,a.refresh_code,a.records_code,a.frame_code,a.mode_code};
    const uint32_t spans[]={8192,8192,8192,8192,8192,8192,EP_LOADOUT_FRAME_BYTES,EP_LOADOUT_MODE_BYTES};
    for (unsigned i=0;i<8;i++) {
        if (!bases[i] || bases[i]>=(UINT64_C(1)<<47)-spans[i]) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (bases[i]<bases[j]+spans[j] && bases[j]<bases[i]+spans[i]) return EP_PROPERTY_OVERLAP;
        records_binding.common.lifecycle.code=bases[i];
        result=ep_loadout_records_validate_span(&records_binding,spans[i]);if (result!=EP_PROPERTY_OK) return result;
    }
    records_binding.common.lifecycle.code=a.records_code;
    EpLoadoutImage life={};EpLoadoutConsumerImage consumers={};EpLoadoutSetupImage setup={};
    EpLoadoutInteractionImage interactions={};
    EpLoadoutRefreshImage refresh={};
    EpLoadoutRecordsImage records={};
    EpLoadoutFrameImage frame={};
    EpLoadoutModeImage mode={};
    result=ep_loadout_lifecycle_build(&l,&life);if (result!=EP_PROPERTY_OK) return result;
    result=ep_loadout_consumers_build(&c,&consumers);if (result!=EP_PROPERTY_OK) return result;
    result=ep_loadout_setup_build(&a.setup,&setup);if (result!=EP_PROPERTY_OK) return result;
    result=ep_loadout_interactions_build(&interaction_binding,&interactions);if (result!=EP_PROPERTY_OK) return result;
    refresh_binding.close_entry=a.interactions_code+interactions.close;
    result=ep_loadout_refresh_build(&refresh_binding,&refresh);if (result!=EP_PROPERTY_OK) return result;
    result=ep_loadout_records_build(&records_binding,&records);if (result!=EP_PROPERTY_OK) return result;
    result=ep_loadout_mode_build(&mode_binding,&mode);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutFrameAddresses frame_binding={records_binding,a.records_code,c.lifecycle.code+consumers.update,c.lifecycle.code+consumers.lookup,a.mode_code+mode.open};
    frame_binding.records.common.lifecycle.code=a.frame_code;
    result=ep_loadout_frame_build(&frame_binding,&frame);if (result!=EP_PROPERTY_OK) return result;
    EpLoadoutGroup group={};
    result=ep_loadout_lifecycle_prepare(api,mod,&l,&group.code[0]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_consumers_prepare(api,mod,&c,&group.code[1]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_setup_prepare(api,mod,&a.setup,&group.code[2]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_interactions_prepare(api,mod,&interaction_binding,&group.code[3]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_refresh_prepare(api,mod,&refresh_binding,&group.code[4]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_records_prepare(api,mod,&records_binding,&group.code[5]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_frame_prepare(api,mod,&frame_binding,&group.code[6]);
    if (result==EP_PROPERTY_OK) result=ep_loadout_mode_prepare(api,mod,&mode_binding,&group.code[7]);
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
    group.capacity=l.capacity;group.state=EP_LOADOUT_GROUP_READY;*out=group;return EP_PROPERTY_OK;
}
