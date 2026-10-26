#include "ep_loadout_refresh.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutRefreshFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_refresh_template.h"
static_assert(EP_LOADOUT_REFRESH_BYTES==EP_LOADOUT_CONSUMER_BYTES,"Shared binding span");
EpPropertyResult ep_loadout_refresh_build(const EpLoadoutRefreshAddresses* input,EpLoadoutRefreshImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutRefreshAddresses a={};if (input) a=*input;*out={};
    EpPropertyResult status=ep_loadout_consumers_validate_link(input ? &a.common : nullptr,a.close_entry);if (status!=EP_PROPERTY_OK) return status;
    const auto& b=a.common;const auto& l=b.lifecycle;
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,
                             b.forward_map,b.inverse_map,b.roster,b.roster_storage,a.close_entry};
    EpLoadoutRefreshImage image={};memcpy(image.data,ep_loadout_refresh_template,sizeof(ep_loadout_refresh_template));
    for (const auto& f:ep_loadout_refresh_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        if (f.kind==3) value-=(int64_t)l.screen;
        for (unsigned i=0;i<(f.kind==1 || f.kind==3 ? 8u : 4u);i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.bytes=sizeof(ep_loadout_refresh_template);image.code_bytes=ep_loadout_refresh_code_bytes;
    image.unwind_offset=ep_loadout_refresh_unwind_offset;image.table_offset=ep_loadout_refresh_table_offset;
    image.handler_offset=ep_loadout_refresh_handler_offset;*out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_refresh_prepare(const HfApi* api,HfMod* mod,const EpLoadoutRefreshAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutRefreshAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutRefreshImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.common.lifecycle.code,sizeof(ep_loadout_refresh_template),&code)) return EP_PROPERTY_RESERVE;
    a.common.lifecycle.code=code.base;EpPropertyResult status=ep_loadout_refresh_build(&a,&image);
    const EpSessionGsCheck gs={1,image.handler_offset,a.common.lifecycle.game+0x21044a0};
    if (status==EP_PROPERTY_OK && !ep_session_code_seal_loadout_refresh(mod,code.handle,image.data,image.bytes,image.table_offset,&gs)) status=EP_PROPERTY_SEAL;
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
