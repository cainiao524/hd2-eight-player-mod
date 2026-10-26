#include "ep_loadout_control.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutControlFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_control_template.h"
static_assert(EP_LOADOUT_CONTROL_BYTES==EP_LOADOUT_CONSUMER_BYTES,"Shared binding span");
EpPropertyResult ep_loadout_control_build(const EpLoadoutControlAddresses* input,EpLoadoutControlImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutControlAddresses a={};if (input) a=*input;*out={};
    EpPropertyResult status=ep_loadout_consumers_validate(input ? &a.common : nullptr);
    if (status!=EP_PROPERTY_OK) return status;
    const uint64_t entries[]={a.mode,a.input,a.edit,a.return_screen,a.ready_flag,a.blocked_flag};
    for (uint64_t entry:entries) {
        status=ep_loadout_consumers_validate_link(&a.common,entry);if (status!=EP_PROPERTY_OK) return status;
    }
    const auto& b=a.common;const auto& l=b.lifecycle;
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,
                             b.forward_map,b.inverse_map,b.roster,b.roster_storage,a.mode,a.input,a.edit,a.return_screen,a.ready_flag,a.blocked_flag};
    EpLoadoutControlImage image={};memcpy(image.data,ep_loadout_control_template,sizeof(ep_loadout_control_template));
    for (const auto& f:ep_loadout_control_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        if (f.kind==3) value-=(int64_t)l.screen;
        const unsigned width=f.kind==1 || f.kind==3 ? 8 : 4;
        for (unsigned i=0;i<width;i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.bytes=sizeof(ep_loadout_control_template);image.code_bytes=ep_loadout_control_code_bytes;
    image.unwind_offset=ep_loadout_control_unwind_offset;image.table_offset=ep_loadout_control_table_offset;
    image.function_count=ep_loadout_control_functions;image.leave=ep_loadout_control_entries[0];
    image.screen_input=ep_loadout_control_entries[1];image.reset_selection=ep_loadout_control_entries[2];*out=image;
    return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_control_prepare(const HfApi* api,HfMod* mod,const EpLoadoutControlAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutControlAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutControlImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.common.lifecycle.code,sizeof(ep_loadout_control_template),&code)) return EP_PROPERTY_RESERVE;
    a.common.lifecycle.code=code.base;EpPropertyResult status=ep_loadout_control_build(&a,&image);
    if (status==EP_PROPERTY_OK && !ep_session_code_seal_table(mod,code.handle,image.data,image.bytes,image.table_offset,image.function_count)) status=EP_PROPERTY_SEAL;
    if (status==EP_PROPERTY_OK) {
        if (ep_session_code_info(mod,code.handle,out)) return EP_PROPERTY_OK;
        status=EP_PROPERTY_SEAL;
    }
    if (!ep_session_code_discard(mod,code.handle)) {
        *out=code;EpSessionCodeInfo retained={};if (ep_session_code_info(mod,code.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return status;
}
