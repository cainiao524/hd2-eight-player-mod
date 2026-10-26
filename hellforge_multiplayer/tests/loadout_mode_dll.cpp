#include "ep_loadout_mode.h"
#include <windows.h>
#include <string.h>
extern "C" __declspec(dllexport) int mode_build(const EpLoadoutConsumerAddresses* a,EpLoadoutModeImage* b)
{return ep_loadout_mode_build(a,b);}
/* One close-body snapshot; Windows only unwinds owned buffers. */
extern "C" __declspec(dllexport) int mode_unwind(const EpLoadoutModeImage* image,uint32_t offset,
    int32_t delta,const uint64_t* registers,const uint8_t* stack_data,uint64_t return_address)
{
    alignas(16) uint8_t code[EP_LOADOUT_MODE_BYTES],stack[0x410];
    memcpy(code,image->data,image->bytes);memcpy(stack+8,stack_data,0x400);
    const auto* row=(const RUNTIME_FUNCTION*)(code+image->table_offset)+3;
    if (offset<row->BeginAddress || offset>=row->EndAddress || delta!=-0x158) return 1;
    CONTEXT c={};c.ContextFlags=CONTEXT_ALL;c.Rip=(DWORD64)code+offset;c.Rsp=(DWORD64)(stack+0x308)+delta;
    c.Rbx=registers[0];c.Rbp=registers[1];c.Rsi=registers[2];c.Rdi=registers[3];
    c.R12=registers[4];c.R13=registers[5];c.R14=registers[6];c.R15=registers[7];
    for (unsigned i=0;i<4;i++) {auto& xmm=(&c.Xmm6)[i];xmm.Low=registers[8+i*2];xmm.High=(LONG64)registers[9+i*2];}
    void* data=nullptr;DWORD64 frame=0;
    auto* handler=RtlVirtualUnwind(UNW_FLAG_EHANDLER,(DWORD64)code,c.Rip,(PRUNTIME_FUNCTION)row,&c,&data,&frame,nullptr);
    if (c.Rsp!=(DWORD64)(stack+0x310) || c.Rip!=return_address) return 2;
    const uint64_t result[]={c.Rbx,c.Rbp,c.Rsi,c.Rdi,c.R12,c.R13,c.R14,c.R15};
    for (unsigned i=0;i<8;i++) if (result[i]!=UINT64_C(0x11110000)+i*0x101) return 3;
    for (unsigned i=0;i<4;i++) if ((&c.Xmm6)[i].Low!=0x66660006+i || (uint64_t)(&c.Xmm6)[i].High!=0xaaaa0006+i) return 4;
    if (handler!=(PEXCEPTION_ROUTINE)(code+image->handler_offset) || !data || *(uint32_t*)data!=0xd0) return 5;
    return 0;
}
