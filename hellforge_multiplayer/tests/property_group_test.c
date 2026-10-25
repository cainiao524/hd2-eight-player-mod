/* Real HellForge chain, only newly allocated arithmetic functions in this PID. */
#include "hellforge_modloader.c"
#include "property_group_dll.h"
static LONG checks;
#define CHECK(x) do { InterlockedIncrement(&checks); if (!(x)) { fprintf(stderr,"FAIL %d: %s\n",__LINE__,#x); exit(1); } } while(0)
static const PropertyGroupTestApi* group;
static HfApi api;
static HfMod* owner;
typedef uint64_t (*Producer)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
typedef uint64_t (*Receiver)(uint64_t,uint64_t,uint64_t,uint64_t);
static Producer send;
static Receiver receive;
static uint64_t current;
static int hook_calls,fail_hook,fail_after,block_hook,begin_ok=1,validate_ok=1,begin_calls,end_calls;
static HANDLE entered,continued,commit_started;
static SRWLOCK mutation_lock=SRWLOCK_INIT;
static EpPropertyCommitGuard guard;
static int Hook(HfMod* mod,uintptr_t target,void* detour,void** next,int32_t priority)
{
    EpPropertyGroupInfo info;
    hook_calls++;
    CHECK(group->info(owner,current,&info) && info.state==EP_GROUP_PUBLISHING && !info.active);
    CHECK(!group->cancel(owner,current) && !group->commit(owner,current,&guard));
    CHECK(send(1,2,3,4,5,6)==22 && receive(1,2,3,4)==12);
    if (block_hook==hook_calls) { SetEvent(entered); CHECK(WaitForSingleObject(continued,5000)==WAIT_OBJECT_0); }
    if (fail_hook==hook_calls && !fail_after) return 1;
    int result=ApiHookEx(mod,target,detour,next,priority);
    CHECK(!result);
    CHECK(send(1,2,3,4,5,6)==22 && receive(1,2,3,4)==12);
    return fail_hook==hook_calls ? 1 : 0;
}
static int Begin(void* context,void** lease)
{
    (void)context; begin_calls++;
    if (!begin_ok) return 0;
    if (commit_started) SetEvent(commit_started);
    AcquireSRWLockExclusive(&mutation_lock); *lease=&mutation_lock; return 1;
}
static int Validate(void* context,void* lease)
{
    (void)context; CHECK(lease==&mutation_lock);
    EpPropertyGroupInfo info;
    CHECK(group->info(owner,current,&info) && info.state==EP_GROUP_COMMITTING && !info.active);
    CHECK(!group->cancel(owner,current) && !group->commit(owner,current,&guard));
    return validate_ok;
}
static void End(void* context,void* lease,int committed)
{
    (void)context; end_calls++; CHECK(lease==&mutation_lock);
    EpPropertyGroupInfo info;
    CHECK(group->info(owner,current,&info) && info.state==EP_GROUP_COMMITTING && info.active==(uint32_t)committed);
    CHECK(!group->cancel(owner,current) && !group->commit(owner,current,&guard));
    CHECK(send(1,2,3,4,5,6)==(committed ? 1021u : 22u));
    CHECK(receive(1,2,3,4)==(committed ? 2010u : 12u));
    ReleaseSRWLockExclusive(&mutation_lock);
}
static EpPropertyGroupBindings Targets(void)
{
    uint8_t* memory=(uint8_t*)VirtualAlloc(NULL,65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE); CHECK(memory!=NULL);
    memset(memory,0x90,65536);
    const uint8_t sum[]={0x48,0x89,0xC8,0x48,0x01,0xD0,0x4C,0x01,0xC0,0x4C,0x01,0xC8};
    const uint8_t tail6[]={0x48,0x03,0x44,0x24,0x28,0x48,0x03,0x44,0x24,0x30,0x48,0x83,0xC0,1,0xC3};
    const uint8_t tail4[]={0x48,0x83,0xC0,2,0xC3};
    memcpy(memory+0x640,sum,sizeof(sum)); memcpy(memory+0x640+sizeof(sum),tail6,sizeof(tail6));
    memcpy(memory+0x890,sum,sizeof(sum)); memcpy(memory+0x890+sizeof(sum),tail4,sizeof(tail4));
    DWORD old; CHECK(VirtualProtect(memory,65536,PAGE_EXECUTE_READ,&old)); CHECK(FlushInstructionCache(GetCurrentProcess(),memory,65536));
    send=(Producer)(memory+0x640); receive=(Receiver)(memory+0x890);
    CHECK(send(1,2,3,4,5,6)==22 && receive(1,2,3,4)==12);
    EpPropertyGroupBindings b={0}; b.game_base=(uintptr_t)memory-0x60C000;
    b.roster_address=(uintptr_t)memory+0x10000000; b.property_address=(uintptr_t)memory+0x20000000;
    b.reject[0]=(uintptr_t)memory+0x30000000; b.reject[1]=(uintptr_t)memory+0x30010000;
    hook_calls=fail_hook=fail_after=block_hook=0;
    return b;
}
static void UnwindGate(EpPropertyGroupInfo info)
{
    const uint32_t positions[]={0,10,13,15,20,30};
    for (unsigned i=0;i<2;i++) {
        DWORD64 base=0;
        PRUNTIME_FUNCTION gate=RtlLookupFunctionEntry(info.code[i].base,&base,NULL);
        CHECK(gate && gate->BeginAddress==0 && gate->EndAddress==32 && base==info.code[i].base);
        CHECK(RtlLookupFunctionEntry(base+32,&base,NULL)==gate+1);
        CHECK((gate+1)->BeginAddress==32 && (gate+1)->EndAddress==(i ? 430u : 702u));
        for (unsigned j=0;j<sizeof(positions)/sizeof(positions[0]);j++) {
            uint64_t stack[16]={0x12345678}; CONTEXT c; memset(&c,0,sizeof(c));
            c.ContextFlags=CONTEXT_FULL; c.Rip=base+positions[j]; c.Rsp=(uintptr_t)stack; c.Rax=info.code[i].next_pointer;
            c.Rbx=11; c.Rbp=22; c.Rsi=33; c.Rdi=44; c.R12=55; c.R13=66; c.R14=77; c.R15=88;
            PVOID handler=NULL; DWORD64 frame=0;
            RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,c.Rip,gate,&c,&handler,&frame,NULL);
            CHECK(c.Rip==stack[0] && c.Rsp==(uintptr_t)stack+8);
            CHECK(c.Rbx==11 && c.Rbp==22 && c.Rsi==33 && c.Rdi==44 && c.R12==55 && c.R13==66 && c.R14==77 && c.R15==88);
        }
    }
}
static DWORD WINAPI PublishThread(void* unused) { (void)unused; return group->publish(owner,current,10) ? 0 : 1; }
static DWORD WINAPI CommitThread(void* unused) { (void)unused; return group->commit(owner,current,&guard) ? 0 : 1; }
static DWORD WINAPI OldReader(void* unused)
{
    (void)unused; AcquireSRWLockShared(&mutation_lock);
    CHECK(send(1,2,3,4,5,6)==22); SetEvent(entered);
    CHECK(WaitForSingleObject(continued,5000)==WAIT_OBJECT_0);
    CHECK(receive(1,2,3,4)==12); ReleaseSRWLockShared(&mutation_lock); return 0;
}
static void BadTables(EpPropertyGroupInfo info)
{
    uint8_t image[756]; DWORD64 base;
    for (unsigned bad=0;bad<10;bad++) {
        memcpy(image,(void*)info.code[0].base,756);
        uint32_t* rows=(uint32_t*)(image+732);
        switch(bad) {
        case 0: rows[0]=1; break;
        case 1: rows[3]=31; break; /* overlapping ranges */
        case 2: rows[4]=32; break; /* empty second function */
        case 3: rows[5]=rows[2]; break; /* shared/overlapping unwind */
        case 4: rows[5]=32; break; /* metadata inside code */
        case 5: image[730]=2; break; /* leaf claims absent slots */
        case 6: rows[4]=33; break; /* prologue larger than its function */
        case 7: rows[5]=705; break; /* unaligned */
        }
        EpSessionCodeInfo allocation;
        CHECK(group->reserve(&api,owner,0,756,&allocation));
        CHECK(!group->seal(owner,allocation.handle,image,756,732,bad==8 ? 0 : bad==9 ? 3 : 2));
        CHECK(RtlLookupFunctionEntry(allocation.base,&base,NULL)==NULL);
        CHECK(group->discard(owner,allocation.handle));
    }
}
static void* extra_next;
static uint64_t Extra(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f)
{ return ((Producer)extra_next)(a,b,c,d,e,f)+100; }
int main(int argc,char** argv)
{
    CHECK(argc==2); HMODULE dll=LoadLibraryA(argv[1]); CHECK(dll!=NULL);
    const PropertyGroupTestApi* (*get)(void)=(const PropertyGroupTestApi*(*)(void))GetProcAddress(dll,"property_group_test_api"); CHECK(get!=NULL); group=get();
    owner=&g_mods[0]; memset(g_mods,0,sizeof(g_mods)); strcpy(owner->id,"ep-group"); strcpy(g_mods[1].id,"later-mod");
    strcpy(g_build,"25480438"); g_modCount=2;
    for (int i=0;i<g_modCount;i++) { g_mods[i].loaded=1; g_mods[i].log=INVALID_HANDLE_VALUE; }
    api.version=13; api.size=sizeof(api); api.build_id=ApiBuildId; api.hook_ex=Hook;
    guard.context=NULL; guard.begin=Begin; guard.validate=Validate; guard.end=End;
    EpPropertyGroupBindings b=Targets(); EpPropertyGroupInfo info,out;
    CHECK(group->prepare(&api,owner,&b,&info)); current=info.handle;
    CHECK(info.state==EP_GROUP_PREPARED && !info.active && !info.published_attempts);
    CHECK(!group->commit(owner,current,&guard)); UnwindGate(info); BadTables(info);
    CHECK(!group->cancel(&g_mods[1],current));
    CHECK(group->cancel(owner,current)); CHECK(!group->info(owner,current,&out));
    /* A failed second candidate cleans the first, unless freeing itself fails. */
    group->failure(4); CHECK(!group->prepare(&api,owner,&b,&out) && !out.handle);
    group->failure(5); CHECK(!group->prepare(&api,owner,&b,&out) && out.handle && out.state==EP_GROUP_FAILED);
    CHECK(!group->cancel(owner,out.handle)); group->failure(0); CHECK(group->cancel(owner,out.handle));
    group->failure(2); CHECK(!group->prepare(&api,owner,&b,&out) && !out.handle); group->failure(0);
    /* Fail before/after first/second publication; never route to a new body. */
    for (unsigned index=1;index<=2;index++) for (unsigned after=0;after<=1;after++) {
        b=Targets(); CHECK(group->prepare(&api,owner,&b,&info)); current=info.handle;
        fail_hook=(int)index; fail_after=(int)after;
        CHECK(!group->publish(owner,current,10));
        CHECK(group->info(owner,current,&out) && out.state==EP_GROUP_FAILED && !out.active && out.published_attempts==index);
        CHECK(!group->commit(owner,current,&guard) && !group->publish(owner,current,10));
        CHECK(group->cancel(owner,current));
        CHECK(group->info(owner,current,&out) && out.state==EP_GROUP_CANCELLED && !out.active);
        CHECK(send(1,2,3,4,5,6)==22 && receive(1,2,3,4)==12);
    }
    b=Targets(); CHECK(group->prepare(&api,owner,&b,&info)); current=info.handle;
    entered=CreateEventA(NULL,TRUE,FALSE,NULL); continued=CreateEventA(NULL,TRUE,FALSE,NULL); CHECK(entered && continued);
    block_hook=2; HANDLE worker=CreateThread(NULL,0,PublishThread,NULL,0,NULL); CHECK(worker!=NULL);
    CHECK(WaitForSingleObject(entered,5000)==WAIT_OBJECT_0);
    CHECK(!group->cancel(owner,current) && !group->publish(owner,current,10) && !group->commit(owner,current,&guard));
    CHECK(send(1,2,3,4,5,6)==22 && receive(1,2,3,4)==12); CHECK(SetEvent(continued));
    CHECK(WaitForSingleObject(worker,5000)==WAIT_OBJECT_0); DWORD result; CHECK(GetExitCodeThread(worker,&result) && result==0);
    CloseHandle(worker); CloseHandle(entered); CloseHandle(continued);
    CHECK(group->info(owner,current,&out) && out.state==EP_GROUP_READY && !out.active && out.published_attempts==2);
    CHECK(!group->commit(owner,current,NULL)); begin_ok=0; CHECK(!group->commit(owner,current,&guard) && end_calls==0);
    begin_ok=1; validate_ok=0; CHECK(!group->commit(owner,current,&guard) && end_calls==1);
    CHECK(send(1,2,3,4,5,6)==22 && receive(1,2,3,4)==12);
    validate_ok=1;
    entered=CreateEventA(NULL,TRUE,FALSE,NULL); continued=CreateEventA(NULL,TRUE,FALSE,NULL);
    commit_started=CreateEventA(NULL,TRUE,FALSE,NULL); CHECK(entered && continued && commit_started);
    HANDLE reader=CreateThread(NULL,0,OldReader,NULL,0,NULL); CHECK(reader!=NULL);
    CHECK(WaitForSingleObject(entered,5000)==WAIT_OBJECT_0);
    worker=CreateThread(NULL,0,CommitThread,NULL,0,NULL); CHECK(worker!=NULL);
    CHECK(WaitForSingleObject(commit_started,5000)==WAIT_OBJECT_0);
    CHECK(group->info(owner,current,&out) && out.state==EP_GROUP_COMMITTING && !out.active);
    CHECK(send(1,2,3,4,5,6)==22 && receive(1,2,3,4)==12);
    CHECK(!group->cancel(owner,current)); CHECK(SetEvent(continued));
    CHECK(WaitForSingleObject(reader,5000)==WAIT_OBJECT_0 && WaitForSingleObject(worker,5000)==WAIT_OBJECT_0);
    CHECK(GetExitCodeThread(worker,&result) && result==0 && end_calls==2);
    CloseHandle(reader); CloseHandle(worker); CloseHandle(entered); CloseHandle(continued); CloseHandle(commit_started); commit_started=NULL;
    CHECK(group->info(owner,current,&out) && out.state==EP_GROUP_ACTIVE && out.active==1);
    CHECK(!group->cancel(owner,current) && !group->commit(owner,current,&guard));
    CHECK(send(10,20,30,40,50,60)==1210 && receive(10,20,30,40)==2100);
    Producer active_send=send; Receiver active_receive=receive;
    /* New SDK links rewrite the next pointer of a cancelled, forwarding gate. */
    b=Targets(); CHECK(group->prepare(&api,owner,&b,&info)); current=info.handle; CHECK(group->publish(owner,current,10));
    CHECK(group->cancel(owner,current));
    CHECK(ApiHookEx(&g_mods[1],(uintptr_t)send,(void*)Extra,&extra_next,0)==0);
    CHECK(send(1,2,3,4,5,6)==122 && receive(1,2,3,4)==12);
    EpPropertyGroupInfo pending[EP_PROPERTY_GROUP_SLOTS]; unsigned filled=0;
    while (filled<EP_PROPERTY_GROUP_SLOTS && group->prepare(&api,owner,&b,&pending[filled])) filled++;
    CHECK(filled==EP_PROPERTY_GROUP_SLOTS-6);
    CHECK(!group->prepare(&api,owner,&b,&out) && !out.handle);
    for (unsigned i=0;i<filled;i++) CHECK(group->cancel(owner,pending[i].handle));
    CHECK(group->prepare(&api,owner,&b,&out) && out.handle!=pending[0].handle);
    CHECK(!group->info(owner,pending[0].handle,&info)); CHECK(group->cancel(owner,out.handle));
    CHECK(FreeLibrary(dll)); HMODULE pinned=NULL;
    CHECK(GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,(LPCSTR)(uintptr_t)group,&pinned) && pinned==dll);
    CHECK(send(1,2,3,4,5,6)==122);
    CHECK(active_send(1,2,3,4,5,6)==1021 && active_receive(1,2,3,4)==2010);
    printf("property group: %ld checks passed; real HellForge chains, synthetic bodies only\n",checks);
    return 0;
}
