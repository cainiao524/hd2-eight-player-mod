#include "ep_property_image.h"
#include <limits.h>
#include <string.h>
typedef struct EpPropertyFixup {
    uint16_t offset, next_offset;
    uint8_t parameter, width;
    int32_t addend;
} EpPropertyFixup;
#include "ep_property_templates.h"
static_assert(sizeof(ep_producer_template)==708 && sizeof(ep_receiver_template)==436,
              "Fixed profile image layout changed; review allocation and unwind extents");
typedef struct EpPropertyRegion { uint64_t address, bytes; } EpPropertyRegion;
static int Pointer(uint64_t p, uint64_t bytes, uint64_t alignment)
{
    const uint64_t end=UINT64_C(1)<<47;
    return p && p<end && !(p%alignment) && bytes<=end-p;
}
static int Overlap(EpPropertyRegion a, EpPropertyRegion b)
{
    return a.address<b.address+b.bytes && b.address<a.address+a.bytes;
}
static int64_t Value(const EpPropertyFixup* f, const uint64_t* p)
{
    int64_t value=(int64_t)p[f->parameter]+f->addend;
    return f->width==4 ? value-(int64_t)(p[1]+f->next_offset) : value;
}
EpPropertyResult ep_property_image_build(uint32_t kind, const EpPropertyAddresses* input, EpPropertyImage* out)
{
    EpPropertyImage result={0};
    EpPropertyAddresses a;
    const EpPropertyFixup *fixups,*legacy;
    const uint8_t* source;
    uint32_t n,old_n,i,j,region_n=0;
    uint64_t p[5];
    EpPropertyRegion regions[9],image_region;
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out));
    if (!input || (kind!=EP_PROPERTY_PRODUCER && kind!=EP_PROPERTY_RECEIVER)) return EP_PROPERTY_ARGUMENT;
    if (kind==EP_PROPERTY_PRODUCER) {
        source=ep_producer_template; result.bytes=sizeof(ep_producer_template);
        result.code_bytes=670; result.unwind_offset=672; result.table_offset=696;
        fixups=ep_producer_fixups; n=sizeof(ep_producer_fixups)/sizeof(*fixups);
        legacy=ep_producer_legacy_ranges; old_n=sizeof(ep_producer_legacy_ranges)/sizeof(*legacy);
    } else {
        source=ep_receiver_template; result.bytes=sizeof(ep_receiver_template);
        result.code_bytes=398; result.unwind_offset=400; result.table_offset=424;
        fixups=ep_receiver_fixups; n=sizeof(ep_receiver_fixups)/sizeof(*fixups);
        legacy=ep_receiver_legacy_ranges; old_n=sizeof(ep_receiver_legacy_ranges)/sizeof(*legacy);
    }
    if (!Pointer(a.game_base,0x3483C24,0x1000) || !Pointer(a.code_address,result.bytes,16) ||
        !Pointer(a.roster_address,0x428,8) || !Pointer(a.property_address,0x100,8) ||
        a.property_address<0x3A8 || !Pointer(a.reject_address,1,1)) return EP_PROPERTY_POINTER;
    p[0]=a.game_base; p[1]=a.code_address; p[2]=a.roster_address;
    p[3]=a.property_address; p[4]=a.reject_address;
    image_region.address=a.code_address; image_region.bytes=result.bytes;
    regions[region_n++]=image_region;
    regions[region_n++]=(EpPropertyRegion){a.roster_address,0x428};
    regions[region_n++]=(EpPropertyRegion){a.property_address,0x100};
    regions[region_n++]=(EpPropertyRegion){a.game_base+0x3483C20,4};
    regions[region_n++]=(EpPropertyRegion){a.game_base+(kind==EP_PROPERTY_PRODUCER ? 0x60C640 : 0x60C890),kind==EP_PROPERTY_PRODUCER ? 578u : 303u};
    regions[region_n++]=(EpPropertyRegion){a.reject_address,1};
    if (kind==EP_PROPERTY_PRODUCER) {
        regions[region_n++]=(EpPropertyRegion){a.game_base+0x3326468,8};
        regions[region_n++]=(EpPropertyRegion){a.game_base+0x173B8D0,1};
        regions[region_n++]=(EpPropertyRegion){a.game_base+0x134F190,92};
        if (Overlap(image_region,(EpPropertyRegion){a.game_base+0x347CEF0,8})) return EP_PROPERTY_OVERLAP;
    }
    for (i=0;i<region_n;i++) for (j=i+1;j<region_n;j++)
        if (Overlap(regions[i],regions[j])) return EP_PROPERTY_OVERLAP;
    /* These also retain the pinned Python emitter's intermediate constraints,
     * so native acceptance cannot silently bypass a source-generation gate. */
    for (i=0;i<old_n;i++) {
        int64_t value=Value(&legacy[i],p);
        if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;
    }
    memcpy(result.data,source,result.bytes);
    for (i=0;i<n;i++) {
        const EpPropertyFixup* f=&fixups[i];
        int64_t value=Value(f,p);
        if (f->width==4 && (value<INT32_MIN || value>INT32_MAX)) return EP_PROPERTY_REL32;
        for (j=0;j<f->width;j++) result.data[f->offset+j]=(uint8_t)((uint64_t)value>>(8*j));
    }
    *out=result;
    return EP_PROPERTY_OK;
}
