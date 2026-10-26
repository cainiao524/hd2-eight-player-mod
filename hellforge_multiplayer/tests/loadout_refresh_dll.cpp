#include "ep_loadout_refresh.h"
#include <windows.h>
#include <string.h>
extern "C" __declspec(dllexport) int refresh_build(const EpLoadoutRefreshAddresses* a,EpLoadoutRefreshImage* b)
{return ep_loadout_refresh_build(a,b);}
/* Unwind one real emulator snapshot through the child -> GS-root chain.
 * Expected registers belong to the nested refresh entry, not the outer input
 * entry. Only owned stack/code bytes are used; no handler is invoked. */
extern "C" __declspec(dllexport) int refresh_unwind(const EpLoadoutRefreshImage* image,uint32_t offset,
    int32_t delta,const uint64_t* registers,const uint8_t* stack_data,const uint64_t* expected,uint64_t return_address)
{
    alignas(16) uint8_t code[EP_LOADOUT_REFRESH_BYTES],stack[528];
    memcpy(code,image->data,image->bytes);memcpy(stack+8,stack_data,512);
    const auto* row=(const RUNTIME_FUNCTION*)(code+image->table_offset)+2;
    if (offset<row->BeginAddress || offset>=row->EndAddress || delta!=-0xa8) return 1;
    CONTEXT c={};c.ContextFlags=CONTEXT_ALL;c.Rip=(DWORD64)code+offset;c.Rsp=(DWORD64)(stack+264)+delta;
    c.Rbx=registers[0];c.Rbp=registers[1];c.Rsi=registers[2];c.Rdi=registers[3];
    c.R12=registers[4];c.R13=registers[5];c.R14=registers[6];c.R15=registers[7];
    c.Xmm6.Low=registers[8];c.Xmm6.High=(LONG64)registers[9];
    c.Xmm7.Low=registers[10];c.Xmm7.High=(LONG64)registers[11];
    c.Xmm8.Low=registers[12];c.Xmm8.High=(LONG64)registers[13];
    void* data=nullptr;DWORD64 frame=0;
    auto* handler=RtlVirtualUnwind(UNW_FLAG_EHANDLER,(DWORD64)code,c.Rip,(PRUNTIME_FUNCTION)row,&c,&data,&frame,nullptr);
    if (c.Rsp!=(DWORD64)(stack+272) || c.Rip!=return_address) return 2;
    const uint64_t result[]={c.Rbx,c.Rbp,c.Rsi,c.Rdi,c.R12,c.R13,c.R14,c.R15,
        c.Xmm6.Low,(uint64_t)c.Xmm6.High,c.Xmm7.Low,(uint64_t)c.Xmm7.High,c.Xmm8.Low,(uint64_t)c.Xmm8.High};
    if (memcmp(result,expected,sizeof result)) return 3;
    if (handler!=(PEXCEPTION_ROUTINE)(code+image->handler_offset) || !data || *(uint32_t*)data!=0x70) return 4;
    return 0;
}
