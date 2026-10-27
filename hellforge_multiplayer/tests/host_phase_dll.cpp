/* Preparation and Windows unwind exercise only our own code/stack buffers. */
#include "ep_host_phase.h"
#include "ep_host_removal.h"
#include <windows.h>
#include <string.h>
#define REQUIRE(x) do {if (!(x)) {result=__LINE__;goto cleanup;}} while (0)
static unsigned hooks;
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {++hooks;return -1;}
extern "C" __declspec(dllexport) int phase_emit(const EpHostPhaseAddresses* a,EpHostPhaseImage* out)
{return ep_host_phase_build(a,out);}
extern "C" __declspec(dllexport) int lookup_emit(const EpHostLifecycleAddresses* a,EpHostRemovalImage* out)
{return ep_host_removal_build(a,out);}
extern "C" __declspec(dllexport) int phase_prepare_flow()
{
    HfMod* mod=(HfMod*)0x9198;HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;
    EpHostPhaseAddresses a={{0x140000000,0x180080000,0x2100162c8,0x220000000,0x1c0000000,
        0x220010000,0x220020000,0x220030000,0x220040000,8,0},0x180090000};
    EpSessionCodeInfo code={};EpHostPhaseImage image={};int result=0;
    REQUIRE(ep_host_phase_prepare(&api,mod,&a,&code)==EP_PROPERTY_OK && code.state==EP_CODE_READY);
    a.host.code=code.base;REQUIRE(ep_host_phase_build(&a,&image)==EP_PROPERTY_OK);
    for (unsigned index=0;index<2;index++) {
        const unsigned row=index ? 6 : 2;uint32_t fragment;memcpy(&fragment,image.data+image.table_offset+row*12,4);
        alignas(16) uint8_t stack[0x940]={};auto sp=(uintptr_t)stack;
        if (index) {
            *(uint64_t*)(sp+0x8c8)=0x12345678;*(uint64_t*)(sp+0x8c0)=0x55;
            *(uint64_t*)(sp+0x8b8)=0x33;*(uint64_t*)(sp+0x8b0)=0x66;*(uint64_t*)(sp+0x8a8)=0xcc;
            *(uint64_t*)(sp+0x8a0)=0xff;*(uint64_t*)(sp+0x8e0)=0x77;*(uint64_t*)(sp+0x8e8)=0xee;
            *(uint64_t*)(sp+0x890)=0x6666;*(uint64_t*)(sp+0x898)=0x7777;
        } else {
            *(uint64_t*)(sp+0x68)=0x12345678;*(uint64_t*)(sp+0x60)=0x55;
            *(uint64_t*)(sp+0x58)=0x33;*(uint64_t*)(sp+0x50)=0x66;*(uint64_t*)(sp+0x48)=0x77;
            *(uint64_t*)(sp+0x40)=0xee;*(uint64_t*)(sp+0x70)=0xff;
        }
        CONTEXT context={};context.ContextFlags=CONTEXT_FULL;context.Rsp=sp;context.Rip=code.base+fragment+(index ? 31 : 5);
        DWORD64 base=0,establisher=0;void* handler=nullptr;auto function=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
        REQUIRE(function && base==code.base);
        RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,function,&context,&handler,&establisher,nullptr);
        REQUIRE(context.Rsp==sp+(index ? 0x8d0 : 0x70) && context.Rip==0x12345678 && context.Rbx==0x33 &&
            context.Rbp==0x55 && context.Rsi==0x66 && context.Rdi==0x77 && context.R14==0xee && context.R15==0xff);
        if (index) REQUIRE(context.R12==0xcc && context.Xmm6.Low==0x6666 && context.Xmm6.High==0x7777);
    }
    REQUIRE(!hooks);
cleanup:
    if (code.handle && !ep_session_code_discard(mod,code.handle)) result=__LINE__;
    return result;
}
