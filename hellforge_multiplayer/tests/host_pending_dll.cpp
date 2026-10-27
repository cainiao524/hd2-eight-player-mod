/* Numeric preparation and unwind of owned memory only; no game or hook. */
#include "ep_host_pending.h"
#include <windows.h>
#include <string.h>
#define REQUIRE(x) do {if (!(x)) {result=__LINE__;goto cleanup;}} while (0)
static unsigned hooks;
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {++hooks;return -1;}
extern "C" __declspec(dllexport) int pending_emit(const EpHostPendingAddresses* a,EpHostPendingImage* out)
{return ep_host_pending_build(a,out);}
extern "C" __declspec(dllexport) int pending_prepare_flow()
{
    HfMod* mod=(HfMod*)0x9196;HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;
    EpHostPendingAddresses a={{0x140000000,0x180000000,0x2100162c8,0x220000000,0x1c0000000,
        0x220010000,0x220020000,0x220030000,0x220040000,8,0},0x180020000};
    EpSessionCodeInfo code={};EpHostPendingImage image={};int result=0;
    REQUIRE(ep_host_pending_prepare(&api,mod,&a,&code)==EP_PROPERTY_OK && code.state==EP_CODE_READY);
    a.host.code=code.base;REQUIRE(ep_host_pending_build(&a,&image)==EP_PROPERTY_OK);
    {
        uint32_t fragment;memcpy(&fragment,image.data+image.table_offset+5*12,4);
        alignas(16) uint8_t stack[0x200]={};auto sp=(uintptr_t)stack;
        *(uint64_t*)(sp+0xe8)=0x12345678;*(uint64_t*)(sp+0xe0)=0x55;*(uint64_t*)(sp+0xd8)=0x33;
        *(uint64_t*)(sp+0xd0)=0x66;*(uint64_t*)(sp+0xc8)=0xcc;*(uint64_t*)(sp+0xc0)=0x77;
        *(uint64_t*)(sp+0xb8)=0xdd;*(uint64_t*)(sp+0xb0)=0xee;*(uint64_t*)(sp+0xa8)=0xff;
        CONTEXT context={};context.ContextFlags=CONTEXT_FULL;context.Rsp=sp;context.Rip=code.base+fragment+1;
        DWORD64 base=0,establisher=0;void* handler=nullptr;auto function=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
        REQUIRE(function && base==code.base);
        RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,function,&context,&handler,&establisher,nullptr);
        REQUIRE(context.Rsp==sp+0xf0 && context.Rip==0x12345678 && context.Rbx==0x33 && context.Rbp==0x55 &&
            context.Rsi==0x66 && context.Rdi==0x77 && context.R12==0xcc && context.R13==0xdd && context.R14==0xee && context.R15==0xff);
    }
    REQUIRE(!hooks);
cleanup:
    if (code.handle && !ep_session_code_discard(mod,code.handle)) result=__LINE__;
    return result;
}
