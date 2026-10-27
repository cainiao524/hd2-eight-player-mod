#include "ep_loadout_mode.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutModeFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_mode_template.h"
#include "ep_loadout_peer_mode_template.h"
static EpPropertyResult build(const EpLoadoutConsumerAddresses* input,const EpPlayerJoinPeers* peers,EpLoadoutModeImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutConsumerAddresses a={};if (input) a=*input;*out={};
    EpPropertyResult result=ep_loadout_consumers_validate_span(input ? &a : nullptr,EP_LOADOUT_MODE_BYTES);
    if (result!=EP_PROPERTY_OK) return result;
    const auto& l=a.lifecycle;
    if (peers) {
        auto peer_result=ep_loadout_consumer_peers_validate(&a,peers,EP_LOADOUT_MODE_BYTES);
        if (peer_result!=EP_PROPERTY_OK) return peer_result;
    }
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,
        a.forward_map,a.inverse_map,a.roster,a.roster_storage,peers ? peers->client : 0,peers ? peers->bank : 0};
    const uint32_t bytes=peers ? sizeof(ep_loadout_peer_mode_template) : sizeof(ep_loadout_mode_template);
    EpLoadoutModeImage image={};memcpy(image.data,peers ? ep_loadout_peer_mode_template : ep_loadout_mode_template,bytes);
    const auto* fixes=peers ? ep_loadout_peer_mode_fixups : ep_loadout_mode_fixups;
    const unsigned count=peers ? sizeof(ep_loadout_peer_mode_fixups)/sizeof(*fixes) : sizeof(ep_loadout_mode_fixups)/sizeof(*fixes);
    for (unsigned index=0;index<count;index++) {const auto& f=fixes[index];
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        if (f.kind==3) value-=(int64_t)l.screen;
        for (unsigned i=0;i<(f.kind==1 || f.kind==3 ? 8u : 4u);i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.bytes=bytes;image.code_bytes=(peers ? ep_loadout_peer_mode_code_bytes : ep_loadout_mode_code_bytes);
    image.unwind_offset=(peers ? ep_loadout_peer_mode_unwind_offset : ep_loadout_mode_unwind_offset);image.table_offset=(peers ? ep_loadout_peer_mode_table_offset : ep_loadout_mode_table_offset);
    image.handler_offset=(peers ? ep_loadout_peer_mode_handler_offset : ep_loadout_mode_handler_offset);image.mode=(peers ? ep_loadout_peer_mode_entries : ep_loadout_mode_entries)[0];
    image.open=(peers ? ep_loadout_peer_mode_entries : ep_loadout_mode_entries)[1];*out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_mode_build(const EpLoadoutConsumerAddresses* a,EpLoadoutModeImage* out)
{return build(a,nullptr,out);}
EpPropertyResult ep_loadout_mode_build_peers(const EpLoadoutConsumerAddresses* a,const EpPlayerJoinPeers* peers,EpLoadoutModeImage* out)
{
    if (!peers) {if (out) *out={};return EP_PROPERTY_ARGUMENT;}
    const auto binding=*peers;return build(a,&binding,out);
}
EpPropertyResult ep_loadout_mode_prepare(const HfApi* api,HfMod* mod,const EpLoadoutConsumerAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutConsumerAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutModeImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.lifecycle.code,sizeof(ep_loadout_mode_template),&code)) return EP_PROPERTY_RESERVE;
    a.lifecycle.code=code.base;EpPropertyResult result=ep_loadout_mode_build(&a,&image);
    const EpSessionGsCheck gs={1,image.handler_offset,a.lifecycle.game+0x21044a0};
    if (result==EP_PROPERTY_OK && !ep_session_code_seal_loadout_mode(mod,code.handle,image.data,image.bytes,image.table_offset,&gs)) result=EP_PROPERTY_SEAL;
    if (result==EP_PROPERTY_OK) {if (ep_session_code_info(mod,code.handle,out)) return EP_PROPERTY_OK;result=EP_PROPERTY_SEAL;}
    if (!ep_session_code_discard(mod,code.handle)) {
        *out=code;EpSessionCodeInfo retained={};if (ep_session_code_info(mod,code.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return result;
}
