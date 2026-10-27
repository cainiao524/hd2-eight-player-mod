#include "ep_player_join_image.h"
#include <limits.h>
#include <string.h>
struct EpPlayerJoinFixup {uint32_t offset,next,rva;};
#include "ep_player_join_template.h"
EpPropertyResult ep_player_join_image_build(uint64_t game,uint64_t code,uint32_t capacity,EpPlayerJoinImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;*out={};
    if (capacity<4 || capacity>8) return EP_PROPERTY_ARGUMENT;
    const uint64_t limit=UINT64_C(1)<<47;
    if (game<0x10000 || game>limit-74727424 || game%4096 || code<0x10000 ||
        code>limit-sizeof(ep_player_join_template) || code%16) return EP_PROPERTY_POINTER;
    if (game<code+sizeof(ep_player_join_template) && code<game+74727424) return EP_PROPERTY_OVERLAP;
    EpPlayerJoinImage image={};memcpy(image.data,ep_player_join_template,sizeof(ep_player_join_template));
    image.data[ep_player_join_capacity]=(uint8_t)capacity;
    for (const auto& f:ep_player_join_fixups) {
        const int64_t value=(int64_t)(game+f.rva)-(int64_t)(code+f.next);
        if (value<INT32_MIN || value>INT32_MAX) return EP_PROPERTY_REL32;
        const auto relative=(int32_t)value;memcpy(image.data+f.offset,&relative,4);
    }
    image.bytes=sizeof(ep_player_join_template);image.table_offset=ep_player_join_table;
    image.function_count=9;image.handler_offset=ep_player_join_handler;
    image.creation_target_offset=ep_player_join_creation_pointer;*out=image;return EP_PROPERTY_OK;
}
EpPropertyResult ep_player_join_gate_build(uint64_t game,uint64_t code,uint64_t control,uint64_t next,
    uint32_t capacity,EpPlayerJoinImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;*out={};
    if (code>(UINT64_C(1)<<47)-EP_PLAYER_JOIN_MAX_BYTES) return EP_PROPERTY_POINTER;
    EpPlayerJoinImage body={};auto rc=ep_player_join_image_build(game,code+32,capacity,&body);
    if (rc!=EP_PROPERTY_OK) return rc;
    uint64_t spans[][2]={{code,body.bytes+48u},{control,4},{next,8}};
    if (code<0x10000 || control<0x10000 || next<0x10000 || control%4 || next%8 ||
        control>(UINT64_C(1)<<47)-4 || next>(UINT64_C(1)<<47)-8) return EP_PROPERTY_POINTER;
    for (unsigned i=0;i<3;i++) {
        auto a=spans[i][0],n=spans[i][1];
        if (a<game+74727424 && game<a+n) return EP_PROPERTY_OVERLAP;
        for (unsigned j=0;j<i;j++) if (a<spans[j][0]+spans[j][1] && spans[j][0]<a+n) return EP_PROPERTY_OVERLAP;
    }
    EpPlayerJoinImage gate={};
    const uint8_t prefix[32]={0x48,0xb8,0,0,0,0,0,0,0,0,0x83,0x38,1,0x75,5,
        0xe9,12,0,0,0,0x48,0xb8,0,0,0,0,0,0,0,0,0xff,0x20};
    memcpy(gate.data,prefix,32);memcpy(gate.data+2,&control,8);memcpy(gate.data+22,&next,8);
    memcpy(gate.data+32,body.data,body.table_offset);
    uint32_t rows[30]={0,32,body.table_offset+32};gate.data[rows[2]]=1;
    memcpy(rows+3,body.data+body.table_offset,108);
    for (unsigned f=0;f<9;f++) {
        const uint32_t uw=rows[5+3*f];
        const uint32_t tail=uw+4+((body.data[uw+2]+1u)&~1u)*2u;
        const unsigned fields=body.data[uw]==33 ? 3 : body.data[uw]==25 ? 1 : 0;
        for (unsigned j=0;j<fields;j++) {
            uint32_t value;memcpy(&value,body.data+tail+4*j,4);value+=32;
            memcpy(gate.data+32+tail+4*j,&value,4);
        }
    }
    for (unsigned i=3;i<30;i++) rows[i]+=32;
    gate.table_offset=body.table_offset+36;gate.bytes=body.bytes+48;
    gate.function_count=10;gate.handler_offset=body.handler_offset+32;
    gate.creation_target_offset=body.creation_target_offset+32;
    memcpy(gate.data+gate.table_offset,rows,sizeof(rows));*out=gate;return EP_PROPERTY_OK;
}
