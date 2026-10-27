/* Only owned test code/stack pages. The native-creation service is a fixture;
 * no game memory, publication or native game functions are invoked. */
#include "ep_client_peers.h"
#include "ep_roster_group.h"
#include "ep_player_join_call.h"
#include <windows.h>
#include <string.h>
extern "C" void EpRosterCallDispatch(EpRosterCallContext*,EpRosterCallFrame*);
static unsigned calls,old_calls,failures,hooks,reads;
static const char* Build() {return "25480438";}
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) {++hooks;return -1;}
static int Read(void*,uintptr_t,void*,size_t) {++reads;return 0;}
static void Failure(void*,uint32_t,EpRosterOwnerResult,EpRosterCallFrame*) {++failures;}
static void Old() {++old_calls;}
static int Create() {return 1;}
uintptr_t ep_player_join_creation_entry() {return (uintptr_t)Create;}
int ep_player_join_invoke(EpRosterCallContext*,EpRosterCallFrame*,const EpNativeRosterView*,uintptr_t) {++calls;return 1;}
extern "C" __declspec(dllexport) int peer_join_emit(uint64_t game,uint64_t code,uint64_t control,uint64_t next,
    uint64_t reject,const EpPlayerJoinPeers* peers,EpPlayerJoinImage* image)
{return ep_player_join_peer_gate_build(game,code,control,next,reject,peers,image);}
extern "C" __declspec(dllexport) int peer_join_operation(uint32_t kind,const EpClientDisconnectAddresses* a,EpClientPeerImage* image)
{return ep_client_peer_build(kind,a,image);}
extern "C" __declspec(dllexport) int peer_join_group_fixture()
{
    auto* mod=(HfMod*)0x918c;HfApi api={};api.version=13;api.size=sizeof(api);api.build_id=Build;api.hook_ex=Hook;
    EpRosterGroupBindings bindings={};bindings.game_base=0x140000000;bindings.roster_address=0x240000000;bindings.storage_address=0x240010000;
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {bindings.desired_code[i]=0x180000000+0x10000ull*i;bindings.reject[i]=0x1c0000000;}
    EpPlayerJoinPeers peers={0x2100162c8,0x220000000,8,0};EpNativeRosterView view={};
    view.game=bindings.game_base;view.roster=bindings.roster_address;view.storage=bindings.storage_address;view.epoch=1;view.build=25480438;
    EpRosterMemory memory={nullptr,Read};uint64_t owner=0;EpRosterGroupInfo group={};EpRosterCallPolicy policy={Failure,nullptr,nullptr};
    if (ep_roster_owner_create(mod,&view,&memory,&owner)!=EP_OWNER_OK) return 1;
    if (!ep_roster_group_prepare_owned_peers(&api,mod,&bindings,owner,&policy,&peers,&group)) return 2;
    int result=0;EpPlayerJoinPeers actual={};
    if (!ep_roster_group_peer_binding(mod,group.handle,&actual) || memcmp(&actual,&peers,sizeof(peers))) result=3;
    const auto& code=group.code[EP_ROSTER_PLAYER_JOIN-1];
    if (code.state!=EP_CODE_READY || code.bytes!=EP_PLAYER_JOIN_PEER_GATE_BYTES) result=4;
    EpPlayerJoinImage image={};
    if (ep_player_join_peer_gate_build(view.game,code.base,0x1c0100000,0x1c0100010,0x1c0000000,&peers,&image)!=EP_PROPERTY_OK) result=5;
    // Negative control: a full accepted-frame chain would restore XMM6..9
    // before they were saved. Require the distinct GP-only parent instead.
    EpSessionCodeInfo trial={};
    if (!ep_session_code_reserve(&api,mod,0x182000000,EP_PLAYER_JOIN_PEER_GATE_BYTES,&trial)) result=6;
    else {
        EpPlayerJoinImage bad={};ep_player_join_peer_gate_build(view.game,trial.base,0x1c0100000,0x1c0100010,0x1c0000000,&peers,&bad);
        auto target=ep_player_join_creation_entry();memcpy(bad.data+bad.creation_target_offset,&target,8);
        uint32_t rows[39];memcpy(rows,bad.data+bad.table_offset,sizeof(rows));memcpy(bad.data+rows[38]+4,rows+18,12);
        const EpSessionGsCheck gs={1,bad.handler_offset,view.game+0x21044a0};
        if (ep_session_code_seal_player_join_peers(mod,trial.handle,bad.data,bad.bytes,bad.table_offset,&gs)) result=7;
        if (!ep_session_code_discard(mod,trial.handle)) result=8;
    }
    uint32_t rows[39];memcpy(rows,image.data+image.table_offset,sizeof(rows));
    for (unsigned row=10;row<13 && !result;row++) {
        alignas(16) uint8_t stack[0x3000]={};auto sp=(uintptr_t)stack;
        const unsigned slots[]={0x2b08,0x2b10,0x2b28,0x2b30,0x2b38,0x2af8,0x2af0,0x2b00,0x2b18};
        const uint64_t values[]={0x3333,0x5555,0x6666,0x7777,0xcccc,0xdddd,0xeeee,0xffff,0x9090};
        for (unsigned i=0;i<9;i++) memcpy(stack+slots[i],values+i,8);
        CONTEXT context={};context.ContextFlags=CONTEXT_FULL;context.Rsp=sp;context.Rip=code.base+rows[3*row]+9;
        memset(&context.Xmm6,0x16,4*sizeof(M128A));memset(stack+0x2ab0,0xa6,64);
        DWORD64 base=0,frame=0;void* data=nullptr;auto* function=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
        if (!function || base!=code.base) {result=9;break;}
        RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,function,&context,&data,&frame,nullptr);
        const uint64_t restored[]={context.Rbx,context.Rbp,context.Rsi,context.Rdi,context.R12,context.R13,context.R14,context.R15,context.Rip};
        uint8_t unchanged[64];memset(unchanged,0x16,64);
        if (context.Rsp!=sp+0x2b20 || memcmp(restored,values,sizeof(values)) || memcmp(&context.Xmm6,unchanged,64)) result=10;
    }
    // Exercise the actual group's owned dispatcher, with only its native body
    // service substituted. OLD still forwards; a foreign client never enters.
    auto* context=*(EpRosterCallContext**)(uintptr_t)(code.base+2);
    *(uintptr_t*)context->next_pointer=(uintptr_t)Old;
    EpRosterCallFrame frame={};frame.rcx=peers.client;EpRosterCallDispatch(context,&frame);
    if (old_calls!=1 || calls || frame.status!=EP_OWNER_OK) result=11;
    *context->active=1;frame={};frame.rcx=peers.client;EpRosterCallDispatch(context,&frame);
    if (calls!=1 || failures || frame.status!=EP_OWNER_OK) result=12;
    frame={};frame.rcx=peers.client+8;EpRosterCallDispatch(context,&frame);
    if (calls!=1 || failures!=1 || frame.padding!=EP_JOIN_NOT_ATTEMPTED) result=13;
    *context->active=0;
    if (!ep_roster_group_cancel(mod,group.handle)) result=14;
    if (ep_roster_owner_close(mod,owner)!=EP_OWNER_OK) result=15;
    if (hooks || reads) result=16;
    return result;
}
