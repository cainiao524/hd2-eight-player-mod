#include "ep_loadout_state.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutStateFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_state_template.h"
EpPropertyResult ep_loadout_state_build(const EpLoadoutStateAddresses* input,EpLoadoutStateImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutStateAddresses a={};if (input) a=*input;*out={};
    EpPropertyResult result=ep_loadout_consumers_validate(input ? &a.common : nullptr);
    if (result!=EP_PROPERTY_OK) return result;
    const uint64_t entries[]={a.open_mode,a.leave};
    for (uint64_t entry:entries) {
        result=ep_loadout_consumers_validate_link(&a.common,entry);if (result!=EP_PROPERTY_OK) return result;
    }
    const auto& b=a.common;const auto& l=b.lifecycle;
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,
        b.forward_map,b.inverse_map,b.roster,b.roster_storage,a.open_mode,a.leave};
    EpLoadoutStateImage image={};memcpy(image.data,ep_loadout_state_template,sizeof(ep_loadout_state_template));
    for (const auto& f:ep_loadout_state_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        if (f.kind==3) value-=(int64_t)l.screen;
        for (unsigned i=0;i<(f.kind==1 || f.kind==3 ? 8u : 4u);i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.bytes=sizeof(ep_loadout_state_template);image.code_bytes=ep_loadout_state_code_bytes;
    image.unwind_offset=ep_loadout_state_unwind_offset;image.table_offset=ep_loadout_state_table_offset;
    image.handler_offset=ep_loadout_state_handler_offset;image.return_screen=ep_loadout_state_entries[0];
    image.change=ep_loadout_state_entries[1];image.context_action=ep_loadout_state_entries[2];image.tick=ep_loadout_state_entries[3];*out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_state_prepare(const HfApi* api,HfMod* mod,const EpLoadoutStateAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutStateAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutStateImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.common.lifecycle.code,sizeof(ep_loadout_state_template),&code)) return EP_PROPERTY_RESERVE;
    a.common.lifecycle.code=code.base;EpPropertyResult result=ep_loadout_state_build(&a,&image);
    const EpSessionGsCheck gs={5,image.handler_offset,a.common.lifecycle.game+0x21044a0};
    if (result==EP_PROPERTY_OK && !ep_session_code_seal_loadout_state(mod,code.handle,image.data,image.bytes,image.table_offset,&gs)) result=EP_PROPERTY_SEAL;
    if (result==EP_PROPERTY_OK) {if (ep_session_code_info(mod,code.handle,out)) return EP_PROPERTY_OK;result=EP_PROPERTY_SEAL;}
    if (!ep_session_code_discard(mod,code.handle)) {
        *out=code;EpSessionCodeInfo retained={};if (ep_session_code_info(mod,code.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return result;
}
