/* Real patched HellForge/MinHook, real owner and bridges, own targets only. */
#include "hellforge_modloader.c"
#include "roster_call_dll.h"
#include "roster_call_abi.h"
static LONG checks,bodies,failures,memory_reads;
#define CHECK(x) do {InterlockedIncrement(&checks);if(!(x)){fprintf(stderr,"FAIL %d: %s\n",__LINE__,#x);exit(1);}} while(0)
typedef uint64_t (*Call)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
typedef double (*FloatCall)(double,double,double,double);
static const RosterCallTestApi* test;
static HfApi api;static HfMod* mod;static uint64_t storage,current,other_storage;
static Call targets[EP_ROSTER_ENTRIES];static int installed[EP_ROSTER_ENTRIES],hooks,fail_hook,fail_after;
static unsigned fault_kind,nested_kind;static int block_leaf,block_commit,validate_ok=1,end_fault,validate_fault,recursive;
static int expected_owned_end=1;
static HANDLE leaf_enter,leaf_resume,commit_enter,validate_enter,validate_resume,end_enter,end_resume;
static EpPropertyCommitGuard guard;static EpNativeRosterView view;static EpRosterOwnerResult last_failure;
static uint64_t Number(unsigned kind,int active)
{return kind+(active?1000:0)+11+3*23+5*37+7*53+(kind==1?11*71+13*97:0);}
static uint64_t Failed(unsigned kind) {return UINT64_C(0xEE000000)+kind;}
static uint64_t StateValue(int active,unsigned i)
{return UINT64_C(0x1111000011110001)*(i+1)+(active?UINT64_C(0x8000000000000000):0);}
static void Failure(void* unused,uint32_t kind,EpRosterOwnerResult result,EpRosterCallFrame* frame)
{
    (void)unused;InterlockedIncrement(&failures);last_failure=result;frame->rax=Failed(kind);
    if(kind==3){double value=-99.5;memcpy(frame->xmm[0],&value,8);}
}
static uint64_t Body(unsigned kind,int active,uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f)
{
    InterlockedIncrement(&bodies);EpRosterOwnerInfo info;
    if(installed[kind-1]) CHECK(test->owner_info(mod,storage,&info)==EP_OWNER_REENTRANT);
    if(block_leaf==(int)kind){SetEvent(leaf_enter);CHECK(WaitForSingleObject(leaf_resume,5000)==WAIT_OBJECT_0);}
    if(fault_kind==kind) RaiseException(0xE0422001,0,0,NULL);
    if(nested_kind==kind){
        if(recursive) targets[kind-1](a,b,c,d,e,f);
        else if(kind==EP_ROSTER_DEPARTURE){
            CHECK(((FloatCall)targets[EP_ROSTER_GETTER-1])(1.25,2.5,4.75,8.0)==88.5+(active?1000:0));
            CHECK(targets[EP_ROSTER_REMOVE_LEGACY-1](a,b,c,d,71,97)==(fault_kind==EP_ROSTER_REMOVE_LEGACY?Failed(EP_ROSTER_REMOVE_LEGACY):Number(EP_ROSTER_REMOVE_LEGACY,active)));
            if(!fault_kind)CHECK(targets[EP_ROSTER_REMOVE_REGISTERED-1](a,b,c,d,71,97)==Number(EP_ROSTER_REMOVE_REGISTERED,active));
        }
        else {targets[0](a,b,c,d,71,97);((FloatCall)targets[2])(1.25,2.5,4.75,8.0);}
    }
    return kind+(active?1000:0)+a+3*b+5*c+7*d+(kind==1?11*e+13*f:0);
}
#define FUNCTIONS(n) static uint64_t Old##n(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f){return Body(n,0,a,b,c,d,n==1?e:0,n==1?f:0);} \
static uint64_t New##n(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f){return Body(n,1,a,b,c,d,n==1?e:0,n==1?f:0);}
FUNCTIONS(1) FUNCTIONS(2) FUNCTIONS(5) FUNCTIONS(6) FUNCTIONS(7) FUNCTIONS(8) FUNCTIONS(9) FUNCTIONS(10) FUNCTIONS(11) FUNCTIONS(12) FUNCTIONS(13) FUNCTIONS(14)
#undef FUNCTIONS
/* Own four-register tail targets. This exercises bridge lifetime across a real
 * indirect tail; it makes no claim about the unresolved game's tail target. */
typedef uint64_t (*TailCall)(uint64_t,uint64_t,uint64_t,uint64_t);
static uint64_t TailOld15(uint64_t a,uint64_t b,uint64_t c,uint64_t d){return Body(EP_ROSTER_DEPARTURE,0,a,b,c,d,0,0);}
static uint64_t TailNew15(uint64_t a,uint64_t b,uint64_t c,uint64_t d){return Body(EP_ROSTER_DEPARTURE,1,a,b,c,d,0,0);}
__attribute__((used)) static TailCall DepartureOldTail=TailOld15,DepartureNewTail=TailNew15;
__attribute__((naked,noinline)) static uint64_t Old15(uint64_t a,uint64_t b,uint64_t c,uint64_t d){__asm__("jmp *DepartureOldTail(%rip)");}
__attribute__((naked,noinline)) static uint64_t New15(uint64_t a,uint64_t b,uint64_t c,uint64_t d){__asm__("jmp *DepartureNewTail(%rip)");}
static double FloatBody(int active,double a,double b,double c,double d)
{
    InterlockedIncrement(&bodies);EpRosterOwnerInfo info;
    if(installed[2])CHECK(test->owner_info(mod,storage,&info)==EP_OWNER_REENTRANT);
    return a+3*b+5*c+7*d+(active?1000:0);
}
static double Old3(double a,double b,double c,double d){return FloatBody(0,a,b,c,d);}
static double New3(double a,double b,double c,double d){return FloatBody(1,a,b,c,d);}
static int Memory(void* unused,uintptr_t address,void* out,size_t n)
{(void)unused;(void)address;(void)out;(void)n;InterlockedIncrement(&memory_reads);return 0;}
static void Routes(int active,int stale)
{
    for(unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {
        int denied=stale && installed[i];
        if(i==2)CHECK(((FloatCall)targets[i])(1.25,2.5,4.75,8.0)==(denied?-99.5:88.5+(active?1000:0)));
        else CHECK(targets[i](11,23,37,53,71,97)==(denied?Failed(i+1):i==3?StateValue(active,0):Number(i+1,active)));
    }
}
static int Hook(HfMod* owner,uintptr_t target,void* detour,void** next,int32_t priority)
{
    hooks++;if(hooks==fail_hook && !fail_after)return 1;
    CHECK(ApiHookEx(owner,target,detour,next,priority)==0);installed[hooks-1]=1;
    return hooks==fail_hook ? 1:0;
}
static int Begin(void* unused,void** lease)
{(void)unused;if(commit_enter)SetEvent(commit_enter);*lease=&guard;return 1;}
static int Validate(void* unused,void* lease)
{
    (void)unused;CHECK(lease==&guard);EpRosterOwnerInfo info;EpRosterGroupInfo group;
    CHECK(test->owner_info(mod,storage,&info)==EP_OWNER_REENTRANT);
    CHECK(test->info(mod,current,&group) && group.state==EP_GROUP_COMMITTING && !group.active);
    if(block_commit){SetEvent(validate_enter);CHECK(WaitForSingleObject(validate_resume,5000)==WAIT_OBJECT_0);}
    if(validate_fault)RaiseException(0xE0422002,0,0,NULL);return validate_ok;
}
static void End(void* unused,void* lease,int committed)
{
    (void)unused;CHECK(lease==&guard);EpRosterGroupInfo group;
    CHECK(test->info(mod,current,&group) && group.active==(unsigned)committed);
    EpRosterOwnerInfo owner_info;CHECK(test->owner_info(mod,storage,&owner_info)==(expected_owned_end?EP_OWNER_REENTRANT:EP_OWNER_UNAVAILABLE));
    if(block_commit){SetEvent(end_enter);CHECK(WaitForSingleObject(end_resume,5000)==WAIT_OBJECT_0);}
    if(end_fault)RaiseException(0xE0422003,0,0,NULL);
}
static EpRosterGroupBindings Targets(void)
{
    uint8_t* memory=VirtualAlloc(NULL,74727424,MEM_RESERVE,PAGE_NOACCESS);CHECK(memory!=NULL);
    EpRosterGroupBindings b={0};b.game_base=(uintptr_t)memory;
    b.roster_address=(uintptr_t)memory+0x8000000;b.storage_address=(uintptr_t)memory+0x10000000;
    const uintptr_t old[EP_ROSTER_ENTRIES]={(uintptr_t)Old1,(uintptr_t)Old2,(uintptr_t)Old3,(uintptr_t)StateOld,(uintptr_t)Old5,(uintptr_t)Old6,(uintptr_t)Old7,(uintptr_t)Old8,(uintptr_t)Old9,(uintptr_t)Old10,(uintptr_t)Old11,(uintptr_t)Old12,(uintptr_t)Old13,(uintptr_t)Old14,(uintptr_t)Old15};
    const uintptr_t next[EP_ROSTER_ENTRIES]={(uintptr_t)New1,(uintptr_t)New2,(uintptr_t)New3,(uintptr_t)StateNew,(uintptr_t)New5,(uintptr_t)New6,(uintptr_t)New7,(uintptr_t)New8,(uintptr_t)New9,(uintptr_t)New10,(uintptr_t)New11,(uintptr_t)New12,(uintptr_t)New13,(uintptr_t)New14,(uintptr_t)New15};
    test->targets(next);
    for(unsigned i=0;i<EP_ROSTER_ENTRIES;i++){
        EpRosterGateLayout layout;CHECK(test->layout(i+1,&layout));uint8_t* at=memory+layout.original_rva;
        CHECK(VirtualAlloc((void*)((uintptr_t)at&~4095ULL),4096,MEM_COMMIT,PAGE_READWRITE)!=NULL);memset(at,0x90,64);
        const uint8_t jump[]={0xFF,0x25,0,0,0,0};memcpy(at,jump,6);memcpy(at+6,&old[i],8);targets[i]=(Call)at;
        b.reject[i]=(uintptr_t)memory+0x20000000+i*0x10000;
    }
    for(unsigned i=0;i<EP_ROSTER_ENTRIES;i++) { DWORD old;CHECK(VirtualProtect((void*)((uintptr_t)targets[i]&~4095ULL),4096,PAGE_EXECUTE_READ,&old));CHECK(FlushInstructionCache(GetCurrentProcess(),(void*)targets[i],64)); }return b;
}
static void Pending(unsigned expected,int closing)
{
    ULONGLONG until=GetTickCount64()+5000;uint32_t refs;int actual;
    do {refs=test->pending(mod,storage,&actual);if(refs==expected && actual==closing)break;Sleep(1);}while(GetTickCount64()<until);
    CHECK(refs==expected && actual==closing);
}
static HANDLE Event(void){HANDLE event=CreateEventA(NULL,TRUE,FALSE,NULL);CHECK(event!=NULL);return event;}
static DWORD WINAPI Commit(void* unused){(void)unused;return test->commit(mod,current,&guard)?0:1;}
static DWORD WINAPI Leaf(void* kind){unsigned n=(unsigned)(uintptr_t)kind;CHECK(targets[n-1](11,23,37,53,71,97)==Number(n,0));return 0;}
static DWORD WINAPI Snapshot(void* unused)
{(void)unused;EpHfRosterSnapshot snapshot;CHECK(test->snapshot(mod,storage,view.game,&snapshot)==EP_NATIVE_READ_FAILED);return 0;}
static DWORD WINAPI Close(void* unused){(void)unused;CHECK(test->close(mod,storage)==EP_OWNER_OK);return 0;}
static DWORD WINAPI Queued(void* unused){(void)unused;CHECK(targets[3](11,23,37,53,71,97)==Failed(4));return 0;}
static void Join(HANDLE thread){DWORD result;CHECK(WaitForSingleObject(thread,5000)==WAIT_OBJECT_0);CHECK(GetExitCodeThread(thread,&result) && !result);CloseHandle(thread);}
static void HardwareAbi(int active)
{
    uint64_t out[30]={0};CallNonvolatile((uintptr_t)targets[3],out);CHECK(out[0]==StateValue(active,0));
    for(unsigned i=0;i<8;i++)CHECK(out[i+1]==4096+i);
    for(unsigned i=10;i<30;i++)CHECK(out[i]==8192);
    EpRosterCallFrame frame={0};
    /* A non-producer must not read an original fifth/sixth argument. */
    void* forbidden=VirtualAlloc(NULL,4096,MEM_RESERVE|MEM_COMMIT,PAGE_NOACCESS);CHECK(forbidden!=NULL);frame.entry_stack=(uintptr_t)forbidden;
    test->invoke(&frame,(uintptr_t)targets[3],0);uint64_t* gpr=&frame.rax;
    for(unsigned i=0;i<7;i++)CHECK(gpr[i]==StateValue(active,i));
    for(unsigned i=0;i<6;i++){uint64_t pair[2];memcpy(pair,frame.xmm[i],16);CHECK(pair[0]==gpr[i] && pair[1]==gpr[i]);}
    CHECK(VirtualFree(forbidden,0,MEM_RELEASE));
    const uint64_t a=UINT64_C(0x123456789abcdef0),b=UINT64_C(0xfedcba9876543210),c=UINT64_C(0x8123456765432100),
        d=UINT64_C(0x70fff11133355577),e=UINT64_C(0xabcdef1234567890),f=UINT64_C(0x9977553311224466);
    CHECK(targets[0](a,b,c,d,e,f)==1+(active?1000:0)+a+3*b+5*c+7*d+11*e+13*f);
}
static void Unwind(const char* dll)
{
    char path[1024];CHECK(strlen(dll)+16<sizeof(path));strcpy(path,dll);strcpy(path+strlen(path)-4,".unwind.bin");
    FILE* input=fopen(path,"rb");CHECK(input!=NULL);char magic[8];uint32_t functions;
    CHECK(fread(magic,8,1,input)==1 && !memcmp(magic,"EPBRUW1\0",8));CHECK(fread(&functions,4,1,input)==1 && functions==2);
    for(unsigned function=0;function<2;function++){
        uint32_t header[3];uint8_t code[4096];CHECK(fread(header,sizeof(header),1,input)==1 && header[0]==function && header[1]<sizeof(code) && header[2]<512);
        uintptr_t address=function?(uintptr_t)test->invoke:test->entry();DWORD64 base;PRUNTIME_FUNCTION rf=RtlLookupFunctionEntry(address,&base,NULL);
        CHECK(rf && base+rf->BeginAddress==address && rf->EndAddress-rf->BeginAddress==header[1]);
        CHECK(fread(code,header[1],1,input)==1 && !memcmp(code,(void*)address,header[1]));
        for(unsigned i=0;i<header[2];i++){
            struct {uint32_t offset;int32_t delta;uint32_t rbx_frame;} row;
            CHECK(fread(&row,sizeof(row),1,input)==1 && row.offset<header[1] && row.delta>=-216 && row.delta<=0);
            uint64_t stack[512]={0};uint64_t* entry=stack+481;*entry=0x12345678;entry[-1]=1;
            CONTEXT context={0};context.ContextFlags=CONTEXT_FULL;context.Rip=address+row.offset;context.Rsp=(uintptr_t)entry+row.delta;
            context.Rbx=row.rbx_frame?0xBAD0:1;context.Rbp=2;context.Rsi=3;context.Rdi=4;context.R12=5;context.R13=6;context.R14=7;context.R15=8;
            M128A* xmm=&context.Xmm0;for(unsigned j=6;j<16;j++){xmm[j].Low=0x1000+j;xmm[j].High=0x2000+j;}
            PVOID handler=NULL;DWORD64 frame;RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,rf,&context,&handler,&frame,NULL);
            CHECK(context.Rsp==(uintptr_t)(entry+1) && context.Rip==*entry);
            CHECK(context.Rbx==1 && context.Rbp==2 && context.Rsi==3 && context.Rdi==4 && context.R12==5 && context.R13==6 && context.R14==7 && context.R15==8);
            for(unsigned j=6;j<16;j++)CHECK(xmm[j].Low==0x1000+j && xmm[j].High==0x2000+j);
        }
    }
    CHECK(fgetc(input)==EOF);fclose(input);
}
static int Unexpected(void* unused,const EpNativeRosterView* v) {(void)unused;(void)v;CHECK(0);return 1;}
static int Scope(void* unused,const EpNativeRosterView* v)
{
    (void)unused;EpHfRosterSnapshot snapshot;CHECK(v->game==view.game);
    CHECK(test->snapshot(mod,storage,view.game,&snapshot)==EP_NATIVE_UNAVAILABLE);
    CHECK(test->close(mod,storage)==EP_OWNER_REENTRANT);
    CHECK(!test->commit(mod,current,&guard));
    CHECK(test->call(mod,other_storage,0,Unexpected,NULL)==EP_OWNER_REENTRANT);
    CHECK(test->call(&g_mods[1],storage,0,Unexpected,NULL)==EP_OWNER_REENTRANT);
    CHECK(targets[0](11,23,37,53,71,97)==Number(1,0));return 1;
}
static void NestedDeparture(int active)
{
    EpRosterOwnerInfo before,after;CHECK(test->owner_info(mod,storage,&before)==EP_OWNER_OK);
    nested_kind=EP_ROSTER_DEPARTURE;
    CHECK(targets[EP_ROSTER_DEPARTURE-1](11,23,37,53,71,97)==Number(EP_ROSTER_DEPARTURE,active));nested_kind=0;
    CHECK(test->owner_info(mod,storage,&after)==EP_OWNER_OK && after.revision==before.revision+1 && !after.fault);
}
static void Race(unsigned kind)
{
    block_leaf=kind;block_commit=1;leaf_enter=Event();leaf_resume=Event();commit_enter=Event();
    validate_enter=Event();validate_resume=Event();end_enter=Event();end_resume=Event();
    HANDLE leaf=CreateThread(NULL,0,Leaf,(void*)(uintptr_t)kind,0,NULL);CHECK(leaf!=NULL);CHECK(WaitForSingleObject(leaf_enter,5000)==WAIT_OBJECT_0);
    HANDLE commit=CreateThread(NULL,0,Commit,NULL,0,NULL);CHECK(commit!=NULL);CHECK(WaitForSingleObject(commit_enter,5000)==WAIT_OBJECT_0);Pending(2,0);
    CHECK(WaitForSingleObject(validate_enter,0)==WAIT_TIMEOUT);SetEvent(leaf_resume);Join(leaf);
    CHECK(WaitForSingleObject(validate_enter,5000)==WAIT_OBJECT_0);LONG before=memory_reads;
    HANDLE snapshot=CreateThread(NULL,0,Snapshot,NULL,0,NULL);CHECK(snapshot!=NULL);Pending(2,0);
    CHECK(WaitForSingleObject(snapshot,20)==WAIT_TIMEOUT && memory_reads==before);
    SetEvent(validate_resume);CHECK(WaitForSingleObject(end_enter,5000)==WAIT_OBJECT_0);
    CHECK(WaitForSingleObject(snapshot,20)==WAIT_TIMEOUT && memory_reads==before);
    SetEvent(end_resume);Join(commit);Join(snapshot);CHECK(memory_reads==before+1);
    CloseHandle(leaf_enter);CloseHandle(leaf_resume);CloseHandle(commit_enter);CloseHandle(validate_enter);CloseHandle(validate_resume);CloseHandle(end_enter);CloseHandle(end_resume);
    block_leaf=block_commit=0;commit_enter=NULL;
}
int main(int argc,char** argv)
{
    CHECK(argc>=2 && argc<=4);HMODULE dll=LoadLibraryA(argv[1]);CHECK(dll!=NULL);
    const RosterCallTestApi* (*get)(void)=(const RosterCallTestApi*(*)(void))GetProcAddress(dll,"roster_call_test_api");CHECK(get!=NULL);test=get();
    const char* mode=argc==3?argv[2]:"normal";
    if(argc!=4 && !strcmp(mode,"normal"))Unwind(argv[1]);
    mod=&g_mods[0];strcpy(mod->id,"owned-roster-test");mod->loaded=1;mod->log=INVALID_HANDLE_VALUE;g_modCount=1;strcpy(g_build,"25480438");
    api.version=13;api.size=sizeof(api);api.build_id=ApiBuildId;api.hook_ex=Hook;
    guard=(EpPropertyCommitGuard){NULL,Begin,Validate,End};EpRosterGroupBindings b=Targets();Routes(0,0);
    view.game=b.game_base;view.roster=b.roster_address;view.storage=b.storage_address;view.epoch=7;view.build=25480438;
    EpRosterMemory memory={NULL,Memory};CHECK(test->create(mod,&view,&memory,&storage)==EP_OWNER_OK);
    EpRosterCallPolicy policy={Failure,NULL};EpRosterGroupInfo group;EpRosterOwnerInfo info,before;
    CHECK(!test->prepare(&api,mod,&b,storage,NULL,&group));EpRosterGroupBindings wrong=b;wrong.storage_address+=0x1000;
    CHECK(!test->prepare(&api,mod,&wrong,storage,&policy,&group));CHECK(!hooks);
    CHECK(test->prepare(&api,mod,&b,storage,&policy,&group) && group.storage_owner==storage);current=group.handle;
    if(argc==4){
        fail_hook=atoi(argv[2]);fail_after=atoi(argv[3]);CHECK(!test->publish(mod,current,10));
        CHECK(test->info(mod,current,&group) && group.state==EP_GROUP_FAILED && !group.active && group.published_attempts==(unsigned)fail_hook);
        CHECK(!test->commit(mod,current,&guard));CHECK(test->cancel(mod,current));Routes(0,0);
        CHECK(test->close(mod,storage)==EP_OWNER_OK);Routes(0,1);CHECK(FreeLibrary(dll));Routes(0,1);
        printf("roster calls: %ld checks passed; scenario %d %d\n",checks,fail_hook,fail_after);return 0;
    }
    CHECK(test->publish(mod,current,10));Routes(0,0);HardwareAbi(0);
    EpNativeRosterView other=view;other.game+=UINT64_C(0x100000000);other.roster+=UINT64_C(0x100000000);other.storage+=UINT64_C(0x100000000);
    CHECK(test->create(mod,&other,&memory,&other_storage)==EP_OWNER_OK);
    CHECK(test->owner_info(mod,storage,&before)==EP_OWNER_OK);
    CHECK(test->call(mod,storage,0,Scope,NULL)==EP_OWNER_OK);
    CHECK(test->owner_info(mod,storage,&info)==EP_OWNER_OK && info.revision==before.revision+1);
    CHECK(test->close(mod,other_storage)==EP_OWNER_OK);
    NestedDeparture(0);
    nested_kind=11;CHECK(test->owner_info(mod,storage,&before)==EP_OWNER_OK);
    CHECK(targets[10](11,23,37,53,71,97)==Number(11,0));nested_kind=0;
    CHECK(test->owner_info(mod,storage,&info)==EP_OWNER_OK && info.revision==before.revision+1);
    if(!strcmp(mode,"unavailable")){
        CHECK(test->close(mod,storage)==EP_OWNER_OK);expected_owned_end=0;CHECK(!test->commit(mod,current,&guard));
        CHECK(test->info(mod,current,&group) && !group.active && group.state==EP_GROUP_READY);Routes(0,1);
    }else if(!strcmp(mode,"close") || !strcmp(mode,"departureclose")){
        unsigned close_kind=!strcmp(mode,"departureclose")?EP_ROSTER_DEPARTURE:2;block_leaf=close_kind;leaf_enter=Event();leaf_resume=Event();HANDLE leaf=CreateThread(NULL,0,Leaf,(void*)(uintptr_t)close_kind,0,NULL);CHECK(leaf!=NULL);
        CHECK(WaitForSingleObject(leaf_enter,5000)==WAIT_OBJECT_0);HANDLE queued=CreateThread(NULL,0,Queued,NULL,0,NULL);CHECK(queued!=NULL);Pending(2,0);
        HANDLE close=CreateThread(NULL,0,Close,NULL,0,NULL);CHECK(close!=NULL);Pending(2,1);CHECK(WaitForSingleObject(close,20)==WAIT_TIMEOUT);
        SetEvent(leaf_resume);Join(leaf);Join(queued);Join(close);block_leaf=0;CloseHandle(leaf_enter);CloseHandle(leaf_resume);Routes(0,1);
        uint64_t next;CHECK(test->create(mod,&view,&memory,&next)==EP_OWNER_OK && next!=storage);Routes(0,1);CHECK(test->close(mod,next)==EP_OWNER_OK);
    }else{
        validate_ok=0;CHECK(!test->commit(mod,current,&guard));CHECK(test->info(mod,current,&group) && !group.active && group.state==EP_GROUP_READY);Routes(0,0);validate_ok=1;
        if(!strcmp(mode,"validatefault") || !strcmp(mode,"endfault")){
            validate_fault=!strcmp(mode,"validatefault");end_fault=!strcmp(mode,"endfault");CHECK(!test->commit(mod,current,&guard));
            CHECK(test->info(mod,current,&group) && group.active==(unsigned)end_fault && group.state==(uint32_t)(end_fault?EP_GROUP_ACTIVE:EP_GROUP_READY));
            if(end_fault)CHECK(!test->cancel(mod,current));
        }else{
            if(!strcmp(mode,"normal") || !strcmp(mode,"departurerace"))Race(!strcmp(mode,"departurerace")?EP_ROSTER_DEPARTURE:2);else CHECK(test->commit(mod,current,&guard));Routes(1,0);HardwareAbi(1);NestedDeparture(1);
            CHECK(test->info(mod,current,&group) && group.active && group.state==EP_GROUP_ACTIVE);
            CHECK(!test->cancel(mod,current));CHECK(test->owner_info(mod,storage,&before)==EP_OWNER_OK);
            if(!strcmp(mode,"exhausted")){
                test->revision(mod,storage,UINT64_MAX);LONG count=bodies;
                CHECK(targets[0](11,23,37,53,71,97)==Failed(1) && last_failure==EP_OWNER_EXHAUSTED && bodies==count);
                CHECK(((FloatCall)targets[2])(1.25,2.5,4.75,8.0)==1088.5);
                CHECK(targets[EP_ROSTER_ASSOCIATION-1](11,23,37,53,71,97)==Number(EP_ROSTER_ASSOCIATION,1));
                CHECK(test->owner_info(mod,storage,&info)==EP_OWNER_OK && info.revision==UINT64_MAX && !info.fault);
            }else{
                if(!strcmp(mode,"nestedfault")){nested_kind=11;fault_kind=1;}
                else if(!strcmp(mode,"departurefault")){nested_kind=EP_ROSTER_DEPARTURE;fault_kind=EP_ROSTER_REMOVE_LEGACY;}
                else if(!strcmp(mode,"depth")){nested_kind=11;recursive=1;}
                else fault_kind=6;
                unsigned kind=nested_kind?nested_kind:6;CHECK(targets[kind-1](11,23,37,53,71,97)==Failed(kind));nested_kind=fault_kind=0;recursive=0;
                CHECK(test->owner_info(mod,storage,&info)==EP_OWNER_OK && info.fault==(uint32_t)(!strcmp(mode,"depth")?EP_OWNER_REENTRANT:EP_OWNER_CALLBACK_FAULT) && info.revision==before.revision);
            }
        }
        if(strcmp(mode,"exhausted")){LONG count=bodies;Routes(1,1);CHECK(bodies==count);}
        CHECK(test->close(mod,storage)==EP_OWNER_OK);Routes(1,1);
    }
    CHECK(FreeLibrary(dll));Routes(1,1);
    printf("roster calls: %ld checks passed; mode %s\n",checks,mode);return 0;
}
