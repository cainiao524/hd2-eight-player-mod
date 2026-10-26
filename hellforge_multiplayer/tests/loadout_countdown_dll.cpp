#include "ep_loadout_countdown.h"
#include <windows.h>
#include <string.h>
extern "C" __declspec(dllexport) int countdown_build(const EpLoadoutCountdownAddresses* a,EpLoadoutCountdownImage* b)
{return ep_loadout_countdown_build(a,b);}
/* One allocation-branch snapshot, unwinding back into its native frame caller. */
extern "C" __declspec(dllexport) int countdown_unwind(const EpLoadoutCountdownImage* image,uint32_t offset,
    int32_t delta,const uint64_t* registers,const uint64_t* expected,const uint8_t* stack_data,uint64_t return_address)
{
    alignas(16) uint8_t code[EP_LOADOUT_COUNTDOWN_BYTES],stack[0x210];
    memcpy(code,image->data,image->bytes);memcpy(stack+8,stack_data,0x200);
    const auto* row=(const RUNTIME_FUNCTION*)(code+image->table_offset)+4;
    if (offset<row->BeginAddress || offset>=row->EndAddress || delta!=-0x78) return 1;
    CONTEXT c={};c.ContextFlags=CONTEXT_ALL;c.Rip=(DWORD64)code+offset;c.Rsp=(DWORD64)(stack+0x108)+delta;
    c.Rbx=registers[0];c.Rbp=registers[1];c.Rsi=registers[2];c.Rdi=registers[3];
    c.R12=registers[4];c.R13=registers[5];c.R14=registers[6];c.R15=registers[7];
    c.Xmm6.Low=registers[8];c.Xmm6.High=(LONG64)registers[9];c.Xmm7.Low=registers[10];c.Xmm7.High=(LONG64)registers[11];
    void* data=nullptr;DWORD64 frame=0;
    auto* handler=RtlVirtualUnwind(UNW_FLAG_EHANDLER,(DWORD64)code,c.Rip,(PRUNTIME_FUNCTION)row,&c,&data,&frame,nullptr);
    if (handler || c.Rsp!=(DWORD64)(stack+0x110) || c.Rip!=return_address) return 2;
    const uint64_t result[]={c.Rbx,c.Rbp,c.Rsi,c.Rdi,c.R12,c.R13,c.R14,c.R15,
        c.Xmm6.Low,(uint64_t)c.Xmm6.High,c.Xmm7.Low,(uint64_t)c.Xmm7.High};
    for (unsigned i=0;i<12;i++) if (result[i]!=expected[i]) return 3;
    return 0;
}
