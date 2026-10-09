#pragma once

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <stdint.h>

extern "C" {

typedef uint32_t (__cdecl *EP_MIDGATE_CAPACITY_HELPER)(void* owner, uint32_t native_base_index);
typedef int32_t (__cdecl *EP_MIDGATE_ALLOCATOR_HELPER)(void* owner, uint32_t start_index);
typedef uint32_t (__cdecl *EP_MIDGATE_LIMIT_HELPER)(void* owner);

typedef struct EP_MIDGATE_CALLBACKS {
    // Callers own callback code, owner state and thread quiescence.  The
    // executor stores addresses in the emitted stubs but never frees them.
    EP_MIDGATE_CAPACITY_HELPER capacity;
    EP_MIDGATE_ALLOCATOR_HELPER allocator;
    EP_MIDGATE_LIMIT_HELPER limit;
} EP_MIDGATE_CALLBACKS;

typedef struct EP_MIDGATE_SITE_HOOK {
    void* target;
    void* code;
    SIZE_T code_size;
    SIZE_T stolen_size;
    BYTE original[38];
    DWORD target_protection;
    RUNTIME_FUNCTION runtime_function;
    BOOL runtime_registered;
    BOOL installed;
} EP_MIDGATE_SITE_HOOK;

typedef struct EP_MIDGATE_HOOK {
    EP_MIDGATE_SITE_HOOK capacity;
    EP_MIDGATE_SITE_HOOK allocator;
    EP_MIDGATE_CALLBACKS callbacks;
    BOOL installed;
} EP_MIDGATE_HOOK;

// Full replacement mid-function patches for build 25480438.  Both sites are
// fixed by byte fingerprint and install atomically; failure at either site
// restores the first site and releases its unwind table/stub.
__declspec(dllexport) BOOL __cdecl ep_midgate_install(
    DWORD steam_build, HMODULE game_module,
    const EP_MIDGATE_CALLBACKS* callbacks, EP_MIDGATE_HOOK* out_hook);
__declspec(dllexport) BOOL __cdecl ep_midgate_remove(EP_MIDGATE_HOOK* hook);
__declspec(dllexport) DWORD __cdecl ep_midgate_expected_build();
__declspec(dllexport) DWORD __cdecl ep_midgate_capacity_rva();
__declspec(dllexport) DWORD __cdecl ep_midgate_allocator_rva();
__declspec(dllexport) DWORD __cdecl ep_midgate_capacity_span();
__declspec(dllexport) DWORD __cdecl ep_midgate_allocator_span();
__declspec(dllexport) DWORD __cdecl ep_midgate_capacity_code_size();
__declspec(dllexport) DWORD __cdecl ep_midgate_allocator_code_size();
}
