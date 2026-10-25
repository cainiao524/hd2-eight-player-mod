#include "ep_property_gate.h"
#include <string.h>
static int EpGateOverlap(uint64_t a,uint64_t n,uint64_t b,uint64_t m)
{ return a<b+m && b<a+n; }
static int EpGatePointers(uint64_t base,uint64_t control,uint64_t next)
{
    uint64_t limit=UINT64_C(1)<<47;
    return base && base<=limit-EP_PROPERTY_GATED_MAX &&
        control>=0x10000 && control<=limit-4 && !(control&3) && next>=0x10000 && next<=limit-8 && !(next&7);
}
static EpPropertyResult EpGateWrap(const EpPropertyImage* candidate,uint64_t base,uint64_t control,uint64_t next,
                                  const uint64_t regions[][2],unsigned count,EpPropertyGateImage* out)
{
    uint32_t rows[6],leaf,bytes=candidate->bytes+48;
    if (EpGateOverlap(base,bytes,control,4) || EpGateOverlap(base,bytes,next,8) || EpGateOverlap(control,4,next,8)) return EP_PROPERTY_OVERLAP;
    for (unsigned i=0;i<count;i++)
        if (EpGateOverlap(base,bytes,regions[i][0],regions[i][1]) ||
            EpGateOverlap(control,4,regions[i][0],regions[i][1]) || EpGateOverlap(next,8,regions[i][0],regions[i][1])) return EP_PROPERTY_OVERLAP;
    const uint8_t gate[32]={0x48,0xB8,0,0,0,0,0,0,0,0,0x83,0x38,1,0x75,5,
                            0xE9,12,0,0,0,0x48,0xB8,0,0,0,0,0,0,0,0,0xFF,0x20};
    memcpy(out->data,gate,sizeof(gate));
    memcpy(out->data+2,&control,8); memcpy(out->data+22,&next,8);
    memcpy(out->data+32,candidate->data,candidate->table_offset);
    leaf=32+candidate->table_offset;
    out->data[leaf]=1; /* version 1, no frame, no unwind actions */
    out->table_offset=leaf+4; out->bytes=bytes;
    rows[0]=0; rows[1]=32; rows[2]=leaf;
    rows[3]=32; rows[4]=32+candidate->code_bytes; rows[5]=32+candidate->unwind_offset;
    memcpy(out->data+out->table_offset,rows,sizeof(rows));
    return EP_PROPERTY_OK;
}
EpPropertyResult ep_property_gate_build(uint32_t kind,const EpPropertyAddresses* input,
                                        uint64_t control,uint64_t next,EpPropertyGateImage* out)
{
    EpPropertyAddresses a; EpPropertyImage candidate;
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out)); if (!input) return EP_PROPERTY_ARGUMENT;
    if (!EpGatePointers(a.code_address,control,next)) return EP_PROPERTY_POINTER;
    a.code_address+=32;
    EpPropertyResult result=ep_property_image_build(kind,&a,&candidate);
    if (result!=EP_PROPERTY_OK) return result;
    uint64_t regions[][2]={{a.roster_address,0x428},{a.property_address,0x100},{a.reject_address,1},
        {a.game_base+0x60C640,578},{a.game_base+0x60C890,303},{a.game_base+0x606AD0,165},{a.game_base+0x3483C20,4},
        {a.game_base+0x3326468,8},{a.game_base+0x173B8D0,1},{a.game_base+0x134F190,92},{a.game_base+0x347CEF0,8}};
    return EpGateWrap(&candidate,a.code_address-32,control,next,regions,sizeof(regions)/sizeof(*regions),out);
}
EpPropertyResult ep_getter_gate_build(const EpGetterAddresses* input,uint64_t control,uint64_t next,EpPropertyGateImage* out)
{
    EpGetterAddresses a; EpPropertyImage candidate;
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out)); if (!input) return EP_PROPERTY_ARGUMENT;
    if (!EpGatePointers(a.code_address,control,next)) return EP_PROPERTY_POINTER;
    a.code_address+=32;
    EpPropertyResult result=ep_getter_image_build(&a,&candidate);
    if (result!=EP_PROPERTY_OK) return result;
    uint64_t regions[][2]={{a.roster_address,0x428},{a.storage_address,0x680},{a.reject_address,1},
        {a.game_base+0x60C640,578},{a.game_base+0x60C890,303},{a.game_base+0x606AD0,165},
        {a.game_base+0x3483C20,4},{a.game_base+0x3326468,8}};
    return EpGateWrap(&candidate,a.code_address-32,control,next,regions,sizeof(regions)/sizeof(*regions),out);
}
