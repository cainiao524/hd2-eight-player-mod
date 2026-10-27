#include "ep_loadout_consumers.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutConsumerFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_consumers_template.h"
#include "ep_loadout_peer_consumers_template.h"
int ep_loadout_maps_initialize(EpLoadoutMaps* out,uint32_t capacity,uint32_t local)
{
    if (!out || !capacity || capacity>EP_LOADOUT_LIFECYCLE_LIMIT || local>=capacity) return 0;
    EpLoadoutMaps maps;memset(&maps,0xff,sizeof maps);
    maps.network_to_slot[local]=0;maps.slot_to_network[0]=local;*out=maps;return 1;
}
static EpPropertyResult EpLoadoutValidate(const EpLoadoutConsumerAddresses* input,uint32_t code_bytes)
{
    EpLoadoutConsumerAddresses a={};if (input) a=*input;const auto& l=a.lifecycle;
    if (!input || l.reserved || !l.capacity || l.capacity>EP_LOADOUT_LIFECYCLE_LIMIT) return EP_PROPERTY_ARGUMENT;
    const uint64_t ranges[][3]={{l.game,0x4000000,4096},{l.code,code_bytes,16},
        {l.screen,EP_LOADOUT_SCREEN_BYTES,8},{l.records,uint64_t(l.capacity)*EP_LOADOUT_RECORD_BYTES,16},
        {l.widgets,uint64_t(l.capacity)*EP_LOADOUT_WIDGET_BYTES,8},{l.reject,1,1},
        {a.forward_map,32,4},{a.inverse_map,32,4},{a.roster,0xe8,8},{a.roster_storage,0x680,16}};
    for (unsigned i=0;i<sizeof(ranges)/sizeof(ranges[0]);i++) {
        const auto& r=ranges[i];
        if (r[0]<0x10000 || r[0]>=(UINT64_C(1)<<47) || r[0]%r[2] || r[1]>(UINT64_C(1)<<47)-r[0]) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (r[0]<ranges[j][0]+ranges[j][1] && ranges[j][0]<r[0]+r[1]) return EP_PROPERTY_OVERLAP;
    }
    return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_consumers_validate(const EpLoadoutConsumerAddresses* input)
{return EpLoadoutValidate(input,EP_LOADOUT_CONSUMER_BYTES);}
EpPropertyResult ep_loadout_consumers_validate_span(const EpLoadoutConsumerAddresses* input,uint32_t code_bytes)
{return !code_bytes || code_bytes>65536 ? EP_PROPERTY_ARGUMENT : EpLoadoutValidate(input,code_bytes);}
EpPropertyResult ep_loadout_consumers_validate_link(const EpLoadoutConsumerAddresses* input,uint64_t entry)
{
    EpPropertyResult status=ep_loadout_consumers_validate(input);if (status!=EP_PROPERTY_OK) return status;
    const auto& l=input->lifecycle;
    if (entry>=l.code && entry<l.code+EP_LOADOUT_CONSUMER_BYTES) return EP_PROPERTY_OVERLAP;
    EpLoadoutConsumerAddresses target=*input;target.lifecycle.code=entry;
    return EpLoadoutValidate(&target,1);
}
EpPropertyResult ep_loadout_consumers_peer_span(const EpPlayerJoinPeers* p,uint64_t at,uint32_t bytes)
{
    if (!p || p->reserved || p->capacity<4 || p->capacity>8 || !bytes) return EP_PROPERTY_ARGUMENT;
    if (p->client<0x262c8 || p->client%8 || p->client>=(UINT64_C(1)<<47)-0x528 ||
        p->bank<0x10000 || p->bank%16 || p->bank>=(UINT64_C(1)<<47)-p->capacity*32 ||
        at<0x10000 || at>=(UINT64_C(1)<<47)-bytes) return EP_PROPERTY_POINTER;
    const uint64_t owner=p->client-0x162c8,end=p->client+0x528;
    if ((p->bank<end && owner<p->bank+p->capacity*32) ||
        (at<end && owner<at+bytes) || (at<p->bank+p->capacity*32 && p->bank<at+bytes)) return EP_PROPERTY_OVERLAP;
    return EP_PROPERTY_OK;
}
static EpPropertyResult build(const EpLoadoutConsumerAddresses* input,uint64_t ready_flag,const EpPlayerJoinPeers* peers,EpLoadoutConsumerImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutConsumerAddresses a={};if (input) a=*input;*out={};
    EpPropertyResult status=ep_loadout_consumers_validate(input ? &a : nullptr);if (status!=EP_PROPERTY_OK) return status;
    status=ep_loadout_consumers_validate_link(&a,ready_flag);if (status!=EP_PROPERTY_OK) return status;
    const auto& l=a.lifecycle;
    if (peers) {
        if (peers->capacity!=l.capacity) return EP_PROPERTY_ARGUMENT;
        const uint64_t ranges[][2]={{l.game,0x4000000},{l.code,EP_LOADOUT_CONSUMER_BYTES},
            {l.screen,EP_LOADOUT_SCREEN_BYTES},{l.records,l.capacity*EP_LOADOUT_RECORD_BYTES},
            {l.widgets,l.capacity*EP_LOADOUT_WIDGET_BYTES},{l.reject,1},
            {a.forward_map,32},{a.inverse_map,32},{a.roster,0xe8},{a.roster_storage,0x680},{ready_flag,1}};
        for (const auto& r:ranges) {
            status=ep_loadout_consumers_peer_span(peers,r[0],(uint32_t)r[1]);if (status!=EP_PROPERTY_OK) return status;
        }
    }
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,
        a.forward_map,a.inverse_map,a.roster,a.roster_storage,ready_flag,peers ? peers->client : 0,peers ? peers->bank : 0};
    EpLoadoutConsumerImage image={};
    image.bytes=peers ? sizeof(ep_loadout_peer_consumers_template) : sizeof(ep_loadout_consumers_template);
    memcpy(image.data,peers ? ep_loadout_peer_consumers_template : ep_loadout_consumers_template,image.bytes);
    const auto* fixes=peers ? ep_loadout_peer_consumer_fixups : ep_loadout_consumer_fixups;
    const unsigned count=peers ? sizeof(ep_loadout_peer_consumer_fixups)/sizeof(*fixes) : sizeof(ep_loadout_consumer_fixups)/sizeof(*fixes);
    for (unsigned n=0;n<count;n++) {const auto& f=fixes[n];
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        if (f.kind==3) value-=(int64_t)l.screen;
        const unsigned width=f.kind==1 || f.kind==3 ? 8 : 4;
        for (unsigned i=0;i<width;i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.code_bytes=peers ? ep_loadout_peer_consumer_code_bytes : ep_loadout_consumer_code_bytes;
    image.unwind_offset=peers ? ep_loadout_peer_consumer_unwind_offset : ep_loadout_consumer_unwind_offset;
    image.table_offset=peers ? ep_loadout_peer_consumer_table_offset : ep_loadout_consumer_table_offset;
    image.function_count=peers ? ep_loadout_peer_consumer_functions : ep_loadout_consumer_functions;
    const auto* entries=peers ? ep_loadout_peer_consumer_entries : ep_loadout_consumer_entries;
    image.update=entries[0];image.lookup=entries[1];image.action=entries[2];*out=image;
    return EP_PROPERTY_OK;
}
static EpPropertyResult prepare(const HfApi* api,HfMod* mod,const EpLoadoutConsumerAddresses* input,uint64_t ready_flag,const EpPlayerJoinPeers* peers,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutConsumerAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutConsumerImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.lifecycle.code,peers ? sizeof(ep_loadout_peer_consumers_template) : sizeof(ep_loadout_consumers_template),&code)) return EP_PROPERTY_RESERVE;
    a.lifecycle.code=code.base;EpPropertyResult status=build(&a,ready_flag,peers,&image);
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
EpPropertyResult ep_loadout_consumers_build(const EpLoadoutConsumerAddresses* a,uint64_t ready,EpLoadoutConsumerImage* out)
{return build(a,ready,nullptr,out);}
EpPropertyResult ep_loadout_consumers_build_peers(const EpLoadoutConsumerAddresses* a,uint64_t ready,const EpPlayerJoinPeers* peers,EpLoadoutConsumerImage* out)
{
    if (!peers) {if (out) *out={};return EP_PROPERTY_ARGUMENT;}
    const auto binding=*peers;return build(a,ready,&binding,out);
}
EpPropertyResult ep_loadout_consumers_prepare(const HfApi* api,HfMod* mod,const EpLoadoutConsumerAddresses* a,uint64_t ready,EpSessionCodeInfo* out)
{return prepare(api,mod,a,ready,nullptr,out);}
EpPropertyResult ep_loadout_consumers_prepare_peers(const HfApi* api,HfMod* mod,const EpLoadoutConsumerAddresses* a,uint64_t ready,const EpPlayerJoinPeers* peers,EpSessionCodeInfo* out)
{
    if (!peers) {if (out) *out={};return EP_PROPERTY_ARGUMENT;}
    const auto binding=*peers;return prepare(api,mod,a,ready,&binding,out);
}
