/* Only numeric preparation, our own code allocations and our own stack. */
#include "ep_host_migration.h"
#include <windows.h>
#include <string.h>
#define REQUIRE(x) do {if (!(x)) {result=__LINE__;goto cleanup;}} while (0)
static unsigned hooks;
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {++hooks;return -1;}
extern "C" __declspec(dllexport) int migration_emit(const EpHostMigrationAddresses* a,EpHostMigrationImage* out)
{return ep_host_migration_build(a,out);}
extern "C" __declspec(dllexport) int lookup_emit(const EpHostLifecycleAddresses* a,EpHostLifecycleImage* out)
{return ep_host_lifecycle_build(EP_HOST_LOOKUP,a,out);}
extern "C" __declspec(dllexport) int removal_emit(const EpHostLifecycleAddresses* a,EpHostRemovalImage* out)
{return ep_host_removal_build(a,out);}
extern "C" __declspec(dllexport) int migration_prepare_flow()
{
    HfMod* mod=(HfMod*)0x9195;HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;
    EpHostMigrationAddresses a={{0x140000000,0x180000000,0x2100162c8,0x220000000,0x1c0000000,
        0x220010000,0x220020000,0x220030000,0x220040000,8,0},
        0x220050000,0x220060000,0x220070000,0x220080000,0x180010000,0x180020000};
    EpSessionCodeInfo code={},tasks={};int result=0;
    REQUIRE(ep_host_migration_prepare(&api,mod,&a,&code)==EP_PROPERTY_OK && code.state==EP_CODE_READY);
    {
        alignas(16) uint8_t stack[0x200]={};auto sp=(uintptr_t)stack;
        *(uint64_t*)(sp+0xd8)=0x12345678;*(uint64_t*)(sp+0xd0)=0x55;*(uint64_t*)(sp+0xc8)=0x33;
        *(uint64_t*)(sp+0xc0)=0x66;*(uint64_t*)(sp+0xb8)=0x77;*(uint64_t*)(sp+0xb0)=0xcc;
        *(uint64_t*)(sp+0xa8)=0xdd;*(uint64_t*)(sp+0xa0)=0xee;*(uint64_t*)(sp+0x98)=0xff;
        CONTEXT context={};context.ContextFlags=CONTEXT_FULL;context.Rsp=sp;context.Rip=code.base+160+0x1d;
        DWORD64 base=0,establisher=0;void* handler=nullptr;auto function=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
        REQUIRE(function && base==code.base);
        RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,function,&context,&handler,&establisher,nullptr);
        REQUIRE(context.Rsp==sp+0xe0 && context.Rip==0x12345678 && context.Rbx==0x33 && context.Rbp==0x55 &&
            context.Rsi==0x66 && context.Rdi==0x77 && context.R12==0xcc && context.R13==0xdd && context.R14==0xee && context.R15==0xff);
    }
    {
        auto task_addresses=a.host;task_addresses.code=0x180020000;EpHostRemovalImage image={};
        REQUIRE(ep_host_removal_prepare(&api,mod,&task_addresses,&tasks)==EP_PROPERTY_OK && tasks.state==EP_CODE_READY);
        task_addresses.code=tasks.base;REQUIRE(ep_host_removal_build(&task_addresses,&image)==EP_PROPERTY_OK);
        uint32_t fragment,unwind;memcpy(&fragment,image.data+image.table_offset+13*12,4);
        memcpy(&unwind,image.data+image.table_offset+13*12+8,4);
        alignas(16) uint8_t stack[0x200]={};auto sp=(uintptr_t)stack;
        *(uint64_t*)(sp+0x78)=0x12345678;*(uint64_t*)(sp+0x70)=0x33;*(uint64_t*)(sp+0x68)=0x66;
        *(uint64_t*)(sp+0x60)=0x77;*(uint64_t*)(sp+0x58)=0xcc;*(uint64_t*)(sp+0x88)=0xdd;
        *(uint64_t*)(sp+0x90)=0xee;*(uint64_t*)(sp+0x50)=0xff;*(uint64_t*)(sp+0x80)=0x55;
        CONTEXT context={};context.ContextFlags=CONTEXT_FULL;context.Rsp=sp;context.Rip=tasks.base+fragment+image.data[unwind+1];
        DWORD64 base=0,establisher=0;void* handler=nullptr;auto function=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
        REQUIRE(function && base==tasks.base);
        RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,function,&context,&handler,&establisher,nullptr);
        REQUIRE(context.Rsp==sp+0x80 && context.Rip==0x12345678 && context.Rbx==0x33 && context.Rbp==0x55 &&
            context.Rsi==0x66 && context.Rdi==0x77 && context.R12==0xcc && context.R13==0xdd && context.R14==0xee && context.R15==0xff);
    }
    REQUIRE(!hooks);
cleanup:
    if (tasks.handle && !ep_session_code_discard(mod,tasks.handle)) result=__LINE__;
    if (code.handle && !ep_session_code_discard(mod,code.handle)) result=__LINE__;
    return result;
}
