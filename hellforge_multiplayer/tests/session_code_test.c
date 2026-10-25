/* Actual pinned HellForge hooks.c/MinHook; ONLY synthetic functions in this
 * test process. Never loader_start/Watch or any installed game/module lookup. */
#include "hellforge_modloader.c"
static volatile LONG checks, hookCalls;
#define CHECK(x) do { InterlockedIncrement(&checks); if (!(x)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
static int failProtect, failFlush, failAdd, failDelete, failFree;
static BOOL TestProtect(LPVOID p,SIZE_T n,DWORD flags,PDWORD old)
{ return failProtect ? FALSE : VirtualProtect(p,n,flags,old); }
static BOOL TestFlush(HANDLE p,LPCVOID at,SIZE_T n)
{ return failFlush ? FALSE : FlushInstructionCache(p,at,n); }
static BOOLEAN TestAdd(PRUNTIME_FUNCTION f,DWORD n,DWORD64 base)
{ return failAdd ? FALSE : RtlAddFunctionTable(f,n,base); }
static BOOLEAN TestDelete(PRUNTIME_FUNCTION f)
{ return failDelete ? FALSE : RtlDeleteFunctionTable(f); }
static BOOL TestFree(LPVOID p,SIZE_T n,DWORD flags)
{ return failFree ? FALSE : VirtualFree(p,n,flags); }
#define VirtualProtect TestProtect
#define FlushInstructionCache TestFlush
#define RtlAddFunctionTable TestAdd
#define RtlDeleteFunctionTable TestDelete
#define VirtualFree TestFree
#include "../mod/src/ep_session_code.cpp"
#undef VirtualProtect
#undef FlushInstructionCache
#undef RtlAddFunctionTable
#undef RtlDeleteFunctionTable
#undef VirtualFree
#include "session_code_dll.h"

static HfApi api;
static uint64_t activeHandle;
static int hookMode;
static HANDLE hookEntered, hookContinue;
static uintptr_t target;
static const SessionCodeTestApi localCode={ep_session_code_reserve,ep_session_code_seal,
    ep_session_code_info,ep_session_code_publish,ep_session_code_discard};
static const SessionCodeTestApi* activeCode=&localCode;
static PRUNTIME_FUNCTION Lookup(uintptr_t pc)
{ DWORD64 base=0; return RtlLookupFunctionEntry(pc,&base,NULL); }
static int HookChecked(HfMod* mod,uintptr_t at,void* detour,void** next,int32_t priority)
{
    EpSessionCodeInfo info; MEMORY_BASIC_INFORMATION mbi;
    InterlockedIncrement(&hookCalls);
    CHECK(activeCode->info(mod,activeHandle,&info));
    CHECK(info.state==EP_CODE_PUBLISHING && info.pinned && info.registered);
    CHECK(info.base==(uintptr_t)detour && info.next_pointer==(uintptr_t)next);
    CHECK(Lookup(info.base)!=NULL);
    CHECK(VirtualQuery(detour,&mbi,sizeof mbi)==sizeof mbi && mbi.Protect==PAGE_EXECUTE_READ);
    CHECK(!activeCode->discard(mod,activeHandle));
    if (hookMode==1) return 1;
    if (hookMode==3)
    { SetEvent(hookEntered); CHECK(WaitForSingleObject(hookContinue,5000)==WAIT_OBJECT_0); }
    int result=ApiHookEx(mod,at,detour,next,priority);
    if (hookMode==2) { CHECK(result==0); return 1; } /* reported failure AFTER exposure */
    return result;
}
static uint8_t* ReadImage(const char* path,uint32_t size)
{
    FILE* f=fopen(path,"rb"); CHECK(f!=NULL);
    uint8_t* data=(uint8_t*)malloc(size); CHECK(data!=NULL);
    CHECK(fread(data,1,size,f)==size && fgetc(f)==EOF); CHECK(fclose(f)==0);
    return data;
}
static EpSessionCodeInfo Reserve(HfMod* mod,uint32_t bytes)
{
    EpSessionCodeInfo info; MEMORY_BASIC_INFORMATION mbi;
    CHECK(ep_session_code_reserve(&api,mod,0,bytes,&info));
    CHECK(info.handle && info.state==EP_CODE_RESERVED && !info.registered && !info.pinned);
    CHECK(!Lookup(info.base));
    CHECK(VirtualQuery((void*)info.base,&mbi,sizeof mbi)==sizeof mbi && mbi.Protect==PAGE_READWRITE);
    return info;
}
static void Discard(HfMod* mod,EpSessionCodeInfo info)
{
    EpSessionCodeInfo out; MEMORY_BASIC_INFORMATION mbi;
    CHECK(ep_session_code_discard(mod,info.handle));
    CHECK(!Lookup(info.base));
    CHECK(VirtualQuery((void*)info.base,&mbi,sizeof mbi)==sizeof mbi && mbi.State==MEM_FREE);
    CHECK(!ep_session_code_info(mod,info.handle,&out) && !out.handle && !out.base);
    CHECK(!ep_session_code_discard(mod,info.handle));
}
static EpSessionCodeInfo Ready(HfMod* mod,const uint8_t* data,uint32_t bytes,uint32_t table)
{
    EpSessionCodeInfo info=Reserve(mod,bytes);
    CHECK(ep_session_code_seal(mod,info.handle,data,bytes,table));
    CHECK(ep_session_code_info(mod,info.handle,&info) && info.state==EP_CODE_READY && info.registered);
    CHECK(Lookup(info.base)==(PRUNTIME_FUNCTION)(info.base+table));
    CHECK(!ep_session_code_seal(mod,info.handle,data,bytes,table));
    return info;
}
static void W32(uint8_t* p,uint32_t v) { memcpy(p,&v,4); }
/* Same prologue/unwind shape as the producer, but a NEW synthetic body:
 * call through HellForge's live next-pointer, add a value, restore and return.
 * No instructions from the game's body execute on the host. */
static EpSessionCodeInfo Wrapper(const SessionCodeTestApi* code,HfMod* mod,const uint8_t* shape,uint32_t add)
{
    EpSessionCodeInfo info; CHECK(code->reserve(&api,mod,0,708,&info));
    uint8_t image[708]; memcpy(image,shape,708);
    memset(image+24,0x90,670-24); size_t n=24;
    image[n++]=0x48; image[n++]=0xB8; memcpy(image+n,&info.next_pointer,8); n+=8;
    image[n++]=0xFF; image[n++]=0x10; /* call [rax], NOT a cached next pointer */
    image[n++]=0x05; W32(image+n,add); n+=4;
    const uint8_t epilogue[]={0x48,0x8B,0x5C,0x24,0x40,0x48,0x8B,0x6C,0x24,0x48,
                            0x48,0x8B,0x74,0x24,0x50,0x48,0x83,0xC4,0x20,0x41,0x5F,0x41,0x5E,0x5F,0xC3};
    memcpy(image+n,epilogue,sizeof epilogue);
    CHECK(code->seal(mod,info.handle,image,sizeof image,696));
    return info;
}
static DWORD WINAPI PublishThread(void* p)
{ return ep_session_code_publish(&g_mods[0],*(uint64_t*)p,target,10) ? 0 : 1; }
int main(int argc,char** argv)
{
    CHECK(argc==4);
    uint8_t* producer=ReadImage(argv[1],708),*receiver=ReadImage(argv[2],436);
    strcpy(g_build,"25480438"); g_modCount=4;
    for (int i=0;i<g_modCount;i++) { g_mods[i].loaded=1; snprintf(g_mods[i].id,sizeof g_mods[i].id,"fixture-%d",i); g_mods[i].log=INVALID_HANDLE_VALUE; }
    api.version=13; api.size=sizeof api; api.build_id=ApiBuildId; api.hook_ex=HookChecked;
    HfMod* mod=&g_mods[0]; EpSessionCodeInfo info,out;
    CHECK(!ep_session_code_reserve(NULL,mod,0,708,&out));
    CHECK(!ep_session_code_reserve(&api,NULL,0,708,&out));
    api.size=offsetof(HfApi,hook_ex); CHECK(!ep_session_code_reserve(&api,mod,0,708,&out)); api.size=sizeof api;
    strcpy(g_build,"other"); CHECK(!ep_session_code_reserve(&api,mod,0,708,&out)); strcpy(g_build,"25480438");
    CHECK(!ep_session_code_reserve(&api,mod,0,0,&out));
    CHECK(!ep_session_code_reserve(&api,mod,0,65537,&out));
    CHECK(!ep_session_code_reserve(&api,mod,0x10001,708,&out));
    info=Reserve(mod,708);
    CHECK(!ep_session_code_reserve(&api,mod,info.base,708,&out)); /* occupied exact address */
    CHECK(!ep_session_code_seal(&g_mods[1],info.handle,producer,708,696));
    CHECK(!ep_session_code_seal(mod,info.handle,producer,707,696));
    CHECK(!ep_session_code_publish(mod,info.handle,0x10000,0) && hookCalls==0);
    uint64_t old=info.handle; Discard(mod,info);
    info=Reserve(mod,708); CHECK(info.handle!=old && !ep_session_code_discard(mod,old)); Discard(mod,info);
    /* Actual two generator outputs: register and look up, never call or hook. */
    info=Ready(mod,producer,708,696); Discard(mod,info);
    info=Ready(mod,receiver,436,424); Discard(mod,info);
    info=Ready(mod,producer,708,696); EpSessionCodeInfo other=Reserve(mod,708);
    CHECK(!ep_session_code_publish(&g_mods[1],info.handle,0x10000,0));
    CHECK(!ep_session_code_publish(mod,info.handle,info.base,0));
    CHECK(!ep_session_code_publish(mod,info.handle,other.base,0));
    CHECK(!ep_session_code_publish(mod,info.handle,other.base+4095,0) && hookCalls==0);
    Discard(mod,other); Discard(mod,info);
    for (unsigned bad=0;bad<8;bad++)
    {
        uint8_t image[708]; memcpy(image,producer,708); info=Reserve(mod,708);
        switch(bad) {
        case 0: image[672]|=8; break; /* EHANDLER */
        case 1: image[672]|=32; break; /* CHAININFO */
        case 2: W32(image+704,700); break; /* unwind outside prefix */
        case 3: W32(image+700,709); break; /* end outside image */
        case 4: image[674]=255; break; /* truncated slots */
        case 5: image[677]=0x66; break; /* unsupported UWOP */
        case 6: image[676]=25; break; /* beyond prologue */
        case 7: image[675]=5; break; /* frame register unsupported */
        }
        CHECK(!ep_session_code_seal(mod,info.handle,image,708,696));
        CHECK(!Lookup(info.base)); Discard(mod,info);
    }
    for(unsigned failure=0;failure<3;failure++)
    {
        info=Reserve(mod,708); failProtect=failure==0; failFlush=failure==1; failAdd=failure==2;
        CHECK(!ep_session_code_seal(mod,info.handle,producer,708,696));
        failProtect=failFlush=failAdd=0;
        CHECK(ep_session_code_info(mod,info.handle,&out) && out.state==EP_CODE_FAILED && !out.registered);
        CHECK(!ep_session_code_publish(mod,info.handle,0x10000,0) && hookCalls==0);
        Discard(mod,info);
    }
    info=Ready(mod,producer,708,696); failDelete=1;
    CHECK(!ep_session_code_discard(mod,info.handle) && Lookup(info.base)!=NULL);
    CHECK(ep_session_code_info(mod,info.handle,&out) && out.registered && out.state==EP_CODE_FAILED);
    failDelete=0; failFree=1;
    CHECK(!ep_session_code_discard(mod,info.handle) && !Lookup(info.base));
    CHECK(ep_session_code_info(mod,info.handle,&out) && !out.registered && out.state==EP_CODE_FAILED);
    failFree=0; Discard(mod,info);

    uint8_t* function=(uint8_t*)VirtualAlloc(NULL,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE); CHECK(function!=NULL);
    memset(function,0x90,4096);
    const uint8_t leaf[]={0x8D,0x41,0x01,0x90,0x90,0xC3}; memcpy(function,leaf,sizeof leaf);
    DWORD protection; CHECK(VirtualProtect(function,4096,PAGE_EXECUTE_READ,&protection));
    CHECK(FlushInstructionCache(GetCurrentProcess(),function,4096)); target=(uintptr_t)function;
    int (*call)(int)=(int(*)(int))function; CHECK(call(7)==8);
    /* Block inside SDK publish. Discard and a competing publish must refuse. */
    EpSessionCodeInfo a=Wrapper(&localCode,mod,producer,10); activeHandle=a.handle; hookMode=3;
    hookEntered=CreateEventA(NULL,TRUE,FALSE,NULL); hookContinue=CreateEventA(NULL,TRUE,FALSE,NULL);
    CHECK(hookEntered && hookContinue);
    HANDLE worker=CreateThread(NULL,0,PublishThread,&a.handle,0,NULL); CHECK(worker!=NULL);
    CHECK(WaitForSingleObject(hookEntered,5000)==WAIT_OBJECT_0);
    CHECK(!ep_session_code_discard(mod,a.handle));
    CHECK(!ep_session_code_publish(mod,a.handle,target,10) && hookCalls==1);
    CHECK(Lookup(a.base)!=NULL); CHECK(SetEvent(hookContinue));
    CHECK(WaitForSingleObject(worker,5000)==WAIT_OBJECT_0); DWORD result; CHECK(GetExitCodeThread(worker,&result) && result==0);
    CloseHandle(worker); CloseHandle(hookEntered); CloseHandle(hookContinue); hookMode=0;
    CHECK(call(7)==18);
    void* firstNext=*(void**)a.next_pointer;
    EpSessionCodeInfo b=Wrapper(&localCode,&g_mods[1],producer,100); activeHandle=b.handle;
    CHECK(ep_session_code_publish(&g_mods[1],b.handle,target,20)); CHECK(call(7)==118);
    EpSessionCodeInfo c=Wrapper(&localCode,&g_mods[2],producer,1000); activeHandle=c.handle;
    CHECK(ep_session_code_publish(&g_mods[2],c.handle,target,5)); CHECK(call(7)==1118);
    CHECK(*(void**)a.next_pointer!=(void*)firstNext && *(void**)a.next_pointer==(void*)c.base);
    CHECK(g_hookTargetCount==1 && g_hookTargets[0].count==3);
    CHECK(!ep_session_code_discard(mod,a.handle));
    CHECK(ep_session_code_info(mod,a.handle,&out) && out.state==EP_CODE_PUBLISHED && out.pinned && out.registered);
    CHECK(!ep_session_code_publish(mod,a.handle,target,10));
    /* Even failure before/after the SDK's publication is retained, not freed. */
    EpSessionCodeInfo d=Wrapper(&localCode,&g_mods[3],producer,10000); activeHandle=d.handle; hookMode=1;
    CHECK(!ep_session_code_publish(&g_mods[3],d.handle,target,0));
    CHECK(ep_session_code_info(&g_mods[3],d.handle,&out) && out.state==EP_CODE_PUBLISH_FAILED && out.pinned);
    CHECK(!ep_session_code_discard(&g_mods[3],d.handle) && Lookup(d.base)!=NULL && call(7)==1118);
    EpSessionCodeInfo e=Wrapper(&localCode,&g_mods[3],producer,10000); activeHandle=e.handle; hookMode=2;
    CHECK(!ep_session_code_publish(&g_mods[3],e.handle,target,0));
    CHECK(ep_session_code_info(&g_mods[3],e.handle,&out) && out.state==EP_CODE_PUBLISH_FAILED && out.pinned);
    CHECK(!ep_session_code_discard(&g_mods[3],e.handle) && Lookup(e.base)!=NULL && call(7)==11118);
    CHECK(g_hookTargetCount==1 && g_hookTargets[0].count==4);
    /* Bounded owner slots never evict or reuse the five published attempts. */
    EpSessionCodeInfo reservations[EP_SESSION_CODE_SLOTS]; unsigned filled=0;
    while(filled<EP_SESSION_CODE_SLOTS && ep_session_code_reserve(&api,mod,0,16,&reservations[filled])) filled++;
    CHECK(filled==EP_SESSION_CODE_SLOTS-5);
    CHECK(!ep_session_code_reserve(&api,mod,0,16,&out));
    for(unsigned i=0;i<filled;i++) CHECK(ep_session_code_discard(mod,reservations[i].handle));
    CHECK(call(7)==11118);
    /* A separate actual DLL owns its stable next variable. After publication,
     * FreeLibrary must not unmap it; the chain must still call through it. */
    HMODULE dll=LoadLibraryA(argv[3]); CHECK(dll!=NULL);
    const SessionCodeTestApi* (*getApi)(void)=(const SessionCodeTestApi*(*)(void))GetProcAddress(dll,"session_code_test_api");
    CHECK(getApi!=NULL); const SessionCodeTestApi* dllCode=getApi();
    EpSessionCodeInfo f=Wrapper(dllCode,mod,producer,100000); activeCode=dllCode; activeHandle=f.handle; hookMode=0;
    CHECK(dllCode->publish(mod,f.handle,target,30)); CHECK(call(7)==111118);
    CHECK(FreeLibrary(dll)); HMODULE remaining=NULL;
    CHECK(GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            (LPCSTR)(uintptr_t)dllCode,&remaining) && remaining==dll);
    CHECK(dllCode->info(mod,f.handle,&out) && out.pinned && out.registered && out.state==EP_CODE_PUBLISHED);
    CHECK(!dllCode->discard(mod,f.handle) && Lookup(f.base)!=NULL && call(7)==111118);
    CHECK(g_hookTargetCount==1 && g_hookTargets[0].count==5);
    free(producer); free(receiver);
    printf("session code: %ld checks passed; real HellForge chain, synthetic code only\n",checks);
    /* Published images, tables, next pointers and target remain valid until
     * this process exits. No pretend unhook or test-only production cleanup. */
    return 0;
}
