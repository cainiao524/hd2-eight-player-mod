#include "ep_player_join_call.h"
#include <windows.h>
#include <string.h>
extern "C" int EpOwnerInvoke(int (*)(void*),void*,int*);
extern "C" void EpRosterCallTarget(EpRosterCallFrame*,uintptr_t,unsigned);
namespace {
struct Join {
    EpRosterCallContext* call;EpRosterCallFrame* frame;const EpNativeRosterView* view;
    uintptr_t body;uint32_t reads,status;bool entered;
};
thread_local Join* current;
struct Map {uintptr_t slots;uint32_t capacity,empty,multiplier;};
struct Record {uint64_t resource;uint32_t handle,network,ordinal,flags;};
static_assert(sizeof(Record)==24,"native record ABI");
[[noreturn]] void Fault(uint32_t status)
{
    if (current) current->status=status;
    RaiseException(0xe045504au,EXCEPTION_NONCONTINUABLE,0,nullptr);
    __builtin_unreachable();
}
bool Pointer(uintptr_t address,size_t size)
{return address>=0x10000 && address<=(UINT64_C(1)<<47)-size;}
void Read(uintptr_t address,void* output,size_t bytes)
{
    if (!current || !Pointer(address,bytes)) Fault(EP_JOIN_LAYOUT);
    if (bytes>65536-current->reads) Fault(EP_JOIN_READ_LIMIT);
    current->reads+=(uint32_t)bytes;memcpy(output,(const void*)address,bytes);
}
template<class T> T Get(uintptr_t address) {T value;Read(address,&value,sizeof(value));return value;}
void Healthy()
{if (ep_roster_owner_native_status(current->call->mod,current->call->owner)!=EP_OWNER_OK) Fault(EP_JOIN_FAULT);}
Map MapAt(uintptr_t address)
{
    Map m={};Read(address,&m,20);
    if (!Pointer(m.slots,8ull*m.capacity) || !m.capacity || m.capacity>8192 ||
        (m.capacity&(m.capacity-1)) || m.slots%8) Fault(EP_JOIN_LAYOUT);
    return m;
}
// 1 found, 0 absent with a free bucket, -1 full and absent. Never write here.
int Find(const Map& map,uint32_t key,uint32_t* value=nullptr)
{
    if (key==map.empty) Fault(EP_JOIN_LAYOUT);
    for (uint32_t probe=0;probe<map.capacity;probe++) {
        uint32_t pair[2];auto slot=(key*map.multiplier+probe)&(map.capacity-1);
        Read(map.slots+8ull*slot,pair,8);
        if (pair[0]==map.empty) return 0;
        if (pair[0]==key) {if (value) *value=pair[1];return 1;}
    }
    return -1;
}
bool Room(const Map& map)
{
    for (uint32_t i=0;i<map.capacity;i++) if (Get<uint32_t>(map.slots+8ull*i)==map.empty) return true;
    return false;
}
uint32_t Count(uintptr_t address)
{
    uint32_t v[3];Read(address,v,12);
    if (v[0]>8 || v[1]>v[0] || v[2]>v[1]) Fault(EP_JOIN_LAYOUT);
    return v[0];
}
bool PlayerResource(uintptr_t game,uint64_t hash)
{
    auto owner=Get<uintptr_t>(game+0x346bf98),table=Get<uintptr_t>(owner+0xf12ea0);
    if (!Pointer(table,0x20000)) Fault(EP_JOIN_LAYOUT);
    for (uint32_t i=0;i<4096;i++) {
        auto at=table+32*((uint32_t(hash)+i)&0xfff);auto key=Get<uint64_t>(at);
        if (!key) return false;if (key!=hash) continue;
        auto components=Get<uintptr_t>(at+8);auto count=Get<uint32_t>(at+16);
        if (count!=9 || Get<uint32_t>(at+24)==UINT32_MAX) return false;
        const uint16_t expected[]={3,33,41,43,226,238,239,250,260};uint16_t actual[9];
        Read(components,actual,sizeof(actual));return !memcmp(actual,expected,sizeof(actual));
    }
    return false;
}
using FreeHandle=void (*)(uint32_t);
using Create=void (*)(uintptr_t,uint32_t,uint64_t,uintptr_t);
using Remove=void (*)(uintptr_t,uintptr_t,uint8_t);
using RemoveOrdinal=void (*)(uintptr_t,uint32_t);
uint32_t Reject(FreeHandle release,uint32_t handle,uint32_t status)
{release(handle);Healthy();current->status=status;return 0;}
uint32_t CheckedCreate(uintptr_t context,uint32_t handle,uint64_t resource,uintptr_t metadata)
{
    if (!current || current->entered) Fault(EP_JOIN_BINDING);
    current->entered=true;current->status=EP_JOIN_OK;Healthy();auto game=current->view->game,roster=current->view->roster;
    if (!Pointer(context,0xf3f830) || resource!=UINT64_C(0xcdc1f82ce3337a82) ||
        !handle || Get<uint8_t>(metadata)!=1 || Get<uintptr_t>(game+0x3326468)!=roster ||
        Get<uintptr_t>(game+0x33267b8)!=context+0x3ce0) Fault(EP_JOIN_BINDING);
    auto empty=Get<uint32_t>(game+0x348456c);
    if (handle==empty) Fault(EP_JOIN_BINDING);
    auto forward=MapAt(context+0xf1aeb0);int present=Find(forward,handle);
    if (present==1) Fault(EP_JOIN_DUPLICATE); // Never release an already-live handle.
    auto api=Get<uintptr_t>(game+0x3326308),service=Get<uintptr_t>(api+0xc0),vtable=Get<uintptr_t>(service);
    auto release=(FreeHandle)Get<uintptr_t>(vtable+8);
    if (!Pointer((uintptr_t)release,1)) Fault(EP_JOIN_BINDING);
    if (present<0) return Reject(release,handle,EP_JOIN_MAP_FULL);
    auto n=Count(roster+0x80),s=Count(context+0x3ce8);
    if (n==8 || s==8) return Reject(release,handle,EP_JOIN_CAPACITY);
    auto rosterMap=MapAt(roster+0xd0),componentMap=MapAt(context+0x3d38);
    if (rosterMap.capacity!=8 || componentMap.capacity!=8) Fault(EP_JOIN_LAYOUT);
    if (Find(rosterMap,handle)==1 || Find(componentMap,handle)==1) Fault(EP_JOIN_DUPLICATE);
    if (!Room(rosterMap) || !Room(componentMap)) return Reject(release,handle,EP_JOIN_MAP_FULL);
    auto cursor=Get<uint32_t>(context+0xf32f14);
    if (cursor>=0x800) Fault(EP_JOIN_LAYOUT);
    auto record=context+0xf32f18+24ull*cursor;auto before=Get<Record>(record);
    if (before.handle!=empty) return Reject(release,handle,EP_JOIN_RECORD_BUSY);
    auto owner8=Get<uintptr_t>(context+8);auto count8=Get<uint32_t>(owner8+0x18);
    if (count8>=0x800 || Get<uint8_t>(owner8+0x301d)) return Reject(release,handle,EP_JOIN_OWNER_FULL);
    auto ownerMap=MapAt(owner8+0xb020),reverse=MapAt(context+0xf22ec8);
    if (Find(ownerMap,0x7fff)==1) Fault(EP_JOIN_LAYOUT);
    if (!Room(ownerMap) || !Room(reverse)) return Reject(release,handle,EP_JOIN_MAP_FULL);
    if (!PlayerResource(game,resource)) return Reject(release,handle,EP_JOIN_RESOURCE);
    if (current->reads>61440) return Reject(release,handle,EP_JOIN_READ_LIMIT);
    ((Create)(game+0xfdc140))(context,handle,resource,metadata);Healthy();
    auto after=Get<Record>(record);uint32_t value=0,slot=0;
    if (after.resource!=resource || after.handle!=handle || !(after.flags&1) ||
        Find(forward,handle,&value)!=1 || value!=cursor || Count(roster+0x80)!=n+1 ||
        Count(context+0x3ce8)!=s+1 || Find(rosterMap,handle,&slot)!=1 || slot>=n+1 ||
        Get<uintptr_t>(current->view->storage+8ull*slot)!=record || Find(componentMap,handle,&slot)!=1 || slot>=s+1)
        Fault(EP_JOIN_POSTCONDITION);
    if (after.ordinal!=0x7fff) {
        if (Find(reverse,after.ordinal,&value)!=1 || value!=cursor ||
            Find(ownerMap,after.ordinal,&value)!=1 || value>=0x800 ||
            Get<uint32_t>(owner8+0x1c+4ull*value)!=after.ordinal ||
            Get<uint32_t>(owner8+0x18)!=count8+1) Fault(EP_JOIN_POSTCONDITION);
        return 1;
    }
    // FDC140 finished all phases. A failed native unit allocation can still
    // have inserted the 7FFF key into owner8; FDC820 deliberately skips it.
    auto now8=Get<uint32_t>(owner8+0x18);int sentinel=Find(ownerMap,0x7fff,&value);
    if (!((now8==count8 && sentinel!=1) || (now8==count8+1 && sentinel==1 && value==count8)))
        Fault(EP_JOIN_POSTCONDITION);
    ((Remove)(game+0xfdc820))(context,record,1);Healthy();
    if (sentinel==1) {((RemoveOrdinal)(game+0xfddc80))(owner8,0x7fff);Healthy();}
    auto removed=Get<Record>(record);
    if (removed.handle!=empty || removed.ordinal!=0x7fff || removed.flags || removed.network ||
        Count(roster+0x80)!=n || Count(context+0x3ce8)!=s || Find(forward,handle)==1 ||
        Find(rosterMap,handle)==1 || Find(componentMap,handle)==1 || Find(ownerMap,0x7fff)==1 ||
        Get<uint32_t>(owner8+0x18)!=count8) Fault(EP_JOIN_POSTCONDITION);
    current->status=EP_JOIN_CLEANED;return 0;
}
int Run(void* opaque)
{auto* j=(Join*)opaque;EpRosterCallTarget(j->frame,j->body,0);Healthy();return 1;}
}
uintptr_t ep_player_join_creation_entry(void) {return (uintptr_t)CheckedCreate;}
int ep_player_join_invoke(EpRosterCallContext* call,EpRosterCallFrame* frame,const EpNativeRosterView* view,uintptr_t body)
{
    if (!frame) return 0;
    frame->reserved=0;frame->padding=EP_JOIN_NOT_ATTEMPTED;
    if (!call || !view || !body || current || view->game!=call->game || view->roster!=call->roster ||
        view->storage!=call->storage || ep_roster_owner_native_status(call->mod,call->owner)!=EP_OWNER_OK)
        {frame->padding=EP_JOIN_BINDING;return 0;}
    Join j={call,frame,view,body,0,EP_JOIN_NOT_ATTEMPTED,false};current=&j;int fault=0;
    int ok=EpOwnerInvoke(Run,&j,&fault);current=nullptr;
    frame->reserved=j.reads;
    frame->padding=fault && (j.status==EP_JOIN_OK || j.status==EP_JOIN_NOT_ATTEMPTED) ? EP_JOIN_FAULT : j.status;
    return ok && !fault;
}
