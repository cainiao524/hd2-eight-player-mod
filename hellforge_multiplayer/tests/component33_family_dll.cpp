/* Own-process lifetime tests only. Never call any generated game instruction. */
#include <windows.h>
#include "../mod/src/ep_component33_family.h"
static unsigned calls[7],failures[7],hook_calls;
static bool Fail(unsigned kind) { return ++calls[kind]==failures[kind]; }
static LPVOID TestAlloc(LPVOID p,SIZE_T n,DWORD type,DWORD protect)
{ return Fail(0) ? nullptr : VirtualAlloc(p,n,type,protect); }
static BOOL TestProtect(LPVOID p,SIZE_T n,DWORD flags,PDWORD old)
{ return Fail(1) ? FALSE : VirtualProtect(p,n,flags,old); }
static BOOL TestFlush(HANDLE p,LPCVOID at,SIZE_T n)
{ return Fail(2) ? FALSE : FlushInstructionCache(p,at,n); }
static BOOLEAN TestAdd(PRUNTIME_FUNCTION p,DWORD n,DWORD64 base)
{ return Fail(3) ? FALSE : RtlAddFunctionTable(p,n,base); }
static BOOLEAN TestDelete(PRUNTIME_FUNCTION p)
{ return Fail(4) ? FALSE : RtlDeleteFunctionTable(p); }
static BOOL TestFree(LPVOID p,SIZE_T n,DWORD flags)
{ return Fail(5) ? FALSE : VirtualFree(p,n,flags); }
static BOOL TestPin(DWORD flags,LPCSTR at,HMODULE* out)
{ return Fail(6) ? FALSE : GetModuleHandleExA(flags,at,out); }
#define VirtualAlloc TestAlloc
#define VirtualProtect TestProtect
#define FlushInstructionCache TestFlush
#define RtlAddFunctionTable TestAdd
#define RtlDeleteFunctionTable TestDelete
#define VirtualFree TestFree
#define GetModuleHandleExA TestPin
#include "../mod/src/ep_session_code.cpp"
#undef VirtualAlloc
#undef VirtualProtect
#undef FlushInstructionCache
#undef RtlAddFunctionTable
#undef RtlDeleteFunctionTable
#undef VirtualFree
#undef GetModuleHandleExA
static const char* Build(void) { return "25480438"; }
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) { ++hook_calls;return 1; }
static HfApi Api(void) { HfApi a={};a.version=13;a.size=sizeof(a);a.build_id=Build;a.hook_ex=Hook;return a; }
#define EXPORT extern "C" __declspec(dllexport)
EXPORT void c33_test_faults(const unsigned* f) { memset(calls,0,sizeof(calls));memcpy(failures,f,sizeof(failures)); }
EXPORT unsigned c33_test_counts(unsigned* out) { memcpy(out,calls,sizeof(calls));return hook_calls; }
EXPORT EpPropertyResult c33_test_prepare(HfMod* m,const EpComponent33FamilyBindings* b,EpComponent33FamilyInfo* i)
{ auto a=Api();return ep_component33_family_prepare(&a,m,b,i); }
EXPORT int c33_test_info(HfMod* m,uint64_t id,EpComponent33FamilyInfo* i) { return ep_component33_family_info(m,id,i); }
EXPORT int c33_test_cancel(HfMod* m,uint64_t id) { return ep_component33_family_cancel(m,id); }
EXPORT int c33_test_retain(HfMod* m,uint64_t id) { return ep_component33_family_retain(m,id); }
EXPORT int c33_test_code_info(HfMod* m,uint64_t id,EpSessionCodeInfo* i) { return ep_session_code_info(m,id,i); }
EXPORT int c33_test_reserve(HfMod* m,uintptr_t p,uint32_t n,EpSessionCodeInfo* i) { auto a=Api();return ep_session_code_reserve(&a,m,p,n,i); }
EXPORT int c33_test_discard(HfMod* m,uint64_t id) { return ep_session_code_discard(m,id); }
/* Deliberately failing test hook, never the real SDK or a target write. */
EXPORT int c33_test_publish(HfMod* m,uint64_t id) { return ep_session_code_publish(m,id,(uintptr_t)&Hook,0); }
EXPORT int c33_test_retain_set(HfMod* m,const uint64_t* ids,uint32_t n) { return ep_session_code_retain_set(m,ids,n); }
EXPORT int c33_test_seal(HfMod* m,uint64_t id,const void* image,uint32_t bytes,uint32_t table,uint32_t count,const EpSessionGsCheck* gs,unsigned mode)
{
    if (mode==2) return ep_session_code_seal_component33_property(m,id,image,bytes,table,gs);
    if (mode==1) return ep_session_code_seal_gs_table(m,id,image,bytes,table,count,gs);
    return ep_session_code_seal_table(m,id,image,bytes,table,count);
}
