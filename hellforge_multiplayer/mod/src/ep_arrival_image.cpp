#include "ep_arrival_image.h"
#include <limits.h>
#include <string.h>
typedef struct EpArrivalFixup { uint16_t offset,next_offset;uint8_t parameter,width;int32_t addend; } EpArrivalFixup;
typedef struct EpArrivalTemplate {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count,fixups;
    const uint8_t* data;const EpArrivalFixup* relocation;
} EpArrivalTemplate;
#include "ep_arrival_templates.h"
static int ArrivalPointer(uint64_t p,uint64_t n,uint64_t alignment)
{return p>=0x10000 && p<=(UINT64_C(1)<<47)-n && !(p%alignment);}
EpPropertyResult ep_arrival_image_build(const EpArrivalAddresses* input,EpArrivalImage* out)
{
    EpArrivalAddresses a;EpArrivalImage result={0};
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out));if (!input) return EP_PROPERTY_ARGUMENT;
    const EpArrivalTemplate* t=&ep_arrival_templates[0];
    if (!ArrivalPointer(a.game_base,74727424,4096) || !ArrivalPointer(a.code_address,t->bytes,16) ||
        !ArrivalPointer(a.roster_address,0x428,8) || !ArrivalPointer(a.storage_address,0x680,16) ||
        !ArrivalPointer(a.reject_address,1,1)) return EP_PROPERTY_POINTER;
    uint64_t regions[][2]={{a.code_address,t->bytes},{a.roster_address,0x428},{a.storage_address,0x680},
        {a.reject_address,1},{a.game_base,74727424}};
    const unsigned count=5;
    for (unsigned i=0;i<count;i++) for (unsigned j=0;j<i;j++)
        if (regions[i][0]<regions[j][0]+regions[j][1] && regions[j][0]<regions[i][0]+regions[i][1]) return EP_PROPERTY_OVERLAP;
    const uint64_t values[]={a.game_base,a.code_address,a.roster_address,a.storage_address,a.reject_address};
    memcpy(result.data,t->data,t->bytes);
    for (unsigned i=0;i<t->fixups;i++) {
        const EpArrivalFixup* f=&t->relocation[i];int64_t value=(int64_t)values[f->parameter]+f->addend;
        if (f->width==4) {
            value-=(int64_t)(a.code_address+f->next_offset);
            if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;
        }
        for (unsigned j=0;j<f->width;j++) result.data[f->offset+j]=(uint8_t)((uint64_t)value>>(8*j));
    }
    result.bytes=t->bytes;result.code_bytes=t->code_bytes;result.unwind_offset=t->unwind_offset;
    result.table_offset=t->table_offset;result.function_count=t->function_count;*out=result;return EP_PROPERTY_OK;
}
EpPropertyResult ep_arrival_code_prepare(const HfApi* api,HfMod* owner,const EpArrivalAddresses* input,EpSessionCodeInfo* out)
{
    EpArrivalAddresses a;EpArrivalImage image;EpSessionCodeInfo allocation={0};EpPropertyResult result;
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out));if (!input) return EP_PROPERTY_ARGUMENT;
    if (!ep_session_code_reserve(api,owner,(uintptr_t)a.code_address,ep_arrival_templates[0].bytes,&allocation)) return EP_PROPERTY_RESERVE;
    a.code_address=allocation.base;result=ep_arrival_image_build(&a,&image);
    const EpSessionGsCheck gs={1,1920,(uintptr_t)a.game_base+0x21044a0};
    if (result==EP_PROPERTY_OK && !ep_session_code_seal_gs_table(owner,allocation.handle,image.data,image.bytes,image.table_offset,image.function_count,&gs)) result=EP_PROPERTY_SEAL;
    if (result==EP_PROPERTY_OK) { if (ep_session_code_info(owner,allocation.handle,out)) return EP_PROPERTY_OK;result=EP_PROPERTY_SEAL; }
    if (!ep_session_code_discard(owner,allocation.handle)) {
        EpSessionCodeInfo retained;*out=allocation;
        if (ep_session_code_info(owner,allocation.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return result;
}
