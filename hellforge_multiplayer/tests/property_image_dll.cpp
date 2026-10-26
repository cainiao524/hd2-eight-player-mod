/* Test-only exports. The production DLL exposes none of these entry points. */
#include <windows.h>
#include <string.h>
#include "../mod/src/ep_property_code.h"
#include "../mod/src/ep_property_gate.h"
#include "../mod/src/ep_getter_image.h"
#include "../mod/src/ep_mover_image.h"
#include "../mod/src/ep_insert_image.h"
#include "../mod/src/ep_remove_image.h"
#include "../mod/src/ep_registry_image.h"
extern "C" __declspec(dllexport) int registry_image_test_build(uint32_t kind,const EpRegistryAddresses* a,EpRegistryImage* out)
{ return ep_registry_image_build(kind,a,out); }
extern "C" __declspec(dllexport) int remove_image_test_build(uint32_t kind,const EpRemoveAddresses* a,EpRemoveImage* out)
{ return ep_remove_image_build(kind,a,out); }
extern "C" __declspec(dllexport) int insert_image_test_build(uint32_t kind,const EpInsertAddresses* a,EpPropertyImage* out)
{ return ep_insert_image_build(kind,a,out); }
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

extern "C" __declspec(dllexport) int insert_image_test_prepare(uint32_t kind,EpInsertAddresses* a,EpPropertyImage* image,uint32_t* checks)
{
    HfApi api={};int owner_marker=0;HfMod* owner=(HfMod*)&owner_marker;
    EpSessionCodeInfo info={},cleared={},stale={};DWORD64 unwind_base=0;MEMORY_BASIC_INFORMATION mbi={};
    void* hint=VirtualAlloc(NULL,65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);*checks=0;
    if (!hint) return -1;
    *a={(uint64_t)hint-0x10000000,(uint64_t)hint,(uint64_t)hint+0x10000000,
        (uint64_t)hint+0x20000000,(uint64_t)hint+0x30000,(uint64_t)hint+0x10000};
    if (!VirtualFree(hint,0,MEM_RELEASE)) return -2;
    const uint64_t desired=kind==EP_INSERT_DENSE_LEGACY ? (uint64_t)hint : 0;a->code_address=desired;
    api.version=13;api.size=sizeof(api);api.build_id=Build;api.hook_ex=Hook;
#define CHECK(x) do { ++*checks; if (!(x)) { fail_free=fail_protect=false; if (info.handle) ep_session_code_discard(owner,info.handle); return __LINE__; } } while(0)
    CHECK(ep_insert_code_prepare(&api,owner,kind,a,&info)==EP_PROPERTY_OK);
    CHECK((!desired || info.base==desired) && info.state==EP_CODE_READY && info.registered && !info.pinned);
    a->code_address=info.base;
    CHECK(ep_insert_image_build(kind,a,image)==EP_PROPERTY_OK);
    CHECK(image->bytes==info.bytes && !memcmp((void*)info.base,image->data,image->bytes));
    CHECK(RtlLookupFunctionEntry(info.base,&unwind_base,NULL)==(PRUNTIME_FUNCTION)(info.base+image->table_offset));
    CHECK(unwind_base==info.base);
    CHECK(RtlLookupFunctionEntry(info.base+image->code_bytes-1,&unwind_base,NULL)==(PRUNTIME_FUNCTION)(info.base+image->table_offset)+1);
    CHECK(unwind_base==info.base);
    CHECK(VirtualQuery((void*)info.base,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.Protect==PAGE_EXECUTE_READ);
    CHECK(!hook_calls);
    CHECK(ep_session_code_discard(owner,info.handle));
    CHECK(!ep_session_code_info(owner,info.handle,&stale));
    CHECK(RtlLookupFunctionEntry(info.base,&unwind_base,NULL)==NULL);
    CHECK(VirtualQuery((void*)info.base,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.State==MEM_FREE);
    info={};a->storage_address++;
    CHECK(ep_insert_code_prepare(&api,owner,kind,a,&info)==EP_PROPERTY_POINTER);
    CHECK(!memcmp(&info,&cleared,sizeof(info)));
    CHECK(VirtualQuery((void*)a->code_address,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.State==MEM_FREE);
    fail_free=true;
    CHECK(ep_insert_code_prepare(&api,owner,kind,a,&info)==EP_PROPERTY_CLEANUP);
    CHECK(info.handle && info.state==EP_CODE_FAILED && !info.pinned && !info.registered);
    CHECK(ep_session_code_info(owner,info.handle,&stale) && stale.handle==info.handle);
    fail_free=false;CHECK(ep_session_code_discard(owner,info.handle));info={};a->storage_address--;
    fail_protect=true;
    CHECK(ep_insert_code_prepare(&api,owner,kind,a,&info)==EP_PROPERTY_SEAL);
    CHECK(!memcmp(&info,&cleared,sizeof(info)));fail_protect=false;
    CHECK(VirtualQuery((void*)a->code_address,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.State==MEM_FREE);
    CHECK(ep_insert_code_prepare(&api,owner,0,a,&info)==EP_PROPERTY_ARGUMENT);
    CHECK(!memcmp(&info,&cleared,sizeof(info)));CHECK(!hook_calls);return 0;
#undef CHECK
}

extern "C" __declspec(dllexport) int remove_image_test_prepare(uint32_t kind,EpRemoveAddresses* a,EpRemoveImage* image,uint32_t* checks)
{
    HfApi api={};int owner_marker=0;HfMod* owner=(HfMod*)&owner_marker;
    EpSessionCodeInfo info={},cleared={},stale={};DWORD64 unwind_base=0;MEMORY_BASIC_INFORMATION mbi={};
    void* hint=VirtualAlloc(NULL,65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);*checks=0;
    if (!hint) return -1;
    *a={(uint64_t)hint-0x10000000,(uint64_t)hint,(uint64_t)hint+0x10000000,
        (uint64_t)hint+0x20000000,(uint64_t)hint+0x30000,(uint64_t)hint+0x10000};
    if (!VirtualFree(hint,0,MEM_RELEASE)) return -2;
    const uint64_t desired=kind==EP_REMOVE_LEGACY ? (uint64_t)hint : 0;a->code_address=desired;
    api.version=13;api.size=sizeof(api);api.build_id=Build;api.hook_ex=Hook;
#define CHECK(x) do { ++*checks; if (!(x)) { fail_free=fail_protect=false; if (info.handle) ep_session_code_discard(owner,info.handle); return __LINE__; } } while(0)
    CHECK(ep_remove_code_prepare(&api,owner,kind,a,&info)==EP_PROPERTY_OK);
    CHECK((!desired || info.base==desired) && info.state==EP_CODE_READY && info.registered && !info.pinned);
    a->code_address=info.base;
    CHECK(ep_remove_image_build(kind,a,image)==EP_PROPERTY_OK);
    CHECK(image->bytes==info.bytes && !memcmp((void*)info.base,image->data,image->bytes));
    CHECK(RtlLookupFunctionEntry(info.base,&unwind_base,NULL)==(PRUNTIME_FUNCTION)(info.base+image->table_offset));
    CHECK(unwind_base==info.base);
    CHECK(RtlLookupFunctionEntry(info.base+image->code_bytes-1,&unwind_base,NULL)==(PRUNTIME_FUNCTION)(info.base+image->table_offset)+1);
    CHECK(unwind_base==info.base);
    CHECK(VirtualQuery((void*)info.base,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.Protect==PAGE_EXECUTE_READ);
    CHECK(!hook_calls);
    CHECK(ep_session_code_discard(owner,info.handle));
    CHECK(!ep_session_code_info(owner,info.handle,&stale));
    CHECK(RtlLookupFunctionEntry(info.base,&unwind_base,NULL)==NULL);
    CHECK(VirtualQuery((void*)info.base,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.State==MEM_FREE);
    info={};a->storage_address++;
    CHECK(ep_remove_code_prepare(&api,owner,kind,a,&info)==EP_PROPERTY_POINTER);
    CHECK(!memcmp(&info,&cleared,sizeof(info)));
    CHECK(VirtualQuery((void*)a->code_address,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.State==MEM_FREE);
    fail_free=true;
    CHECK(ep_remove_code_prepare(&api,owner,kind,a,&info)==EP_PROPERTY_CLEANUP);
    CHECK(info.handle && info.state==EP_CODE_FAILED && !info.pinned && !info.registered);
    CHECK(ep_session_code_info(owner,info.handle,&stale) && stale.handle==info.handle);
    fail_free=false;CHECK(ep_session_code_discard(owner,info.handle));info={};a->storage_address--;
    fail_protect=true;
    CHECK(ep_remove_code_prepare(&api,owner,kind,a,&info)==EP_PROPERTY_SEAL);
    CHECK(!memcmp(&info,&cleared,sizeof(info)));fail_protect=false;
    CHECK(VirtualQuery((void*)a->code_address,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.State==MEM_FREE);
    CHECK(ep_remove_code_prepare(&api,owner,0,a,&info)==EP_PROPERTY_ARGUMENT);
    CHECK(!memcmp(&info,&cleared,sizeof(info)));CHECK(!hook_calls);return 0;
#undef CHECK
}

#include "../mod/src/ep_classify_image.h"
extern "C" __declspec(dllexport) int classify_image_test_build(uint32_t kind,const EpClassifyAddresses* a,EpClassifyImage* out) { return ep_classify_image_build(kind,a,out); }
extern "C" __declspec(dllexport) int classify_image_test_prepare(uint32_t kind,EpClassifyAddresses* a,EpClassifyImage* image,uint32_t* checks)
{
    HfApi api={};int owner_marker=0;HfMod* owner=(HfMod*)&owner_marker;
    EpSessionCodeInfo info={},cleared={},stale={};DWORD64 unwind_base=0;MEMORY_BASIC_INFORMATION mbi={};
    void* hint=VirtualAlloc(NULL,65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);*checks=0;
    if (!hint) return -1;
    *a={(uint64_t)hint-0x10000000,(uint64_t)hint,(uint64_t)hint+0x10000000,
        (uint64_t)hint+0x20000000,(uint64_t)hint+0x10000};
    if (!VirtualFree(hint,0,MEM_RELEASE)) return -2;
    const uint64_t desired=kind==EP_CLASSIFY_ENTER ? (uint64_t)hint : 0;a->code_address=desired;
    api.version=13;api.size=sizeof(api);api.build_id=Build;api.hook_ex=Hook;
#define CHECK(x) do { ++*checks; if (!(x)) { fail_free=fail_protect=false; if (info.handle) ep_session_code_discard(owner,info.handle); return __LINE__; } } while(0)
    CHECK(ep_classify_code_prepare(&api,owner,kind,a,&info)==EP_PROPERTY_OK);
    CHECK((!desired || info.base==desired) && info.state==EP_CODE_READY && info.registered && !info.pinned);
    a->code_address=info.base;
    CHECK(ep_classify_image_build(kind,a,image)==EP_PROPERTY_OK);
    CHECK(image->bytes==info.bytes && !memcmp((void*)info.base,image->data,image->bytes));
    CHECK(RtlLookupFunctionEntry(info.base,&unwind_base,NULL)==(PRUNTIME_FUNCTION)(info.base+image->table_offset));
    CHECK(unwind_base==info.base);
    CHECK(RtlLookupFunctionEntry(info.base+image->code_bytes-1,&unwind_base,NULL)==(PRUNTIME_FUNCTION)(info.base+image->table_offset)+1);
    CHECK(unwind_base==info.base);
    CHECK(VirtualQuery((void*)info.base,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.Protect==PAGE_EXECUTE_READ);
    CHECK(!hook_calls);
    CHECK(ep_session_code_discard(owner,info.handle));
    CHECK(!ep_session_code_info(owner,info.handle,&stale));
    CHECK(RtlLookupFunctionEntry(info.base,&unwind_base,NULL)==NULL);
    CHECK(VirtualQuery((void*)info.base,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.State==MEM_FREE);
    info={};a->storage_address++;
    CHECK(ep_classify_code_prepare(&api,owner,kind,a,&info)==EP_PROPERTY_POINTER);
    CHECK(!memcmp(&info,&cleared,sizeof(info)));
    CHECK(VirtualQuery((void*)a->code_address,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.State==MEM_FREE);
    fail_free=true;
    CHECK(ep_classify_code_prepare(&api,owner,kind,a,&info)==EP_PROPERTY_CLEANUP);
    CHECK(info.handle && info.state==EP_CODE_FAILED && !info.pinned && !info.registered);
    CHECK(ep_session_code_info(owner,info.handle,&stale) && stale.handle==info.handle);
    fail_free=false;CHECK(ep_session_code_discard(owner,info.handle));info={};a->storage_address--;
    fail_protect=true;
    CHECK(ep_classify_code_prepare(&api,owner,kind,a,&info)==EP_PROPERTY_SEAL);
    CHECK(!memcmp(&info,&cleared,sizeof(info)));fail_protect=false;
    CHECK(VirtualQuery((void*)a->code_address,&mbi,sizeof(mbi))==sizeof(mbi) && mbi.State==MEM_FREE);
    CHECK(ep_classify_code_prepare(&api,owner,0,a,&info)==EP_PROPERTY_ARGUMENT);
    CHECK(!memcmp(&info,&cleared,sizeof(info)));CHECK(!hook_calls);return 0;
#undef CHECK
}
#include "../mod/src/ep_roster_gate.h"
extern "C" __declspec(dllexport) EpPropertyResult roster_gate_test_build(uint32_t kind,const EpInsertAddresses* a,uint64_t control,uint64_t next,EpRosterGateImage* out)
{ return ep_roster_gate_build(kind,a,control,next,out); }

extern "C" __declspec(dllexport) int registry_image_test_prepare(uint32_t kind,uint32_t* checks)
{
    HfApi api={};int marker=0;HfMod* owner=(HfMod*)&marker;EpSessionCodeInfo info={},empty={};EpRegistryImage image;
    void* hint=VirtualAlloc(NULL,65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);*checks=0;
    if (!hint || !VirtualFree(hint,0,MEM_RELEASE)) return -1;
    EpRegistryAddresses a={(uintptr_t)hint-0x10000000,(uintptr_t)hint,(uintptr_t)hint+0x10000000,
        (uintptr_t)hint+0x20000000,(uintptr_t)hint+0x30000,(uintptr_t)hint+0x10000};
    api.version=13;api.size=sizeof(api);api.build_id=Build;api.hook_ex=Hook;
#define CHECK(x) do {++*checks;if(!(x)){fail_free=fail_protect=false;if(info.handle)ep_session_code_discard(owner,info.handle);return __LINE__;}} while(0)
    CHECK(ep_registry_code_prepare(&api,owner,kind,&a,&info)==EP_PROPERTY_OK);
    CHECK(info.base==a.code_address && info.state==EP_CODE_READY && info.registered && !info.pinned);
    CHECK(ep_registry_image_build(kind,&a,&image)==EP_PROPERTY_OK && info.bytes==image.bytes && !memcmp((void*)info.base,image.data,image.bytes));
    RUNTIME_FUNCTION* rows=(RUNTIME_FUNCTION*)(image.data+image.table_offset);DWORD64 base=0;
    for(unsigned i=0;i<image.function_count;i++) {
        CHECK(RtlLookupFunctionEntry(info.base+rows[i].BeginAddress,&base,NULL)==(RUNTIME_FUNCTION*)(info.base+image.table_offset)+i && base==info.base);
    }
    CHECK(ep_session_code_discard(owner,info.handle));info={};
    CHECK(RtlLookupFunctionEntry(a.code_address,&base,NULL)==NULL);
    for(unsigned variant=0;variant<3;variant++) {
        EpRegistryImage broken=image;RUNTIME_FUNCTION* r=(RUNTIME_FUNCTION*)(broken.data+broken.table_offset);
        if(variant==0) broken.data[r[0].UnwindData]=9;
        else if(kind==1) {
            uint8_t* uw=broken.data+r[1].UnwindData;unsigned chain=4+((uw[2]+1u)&~1u)*2;
            if(variant==1) memcpy(uw+chain,&r[1],12); /* cycle */
            else memcpy(uw+chain,&r[image.function_count-1],12); /* forward parent */
        } else broken.data[r[0].UnwindData]=variant==1?33:17; /* truncated chain or unsupported flags */
        CHECK(ep_session_code_reserve(&api,owner,(uintptr_t)a.code_address,broken.bytes,&info));
        CHECK(!ep_session_code_seal_table(owner,info.handle,broken.data,broken.bytes,broken.table_offset,broken.function_count));
        CHECK(ep_session_code_discard(owner,info.handle));info={};
    }
    a.storage_address++;
    CHECK(ep_registry_code_prepare(&api,owner,kind,&a,&info)==EP_PROPERTY_POINTER && !memcmp(&info,&empty,sizeof(info)));
    fail_free=true;
    CHECK(ep_registry_code_prepare(&api,owner,kind,&a,&info)==EP_PROPERTY_CLEANUP && info.handle && !info.registered);
    fail_free=false;CHECK(ep_session_code_discard(owner,info.handle));info={};a.storage_address--;
    fail_protect=true;
    CHECK(ep_registry_code_prepare(&api,owner,kind,&a,&info)==EP_PROPERTY_SEAL && !memcmp(&info,&empty,sizeof(info)));
    fail_protect=false;CHECK(!hook_calls);return 0;
#undef CHECK
}
