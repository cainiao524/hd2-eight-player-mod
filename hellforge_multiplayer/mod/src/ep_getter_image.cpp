#include "ep_getter_image.h"
#include <limits.h>
#include <string.h>
typedef struct EpGetterFixup {
    uint16_t offset,next_offset;
    uint8_t parameter,width;
    int32_t addend;
} EpGetterFixup;
#include "ep_getter_template.h"
static_assert(EP_GETTER_IMAGE_BYTES<=sizeof(((EpPropertyImage*)0)->data),"Getter exceeds image storage");
static int GetterPointer(uint64_t p,uint64_t n,uint64_t alignment)
{ return p && p<(UINT64_C(1)<<47) && !(p%alignment) && n<=(UINT64_C(1)<<47)-p; }
EpPropertyResult ep_getter_image_build(const EpGetterAddresses* input,EpPropertyImage* out)
{
    EpGetterAddresses a; EpPropertyImage result={0};
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out)); if (!input) return EP_PROPERTY_ARGUMENT;
    if (!GetterPointer(a.game_base,0x3483C24,4096) || !GetterPointer(a.code_address,EP_GETTER_IMAGE_BYTES,16) ||
        !GetterPointer(a.roster_address,0x428,8) || !GetterPointer(a.storage_address,0x680,16) ||
        !GetterPointer(a.reject_address,1,1)) return EP_PROPERTY_POINTER;
    uint64_t regions[][2]={{a.code_address,EP_GETTER_IMAGE_BYTES},{a.roster_address,0x428},{a.storage_address,0x680},
        {a.reject_address,1},{a.game_base+0x606AD0,165},{a.game_base+0x3326468,8},{a.game_base+0x3483C20,4}};
    for (unsigned i=0;i<7;i++) for (unsigned j=i+1;j<7;j++)
        if (regions[i][0]<regions[j][0]+regions[j][1] && regions[j][0]<regions[i][0]+regions[i][1]) return EP_PROPERTY_OVERLAP;
    uint64_t values[]={a.game_base,a.code_address,a.roster_address,a.storage_address,a.reject_address};
    memcpy(result.data,ep_getter_template,EP_GETTER_IMAGE_BYTES);
    for (unsigned i=0;i<sizeof(ep_getter_fixups)/sizeof(*ep_getter_fixups);i++) {
        const EpGetterFixup* f=&ep_getter_fixups[i];
        int64_t value=(int64_t)values[f->parameter]+f->addend;
        if (f->width==4) {
            value-=(int64_t)(a.code_address+f->next_offset);
            if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;
        }
        for (unsigned j=0;j<f->width;j++) result.data[f->offset+j]=(uint8_t)((uint64_t)value>>(8*j));
    }
    result.bytes=EP_GETTER_IMAGE_BYTES; result.code_bytes=EP_GETTER_CODE_BYTES;
    result.unwind_offset=EP_GETTER_UNWIND_OFFSET; result.table_offset=EP_GETTER_TABLE_OFFSET;
    *out=result; return EP_PROPERTY_OK;
}
EpPropertyResult ep_getter_code_prepare(const HfApi* api,HfMod* owner,const EpGetterAddresses* input,EpSessionCodeInfo* out)
{
    EpGetterAddresses a; EpPropertyImage image; EpSessionCodeInfo allocation={0}; EpPropertyResult result;
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out)); if (!input) return EP_PROPERTY_ARGUMENT;
    if (!ep_session_code_reserve(api,owner,(uintptr_t)a.code_address,EP_GETTER_IMAGE_BYTES,&allocation)) return EP_PROPERTY_RESERVE;
    a.code_address=allocation.base; result=ep_getter_image_build(&a,&image);
    if (result==EP_PROPERTY_OK && !ep_session_code_seal(owner,allocation.handle,image.data,image.bytes,image.table_offset)) result=EP_PROPERTY_SEAL;
    if (result==EP_PROPERTY_OK) {
        if (ep_session_code_info(owner,allocation.handle,out)) return EP_PROPERTY_OK;
        result=EP_PROPERTY_SEAL;
    }
    if (!ep_session_code_discard(owner,allocation.handle)) {
        EpSessionCodeInfo retained; *out=allocation;
        if (ep_session_code_info(owner,allocation.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return result;
}
