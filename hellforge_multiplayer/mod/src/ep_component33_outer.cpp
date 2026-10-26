#include "ep_component33_outer.h"
#include <string.h>
#include <limits.h>
struct EpC33OuterFixup { uint32_t offset,next,key,width;int64_t add; };
struct EpC33OuterWindowTemplate { uint32_t rva,entry;uint8_t expected[5]; };
#include "ep_component33_outer_template.h"
#include "ep_component33_refresh_template.h"
#include "ep_component33_leave_template.h"
uint32_t ep_component33_outer_image_bytes(void) { return sizeof(ep_c33_outer_image); }
static bool Pointer(uint64_t p,uint64_t n,uint64_t alignment)
{ return p && p<(UINT64_C(1)<<47) && !(p%alignment) && n<=(UINT64_C(1)<<47)-p; }
EpPropertyResult ep_component33_outer_build(const EpC33ConsumerAddresses* input,EpComponent33OuterPlan* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpC33ConsumerAddresses a={};if (input) a=*input;memset(out,0,sizeof(*out));
    if (!input) return EP_PROPERTY_ARGUMENT;
    if (!Pointer(a.game_base,0x379819c,4096)) return EP_PROPERTY_POINTER;
    const uint64_t regions[][3]={{a.code_address,4096,16},{a.component_address,0x2b8,8},{a.storage_address,0x490,16},{a.release_address,4096,16},{a.reject_address,1,1}};
    for (unsigned i=0;i<5;i++) {
        const auto& r=regions[i];if (!Pointer(r[0],r[1],r[2])) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (r[0]<regions[j][0]+regions[j][1] && regions[j][0]<r[0]+r[1]) return EP_PROPERTY_OVERLAP;
        for (const auto& p:ep_c33_outer_protected) if (r[0]<a.game_base+p[0]+p[1] && a.game_base+p[0]<r[0]+r[1]) return EP_PROPERTY_OVERLAP;
    }
    EpComponent33OuterPlan p={};auto& b=p.bridge;
    b.bytes=sizeof(ep_c33_outer_image);b.code_bytes=ep_c33_outer_code_bytes;b.unwind_offset=ep_c33_outer_unwind_offset;
    b.table_offset=ep_c33_outer_table_offset;b.function_count=ep_c33_outer_function_count;memcpy(b.data,ep_c33_outer_image,b.bytes);
    const uint64_t values[]={a.game_base,a.code_address,a.component_address,a.storage_address,a.release_address,a.reject_address};
    for (const auto& f:ep_c33_outer_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (f.width==4) { value-=(int64_t)a.code_address+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32; }
        for (unsigned j=0;j<f.width;j++) b.data[f.offset+j]=(uint8_t)((uint64_t)value>>(8*j));
    }
    for (unsigned i=0;i<5;i++) {
        const auto& t=ep_c33_outer_windows[i];auto& w=p.windows[i];w.target=a.game_base+t.rva;w.bytes=5;
        const uint64_t destination=t.entry==UINT32_MAX ? a.release_address : a.code_address+t.entry;
        const int64_t rel=(int64_t)destination-(int64_t)(w.target+5);if (rel<INT32_MIN || rel>INT32_MAX) return EP_PROPERTY_REL32;
        memcpy(w.expected,t.expected,5);w.replacement[0]=0xe8;
        for (unsigned j=0;j<4;j++) w.replacement[j+1]=(uint8_t)((uint64_t)rel>>(8*j));
    }
    *out=p;return EP_PROPERTY_OK;
}
uint32_t ep_component33_refresh_image_bytes(void) { return sizeof(ep_c33_refresh_image); }
EpPropertyResult ep_component33_refresh_build(const EpC33RefreshAddresses* input,EpComponent33Image* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpC33RefreshAddresses a={};if (input) a=*input;memset(out,0,sizeof(*out));if (!input) return EP_PROPERTY_ARGUMENT;
    if (!Pointer(a.game_base,0x4000000,4096) || !Pointer(a.code_address,4096,16) || !Pointer(a.acquire_address,48,16)) return EP_PROPERTY_POINTER;
    const uint64_t spans[][2]={{a.game_base,0x4000000},{a.code_address,4096},{a.acquire_address,48}};
    for (unsigned i=0;i<3;i++) for (unsigned j=0;j<i;j++)
        if (spans[i][0]<spans[j][0]+spans[j][1] && spans[j][0]<spans[i][0]+spans[i][1]) return EP_PROPERTY_OVERLAP;
    EpComponent33Image image={};memcpy(image.data,ep_c33_refresh_image,sizeof(ep_c33_refresh_image));
    const uint64_t values[]={a.game_base,a.acquire_address};
    for (const auto& f:ep_c33_refresh_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add-(int64_t)a.code_address-f.next;
        if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;
        int32_t relative=(int32_t)value;memcpy(image.data+f.offset,&relative,4);
    }
    image.bytes=sizeof(ep_c33_refresh_image);image.code_bytes=ep_c33_refresh_code_bytes;image.unwind_offset=ep_c33_refresh_unwind_offset;
    image.table_offset=ep_c33_refresh_table_offset;image.function_count=ep_c33_refresh_function_count;
    *out=image;return EP_PROPERTY_OK;
}
uint32_t ep_component33_leave_image_bytes(void) { return sizeof(ep_c33_leave_image); }
EpPropertyResult ep_component33_leave_build(const EpC33LeaveAddresses* input,EpComponent33Image* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpC33LeaveAddresses a={};if (input) a=*input;memset(out,0,sizeof(*out));if (!input) return EP_PROPERTY_ARGUMENT;
    if (!Pointer(a.game_base,0x4000000,4096) || !Pointer(a.code_address,4096,16) || !Pointer(a.defer_address,48,16)) return EP_PROPERTY_POINTER;
    const uint64_t spans[][2]={{a.game_base,0x4000000},{a.code_address,4096},{a.defer_address,48}};
    for (unsigned i=0;i<3;i++) for (unsigned j=0;j<i;j++)
        if (spans[i][0]<spans[j][0]+spans[j][1] && spans[j][0]<spans[i][0]+spans[i][1]) return EP_PROPERTY_OVERLAP;
    EpComponent33Image image={};memcpy(image.data,ep_c33_leave_image,sizeof(ep_c33_leave_image));
    const uint64_t values[]={a.game_base,a.defer_address};
    for (const auto& f:ep_c33_leave_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add-(int64_t)a.code_address-f.next;
        if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;
        int32_t relative=(int32_t)value;memcpy(image.data+f.offset,&relative,4);
    }
    image.bytes=sizeof(ep_c33_leave_image);image.code_bytes=ep_c33_leave_code_bytes;image.unwind_offset=ep_c33_leave_unwind_offset;
    image.table_offset=ep_c33_leave_table_offset;image.function_count=ep_c33_leave_function_count;
    *out=image;return EP_PROPERTY_OK;
}
