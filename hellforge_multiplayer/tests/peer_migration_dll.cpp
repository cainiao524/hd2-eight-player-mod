/* Real migration/coordinator/owner, with explicit group/component fixtures.
 * All data belongs to this DLL. Never reads a process or invokes game code. */
#include "ep_multiplayer_commit.h"
#include "ep_roster_group_transition.h"
#include <windows.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
static void Check(bool ok,const char* why) {if (!ok) {fprintf(stderr,"peer migration: %s\n",why);abort();}}
static void D(void* p,uint32_t v) {memcpy(p,&v,4);}
static void Q(void* p,uint64_t v) {memcpy(p,&v,8);}
static HfMod* mod=(HfMod*)0x918c;
static EpNativeRosterView view;
static EpPlayerJoinPeers binding;
static uint64_t owner;
static EpRosterMigrationSnapshot source;
alignas(16) static uint8_t bank[288],roster[0x680],expected[0x680];
static bool claimed,frozen,switching,active,change_source;
static unsigned requests,peer_reads,ends,commits;
static int Memory(void*,uintptr_t,void*,size_t) {Check(false,"unexpected provider read");return 0;}
static int Read(uintptr_t a,void* out,size_t n)
{
    Check(frozen && switching && ep_roster_owner_native_status(mod,owner)==EP_OWNER_OK,"read outside freeze/owner");
    struct Region {uint64_t address;size_t size;const void* data;};
    const Region regions[]={{view.game+0x3326468,8,&source.global},{view.game+0x3483c34,4,&source.invalid},
        {view.roster,sizeof(source.source),source.source},{view.game+0x347cef0,8,&source.peers.global},
        {binding.client+0xc8,4,&source.peers.count},{binding.client+0xd0,128,source.peers.records}};
    requests+=(unsigned)n;
    for (const auto& r:regions) if (a==r.address && n==r.size) {
        memcpy(out,r.data,n);if (a==binding.client+0xd0) ++peer_reads;return 0;
    }
    for (const auto& e:source.entities) if (n==4 && (a==e.address+8 || a==e.address+20)) {
        memcpy(out,a==e.address+8 ? &e.id : &e.flags,4);return 0;
    }
    Check(false,"unlisted SDK read");return 1;
}
// These fixtures implement only the coordinator interfaces under examination;
// they do not publish hooks, construct resources, or replace engine exclusion.
int ep_component33_resource_entries_transaction_binding(HfMod*,uint64_t,uint64_t* o,uint64_t* g)
{*o=owner;*g=view.game;return 1;}
int ep_component33_resource_entries_transaction_view(HfMod*,uint64_t,EpC33ResourceScopeView* out)
{*out={view.game,0x230000000,0x230010000,{0x230020000,128,0}};return 1;}
int ep_roster_group_peer_binding(HfMod*,uint64_t,EpPlayerJoinPeers* out)
{Check(claimed,"binding before claim");*out=binding;return 1;}
int ep_roster_group_transition_claim(HfMod*,uint64_t g,uint64_t o,uint64_t game,EpRosterGroupTransition* out)
{Check(!claimed && !active && o==owner && game==view.game,"claim");claimed=true;*out={g,1,o};return 1;}
int ep_roster_group_transition_enter(HfMod*,const EpRosterGroupTransition*)
{Check(claimed && frozen && ep_roster_owner_native_status(mod,owner)==EP_OWNER_OK,"enter");switching=true;return 1;}
int ep_roster_group_transition_activate(HfMod*,const EpRosterGroupTransition*)
{Check(switching && frozen,"activate outside freeze");active=true;return 1;}
int ep_roster_group_transition_finish(HfMod*,const EpRosterGroupTransition*,uint32_t outcome)
{Check(claimed && (outcome==EP_C33_COMMIT_NEW)==active,"finish");claimed=false;switching=false;return 1;}
struct ComponentCall {const EpC33EntryCommitGuard* guard;void* lease;int ok;};
static int UnderOwner(void* p,const EpNativeRosterView*)
{
    auto* c=(ComponentCall*)p;c->ok=c->guard->validate(c->guard->context,c->lease);
    c->guard->end(c->guard->context,c->lease,c->ok ? EP_C33_COMMIT_NEW : EP_C33_COMMIT_OLD);return 1;
}
int ep_component33_resource_entries_commit_budgeted(HfMod*,uint64_t,const EpC33EntryCommitGuard* guard,
    EpCommitReadBudget*,EpC33MigrationCommitResult* out)
{
    ++commits;*out={};ComponentCall call={guard,nullptr,0};Check(guard->begin(guard->context,&call.lease)!=0,"begin");
    Check(ep_roster_owner_call(mod,owner,1,UnderOwner,&call)==EP_OWNER_OK,"joint owner callback");return call.ok;
}
static int Begin(void*,void** lease) {Check(!frozen,"double freeze");frozen=true;*lease=&source;return 1;}
static void Data(bool migrated)
{
    if (migrated) {
        Check(!memcmp(roster,expected,sizeof(roster)),"roster arrays");
        Check(!memcmp(bank+16,source.peers.records,128),"complete peer records/order");
        for (unsigned i=144;i<272;i++) Check(bank[i]==0,"new slots not clear");
    } else {
        for (auto b:roster) Check(b==0xa7,"roster rollback");
        for (unsigned i=16;i<272;i++) Check(bank[i]==0xa9,"peer rollback");
    }
    for (unsigned i=0;i<16;i++) Check(bank[i]==0x6c && bank[i+272]==0x6c,"bank boundary");
}
static int Validate(void*,void*)
{
    Data(true);
    if (change_source) source.peers.records[127]^=0x55; // opaque byte drift, after staging
    return 1;
}
static void End(void*,void* lease,uint32_t outcome)
{
    Check(lease==&source && frozen && switching,"end lease");Data(outcome==EP_C33_COMMIT_NEW);
    Check(active==(outcome==EP_C33_COMMIT_NEW),"end before activation");++ends;frozen=false;
}
extern "C" __declspec(dllexport) unsigned peer_migration_flow()
{
    memset(bank,0x6c,sizeof(bank));memset(bank+16,0xa9,256);memset(roster,0xa7,sizeof(roster));
    view={};view.game=0x140000000;view.roster=0x220000000;view.storage=(uintptr_t)roster;view.epoch=3;view.build=25480438;view.ticket_count=4;
    binding={0x2100162c8,(uintptr_t)(bank+16),8,0};source={};source.global=view.roster;source.invalid=UINT32_MAX;
    source.peers.global=binding.client-0x162c8;source.peers.count=4;auto* s=source.source;
    D(s+0x80,4);D(s+0x84,4);D(s+0x88,2);Q(s+0xd0,view.roster+0x90);D(s+0xd8,8);D(s+0xe0,1);
    for (unsigned i=0xe8;i<sizeof(source.source);i++) s[i]=(uint8_t)(i*37+11);
    for (unsigned i=0;i<128;i++) source.peers.records[i]=(uint8_t)(i*13+7);
    for (unsigned i=0;i<4;i++) {
        source.entities[i]={0x260000000+64ull*i,i+1,unsigned(i<2)};
        Q(s+0xe8+8*i,source.entities[i].address);Q(s+0x2c8+0x38*i,100+i);D(s+0x3a8+0x20*i+12,(i+1)%4);
        D(s+0x90+(i+1)*8,i+1);D(s+0x90+(i+1)*8+4,i);view.tickets[i]={100+i,3,i+1,(i+1)%4,1,0};
        unsigned ordinal=3-i;Q(source.peers.records+ordinal*32,100+i);D(source.peers.records+ordinal*32+0x14,(i+1)%4);
    }
    memcpy(expected,s+0xe8,32);memcpy(expected+0x40,s+0x108,4*0x70);memcpy(expected+0x3c0,s+0x2c8,4*0x38);memcpy(expected+0x580,s+0x3a8,4*0x20);
    EpRosterMemory memory={nullptr,Memory};Check(ep_roster_owner_create(mod,&view,&memory,&owner)==EP_OWNER_OK,"owner");
    HfApi api={};api.version=13;api.size=sizeof(api);api.read=Read;EpC33EntryCommitGuard guard={nullptr,Begin,Validate,End};EpMultiplayerCommitResult result={};
    // An alias must fail BEFORE even the component's staging callback.
    auto saved=binding.bank;binding.bank=0x230010000;
    Check(!ep_multiplayer_commit_migrated(&api,mod,1,2,&guard,&result) && !commits && !requests && !claimed,"early alias rejection");binding.bank=saved;
    change_source=true;
    Check(!ep_multiplayer_commit_migrated(&api,mod,1,2,&guard,&result),"changed source accepted");
    Check(result.outcome==EP_C33_COMMIT_OLD && result.roster_migration.status==EP_ROSTER_MIGRATION_CHANGED &&
        result.roster_migration.restored && result.roster_migration.peer_restored && result.roster_migration.peer_staged,"rollback diagnostics");
    Check(result.total_read_bytes==requests && requests<=65536 && peer_reads==3,"shared budget/three peer snapshots");
    requests=peer_reads=0;change_source=false;
    Check(ep_multiplayer_commit_migrated(&api,mod,1,2,&guard,&result),"fresh retry");Data(true);
    Check(result.outcome==EP_C33_COMMIT_NEW && result.roster_migration.status==EP_ROSTER_MIGRATION_OK &&
        result.roster_migration.peer_count==4 && result.roster_migration.peer_staged && !result.roster_migration.peer_restored &&
        result.total_read_bytes==requests && requests<=65536 && peer_reads==3 && ends==2,"retry/budget diagnostics");
    Check(ep_roster_owner_close(mod,owner)==EP_OWNER_OK,"close");return requests;
}
