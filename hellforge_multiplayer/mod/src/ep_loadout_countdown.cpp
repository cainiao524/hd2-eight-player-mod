#include "ep_loadout_countdown.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutCountdownFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_countdown_template.h"
#include "ep_loadout_peer_countdown_template.h"
static_assert(EP_LOADOUT_COUNTDOWN_BYTES==EP_LOADOUT_CONSUMER_BYTES,"Shared binding span");
EpPropertyResult ep_loadout_countdown_validate_span(const EpLoadoutCountdownAddresses* a,uint32_t code_bytes)
{
    EpPropertyResult result=ep_loadout_records_validate_span(a ? &a->records : nullptr,code_bytes);
    if (result!=EP_PROPERTY_OK) return result;
    const auto& b=a->records.common;const auto& l=b.lifecycle;const auto& s=a->records.source;
    const uint64_t n=l.capacity;
    const uint64_t prior[][2]={{l.game,0x4000000},{l.code,code_bytes},{l.screen,EP_LOADOUT_SCREEN_BYTES},
        {l.records,n*EP_LOADOUT_RECORD_BYTES},{l.widgets,n*EP_LOADOUT_WIDGET_BYTES},{l.reject,1},
        {b.forward_map,32},{b.inverse_map,32},{b.roster,0xe8},{b.roster_storage,0x680},
        {s.manager,0x948},{s.actors,n*8},{s.equipment,n*0x40},{s.status,n*0x44}};
    const uint64_t rows[][3]={{a->source.manager,0x13000,8},{a->source.resources,n*0x4c,4}};
    for (unsigned i=0;i<2;i++) {
        const auto& r=rows[i];
        if (r[0]<0x10000 || r[0]>=(UINT64_C(1)<<47)-r[1] || r[0]%r[2]) return EP_PROPERTY_POINTER;
        for (const auto& p:prior) if (r[0]<p[0]+p[1] && p[0]<r[0]+r[1]) return EP_PROPERTY_OVERLAP;
        if (i && r[0]<rows[0][0]+rows[0][1] && rows[0][0]<r[0]+r[1]) return EP_PROPERTY_OVERLAP;
    }
    return EP_PROPERTY_OK;
}
static EpPropertyResult build(const EpLoadoutCountdownAddresses* input,const EpPlayerJoinPeers* peers,EpLoadoutCountdownImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutCountdownAddresses a={};if (input) a=*input;*out={};
    EpPropertyResult status=ep_loadout_countdown_validate_span(input ? &a : nullptr,EP_LOADOUT_COUNTDOWN_BYTES);if (status!=EP_PROPERTY_OK) return status;
    const auto& b=a.records.common;const auto& l=b.lifecycle;
    if (peers) {
        auto peer_result=ep_loadout_consumer_peers_validate(&b,peers,EP_LOADOUT_COUNTDOWN_BYTES);
        if (peer_result!=EP_PROPERTY_OK) return peer_result;
        const auto& s=a.records.source;
        const uint64_t extra[][2]={{s.manager,0xb7c},{s.actors,l.capacity*8},{s.equipment,l.capacity*0x40},{s.status,l.capacity*0x44},
            {a.source.manager,0x13000},{a.source.resources,l.capacity*0x4c},{a.context_action,1},{a.transition,1}};
        for (const auto& range:extra) {
            peer_result=ep_loadout_consumers_peer_span(peers,range[0],(uint32_t)range[1]);if (peer_result!=EP_PROPERTY_OK) return peer_result;
        }
    }
    const uint64_t entries[]={a.context_action,a.transition};
    for (uint64_t entry:entries) {
        if (entry>=l.code && entry<l.code+EP_LOADOUT_COUNTDOWN_BYTES) return EP_PROPERTY_OVERLAP;
        EpLoadoutCountdownAddresses target=a;target.records.common.lifecycle.code=entry;
        status=ep_loadout_countdown_validate_span(&target,1);if (status!=EP_PROPERTY_OK) return status;
    }
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,
                             b.forward_map,b.inverse_map,b.roster,b.roster_storage,a.source.manager,a.source.resources,a.context_action,a.transition,peers ? peers->client : 0,peers ? peers->bank : 0};
    const uint32_t bytes=peers ? sizeof(ep_loadout_peer_countdown_template) : sizeof(ep_loadout_countdown_template);
    EpLoadoutCountdownImage image={};memcpy(image.data,peers ? ep_loadout_peer_countdown_template : ep_loadout_countdown_template,bytes);
    const auto* fixes=peers ? ep_loadout_peer_countdown_fixups : ep_loadout_countdown_fixups;
    const unsigned count=peers ? sizeof(ep_loadout_peer_countdown_fixups)/sizeof(*fixes) : sizeof(ep_loadout_countdown_fixups)/sizeof(*fixes);
    for (unsigned index=0;index<count;index++) {const auto& f=fixes[index];
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        if (f.kind==3) value-=(int64_t)l.screen;
        const unsigned width=f.kind==1 || f.kind==3 ? 8 : 4;
        for (unsigned i=0;i<width;i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.bytes=bytes;image.code_bytes=(peers ? ep_loadout_peer_countdown_code_bytes : ep_loadout_countdown_code_bytes);
    image.unwind_offset=(peers ? ep_loadout_peer_countdown_unwind_offset : ep_loadout_countdown_unwind_offset);image.table_offset=(peers ? ep_loadout_peer_countdown_table_offset : ep_loadout_countdown_table_offset);
    image.function_count=(peers ? ep_loadout_peer_countdown_functions : ep_loadout_countdown_functions);image.update=(peers ? ep_loadout_peer_countdown_entries : ep_loadout_countdown_entries)[0];
    image.resource_lookup=(peers ? ep_loadout_peer_countdown_entries : ep_loadout_countdown_entries)[1];image.reset_timers=(peers ? ep_loadout_peer_countdown_entries : ep_loadout_countdown_entries)[2];*out=image;
    return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_countdown_build(const EpLoadoutCountdownAddresses* a,EpLoadoutCountdownImage* out)
{return build(a,nullptr,out);}
EpPropertyResult ep_loadout_countdown_build_peers(const EpLoadoutCountdownAddresses* a,const EpPlayerJoinPeers* peers,EpLoadoutCountdownImage* out)
{
    if (!peers) {if (out) *out={};return EP_PROPERTY_ARGUMENT;}
    const auto binding=*peers;return build(a,&binding,out);
}
EpPropertyResult ep_loadout_countdown_prepare(const HfApi* api,HfMod* mod,const EpLoadoutCountdownAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutCountdownAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutCountdownImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.records.common.lifecycle.code,sizeof(ep_loadout_countdown_template),&code)) return EP_PROPERTY_RESERVE;
    a.records.common.lifecycle.code=code.base;EpPropertyResult status=ep_loadout_countdown_build(&a,&image);
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
