#include "ep_loadout_records.h"
#include <windows.h>
#include <string.h>
extern "C" __declspec(dllexport) int records_build(const EpLoadoutRecordsAddresses* a,EpLoadoutRecordsImage* b)
{return ep_loadout_records_build(a,b);}
/* One body snapshot exercises both chained parents and the unchanged large
 * GS frame. Windows reads owned bytes; it never calls the game handler. */
extern "C" __declspec(dllexport) int records_unwind(const EpLoadoutRecordsImage* image,uint32_t offset,
    int32_t delta,const uint64_t* registers,const uint8_t* stack_data,uint64_t return_address)
{
    alignas(16) uint8_t code[EP_LOADOUT_RECORDS_BYTES],stack[0x1710];
    memcpy(code,image->data,image->bytes);memcpy(stack+8,stack_data,0x1700);
    const auto* row=(const RUNTIME_FUNCTION*)(code+image->table_offset)+3;
    if (offset<row->BeginAddress || offset>=row->EndAddress || delta!=-0x1498) return 1;
    CONTEXT c={};c.ContextFlags=CONTEXT_ALL;c.Rip=(DWORD64)code+offset;c.Rsp=(DWORD64)(stack+0x1608)+delta;
    c.Rbx=registers[0];c.Rbp=registers[1];c.Rsi=registers[2];c.Rdi=registers[3];
    c.R12=registers[4];c.R13=registers[5];c.R14=registers[6];c.R15=registers[7];
    void* data=nullptr;DWORD64 frame=0;
    auto* handler=RtlVirtualUnwind(UNW_FLAG_EHANDLER,(DWORD64)code,c.Rip,(PRUNTIME_FUNCTION)row,&c,&data,&frame,nullptr);
    if (c.Rsp!=(DWORD64)(stack+0x1610) || c.Rip!=return_address) return 2;
    const uint64_t values[]={c.Rbx,c.Rbp,c.Rsi,c.Rdi,c.R12,c.R13,c.R14,c.R15};
    for (unsigned i=0;i<8;i++) if (values[i]!=0x11110000+i*0x101) return 3;
    if (handler!=(PEXCEPTION_ROUTINE)(code+image->handler_offset) || !data || *(uint32_t*)data!=0x1460) return 4;
    return 0;
}
