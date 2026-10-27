/* Own allocations only, including the expanded frame and GS/unwind profile. */
#include "ep_host_update.h"
#include <windows.h>
#include <string.h>
#define REQUIRE(x) do {if (!(x)) {result=__LINE__;goto cleanup;}} while (0)
static unsigned hooks;
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {++hooks;return -1;}
extern "C" __declspec(dllexport) int update_emit(const EpHostUpdateAddresses* a,EpHostUpdateImage* out)
{return ep_host_update_build(a,out);}
extern "C" __declspec(dllexport) int update_prepare_flow()
{
    HfMod* mod=(HfMod*)0x9197;HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;
    EpHostUpdateAddresses a={{0x140000000,0x180010000,0x2100162c8,0x220000000,0x1c0000000,
        0x220010000,0x220020000,0x220030000,0x220040000,8,0},0x220050000,
        0x180020000,0x180030000,0x180040000,0x180050000,0x180060000,0x180070000};
    EpSessionCodeInfo code={};EpHostUpdateImage image={};int result=0;
    REQUIRE(ep_host_update_prepare(&api,mod,&a,&code)==EP_PROPERTY_OK && code.state==EP_CODE_READY);
    a.host.code=code.base;REQUIRE(ep_host_update_build(&a,&image)==EP_PROPERTY_OK);
    {
        uint32_t fragment;memcpy(&fragment,image.data+image.table_offset+3*12,4);
        alignas(16) uint8_t stack[0x700]={};auto sp=(uintptr_t)stack;
        *(uint64_t*)(sp+0x578)=0x12345678;*(uint64_t*)(sp+0x570)=0x55;*(uint64_t*)(sp+0x568)=0x33;
        *(uint64_t*)(sp+0x560)=0x77;*(uint64_t*)(sp+0x558)=0xcc;*(uint64_t*)(sp+0x388)=0x66;
        *(uint64_t*)(sp+0x390)=0xdd;*(uint64_t*)(sp+0x398)=0xee;*(uint64_t*)(sp+0x350)=0xff;
        *(uint64_t*)(sp+0x340)=0x6666;*(uint64_t*)(sp+0x348)=0x7777;
        CONTEXT context={};context.ContextFlags=CONTEXT_FULL;context.Rsp=sp;context.Rip=code.base+fragment+8;
        DWORD64 base=0,establisher=0;void* handler=nullptr;auto function=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
        REQUIRE(function && base==code.base);
        RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,function,&context,&handler,&establisher,nullptr);
        REQUIRE(context.Rsp==sp+0x580 && context.Rip==0x12345678 && context.Rbx==0x33 && context.Rbp==0x55 &&
            context.Rsi==0x66 && context.Rdi==0x77 && context.R12==0xcc && context.R13==0xdd && context.R14==0xee && context.R15==0xff &&
            context.Xmm6.Low==0x6666 && context.Xmm6.High==0x7777);
    }
    REQUIRE(!hooks);
cleanup:
    if (code.handle && !ep_session_code_discard(mod,code.handle)) result=__LINE__;
    return result;
}
