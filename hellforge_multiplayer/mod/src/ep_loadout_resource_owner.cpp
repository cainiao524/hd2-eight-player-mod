#include "ep_loadout_resource_owner.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutResourceOwnerFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_resource_owner_template.h"
static_assert(EP_LOADOUT_RESOURCE_OWNER_BYTES==EP_LOADOUT_CONSUMER_BYTES,"Shared binding span");
EpPropertyResult ep_loadout_resource_owner_validate_span(const EpLoadoutResourceOwnerAddresses* a,uint32_t code_bytes)
{
    if (!a) return EP_PROPERTY_ARGUMENT;
    EpLoadoutCountdownAddresses base={a->records,a->countdown_source,0,0};
    EpPropertyResult result=ep_loadout_countdown_validate_span(&base,code_bytes);if (result!=EP_PROPERTY_OK) return result;
    const auto& b=a->records.common;const auto& l=b.lifecycle;const auto& s=a->records.source;
    const uint64_t n=l.capacity;
    const uint64_t prior[][2]={{l.game,0x4000000},{l.code,code_bytes},{l.screen,EP_LOADOUT_SCREEN_BYTES},
        {l.records,n*EP_LOADOUT_RECORD_BYTES},{l.widgets,n*EP_LOADOUT_WIDGET_BYTES},{l.reject,1},
        {b.forward_map,32},{b.inverse_map,32},{b.roster,0xe8},{b.roster_storage,0x680},
        {s.manager,0x948},{s.actors,n*8},{s.equipment,n*0x40},{s.status,n*0x44},
        {a->countdown_source.manager,0x13000},{a->countdown_source.resources,n*0x4c}};
    const uint64_t banks[][3]={{a->source.owner,0x118,8},{a->source.objects,n*8,8},
        {a->source.phases,n*12,4},{a->source.rows,n*20,4},{a->source.states,n*4,4}};
    for (unsigned i=0;i<5;i++) {
        const auto& r=banks[i];
        if (r[0]<0x10000 || r[0]>=(UINT64_C(1)<<47)-r[1] || r[0]%r[2]) return EP_PROPERTY_POINTER;
        for (const auto& p:prior) if (r[0]<p[0]+p[1] && p[0]<r[0]+r[1]) return EP_PROPERTY_OVERLAP;
        for (unsigned j=0;j<i;j++) if (r[0]<banks[j][0]+banks[j][1] && banks[j][0]<r[0]+r[1]) return EP_PROPERTY_OVERLAP;
    }
    return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_resource_owner_build(const EpLoadoutResourceOwnerAddresses* input,EpLoadoutResourceOwnerImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutResourceOwnerAddresses a={};if (input) a=*input;*out={};
    EpPropertyResult status=ep_loadout_resource_owner_validate_span(input ? &a : nullptr,EP_LOADOUT_RESOURCE_OWNER_BYTES);if (status!=EP_PROPERTY_OK) return status;
    const auto& b=a.records.common;const auto& l=b.lifecycle;
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,
                             b.forward_map,b.inverse_map,b.roster,b.roster_storage,a.countdown_source.manager,a.countdown_source.resources,
                             a.source.owner,a.source.objects,a.source.phases,a.source.rows,a.source.states};
    EpLoadoutResourceOwnerImage image={};memcpy(image.data,ep_loadout_resource_owner_template,sizeof(ep_loadout_resource_owner_template));
    for (const auto& f:ep_loadout_resource_owner_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        if (f.kind==3) value-=(int64_t)l.screen;
        const unsigned width=f.kind==1 || f.kind==3 ? 8 : 4;
        for (unsigned i=0;i<width;i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.bytes=sizeof(ep_loadout_resource_owner_template);image.code_bytes=ep_loadout_resource_owner_code_bytes;
    image.unwind_offset=ep_loadout_resource_owner_unwind_offset;image.table_offset=ep_loadout_resource_owner_table_offset;
    image.function_count=ep_loadout_resource_owner_functions;image.insert=ep_loadout_resource_owner_entries[0];
    image.enqueue=ep_loadout_resource_owner_entries[1];image.move=ep_loadout_resource_owner_entries[2];
    image.remove=ep_loadout_resource_owner_entries[3];*out=image;
    return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_resource_owner_prepare(const HfApi* api,HfMod* mod,const EpLoadoutResourceOwnerAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutResourceOwnerAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutResourceOwnerImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.records.common.lifecycle.code,sizeof(ep_loadout_resource_owner_template),&code)) return EP_PROPERTY_RESERVE;
    a.records.common.lifecycle.code=code.base;EpPropertyResult status=ep_loadout_resource_owner_build(&a,&image);
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
