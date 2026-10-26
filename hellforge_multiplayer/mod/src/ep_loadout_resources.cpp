#include "ep_loadout_resources.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutResourcesFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_resources_template.h"
static_assert(EP_LOADOUT_RESOURCES_BYTES==EP_LOADOUT_CONSUMER_BYTES,"Shared binding span");
EpPropertyResult ep_loadout_resources_build(const EpLoadoutResourcesAddresses* input,EpLoadoutResourcesImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutResourcesAddresses a={};if (input) a=*input;*out={};
    EpLoadoutCountdownAddresses validation={a.records,a.source,0,0};
    EpPropertyResult status=ep_loadout_countdown_validate_span(input ? &validation : nullptr,EP_LOADOUT_RESOURCES_BYTES);if (status!=EP_PROPERTY_OK) return status;
    const auto& b=a.records.common;const auto& l=b.lifecycle;
    const uint64_t entries[]={a.resource_lookup};
    for (uint64_t entry:entries) {
        if (entry>=l.code && entry<l.code+EP_LOADOUT_RESOURCES_BYTES) return EP_PROPERTY_OVERLAP;
        EpLoadoutCountdownAddresses target=validation;target.records.common.lifecycle.code=entry;
        status=ep_loadout_countdown_validate_span(&target,1);if (status!=EP_PROPERTY_OK) return status;
    }
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,
                             b.forward_map,b.inverse_map,b.roster,b.roster_storage,a.source.manager,a.source.resources,a.resource_lookup};
    EpLoadoutResourcesImage image={};memcpy(image.data,ep_loadout_resources_template,sizeof(ep_loadout_resources_template));
    for (const auto& f:ep_loadout_resources_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        if (f.kind==3) value-=(int64_t)l.screen;
        const unsigned width=f.kind==1 || f.kind==3 ? 8 : 4;
        for (unsigned i=0;i<width;i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.bytes=sizeof(ep_loadout_resources_template);image.code_bytes=ep_loadout_resources_code_bytes;
    image.unwind_offset=ep_loadout_resources_unwind_offset;image.table_offset=ep_loadout_resources_table_offset;
    image.function_count=ep_loadout_resources_functions;image.write=ep_loadout_resources_entries[0];
    image.ordinal=ep_loadout_resources_entries[1];image.transform=ep_loadout_resources_entries[2];
    image.player_value=ep_loadout_resources_entries[3];image.assign=ep_loadout_resources_entries[4];*out=image;
    return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_resources_prepare(const HfApi* api,HfMod* mod,const EpLoadoutResourcesAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutResourcesAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutResourcesImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.records.common.lifecycle.code,sizeof(ep_loadout_resources_template),&code)) return EP_PROPERTY_RESERVE;
    a.records.common.lifecycle.code=code.base;EpPropertyResult status=ep_loadout_resources_build(&a,&image);
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
