#include "ep_consumer_executor.h"
#include <cstdint>
#include <cstdio>
#include <cstring>

static void* resolver(void* owner) { return *reinterpret_cast<void**>(static_cast<unsigned char*>(owner)+8); }
static int mode(void*) { return 1; }
static UINT64 identity(void*) { return 1; }
static void* lookup(void* platform, UINT64 id, void* owner) {
    return platform && owner && id >= 2 && id <= 8 ? reinterpret_cast<void*>(id) : nullptr;
}
static int status(void* token) { return token ? 0 : 1; }

int main() {
    constexpr DWORD rva = 0x1093590;
    constexpr SIZE_T module_size = 0x10a0000;
    auto module = static_cast<unsigned char*>(VirtualAlloc(nullptr, module_size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    auto owner = static_cast<unsigned char*>(VirtualAlloc(nullptr, 0x2000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    auto platform = static_cast<unsigned char*>(VirtualAlloc(nullptr, 0x2000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    auto sidecar = static_cast<unsigned char*>(VirtualAlloc(nullptr, 0x100, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (!module || !owner || !platform || !sidecar) return 10;
    unsigned char* target = module + rva;
    const unsigned char original[14] = {0xB8,0xFF,0xFF,0xFF,0xFF,0xC3,0x90,0x90,0x90,0x90,0x90,0x90,0x90,0x90};
    std::memcpy(target, original, sizeof(original));
    *reinterpret_cast<void**>(owner) = platform;
    *reinterpret_cast<void**>(owner + 8) = sidecar;
    owner[0x1ba6] = 1;
    for (unsigned i = 0; i < 8; ++i) *reinterpret_cast<UINT64*>(sidecar + i*8) = i + 1;
    *reinterpret_cast<UINT32*>(sidecar + 0x40) = 8;
    EP_CONSUMER_CALLBACKS callbacks{resolver, reinterpret_cast<void*>(&mode), reinterpret_cast<void*>(&identity), reinterpret_cast<void*>(&lookup), reinterpret_cast<void*>(&status)};
    EP_CONSUMER_HOOK hook{};
    if (ep_consumer_expected_build() != 25480438u || ep_consumer_code_size() != 270 || ep_consumer_stolen_size() != 14) return 11;
    if (!ep_consumer_install(25480438u, reinterpret_cast<HMODULE>(module), rva, original, sizeof(original), &callbacks, &hook)) return 12;
    auto fn = reinterpret_cast<int (__cdecl*)(void*)>(target);
    if (fn(owner) != 1) return 13;
    *reinterpret_cast<UINT32*>(sidecar + 0x40) = 9;
    if (fn(owner) != -1) return 14;
    if (!ep_consumer_remove(&hook)) return 15;
    if (fn(owner) != -1) return 16;
    if (ep_consumer_install(25480438u, reinterpret_cast<HMODULE>(module), rva, original, sizeof(original), nullptr, &hook)) return 17;
    target[0] ^= 1;
    if (ep_consumer_install(25480438u, reinterpret_cast<HMODULE>(module), rva, original, sizeof(original), &callbacks, &hook)) return 18;
    VirtualFree(sidecar, 0, MEM_RELEASE); VirtualFree(platform, 0, MEM_RELEASE);
    VirtualFree(owner, 0, MEM_RELEASE); VirtualFree(module, 0, MEM_RELEASE);
    std::puts("ep_consumer_executor_synthetic_passed");
    return 0;
}
