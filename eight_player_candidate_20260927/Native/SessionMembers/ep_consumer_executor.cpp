#include "ep_consumer_executor.h"
#include <cstring>
#include <cstdint>

namespace {
constexpr DWORD kBuild = 25480438u;
constexpr DWORD kEntryRva = 0x1093590u;
constexpr SIZE_T kCodeSize = 270;
constexpr SIZE_T kStolen = 14;
constexpr SIZE_T kUnwindSize = 24;
constexpr SIZE_T kUnwindOffset = (kCodeSize + 3u) & ~SIZE_T(3u);
constexpr BYTE kDetourPrefix[] = {0xff, 0x25, 0, 0, 0, 0};
constexpr SIZE_T kCallbackOffset[] = {30, 69, 122, 170, 200};
constexpr BYTE kUnwind[] = {
    0x01, 0x10, 0x09, 0x00,
    0x10, 0x42, 0x0c, 0xf0, 0x0a, 0xe0, 0x08, 0xd0,
    0x06, 0xc0, 0x04, 0x70, 0x03, 0x60, 0x02, 0x50,
    0x01, 0x30, 0x00, 0x00,
};
constexpr BYTE kCode[] = {
  0x53,0x55,0x56,0x57,0x41,0x54,0x41,0x55,0x41,0x56,0x41,0x57,0x48,0x83,0xEC,0x28,0x48,0x85,0xC9,0x0F,0x84,0xDF,0x00,0x00,0x00,0x48,0x89,0xCB,0x48,0xB8,0,0,0,0,0,0,0,0,0xFF,0xD0,0x48,0x85,0xC0,0x0F,0x84,0xC7,0x00,0x00,0x00,0x49,0x89,0xC4,0x45,0x8B,0x6C,0x24,0x40,0x41,0x83,0xFD,0x08,0x0F,0x87,0xB5,0x00,0x00,0x00,0x48,0xB8,0,0,0,0,0,0,0,0,0x48,0x89,0xD9,0xFF,0xD0,0x44,0x0F,0xB6,0xF8,0x48,0x8B,0x3B,0x48,0x85,0xFF,0x0F,0x84,0x8E,0x00,0x00,0x00,0x80,0xBB,0xA6,0x1B,0x00,0x00,0x00,0x0F,0x84,0x89,0x00,0x00,0x00,0x45,0x85,0xED,0x0F,0x84,0x80,0x00,0x00,0x00,0x48,0xB8,0,0,0,0,0,0,0,0,0x48,0x89,0xD9,0xFF,0xD0,0x48,0x89,0xC6,0xBD,0x01,0x00,0x00,0x00,0x45,0x33,0xF6,0x45,0x3B,0xF5,0x0F,0x83,0x4C,0x00,0x00,0x00,0x4B,0x8B,0x14,0xF4,0x48,0x39,0xF2,0x0F,0x84,0x37,0x00,0x00,0x00,0x48,0xB8,0,0,0,0,0,0,0,0,0x48,0x89,0xF9,0x49,0x89,0xD8,0xFF,0xD0,0x48,0x85,0xC0,0x0F,0x84,0x1C,0x00,0x00,0x00,0x48,0x89,0xC1,0x48,0xB8,0,0,0,0,0,0,0,0,0xFF,0xD0,0x85,0xC0,0x0F,0x94,0xC0,0x0F,0xB6,0xC0,0x41,0x21,0xC7,0xFF,0xC5,0x41,0xFF,0xC6,0xE9,0xAB,0xFF,0xFF,0xFF,0x41,0x3B,0xED,0x0F,0x85,0x08,0x00,0x00,0x00,0x44,0x89,0xF8,0xE9,0x05,0x00,0x00,0x00,0xB8,0xFF,0xFF,0xFF,0xFF,0x48,0x83,0xC4,0x28,0x41,0x5F,0x41,0x5E,0x41,0x5D,0x41,0x5C,0x5F,0x5E,0x5D,0x5B,0xC3
};
static_assert(sizeof(kCode) == kCodeSize);
static_assert(sizeof(kUnwind) == kUnwindSize);

bool executable(void* address, SIZE_T size, DWORD* old_protect) {
    MEMORY_BASIC_INFORMATION mbi{};
    if (!address || !VirtualQuery(address, &mbi, sizeof(mbi)) || mbi.State != MEM_COMMIT) return false;
    const DWORD p = mbi.Protect & 0xff;
    if (p != PAGE_EXECUTE && p != PAGE_EXECUTE_READ && p != PAGE_EXECUTE_READWRITE && p != PAGE_EXECUTE_WRITECOPY) return false;
    return VirtualProtect(address, size, PAGE_EXECUTE_READWRITE, old_protect) != FALSE;
}

bool expected(const BYTE* address, const BYTE* bytes, SIZE_T size) {
    __try { return std::memcmp(address, bytes, size) == 0; }
    __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}

bool callback_set(const EP_CONSUMER_CALLBACKS& c) {
    return c.resolver && c.mode && c.identity && c.lookup && c.status;
}

void fill_detour(BYTE* out, void* destination) {
    std::memcpy(out, kDetourPrefix, sizeof(kDetourPrefix));
    const UINT64 value = reinterpret_cast<UINT64>(destination);
    std::memcpy(out + sizeof(kDetourPrefix), &value, sizeof(value));
}

void release_code(EP_CONSUMER_HOOK* hook) {
    if (!hook) return;
    if (hook->runtime_registered) {
        RtlDeleteFunctionTable(&hook->runtime_function);
        hook->runtime_registered = FALSE;
    }
    if (hook->code) VirtualFree(hook->code, 0, MEM_RELEASE);
    hook->code = nullptr;
}
}

extern "C" BOOL __cdecl ep_consumer_install(
    DWORD steam_build, HMODULE game_module, DWORD entry_rva,
    const BYTE* expected_entry, SIZE_T expected_size,
    const EP_CONSUMER_CALLBACKS* callbacks, EP_CONSUMER_HOOK* out_hook) {
    if (!out_hook || !game_module || !expected_entry || expected_size != kStolen ||
        !callbacks || !callback_set(*callbacks) || steam_build != kBuild || entry_rva != kEntryRva) return FALSE;
    const auto target = reinterpret_cast<BYTE*>(game_module) + entry_rva;
    if (!expected(target, expected_entry, expected_size)) return FALSE;
    std::memset(out_hook, 0, sizeof(*out_hook));
    out_hook->target = target;
    out_hook->stolen_size = kStolen;
    std::memcpy(out_hook->original, target, kStolen);
    const SIZE_T allocation = kUnwindOffset + kUnwindSize;
    BYTE* code = static_cast<BYTE*>(VirtualAlloc(nullptr, allocation, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (!code) return FALSE;
    std::memcpy(code, kCode, kCodeSize);
    const void* callback_values[] = {callbacks->resolver, callbacks->mode, callbacks->identity, callbacks->lookup, callbacks->status};
    for (SIZE_T i = 0; i < 5; ++i) std::memcpy(code + kCallbackOffset[i], &callback_values[i], sizeof(callback_values[i]));
    std::memcpy(code + kUnwindOffset, kUnwind, kUnwindSize);
    out_hook->code = code; out_hook->code_size = kCodeSize;
    out_hook->runtime_function = {0, static_cast<DWORD>(kCodeSize), static_cast<DWORD>(kUnwindOffset)};
    if (!RtlAddFunctionTable(&out_hook->runtime_function, 1, reinterpret_cast<DWORD64>(code))) { release_code(out_hook); return FALSE; }
    out_hook->runtime_registered = TRUE;
    DWORD old = 0;
    if (!executable(target, kStolen, &old)) { release_code(out_hook); return FALSE; }
    BYTE detour[kStolen]{}; fill_detour(detour, code);
    if (!expected(target, expected_entry, expected_size)) { DWORD ignored=0; VirtualProtect(target,kStolen,old,&ignored); release_code(out_hook); return FALSE; }
    std::memcpy(target, detour, kStolen);
    FlushInstructionCache(GetCurrentProcess(), target, kStolen);
    DWORD ignored = 0; VirtualProtect(target, kStolen, old, &ignored);
    out_hook->target_protection = old; out_hook->installed = TRUE;
    return TRUE;
}

extern "C" BOOL __cdecl ep_consumer_remove(EP_CONSUMER_HOOK* hook) {
    if (!hook || !hook->installed || !hook->target || !hook->code) return FALSE;
    BYTE detour[14]{}; fill_detour(detour, hook->code);
    if (!expected(static_cast<const BYTE*>(hook->target), detour, sizeof(detour))) return FALSE;
    DWORD old = 0;
    if (!VirtualProtect(hook->target, hook->stolen_size, PAGE_EXECUTE_READWRITE, &old)) return FALSE;
    std::memcpy(hook->target, hook->original, hook->stolen_size);
    FlushInstructionCache(GetCurrentProcess(), hook->target, hook->stolen_size);
    DWORD ignored=0; VirtualProtect(hook->target, hook->stolen_size, old, &ignored);
    release_code(hook); hook->installed=FALSE; hook->target=nullptr;
    return TRUE;
}
extern "C" DWORD __cdecl ep_consumer_expected_build() { return kBuild; }
extern "C" DWORD __cdecl ep_consumer_code_size() { return static_cast<DWORD>(kCodeSize); }
extern "C" DWORD __cdecl ep_consumer_stolen_size() { return static_cast<DWORD>(kStolen); }
