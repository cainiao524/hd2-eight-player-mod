#include "ep_loadout_resource_sync.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutResourceSyncFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_resource_sync_template.h"
static_assert(EP_LOADOUT_RESOURCE_SYNC_BYTES==EP_LOADOUT_CONSUMER_BYTES,"Shared binding span");
EpPropertyResult ep_loadout_resource_sync_build(const EpLoadoutResourceSyncAddresses* input,EpLoadoutResourceSyncImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutResourceSyncAddresses a={};if (input) a=*input;*out={};
    EpPropertyResult status=ep_loadout_resource_owner_validate_span(input ? &a : nullptr,EP_LOADOUT_RESOURCE_SYNC_BYTES);if (status!=EP_PROPERTY_OK) return status;
    const auto& b=a.records.common;const auto& l=b.lifecycle;
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,
                             b.forward_map,b.inverse_map,b.roster,b.roster_storage,a.countdown_source.manager,a.countdown_source.resources,
                             a.source.owner,a.source.objects,a.source.phases,a.source.rows,a.source.states};
    EpLoadoutResourceSyncImage image={};memcpy(image.data,ep_loadout_resource_sync_template,sizeof(ep_loadout_resource_sync_template));
    for (const auto& f:ep_loadout_resource_sync_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        if (f.kind==3) value-=(int64_t)l.screen;
        const unsigned width=f.kind==1 || f.kind==3 ? 8 : 4;
        for (unsigned i=0;i<width;i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.bytes=sizeof(ep_loadout_resource_sync_template);image.code_bytes=ep_loadout_resource_sync_code_bytes;
    image.unwind_offset=ep_loadout_resource_sync_unwind_offset;image.table_offset=ep_loadout_resource_sync_table_offset;
    image.function_count=ep_loadout_resource_sync_functions;image.emit_initial=ep_loadout_resource_sync_entries[0];
    image.receive=ep_loadout_resource_sync_entries[1];*out=image;
    return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_resource_sync_prepare(const HfApi* api,HfMod* mod,const EpLoadoutResourceSyncAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutResourceSyncAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutResourceSyncImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.records.common.lifecycle.code,sizeof(ep_loadout_resource_sync_template),&code)) return EP_PROPERTY_RESERVE;
    a.records.common.lifecycle.code=code.base;EpPropertyResult status=ep_loadout_resource_sync_build(&a,&image);
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
