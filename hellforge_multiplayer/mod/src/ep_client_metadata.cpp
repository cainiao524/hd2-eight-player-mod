#include "ep_client_metadata.h"
#include <limits.h>
#include <string.h>
struct EpClientMetadataFixup {uint32_t offset,next,key,kind;int64_t add;};
#include "ep_client_metadata_template.h"
EpPropertyResult ep_client_metadata_build(const EpClientMetadataAddresses* input,EpClientMetadataImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpClientMetadataAddresses a={};if (input) a=*input;*out={};
    if (!input || a.reserved || a.capacity<4 || a.capacity>8) return EP_PROPERTY_ARGUMENT;
    if (a.client<0x262c8) return EP_PROPERTY_POINTER;
    const uint64_t regions[][3]={{a.game,74727424,4096},{a.code,4096,16},{a.client-0x162c8,0x20100,8},
        {a.metadata,16ull*a.capacity,16},{a.ready,16ull*a.capacity,16},{a.reject,1,1}};
    for (unsigned i=0;i<6;i++) {
        auto p=regions[i][0],n=regions[i][1];
        if (p<0x10000 || p>(UINT64_C(1)<<47)-n || p%regions[i][2]) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (p<regions[j][0]+regions[j][1] && regions[j][0]<p+n) return EP_PROPERTY_OVERLAP;
    }
    const uint64_t values[]={a.game,a.code,a.client,a.client-0x162c8,a.metadata,a.ready,a.capacity,a.reject};
    EpClientMetadataImage image={};memcpy(image.data,ep_client_metadata_template,sizeof(ep_client_metadata_template));
    for (const auto& f:ep_client_metadata_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)(a.code+f.next);if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        for (unsigned i=0;i<(f.kind==1 ? 8u : 4u);i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(i*8));
    }
    image.bytes=sizeof(ep_client_metadata_template);image.table_offset=ep_client_metadata_table;image.function_count=10;
    memcpy(image.entry,ep_client_metadata_entries,sizeof(image.entry));*out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_client_metadata_prepare(const HfApi* api,HfMod* mod,const EpClientMetadataAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpClientMetadataAddresses a={};if (input) a=*input;*out={};
    if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpClientMetadataImage image={};
    if (!ep_session_code_reserve(api,mod,a.code,sizeof(ep_client_metadata_template),&code)) return EP_PROPERTY_RESERVE;
    a.code=code.base;auto rc=ep_client_metadata_build(&a,&image);
    if (rc==EP_PROPERTY_OK && !ep_session_code_seal_table(mod,code.handle,image.data,image.bytes,image.table_offset,image.function_count)) rc=EP_PROPERTY_SEAL;
    if (rc==EP_PROPERTY_OK && ep_session_code_info(mod,code.handle,out)) return EP_PROPERTY_OK;
    if (rc==EP_PROPERTY_OK) rc=EP_PROPERTY_SEAL;
    if (!ep_session_code_discard(mod,code.handle)) {
        *out=code;EpSessionCodeInfo retained={};if (ep_session_code_info(mod,code.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return rc;
}
