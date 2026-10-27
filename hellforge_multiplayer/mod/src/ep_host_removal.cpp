#include "ep_host_removal.h"
#include <limits.h>
#include <string.h>
struct EpHostRemovalFixup {uint32_t offset,next,key,kind,multiplier;int64_t add;};
#include "ep_host_removal_template.h"
EpPropertyResult ep_host_removal_build(const EpHostLifecycleAddresses* input,EpHostRemovalImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpHostLifecycleAddresses a={};if (input) a=*input;*out={};
    if (!input || a.reserved || a.capacity<4 || a.capacity>8) return EP_PROPERTY_ARGUMENT;
    if (a.client<0x262c8) return EP_PROPERTY_POINTER;
    const uint64_t regions[][3]={{a.game,74727424,4096},{a.code,4096,16},{a.client-0x162c8,0x20100,8},
        {a.confirmed,32ull*a.capacity,16},{a.reject,1,1},{a.peers,56ull*a.capacity,16},
        {a.flags,a.capacity,8},{a.large,448ull*a.capacity,16},{a.pending,64ull*a.capacity,16}};
    for (unsigned i=0;i<9;i++) {
        auto p=regions[i][0],n=regions[i][1];
        if (p<0x10000 || p>(UINT64_C(1)<<47)-n || p%regions[i][2]) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (p<regions[j][0]+regions[j][1] && regions[j][0]<p+n) return EP_PROPERTY_OVERLAP;
    }
    EpHostRemovalImage image={};memcpy(image.data,ep_host_removal_template,sizeof(ep_host_removal_template));
    const uint64_t values[]={a.game,a.client-0x918,a.client-0x162c8,a.confirmed,a.peers,a.flags,a.large,a.pending,a.capacity,a.reject};
    for (const auto& f:ep_host_removal_fixups) {
        int64_t value=(int64_t)(values[f.key]*f.multiplier)+f.add;
        if (!f.kind) {value-=(int64_t)(a.code+f.next);if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        for (unsigned i=0;i<(f.kind==1 ? 8u : 4u);i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(i*8));
    }
    image.bytes=sizeof(ep_host_removal_template);image.table_offset=ep_host_removal_table;image.function_count=9;
    memcpy(image.entry,ep_host_removal_entries,sizeof(image.entry));*out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_host_removal_prepare(const HfApi* api,HfMod* mod,const EpHostLifecycleAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpHostLifecycleAddresses a={};if (input) a=*input;*out={};
    if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpHostRemovalImage image={};
    if (!ep_session_code_reserve(api,mod,a.code,sizeof(ep_host_removal_template),&code)) return EP_PROPERTY_RESERVE;
    a.code=code.base;auto rc=ep_host_removal_build(&a,&image);
    if (rc==EP_PROPERTY_OK && !ep_session_code_seal_table(mod,code.handle,image.data,image.bytes,image.table_offset,image.function_count)) rc=EP_PROPERTY_SEAL;
    if (rc==EP_PROPERTY_OK && ep_session_code_info(mod,code.handle,out)) return EP_PROPERTY_OK;
    if (rc==EP_PROPERTY_OK) rc=EP_PROPERTY_SEAL;
    if (!ep_session_code_discard(mod,code.handle)) {
        *out=code;EpSessionCodeInfo retained={};if (ep_session_code_info(mod,code.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return rc;
}
