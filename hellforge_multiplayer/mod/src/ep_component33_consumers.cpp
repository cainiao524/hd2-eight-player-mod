#include "ep_component33_consumers.h"
#include <limits.h>
#include <string.h>
struct EpC33ConsumerFixup { uint16_t offset,next_offset; uint8_t parameter,width; int32_t addend; };
struct EpC33ConsumerTemplate {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,functions,fixups;
    const uint8_t* data;const EpC33ConsumerFixup* relocation;
};
#include "ep_component33_consumers_template.h"
uint32_t ep_component33_consumer_bytes(uint32_t kind)
{ return kind>=1 && kind<=4 ? ep_c33_consumer_templates[kind-1].bytes : 0; }
static bool Valid(uint64_t p,uint64_t n,uint64_t alignment)
{ return p && p<(UINT64_C(1)<<47) && !(p%alignment) && n<=(UINT64_C(1)<<47)-p; }
EpPropertyResult ep_component33_consumer_build(uint32_t kind,const EpC33ConsumerAddresses* input,EpComponent33Image* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpC33ConsumerAddresses a={};if (input) a=*input;
    memset(out,0,sizeof(*out));if (!input || kind<1 || kind>4) return EP_PROPERTY_ARGUMENT;
    if (!Valid(a.game_base,0x379819c,4096) || !Valid(a.release_address,4096,16) || a.storage_address<0x70) return EP_PROPERTY_POINTER;
    const uint64_t regions[][3]={{a.code_address,4096,16},{a.component_address,0x2b8,8},
        {a.storage_address,0x490,16},{a.reject_address,1,1},{a.release_address,4096,16}};
    unsigned count=(kind==EP_C33_ACQUIRE || kind==EP_C33_DEFER) ? 5 : 4;
    for (unsigned i=0;i<count;i++) {
        const auto& r=regions[i];if (!Valid(r[0],r[1],r[2])) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (r[0]<regions[j][0]+regions[j][1] && regions[j][0]<r[0]+r[1]) return EP_PROPERTY_OVERLAP;
        for (const auto& p:ep_c33_consumer_protected) if (r[0]<a.game_base+p[0]+p[1] && a.game_base+p[0]<r[0]+r[1]) return EP_PROPERTY_OVERLAP;
    }
    const auto& t=ep_c33_consumer_templates[kind-1];EpComponent33Image result={};
    const uint64_t values[]={a.game_base,a.code_address,a.component_address,a.storage_address,a.release_address,a.reject_address};
    memcpy(result.data,t.data,t.bytes);
    for (unsigned i=0;i<t.fixups;i++) {
        const auto& f=t.relocation[i];int64_t value=(int64_t)values[f.parameter]+f.addend;
        if (f.width==4) { value-=(int64_t)(a.code_address+f.next_offset);if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32; }
        for (unsigned j=0;j<f.width;j++) result.data[f.offset+j]=(uint8_t)((uint64_t)value>>(8*j));
    }
    result.bytes=t.bytes;result.code_bytes=t.code_bytes;result.unwind_offset=t.unwind_offset;
    result.table_offset=t.table_offset;result.function_count=t.functions;*out=result;return EP_PROPERTY_OK;
}
