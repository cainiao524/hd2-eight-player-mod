/* Actual HellForge/MinHook, synthetic targets in this process only. */
#include "hellforge_modloader.c"
#include "roster_group_dll.h"
static LONG checks;
#define CHECK(x) do {InterlockedIncrement(&checks);if (!(x)) {fprintf(stderr,"FAIL %d: %s\n",__LINE__,#x);exit(1);}} while(0)
static const RosterGroupTestApi* group;
static HfApi api;static HfMod* owner;static uint64_t current;
typedef uint64_t (*Call)(void);
static Call targets[EP_ROSTER_ENTRIES];
static int hooks,fail_hook,fail_after,begin_ok=1,validate_ok=1,end_calls;
static SRWLOCK mutation=SRWLOCK_INIT;
static HANDLE entered,resume,commit_started;
static EpPropertyCommitGuard guard;
static void Routes(int active) {for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) CHECK(targets[i]()==i+1+(active ? 1000u : 0u));}
static int Hook(HfMod* mod,uintptr_t target,void* detour,void** next,int32_t priority)
{
    EpRosterGroupInfo info;hooks++;
    CHECK(group->info(owner,current,&info) && info.state==EP_GROUP_PUBLISHING && !info.active);
    CHECK(!group->cancel(owner,current) && !group->commit(owner,current,&guard));Routes(0);
    if (fail_hook==hooks && !fail_after) return 1;
    CHECK(ApiHookEx(mod,target,detour,next,priority)==0);Routes(0);
    return fail_hook==hooks ? 1 : 0;
}
static int Begin(void* unused,void** lease)
{
    (void)unused;if (!begin_ok) return 0;
    if (commit_started) SetEvent(commit_started);
    AcquireSRWLockExclusive(&mutation);*lease=&mutation;return 1;
}
static int Validate(void* unused,void* lease)
{
    (void)unused;EpRosterGroupInfo info;CHECK(lease==&mutation);
    CHECK(group->info(owner,current,&info) && info.state==EP_GROUP_COMMITTING && !info.active);
    CHECK(!group->cancel(owner,current) && !group->publish(owner,current,0) && !group->commit(owner,current,&guard));Routes(0);
    return validate_ok;
}
static void End(void* unused,void* lease,int committed)
{
    (void)unused;EpRosterGroupInfo info;end_calls++;CHECK(lease==&mutation);
    CHECK(group->info(owner,current,&info) && info.state==EP_GROUP_COMMITTING && info.active==(uint32_t)committed);
    CHECK(!group->cancel(owner,current) && !group->commit(owner,current,&guard));Routes(committed);ReleaseSRWLockExclusive(&mutation);
}
static EpRosterGroupBindings Targets(void)
{
    uint8_t* memory=VirtualAlloc(NULL,74727424,MEM_RESERVE,PAGE_NOACCESS);CHECK(memory!=NULL);
    EpRosterGroupBindings b={0};b.game_base=(uintptr_t)memory;
    b.roster_address=(uintptr_t)memory+0x8000000;b.storage_address=(uintptr_t)memory+0x10000000;
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {
        EpRosterGateLayout layout;CHECK(group->layout(i+1,&layout));
        uint8_t* at=memory+layout.original_rva;uint32_t value=i+1;
        CHECK(VirtualAlloc((void*)((uintptr_t)at&~4095ULL),4096,MEM_COMMIT,PAGE_READWRITE)!=NULL);memset(at,0x90,64);
        at[0]=0xB8;memcpy(at+1,&value,4);at[5]=0xC3;targets[i]=(Call)at;
        b.reject[i]=(uintptr_t)memory+0x20000000+i*0x10000;
    }
    for(unsigned i=0;i<EP_ROSTER_ENTRIES;i++) { DWORD old;CHECK(VirtualProtect((void*)((uintptr_t)targets[i]&~4095ULL),4096,PAGE_EXECUTE_READ,&old));CHECK(FlushInstructionCache(GetCurrentProcess(),(void*)targets[i],64)); }
    hooks=0;Routes(0);return b;
}
static void Tables(const EpRosterGroupInfo* info)
{
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {
        DWORD64 base;PRUNTIME_FUNCTION rf=RtlLookupFunctionEntry(info->code[i].base,&base,NULL);
        CHECK(rf && base==info->code[i].base && rf[0].BeginAddress==0 && rf[0].EndAddress==32);
        CHECK(RtlLookupFunctionEntry(base+32,&base,NULL)==rf+1);
        EpRosterGateLayout layout;CHECK(group->layout(i+1,&layout));
        for(unsigned row=2;row<layout.function_count;row++) CHECK(RtlLookupFunctionEntry(base+rf[row].BeginAddress,&base,NULL)==rf+row);
        const unsigned pcs[]={0,10,13,15,20,30,32};
        for (unsigned j=0;j<sizeof(pcs)/sizeof(*pcs);j++) {
            uint64_t stack[8]={0x12345678};CONTEXT c={0};c.ContextFlags=CONTEXT_FULL;c.Rsp=(uintptr_t)stack;c.Rip=base+pcs[j];
            c.Rbx=1;c.Rbp=2;c.Rsi=3;c.Rdi=4;c.R12=5;c.R13=6;c.R14=7;c.R15=8;
            PVOID handler=NULL;DWORD64 frame;PRUNTIME_FUNCTION row=RtlLookupFunctionEntry(c.Rip,&base,NULL);
            CHECK(row!=NULL);RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,c.Rip,row,&c,&handler,&frame,NULL);
            CHECK(c.Rsp==(uintptr_t)stack+8 && c.Rip==stack[0] && c.Rbx==1 && c.Rbp==2 && c.Rsi==3 && c.Rdi==4 && c.R12==5 && c.R13==6 && c.R14==7 && c.R15==8);
        }
    }
    /* Saved B54F23 call, relocated to candidate +0x18e, must bypass only the
     * companion's gate and stay inside this group's shared owner scope. */
    uintptr_t call=info->code[EP_ROSTER_REGISTRY_UPDATE-1].base+32+0x18e;
    int32_t displacement;CHECK(*(uint8_t*)call==0xe8);memcpy(&displacement,(void*)(call+1),4);
    CHECK(call+5+displacement==info->code[EP_ROSTER_ASSOCIATION-1].base+32);
}
static void BadTables(const EpRosterGroupInfo* info)
{
    const EpSessionCodeInfo* code=&info->code[11];uint8_t data[EP_ROSTER_GATED_MAX];
    DWORD64 base;PRUNTIME_FUNCTION rf=RtlLookupFunctionEntry(code->base,&base,NULL);uint32_t at=(uint32_t)((uintptr_t)rf-base);
    for (unsigned bad=0;bad<8;bad++) {
        memcpy(data,(void*)base,code->bytes);uint32_t* rows=(uint32_t*)(data+at);
        switch(bad) {
        case 0:rows[6]=rows[4]-1;break;
        case 1:rows[7]=rows[6];break;
        case 2:rows[8]=rows[5];break;
        case 3:rows[8]=rows[6];break;
        case 4:rows[8]++;break;
        case 5:data[rows[8]+2]=255;break;
        }
        EpSessionCodeInfo allocation;CHECK(group->reserve(&api,owner,0,code->bytes,&allocation));
        CHECK(!group->seal(owner,allocation.handle,data,code->bytes,at,bad==6 ? 2 : bad==7 ? 4 : 3));
        CHECK(group->discard(owner,allocation.handle));
    }
}
static DWORD WINAPI Commit(void* p) {(void)p;return group->commit(owner,current,&guard) ? 0 : 1;}
static DWORD WINAPI OldCall(void* p)
{(void)p;AcquireSRWLockShared(&mutation);Routes(0);SetEvent(entered);CHECK(WaitForSingleObject(resume,5000)==WAIT_OBJECT_0);Routes(0);ReleaseSRWLockShared(&mutation);return 0;}
static void* next_extra;
static uint64_t Extra(void) {return ((Call)next_extra)()+100;}
int main(int argc,char** argv)
{
    CHECK(argc==2 || argc==4);HMODULE dll=LoadLibraryA(argv[1]);CHECK(dll!=NULL);
    const RosterGroupTestApi* (*get)(void)=(const RosterGroupTestApi*(*)(void))GetProcAddress(dll,"roster_group_test_api");CHECK(get!=NULL);group=get();
    owner=&g_mods[0];strcpy(owner->id,"roster-test");strcpy(g_mods[1].id,"later-test");g_modCount=2;strcpy(g_build,"25480438");
    for(int i=0;i<2;i++){g_mods[i].loaded=1;g_mods[i].log=INVALID_HANDLE_VALUE;}
    api.version=13;api.size=sizeof(api);api.build_id=ApiBuildId;api.hook_ex=Hook;
    guard=(EpPropertyCommitGuard){NULL,Begin,Validate,End};
    EpRosterGroupBindings b=Targets(),invalid;EpRosterGroupInfo info,out;
    if(argc==4) {
        fail_hook=atoi(argv[2]);fail_after=atoi(argv[3]);CHECK(fail_hook>=1 && fail_hook<=EP_ROSTER_ENTRIES && (fail_after==0 || fail_after==1));
        CHECK(group->prepare(&api,owner,&b,&info));current=info.handle;
        CHECK(!group->publish(owner,current,10));CHECK(group->info(owner,current,&out) && out.state==EP_GROUP_FAILED && !out.active && out.published_attempts==(unsigned)fail_hook);
        CHECK(!group->commit(owner,current,&guard));CHECK(group->cancel(owner,current));
        CHECK(group->info(owner,current,&out) && out.state==EP_GROUP_CANCELLED && !out.active);Routes(0);
        CHECK(FreeLibrary(dll));Routes(0);
        printf("roster group: %ld checks passed; scenario %d %d\n",checks,fail_hook,fail_after);return 0;
    }
    CHECK(group->prepare(&api,owner,&b,&info));current=info.handle;Tables(&info);BadTables(&info);
    CHECK(!group->commit(owner,current,&guard));CHECK(!group->cancel(&g_mods[1],current));CHECK(group->cancel(owner,current));
    CHECK(!group->info(owner,current,&out));
    /* Every preparation step may fail after all entry reservations exist. */
    for(unsigned i=1;i<=EP_ROSTER_ENTRIES;i++) {
        group->failure(i,0);CHECK(!group->prepare(&api,owner,&b,&out) && !out.handle);
        group->failure(i,1);CHECK(!group->prepare(&api,owner,&b,&out) && out.handle && out.state==EP_GROUP_FAILED);
        CHECK(!group->cancel(owner,out.handle));group->failure(0,0);CHECK(group->cancel(owner,out.handle));
    }
    for(unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {
        invalid=b;invalid.reject[i]=b.storage_address+0x670;CHECK(!group->prepare(&api,owner,&invalid,&out) && !out.handle);
        EpRosterGateLayout layout;CHECK(group->layout(i+1,&layout));
        invalid=b;invalid.storage_address=(b.game_base+layout.original_rva)&~15ULL;CHECK(!group->prepare(&api,owner,&invalid,&out) && !out.handle);
    }
    void* hint=VirtualAlloc(NULL,65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);CHECK(hint && VirtualFree(hint,0,MEM_RELEASE));
    invalid=b;invalid.desired_code[11]=(uintptr_t)hint;invalid.reject[0]=(uintptr_t)hint+2815;
    CHECK(!group->prepare(&api,owner,&invalid,&out) && !out.handle);
    invalid=b;invalid.desired_code[11]=(uintptr_t)hint;invalid.reject[0]=(uintptr_t)hint+4095;
    CHECK(!group->prepare(&api,owner,&invalid,&out) && !out.handle);
    invalid=b;invalid.desired_code[0]=(uintptr_t)hint;invalid.storage_address=(uintptr_t)hint+0x400;
    CHECK(!group->prepare(&api,owner,&invalid,&out) && !out.handle);
    invalid=b;invalid.desired_code[0]=(uintptr_t)hint;invalid.roster_address=(uintptr_t)hint+0x400;
    CHECK(!group->prepare(&api,owner,&invalid,&out) && !out.handle);
    invalid=b;invalid.desired_code[3]=(uintptr_t)hint;invalid.desired_code[4]=(uintptr_t)hint;
    CHECK(!group->prepare(&api,owner,&invalid,&out) && !out.handle);
    CHECK(group->prepare(&api,owner,&b,&info));current=info.handle;CHECK(group->publish(owner,current,10));
    CHECK(group->info(owner,current,&out) && out.state==EP_GROUP_READY && !out.active && out.published_attempts==EP_ROSTER_ENTRIES);
    CHECK(!group->commit(owner,current,NULL));begin_ok=0;CHECK(!group->commit(owner,current,&guard) && !end_calls);
    begin_ok=1;validate_ok=0;CHECK(!group->commit(owner,current,&guard) && end_calls==1);Routes(0);validate_ok=1;
    entered=CreateEventA(NULL,TRUE,FALSE,NULL);resume=CreateEventA(NULL,TRUE,FALSE,NULL);commit_started=CreateEventA(NULL,TRUE,FALSE,NULL);
    CHECK(entered && resume && commit_started);HANDLE reader=CreateThread(NULL,0,OldCall,NULL,0,NULL);CHECK(reader!=NULL);
    CHECK(WaitForSingleObject(entered,5000)==WAIT_OBJECT_0);HANDLE worker=CreateThread(NULL,0,Commit,NULL,0,NULL);CHECK(worker!=NULL);
    CHECK(WaitForSingleObject(commit_started,5000)==WAIT_OBJECT_0);
    CHECK(group->info(owner,current,&out) && out.state==EP_GROUP_COMMITTING && !out.active);Routes(0);
    CHECK(!group->cancel(owner,current));SetEvent(resume);CHECK(WaitForSingleObject(reader,5000)==WAIT_OBJECT_0 && WaitForSingleObject(worker,5000)==WAIT_OBJECT_0);
    DWORD result;CHECK(GetExitCodeThread(worker,&result) && !result);CloseHandle(reader);CloseHandle(worker);CloseHandle(entered);CloseHandle(resume);CloseHandle(commit_started);commit_started=NULL;
    CHECK(group->info(owner,current,&out) && out.state==EP_GROUP_ACTIVE && out.active);Routes(1);CHECK(!group->cancel(owner,current));
    Call active[EP_ROSTER_ENTRIES];memcpy(active,targets,sizeof(active));
    b=Targets();CHECK(group->prepare(&api,owner,&b,&info));current=info.handle;CHECK(group->publish(owner,current,10));CHECK(group->cancel(owner,current));
    CHECK(ApiHookEx(&g_mods[1],(uintptr_t)targets[11],(void*)Extra,&next_extra,0)==0);CHECK(targets[11]()==112);
    EpRosterGroupInfo pending[EP_ROSTER_GROUP_SLOTS];unsigned filled=0;
    while(filled<EP_ROSTER_GROUP_SLOTS && group->prepare(&api,owner,&b,&pending[filled])) filled++;
    CHECK(filled==EP_ROSTER_GROUP_SLOTS-2);CHECK(!group->prepare(&api,owner,&b,&out) && !out.handle);
    for(unsigned i=0;i<filled;i++) CHECK(group->cancel(owner,pending[i].handle));
    CHECK(group->prepare(&api,owner,&b,&out) && out.handle!=pending[0].handle);CHECK(!group->info(owner,pending[0].handle,&info));CHECK(group->cancel(owner,out.handle));
    CHECK(FreeLibrary(dll));HMODULE pinned=NULL;CHECK(GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,(LPCSTR)(uintptr_t)group,&pinned) && pinned==dll);
    CHECK(targets[11]()==112);for(unsigned i=0;i<EP_ROSTER_ENTRIES;i++) CHECK(active[i]()==1001+i);
    printf("roster group: %ld checks passed; scenario 0 0\n",checks);return 0;
}
