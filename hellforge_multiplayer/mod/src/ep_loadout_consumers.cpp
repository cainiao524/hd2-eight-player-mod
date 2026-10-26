#include "ep_loadout_consumers.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutConsumerFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_consumers_template.h"
int ep_loadout_maps_initialize(EpLoadoutMaps* out,uint32_t capacity,uint32_t local)
{
    if (!out || !capacity || capacity>EP_LOADOUT_LIFECYCLE_LIMIT || local>=capacity) return 0;
    EpLoadoutMaps maps;memset(&maps,0xff,sizeof maps);
    maps.network_to_slot[local]=0;maps.slot_to_network[0]=local;*out=maps;return 1;
}
EpPropertyResult ep_loadout_consumers_build(const EpLoadoutConsumerAddresses* input,EpLoadoutConsumerImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutConsumerAddresses a={};if (input) a=*input;*out={};const auto& l=a.lifecycle;
    if (!input || l.reserved || !l.capacity || l.capacity>EP_LOADOUT_LIFECYCLE_LIMIT) return EP_PROPERTY_ARGUMENT;
    const uint64_t ranges[][3]={{l.game,0x4000000,4096},{l.code,EP_LOADOUT_CONSUMER_BYTES,16},
        {l.screen,EP_LOADOUT_SCREEN_BYTES,8},{l.records,uint64_t(l.capacity)*EP_LOADOUT_RECORD_BYTES,16},
        {l.widgets,uint64_t(l.capacity)*EP_LOADOUT_WIDGET_BYTES,8},{l.reject,1,1},
        {a.forward_map,32,4},{a.inverse_map,32,4},{a.roster,0xe8,8},{a.roster_storage,0x680,16}};
    for (unsigned i=0;i<sizeof(ranges)/sizeof(ranges[0]);i++) {
        const auto& r=ranges[i];
        if (r[0]<0x10000 || r[0]>=(UINT64_C(1)<<47) || r[0]%r[2] || r[1]>(UINT64_C(1)<<47)-r[0]) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (r[0]<ranges[j][0]+ranges[j][1] && ranges[j][0]<r[0]+r[1]) return EP_PROPERTY_OVERLAP;
    }
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,
                             a.forward_map,a.inverse_map,a.roster,a.roster_storage};
    EpLoadoutConsumerImage image={};memcpy(image.data,ep_loadout_consumers_template,sizeof(ep_loadout_consumers_template));
    for (const auto& f:ep_loadout_consumer_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        if (f.kind==3) value-=(int64_t)l.screen;
        const unsigned width=f.kind==1 || f.kind==3 ? 8 : 4;
        for (unsigned i=0;i<width;i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.bytes=sizeof(ep_loadout_consumers_template);image.code_bytes=ep_loadout_consumer_code_bytes;
    image.unwind_offset=ep_loadout_consumer_unwind_offset;image.table_offset=ep_loadout_consumer_table_offset;
    image.function_count=ep_loadout_consumer_functions;image.update=ep_loadout_consumer_entries[0];
    image.lookup=ep_loadout_consumer_entries[1];image.action=ep_loadout_consumer_entries[2];*out=image;
    return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_consumers_prepare(const HfApi* api,HfMod* mod,const EpLoadoutConsumerAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutConsumerAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutConsumerImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.lifecycle.code,sizeof(ep_loadout_consumers_template),&code)) return EP_PROPERTY_RESERVE;
    a.lifecycle.code=code.base;EpPropertyResult status=ep_loadout_consumers_build(&a,&image);
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
