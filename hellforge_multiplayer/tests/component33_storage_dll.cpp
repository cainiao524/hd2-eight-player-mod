/* Own-process allocations and supplied snapshots only. No generated execution. */
#include <windows.h>
#include "../mod/src/ep_component33_storage.h"
static unsigned calls[7],failures[7],hook_calls;
static bool Fail(unsigned k) { ++calls[k];return failures[k]==UINT32_MAX || calls[k]==failures[k]; }
static LPVOID TestAlloc(LPVOID p,SIZE_T n,DWORD t,DWORD f) { return Fail(0) ? nullptr : VirtualAlloc(p,n,t,f); }
static BOOL TestProtect(LPVOID p,SIZE_T n,DWORD f,PDWORD old) { return Fail(1) ? FALSE : VirtualProtect(p,n,f,old); }
static BOOL TestFlush(HANDLE h,LPCVOID p,SIZE_T n) { return Fail(2) ? FALSE : FlushInstructionCache(h,p,n); }
static BOOLEAN TestAdd(PRUNTIME_FUNCTION p,DWORD n,DWORD64 base) { return Fail(3) ? FALSE : RtlAddFunctionTable(p,n,base); }
static BOOLEAN TestDelete(PRUNTIME_FUNCTION p) { return Fail(4) ? FALSE : RtlDeleteFunctionTable(p); }
static BOOL TestFree(LPVOID p,SIZE_T n,DWORD f) { return Fail(5) ? FALSE : VirtualFree(p,n,f); }
static BOOL TestPin(DWORD f,LPCSTR p,HMODULE* out) { return Fail(6) ? FALSE : GetModuleHandleExA(f,p,out); }
#define VirtualAlloc TestAlloc
#define VirtualProtect TestProtect
#define FlushInstructionCache TestFlush
#define RtlAddFunctionTable TestAdd
#define RtlDeleteFunctionTable TestDelete
#define VirtualFree TestFree
#define GetModuleHandleExA TestPin
#include "../mod/src/ep_session_code.cpp"
#include "../mod/src/ep_component33_storage.cpp"
#undef VirtualAlloc
#undef VirtualProtect
#undef FlushInstructionCache
#undef RtlAddFunctionTable
#undef RtlDeleteFunctionTable
#undef VirtualFree
#undef GetModuleHandleExA
static const char* Build(void) { return "25480438"; }
static int Hook(HfMod*,uintptr_t,void*,void**,int32_t) { ++hook_calls;return 1; }
#define EXPORT extern "C" __declspec(dllexport)
EXPORT void c33_storage_faults(const unsigned* f) { memset(calls,0,sizeof(calls));memcpy(failures,f,sizeof(failures)); }
EXPORT unsigned c33_storage_counts(unsigned* out) { memcpy(out,calls,sizeof(calls));return hook_calls; }
EXPORT EpC33StorageResult c33_storage_migrate(const EpC33Snapshot* s,EpC33Migration* out) { return ep_component33_migrate_snapshot(s,out); }
EXPORT EpC33StorageResult c33_storage_prepare(HfMod* m,const EpC33StorageBindings* b,const EpC33Snapshot* s,EpC33StorageInfo* out)
{ HfApi a={};a.version=13;a.size=sizeof(a);a.build_id=Build;a.hook_ex=Hook;return ep_component33_storage_prepare(&a,m,b,s,out); }
EXPORT int c33_storage_info(HfMod* m,uint64_t id,EpC33StorageInfo* out) { return ep_component33_storage_info(m,id,out); }
EXPORT int c33_storage_cancel(HfMod* m,uint64_t id) { return ep_component33_storage_cancel(m,id); }
EXPORT EpC33StorageResult c33_storage_retain(HfMod* m,uint64_t id,const EpC33Snapshot* s) { return ep_component33_storage_retain(m,id,s); }
EXPORT EpC33StorageResult c33_storage_prepare_resources(HfMod* m,const EpC33StorageBindings* b,const EpC33Snapshot* s,const EpC33ResourceStorageConfig* r,const EpC33ResourceSnapshot* snap,EpC33StorageInfo* out)
{ HfApi a={};a.version=13;a.size=sizeof(a);a.build_id=Build;a.hook_ex=Hook;return ep_component33_storage_prepare_resources(&a,m,b,s,r,snap,out); }
EXPORT int c33_storage_resources(HfMod* m,uint64_t id,EpC33ResourceStorageInfo* out) { return ep_component33_storage_resources(m,id,out); }
EXPORT EpC33StorageResult c33_storage_retain_resources(HfMod* m,uint64_t id,const EpC33Snapshot* s,const EpC33ResourceSnapshot* r) { return ep_component33_storage_retain_resources(m,id,s,r); }
