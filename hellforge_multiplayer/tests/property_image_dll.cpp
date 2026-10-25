/* Test-only exports. The production DLL exposes none of these entry points. */
#include <windows.h>
#include <string.h>
#include "../mod/src/ep_property_code.h"
#include "../mod/src/ep_property_gate.h"
#include "../mod/src/ep_getter_image.h"
#include "../mod/src/ep_mover_image.h"
extern "C" __declspec(dllexport) int mover_image_test_build(const EpMoverAddresses* a,EpPropertyImage* out)
{ return ep_mover_image_build(a,out); }
extern "C" __declspec(dllexport) int getter_image_test_build(const EpGetterAddresses* a,EpPropertyImage* out)
{ return ep_getter_image_build(a,out); }
static EpGetterAddresses GetterArguments(const EpPropertyAddresses* a)
{ return {a->game_base,a->code_address,a->roster_address,a->property_address,a->reject_address}; }
static EpPropertyResult Prepare(const HfApi* api,HfMod* owner,uint32_t kind,const EpPropertyAddresses* a,EpSessionCodeInfo* out)
{
    if (kind==4) { EpMoverAddresses m={a->game_base,a->code_address,a->roster_address,a->property_address,a->reject_address}; return ep_mover_code_prepare(api,owner,&m,out); }
    if (kind==3) { EpGetterAddresses g=GetterArguments(a); return ep_getter_code_prepare(api,owner,&g,out); }
    return ep_property_code_prepare(api,owner,kind,a,out);
}
static EpPropertyResult ImageBuild(uint32_t kind,const EpPropertyAddresses* a,EpPropertyImage* out)
{
    if (kind==4) { EpMoverAddresses m={a->game_base,a->code_address,a->roster_address,a->property_address,a->reject_address}; return ep_mover_image_build(&m,out); }
    if (kind==3) { EpGetterAddresses g=GetterArguments(a); return ep_getter_image_build(&g,out); }
    return ep_property_image_build(kind,a,out);
}
extern "C" __declspec(dllexport) int property_image_test_gate(uint32_t kind,const EpPropertyAddresses* a,uint64_t control,uint64_t next,EpPropertyGateImage* out)
{ return ep_property_gate_build(kind,a,control,next,out); }
extern "C" __declspec(dllexport) int getter_image_test_gate(const EpGetterAddresses* a,uint64_t control,uint64_t next,EpPropertyGateImage* out)
{ return ep_getter_gate_build(a,control,next,out); }
static bool fail_free,fail_protect;
static BOOL TestFree(LPVOID p,SIZE_T n,DWORD flags)
{ return fail_free ? FALSE : VirtualFree(p,n,flags); }
static BOOL TestProtect(LPVOID p,SIZE_T n,DWORD flags,PDWORD old)
{ return fail_protect ? FALSE : VirtualProtect(p,n,flags,old); }
#define VirtualFree TestFree
#define VirtualProtect TestProtect
#include "../mod/src/ep_session_code.cpp"
#undef VirtualFree
#undef VirtualProtect
static unsigned hook_calls;
static const char* Build(void) { return "25480438"; }
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) { hook_calls++; return 1; }
extern "C" __declspec(dllexport) int property_image_test_build(uint32_t kind,const EpPropertyAddresses* a,EpPropertyImage* out)
{
    return ep_property_image_build(kind,a,out);
}
/* Allocate only our own image; all external bindings are numerical fixture
 * addresses. Register/look up/delete metadata but never execute the image. */
extern "C" __declspec(dllexport) int property_image_test_prepare(uint32_t kind,EpPropertyAddresses* a,EpPropertyImage* image,uint32_t* checks)
{
    HfApi api={}; int owner_marker=0;
    HfMod* owner=(HfMod*)&owner_marker;
    EpSessionCodeInfo info={},cleared={},stale={};
    DWORD64 unwind_base=0;
    MEMORY_BASIC_INFORMATION mbi={};
    void* hint=VirtualAlloc(NULL,65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    EpPropertyResult result;
    *checks=0;
    if (!hint) return -1;
    *a={(uint64_t)hint-0x10000000,(uint64_t)hint,(uint64_t)hint+0x10000000,
        (uint64_t)hint+0x20000000,(uint64_t)hint+0x10000};
    if (!VirtualFree(hint,0,MEM_RELEASE)) return -2;
    const uint64_t desired=kind==EP_PROPERTY_PRODUCER ? (uint64_t)hint : 0;
    a->code_address=desired;
    api.version=13; api.size=sizeof(api); api.build_id=Build; api.hook_ex=Hook;
#define CHECK(x) do { ++*checks; if (!(x)) { fail_free=fail_protect=false; if (info.handle) ep_session_code_discard(owner,info.handle); return __LINE__; } } while(0)
    result=Prepare(&api,owner,kind,a,&info);
    CHECK(result==EP_PROPERTY_OK);
    CHECK((!desired || info.base==desired) && info.state==EP_CODE_READY && info.registered && !info.pinned);
    a->code_address=info.base;
    CHECK(ImageBuild(kind,a,image)==EP_PROPERTY_OK);
    CHECK(image->bytes==info.bytes && !memcmp((void*)info.base,image->data,image->bytes));
    CHECK(RtlLookupFunctionEntry(info.base+image->code_bytes-1,&unwind_base,NULL)==(PRUNTIME_FUNCTION)(info.base+image->table_offset)+(kind==4 ? 1 : 0));
    CHECK(unwind_base==info.base);
    CHECK(VirtualQuery((void*)info.base,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.Protect==PAGE_EXECUTE_READ);
    CHECK(!hook_calls);
    CHECK(ep_session_code_discard(owner,info.handle));
    CHECK(!ep_session_code_info(owner,info.handle,&stale));
    CHECK(RtlLookupFunctionEntry(info.base,&unwind_base,NULL)==NULL);
    CHECK(VirtualQuery((void*)info.base,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.State==MEM_FREE);
    info={};
    /* Failure after reserve must return no handle and leave no allocation. */
    a->property_address++;
    CHECK(Prepare(&api,owner,kind,a,&info)==EP_PROPERTY_POINTER);
    CHECK(!memcmp(&info,&cleared,sizeof(info)));
    CHECK(VirtualQuery((void*)a->code_address,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.State==MEM_FREE);
    fail_free=true;
    CHECK(Prepare(&api,owner,kind,a,&info)==EP_PROPERTY_CLEANUP);
    CHECK(info.handle && info.state==EP_CODE_FAILED && !info.pinned && !info.registered);
    CHECK(ep_session_code_info(owner,info.handle,&stale) && stale.handle==info.handle);
    fail_free=false;
    CHECK(ep_session_code_discard(owner,info.handle));
    info={};
    a->property_address--;
    fail_protect=true;
    CHECK(Prepare(&api,owner,kind,a,&info)==EP_PROPERTY_SEAL);
    CHECK(!memcmp(&info,&cleared,sizeof(info)));
    fail_protect=false;
    CHECK(VirtualQuery((void*)a->code_address,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.State==MEM_FREE);
    CHECK(ep_property_code_prepare(&api,owner,0,a,&info)==EP_PROPERTY_ARGUMENT);
    CHECK(!memcmp(&info,&cleared,sizeof(info)));
    CHECK(!hook_calls);
    return 0;
#undef CHECK
}
