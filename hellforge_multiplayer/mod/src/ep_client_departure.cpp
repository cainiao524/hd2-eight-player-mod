#include "ep_client_departure.h"
#include <limits.h>
#include <string.h>
struct EpClientDepartureFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_client_departure_template.h"
EpPropertyResult ep_client_departure_build(const EpClientDepartureAddresses* input,EpClientDepartureImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpClientDepartureAddresses a={};if (input) a=*input;*out={};const auto& c=a.client;
    if (!input || c.reserved || c.capacity<4 || c.capacity>8) return EP_PROPERTY_ARGUMENT;
    if (c.client<0x262c8) return EP_PROPERTY_POINTER;
    const uint64_t regions[][3]={{c.game,74727424,4096},{c.code,4096,16},{c.client-0x162c8,0x20100,8},
        {c.peers,32ull*c.capacity,16},{c.reject,1,1},{a.ready,16ull*c.capacity,16},{a.ids,8ull*c.capacity,8},
        {a.history,16ull*c.capacity,16},{a.metadata,16ull*c.capacity,16},{a.slots,24ull*c.capacity,8},{a.ready_finish,1,1}};
    for (unsigned i=0;i<11;i++) {
        auto p=regions[i][0],n=regions[i][1];
        if (p<0x10000 || p>(UINT64_C(1)<<47)-n || p%regions[i][2]) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (p<regions[j][0]+regions[j][1] && regions[j][0]<p+n) return EP_PROPERTY_OVERLAP;
    }
    const uint64_t values[]={c.game,c.client,c.peers,c.capacity,c.reject,a.ready,a.ids,a.history,a.metadata,a.slots,a.ready_finish,c.client-0x162c8};
    EpClientDepartureImage image={};memcpy(image.data,ep_client_departure_template,sizeof(ep_client_departure_template));
    for (const auto& f:ep_client_departure_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)(c.code+f.next);if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        for (unsigned i=0;i<(f.kind==1 ? 8u : 4u);i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(i*8));
    }
    image.bytes=sizeof(ep_client_departure_template);image.table_offset=ep_client_departure_table;image.function_count=5;image.body_offset=ep_client_departure_body;
    *out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_client_departure_prepare(const HfApi* api,HfMod* mod,const EpClientDepartureAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpClientDepartureAddresses a={};if (input) a=*input;*out={};
    if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpClientDepartureImage image={};
    if (!ep_session_code_reserve(api,mod,a.client.code,sizeof(ep_client_departure_template),&code)) return EP_PROPERTY_RESERVE;
    a.client.code=code.base;auto rc=ep_client_departure_build(&a,&image);
    if (rc==EP_PROPERTY_OK && !ep_session_code_seal_table(mod,code.handle,image.data,image.bytes,image.table_offset,image.function_count)) rc=EP_PROPERTY_SEAL;
    if (rc==EP_PROPERTY_OK && ep_session_code_info(mod,code.handle,out)) return EP_PROPERTY_OK;
    if (rc==EP_PROPERTY_OK) rc=EP_PROPERTY_SEAL;
    if (!ep_session_code_discard(mod,code.handle)) {
        *out=code;EpSessionCodeInfo retained={};if (ep_session_code_info(mod,code.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return rc;
}
