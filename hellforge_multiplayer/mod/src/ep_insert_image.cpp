#include "ep_insert_image.h"
#include <limits.h>
#include <string.h>
typedef struct EpInsertFixup {
    uint16_t offset,next_offset;
    uint8_t parameter,width;
    int32_t addend;
} EpInsertFixup;
typedef struct EpInsertTemplate {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,original_rva,original_bytes,fixups;
    const uint8_t* data;
    const EpInsertFixup* relocation;
} EpInsertTemplate;
#include "ep_insert_templates.h"
static int InsertPointer(uint64_t p,uint64_t n,uint64_t alignment)
{ return p && p<(UINT64_C(1)<<47) && !(p%alignment) && n<=(UINT64_C(1)<<47)-p; }
EpPropertyResult ep_insert_image_build(uint32_t kind,const EpInsertAddresses* input,EpPropertyImage* out)
{
    EpInsertAddresses a; EpPropertyImage result={0};
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out));
    if (!input || kind<1 || kind>4) return EP_PROPERTY_ARGUMENT;
    const EpInsertTemplate* t=&ep_insert_templates[kind-1];
    if (t->bytes>sizeof(result.data)) return EP_PROPERTY_ARGUMENT;
    if (!InsertPointer(a.game_base,0x3326470,4096) || !InsertPointer(a.code_address,t->bytes,16) ||
        !InsertPointer(a.roster_address,0x428,8) || !InsertPointer(a.storage_address,0x680,16) || a.storage_address<0xE8 ||
        !InsertPointer(a.move_code_address,EP_INSERT_MOVER_BYTES,16) || !InsertPointer(a.reject_address,1,1)) return EP_PROPERTY_POINTER;
    uint64_t regions[][2]={{a.code_address,t->bytes},{a.roster_address,0x428},{a.storage_address,0x680},{a.reject_address,1},
        {a.move_code_address,EP_INSERT_MOVER_BYTES},{a.game_base+0x3326468,8},{a.game_base+0x172F790,110},
        {a.game_base+0x60C410,430},{0,0},{0,0},{0,0},{0,0}};
    for (unsigned i=0;i<4;i++) { regions[8+i][0]=a.game_base+ep_insert_templates[i].original_rva; regions[8+i][1]=ep_insert_templates[i].original_bytes; }
    for (unsigned i=0;i<12;i++) for (unsigned j=i+1;j<12;j++)
        if (regions[i][0]<regions[j][0]+regions[j][1] && regions[j][0]<regions[i][0]+regions[i][1]) return EP_PROPERTY_OVERLAP;
    uint64_t values[]={a.game_base,a.code_address,a.roster_address,a.storage_address,a.move_code_address,a.reject_address};
    memcpy(result.data,t->data,t->bytes);
    for (unsigned i=0;i<t->fixups;i++) {
        const EpInsertFixup* f=&t->relocation[i];int64_t value=(int64_t)values[f->parameter]+f->addend;
        if (f->width==4) {
            value-=(int64_t)(a.code_address+f->next_offset);
            if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;
        }
        for (unsigned j=0;j<f->width;j++) result.data[f->offset+j]=(uint8_t)((uint64_t)value>>(8*j));
    }
    result.bytes=t->bytes;result.code_bytes=t->code_bytes;result.unwind_offset=t->unwind_offset;result.table_offset=t->table_offset;
    *out=result;return EP_PROPERTY_OK;
}
EpPropertyResult ep_insert_code_prepare(const HfApi* api,HfMod* owner,uint32_t kind,const EpInsertAddresses* input,EpSessionCodeInfo* out)
{
    EpInsertAddresses a;EpPropertyImage image;EpSessionCodeInfo allocation={0};EpPropertyResult result;
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out));if (!input || kind<1 || kind>4) return EP_PROPERTY_ARGUMENT;
    if (!ep_session_code_reserve(api,owner,(uintptr_t)a.code_address,ep_insert_templates[kind-1].bytes,&allocation)) return EP_PROPERTY_RESERVE;
    a.code_address=allocation.base;result=ep_insert_image_build(kind,&a,&image);
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
