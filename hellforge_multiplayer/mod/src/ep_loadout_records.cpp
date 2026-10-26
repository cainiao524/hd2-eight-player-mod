#include "ep_loadout_records.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutRecordsFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_records_template.h"
static_assert(EP_LOADOUT_RECORDS_BYTES==EP_LOADOUT_CONSUMER_BYTES,"Shared binding span");
EpPropertyResult ep_loadout_records_validate(const EpLoadoutRecordsAddresses* a)
{return ep_loadout_records_validate_span(a,EP_LOADOUT_RECORDS_BYTES);}
EpPropertyResult ep_loadout_records_validate_span(const EpLoadoutRecordsAddresses* a,uint32_t code_bytes)
{
    EpPropertyResult result=ep_loadout_consumers_validate_span(a ? &a->common : nullptr,code_bytes);if (result!=EP_PROPERTY_OK) return result;
    const auto& b=a->common;const auto& l=b.lifecycle;const auto& s=a->source;const uint64_t n=l.capacity;
    const uint64_t ranges[][3]={{l.game,0x4000000,4096},{l.code,code_bytes,16},
        {l.screen,EP_LOADOUT_SCREEN_BYTES,8},{l.records,n*EP_LOADOUT_RECORD_BYTES,16},
        {l.widgets,n*EP_LOADOUT_WIDGET_BYTES,8},{l.reject,1,1},{b.forward_map,32,4},{b.inverse_map,32,4},
        {b.roster,0xe8,8},{b.roster_storage,0x680,16},
        {s.manager,0x948,8},{s.actors,n*8,8},{s.equipment,n*0x40,16},{s.status,n*0x44,4}};
    for (unsigned i=10;i<sizeof(ranges)/sizeof(ranges[0]);i++) {
        const auto& r=ranges[i];
        if (r[0]<0x10000 || r[0]>=(UINT64_C(1)<<47) || r[1]>(UINT64_C(1)<<47)-r[0] || r[0]%r[2]) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (r[0]<ranges[j][0]+ranges[j][1] && ranges[j][0]<r[0]+r[1]) return EP_PROPERTY_OVERLAP;
    }
    return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_records_build(const EpLoadoutRecordsAddresses* input,EpLoadoutRecordsImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutRecordsAddresses a={};if (input) a=*input;*out={};
    EpPropertyResult result=ep_loadout_records_validate(input ? &a : nullptr);if (result!=EP_PROPERTY_OK) return result;
    const auto& b=a.common;const auto& l=b.lifecycle;const auto& s=a.source;
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,
        b.forward_map,b.inverse_map,b.roster,b.roster_storage,s.manager,s.actors,s.equipment,s.status};
    EpLoadoutRecordsImage image={};memcpy(image.data,ep_loadout_records_template,sizeof(ep_loadout_records_template));
    for (const auto& f:ep_loadout_records_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        if (f.kind==3) value-=(int64_t)l.screen;
        for (unsigned i=0;i<(f.kind==1 || f.kind==3 ? 8u : 4u);i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.bytes=sizeof(ep_loadout_records_template);image.code_bytes=ep_loadout_records_code_bytes;
    image.unwind_offset=ep_loadout_records_unwind_offset;image.table_offset=ep_loadout_records_table_offset;
    image.handler_offset=ep_loadout_records_handler_offset;*out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_records_prepare(const HfApi* api,HfMod* mod,const EpLoadoutRecordsAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutRecordsAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutRecordsImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.common.lifecycle.code,sizeof(ep_loadout_records_template),&code)) return EP_PROPERTY_RESERVE;
    a.common.lifecycle.code=code.base;EpPropertyResult result=ep_loadout_records_build(&a,&image);
    const EpSessionGsCheck gs={1,image.handler_offset,a.common.lifecycle.game+0x21044a0};
    if (result==EP_PROPERTY_OK && !ep_session_code_seal_loadout_records(mod,code.handle,image.data,image.bytes,image.table_offset,&gs)) result=EP_PROPERTY_SEAL;
    if (result==EP_PROPERTY_OK) {if (ep_session_code_info(mod,code.handle,out)) return EP_PROPERTY_OK;result=EP_PROPERTY_SEAL;}
    if (!ep_session_code_discard(mod,code.handle)) {
        *out=code;EpSessionCodeInfo retained={};if (ep_session_code_info(mod,code.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return result;
}
