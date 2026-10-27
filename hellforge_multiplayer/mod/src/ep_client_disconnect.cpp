#include "ep_client_disconnect.h"
#include <limits.h>
#include <string.h>
struct EpClientDisconnectFixup {uint32_t offset,next,key,kind,multiplier;int64_t add;};
#include "ep_client_disconnect_template.h"
EpPropertyResult ep_client_disconnect_build(const EpClientDisconnectAddresses* input,EpClientDisconnectImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpClientDisconnectAddresses a={};if (input) a=*input;*out={};
    if (!input || a.reserved || a.capacity<4 || a.capacity>8) return EP_PROPERTY_ARGUMENT;
    const uint64_t regions[][3]={{a.game,74727424,4096},{a.code,4096,16},{a.client,0x528,8},
        {a.peers,32ull*a.capacity,16},{a.reject,1,1}};
    for (unsigned i=0;i<5;i++) {
        auto p=regions[i][0],n=regions[i][1];
        if (p<0x10000 || p>(UINT64_C(1)<<47)-n || p%regions[i][2]) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (p<regions[j][0]+regions[j][1] && regions[j][0]<p+n) return EP_PROPERTY_OVERLAP;
    }
    EpClientDisconnectImage image={};memcpy(image.data,ep_client_disconnect_template,sizeof(ep_client_disconnect_template));
    const uint64_t values[]={a.game,a.client,a.peers,a.capacity,a.reject};
    for (const auto& f:ep_client_disconnect_fixups) {
        int64_t value=(int64_t)(values[f.key]*f.multiplier)+f.add;
        if (!f.kind) {value-=(int64_t)(a.code+f.next);if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        for (unsigned i=0;i<(f.kind==1 ? 8u : 4u);i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(i*8));
    }
    image.bytes=sizeof(ep_client_disconnect_template);image.table_offset=ep_client_disconnect_table;
    image.function_count=11;image.handler_offset=ep_client_disconnect_handler;
    image.body_offset=ep_client_disconnect_body;image.lookup_offset=ep_client_disconnect_lookup;
    *out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_client_disconnect_prepare(const HfApi* api,HfMod* owner,const EpClientDisconnectAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpClientDisconnectAddresses a={};if (input) a=*input;*out={};
    if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpClientDisconnectImage image={};
    if (!ep_session_code_reserve(api,owner,a.code,sizeof(ep_client_disconnect_template),&code)) return EP_PROPERTY_RESERVE;
    a.code=code.base;auto rc=ep_client_disconnect_build(&a,&image);
    const EpSessionGsCheck gs={1,image.handler_offset,a.game+0x21044a0};
    if (rc==EP_PROPERTY_OK && !ep_session_code_seal_client_disconnect(owner,code.handle,image.data,image.bytes,image.table_offset,&gs)) rc=EP_PROPERTY_SEAL;
    if (rc==EP_PROPERTY_OK && ep_session_code_info(owner,code.handle,out)) return EP_PROPERTY_OK;
    if (rc==EP_PROPERTY_OK) rc=EP_PROPERTY_SEAL;
    if (!ep_session_code_discard(owner,code.handle)) {
        *out=code;EpSessionCodeInfo retained={};
        if (ep_session_code_info(owner,code.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return rc;
}
