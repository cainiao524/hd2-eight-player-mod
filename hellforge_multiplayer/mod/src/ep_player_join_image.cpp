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
static EpPropertyResult EpJoinGate(uint64_t game,uint64_t code,uint64_t control,uint64_t next,
    const EpPlayerJoinImage& body,EpPlayerJoinImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;*out={};
    if (code>(UINT64_C(1)<<47)-EP_PLAYER_JOIN_MAX_BYTES) return EP_PROPERTY_POINTER;
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
    if (body.function_count>12 || body.bytes+48>sizeof(gate.data)) return EP_PROPERTY_ARGUMENT;
    uint32_t rows[39]={0,32,body.table_offset+32};gate.data[rows[2]]=1;
    memcpy(rows+3,body.data+body.table_offset,12*body.function_count);
    for (unsigned f=0;f<body.function_count;f++) {
        const uint32_t uw=rows[5+3*f];
        const uint32_t tail=uw+4+((body.data[uw+2]+1u)&~1u)*2u;
        const unsigned fields=body.data[uw]==33 ? 3 : body.data[uw]==25 ? 1 : 0;
        for (unsigned j=0;j<fields;j++) {
            uint32_t value;memcpy(&value,body.data+tail+4*j,4);value+=32;
            memcpy(gate.data+32+tail+4*j,&value,4);
        }
    }
    for (unsigned i=3;i<3+3*body.function_count;i++) rows[i]+=32;
    gate.table_offset=body.table_offset+36;gate.bytes=body.bytes+48;
    gate.function_count=body.function_count+1;gate.handler_offset=body.handler_offset+32;
    gate.creation_target_offset=body.creation_target_offset+32;
    memcpy(gate.data+gate.table_offset,rows,12*gate.function_count);*out=gate;return EP_PROPERTY_OK;
}
EpPropertyResult ep_player_join_gate_build(uint64_t game,uint64_t code,uint64_t control,uint64_t next,
    uint32_t capacity,EpPlayerJoinImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;*out={};
    if (code>(UINT64_C(1)<<47)-EP_PLAYER_JOIN_MAX_BYTES) return EP_PROPERTY_POINTER;
    EpPlayerJoinImage body={};auto rc=ep_player_join_image_build(game,code+32,capacity,&body);
    return rc==EP_PROPERTY_OK ? EpJoinGate(game,code,control,next,body,out) : rc;
}
namespace {
struct JoinPeerCode {
    uint8_t* data;uint32_t at;uint64_t base;bool valid;
    void raw(const uint8_t* p,uint32_t n) {memcpy(data+at,p,n);at+=n;}
    void byte(uint8_t v) {data[at++]=v;}
    void word(uint32_t v) {memcpy(data+at,&v,4);at+=4;}
    void address(uint64_t v) {memcpy(data+at,&v,8);at+=8;}
    void align(uint32_t n) {while (at%n) byte(0xcc);}
    void relative(uint64_t target) {
        const int64_t d=(int64_t)target-(int64_t)(base+at+4);
        if (d<INT32_MIN || d>INT32_MAX) valid=false;word((uint32_t)d);
    }
    void jump(uint32_t target) {byte(0xe9);relative(base+target);}
    uint32_t condition(uint8_t op) {byte(0x0f);byte(op);auto off=at;word(0);return off;}
    void resolve(uint32_t off,uint32_t target) {int32_t delta=(int32_t)target-(int32_t)off-4;memcpy(data+off,&delta,4);}
    void constant(uint64_t v) {byte(0x49);byte(0xbb);address(v);}
    void reject(uint64_t target) {constant(target);const uint8_t tail[]={0x41,0xff,0xd3,0x0f,0x0b};raw(tail,5);}
};
bool JoinPeerPointer(uint64_t p,uint64_t n,uint64_t align)
{return p>=0x10000 && p<=(UINT64_C(1)<<47)-n && !(p%align);}
}
EpPropertyResult ep_player_join_peer_gate_build(uint64_t game,uint64_t code,uint64_t control,uint64_t next,
    uint64_t reject,const EpPlayerJoinPeers* input,EpPlayerJoinImage* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;EpPlayerJoinPeers peers={};if (input) peers=*input;*out={};
    if (!input || peers.reserved || peers.capacity<4 || peers.capacity>8) return EP_PROPERTY_ARGUMENT;
    if (peers.client<0x10000+0x162c8) return EP_PROPERTY_POINTER;
    const uint64_t owner=peers.client-0x162c8;
    const uint64_t spans[][3]={{game,74727424,4096},{code,4096,16},{owner,0x162c8+0x528,8},
        {peers.bank,peers.capacity*32ull,16},{reject,1,1},{control,4,4},{next,8,8}};
    for (unsigned i=0;i<7;i++) {
        auto p=spans[i][0],n=spans[i][1];if (!JoinPeerPointer(p,n,spans[i][2])) return EP_PROPERTY_POINTER;
        for (unsigned j=0;j<i;j++) if (p<spans[j][0]+spans[j][1] && spans[j][0]<p+n) return EP_PROPERTY_OVERLAP;
    }
    const uint64_t base=code+32;EpPlayerJoinImage old={};
    auto rc=ep_player_join_image_build(game,base,peers.capacity,&old);if (rc!=EP_PROPERTY_OK) return rc;
    EpPlayerJoinImage body=old;JoinPeerCode b={body.data,ep_player_join_code_bytes,base,true};
    uint32_t islands[3][2];
    // Owner/count window 1086212..1086223; the later TEST R9D is preserved.
    b.align(16);islands[0][0]=b.at;
    const uint8_t get_owner[]={0x4c,0x8b,0x05};b.raw(get_owner,3);b.relative(game+0x347cef0);
    b.constant(owner);const uint8_t match_owner[]={0x4d,0x39,0xd8};b.raw(match_owner,3);auto foreign=b.condition(0x85);
    const uint8_t get_count[]={0x45,0x8b,0x88,0x90,0x63,1,0,0x41,0x81,0xf9};b.raw(get_count,10);b.word(peers.capacity);
    auto excess=b.condition(0x87);const uint8_t ordinal[]={0x41,0x8b,0xce};b.raw(ordinal,3);b.jump(0x1086223-0x1085d70);
    b.resolve(foreign,b.at);b.resolve(excess,b.at);b.reject(reject);islands[0][1]=b.at;
    // Search compares the whole peer ID; the original JE consumes these flags.
    b.align(16);islands[1][0]=b.at;
    const uint8_t bound_rax[]={0x48,0x81,0xf8};b.raw(bound_rax,3);b.word(peers.capacity*32);auto beyond=b.condition(0x83);
    b.constant(peers.bank);const uint8_t compare_peer[]={0x4d,0x39,0x14,0x03};b.raw(compare_peer,4);b.jump(0x1086240-0x1085d70);
    b.resolve(beyond,b.at);b.reject(reject);islands[1][1]=b.at;
    // This island is BEFORE the accepted fragment's delayed XMM saves. It
    // chains to the preceding GP-only search frame, never the full XMM frame.
    b.align(16);islands[2][0]=b.at;
    const uint8_t bound_rdx[]={0x48,0x81,0xfa};b.raw(bound_rdx,3);b.word(peers.capacity*32);beyond=b.condition(0x83);
    b.constant(peers.bank);const uint8_t compare_index[]={0x41,0x83,0x7c,0x13,0x14};b.raw(compare_index,5);b.byte((uint8_t)peers.capacity);
    b.jump(0x1086469-0x1085d70);b.resolve(beyond,b.at);b.reject(reject);islands[2][1]=b.at;
    if (!b.valid) return EP_PROPERTY_REL32;
    const uint32_t sites[]={0x1086212-0x1085d70,0x1086238-0x1085d70,0x1086460-0x1085d70};
    const uint32_t sizes[]={17,8,9};
    for (unsigned i=0;i<3;i++) {JoinPeerCode patch={body.data,sites[i],base,true};patch.jump(islands[i][0]);while (patch.at<sites[i]+sizes[i]) patch.byte(0x90);}
    b.align(4);uint32_t rows[36];memcpy(rows,old.data+old.table_offset,108);
    const uint32_t old_metadata=rows[2],delta=b.at-old_metadata;
    b.raw(old.data+old_metadata,old.table_offset-old_metadata);
    for (unsigned f=0;f<9;f++) {
        uint32_t& u=rows[3*f+2];u+=delta;
        if (body.data[u]==33) {
            auto at=u+4+((body.data[u+2]+1u)&~1u)*2u+8;uint32_t parent;
            memcpy(&parent,body.data+at,4);parent+=delta;memcpy(body.data+at,&parent,4);
        }
    }
    for (unsigned i=0;i<3;i++) {
        rows[27+3*i]=islands[i][0];rows[28+3*i]=islands[i][1];rows[29+3*i]=b.at;
        b.word(33);b.raw((const uint8_t*)(rows+6),12);
    }
    body.table_offset=b.at;b.raw((const uint8_t*)rows,sizeof(rows));body.bytes=b.at;body.function_count=12;
    if (body.bytes+48!=EP_PLAYER_JOIN_PEER_GATE_BYTES) return EP_PROPERTY_ARGUMENT;
    return EpJoinGate(game,code,control,next,body,out);
}
