#include "ep_property_code.h"
#include <string.h>
EpPropertyResult ep_property_code_prepare(const HfApi* api, HfMod* owner, uint32_t kind,
                                         const EpPropertyAddresses* input, EpSessionCodeInfo* out)
{
    EpPropertyAddresses addresses;
    EpPropertyImage image;
    EpSessionCodeInfo allocation={0};
    EpPropertyResult result;
    uint32_t bytes;
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) addresses=*input;
    memset(out,0,sizeof(*out));
    if (!input || (kind!=EP_PROPERTY_PRODUCER && kind!=EP_PROPERTY_RECEIVER)) return EP_PROPERTY_ARGUMENT;
    bytes=kind==EP_PROPERTY_PRODUCER ? 708 : 436;
    if (!ep_session_code_reserve(api,owner,(uintptr_t)addresses.code_address,bytes,&allocation)) return EP_PROPERTY_RESERVE;
    addresses.code_address=allocation.base;
    result=ep_property_image_build(kind,&addresses,&image);
    if (result==EP_PROPERTY_OK && !ep_session_code_seal(owner,allocation.handle,image.data,image.bytes,image.table_offset)) result=EP_PROPERTY_SEAL;
    if (result==EP_PROPERTY_OK) {
        if (ep_session_code_info(owner,allocation.handle,out)) return EP_PROPERTY_OK;
        result=EP_PROPERTY_SEAL;
    }
    if (!ep_session_code_discard(owner,allocation.handle)) {
        EpSessionCodeInfo retained;
        *out=allocation;
        if (ep_session_code_info(owner,allocation.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return result;
}
