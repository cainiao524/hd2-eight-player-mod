#include "ep_loadout_group.h"
#include <windows.h>
#include <string.h>
extern "C" __declspec(dllexport) int setup_build(const EpLoadoutSetupAddresses* a,EpLoadoutSetupImage* b)
{return ep_loadout_setup_build(a,b);}
static unsigned hooks;
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {++hooks;return 1;}
extern "C" __declspec(dllexport) int setup_group(const EpLoadoutGroupAddresses* a)
{
    HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;hooks=0;
    HfMod* owner=(HfMod*)(uintptr_t)0x9183;EpLoadoutGroup group={};
    if (ep_loadout_group_prepare(&api,owner,a,&group)!=EP_PROPERTY_OK) return 1;
    int failure=group.state!=EP_LOADOUT_GROUP_READY || group.capacity!=a->setup.common.lifecycle.capacity || hooks;
    const EpSessionCodeInfo codes[]={group.code[0],group.code[1],group.code[2],group.code[3],group.code[4],group.code[5],group.code[6],group.code[7],group.code[8],group.code[9],group.code[10],group.code[11],group.code[12],group.code[13]};
    for (const auto& code:codes) if (code.state!=EP_CODE_READY || !code.registered || code.pinned) failure=2;
    const uint64_t entries[]={group.constructor,group.release,group.alternate_release,group.transition,
                              group.update,group.lookup,group.action,group.setup,group.input,group.edit,group.close,group.refresh,group.sync_records,group.frame,group.local_update,group.mode,group.open_mode,group.leave,group.screen_input,group.reset_selection,group.state_change,group.return_screen,group.context_action,group.state_tick,group.prompt,group.selection_prompt,group.active_prompt,group.ready_flag,group.blocked_flag,group.countdown,group.resource_lookup,group.reset_timers,group.resource_write,group.resource_ordinal,group.resource_transform,group.player_value,group.assign_resources,group.insert_resource_object,group.enqueue_resource_object,group.move_resource_object,group.remove_resource_object};
    for (unsigned i=0;i<41;i++) {
        const auto& code=codes[i<4 ? 0 : i<7 ? 1 : i==7 ? 2 : i<11 ? 3 : i==11 ? 4 : i==12 ? 5 : i<15 ? 6 : i<17 ? 7 : i<20 ? 8 : i<24 ? 9 : i<29 ? 10 : i<32 ? 11 : i<37 ? 12 : 13];
        if (entries[i]<code.base || entries[i]>=code.base+code.bytes) failure=3;
    }
    if (ep_loadout_group_discard(owner,&group)!=EP_PROPERTY_OK || group.state!=EP_LOADOUT_GROUP_EMPTY) return 4;
    for (const auto& code:codes) {EpSessionCodeInfo after={};if (ep_session_code_info(owner,code.handle,&after)) failure=5;}
    return failure;
}
/* One setup-body snapshot, with a local stack large enough for the native
 * 0x178-byte frame. Windows only unwinds owned memory; it calls no game code. */
extern "C" __declspec(dllexport) int setup_unwind(const EpLoadoutSetupImage* image,uint32_t offset,
    int32_t delta,const uint64_t* registers,const uint8_t* stack_data,uint64_t return_address)
{
    alignas(16) uint8_t code[EP_LOADOUT_SETUP_BYTES],stack[1040];
    memcpy(code,image->data,image->bytes);memcpy(stack+8,stack_data,1024);
    const auto* row=(const RUNTIME_FUNCTION*)(code+image->table_offset)+1;
    if (offset<row->BeginAddress || offset>=row->EndAddress || delta!=-0x178) return 1;
    CONTEXT c={};c.ContextFlags=CONTEXT_ALL;c.Rip=(DWORD64)code+offset;c.Rsp=(DWORD64)(stack+520)+delta;
    c.Rbx=registers[0];c.Rbp=registers[1];c.Rsi=registers[2];c.Rdi=registers[3];
    c.R12=registers[4];c.R13=registers[5];c.R14=registers[6];c.R15=registers[7];
    c.Xmm6.Low=registers[8];c.Xmm6.High=(LONG64)registers[9];
    void* data=nullptr;DWORD64 frame=0;
    auto* handler=RtlVirtualUnwind(UNW_FLAG_EHANDLER,(DWORD64)code,c.Rip,(PRUNTIME_FUNCTION)row,&c,&data,&frame,nullptr);
    if (c.Rsp!=(DWORD64)(stack+528) || c.Rip!=return_address) return 2;
    const uint64_t result[]={c.Rbx,c.Rbp,c.Rsi,c.Rdi,c.R12,c.R13,c.R14,c.R15};
    for (unsigned i=0;i<8;i++) if (result[i]!=UINT64_C(0x11110000)+i*0x101) return 3;
    if (c.Xmm6.Low!=0x66660006 || (uint64_t)c.Xmm6.High!=0xaaaa0006) return 4;
    if (handler!=(PEXCEPTION_ROUTINE)(code+image->handler_offset) || !data || *(uint32_t*)data!=0x130) return 5;
    return 0;
}
