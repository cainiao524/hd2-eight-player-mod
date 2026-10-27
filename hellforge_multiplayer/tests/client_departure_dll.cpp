#include "ep_client_departure.h"
#include "ep_client_metadata.h"
#include "ep_player_join_image.h"
#include <windows.h>
#include <string.h>
#define REQUIRE(x) do {if (!(x)) {result=__LINE__;goto cleanup;}} while (0)
static unsigned hooks;
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {++hooks;return -1;}
extern "C" __declspec(dllexport) int departure_emit(const EpClientDepartureAddresses* a,EpClientDepartureImage* out)
{return ep_client_departure_build(a,out);}
extern "C" __declspec(dllexport) int departure_metadata_emit(const EpClientMetadataAddresses* a,EpClientMetadataImage* out)
{return ep_client_metadata_build(a,out);}
extern "C" __declspec(dllexport) int departure_join_emit(uint64_t game,uint64_t code,uint64_t control,uint64_t next,
    uint64_t reject,const EpPlayerJoinPeers* p,const EpPlayerJoinReadiness* r,EpPlayerJoinImage* out)
{return ep_player_join_ready_gate_build(game,code,control,next,reject,p,r,out);}
extern "C" __declspec(dllexport) int departure_prepare_flow()
{
    HfMod* mod=(HfMod*)0x919b;HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;
    EpClientDepartureAddresses a={{0x140000000,0x1800e0000,0x2100162c8,0x220000000,0x1c0000000,8,0},
        0x220070000,0x220050000,0x220080000,0x220060000,0x220090000,0x1800d0400};
    EpSessionCodeInfo code={};EpClientDepartureImage image={};int result=0;
    REQUIRE(ep_client_departure_prepare(&api,mod,&a,&code)==EP_PROPERTY_OK && code.state==EP_CODE_READY);
    a.client.code=code.base;REQUIRE(ep_client_departure_build(&a,&image)==EP_PROPERTY_OK);
    {
        uint32_t fragment;memcpy(&fragment,image.data+image.table_offset+2*12,4);
        alignas(16) uint8_t stack[0x80]={};auto sp=(uintptr_t)stack;
        *(uint64_t*)(sp+0x28)=0x12345678;*(uint64_t*)(sp+0x20)=0xee;*(uint64_t*)(sp+0x40)=0x33;
        *(uint64_t*)(sp+0x48)=0x77;*(uint64_t*)(sp+0x30)=0x55;*(uint64_t*)(sp+0x38)=0x66;
        CONTEXT context={};context.ContextFlags=CONTEXT_FULL;context.Rsp=sp;context.Rip=code.base+fragment+10;
        DWORD64 base=0,establisher=0;void* handler=nullptr;auto function=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
        REQUIRE(function && base==code.base);
        RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,function,&context,&handler,&establisher,nullptr);
        REQUIRE(context.Rsp==sp+0x30 && context.Rip==0x12345678 && context.Rbx==0x33 && context.Rdi==0x77 &&
            context.R14==0xee && context.Rbp==0x55 && context.Rsi==0x66);
    }
    REQUIRE(!hooks);
cleanup:
    if (code.handle && !ep_session_code_discard(mod,code.handle)) result=__LINE__;
    return result;
}
