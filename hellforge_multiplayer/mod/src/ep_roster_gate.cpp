#include "ep_roster_gate.h"
#include "ep_property_gate.h"
#include "ep_mover_image.h"
#include "ep_remove_image.h"
#include "ep_classify_image.h"
#include "ep_registry_image.h"
#include "ep_departure_image.h"
#include "ep_arrival_image.h"
#include <string.h>
static const EpRosterGateLayout layouts[EP_ROSTER_ENTRIES]={
    {0x60C640,578,756,2},{0x60C890,303,484,2},{0x606AD0,165,436,2},{0x60C410,430,660,3},
    {0x60CA80,287,688,3},{0x60CBA0,203,588,3},{0x540850,206,592,3},{0x540920,286,684,3},
    {0x60CEA0,172,824,3},{0x540A40,160,808,3},{0x60CF50,934,2344,3},{0x60D300,1120,2816,3},
    {0xB54E00,873,1884,5},{0x606520,271,536,4},{0x605950,1503,2760,15},{0xFDC820,1503,80,2},
    {0x6054F0,1111,2072,4}
};
int ep_roster_gate_layout(uint32_t kind,EpRosterGateLayout* out)
{
    if (!out) return 0;
    memset(out,0,sizeof(*out)); if (!kind || kind>EP_ROSTER_ENTRIES) return 0;
    *out=layouts[kind-1];return 1;
}
static int RosterOverlap(uint64_t a,uint64_t n,uint64_t b,uint64_t m) {return a<b+m && b<a+n;}
static int RosterPointer(uint64_t a,uint64_t n,uint64_t alignment)
{return a>=0x10000 && a<=(UINT64_C(1)<<47)-n && !(a%alignment);}
EpPropertyResult ep_roster_gate_build(uint32_t kind,const EpInsertAddresses* input,uint64_t control,uint64_t next,EpRosterGateImage* out)
{
    EpInsertAddresses a;EpRosterGateImage result={0};EpRosterGateLayout layout;
    if (!out) return EP_PROPERTY_ARGUMENT;
    if (input) a=*input;
    memset(out,0,sizeof(*out));
    if (!input || !ep_roster_gate_layout(kind,&layout)) return EP_PROPERTY_ARGUMENT;
    if (!RosterPointer(a.game_base,74727424,4096) || !RosterPointer(a.code_address,layout.image_bytes,16) ||
        !RosterPointer(a.roster_address,0x428,8) || !RosterPointer(a.storage_address,0x680,16) ||
        !RosterPointer(a.reject_address,1,1) || !RosterPointer(control,4,4) || !RosterPointer(next,8,8)) return EP_PROPERTY_POINTER;
    uint64_t resources[7][2]={{a.code_address,layout.image_bytes},{control,4},{next,8},
        {a.roster_address,0x428},{a.storage_address,0x680},{a.reject_address,1},{a.move_code_address,612}};
    unsigned count=((kind>=5 && kind<=10) || kind==EP_ROSTER_REGISTRY_UPDATE || kind==EP_ROSTER_DEPARTURE) ? 7 : 6;
    if (kind==EP_ROSTER_REGISTRY_UPDATE) resources[6][1]=488;
    if (kind==EP_ROSTER_DEPARTURE) resources[6][1]=388;
    if (count==7 && !RosterPointer(a.move_code_address,resources[6][1],16)) return EP_PROPERTY_POINTER;
    const uint32_t other[][2]={{0x3326468,8},{0x3483C20,4},{0x347CEF0,8},{0x134F190,92},
        {0x172F790,110},{0x172F8A0,259},{0x173B6F0,0x104},{0x173B8D0,0x182},{0x173BC20,0x77}};
    for (unsigned i=0;i<count;i++) {
        if (RosterOverlap(resources[i][0],resources[i][1],a.game_base,74727424)) return EP_PROPERTY_OVERLAP;
        for (unsigned j=0;j<i;j++) if (RosterOverlap(resources[i][0],resources[i][1],resources[j][0],resources[j][1])) return EP_PROPERTY_OVERLAP;
        for (unsigned j=0;j<EP_ROSTER_ENTRIES;j++)
            if (RosterOverlap(resources[i][0],resources[i][1],a.game_base+layouts[j].original_rva,layouts[j].original_bytes)) return EP_PROPERTY_OVERLAP;
        for (unsigned j=0;j<sizeof(other)/sizeof(*other);j++)
            if (RosterOverlap(resources[i][0],resources[i][1],a.game_base+other[j][0],other[j][1])) return EP_PROPERTY_OVERLAP;
    }
    EpPropertyResult rc;EpGetterAddresses basic={a.game_base,a.code_address,a.roster_address,a.storage_address,a.reject_address};
    if (kind==EP_ROSTER_ENTITY_REMOVE) {
        /* Keep the complete original entity lifecycle and later SDK hooks.
         * This leaf forwarding body also supports the unowned group API. */
        const uint8_t gate[32]={0x48,0xB8,0,0,0,0,0,0,0,0,0x83,0x38,1,0x75,5,
            0xE9,12,0,0,0,0x48,0xB8,0,0,0,0,0,0,0,0,0xFF,0x20};
        memcpy(result.data,gate,32);memcpy(result.data+2,&control,8);memcpy(result.data+22,&next,8);
        memcpy(result.data+32,gate+20,12);memcpy(result.data+34,&next,8);
        memset(result.data+44,0x90,4);result.data[48]=result.data[52]=1;
        const uint32_t rows[]={0,32,48,32,48,52};memcpy(result.data+56,rows,sizeof(rows));
        result.bytes=80;result.table_offset=56;result.function_count=2;
    } else if (kind<=3) {
        EpPropertyGateImage image;
        if (kind==3) rc=ep_getter_gate_build(&basic,control,next,&image);
        else {EpPropertyAddresses prop={a.game_base,a.code_address,a.roster_address,a.storage_address+0x580,a.reject_address};
            rc=ep_property_gate_build(kind,&prop,control,next,&image);}
        if (rc!=EP_PROPERTY_OK) return rc;
        result.bytes=image.bytes;result.table_offset=image.table_offset;result.function_count=2;
        memcpy(result.data,image.data,image.bytes);
    } else {
        a.code_address+=32;basic.code_address+=32;
        EpPropertyImage small;EpRemoveImage removed;EpClassifyImage classified;EpRegistryImage registry;EpDepartureImage departure;EpArrivalImage arrival;
        const uint8_t* data;uint32_t bytes,table,functions=2;
        if (kind==4) {EpMoverAddresses mover={a.game_base,a.code_address,a.roster_address,a.storage_address,a.reject_address};
            rc=ep_mover_image_build(&mover,&small);data=small.data;bytes=small.bytes;table=small.table_offset;}
        else if (kind<=8) {rc=ep_insert_image_build(kind-4,&a,&small);data=small.data;bytes=small.bytes;table=small.table_offset;}
        else if (kind<=10) {rc=ep_remove_image_build(kind-8,&a,&removed);data=removed.data;bytes=removed.bytes;table=removed.table_offset;}
        else if (kind<=12) {rc=ep_classify_image_build(kind-10,&basic,&classified);data=classified.data;bytes=classified.bytes;table=classified.table_offset;}
        else if (kind<=14) {EpRegistryAddresses r={a.game_base,a.code_address,a.roster_address,a.storage_address,a.move_code_address,a.reject_address};
            rc=ep_registry_image_build(kind-12,&r,&registry);data=registry.data;bytes=registry.bytes;table=registry.table_offset;functions=registry.function_count;}
        else if (kind==EP_ROSTER_STATE_UPDATE) {EpArrivalAddresses state={a.game_base,a.code_address,a.roster_address,a.storage_address,a.reject_address};
            rc=ep_arrival_image_build(&state,&arrival);data=arrival.data;bytes=arrival.bytes;table=arrival.table_offset;functions=arrival.function_count;}
        else {EpDepartureAddresses d={a.game_base,a.code_address,a.roster_address,a.storage_address,a.move_code_address,a.reject_address};
            rc=ep_departure_image_build(&d,&departure);data=departure.data;bytes=departure.bytes;table=departure.table_offset;functions=departure.function_count;}
        if (rc!=EP_PROPERTY_OK) return rc;
        if (functions>14 || bytes!=table+12*functions || bytes+48!=layout.image_bytes) return EP_PROPERTY_ARGUMENT;
        const uint8_t gate[32]={0x48,0xB8,0,0,0,0,0,0,0,0,0x83,0x38,1,0x75,5,
            0xE9,12,0,0,0,0x48,0xB8,0,0,0,0,0,0,0,0,0xFF,0x20};
        memcpy(result.data,gate,32);memcpy(result.data+2,&control,8);memcpy(result.data+22,&next,8);
        memcpy(result.data+32,data,table);
        uint32_t leaf=32+table,rows[45]={0,32,leaf};result.data[leaf]=1;
        memcpy(rows+3,data+table,12*functions);
        for (unsigned i=0;i<functions;i++) {
            uint32_t uw=rows[3+3*i+2];
            if ((data[uw]>>3)==4) {
                uint32_t chain=uw+4+((data[uw+2]+1u)&~1u)*2u,parent[3];
                if (chain+12>table) return EP_PROPERTY_ARGUMENT;
                memcpy(parent,data+chain,12);for(unsigned j=0;j<3;j++) parent[j]+=32;
                memcpy(result.data+32+chain,parent,12);
            } else if ((data[uw]>>3)==3) {
                if (kind!=EP_ROSTER_STATE_UPDATE) return EP_PROPERTY_ARGUMENT;
                uint32_t at=uw+4+((data[uw+2]+1u)&~1u)*2u,handler;
                if (at+8>table) return EP_PROPERTY_ARGUMENT;
                memcpy(&handler,data+at,4);handler+=32;memcpy(result.data+32+at,&handler,4);
            }
        }
        for (unsigned i=3;i<3+3*functions;i++) rows[i]+=32;
        result.bytes=bytes+48;result.table_offset=leaf+4;result.function_count=functions+1;
        memcpy(result.data+result.table_offset,rows,12*(functions+1));
    }
    if (result.bytes!=layout.image_bytes || result.function_count!=layout.function_count) return EP_PROPERTY_ARGUMENT;
    *out=result;return EP_PROPERTY_OK;
}
