/* The fixture allocates/registers only its own candidate code and stack. */
#include "ep_client_metadata.h"
#include "ep_host_accept.h"
#include <windows.h>
#include <string.h>
#define REQUIRE(x) do {if (!(x)) {result=__LINE__;goto cleanup;}} while (0)
static unsigned hooks;
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {++hooks;return -1;}
extern "C" __declspec(dllexport) int metadata_emit(const EpClientMetadataAddresses* a,EpClientMetadataImage* out)
{return ep_client_metadata_build(a,out);}
extern "C" __declspec(dllexport) int metadata_receive_emit(const EpHostAcceptAddresses* a,EpHostAcceptImage* out)
{return ep_host_accept_build(a,out);}
extern "C" __declspec(dllexport) int metadata_prepare_flow()
{
    HfMod* mod=(HfMod*)0x919a;HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;
    EpClientMetadataAddresses a={0x140000000,0x1800d0000,0x2100162c8,0x220060000,0x220070000,0x1c0000000,8,0};
    EpSessionCodeInfo code={};EpClientMetadataImage image={};int result=0;
    REQUIRE(ep_client_metadata_prepare(&api,mod,&a,&code)==EP_PROPERTY_OK && code.state==EP_CODE_READY);
    a.code=code.base;REQUIRE(ep_client_metadata_build(&a,&image)==EP_PROPERTY_OK);
    {
        uint32_t fragment;memcpy(&fragment,image.data+image.table_offset+3*12,4);
        alignas(16) uint8_t stack[0x80]={};auto sp=(uintptr_t)stack;
        *(uint64_t*)(sp+0x28)=0x12345678;*(uint64_t*)(sp+0x20)=0x77;*(uint64_t*)(sp+0x30)=0x33;
        CONTEXT context={};context.ContextFlags=CONTEXT_FULL;context.Rsp=sp;context.Rip=code.base+fragment+10;
        DWORD64 base=0,establisher=0;void* handler=nullptr;auto function=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
        REQUIRE(function && base==code.base);
        RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,function,&context,&handler,&establisher,nullptr);
        REQUIRE(context.Rsp==sp+0x30 && context.Rip==0x12345678 && context.Rbx==0x33 && context.Rdi==0x77);
    }
    REQUIRE(!hooks);
cleanup:
    if (code.handle && !ep_session_code_discard(mod,code.handle)) result=__LINE__;
    return result;
}
