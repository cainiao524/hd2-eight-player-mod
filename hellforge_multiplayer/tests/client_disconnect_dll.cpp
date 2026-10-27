/* Disposable process only. Seal/unwind actual generated code, never publish it
 * or call game services. Native callback execution is tested separately with
 * explicit Unicorn fixtures by validate_client_disconnect.py. */
#include "ep_client_disconnect.h"
#include <windows.h>
#include <string.h>
#include <initializer_list>
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {return -1;}
extern "C" __declspec(dllexport) int client_disconnect_emit(const EpClientDisconnectAddresses* a,EpClientDisconnectImage* out)
{return ep_client_disconnect_build(a,out);}
extern "C" __declspec(dllexport) int client_disconnect_unwind()
{
    HfMod* mod=(HfMod*)0x918a;HfApi api={};api.version=13;api.size=sizeof(api);api.build_id=Build;api.hook_ex=Hook;
    EpSessionCodeInfo code={};EpClientDisconnectImage image={};
    EpClientDisconnectAddresses a={0x140000000,0x180000000,0x200000000,0x200010000,0x1c0000000,8,0};
    if (ep_client_disconnect_build(&a,&image)!=EP_PROPERTY_OK) return 1;
    if (!ep_session_code_reserve(&api,mod,a.code,image.bytes,&code)) return 2;
    int result=0;
    uint32_t rows[33];memcpy(rows,image.data+image.table_offset,sizeof(rows));
    const EpSessionGsCheck gs={1,image.handler_offset,a.game+0x21044a0};
    auto bad=image;bad.data[rows[5]+16]^=1;
    if (!result && ep_session_code_seal_client_disconnect(mod,code.handle,bad.data,bad.bytes,bad.table_offset,&gs)) result=3;
    bad=image;memcpy(bad.data+rows[29]+4,rows+3,12);
    if (!result && ep_session_code_seal_client_disconnect(mod,code.handle,bad.data,bad.bytes,bad.table_offset,&gs)) result=4;
    if (!result && !ep_session_code_seal_client_disconnect(mod,code.handle,image.data,image.bytes,image.table_offset,&gs)) result=5;
    if (!result) {
        alignas(16) uint8_t stack[0x400]={};auto sp=(uintptr_t)stack;
        const unsigned offsets[]={0x180,0x170,0x160,0x188,0x190,0x198};
        const uint64_t values[]={0x3333,0x6666,0xffff,0xcccc,0x7777,0x9090};
        for (unsigned i=0;i<6;i++) memcpy(stack+offsets[i],values+i,8);
        for (auto pc:{image.lookup_offset+13,image.body_offset + 0x10849de - 0x10845b0,
                     image.body_offset + 0x10849f7 - 0x10845b0}) {
            CONTEXT context={};context.ContextFlags=CONTEXT_FULL;context.Rsp=sp;context.Rip=code.base+pc;
            context.Rbp=0x5555;context.R14=0xeeee;
            DWORD64 base=0,establisher=0;PVOID data=nullptr;
            auto* function=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
            if (!function || base!=code.base) {result=6;break;}
            RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,function,&context,&data,&establisher,nullptr);
            if (context.Rsp!=sp+0x1a0 || context.Rip!=0x9090 || context.Rbx!=0x3333 ||
                context.Rsi!=0x6666 || context.R15!=0xffff || context.R12!=0xcccc || context.Rdi!=0x7777 ||
                context.Rbp!=0x5555 || context.R14!=0xeeee) {result=7;break;}
        }
    }
    if (!ep_session_code_discard(mod,code.handle)) result=8;
    return result;
}
