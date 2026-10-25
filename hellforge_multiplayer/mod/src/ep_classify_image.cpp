#include "ep_classify_image.h"
#include <limits.h>
#include <string.h>
typedef struct EpClassifyFixup {
    uint16_t offset,next_offset;
    uint8_t parameter,width;
    int32_t addend;
} EpClassifyFixup;
typedef struct EpClassifyTemplate {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,original_rva,original_bytes,fixups;
    const uint8_t* data;
    const EpClassifyFixup* relocation;
} EpClassifyTemplate;
#include "ep_classify_templates.h"
static int ClassifyPointer(uint64_t p,uint64_t n,uint64_t alignment)
{ return p && p<(UINT64_C(1)<<47) && !(p%alignment) && n<=(UINT64_C(1)<<47)-p; }
EpPropertyResult ep_classify_image_build(uint32_t kind,const EpClassifyAddresses* input,EpClassifyImage* out)
{
    EpClassifyAddresses a; EpClassifyImage result={0};
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out));
    if (!input || kind<1 || kind>2) return EP_PROPERTY_ARGUMENT;
    const EpClassifyTemplate* t=&ep_classify_templates[kind-1];
    if (t->bytes>sizeof(result.data)) return EP_PROPERTY_ARGUMENT;
    if (!ClassifyPointer(a.game_base,0x3483C24,4096) || !ClassifyPointer(a.code_address,t->bytes,16) ||
        !ClassifyPointer(a.roster_address,0x428,8) || !ClassifyPointer(a.storage_address,0x680,16) || a.storage_address<0xE8 || !ClassifyPointer(a.reject_address,1,1)) return EP_PROPERTY_POINTER;
    uint64_t regions[][2]={{a.code_address,t->bytes},{a.roster_address,0x428},{a.storage_address,0x680},{a.reject_address,1},
        {a.game_base+0x3326468,8},{a.game_base+0x3483C20,4},{a.game_base+0x173B6F0,0x104},
        {a.game_base+0x173B8D0,0x182},{a.game_base+0x173BC20,0x77},{0,0},{0,0}};
    for (unsigned i=0;i<2;i++) { regions[9+i][0]=a.game_base+ep_classify_templates[i].original_rva; regions[9+i][1]=ep_classify_templates[i].original_bytes; }
    for (unsigned i=0;i<11;i++) for (unsigned j=i+1;j<11;j++)
        if (regions[i][0]<regions[j][0]+regions[j][1] && regions[j][0]<regions[i][0]+regions[i][1]) return EP_PROPERTY_OVERLAP;
    uint64_t values[]={a.game_base,a.code_address,a.roster_address,a.storage_address,a.reject_address};
    memcpy(result.data,t->data,t->bytes);
    for (unsigned i=0;i<t->fixups;i++) {
        const EpClassifyFixup* f=&t->relocation[i];int64_t value=(int64_t)values[f->parameter]+f->addend;
        if (f->width==4) {
            value-=(int64_t)(a.code_address+f->next_offset);
            if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;
        }
        for (unsigned j=0;j<f->width;j++) result.data[f->offset+j]=(uint8_t)((uint64_t)value>>(8*j));
    }
    result.bytes=t->bytes;result.code_bytes=t->code_bytes;result.unwind_offset=t->unwind_offset;result.table_offset=t->table_offset;
    *out=result;return EP_PROPERTY_OK;
}
EpPropertyResult ep_classify_code_prepare(const HfApi* api,HfMod* owner,uint32_t kind,const EpClassifyAddresses* input,EpSessionCodeInfo* out)
{
    EpClassifyAddresses a;EpClassifyImage image;EpSessionCodeInfo allocation={0};EpPropertyResult result;
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out));if (!input || kind<1 || kind>2) return EP_PROPERTY_ARGUMENT;
    if (!ep_session_code_reserve(api,owner,(uintptr_t)a.code_address,ep_classify_templates[kind-1].bytes,&allocation)) return EP_PROPERTY_RESERVE;
    a.code_address=allocation.base;result=ep_classify_image_build(kind,&a,&image);
    if (result==EP_PROPERTY_OK && !ep_session_code_seal_table(owner,allocation.handle,image.data,image.bytes,image.table_offset,2)) result=EP_PROPERTY_SEAL;
    if (result==EP_PROPERTY_OK) {
        if (ep_session_code_info(owner,allocation.handle,out)) return EP_PROPERTY_OK;
        result=EP_PROPERTY_SEAL;
    }
    if (!ep_session_code_discard(owner,allocation.handle)) {
        EpSessionCodeInfo retained;*out=allocation;
        if (ep_session_code_info(owner,allocation.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return result;
}
