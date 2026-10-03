#include "ep_consumer_native_callbacks.h"
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstring>

static unsigned char* g_sidecar = nullptr;
static void* __cdecl sidecar_resolver(void*) { return g_sidecar; }
static void* __cdecl fake_lookup(void*, unsigned long long id, const void*) {
    return id >= 1 && id <= 8 ? reinterpret_cast<void*>(static_cast<uintptr_t>(id)) : nullptr;
}

static void write_headers(unsigned char* image, unsigned size) {
    std::memset(image, 0, size);
    *reinterpret_cast<WORD*>(image) = 0x5a4d;
    *reinterpret_cast<DWORD*>(image + 0x3c) = 0x80;
    auto* nt = image + 0x80;
    *reinterpret_cast<DWORD*>(nt) = 0x4550;
    *reinterpret_cast<WORD*>(nt + 4) = 0x8664;
    *reinterpret_cast<DWORD*>(nt + 8) = 1790161983u;
    *reinterpret_cast<WORD*>(nt + 24) = 0x20b;
    *reinterpret_cast<DWORD*>(nt + 24 + 56) = 74727424u;
}

int main() {
    constexpr SIZE_T image_size = 0x4800000;
    auto* image = static_cast<unsigned char*>(VirtualAlloc(nullptr, image_size,
        MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    auto* owner = static_cast<unsigned char*>(VirtualAlloc(nullptr, 0xC000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    auto* platform = static_cast<unsigned char*>(VirtualAlloc(nullptr, 0x1000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    auto* sidecar = static_cast<unsigned char*>(VirtualAlloc(nullptr, 0x100, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    auto* mode_state = image + 0x400000;
    auto* enum_root = image + 0x500000;
    auto* lookup_root = image + 0x600000;
    auto* lookup_object = image + 0x610000;
    auto* lookup_table = image + 0x620000;
    if (!image || !owner || !platform || !sidecar) return 10;
    write_headers(image, 0x200);
    g_sidecar = sidecar;
    *reinterpret_cast<void**>(owner) = platform;
    *reinterpret_cast<UINT64*>(owner + 0xB398) = 0x1122334455667788ull;
    *reinterpret_cast<void**>(image + 0x3326340) = mode_state;
    *reinterpret_cast<unsigned char*>(mode_state + 0xAC4D9) = 1;
    *reinterpret_cast<void**>(image + 0x3326E48) = enum_root;
    *reinterpret_cast<DWORD*>(enum_root + 4) = 0;
    *reinterpret_cast<void**>(image + 0x3326308) = lookup_root;
    *reinterpret_cast<void**>(lookup_root + 0xF8) = lookup_object;
    *reinterpret_cast<void**>(lookup_object + 0x118) = reinterpret_cast<void*>(&fake_lookup);
    // A tiny executable body at the captured direct status RVA: return zero.
    unsigned char status_code[] = {0xB8,0,0,0,0,0xC3};
    std::memcpy(image + 0x20BDE78, status_code, sizeof(status_code));
    EP_CONSUMER_CALLBACKS callbacks{};
    if (ep_consumer_native_get_callbacks(&callbacks) != EP_CONSUMER_NATIVE_NOT_BOUND) return 11;
    if (ep_consumer_native_bind(25480438u, reinterpret_cast<HMODULE>(image), &sidecar_resolver) != EP_CONSUMER_NATIVE_OK) return 12;
    if (ep_consumer_native_get_callbacks(&callbacks) != EP_CONSUMER_NATIVE_OK) return 13;
    if (!callbacks.resolver || !callbacks.mode || !callbacks.identity || !callbacks.lookup || !callbacks.status) return 14;
    auto resolver = reinterpret_cast<void* (__cdecl *)(void*)>(callbacks.resolver);
    auto mode = reinterpret_cast<int (__cdecl *)(void*)>(callbacks.mode);
    auto identity = reinterpret_cast<unsigned long long (__cdecl *)(void*)>(callbacks.identity);
    auto lookup = reinterpret_cast<void* (__cdecl *)(void*, unsigned long long, void*)>(callbacks.lookup);
    auto status = reinterpret_cast<int (__cdecl *)(void*)>(callbacks.status);
    if (resolver(owner) != sidecar || mode(owner) != 1 || identity(owner) != 0x1122334455667788ull) return 15;
    if (lookup(platform, 3, owner) != reinterpret_cast<void*>(3)) return 16;
    if (lookup(platform, 9, owner) != nullptr || status(reinterpret_cast<void*>(1)) != 0) return 17;
    if (ep_consumer_native_unbind() != EP_CONSUMER_NATIVE_OK) return 18;
    if (ep_consumer_native_get_callbacks(&callbacks) != EP_CONSUMER_NATIVE_NOT_BOUND) return 19;
    VirtualFree(sidecar, 0, MEM_RELEASE); VirtualFree(platform, 0, MEM_RELEASE);
    VirtualFree(owner, 0, MEM_RELEASE); VirtualFree(image, 0, MEM_RELEASE);
    std::puts("ep_consumer_native_callbacks_synthetic_passed");
    return 0;
}
