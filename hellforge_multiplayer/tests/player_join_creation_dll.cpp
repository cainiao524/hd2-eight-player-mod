/* One reject -> completed-native-failure cleanup -> successful retry flow.
 * Real checked creation, call bridge, owner and SEH boundary. Engine functions
 * and their side effects are explicit fixtures, all memory test-owned. */
#include "ep_player_join_call.h"
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <initializer_list>
#define NEED(x) do {if (!(x)) {fprintf(stderr,"join flow line %d: %s\n",__LINE__,#x);abort();}} while (0)
namespace {
constexpr uintptr_t game=0x140000000;constexpr uint64_t resource=0xcdc1f82ce3337a82;
uintptr_t context,resourceOwner,descriptor,roster,storage,owner8,metadata;
uint64_t owner;HfMod* mod=(HfMod*)0x9189;
unsigned freed,created,removed,ordinal_removed,notified;bool allocate;uint32_t handle=0x1357;
struct Record {uint64_t resource;uint32_t handle,network,ordinal,flags;};
template<class T> T& Ref(uintptr_t address) {return *(T*)address;}
uintptr_t Alloc(size_t n) {auto p=(uintptr_t)VirtualAlloc(nullptr,n,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);NEED(p);return p;}
void CheckOwner() {NEED(ep_roster_owner_native_status(mod,owner)==EP_OWNER_OK);}
void Map(uintptr_t at,unsigned size)
{
    auto p=Alloc(size*8);memset((void*)p,0xff,size*8);Ref<uintptr_t>(at)=p;
    Ref<uint32_t>(at+8)=size;Ref<uint32_t>(at+12)=UINT32_MAX;Ref<uint32_t>(at+16)=1;
}
void Put(uintptr_t map,uint32_t key,uint32_t value)
{
    auto slots=Ref<uintptr_t>(map);auto count=Ref<uint32_t>(map+8);
    for (uint32_t i=0;i<count;i++) {auto p=slots+8*((key+i)&(count-1));
        if (Ref<uint32_t>(p)==UINT32_MAX) {Ref<uint32_t>(p)=key;Ref<uint32_t>(p+4)=value;return;}}
    NEED(false);
}
void Erase(uintptr_t map,uint32_t key)
{
    auto slots=Ref<uintptr_t>(map);for (unsigned i=0;i<Ref<uint32_t>(map+8);i++)
        if (Ref<uint32_t>(slots+i*8)==key) {Ref<uint32_t>(slots+i*8)=UINT32_MAX;return;}
    NEED(false);
}
void Free(uint32_t h) {CheckOwner();NEED(h==handle);++freed;}
void Create(uintptr_t c,uint32_t h,uint64_t hash,uintptr_t meta)
{
    CheckOwner();NEED(c==context && h==handle && hash==resource && meta==metadata);++created;
    uint32_t cursor=Ref<uint32_t>(c+0xf32f14),n=Ref<uint32_t>(roster+0x80),unit=allocate ? 0x77 : 0x7fff;
    auto record=c+0xf32f18+cursor*24;Ref<Record>(record)={hash,h,0,unit,1};
    Put(c+0xf1aeb0,h,cursor);Put(roster+0xd0,h,n);Put(c+0x3d38,h,n);
    Ref<uintptr_t>(storage+8*n)=record;
    for (auto at:{roster+0x80,c+0x3ce8}) for (unsigned i=0;i<3;i++) ++Ref<uint32_t>(at+4*i);
    auto ordinal=Ref<uint32_t>(owner8+0x18)++;Put(owner8+0xb020,unit,ordinal);Ref<uint32_t>(owner8+0x1c+ordinal*4)=unit;
    if (unit!=0x7fff) Put(c+0xf22ec8,unit,cursor);
    ++Ref<uint32_t>(c+0xf32f14);
}
void Remove(uintptr_t c,uintptr_t record,uint8_t flag)
{
    CheckOwner();NEED(c==context && flag==1 && Ref<Record>(record).ordinal==0x7fff);++removed;
    Erase(c+0xf1aeb0,handle);Erase(roster+0xd0,handle);Erase(c+0x3d38,handle);
    for (auto at:{roster+0x80,c+0x3ce8}) for (unsigned i=0;i<3;i++) --Ref<uint32_t>(at+4*i);
    Ref<Record>(record)={resource,UINT32_MAX,0,0x7fff,0};Free(handle);
    // Original FDC820 skips FDDC80 for the sentinel; preserve that gap here.
}
void RemoveOrdinal(uintptr_t o,uint32_t key)
{CheckOwner();NEED(o==owner8 && key==0x7fff);++ordinal_removed;Erase(o+0xb020,key);--Ref<uint32_t>(o+0x18);}
void Jump(uintptr_t at,uintptr_t target)
{uint8_t code[]={0x48,0xb8,0,0,0,0,0,0,0,0,0xff,0xe0};memcpy(code+2,&target,8);memcpy((void*)at,code,12);}
void NativeJoin()
{CheckOwner();using F=uint32_t (*)(uintptr_t,uint32_t,uint64_t,uintptr_t);
 if (((F)ep_player_join_creation_entry())(context,handle,resource,metadata)) ++notified;}
int Read(void*,uintptr_t at,void* out,size_t n) {memcpy(out,(void*)at,n);return 1;}
struct Invocation {EpRosterCallContext call;EpRosterCallFrame frame;};
int Invoke(void* p,const EpNativeRosterView* view)
{auto* i=(Invocation*)p;return ep_player_join_invoke(&i->call,&i->frame,view,(uintptr_t)NativeJoin);}
}
extern "C" __declspec(dllexport) int player_join_creation_flow()
{
    NEED(VirtualAlloc((void*)game,74727424,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==(void*)game);
    context=Alloc(0x1000000);resourceOwner=Alloc(0x1000000);roster=Alloc(0x1000);storage=Alloc(0x1000);
    owner8=Alloc(0xc000);metadata=Alloc(0x100);auto table=Alloc(0x20000),list=Alloc(0x100);
    Ref<uintptr_t>(game+0x3326468)=roster;Ref<uintptr_t>(game+0x33267b8)=context+0x3ce0;
    Ref<uint32_t>(game+0x348456c)=UINT32_MAX;Ref<uintptr_t>(game+0x346bf98)=resourceOwner;
    Ref<uintptr_t>(resourceOwner+0xf12ea0)=table;
    descriptor=table+32*(resource&0xfff);Ref<uint64_t>(descriptor)=resource;Ref<uintptr_t>(descriptor+8)=list;
    Ref<uint32_t>(descriptor+16)=9;Ref<uint32_t>(descriptor+24)=UINT32_MAX;
    const uint16_t types[]={3,33,41,43,226,238,239,250,260};memcpy((void*)list,types,sizeof(types));
    Ref<uint8_t>(metadata)=1;Ref<uintptr_t>(context+8)=owner8;Ref<uint32_t>(context+0xf32f14)=4;
    for (unsigned i=0;i<0x800;i++) Ref<uint32_t>(context+0xf32f20+24*i)=UINT32_MAX;
    for (auto at:{roster+0x80,context+0x3ce8}) for (unsigned i=0;i<3;i++) Ref<uint32_t>(at+4*i)=4;
    Map(context+0xf1aeb0,16);Map(context+0xf22ec8,16);Map(owner8+0xb020,16);Map(roster+0xd0,8);Map(context+0x3d38,8);
    Ref<uint32_t>(owner8+0x18)=4;
    for (unsigned i=0;i<4;i++) {
        Put(context+0xf1aeb0,0x100+i,i);Put(roster+0xd0,0x100+i,i);Put(context+0x3d38,0x100+i,i);
        Put(owner8+0xb020,0x20+i,i);Put(context+0xf22ec8,0x20+i,i);Ref<uint32_t>(owner8+0x1c+i*4)=0x20+i;
    }
    auto api=Alloc(0x1000),service=Alloc(0x100),vtable=Alloc(0x100);
    Ref<uintptr_t>(game+0x3326308)=api;Ref<uintptr_t>(api+0xc0)=service;Ref<uintptr_t>(service)=vtable;
    Ref<uintptr_t>(vtable+8)=(uintptr_t)Free;
    Jump(game+0xfdc140,(uintptr_t)Create);Jump(game+0xfdc820,(uintptr_t)Remove);Jump(game+0xfddc80,(uintptr_t)RemoveOrdinal);
    DWORD old;NEED(VirtualProtect((void*)(game+0xfdc000),0x2000,PAGE_EXECUTE_READ,&old));
    NEED(FlushInstructionCache(GetCurrentProcess(),(void*)(game+0xfdc000),0x2000));
    EpNativeRosterView view={};view.game=game;view.roster=roster;view.storage=storage;view.epoch=1;view.build=25480438;
    EpRosterMemory memory={nullptr,Read};NEED(ep_roster_owner_create(mod,&view,&memory,&owner)==EP_OWNER_OK);
    Invocation call={};call.call.mod=mod;call.call.owner=owner;
    call.call.game=game;call.call.roster=roster;call.call.storage=storage;
    NEED(ep_roster_owner_call(mod,owner,1,Invoke,&call)==EP_OWNER_OK);
    NEED(call.frame.padding==EP_JOIN_RESOURCE && freed==1 && !created && !notified && Ref<uint32_t>(context+0xf32f14)==4);
    Ref<uint32_t>(descriptor+24)=17;++handle;
    NEED(ep_roster_owner_call(mod,owner,1,Invoke,&call)==EP_OWNER_OK);
    NEED(call.frame.padding==EP_JOIN_CLEANED && freed==2 && created==1 && removed==1 && ordinal_removed==1 && !notified);
    NEED(Ref<uint32_t>(owner8+0x18)==4 && Ref<uint32_t>(roster+0x80)==4 && call.frame.reserved<=65536);
    allocate=true;++handle;
    NEED(ep_roster_owner_call(mod,owner,1,Invoke,&call)==EP_OWNER_OK);
    NEED(call.frame.padding==EP_JOIN_OK && created==2 && notified==1 && freed==2 && Ref<uint32_t>(owner8+0x18)==5);
    NEED(call.frame.reserved<=65536 && !ep_roster_owner_in_scope());
    NEED(ep_roster_owner_close(mod,owner)==EP_OWNER_OK);
    return 0; // disposable worker owns allocations; no persisted game/process effects
}
