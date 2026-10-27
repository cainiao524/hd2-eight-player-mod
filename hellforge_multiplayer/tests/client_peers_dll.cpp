/* Self-owned code pages only; no game calls or hook publication. */
#include "ep_client_peers.h"
#include <windows.h>
#include <string.h>
static unsigned hooks;
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {++hooks;return -1;}
extern "C" __declspec(dllexport) int client_peer_emit(uint32_t kind,const EpClientDisconnectAddresses* a,EpClientPeerImage* out)
{return ep_client_peer_build(kind,a,out);}
extern "C" __declspec(dllexport) int client_peer_disconnect_emit(const EpClientDisconnectAddresses* a,EpClientDisconnectImage* out)
{return ep_client_disconnect_build(a,out);}
extern "C" __declspec(dllexport) int client_peer_reader_fixture()
{
    HfMod* mod=(HfMod*)0x918d;HfApi api={};api.version=13;api.size=sizeof(api);api.build_id=Build;api.hook_ex=Hook;
    EpClientPeerFamilyAddresses a={};a.game=0x140000000;a.client=0x200000000;a.peers=0x200010010;a.reject=0x1c0000000;a.capacity=8;
    for (unsigned i=0;i<EP_CLIENT_PEER_FAMILY_COUNT;i++) a.code[i]=0x180000000+0x10000ull*i;
    auto bad=a;bad.code[7]=UINT64_C(1)<<47;EpClientPeerFamily family={};
    if (ep_client_peer_family_prepare(&api,mod,&bad,&family)==EP_PROPERTY_OK) return 1;
    for (const auto& code:family.code) if (code.handle) {ep_client_peer_family_discard(mod,&family);return 2;}
    if (ep_client_peer_family_prepare(&api,mod,&a,&family)!=EP_PROPERTY_OK) return 3;
    int result=0;
    for (unsigned i=5;i<=EP_CLIENT_PEER_SET_FLAG && !result;i++) {
        const auto& code=family.code[i];EpClientPeerImage image={};
        const EpClientDisconnectAddresses at={a.game,code.base,a.client,a.peers,a.reject,8,0};
        if (code.state!=EP_CODE_READY || ep_client_peer_build(i,&at,&image)!=EP_PROPERTY_OK || image.function_count!=1) {result=4;break;}
        uint64_t stack[4]={0x9090,0,0,0};CONTEXT context={};context.ContextFlags=CONTEXT_FULL;
        context.Rsp=(uintptr_t)stack;context.Rip=code.base+2;context.Rbx=0x3333;context.Rsi=0x6666;context.Rdi=0x7777;
        DWORD64 base=0,frame=0;void* data=nullptr;auto* fn=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
        if (!fn || base!=code.base) {result=5;break;}
        RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,fn,&context,&data,&frame,nullptr);
        if (context.Rsp!=(uintptr_t)(stack+1) || context.Rip!=0x9090 || context.Rbx!=0x3333 || context.Rsi!=0x6666 || context.Rdi!=0x7777) result=6;
    }
    if (!ep_client_peer_family_discard(mod,&family)) result=7;
    if (hooks) result=8;
    return result;
}
extern "C" __declspec(dllexport) int client_peer_family_fixture()
{
    HfMod* mod=(HfMod*)0x918b;HfApi api={};api.version=13;api.size=sizeof(api);api.build_id=Build;api.hook_ex=Hook;
    EpClientPeerFamilyAddresses a={};a.game=0x140000000;a.client=0x200000000;a.peers=0x200010010;a.reject=0x1c0000000;a.capacity=8;
    for (unsigned i=0;i<EP_CLIENT_PEER_FAMILY_COUNT;i++) a.code[i]=0x180000000+0x10000ull*i;
    EpClientPeerFamily family={};auto bad=a;bad.code[4]=UINT64_C(1)<<47;
    if (ep_client_peer_family_prepare(&api,mod,&bad,&family)==EP_PROPERTY_OK) return 1;
    for (const auto& code:family.code) if (code.handle) {ep_client_peer_family_discard(mod,&family);return 2;}
    auto rc=ep_client_peer_family_prepare(&api,mod,&a,&family);if (rc!=EP_PROPERTY_OK) return 10+(int)rc;
    int result=0;
    for (unsigned k=0;k<4 && !result;k++) {
        EpClientPeerImage image={};const auto& code=family.code[k];
        const EpClientDisconnectAddresses at={a.game,code.base,a.client,a.peers,a.reject,8,0};
        if (code.state!=EP_CODE_READY || ep_client_peer_build(k+1,&at,&image)!=EP_PROPERTY_OK) {result=30;break;}
        const unsigned row=image.function_count-(k==3 ? 2 : 1);uint32_t offset;
        memcpy(&offset,image.data+image.table_offset+12*row,4);
        alignas(16) uint8_t stack[0xc00]={};auto sp=(uintptr_t)stack;
        CONTEXT context={};context.ContextFlags=CONTEXT_FULL;context.Rsp=sp;context.Rip=code.base+offset+5;
        context.Rbp=0x5555;context.R12=0xcccc;context.R13=0xdddd;context.R14=0xeeee;context.R15=0xffff;
        auto put=[&](unsigned off,uint64_t value) {memcpy(stack+off,&value,8);};
        unsigned return_at=0;
        if (k==0) {put(0x50,0x3333);put(0x58,0x6666);put(0x40,0x7777);return_at=0x48;}
        if (k==1) {
            put(0xb0,0x3333);put(0xb8,0x6666);put(0xc0,0x5555);put(0xa0,0x7777);
            put(0x98,0xcccc);put(0x90,0xdddd);put(0x88,0xeeee);put(0x80,0xffff);return_at=0xa8;
        }
        if (k==2) {put(0x40,0x3333);put(0x48,0x7777);put(0x38,0x6666);put(0x20,0xeeee);return_at=0x28;}
        if (k==3) {
            put(0xa68,0x3333);put(0xa70,0x6666);put(0xa78,0x7777);put(0xa30,0xeeee);
            put(0xa40,0xcccc);put(0xa38,0xdddd);put(0xa48,0xffff);put(0xa50,0x5555);return_at=0xa58;
        }
        put(return_at,0x9090);DWORD64 base=0,establisher=0;PVOID data=nullptr;
        auto* function=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
        if (!function || base!=code.base) {result=40+(int)k;break;}
        RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,function,&context,&data,&establisher,nullptr);
        if (context.Rsp!=sp+return_at+8 || context.Rip!=0x9090 || context.Rbx!=0x3333 || context.Rsi!=0x6666 ||
            context.Rdi!=0x7777 || context.Rbp!=0x5555 || context.R12!=0xcccc || context.R13!=0xdddd ||
            context.R14!=0xeeee || context.R15!=0xffff) result=50+(int)k;
    }
    if (!ep_client_peer_family_discard(mod,&family)) result=60;
    if (hooks) result=61;
    return result;
}
