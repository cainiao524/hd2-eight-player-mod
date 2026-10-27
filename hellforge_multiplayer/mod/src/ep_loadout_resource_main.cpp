#include "ep_loadout_resource_main.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutResourceMainFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_resource_main_template.h"
EpPropertyResult ep_loadout_resource_main_build(const EpLoadoutResourceMainAddresses* input,EpLoadoutResourceMainImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutResourceMainAddresses a={};if (input) a=*input;*out={};
    EpPropertyResult status=ep_loadout_resource_owner_validate_span(input ? &a.owner : nullptr,EP_LOADOUT_RESOURCE_MAIN_BYTES);if (status!=EP_PROPERTY_OK) return status;
    const auto& b=a.owner.records.common;const auto& l=b.lifecycle;
    if (a.reset_entry<0x10000 || a.reset_entry>=(UINT64_C(1)<<47)) return EP_PROPERTY_POINTER;
    if (a.reset_entry>=l.code && a.reset_entry<l.code+EP_LOADOUT_RESOURCE_MAIN_BYTES) return EP_PROPERTY_OVERLAP;
    EpLoadoutResourceOwnerAddresses target=a.owner;target.records.common.lifecycle.code=a.reset_entry;
    status=ep_loadout_resource_owner_validate_span(&target,1);if (status!=EP_PROPERTY_OK) return status;
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,
                             b.forward_map,b.inverse_map,b.roster,b.roster_storage,a.owner.countdown_source.manager,a.owner.countdown_source.resources,
                             a.owner.source.owner,a.owner.source.objects,a.owner.source.phases,a.owner.source.rows,a.owner.source.states,a.reset_entry};
    EpLoadoutResourceMainImage image={};memcpy(image.data,ep_loadout_resource_main_template,sizeof(ep_loadout_resource_main_template));
    for (const auto& f:ep_loadout_resource_main_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        if (f.kind==3) value-=(int64_t)l.screen;
        const unsigned width=f.kind==1 || f.kind==3 ? 8 : 4;
        for (unsigned i=0;i<width;i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.bytes=sizeof(ep_loadout_resource_main_template);image.code_bytes=ep_loadout_resource_main_code_bytes;
    image.unwind_offset=ep_loadout_resource_main_unwind_offset;image.table_offset=ep_loadout_resource_main_table_offset;
    image.function_count=ep_loadout_resource_main_functions;image.update=ep_loadout_resource_main_entries[0];
    image.query=ep_loadout_resource_main_entries[1];image.handler_offset=ep_loadout_resource_main_handler_offset;*out=image;
    return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_resource_main_prepare(const HfApi* api,HfMod* mod,const EpLoadoutResourceMainAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutResourceMainAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutResourceMainImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.owner.records.common.lifecycle.code,sizeof(ep_loadout_resource_main_template),&code)) return EP_PROPERTY_RESERVE;
    a.owner.records.common.lifecycle.code=code.base;EpPropertyResult status=ep_loadout_resource_main_build(&a,&image);
    const EpSessionGsCheck gs={1,image.handler_offset,a.owner.records.common.lifecycle.game+0x21044a0};
    if (status==EP_PROPERTY_OK && !ep_session_code_seal_loadout_resource_main(mod,code.handle,image.data,image.bytes,image.table_offset,&gs)) status=EP_PROPERTY_SEAL;
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
