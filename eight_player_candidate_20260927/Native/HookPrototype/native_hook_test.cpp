#include <windows.h>
#include <cstdio>
#include <cstring>

#include "native_hook_scaffold.h"

using InstallFn = BOOL(__cdecl*)(void*, void*, SIZE_T, EP_HOOK*);
using RemoveFn = BOOL(__cdecl*)(EP_HOOK*);
using VerifyHostFn = BOOL(__cdecl*)(HMODULE);
using StolenLengthFn = DWORD(__cdecl*)();
using RelocateFn = BOOL(__cdecl*)(const BYTE*, SIZE_T, UINT64, BYTE*, SIZE_T, UINT64, SIZE_T*);

static EP_HOOK g_hook{};
static int g_calls = 0;
static int (__cdecl* g_original)(int) = nullptr;

extern "C" __declspec(noinline) int __cdecl synthetic_detour(int x) {
    ++g_calls;
    return g_original ? g_original(x) + 1000 : -1;
}

int main() {
    // 14 bytes of instruction-aligned code followed by RET.  The target is
    // allocated as RWX only for this synthetic test; no game module is loaded
    // or modified.
    BYTE code[] = {
        0x8B, 0xC1,                         // mov eax, ecx
        0x83, 0xC0, 0x07,                   // add eax, 7
        0x83, 0xC0, 0x01,                   // add eax, 1
        0x90, 0x90, 0x90, 0x90, 0x90, 0x90, // six NOPs: 14 bytes total
        0xC3                                // ret
    };
    void* target = VirtualAlloc(nullptr, sizeof(code), MEM_COMMIT | MEM_RESERVE,
                                PAGE_EXECUTE_READWRITE);
    if (!target) return 10;
    std::memcpy(target, code, sizeof(code));
    FlushInstructionCache(GetCurrentProcess(), target, sizeof(code));
    auto fn = reinterpret_cast<int(__cdecl*)(int)>(target);
    if (fn(5) != 13) return 11;

    HMODULE dll = LoadLibraryW(L"native_hook_scaffold.dll");
    if (!dll) return 12;
    auto install = reinterpret_cast<InstallFn>(GetProcAddress(dll, "ep_install_hook"));
    auto remove = reinterpret_cast<RemoveFn>(GetProcAddress(dll, "ep_remove_hook"));
    auto verify_host = reinterpret_cast<VerifyHostFn>(GetProcAddress(dll, "ep_verify_host_join_site"));
    auto stolen_length = reinterpret_cast<StolenLengthFn>(GetProcAddress(dll, "ep_host_join_stolen_length"));
    auto relocate = reinterpret_cast<RelocateFn>(GetProcAddress(dll, "ep_relocate_block"));
    if (!install || !remove || !verify_host || !stolen_length || !relocate) return 13;
    if (stolen_length() != 18) return 18;
    // The validator is exercised against a synthetic module-shaped mapping.
    // It verifies the exact captured prologue and does not write it.
    SIZE_T fake_size = 0x108BC70 + 18;
    BYTE* fake_module = static_cast<BYTE*>(VirtualAlloc(nullptr, fake_size,
        MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (!fake_module) return 19;
    const BYTE prologue[] = {0x40,0x55,0x53,0x56,0x41,0x54,0x48,0x8D,0x6C,0x24,0xE9,
                             0x48,0x81,0xEC,0xC8,0x00,0x00,0x00};
    std::memcpy(fake_module + 0x108BC70, prologue, sizeof(prologue));
    if (!verify_host(reinterpret_cast<HMODULE>(fake_module))) return 20;
    fake_module[0x108BC70 + 16] ^= 0x01;
    if (verify_host(reinterpret_cast<HMODULE>(fake_module))) return 21;
    VirtualFree(fake_module, 0, MEM_RELEASE);

    // RIP-relative load keeps the same absolute target after relocation.
    const BYTE rip_load[] = {0x48, 0x8B, 0x05, 0x78, 0x56, 0x34, 0x12};
    BYTE rip_relocated[16]{};
    SIZE_T relocated_length = 0;
    constexpr UINT64 rip_source = 0x0000000010000000ULL;
    constexpr UINT64 rip_destination = 0x0000000020000000ULL;
    if (!relocate(rip_load, sizeof(rip_load), rip_source, rip_relocated,
                  sizeof(rip_relocated), rip_destination, &relocated_length) ||
        relocated_length != sizeof(rip_load) ||
        std::memcmp(rip_relocated, rip_load, 3) != 0) return 22;
    INT32 old_rip_disp = 0;
    INT32 new_rip_disp = 0;
    std::memcpy(&old_rip_disp, rip_load + 3, sizeof(old_rip_disp));
    std::memcpy(&new_rip_disp, rip_relocated + 3, sizeof(new_rip_disp));
    const UINT64 old_target = rip_source + sizeof(rip_load) + static_cast<INT64>(old_rip_disp);
    const UINT64 new_target = rip_destination + sizeof(rip_load) + static_cast<INT64>(new_rip_disp);
    if (old_target != new_target) return 23;

    // rel32 CALL is adjusted to the same absolute destination.
    const BYTE rel_call[] = {0xE8, 0x10, 0x00, 0x00, 0x00};
    BYTE call_relocated[8]{};
    if (!relocate(rel_call, sizeof(rel_call), rip_source, call_relocated,
                  sizeof(call_relocated), rip_destination, &relocated_length) ||
        relocated_length != sizeof(rel_call) || call_relocated[0] != 0xE8) return 24;
    INT32 old_call_disp = 0;
    INT32 new_call_disp = 0;
    std::memcpy(&old_call_disp, rel_call + 1, sizeof(old_call_disp));
    std::memcpy(&new_call_disp, call_relocated + 1, sizeof(new_call_disp));
    const UINT64 old_call_target = rip_source + 5 + static_cast<INT64>(old_call_disp);
    const UINT64 new_call_target = rip_destination + 5 + static_cast<INT64>(new_call_disp);
    if (old_call_target != new_call_target) return 25;

    // Short and conditional branches are intentionally rejected because this
    // bounded helper cannot prove their continuation contract.
    const BYTE short_jump[] = {0xEB, 0x02, 0x90, 0x90};
    const BYTE conditional_jump[] = {0x0F, 0x85, 0x10, 0x00, 0x00, 0x00};
    if (relocate(short_jump, sizeof(short_jump), rip_source, rip_relocated,
                 sizeof(rip_relocated), rip_destination, &relocated_length) ||
        relocate(conditional_jump, sizeof(conditional_jump), rip_source,
                 rip_relocated, sizeof(rip_relocated), rip_destination,
                 &relocated_length)) return 26;

    if (!install(target, reinterpret_cast<void*>(&synthetic_detour), 14, &g_hook)) return 14;
    g_original = reinterpret_cast<int(__cdecl*)(int)>(g_hook.trampoline);
    if (fn(5) != 1013 || g_calls != 1) return 15;
    if (!remove(&g_hook)) return 16;
    g_original = nullptr;
    if (fn(5) != 13) return 17;
    VirtualFree(target, 0, MEM_RELEASE);
    FreeLibrary(dll);
    std::puts("native_hook_scaffold_synthetic_passed");
    return 0;
}
