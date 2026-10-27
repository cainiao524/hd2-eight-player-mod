/* Focused join emitter + registered Windows unwind, disposable process only.
 * SDK is a forbidden-publication fixture. The numeric game base is not read.
 * This does not run real resources, game code, SDK hooks or the full join. */
#include "ep_player_join_image.h"
#include "ep_session_code.h"
#include <windows.h>
#include <string.h>
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {TerminateProcess(GetCurrentProcess(),99);return -1;}
static uint32_t CreateFixture() {return 1;}
extern "C" __declspec(dllexport) int player_join_emit(uint64_t game,uint64_t code,uint64_t control,uint64_t next,
    uint32_t capacity,EpPlayerJoinImage* out)
{return ep_player_join_gate_build(game,code,control,next,capacity,out);}
extern "C" __declspec(dllexport) int player_join_unwind()
{
    const auto game=UINT64_C(0x140000000);auto* mod=(HfMod*)(uintptr_t)0x9189;
    HfApi api={};api.version=13;api.size=sizeof(api);api.build_id=Build;api.hook_ex=Hook;
    EpSessionCodeInfo code={};EpPlayerJoinImage image={};static uint32_t active;static void* next;
    if (!ep_session_code_reserve(&api,mod,UINT64_C(0x180000000),3468,&code)) return 1;
    int result=0;
    if (ep_player_join_gate_build(game,code.base,(uintptr_t)&active,(uintptr_t)&next,8,&image)!=EP_PROPERTY_OK) result=2;
    uintptr_t target=(uintptr_t)CreateFixture;memcpy(image.data+image.creation_target_offset,&target,8);
    const EpSessionGsCheck gs={1,image.handler_offset,game+0x21044a0};
    // A corrupt cookie and a valid-but-wrong chain must both be rejected;
    // reserved memory can be retried and is never exposed.
    uint32_t rows[30];memcpy(rows,image.data+image.table_offset,sizeof(rows));
    auto bad=image;bad.data[rows[5]+20]^=1;
    if (!result && ep_session_code_seal_player_join(mod,code.handle,bad.data,bad.bytes,bad.table_offset,&gs)) result=3;
    bad=image;memcpy(bad.data+rows[11]+8,rows+3,12);
    if (!result && ep_session_code_seal_player_join(mod,code.handle,bad.data,bad.bytes,bad.table_offset,&gs)) result=4;
    if (!result && !ep_session_code_seal_player_join(mod,code.handle,image.data,image.bytes,image.table_offset,&gs)) result=5;
    if (!result) {
        // Native accepted branch after all delayed saves, before FDC140.
        alignas(16) uint8_t stack[0x3000]={};auto sp=(uintptr_t)stack;
        const uint32_t slots[]={0x2b08,0x2b10,0x2b28,0x2b30,0x2b38,0x2af8,0x2af0,0x2b00};
        const uint64_t values[]={0x3333,0x5555,0x6666,0x7777,0xcccc,0xdddd,0xeeee,0xffff};
        for (unsigned i=0;i<8;i++) memcpy(stack+slots[i],&values[i],8);
        const uint64_t caller=0x12345678;memcpy(stack+0x2b18,&caller,8);
        for (unsigned i=0;i<4;i++) memset(stack+0x2ae0-i*16,0xa6+i,16);
        CONTEXT context={};context.ContextFlags=CONTEXT_FULL;context.Rsp=sp;
        context.Rip=code.base+rows[21]+8; // appended continuation chains through full accepted frame
        DWORD64 base=0,frame=0;void* data=nullptr;
        auto* f=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
        if (!f || base!=code.base) result=6;
        else {
            RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,f,&context,&data,&frame,nullptr);
            const uint64_t actual[]={context.Rbx,context.Rbp,context.Rsi,context.Rdi,context.R12,context.R13,context.R14,context.R15};
            if (context.Rsp!=sp+0x2b20 || context.Rip!=caller || memcmp(actual,values,sizeof(values))) result=7;
            const M128A vectors[]={context.Xmm6,context.Xmm7,context.Xmm8,context.Xmm9};
            for (unsigned i=0;i<4;i++) if (memcmp(&vectors[i],stack+0x2ae0-i*16,16)) result=8;
        }
    }
    if (!ep_session_code_discard(mod,code.handle)) return 9;
    return result;
}
