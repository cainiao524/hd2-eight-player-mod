#include "ep_loadout_lifecycle.h"
#include <limits.h>
#include <string.h>
struct EpLoadoutFixup { uint32_t offset,next,key,kind;int64_t add; };
#include "ep_loadout_lifecycle_template.h"
static bool LoadoutPointer(uint64_t p,uint64_t n,uint64_t alignment)
{return p && p<(UINT64_C(1)<<47) && !(p%alignment) && n<=(UINT64_C(1)<<47)-p;}
EpPropertyResult ep_loadout_lifecycle_build(const EpLoadoutAddresses* input,EpLoadoutImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutAddresses a={};if (input) a=*input;*out={};
    if (!input || a.reserved || !a.capacity || a.capacity>EP_LOADOUT_LIFECYCLE_LIMIT) return EP_PROPERTY_ARGUMENT;
    const uint64_t regions[][3]={{a.game,0x4000000,4096},{a.code,4096,16},
        {a.screen,EP_LOADOUT_SCREEN_BYTES,8},{a.records,uint64_t(a.capacity)*EP_LOADOUT_RECORD_BYTES,16},
        {a.widgets,uint64_t(a.capacity)*EP_LOADOUT_WIDGET_BYTES,8},{a.reject,1,1}};
    for (unsigned i=0;i<6;i++) {
        const auto& r=regions[i];if (!LoadoutPointer(r[0],r[1],r[2])) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (r[0]<regions[j][0]+regions[j][1] && regions[j][0]<r[0]+r[1]) return EP_PROPERTY_OVERLAP;
    }
    EpLoadoutImage image={};memcpy(image.data,ep_loadout_lifecycle_template,sizeof(ep_loadout_lifecycle_template));
    const uint64_t values[]={a.game,a.code,a.screen,a.records,a.widgets,a.capacity,a.reject};
    for (const auto& f:ep_loadout_lifecycle_fixups) {
        int64_t value=(int64_t)values[f.key]+f.add;
        if (!f.kind) {value-=(int64_t)a.code+f.next;if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;}
        unsigned width=f.kind==1 ? 8 : 4;
        for (unsigned i=0;i<width;i++) image.data[f.offset+i]=(uint8_t)((uint64_t)value>>(8*i));
    }
    image.bytes=sizeof(ep_loadout_lifecycle_template);image.code_bytes=ep_loadout_code_bytes;
    image.unwind_offset=ep_loadout_unwind_offset;image.table_offset=ep_loadout_table_offset;image.function_count=6;
    image.constructor=ep_loadout_entries[0];image.release=ep_loadout_entries[1];image.alternate_release=ep_loadout_entries[2];
    *out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_loadout_lifecycle_prepare(const HfApi* api,HfMod* mod,const EpLoadoutAddresses* input,EpSessionCodeInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpLoadoutAddresses a={};if (input) a=*input;*out={};if (!input) return EP_PROPERTY_ARGUMENT;
    EpSessionCodeInfo code={};EpLoadoutImage image={};
    if (!ep_session_code_reserve(api,mod,(uintptr_t)a.code,sizeof(ep_loadout_lifecycle_template),&code)) return EP_PROPERTY_RESERVE;
    a.code=code.base;EpPropertyResult result=ep_loadout_lifecycle_build(&a,&image);
    if (result==EP_PROPERTY_OK && !ep_session_code_seal_table(mod,code.handle,image.data,image.bytes,image.table_offset,image.function_count)) result=EP_PROPERTY_SEAL;
    if (result==EP_PROPERTY_OK) {
        if (ep_session_code_info(mod,code.handle,out)) return EP_PROPERTY_OK;
        result=EP_PROPERTY_SEAL;
    }
    if (!ep_session_code_discard(mod,code.handle)) {
        *out=code;EpSessionCodeInfo retained={};if (ep_session_code_info(mod,code.handle,&retained)) *out=retained;
        return EP_PROPERTY_CLEANUP;
    }
    return result;
}
