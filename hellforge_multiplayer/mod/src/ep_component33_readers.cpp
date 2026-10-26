#include "ep_component33_readers.h"
#include <string.h>
#include <limits.h>
#include "ep_component33_readers_template.h"
uint32_t ep_component33_readers_image_bytes(void) { return sizeof(ep_c33_reader_image); }
static bool Pointer(uint64_t p,uint64_t n,uint64_t alignment)
{ return p && p<(UINT64_C(1)<<47) && !(p%alignment) && n<=(UINT64_C(1)<<47)-p; }
EpPropertyResult ep_component33_readers_build(const EpComponent33ReaderAddresses* input,EpComponent33ReaderPlan* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    memset(out,0,sizeof(*out));if (!input) return EP_PROPERTY_ARGUMENT;
    const auto a=*input;
    if (!Pointer(a.game_base,0x3483c38,4096)) return EP_PROPERTY_POINTER;
    const uint64_t regions[][3]={{a.code_address,4096,16},{a.component_address,0x2b8,8},
        {a.storage_address,0x490,16},{a.reset_address,4096,16},{a.reject_address,1,1}};
    for (unsigned i=0;i<5;i++) {
        const auto& x=regions[i];if (!Pointer(x[0],x[1],x[2])) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (x[0]<regions[j][0]+regions[j][1] && regions[j][0]<x[0]+x[1]) return EP_PROPERTY_OVERLAP;
        for (const auto& p:ep_c33_reader_protected) if (x[0]<a.game_base+p[0]+p[1] && a.game_base+p[0]<x[0]+x[1]) return EP_PROPERTY_OVERLAP;
    }
    EpComponent33ReaderPlan p={};auto& b=p.bridge;
    b.bytes=sizeof(ep_c33_reader_image);b.code_bytes=ep_c33_reader_code_bytes;
    b.unwind_offset=ep_c33_reader_unwind_offset;b.table_offset=ep_c33_reader_table_offset;b.function_count=1;
    memcpy(b.data,ep_c33_reader_image,b.bytes);
    const uint64_t values[]={a.component_address,a.game_base+0x33267b8,a.storage_address,a.reset_address,a.reject_address};
    for (const auto& f:ep_c33_reader_fixups) for (unsigned j=0;j<8;j++) b.data[f[0]+j]=(uint8_t)(values[f[1]]>>(8*j));
    const uint32_t rvas[]={0xaddd85,0xb62400},sizes[]={10,13},calls[]={0,5};
    const uint8_t* expected[]={ep_c33_reader_expected_0,ep_c33_reader_expected_1};
    const uint8_t* replacement[]={ep_c33_reader_patch_0,ep_c33_reader_patch_1};
    for (unsigned i=0;i<2;i++) {
        auto& w=p.windows[i];w.target=a.game_base+rvas[i];w.bytes=sizes[i];w.call_offset=calls[i];
        const int64_t rel=(int64_t)a.code_address-(int64_t)(w.target+w.call_offset+5);
        if (rel<INT32_MIN || rel>INT32_MAX) return EP_PROPERTY_REL32;
        memcpy(w.expected,expected[i],w.bytes);memcpy(w.replacement,replacement[i],w.bytes);
        for (unsigned j=0;j<4;j++) w.replacement[w.call_offset+1+j]=(uint8_t)((uint64_t)rel>>(8*j));
    }
    *out=p;return EP_PROPERTY_OK;
}
