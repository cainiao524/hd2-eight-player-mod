#include "ep_client_peers.h"
#include "ep_client_update.h"
#include <limits.h>
#include <string.h>
struct EpClientPeerFixup {uint32_t offset,next,key,kind,multiplier;int64_t add;};
struct EpClientPeerTemplate {
    const uint8_t* data;const EpClientPeerFixup* fixes;
    uint32_t bytes,fixup_count,table,count,handler,source;
};
#include "ep_client_peers_template.h"
EpPropertyResult ep_client_peer_build(uint32_t kind,const EpClientDisconnectAddresses* input,EpClientPeerImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpClientDisconnectAddresses a={};if (input) a=*input;*out={};
    if (!input || kind<1 || kind>EP_CLIENT_PEER_SET_FLAG || a.reserved || a.capacity<4 || a.capacity>8) return EP_PROPERTY_ARGUMENT;
    const uint64_t regions[][3]={{a.game,74727424,4096},{a.code,4096,16},{a.client,0x528,8},
        {a.peers,32ull*a.capacity,16},{a.reject,1,1}};
    for (unsigned i=0;i<5;i++) {
        auto p=regions[i][0],n=regions[i][1];
        if (p<0x10000 || p>(UINT64_C(1)<<47)-n || p%regions[i][2]) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (p<regions[j][0]+regions[j][1] && regions[j][0]<p+n) return EP_PROPERTY_OVERLAP;
    }
    const auto& t=ep_client_peer_templates[kind-1];EpClientPeerImage image={};memcpy(image.data,t.data,t.bytes);
    const uint64_t values[]={a.game,a.client,a.peers,a.capacity,a.reject};
    for (unsigned n=0;n<t.fixup_count;n++) {
        const auto& f=t.fixes[n];int64_t value=(int64_t)(values[f.key]*f.multiplier)+f.add;
        if (!f.kind) {value-=(int64_t)(a.code+f.next);if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        for (unsigned i=0;i<(f.kind==1 ? 8u : 4u);i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(i*8));
    }
    image.bytes=t.bytes;image.table_offset=t.table;image.function_count=t.count;
    image.handler_offset=t.handler;image.body_offset=64;image.source_rva=t.source;*out=image;return EP_PROPERTY_OK;
}
static EpPropertyResult EpPeerPrepare(const HfApi* api,HfMod* owner,uint32_t kind,EpClientDisconnectAddresses a,EpSessionCodeInfo* out)
{
    EpSessionCodeInfo code={};EpClientPeerImage image={};
    if (!ep_session_code_reserve(api,owner,a.code,ep_client_peer_templates[kind-1].bytes,&code)) return EP_PROPERTY_RESERVE;
    a.code=code.base;auto rc=ep_client_peer_build(kind,&a,&image);
    if (rc==EP_PROPERTY_OK) {
        const EpSessionGsCheck gs={1,image.handler_offset,a.game+0x21044a0};
        int ok=kind==EP_CLIENT_PEER_RESET ? ep_session_code_seal_client_peer_reset(owner,code.handle,image.data,image.bytes,image.table_offset,&gs) :
            ep_session_code_seal_table(owner,code.handle,image.data,image.bytes,image.table_offset,image.function_count);
        if (!ok) rc=EP_PROPERTY_SEAL;
    }
    if (rc==EP_PROPERTY_OK && ep_session_code_info(owner,code.handle,out)) return EP_PROPERTY_OK;
    if (rc==EP_PROPERTY_OK) rc=EP_PROPERTY_SEAL;
    if (!ep_session_code_discard(owner,code.handle)) {
        *out=code;EpSessionCodeInfo retained={};if (ep_session_code_info(owner,code.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return rc;
}
int ep_client_peer_family_discard(HfMod* owner,EpClientPeerFamily* family)
{
    if (!family) return 0;int ok=1;
    for (unsigned i=EP_CLIENT_PEER_FAMILY_COUNT;i--;) if (family->code[i].handle) {
        if (ep_session_code_discard(owner,family->code[i].handle)) family->code[i]={};
        else {EpSessionCodeInfo retained={};if (ep_session_code_info(owner,family->code[i].handle,&retained)) family->code[i]=retained;ok=0;}
    }
    return ok;
}
EpPropertyResult ep_client_peer_family_prepare(const HfApi* api,HfMod* owner,const EpClientPeerFamilyAddresses* input,EpClientPeerFamily* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpClientPeerFamilyAddresses a={};if (input) a=*input;*out={};
    if (!input || a.reserved || a.capacity<4 || a.capacity>8) return EP_PROPERTY_ARGUMENT;
    for (unsigned i=0;i<EP_CLIENT_PEER_FAMILY_COUNT;i++) {
        const EpClientDisconnectAddresses at={a.game,a.code[i],a.client,a.peers,a.reject,a.capacity,0};
        auto rc=i==8 ? ep_client_update_prepare(api,owner,&at,&out->code[i]) : i==4 ? ep_client_disconnect_prepare(api,owner,&at,&out->code[i]) :
            EpPeerPrepare(api,owner,i<4 ? i+1 : i,at,&out->code[i]);
        if (rc!=EP_PROPERTY_OK) return ep_client_peer_family_discard(owner,out) ? rc : EP_PROPERTY_CLEANUP;
    }
    return EP_PROPERTY_OK;
}
