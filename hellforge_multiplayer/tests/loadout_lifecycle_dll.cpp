#include "ep_loadout_lifecycle.h"
#include <windows.h>
#include <string.h>
extern "C" __declspec(dllexport) int loadout_build(const EpLoadoutAddresses* a,EpLoadoutImage* b)
{return ep_loadout_lifecycle_build(a,b);}
static const char* TestBuild() {return "25480438";}
static int NoHooks(HfMod*,uintptr_t,void*,void**,int32_t) {return 1;}
extern "C" __declspec(dllexport) int loadout_prepare_test(const EpLoadoutAddresses* input)
{
    HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=TestBuild;api.hook_ex=NoHooks;
    auto* mod=(HfMod*)(uintptr_t)0x9181;EpSessionCodeInfo code={};EpLoadoutImage image={};
    int status=ep_loadout_lifecycle_prepare(&api,mod,input,&code);
    if (status!=EP_PROPERTY_OK) return 1;
    int failure=0;EpLoadoutAddresses a=*input;a.code=code.base;
    if (ep_loadout_lifecycle_build(&a,&image)!=EP_PROPERTY_OK || code.state!=EP_CODE_READY || !code.registered || code.pinned ||
        memcmp((void*)code.base,image.data,image.bytes)) failure=2;
    for (unsigned i=0;i<6 && !failure;i++) {
        const auto* row=(const RUNTIME_FUNCTION*)(image.data+image.table_offset)+i;DWORD64 base=0;
        auto* live=RtlLookupFunctionEntry(code.base+row->BeginAddress,&base,nullptr);
        if (!live || base!=code.base || memcmp(live,row,sizeof(*row))) failure=3;
    }
    if (!ep_session_code_discard(mod,code.handle)) failure=4;
    if (ep_session_code_info(mod,code.handle,&code)) failure=5;
    return failure;
}
/* The input is an emulator stack/register snapshot, never a game context.
 * RtlVirtualUnwind operates on this helper's local backing memory only. */
extern "C" __declspec(dllexport) int loadout_unwind(const EpLoadoutImage* image,uint32_t offset,
    int32_t stack_delta,const uint64_t* registers,const uint8_t* stack_data,uint64_t return_address)
{
    alignas(16) uint8_t code[4096],stack[528];memcpy(code,image->data,image->bytes);memcpy(stack+8,stack_data,512);
    const auto* rows=(const RUNTIME_FUNCTION*)(code+image->table_offset);const RUNTIME_FUNCTION* row=nullptr;
    for (unsigned i=0;i<image->function_count;i++) if (rows[i].BeginAddress<=offset && offset<rows[i].EndAddress) row=rows+i;
    if (!row || stack_delta < -128 || stack_delta>0) return 1;
    CONTEXT c={};c.ContextFlags=CONTEXT_ALL;c.Rip=(DWORD64)code+offset;c.Rsp=(DWORD64)(stack+264)+stack_delta;
    c.Rbx=registers[0];c.Rbp=registers[1];c.Rsi=registers[2];c.Rdi=registers[3];
    c.R12=registers[4];c.R13=registers[5];c.R14=registers[6];c.R15=registers[7];
    void* handler=nullptr;DWORD64 frame=0;
    RtlVirtualUnwind(UNW_FLAG_NHANDLER,(DWORD64)code,c.Rip,(PRUNTIME_FUNCTION)row,&c,&handler,&frame,nullptr);
    if (c.Rsp!=(DWORD64)(stack+272) || c.Rip!=return_address) return 2;
    const uint64_t result[]={c.Rbx,c.Rbp,c.Rsi,c.Rdi,c.R12,c.R13,c.R14,c.R15};
    for (unsigned i=0;i<8;i++) if (result[i]!=UINT64_C(0x11110000)+i*0x101) return 3;
    return 0;
}
