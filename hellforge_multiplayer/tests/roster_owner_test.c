/* Test-owned emulator fixtures only. Actual loader consumers + actual owner DLL.
 * These races exercise production owner APIs, not a stand-in test lock. */
#include "native_fixture.h"
#include "roster_owner_dll.h"
#undef CHECK
#define CHECK(x) do { InterlockedIncrement((volatile LONG*)&checks); if (!(x)) { fprintf(stderr,"FAIL %d: %s\n",__LINE__,#x); exit(1); } } while(0)
static const RosterOwnerTestApi* api;
static HfMod* mod;
static uint64_t owner;
static EpRosterMemory memory;
static EpNativeRosterView initial;
static EpRosterIdentitySet full,seven,rejoined;
typedef struct Fixture {unsigned count; Region regions[32];} Fixture;
static Fixture fixtures[3];
static volatile LONG mutations,memoryCalls,readPause,readFault,readFailure,reenterRead;
static HANDLE entered,resume;
static void Install(unsigned index)
{ regionCount=fixtures[index].count;memcpy(regions,fixtures[index].regions,sizeof(regions)); }
static void Reentry(void)
{
    EpHfRosterSnapshot out;EpRosterOwnerInfo info;EpHfRosterProvider provider;uint64_t id=99;
    CHECK(api->snapshot(mod,owner,initial.game,&out)==EP_NATIVE_UNAVAILABLE && !out.count);
    CHECK(api->info(mod,owner,&info)==EP_OWNER_REENTRANT);
    CHECK(api->provider(mod,owner,&provider)==EP_OWNER_REENTRANT);
    CHECK(api->create(mod,&initial,&memory,&id)==EP_OWNER_REENTRANT && !id);
    CHECK(api->close(mod,owner)==EP_OWNER_REENTRANT);
}
static int Memory(void* context,uintptr_t address,void* out,size_t bytes)
{
    CHECK(context==&fixtures);InterlockedIncrement(&memoryCalls);
    if (InterlockedExchange(&reenterRead,0)) Reentry();
    if (InterlockedExchange(&readPause,0)) {
        SetEvent(entered);CHECK(WaitForSingleObject(resume,5000)==WAIT_OBJECT_0);
    }
    if (InterlockedExchange(&readFault,0)) RaiseException(0xE0421001,0,0,NULL);
    if (InterlockedExchange(&readFailure,0)) return 0;
    for (unsigned i=0;i<regionCount;i++) if (address>=regions[i].address && address-regions[i].address<=regions[i].size &&
        bytes<=regions[i].size-(address-regions[i].address)) {
        memcpy(out,regions[i].data+address-regions[i].address,bytes);return 1;
    }
    return 0;
}
typedef struct Change {unsigned fixture;int mode;} Change;
static int Mutate(void* context,const EpNativeRosterView* current)
{
    Change* change=(Change*)context;InterlockedIncrement(&mutations);
    CHECK(current->game==initial.game && current->roster==initial.roster && current->storage==initial.storage);
    CHECK(current->lease==NULL && current->epoch==42);
    if (change->mode==1) {
        /* Deliberately inconsistent halfway state; reader must not see it. */
        regions[0]=fixtures[change->fixture].regions[0];
        SetEvent(entered);CHECK(WaitForSingleObject(resume,5000)==WAIT_OBJECT_0);
    }
    if (change->mode==2) {
        Reentry();
        CHECK(api->mutate(mod,owner,1,NULL,Mutate,context)==EP_OWNER_REENTRANT);
    }
    if (change->mode==3 || change->mode==4) {
        Write32(0,0x80,9);
        if (change->mode==4) RaiseException(0xE0421002,0,0,NULL);
        return 0;
    }
    Install(change->fixture);return 1;
}
static void Open(void)
{
    Install(0);CHECK(api->create(mod,&initial,&memory,&owner)==EP_OWNER_OK && owner);
}
static uint64_t Revision(void)
{
    EpRosterOwnerInfo info;CHECK(api->info(mod,owner,&info)==EP_OWNER_OK && !info.fault);return info.revision;
}
static void GoodRead(unsigned count)
{
    EpHfRosterSnapshot out;CHECK(api->snapshot(mod,owner,initial.game,&out)==EP_NATIVE_OK && out.count==count && out.epoch==42);
    for (unsigned i=0;i<out.count;i++) {
        CHECK(out.players[i].network_index<8 && out.players[i].generation);
        if (count==7) CHECK(out.players[i].peer!=104);
    }
}
static void NoCall(EpRosterOwnerResult expected,uint64_t revision,const EpRosterIdentitySet* next)
{
    LONG before=mutations;Change change={0,0};
    CHECK(api->mutate(mod,owner,revision,next,Mutate,&change)==expected && mutations==before);
}
typedef struct Job {
    int operation;uint64_t revision;const EpRosterIdentitySet* next;Change change;
    EpRosterOwnerResult result;EpNativeRosterStatus read_result;EpHfRosterSnapshot out;
} Job;
static DWORD WINAPI Work(LPVOID context)
{
    Job* job=(Job*)context;
    if (job->operation==1) job->result=api->mutate(mod,owner,job->revision,job->next,Mutate,&job->change);
    else if (job->operation==2) job->result=api->close(mod,owner);
    else if (job->operation==3) job->read_result=EpRosterRead(initial.game,&job->out)==8 ? EP_NATIVE_OK : EP_NATIVE_UNAVAILABLE;
    else job->read_result=api->snapshot(mod,owner,initial.game,&job->out);
    return 0;
}
static HANDLE Start(Job* job)
{ HANDLE thread=CreateThread(NULL,0,Work,job,0,NULL);CHECK(thread!=NULL);return thread; }
static void Join(HANDLE thread)
{ CHECK(WaitForSingleObject(thread,5000)==WAIT_OBJECT_0);CHECK(CloseHandle(thread)); }
static void Waiting(unsigned refs,int closing)
{
    ULONGLONG until=GetTickCount64()+5000;int observed=0;uint32_t count;
    do {
        count=api->pending(mod,owner,&observed);
        if (count==refs && observed==closing) return;
        Sleep(1);
    } while(GetTickCount64()<until);
    CHECK(count==refs && observed==closing);
}
static void Events(void)
{ ResetEvent(entered);ResetEvent(resume); }
static void ArgumentTests(void)
{
    uint64_t id=123;EpNativeRosterView v=initial;EpRosterMemory bad=memory;
    CHECK(api->create(NULL,&v,&memory,&id)==EP_OWNER_ARGUMENT && !id);
    CHECK(api->create(mod,NULL,&memory,&id)==EP_OWNER_ARGUMENT);
    CHECK(api->create(mod,&v,NULL,&id)==EP_OWNER_ARGUMENT);
    CHECK(api->create(mod,&v,&memory,NULL)==EP_OWNER_ARGUMENT);
    bad.read=NULL;CHECK(api->create(mod,&v,&bad,&id)==EP_OWNER_ARGUMENT);
    for (unsigned i=0;i<10;i++) {
        v=initial;
        switch (i) {
            case 0:v.epoch=0;break;case 1:v.build=1;break;case 2:v.lease=&v;break;
            case 3:v.game++;break;case 4:v.roster++;break;case 5:v.storage++;break;
            case 6:v.storage=v.roster+16;break;case 7:v.game=(UINT64_C(1)<<47)-4096;break;
            case 8:v.roster=0;break;case 9:v.storage=(UINT64_C(1)<<47)-16;break;
        }
        CHECK(api->create(mod,&v,&memory,&id)==EP_OWNER_ARGUMENT && !id);
    }
    for (unsigned i=0;i<10;i++) {
        v=initial;
        switch(i) {
            case 0:v.ticket_count=9;break;case 1:v.tickets[0].peer=0;break;
            case 2:v.tickets[0].player=0;break;case 3:v.tickets[0].epoch++;break;
            case 4:v.tickets[0].generation=0;break;case 5:v.tickets[0].reserved=1;break;
            case 6:v.tickets[0].network_index=8;break;
            case 7:v.tickets[0].peer=v.tickets[1].peer;break;
            case 8:v.tickets[0].player=v.tickets[1].player;break;
            case 9:v.tickets[0].network_index=v.tickets[1].network_index;break;
        }
        CHECK(api->create(mod,&v,&memory,&id)==EP_OWNER_IDENTITY && !id);
    }
    Open();LONG before=memoryCalls;
    for (unsigned i=0;i<5;i++) {
        v=initial;v.game+=0x10000000;v.roster+=0x10000000;v.storage+=0x10000000;
        switch(i) {
            case 0:v.game=initial.game;break;case 1:v.roster=initial.roster+0x420;break;
            case 2:v.roster=initial.storage+0x678;break;case 3:v.storage=initial.roster+0x420;break;
            case 4:v.storage=initial.storage+0x670;break;
        }
        CHECK(api->create(&g_mods[1],&v,&memory,&id)==EP_OWNER_CONFLICT && !id);
    }
    CHECK(memoryCalls==before);
    CHECK(api->info(&g_mods[1],owner,&(EpRosterOwnerInfo){0})==EP_OWNER_UNAVAILABLE);
    CHECK(api->close(&g_mods[1],owner)==EP_OWNER_UNAVAILABLE);
    EpHfRosterSnapshot out;
    CHECK(api->snapshot(&g_mods[1],owner,initial.game,&out)==EP_NATIVE_UNAVAILABLE);
    CHECK(api->snapshot(mod,owner,initial.game+4096,&out)==EP_NATIVE_UNAVAILABLE && memoryCalls==before);
    GoodRead(8);readFailure=1;
    CHECK(api->snapshot(mod,owner,initial.game,&out)==EP_NATIVE_READ_FAILED && !out.count);
    GoodRead(8);reenterRead=1;GoodRead(8);
    Change change={0,2};CHECK(api->mutate(mod,owner,1,NULL,Mutate,&change)==EP_OWNER_OK);
    NoCall(EP_OWNER_STALE,1,NULL);CHECK(Revision()==2);
    for (unsigned i=0;i<8;i++) {
        EpRosterIdentitySet badSet=full;
        switch(i) {
            case 0:badSet.count=9;break;case 1:badSet.tickets[0].generation++;break;
            case 2:badSet.tickets[0].peer++;break;case 3:badSet.tickets[0].generation=0;break;
            case 4:badSet.tickets[0].epoch++;break;case 5:badSet.tickets[0].reserved=1;break;
            case 6:badSet.tickets[0].network_index=8;break;
            case 7:badSet.tickets[0].player=badSet.tickets[1].player;break;
        }
        NoCall(EP_OWNER_IDENTITY,2,&badSet);
    }
    CHECK(api->close(mod,owner)==EP_OWNER_OK);
}
static void Lifecycle(void)
{
    Open();EpHfRosterProvider provider;EpHfRosterSnapshot out;
    CHECK(api->provider(mod,owner,&provider)==EP_OWNER_OK);
    uint64_t binding=EpRosterBind(mod,&provider);CHECK(binding);
    spawns=0;g_playerCount=0;
    CHECK(ApiSubscribe(mod,HF_ON_PLAYER_SPAWN,Heard,NULL,0));
    PollPlayers(initial.game);CHECK(spawns==8 && ActPlayerCount(initial.game)==8);
    Change remove={1,0},join={2,0};
    CHECK(api->mutate(mod,owner,1,&seven,Mutate,&remove)==EP_OWNER_OK);
    GoodRead(7);PollPlayers(initial.game);CHECK(spawns==8 && ActPlayerCount(initial.game)==7);
    NoCall(EP_OWNER_IDENTITY,2,&full); /* stale generation on the freed slot */
    CHECK(api->mutate(mod,owner,2,&rejoined,Mutate,&join)==EP_OWNER_OK);
    GoodRead(8);PollPlayers(initial.game);CHECK(spawns==9 && ActPlayerCount(initial.game)==8);
    CHECK(api->snapshot(mod,owner,initial.game,&out)==EP_NATIVE_OK);
    CHECK(out.players[7].peer==104 && out.players[7].network_index==6 && out.players[7].generation==15);
    CHECK(out.players[4].peer==107 && out.players[4].network_index==7);
    uint64_t stale=owner;CHECK(api->close(mod,owner)==EP_OWNER_OK);
    Open();CHECK(owner!=stale);
    CHECK(!provider.read(provider.context,initial.game,&out) && !out.count && !out.epoch);
    CHECK(EpRosterRead(initial.game,&out)==-1); /* no legacy fallback/ABA */
    CHECK(EpRosterUnbind(mod,binding));CHECK(api->close(mod,owner)==EP_OWNER_OK);
}
static void Races(void)
{
    Open();Events();Job writer={.operation=1,.revision=1,.next=&seven,.change={1,1}},reader={0};
    HANDLE w=Start(&writer);CHECK(WaitForSingleObject(entered,5000)==WAIT_OBJECT_0);
    HANDLE r=Start(&reader);Waiting(2,0);CHECK(WaitForSingleObject(r,20)==WAIT_TIMEOUT);
    SetEvent(resume);Join(w);Join(r);
    CHECK(writer.result==EP_OWNER_OK && reader.read_result==EP_NATIVE_OK && reader.out.count==7);
    CHECK(Revision()==2);CHECK(api->close(mod,owner)==EP_OWNER_OK);
    Open();Events();readPause=1;reader=(Job){0};writer=(Job){.operation=1,.revision=1,.next=&seven,.change={1,0}};
    r=Start(&reader);CHECK(WaitForSingleObject(entered,5000)==WAIT_OBJECT_0);LONG before=mutations;
    w=Start(&writer);Waiting(2,0);CHECK(mutations==before && WaitForSingleObject(w,20)==WAIT_TIMEOUT);
    SetEvent(resume);Join(r);Join(w);
    CHECK(reader.out.count==8 && writer.result==EP_OWNER_OK);GoodRead(7);
    CHECK(api->close(mod,owner)==EP_OWNER_OK);
    /* Two writers share an expected revision. Only one can change data. */
    Open();Events();writer=(Job){.operation=1,.revision=1,.next=&seven,.change={1,1}};
    Job second={.operation=1,.revision=1,.next=&seven,.change={1,0}};
    w=Start(&writer);CHECK(WaitForSingleObject(entered,5000)==WAIT_OBJECT_0);before=mutations;
    HANDLE s=Start(&second);Waiting(2,0);SetEvent(resume);Join(w);Join(s);
    CHECK(writer.result==EP_OWNER_OK && second.result==EP_OWNER_STALE && mutations==before);
    CHECK(api->close(mod,owner)==EP_OWNER_OK);
    /* Close waits for an in-flight actual loader read AND a queued writer. */
    Open();EpHfRosterProvider provider;CHECK(api->provider(mod,owner,&provider)==EP_OWNER_OK);
    uint64_t binding=EpRosterBind(mod,&provider);CHECK(binding);
    Events();readPause=1;reader=(Job){.operation=3};writer=(Job){.operation=1,.revision=1,.next=&seven,.change={1,0}};
    r=Start(&reader);CHECK(WaitForSingleObject(entered,5000)==WAIT_OBJECT_0);
    w=Start(&writer);Waiting(2,0);before=mutations;
    Job close={.operation=2};HANDLE c=Start(&close);Waiting(2,1);
    EpHfRosterSnapshot out;CHECK(api->snapshot(mod,owner,initial.game,&out)==EP_NATIVE_UNAVAILABLE);
    uint64_t conflict=0;CHECK(api->create(mod,&initial,&memory,&conflict)==EP_OWNER_CONFLICT);
    CHECK(WaitForSingleObject(c,20)==WAIT_TIMEOUT);
    SetEvent(resume);Join(r);Join(w);Join(c);
    CHECK(reader.read_result==EP_NATIVE_OK && writer.result==EP_OWNER_UNAVAILABLE && mutations==before && close.result==EP_OWNER_OK);
    CHECK(EpRosterRead(initial.game,&out)==-1);CHECK(EpRosterUnbind(mod,binding));
}
static void Faults(void)
{
    for (int fault=0;fault<3;fault++) {
        Open();EpHfRosterProvider provider;EpHfRosterSnapshot out;EpRosterOwnerInfo info;
        CHECK(api->provider(mod,owner,&provider)==EP_OWNER_OK);
        uint64_t binding=EpRosterBind(mod,&provider);CHECK(binding);
        if (fault==2) {readFault=1;CHECK(EpRosterRead(initial.game,&out)==-1);}
        else {
            Change change={0,fault ? 4 : 3};
            CHECK(api->mutate(mod,owner,1,&seven,Mutate,&change)==(fault ? EP_OWNER_CALLBACK_FAULT : EP_OWNER_CALLBACK_FAILED));
        }
        CHECK(api->info(mod,owner,&info)==EP_OWNER_OK && info.fault && info.revision==1 && info.ticket_count==8);
        LONG before=memoryCalls;CHECK(EpRosterRead(initial.game,&out)==-1 && !out.count && memoryCalls==before);
        NoCall(EP_OWNER_FAULTED,1,NULL);
        CHECK(EpRosterUnbind(mod,binding));CHECK(api->close(mod,owner)==EP_OWNER_OK);
    }
    Open();EpRosterIdentitySet high=full;high.tickets[0].peer=999;high.tickets[0].generation=UINT32_MAX;
    Change change={0,0};CHECK(api->mutate(mod,owner,1,&high,Mutate,&change)==EP_OWNER_OK);
    EpRosterIdentitySet empty={0};CHECK(api->mutate(mod,owner,2,&empty,Mutate,&change)==EP_OWNER_OK);
    NoCall(EP_OWNER_IDENTITY,3,&high);high.tickets[0].generation=1;NoCall(EP_OWNER_IDENTITY,3,&high);
    CHECK(api->close(mod,owner)==EP_OWNER_OK);
}
static void Capacity(void)
{
    uint64_t ids[8],extra;EpNativeRosterView v=initial;
    for (unsigned i=0;i<8;i++) {
        v=initial;v.game+=UINT64_C(0x10000000)*(i+1);v.roster+=UINT64_C(0x10000000)*(i+1);v.storage+=UINT64_C(0x10000000)*(i+1);
        CHECK(api->create(mod,&v,&memory,&ids[i])==EP_OWNER_OK);
    }
    v=initial;CHECK(api->create(mod,&v,&memory,&extra)==EP_OWNER_EXHAUSTED && !extra);
    for (unsigned i=0;i<8;i++) CHECK(api->close(mod,ids[i])==EP_OWNER_OK);
    Open();GoodRead(8);CHECK(api->close(mod,owner)==EP_OWNER_OK);
}
int main(int argc,char** argv)
{
    CHECK(argc==5);(void)Begin;(void)End;(void)ReadMemory;(void)Snapshot;
    HMODULE dll=LoadLibraryA(argv[1]);CHECK(dll!=NULL);
    const RosterOwnerTestApi* (*get)(void)=(const RosterOwnerTestApi*(*)(void))GetProcAddress(dll,"roster_owner_test_api");CHECK(get!=NULL);api=get();
    for (unsigned i=0;i<3;i++) {LoadFixture(argv[i+2]);fixtures[i].count=regionCount;memcpy(fixtures[i].regions,regions,sizeof(regions));}
    initial=view;initial.epoch=42;initial.build=25480438;initial.ticket_count=8;initial.lease=NULL;
    for (unsigned i=0;i<8;i++) initial.tickets[i]=(EpNativeTicket){100+i,42,1+8*i,(3*i+2)%8,10+i,0};
    full.count=8;memcpy(full.tickets,initial.tickets,sizeof(full.tickets));rejoined=full;rejoined.tickets[4].generation++;
    for (unsigned i=0;i<8;i++) if (i!=4) seven.tickets[seven.count++]=full.tickets[i];
    strcpy(g_build,"25480438");g_modCount=2;g_mods[0].loaded=g_mods[1].loaded=1;mod=&g_mods[0];memory=(EpRosterMemory){&fixtures,Memory};
    entered=CreateEventA(NULL,TRUE,FALSE,NULL);resume=CreateEventA(NULL,TRUE,FALSE,NULL);CHECK(entered && resume);
    fprintf(stderr,"owner: arguments\n");ArgumentTests();
    fprintf(stderr,"owner: lifecycle\n");Lifecycle();
    fprintf(stderr,"owner: races\n");Races();
    fprintf(stderr,"owner: faults\n");Faults();
    fprintf(stderr,"owner: capacity\n");Capacity();
    CloseHandle(entered);CloseHandle(resume);CHECK(FreeLibrary(dll));
    printf("roster owner: %u checks passed; production DLL and real loader, synthetic memory only\n",checks);return 0;
}
