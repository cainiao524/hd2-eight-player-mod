#include "ep_loadout_consumers.h"
#include <windows.h>
#include <string.h>
extern "C" __declspec(dllexport) int ui_build(const EpLoadoutConsumerAddresses* a,EpLoadoutConsumerImage* b,uint64_t ready_flag)
{return ep_loadout_consumers_build(a,ready_flag,b);}
extern "C" __declspec(dllexport) int ui_build_peers(const EpLoadoutConsumerAddresses* a,EpLoadoutConsumerImage* b,uint64_t ready_flag,const EpPlayerJoinPeers* peers)
{return ep_loadout_consumers_build_peers(a,ready_flag,peers,b);}
extern "C" __declspec(dllexport) int ui_maps(EpLoadoutMaps* m)
{return ep_loadout_maps_initialize(m,8,3);}
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {return 1;}
static int prepare(const EpLoadoutConsumerAddresses* a,uint64_t ready_flag,const EpPlayerJoinPeers* peers)
{
    HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;
    HfMod* mod=(HfMod*)(uintptr_t)0x9182;EpSessionCodeInfo code={};
    if ((peers ? ep_loadout_consumers_prepare_peers(&api,mod,a,ready_flag,peers,&code) :
                 ep_loadout_consumers_prepare(&api,mod,a,ready_flag,&code))!=EP_PROPERTY_OK) return 1;
    int failure=code.state!=EP_CODE_READY || !code.registered || code.pinned;
    if (!ep_session_code_discard(mod,code.handle)) return 2;
    return failure;
}
extern "C" __declspec(dllexport) int ui_prepare(const EpLoadoutConsumerAddresses* a,uint64_t ready_flag)
{return prepare(a,ready_flag,nullptr);}
extern "C" __declspec(dllexport) int ui_prepare_peers(const EpLoadoutConsumerAddresses* a,uint64_t ready_flag,const EpPlayerJoinPeers* peers)
{return prepare(a,ready_flag,peers);}
/* Three selected snapshots from a single owned-memory smoke flow. No code
 * in the candidate image or its external targets is executed by Windows. */
extern "C" __declspec(dllexport) int ui_unwind(const EpLoadoutConsumerImage* image,uint32_t offset,
    int32_t delta,const uint64_t* registers,const uint8_t* stack_data,uint64_t return_address)
{
    alignas(16) uint8_t code[EP_LOADOUT_CONSUMER_BYTES],stack[528];
    memcpy(code,image->data,image->bytes);memcpy(stack+8,stack_data,512);
    const auto* rows=(const RUNTIME_FUNCTION*)(code+image->table_offset);const RUNTIME_FUNCTION* row=nullptr;
    for (unsigned i=0;i<image->function_count;i++) if (rows[i].BeginAddress<=offset && offset<rows[i].EndAddress) row=rows+i;
    if (!row || delta < -208 || delta>0) return 1;
    CONTEXT c={};c.ContextFlags=CONTEXT_ALL;c.Rip=(DWORD64)code+offset;c.Rsp=(DWORD64)(stack+264)+delta;
    c.Rbx=registers[0];c.Rbp=registers[1];c.Rsi=registers[2];c.Rdi=registers[3];
    c.R12=registers[4];c.R13=registers[5];c.R14=registers[6];c.R15=registers[7];
    c.Xmm6.Low=registers[8];c.Xmm6.High=(LONG64)registers[9];
    c.Xmm7.Low=registers[10];c.Xmm7.High=(LONG64)registers[11];
    c.Xmm8.Low=registers[12];c.Xmm8.High=(LONG64)registers[13];
    void* handler=nullptr;DWORD64 frame=0;
    RtlVirtualUnwind(UNW_FLAG_NHANDLER,(DWORD64)code,c.Rip,(PRUNTIME_FUNCTION)row,&c,&handler,&frame,nullptr);
    if (c.Rsp!=(DWORD64)(stack+272) || c.Rip!=return_address) return 2;
    const uint64_t result[]={c.Rbx,c.Rbp,c.Rsi,c.Rdi,c.R12,c.R13,c.R14,c.R15};
    for (unsigned i=0;i<8;i++) if (result[i]!=UINT64_C(0x11110000)+i*0x101) return 3;
    const M128A xmm[]={c.Xmm6,c.Xmm7,c.Xmm8};
    for (unsigned i=0;i<3;i++) if (xmm[i].Low!=0x66660006u+i || (uint64_t)xmm[i].High!=0xaaaa0006u+i) return 4;
    return 0;
}
