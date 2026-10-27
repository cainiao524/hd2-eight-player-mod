#include "ep_host_accept.h"
#include <limits.h>
#include <string.h>
struct EpHostAcceptFixup {uint32_t offset,next,key,kind,multiplier;int64_t add;};
#include "ep_host_accept_template.h"
EpPropertyResult ep_host_accept_build(const EpHostAcceptAddresses* input,EpHostAcceptImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpHostAcceptAddresses a={};if (input) a=*input;*out={};
    const auto& h=a.host;
    if (!input || h.reserved || h.capacity<4 || h.capacity>8) return EP_PROPERTY_ARGUMENT;
    if (h.client<0x262c8) return EP_PROPERTY_POINTER;
    const uint64_t regions[][3]={{h.game,74727424,4096},{h.code,4096,16},{h.client-0x162c8,0x20100,8},
        {h.confirmed,32ull*h.capacity,16},{h.reject,1,1},{h.peers,56ull*h.capacity,16},
        {h.flags,h.capacity,8},{h.large,uint64_t(EP_HOST_TASK_STRIDE)*h.capacity,16},
        {h.pending,uint64_t(EP_HOST_PENDING_STRIDE)*h.capacity,16},{a.metadata,16ull*h.capacity,16},{a.remove_data,1,1},{a.registered_insert,1,1}};
    for (unsigned i=0;i<12;i++) {
        auto p=regions[i][0],n=regions[i][1];
        if (p<0x10000 || p>(UINT64_C(1)<<47)-n || p%regions[i][2]) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (p<regions[j][0]+regions[j][1] && regions[j][0]<p+n) return EP_PROPERTY_OVERLAP;
    }
    const uint64_t values[]={h.game,h.client-0x918,h.client-0x162c8,h.confirmed,h.peers,h.flags,h.large,h.pending,h.capacity,h.reject,
        a.metadata,a.remove_data,a.registered_insert,h.client};
    EpHostAcceptImage image={};memcpy(image.data,ep_host_accept_template,sizeof(ep_host_accept_template));
    for (const auto& f:ep_host_accept_fixups) {
        int64_t value=(int64_t)(values[f.key]*f.multiplier)+f.add;
        if (!f.kind) {value-=(int64_t)(h.code+f.next);if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        for (unsigned i=0;i<(f.kind==1 ? 8u : 4u);i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(i*8));
    }
    image.bytes=sizeof(ep_host_accept_template);image.table_offset=ep_host_accept_table;
    image.function_count=13;image.handler_offset=ep_host_accept_handler;
    memcpy(image.entry,ep_host_accept_entries,sizeof(image.entry));*out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_host_accept_prepare(const HfApi* api,HfMod* mod,const EpHostAcceptAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpHostAcceptAddresses a={};if (input) a=*input;*out={};
    if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpHostAcceptImage image={};
    if (!ep_session_code_reserve(api,mod,a.host.code,sizeof(ep_host_accept_template),&code)) return EP_PROPERTY_RESERVE;
    a.host.code=code.base;auto rc=ep_host_accept_build(&a,&image);
    if (rc==EP_PROPERTY_OK) {
        const EpSessionGsCheck gs={1,image.handler_offset,a.host.game+0x21044a0};
        if (!ep_session_code_seal_host_accept(mod,code.handle,image.data,image.bytes,image.table_offset,&gs)) rc=EP_PROPERTY_SEAL;
    }
    if (rc==EP_PROPERTY_OK && ep_session_code_info(mod,code.handle,out)) return EP_PROPERTY_OK;
    if (rc==EP_PROPERTY_OK) rc=EP_PROPERTY_SEAL;
    if (!ep_session_code_discard(mod,code.handle)) {
        *out=code;EpSessionCodeInfo retained={};if (ep_session_code_info(mod,code.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return rc;
}
