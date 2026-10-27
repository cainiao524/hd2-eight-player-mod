#include "ep_loadout_setup.h"
#include <limits.h>
#include <math.h>
#include <string.h>
struct EpLoadoutSetupFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_loadout_setup_template.h"
#include "ep_loadout_peer_setup_template.h"
static EpPropertyResult build(const EpLoadoutSetupAddresses* input,const EpPlayerJoinPeers* peers,EpLoadoutSetupImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutSetupAddresses a={};if (input) a=*input;*out={};
    EpPropertyResult status=ep_loadout_consumers_validate(input ? &a.common : nullptr);if (status!=EP_PROPERTY_OK) return status;
    const auto& b=a.common;const auto& l=b.lifecycle;
    if (peers) {
        auto peer_result=ep_loadout_consumer_peers_validate(&b,peers,EP_LOADOUT_SETUP_BYTES);
        if (peer_result!=EP_PROPERTY_OK) return peer_result;
    }
    for (uint32_t i=0;i<l.capacity;i++) {
        const auto& p=a.placements[i];const float values[]={p.offset_x,p.offset_y,p.anchor_x,p.anchor_y,p.pivot_x,p.pivot_y};
        for (unsigned j=0;j<6;j++) if (!isfinite(values[j]) || (j>=2 && (values[j]<0 || values[j]>1))) return EP_PROPERTY_ARGUMENT;
    }
    const uint32_t bytes=peers ? sizeof(ep_loadout_peer_setup_template) : sizeof(ep_loadout_setup_template);
    EpLoadoutSetupImage image={};memcpy(image.data,peers ? ep_loadout_peer_setup_template : ep_loadout_setup_template,bytes);
    const uint64_t values[]={l.game,l.code,l.screen,l.records,l.widgets,l.capacity,l.reject,b.forward_map,b.inverse_map,b.roster,b.roster_storage,peers ? peers->client : 0,peers ? peers->bank : 0};
    const auto* fixes=peers ? ep_loadout_peer_setup_fixups : ep_loadout_setup_fixups;
    const unsigned count=peers ? sizeof(ep_loadout_peer_setup_fixups)/sizeof(*fixes) : sizeof(ep_loadout_setup_fixups)/sizeof(*fixes);
    for (unsigned index=0;index<count;index++) {const auto& f=fixes[index];
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)l.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        for (unsigned i=0;i<(f.kind==1 ? 8u : 4u);i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    static_assert(sizeof(EpLoadoutPlacement)==24,"Native placement ABI");
    memcpy(image.data+(peers ? ep_loadout_peer_setup_placements_offset : ep_loadout_setup_placements_offset),a.placements,l.capacity*sizeof(EpLoadoutPlacement));
    image.bytes=bytes;image.code_bytes=(peers ? ep_loadout_peer_setup_code_bytes : ep_loadout_setup_code_bytes);
    image.unwind_offset=(peers ? ep_loadout_peer_setup_unwind_offset : ep_loadout_setup_unwind_offset);image.table_offset=(peers ? ep_loadout_peer_setup_table_offset : ep_loadout_setup_table_offset);
    image.handler_offset=(peers ? ep_loadout_peer_setup_handler_offset : ep_loadout_setup_handler_offset);image.placements_offset=(peers ? ep_loadout_peer_setup_placements_offset : ep_loadout_setup_placements_offset);
    image.attach_widgets=(peers ? ep_loadout_peer_setup_attach_widgets : ep_loadout_setup_attach_widgets);
    image.replace_widgets=(peers ? ep_loadout_peer_setup_replace_widgets : ep_loadout_setup_replace_widgets);
    *out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_setup_build(const EpLoadoutSetupAddresses* a,EpLoadoutSetupImage* out)
{return build(a,nullptr,out);}
EpPropertyResult ep_loadout_setup_build_peers(const EpLoadoutSetupAddresses* a,const EpPlayerJoinPeers* peers,EpLoadoutSetupImage* out)
{
    if (!peers) {if (out) *out={};return EP_PROPERTY_ARGUMENT;}
    const auto binding=*peers;return build(a,&binding,out);
}
EpPropertyResult ep_loadout_setup_prepare(const HfApi* api,HfMod* mod,const EpLoadoutSetupAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutSetupAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutSetupImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.common.lifecycle.code,sizeof(ep_loadout_setup_template),&code)) return EP_PROPERTY_RESERVE;
    a.common.lifecycle.code=code.base;EpPropertyResult status=ep_loadout_setup_build(&a,&image);
    const EpSessionGsCheck gs={1,image.handler_offset,a.common.lifecycle.game+0x21044a0};
    if (status==EP_PROPERTY_OK && !ep_session_code_seal_loadout_setup(mod,code.handle,image.data,image.bytes,image.table_offset,&gs)) status=EP_PROPERTY_SEAL;
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
