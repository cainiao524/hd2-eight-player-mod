#pragma once
#include <windows.h>

extern "C" {

typedef struct EP_CONSUMER_CALLBACKS {
    void* resolver;
    void* mode;
    void* identity;
    void* lookup;
    void* status;
} EP_CONSUMER_CALLBACKS;

typedef struct EP_CONSUMER_HOOK {
    void* target;
    void* code;
    SIZE_T code_size;
    SIZE_T stolen_size;
    BYTE original[14];
    DWORD target_protection;
    RUNTIME_FUNCTION runtime_function;
    BOOL runtime_registered;
    BOOL installed;
} EP_CONSUMER_HOOK;

// The full-replacement consumer has no trampoline. The caller owns thread
// quiescence before install/remove and must keep every callback and resolver
// object alive until remove returns.
__declspec(dllexport) BOOL __cdecl ep_consumer_install(
    DWORD steam_build, HMODULE game_module, DWORD entry_rva,
    const BYTE* expected_entry, SIZE_T expected_size,
    const EP_CONSUMER_CALLBACKS* callbacks, EP_CONSUMER_HOOK* out_hook);
__declspec(dllexport) BOOL __cdecl ep_consumer_remove(EP_CONSUMER_HOOK* hook);
__declspec(dllexport) DWORD __cdecl ep_consumer_expected_build();
__declspec(dllexport) DWORD __cdecl ep_consumer_code_size();
__declspec(dllexport) DWORD __cdecl ep_consumer_stolen_size();
}
