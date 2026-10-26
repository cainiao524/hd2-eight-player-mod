#include "ep_loadout_prompt.h"
#include <windows.h>
#include <string.h>
extern "C" __declspec(dllexport) int prompt_build(const EpLoadoutConsumerAddresses* a,EpLoadoutPromptImage* b)
{return ep_loadout_prompt_build(a,b);}
/* One live snapshot inside the dispatcher peer lookup, including both cold
 * register-save chains. Windows unwinds only owned code and copied stack. */
extern "C" __declspec(dllexport) int prompt_unwind(const EpLoadoutPromptImage* image,uint32_t offset,
    int32_t delta,const uint64_t* registers,const uint8_t* stack_data,uint64_t return_address)
{
    alignas(16) uint8_t code[EP_LOADOUT_PROMPT_BYTES],stack[0x410];
    memcpy(code,image->data,image->bytes);memcpy(stack+8,stack_data,0x400);
    const auto* row=(const RUNTIME_FUNCTION*)(code+image->table_offset)+3;
    if (offset<row->BeginAddress || offset>=row->EndAddress || delta!=-0x28) return 1;
    CONTEXT c={};c.ContextFlags=CONTEXT_ALL;c.Rip=(DWORD64)code+offset;c.Rsp=(DWORD64)(stack+0x308)+delta;
    c.Rbx=registers[0];c.Rbp=registers[1];c.Rsi=registers[2];c.Rdi=registers[3];
    c.R12=registers[4];c.R13=registers[5];c.R14=registers[6];c.R15=registers[7];
    void* data=nullptr;DWORD64 frame=0;
    auto* handler=RtlVirtualUnwind(UNW_FLAG_EHANDLER,(DWORD64)code,c.Rip,(PRUNTIME_FUNCTION)row,&c,&data,&frame,nullptr);
    if (handler || c.Rsp!=(DWORD64)(stack+0x310) || c.Rip!=return_address) return 2;
    const uint64_t result[]={c.Rbx,c.Rbp,c.Rsi,c.Rdi,c.R12,c.R13,c.R14,c.R15};
    for (unsigned i=0;i<8;i++) if (result[i]!=UINT64_C(0x11110000)+i*0x101) return 3;
    return 0;
}
