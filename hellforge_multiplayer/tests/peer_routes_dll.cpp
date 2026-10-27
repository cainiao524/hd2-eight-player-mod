/* One owned-memory routing flow. SDK publication records callbacks only; it
 * never installs hooks. Only generated lookup/contains leaves execute natively.
 * Insert services are OLD ABI fixtures, not game services or multiplayer proof. */
#include "ep_roster_group.h"
#include "ep_roster_group_transition.h"
#include "ep_player_join_call.h"
#include <windows.h>
#include <string.h>
#define REQUIRE(x) do {if (!(x)) return __LINE__;} while (0)
static HfMod* mod=(HfMod*)0x9192;
static uint64_t owner,client=0x2100162c8,bank=0x220000000;
static unsigned hooks,old_insert,old_registered,failures,bad;
static uint32_t failed_kind;
static EpRosterPeerRoutesInfo routes;
static EpRosterGroupInfo group;
static EpRosterGroupTransition token;
static const char* Build() {return "25480438";}
static int Read(void*,uintptr_t,void*,size_t) {++bad;return 0;}
static uint64_t Old() {return 0xabcdef;}
static uint64_t Insert(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f,uint64_t g)
{
    if (ep_roster_owner_native_status(mod,owner)!=EP_OWNER_OK ||
        a!=client || b!=0x11 || c!=0x22 || d!=0x33 || e!=0x44 || f!=0x55 || g!=0x66) ++bad;
    ++old_insert;return 0x123456789;
}
static uint64_t Registered(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f)
{
    if (ep_roster_owner_native_status(mod,owner)!=EP_OWNER_OK ||
        a!=0x77 || b!=0x88 || c!=0x99 || d!=0xaa || e!=0xbb || f!=0xcc) ++bad;
    ++old_registered;return 0x987654321;
}
static int Hook(HfMod*,uintptr_t target,void*,void** next,int32_t)
{
    // All images must already be retained when even the first roster hook is exposed.
    EpRosterPeerRoutesInfo retained={};
    if (!ep_roster_group_peer_routes_info(mod,group.handle,&retained) || !retained.retained) ++bad;
    for (unsigned i=0;i<8;i++) if (!retained.body[i].pinned || !retained.gate[i].pinned) ++bad;
    ++hooks;*next=target==0x1410872c0 ? (void*)Insert : target==0x140b90b20 ? (void*)Registered : (void*)Old;return 0;
}
static void Failure(void*,uint32_t kind,EpRosterOwnerResult,EpRosterCallFrame* frame)
{++failures;failed_kind=kind;frame->rax=0xbadc0de;}
static int UnusedCreate() {++bad;return 0;}
uintptr_t ep_player_join_creation_entry() {return (uintptr_t)UnusedCreate;}
int ep_player_join_invoke(EpRosterCallContext*,EpRosterCallFrame*,const EpNativeRosterView*,uintptr_t) {++bad;return 0;}
static int Activate(void*,const EpNativeRosterView*)
{
    return ep_roster_group_transition_enter(mod,&token) && ep_roster_group_transition_activate(mod,&token) &&
        ep_roster_group_transition_finish(mod,&token,EP_ROSTER_TRANSITION_NEW);
}
static int Lookup(void* expected,const EpNativeRosterView*)
{
    const auto call=(uint64_t(*)(uint64_t,uint64_t))routes.gate[5].base;
    const auto record=call(client,0x107);
    uint32_t index=0;if (record) memcpy(&index,(const void*)(record+0x14),4);
    return record==(uintptr_t)expected && index==4 && ep_roster_owner_native_status(mod,owner)==EP_OWNER_OK;
}
static int Compact(void*,const EpNativeRosterView*)
{
    memcpy((void*)bank,(const void*)(bank+224),32);memset((void*)(bank+224),0,32);
    *(uint32_t*)(client+0xc8)=7;return Lookup((void*)bank,nullptr);
}
extern "C" __declspec(dllexport) int peer_routes_flow()
{
    HfApi api={};api.size=sizeof(api);api.version=13;api.build_id=Build;api.hook_ex=Hook;
    EpRosterGroupBindings bindings={};bindings.game_base=0x140000000;bindings.roster_address=0x240000000;bindings.storage_address=0x240010000;
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {bindings.desired_code[i]=0x180000000+0x10000ull*i;bindings.reject[i]=0x1c0000000;}
    EpClientPeerFamilyAddresses family={};family.game=bindings.game_base;family.client=client;family.peers=bank;family.reject=0x1c0000000;family.capacity=8;
    for (unsigned i=0;i<8;i++) family.code[i]=0x182000000+0x10000ull*i;
    EpNativeRosterView view={};view.game=bindings.game_base;view.roster=bindings.roster_address;view.storage=bindings.storage_address;view.build=25480438;view.epoch=1;
    EpRosterMemory memory={nullptr,Read};EpRosterCallPolicy policy={Failure,nullptr,nullptr};
    REQUIRE(ep_roster_owner_create(mod,&view,&memory,&owner)==EP_OWNER_OK);
    REQUIRE(ep_roster_group_prepare_owned_peer_family(&api,mod,&bindings,owner,&policy,&family,&group));
    REQUIRE(ep_roster_group_peer_routes_info(mod,group.handle,&routes) && routes.count==8 && !routes.retained && !hooks);
    auto saved=routes;
    REQUIRE(ep_roster_group_cancel(mod,group.handle));
    for (unsigned i=0;i<8;i++) {
        EpSessionCodeInfo info={};REQUIRE(!ep_session_code_info(mod,saved.body[i].handle,&info));
        REQUIRE(!ep_session_code_info(mod,saved.gate[i].handle,&info));
    }
    REQUIRE(ep_roster_group_prepare_owned_peer_family(&api,mod,&bindings,owner,&policy,&family,&group));
    REQUIRE(ep_roster_group_peer_routes_info(mod,group.handle,&routes));
    EpRosterCallContext* roster_call=nullptr;memcpy(&roster_call,(const void*)(group.code[0].base+2),8);
    for (unsigned i=0;i<8;i++) {
        EpRosterCallContext* call=nullptr;memcpy(&call,(const void*)(routes.gate[i].base+2),8);
        REQUIRE(call->active==roster_call->active && call->switching==roster_call->switching && call->owner==owner);
        REQUIRE(call->body==routes.body[i].base && call->join_client==client && call->kind==EP_ROSTER_CALL_PEER_INSERT+i);
    }
    REQUIRE(ep_roster_group_publish(mod,group.handle,0) && hooks==26 && !bad);
    auto insert=(uint64_t(*)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t))routes.gate[0].base;
    auto registered=(uint64_t(*)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t))routes.gate[1].base;
    REQUIRE(insert(client,0x11,0x22,0x33,0x44,0x55,0x66)==0x123456789);
    REQUIRE(registered(0x77,0x88,0x99,0xaa,0xbb,0xcc)==0x987654321 && old_insert==1 && old_registered==1 && !bad);
    REQUIRE(VirtualAlloc((void*)(client-0x162c8),0x17000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==(void*)(client-0x162c8));
    REQUIRE(VirtualAlloc((void*)bank,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE)==(void*)bank);
    *(uint32_t*)(client+0xc8)=8;memset((void*)(client+0xd0),0xa5,128);
    for (unsigned i=0;i<8;i++) {*(uint64_t*)(bank+i*32)=0x100+i;*(uint32_t*)(bank+i*32+0x14)=i==7 ? 4 : i;}
    REQUIRE(ep_roster_group_transition_claim(mod,group.handle,owner,view.game,&token));
    REQUIRE(ep_roster_owner_call(mod,owner,1,Activate,nullptr)==EP_OWNER_OK);
    REQUIRE(ep_roster_group_info(mod,group.handle,&group) && group.active && group.state==EP_GROUP_ACTIVE);
    auto contains=(uint64_t(*)(uint64_t,uint64_t))routes.gate[6].base;
    EpRosterOwnerInfo before={},after={};REQUIRE(ep_roster_owner_info(mod,owner,&before)==EP_OWNER_OK);
    REQUIRE((contains(client,0x107)&0xff)==1);
    REQUIRE(ep_roster_owner_call(mod,owner,0,Lookup,(void*)(bank+224))==EP_OWNER_OK);
    REQUIRE(ep_roster_owner_info(mod,owner,&after)==EP_OWNER_OK && before.revision==after.revision);
    REQUIRE(ep_roster_owner_call(mod,owner,1,Compact,nullptr)==EP_OWNER_OK);
    REQUIRE((contains(client,0x100)&0xff)==0 && (contains(client,0x107)&0xff)==1);
    // No enclosing lease: the movable lookup pointer must not escape.
    auto lookup=(uint64_t(*)(uint64_t,uint64_t))routes.gate[5].base;
    REQUIRE(lookup(client,0x107)==0xbadc0de && failures==1 && failed_kind==EP_ROSTER_CALL_PEER_LOOKUP);
    REQUIRE(ep_roster_owner_info(mod,owner,&after)==EP_OWNER_OK && after.fault && !bad);
    REQUIRE(!ep_roster_group_cancel(mod,group.handle));
    return 0;
}
