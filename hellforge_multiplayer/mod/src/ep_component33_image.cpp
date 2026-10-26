#include "ep_component33_image.h"
#include <limits.h>
#include <string.h>
typedef struct EpComponent33Fixup { uint16_t offset,next_offset; uint8_t parameter,width; int32_t addend; } EpComponent33Fixup;
typedef struct EpComponent33Template {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,functions,fixups;
    const uint8_t* data; const EpComponent33Fixup* relocation;
} EpComponent33Template;
#include "ep_component33_templates.h"
static int C33Pointer(uint64_t p,uint64_t n,uint64_t alignment)
{ return p && p<(UINT64_C(1)<<47) && !(p%alignment) && n<=(UINT64_C(1)<<47)-p; }
EpPropertyResult ep_component33_image_build(uint32_t kind,const EpComponent33Addresses* input,EpComponent33Image* out)
{
    EpComponent33Addresses a;EpComponent33Image result={};
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out));
    if (!input || kind<1 || kind>sizeof(ep_component33_templates)/sizeof(ep_component33_templates[0])) return EP_PROPERTY_ARGUMENT;
    if (!C33Pointer(a.game_base,0x3483c38,4096) || !C33Pointer(a.code_address,4096,16) ||
        !C33Pointer(a.component_address,0x2b8,8) || !C33Pointer(a.storage_address,0x490,16) ||
        a.storage_address<0x70 || !C33Pointer(a.move_code_address,4096,16) || !C33Pointer(a.reject_address,1,1)) return EP_PROPERTY_POINTER;
    uint64_t regions[7+sizeof(ep_component33_sources)/sizeof(ep_component33_sources[0])+
                     sizeof(ep_component33_extra_globals)/sizeof(ep_component33_extra_globals[0])][2]={{a.code_address,4096},{a.component_address,0x2b8},{a.storage_address,0x490},
                            {a.reject_address,1},{a.game_base+0x33267b8,8},{a.game_base+0x3483c34,4}};
    unsigned count=6;
    if (kind!=EP_COMPONENT33_MOVER) { regions[count][0]=a.move_code_address;regions[count++][1]=4096; }
    for (const auto& source:ep_component33_sources) { regions[count][0]=a.game_base+source[0];regions[count++][1]=source[1]; }
    for (const auto& source:ep_component33_extra_globals) { regions[count][0]=a.game_base+source[0];regions[count++][1]=source[1]; }
    for (unsigned i=0;i<count;i++) for (unsigned j=i+1;j<count;j++)
        if (regions[i][0]<regions[j][0]+regions[j][1] && regions[j][0]<regions[i][0]+regions[i][1]) return EP_PROPERTY_OVERLAP;
    const auto& t=ep_component33_templates[kind-1];
    if (t.bytes>sizeof(result.data)) return EP_PROPERTY_ARGUMENT;
    const uint64_t values[]={a.game_base,a.code_address,a.component_address,a.storage_address,a.move_code_address,a.reject_address};
    memcpy(result.data,t.data,t.bytes);
    for (unsigned i=0;i<t.fixups;i++) {
        const auto& f=t.relocation[i];int64_t value=(int64_t)values[f.parameter]+f.addend;
        if (f.width==4) { value-=(int64_t)(a.code_address+f.next_offset);if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32; }
        for (unsigned j=0;j<f.width;j++) result.data[f.offset+j]=(uint8_t)((uint64_t)value>>(8*j));
    }
    result.bytes=t.bytes;result.code_bytes=t.code_bytes;result.unwind_offset=t.unwind_offset;
    result.table_offset=t.table_offset;result.function_count=t.functions;*out=result;return EP_PROPERTY_OK;
}
