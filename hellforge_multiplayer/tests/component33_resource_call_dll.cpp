/* Actual retained allocations and roster scope; callbacks use ONLY own test
 * memory. Generated game instructions are never executed natively. */
#include <windows.h>
#include <stdio.h>
#include "../mod/src/ep_native_roster.cpp"
#include "../mod/src/ep_roster_owner.cpp"
static unsigned allocations,frees;static bool fail_alloc;
static void* Alloc(HANDLE h,DWORD f,SIZE_T n) { ++allocations;return fail_alloc ? nullptr : HeapAlloc(h,f,n); }
static BOOL Free(HANDLE h,DWORD f,void* p) { ++frees;return HeapFree(h,f,p); }
#define HeapAlloc Alloc
#define HeapFree Free
#include "../mod/src/ep_component33_resource_call.cpp"
#undef HeapAlloc
#undef HeapFree
static unsigned checks,hooks;
static void Check(bool yes,const char* msg) { ++checks;if (!yes) { fprintf(stderr,"resource call check failed: %s\n",msg);ExitProcess(73); } }
static void W32(void* p,uint32_t x) { memcpy(p,&x,4); }
static void W64(void* p,uint64_t x) { memcpy(p,&x,8); }
static const char* Build(void) { return "25480438"; }
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) { ++hooks;return 1; }
static int Read(void*,uintptr_t,void*,size_t) { return 0; }
struct Test {
    HfMod* mod;uint64_t owner;EpC33StorageInfo storage;EpC33ResourceStorageInfo resources;
    EpNativeRosterView roster;EpC33AcquireSnapshot input;EpC33ResourceAcquireOps ops;
    EpC33ResourceCallResult result;unsigned collect,execute,mode;HANDLE entered,proceed;
};
static int Collect(void* opaque,const EpC33ResourceScopeView* v,EpC33AcquireSnapshot* out)
{
    auto* t=(Test*)opaque;++t->collect;Check(ep_roster_owner_in_scope(),"collect outside owner scope");
    Check(v->game==t->roster.game && v->storage==t->storage.storage_address,"wrong scope binding");
    if (t->mode==5) RaiseException(0xe00000c3,0,0,nullptr);
    if (t->mode==6) {
        EpC33ResourceCallResult r={};Check(ep_component33_resource_acquire_call(t->mod,t->storage.handle,t->owner,&t->ops,&r)==EP_C33_CALL_REENTRANT,"nested resource accepted");
    }
    if (t->mode==7) W32((void*)(uintptr_t)(v->resources.address+24),123);
    if (t->mode==8) return 0;
    if (t->mode==9) return 2;
    if (t->mode==2 || t->mode==12) { SetEvent(t->entered);Check(WaitForSingleObject(t->proceed,5000)==WAIT_OBJECT_0,"collect wait timeout"); }
    *out=t->input;return 1;
}
static int ExecuteTest(void* opaque,const EpC33ResourceScopeView* v,const EpC33AcquireSnapshot* s,const EpC33AcquireDemand* demand)
{
    auto* t=(Test*)opaque;++t->execute;Check(ep_roster_owner_in_scope(),"execute outside owner scope");
    Check(!memcmp(s,&t->input,sizeof(*s)),"execute snapshot drift");
    Check(demand->count==384,"incomplete six-group demand");
    Check(ep_c33_resource_validate(&v->resources,(void*)(uintptr_t)v->resources.address,t->resources.arena_bytes)==0,"invalid admitted arena");
    auto* table=(EpC33ResourceEntry*)(uintptr_t)(v->resources.address+48+v->resources.capacity*8);
    for (unsigned i=0;i<demand->count;i++) {
        EpC33ResourceEntry* found=nullptr;
        for (unsigned j=0;j<v->resources.capacity;j++) if (table[j].key==demand->keys[i]) { found=&table[j];break; }
        Check(found!=nullptr,"execute saw unadmitted demand");++found->references;
    }
    if (t->mode==3) { SetEvent(t->entered);Check(WaitForSingleObject(t->proceed,5000)==WAIT_OBJECT_0,"execute wait timeout"); }
    if (t->mode==4) RaiseException(0xe00000c3,0,0,nullptr);
    if (t->mode==10) return 0;
    if (t->mode==11) { EpC33ResourceCallResult r={};Check(ep_component33_resource_acquire_call(t->mod,t->storage.handle,t->owner,&t->ops,&r)==EP_C33_CALL_REENTRANT,"execute nested accepted"); }
    if (t->mode==19) W32((void*)(uintptr_t)(v->resources.address+8),0);
    return 1;
}
static void Setup(Test* t,unsigned mode)
{
    t->mod=(HfMod*)0x10001;t->mode=mode;t->entered=CreateEventA(nullptr,TRUE,FALSE,nullptr);t->proceed=CreateEventA(nullptr,TRUE,FALSE,nullptr);
    Check(t->entered && t->proceed,"events");
    EpC33Snapshot source={};source.component_address=source.global_component=0x200000000;source.invalid_entity_id=0xffffffff;
    W64(source.component+0x58,source.component_address+0x14);W32(source.component+0x60,8);W32(source.component+0x68,1);
    EpC33StorageBindings b={};b.game_base=0x180000000;b.reject_address=0x1a0000000;b.desired_storage=0x210000000;
    for (unsigned i=0;i<20;i++) b.desired_code[i]=0x190000000+i*0x10000;
    EpC33ResourceSnapshot resource={};resource.seed=1;
    if (mode==1) for (unsigned i=0;i<128;i++) resource.entries[i]={i+1,1};
    EpC33ResourceStorageConfig config={0x1b0000000,mode==1 ? 128u : 512u,0};
    HfApi api={};api.version=13;api.size=sizeof(api);api.build_id=Build;api.hook_ex=Hook;
    Check(ep_component33_storage_prepare_resources(&api,t->mod,&b,&source,&config,&resource,&t->storage)==EP_C33_STORAGE_OK,"prepare real resource owner");
    if (mode!=13) Check(ep_component33_storage_retain_resources(t->mod,t->storage.handle,&source,&resource)==EP_C33_STORAGE_OK,"retain real resource owner");
    Check(ep_component33_storage_resources(t->mod,t->storage.handle,&t->resources),"resource info");
    t->roster.game=b.game_base;t->roster.roster=0x240000000;t->roster.storage=0x241000000;t->roster.epoch=1;t->roster.build=25480438;
    if (mode==14) t->roster.game+=0x40000000;
    EpRosterMemory memory={nullptr,Read};Check(ep_roster_owner_create(t->mod,&t->roster,&memory,&t->owner)==EP_OWNER_OK,"create shared owner");
    for (unsigned g=0;g<6;g++) {
        uint8_t* group=t->input.package+g*0x808;W32(group+0x800,g+1);t->input.thresholds[g]=g*100;
        for (unsigned row=0;row<64;row++) {
            uint8_t* p=group+row*0x20;W64(p,mode==17 ? 999 : 999+g*64+row);W32(p+0x10,g*100);W32(p+0x14,g*100);
        }
    }
    if (mode==18) { EpRosterOwner* o=OwnerAcquire(t->mod,t->owner);Check(o!=nullptr,"revision access");o->revision=UINT64_MAX;OwnerRelease(o); }
    t->ops={t,Collect,ExecuteTest};
}
static DWORD WINAPI Run(LPVOID opaque)
{
    auto* t=(Test*)opaque;ep_component33_resource_acquire_call(t->mod,t->storage.handle,t->owner,&t->ops,&t->result);return 0;
}
struct Observer { Test* test;EpRosterOwnerInfo info;EpRosterOwnerResult status; };
static DWORD WINAPI Observe(LPVOID p) { auto* o=(Observer*)p;o->status=ep_roster_owner_info(o->test->mod,o->test->owner,&o->info);return 0; }
static DWORD WINAPI Close(LPVOID p) { auto* o=(Observer*)p;o->status=ep_roster_owner_close(o->test->mod,o->test->owner);return 0; }
static int Outer(void* p,const EpNativeRosterView*) { Run(p);return 1; }
static bool Pending(Test* t,bool closing)
{
    AcquireSRWLockExclusive(&epOwnersLock);EpRosterOwner* o=OwnerFind(t->mod,t->owner);
    bool ok=o && (closing ? bool(o->closing) : o->refs>=2);ReleaseSRWLockExclusive(&epOwnersLock);return ok;
}
#define EXPORT extern "C" __declspec(dllexport)
EXPORT int c33_acquire_demand(const EpC33AcquireSnapshot* s,EpC33AcquireDemand* out) { return ep_component33_acquire_demand(s,out); }
EXPORT unsigned c33_resource_call_test(unsigned mode)
{
    Test t={};Setup(&t,mode);auto* original=HeapAlloc(GetProcessHeap(),0,t.resources.arena_bytes);
    Check(original!=nullptr,"baseline");memcpy(original,(void*)(uintptr_t)t.resources.binding.address,t.resources.arena_bytes);
    if (mode==15) fail_alloc=true;
    if (mode==2 || mode==3 || mode==12) {
        HANDLE worker=CreateThread(nullptr,0,Run,&t,0,nullptr);Check(worker!=nullptr,"worker");
        Check(WaitForSingleObject(t.entered,5000)==WAIT_OBJECT_0,"callback entered");Observer observer={};observer.test=&t;
        HANDLE other=CreateThread(nullptr,0,mode==12 ? Close : Observe,&observer,0,nullptr);Check(other!=nullptr,"observer");
        ULONGLONG until=GetTickCount64()+5000;while (!Pending(&t,mode==12) && GetTickCount64()<until) Sleep(1);
        Check(Pending(&t,mode==12),"observer did not join exact owner");Check(WaitForSingleObject(other,0)==WAIT_TIMEOUT,"observer escaped whole call");
        SetEvent(t.proceed);Check(WaitForSingleObject(worker,5000)==WAIT_OBJECT_0 && WaitForSingleObject(other,5000)==WAIT_OBJECT_0,"scope failed to drain");
        Check(observer.status==EP_OWNER_OK,"observer failed");if (mode!=12) Check(observer.info.revision==2,"observer missed committed revision");
        CloseHandle(worker);CloseHandle(other);
    } else if (mode==16) Check(ep_roster_owner_call(t.mod,t.owner,1,Outer,&t)==EP_OWNER_OK,"nested in roster call");
    else Run(&t);
    bool success=mode==0 || mode==2 || mode==3 || mode==12 || mode==16 || mode==17;
    bool fault=mode==4 || mode==5 || mode==6 || mode==7 || mode==10 || mode==11 || mode==18 || mode==19;
    bool executed=success || mode==4 || mode==10 || mode==11 || mode==19;
    Check(t.result.executed==unsigned(executed) && t.execute==unsigned(executed),"unexpected side effect callback");
    Check((t.result.status==EP_C33_CALL_OK)==(success || mode==9),"operation result");
    Check(t.result.owner_result==(fault ? (mode==4 || mode==5 ? EP_OWNER_CALLBACK_FAULT : mode==18 ? EP_OWNER_EXHAUSTED : EP_OWNER_CALLBACK_FAILED) : EP_OWNER_OK),"owner result");
    if (mode==1) Check(t.result.status==EP_C33_CALL_CAPACITY && t.result.demand_count==384,"capacity refused before effect");
    if (mode==8) Check(t.result.status==EP_C33_CALL_SNAPSHOT,"snapshot unavailable");
    if (mode==13 || mode==14) Check(t.result.status==EP_C33_CALL_STORAGE && !t.collect,"bad binding/prepared call");
    if (mode==15) Check(t.result.status==EP_C33_CALL_MEMORY && !t.collect,"allocation refusal");
    if (!executed && mode!=7) Check(!memcmp(original,(void*)(uintptr_t)t.resources.binding.address,t.resources.arena_bytes),"refusal changed arena");
    Check(allocations==(mode==13 ? 0u : 1u) && frees==allocations-(mode==15 ? 1u : 0u),"scratch lifetime after failure/SEH");
    Check(!ep_roster_owner_in_scope() && !resourceCall,"TLS scope leaked");Check(hooks==0,"hook installation attempted");
    if (mode!=12) {
        EpRosterOwnerInfo info={};auto result=ep_roster_owner_info(t.mod,t.owner,&info);Check(result==EP_OWNER_OK,"owner info");
        Check(bool(info.fault)==fault,"quarantine state");Check(info.revision==(mode==18 ? UINT64_MAX : success ? 2u : 1u),"revision changed on refusal or fault");
        if (fault) { auto old=t.collect;Run(&t);Check(t.result.owner_result==EP_OWNER_FAULTED && t.collect==old,"quarantined owner invoked provider"); }
        Check(ep_roster_owner_close(t.mod,t.owner)==EP_OWNER_OK,"close after operation");
    }
    if (mode==0) {
        EpRosterMemory memory={nullptr,Read};Check(ep_roster_owner_create(t.mod,&t.roster,&memory,&t.owner)==EP_OWNER_OK,"recreate owner");
        auto old=t.collect;Run(&t);Check(t.result.status==EP_C33_CALL_STORAGE && t.collect==old,"new owner reused permanent resource binding");
        Check(ep_roster_owner_close(t.mod,t.owner)==EP_OWNER_OK,"close replacement owner");
    }
    if (mode==13) Check(ep_component33_storage_cancel(t.mod,t.storage.handle),"prepared cleanup");
    HeapFree(GetProcessHeap(),0,original);CloseHandle(t.entered);CloseHandle(t.proceed);return checks;
}
