#include "ep_loadout_control.h"
#include <windows.h>
#include <string.h>
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {return -1;}
extern "C" __declspec(dllexport) int exit_build(const EpLoadoutControlAddresses* input,EpLoadoutControlImage* image)
{
    auto result=ep_loadout_control_build(input,image);if (result!=EP_PROPERTY_OK) return result;
    // Exercise the production table sealer with this changed unwind family.
    // Only owned code is allocated; the image is never executed or published.
    HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;
    HfMod* mod=(HfMod*)(uintptr_t)0x9178;EpSessionCodeInfo code={};
    if (!ep_session_code_reserve(&api,mod,0,image->bytes,&code)) return 100;
    const int sealed=ep_session_code_seal_table(mod,code.handle,image->data,image->bytes,image->table_offset,image->function_count);
    const int discarded=ep_session_code_discard(mod,code.handle);return sealed && discarded ? 0 : 101;
}
extern "C" __declspec(dllexport) int exit_unwind(const EpLoadoutControlImage* image,uint32_t offset,
    int32_t delta,const uint64_t* registers,const uint8_t* saved_stack,uint64_t emulator_base,uint64_t stop)
{
    alignas(16) uint8_t code[EP_LOADOUT_CONTROL_BYTES],stack[0x810];
    memcpy(code,image->data,image->bytes);memcpy(stack+8,saved_stack,0x800);
    CONTEXT c={};c.ContextFlags=CONTEXT_ALL;c.Rip=(DWORD64)code+offset;c.Rsp=(DWORD64)(stack+0x408)+delta;
    c.Rbx=registers[0];c.Rbp=registers[1];c.Rsi=registers[2];c.Rdi=registers[3];
    c.R12=registers[4];c.R13=registers[5];c.R14=registers[6];c.R15=registers[7];
    for (unsigned depth=0;depth<2;depth++) {
        auto* table=(RUNTIME_FUNCTION*)(code+image->table_offset);RUNTIME_FUNCTION* row=nullptr;
        for (unsigned i=0;i<image->function_count;i++)
            if (c.Rip>=(DWORD64)code+table[i].BeginAddress && c.Rip<(DWORD64)code+table[i].EndAddress) row=table+i;
        if (!row) return 1;
        void* data=nullptr;DWORD64 frame=0;
        if (RtlVirtualUnwind(UNW_FLAG_EHANDLER,(DWORD64)code,c.Rip,row,&c,&data,&frame,nullptr)) return 2;
        if (!depth) {
            if (c.Rip<emulator_base || c.Rip>=emulator_base+image->code_bytes) return 3;
            c.Rip=(DWORD64)code+c.Rip-emulator_base;
        }
    }
    if (c.Rip!=stop || c.Rsp!=(DWORD64)(stack+0x410)) return 4;
    const uint64_t values[]={c.Rbx,c.Rbp,c.Rsi,c.Rdi,c.R12,c.R13,c.R14,c.R15};
    for (unsigned i=0;i<8;i++) if (values[i]!=UINT64_C(0x11110000)+i*0x101) return 5;
    return 0;
}
