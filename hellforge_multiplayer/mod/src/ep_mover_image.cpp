#include "ep_mover_image.h"
#include <limits.h>
#include <string.h>
typedef struct EpMoverFixup {
    uint16_t offset,next_offset;
    uint8_t parameter,width;
    int32_t addend;
} EpMoverFixup;
#include "ep_mover_template.h"
static_assert(EP_MOVER_IMAGE_BYTES<=sizeof(((EpPropertyImage*)0)->data),"Mover exceeds image storage");
static int MoverPointer(uint64_t p,uint64_t n,uint64_t alignment)
{ return p && p<(UINT64_C(1)<<47) && !(p%alignment) && n<=(UINT64_C(1)<<47)-p; }
EpPropertyResult ep_mover_image_build(const EpMoverAddresses* input,EpPropertyImage* out)
{
    EpMoverAddresses a; EpPropertyImage result={0};
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out)); if (!input) return EP_PROPERTY_ARGUMENT;
    if (!MoverPointer(a.game_base,0x60C5BE,4096) || !MoverPointer(a.code_address,EP_MOVER_IMAGE_BYTES,16) ||
        !MoverPointer(a.roster_address,0x428,8) || !MoverPointer(a.storage_address,0x680,16) ||
        a.storage_address<0xE8 || !MoverPointer(a.reject_address,1,1)) return EP_PROPERTY_POINTER;
    uint64_t regions[][2]={{a.code_address,EP_MOVER_IMAGE_BYTES},{a.roster_address,0x428},{a.storage_address,0x680},
        {a.reject_address,1},{a.game_base+0x60C410,430}};
    for (unsigned i=0;i<5;i++) for (unsigned j=i+1;j<5;j++)
        if (regions[i][0]<regions[j][0]+regions[j][1] && regions[j][0]<regions[i][0]+regions[i][1]) return EP_PROPERTY_OVERLAP;
    uint64_t values[]={a.game_base,a.code_address,a.roster_address,a.storage_address,a.reject_address};
    memcpy(result.data,ep_mover_template,EP_MOVER_IMAGE_BYTES);
    for (unsigned i=0;i<sizeof(ep_mover_fixups)/sizeof(*ep_mover_fixups);i++) {
        const EpMoverFixup* f=&ep_mover_fixups[i];
        int64_t value=(int64_t)values[f->parameter]+f->addend;
        if (f->width==4) {
            value-=(int64_t)(a.code_address+f->next_offset);
            if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;
        }
        for (unsigned j=0;j<f->width;j++) result.data[f->offset+j]=(uint8_t)((uint64_t)value>>(8*j));
    }
    result.bytes=EP_MOVER_IMAGE_BYTES; result.code_bytes=EP_MOVER_CODE_BYTES;
    result.unwind_offset=EP_MOVER_UNWIND_OFFSET; result.table_offset=EP_MOVER_TABLE_OFFSET;
    *out=result; return EP_PROPERTY_OK;
}
EpPropertyResult ep_mover_code_prepare(const HfApi* api,HfMod* owner,const EpMoverAddresses* input,EpSessionCodeInfo* out)
{
    EpMoverAddresses a; EpPropertyImage image; EpSessionCodeInfo allocation={0}; EpPropertyResult result;
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out)); if (!input) return EP_PROPERTY_ARGUMENT;
    if (!ep_session_code_reserve(api,owner,(uintptr_t)a.code_address,EP_MOVER_IMAGE_BYTES,&allocation)) return EP_PROPERTY_RESERVE;
    a.code_address=allocation.base; result=ep_mover_image_build(&a,&image);
    if (result==EP_PROPERTY_OK && !ep_session_code_seal_table(owner,allocation.handle,image.data,image.bytes,image.table_offset,2)) result=EP_PROPERTY_SEAL;
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
