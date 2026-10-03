#include "ep_midgate_executor.h"

#include <cstring>
#include <limits>

namespace {
constexpr DWORD kBuild = 25480438u;
constexpr DWORD kCapacityRva = 0x108C18Fu;
constexpr DWORD kCapacityEndRva = 0x108C1B5u;
constexpr DWORD kCapacityContinuationRva = 0x108C1BAu;
constexpr DWORD kAllocatorRva = 0x108C3D8u;
constexpr DWORD kAllocatorEndRva = 0x108C3E7u;
constexpr DWORD kAllocatorContinuationRva = 0x108C3F7u;
constexpr SIZE_T kCapacitySpan = kCapacityEndRva - kCapacityRva;
constexpr SIZE_T kAllocatorSpan = kAllocatorEndRva - kAllocatorRva;
constexpr SIZE_T kCapacityCodeSize = 77;
constexpr SIZE_T kAllocatorCodeSize = 63;
constexpr SIZE_T kUnwindCapacitySize = 20;
constexpr SIZE_T kUnwindAllocatorSize = 12;
constexpr SIZE_T kCapacityUnwindOffset = (kCapacityCodeSize + 3u) & ~SIZE_T(3u);
constexpr SIZE_T kAllocatorUnwindOffset = (kAllocatorCodeSize + 3u) & ~SIZE_T(3u);
constexpr DWORD kImageTimestamp = 1790161983u;
constexpr DWORD kImageSize = 74727424u;

constexpr BYTE kCapacityExpected[kCapacitySpan] = {
    0x41,0x8b,0xc6,0x49,0x39,0x41,0x58,0x0f,0x95,0xc0,0xff,0xc4,
    0x4d,0x39,0xb1,0x90,0x00,0x00,0x00,0x8d,0x48,0x01,0x0f,0x44,
    0xc8,0x4d,0x39,0xb1,0xc8,0x00,0x00,0x00,0x8d,0x41,0x01,0x0f,
    0x44,0xc1};
constexpr BYTE kAllocatorExpected[kAllocatorSpan] = {
    0x44,0x38,0x30,0x74,0x0c,0xff,0xc1,0x48,0xff,0xc0,0x83,0xf9,0x04,0x72,0xf1};
constexpr BYTE kCapacityCode[kCapacityCodeSize] = {
    0x41,0x51,0x41,0x54,0x41,0x55,0x41,0x56,0x41,0x57,0x55,0x48,0x83,0xec,0x20,
    0x4c,0x8b,0xc9,0x41,0x8b,0xd6,0x48,0xb8,0,0,0,0,0,0,0,0,0xff,0xd0,
    0x48,0x83,0xc4,0x20,0x5d,0x41,0x5f,0x41,0x5e,0x41,0x5d,0x41,0x5c,0x41,0x59,
    0x83,0xf8,0x08,0x76,0x05,0xb8,0x08,0x00,0x00,0x00,0xb9,0x08,0x00,0x00,0x00,
    0xff,0x25,0x00,0x00,0x00,0x00,0,0,0,0,0,0,0,0};
constexpr BYTE kAllocatorCode[kAllocatorCodeSize] = {
    0x41,0x51,0x52,0x48,0x83,0xec,0x20,0x4c,0x8b,0xc9,0x41,0x8b,0xd6,
    0x48,0xb8,0,0,0,0,0,0,0,0,0xff,0xd0,0x48,0x83,0xc4,0x20,0x5a,0x41,0x59,
    0x83,0xf8,0x08,0x72,0x0a,0x83,0xf8,0xff,0x74,0x05,0xb8,0xff,0xff,0xff,0xff,
    0x44,0x8b,0xc0,0x49,0xbb,0,0,0,0,0,0,0,0,0x41,0xff,0xe3};
constexpr BYTE kCapacityUnwind[kUnwindCapacitySize] = {
    0x01,0x0f,0x07,0x00,0x0f,0x32,0x0b,0x50,0x0a,0xf0,0x08,0xe0,
    0x06,0xd0,0x04,0xc0,0x02,0x90,0x00,0x00};
constexpr BYTE kAllocatorUnwind[kUnwindAllocatorSize] = {
    0x01,0x07,0x03,0x00,0x07,0x32,0x03,0x20,0x02,0x90,0x00,0x00};
static_assert(sizeof(kCapacityExpected) == kCapacitySpan);
static_assert(sizeof(kAllocatorExpected) == kAllocatorSpan);
static_assert(sizeof(kCapacityCode) == kCapacityCodeSize);
static_assert(sizeof(kAllocatorCode) == kAllocatorCodeSize);

bool add_ok(uintptr_t base, uintptr_t offset) {
    return base != 0 && offset <= (std::numeric_limits<uintptr_t>::max() - base);
}

bool read_bytes(uintptr_t address, void* out, SIZE_T size) {
    if (!address || !out || !size) return false;
    __try {
        std::memcpy(out, reinterpret_cast<const void*>(address), size);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool module_identity(HMODULE module) {
    if (!module) return false;
    const uintptr_t base = reinterpret_cast<uintptr_t>(module);
    WORD mz{}; DWORD pe_offset{}; DWORD signature{}; WORD machine{};
    DWORD timestamp{}; WORD magic{}; DWORD image_size{};
    if (!read_bytes(base, &mz, sizeof(mz)) || mz != 0x5a4d ||
        !read_bytes(base + 0x3c, &pe_offset, sizeof(pe_offset)) || pe_offset > 0x1000 ||
        !add_ok(base, pe_offset) ||
        !read_bytes(base + pe_offset, &signature, sizeof(signature)) || signature != 0x4550 ||
        !read_bytes(base + pe_offset + 4, &machine, sizeof(machine)) || machine != 0x8664 ||
        !read_bytes(base + pe_offset + 8, &timestamp, sizeof(timestamp)) || timestamp != kImageTimestamp ||
        !read_bytes(base + pe_offset + 24, &magic, sizeof(magic)) || magic != 0x20b ||
        !read_bytes(base + pe_offset + 24 + 56, &image_size, sizeof(image_size)) || image_size != kImageSize) {
        return false;
    }
    return true;
}

bool readable(const void* address, SIZE_T size) {
    if (!address || size == 0) return false;
    const uintptr_t begin = reinterpret_cast<uintptr_t>(address);
    if (size > UINTPTR_MAX - begin) return false;
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(address, &mbi, sizeof(mbi)) != sizeof(mbi) || mbi.State != MEM_COMMIT) return false;
    const DWORD protect = mbi.Protect & 0xffu;
    if (protect == PAGE_NOACCESS || protect == PAGE_GUARD) return false;
    const uintptr_t region = reinterpret_cast<uintptr_t>(mbi.BaseAddress);
    if (mbi.RegionSize > UINTPTR_MAX - region) return false;
    return begin >= region && begin + size <= region + mbi.RegionSize;
}

bool matches(const BYTE* address, const BYTE* expected, SIZE_T size) {
    if (!readable(address, size)) return false;
    __try { return std::memcmp(address, expected, size) == 0; }
    __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}

void write_qword(BYTE* code, SIZE_T offset, uintptr_t value) {
    const UINT64 v = static_cast<UINT64>(value);
    std::memcpy(code + offset, &v, sizeof(v));
}

void detour_bytes(BYTE* out, void* destination, SIZE_T span) {
    out[0] = 0xff; out[1] = 0x25; out[2] = 0; out[3] = 0; out[4] = 0; out[5] = 0;
    const UINT64 address = reinterpret_cast<UINT64>(destination);
    std::memcpy(out + 6, &address, sizeof(address));
    for (SIZE_T i = 14; i < span; ++i) out[i] = 0x90;
}

void release_site(EP_MIDGATE_SITE_HOOK* site) {
    if (!site) return;
    if (site->runtime_registered) {
        RtlDeleteFunctionTable(&site->runtime_function);
        site->runtime_registered = FALSE;
    }
    if (site->code) VirtualFree(site->code, 0, MEM_RELEASE);
    site->code = nullptr;
}

bool allocate_site(EP_MIDGATE_SITE_HOOK* site, const BYTE* template_bytes, SIZE_T code_size,
                   const BYTE* unwind, SIZE_T unwind_size, SIZE_T unwind_offset,
                   void* helper, void* continuation, SIZE_T helper_offset, SIZE_T continuation_offset) {
    if (!site || !template_bytes || !unwind || !helper || !continuation) return false;
    const SIZE_T allocation = unwind_offset + unwind_size;
    BYTE* code = static_cast<BYTE*>(VirtualAlloc(nullptr, allocation,
        MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (!code) return false;
    std::memcpy(code, template_bytes, code_size);
    write_qword(code, helper_offset, reinterpret_cast<uintptr_t>(helper));
    write_qword(code, continuation_offset, reinterpret_cast<uintptr_t>(continuation));
    std::memcpy(code + unwind_offset, unwind, unwind_size);
    site->code = code;
    site->code_size = code_size;
    site->runtime_function = {0, static_cast<DWORD>(code_size), static_cast<DWORD>(unwind_offset)};
    if (!RtlAddFunctionTable(&site->runtime_function, 1, reinterpret_cast<DWORD64>(code))) {
        release_site(site);
        return false;
    }
    site->runtime_registered = TRUE;
    return true;
}

bool install_site(EP_MIDGATE_SITE_HOOK* site, BYTE* target, const BYTE* expected, SIZE_T span,
                  const BYTE* template_bytes, SIZE_T code_size, const BYTE* unwind, SIZE_T unwind_size,
                  SIZE_T unwind_offset, void* helper, void* continuation,
                  SIZE_T helper_offset, SIZE_T continuation_offset) {
    if (!site || !target || !expected || !matches(target, expected, span)) return false;
    std::memset(site, 0, sizeof(*site));
    site->target = target;
    site->stolen_size = span;
    std::memcpy(site->original, expected, span);
    if (!allocate_site(site, template_bytes, code_size, unwind, unwind_size, unwind_offset,
                       helper, continuation, helper_offset, continuation_offset)) return false;
    DWORD old = 0;
    if (!VirtualProtect(target, span, PAGE_EXECUTE_READWRITE, &old)) {
        release_site(site);
        return false;
    }
    BYTE patch[38]{};
    detour_bytes(patch, site->code, span);
    if (!matches(target, expected, span)) {
        DWORD ignored = 0; VirtualProtect(target, span, old, &ignored);
        release_site(site);
        return false;
    }
    std::memcpy(target, patch, span);
    FlushInstructionCache(GetCurrentProcess(), target, span);
    DWORD ignored = 0;
    const BOOL restored = VirtualProtect(target, span, old, &ignored);
    site->target_protection = old;
    site->installed = restored != FALSE;
    if (!site->installed) {
        // Best-effort exact rollback while the page is still writable if the
        // protection restore itself failed.
        DWORD rollback_old = 0;
        if (VirtualProtect(target, span, PAGE_EXECUTE_READWRITE, &rollback_old)) {
            std::memcpy(target, expected, span);
            FlushInstructionCache(GetCurrentProcess(), target, span);
            VirtualProtect(target, span, old, &ignored);
        }
        release_site(site);
        return false;
    }
    return true;
}

bool owns_detour(const EP_MIDGATE_SITE_HOOK& site) {
    if (!site.installed || !site.target || !site.code) return false;
    BYTE patch[38]{};
    detour_bytes(patch, site.code, site.stolen_size);
    return matches(static_cast<const BYTE*>(site.target), patch, site.stolen_size);
}

bool restore_site(EP_MIDGATE_SITE_HOOK* site) {
    if (!site || !owns_detour(*site)) return false;
    DWORD old = 0;
    if (!VirtualProtect(site->target, site->stolen_size, PAGE_EXECUTE_READWRITE, &old)) return false;
    std::memcpy(site->target, site->original, site->stolen_size);
    FlushInstructionCache(GetCurrentProcess(), site->target, site->stolen_size);
    DWORD ignored = 0;
    if (!VirtualProtect(site->target, site->stolen_size, old, &ignored)) return false;
    site->installed = FALSE;
    release_site(site);
    site->target = nullptr;
    return true;
}
}

extern "C" BOOL __cdecl ep_midgate_install(
    DWORD steam_build, HMODULE game_module,
    const EP_MIDGATE_CALLBACKS* callbacks, EP_MIDGATE_HOOK* out_hook) {
    if (!out_hook || !game_module || !callbacks || !callbacks->capacity || !callbacks->allocator ||
        steam_build != kBuild || !module_identity(game_module)) return FALSE;
    const uintptr_t base = reinterpret_cast<uintptr_t>(game_module);
    if (!add_ok(base, kCapacityRva) || !add_ok(base, kAllocatorRva) ||
        !add_ok(base, kCapacityContinuationRva) || !add_ok(base, kAllocatorContinuationRva)) return FALSE;
    auto* capacity_target = reinterpret_cast<BYTE*>(base + kCapacityRva);
    auto* allocator_target = reinterpret_cast<BYTE*>(base + kAllocatorRva);
    if (!matches(capacity_target, kCapacityExpected, kCapacitySpan) ||
        !matches(allocator_target, kAllocatorExpected, kAllocatorSpan)) return FALSE;
    std::memset(out_hook, 0, sizeof(*out_hook));
    out_hook->callbacks = *callbacks;
    auto* capacity_continuation = reinterpret_cast<void*>(base + kCapacityContinuationRva);
    auto* allocator_continuation = reinterpret_cast<void*>(base + kAllocatorContinuationRva);
    if (!install_site(&out_hook->capacity, capacity_target, kCapacityExpected, kCapacitySpan,
                      kCapacityCode, kCapacityCodeSize, kCapacityUnwind, kUnwindCapacitySize,
                      kCapacityUnwindOffset, reinterpret_cast<void*>(callbacks->capacity),
                      capacity_continuation, 23, 69)) return FALSE;
    if (!install_site(&out_hook->allocator, allocator_target, kAllocatorExpected, kAllocatorSpan,
                      kAllocatorCode, kAllocatorCodeSize, kAllocatorUnwind, kUnwindAllocatorSize,
                      kAllocatorUnwindOffset, reinterpret_cast<void*>(callbacks->allocator),
                      allocator_continuation, 15, 52)) {
        restore_site(&out_hook->capacity);
        return FALSE;
    }
    out_hook->installed = TRUE;
    return TRUE;
}

extern "C" BOOL __cdecl ep_midgate_remove(EP_MIDGATE_HOOK* hook) {
    if (!hook || !hook->installed || !owns_detour(hook->capacity) || !owns_detour(hook->allocator)) return FALSE;
    if (!restore_site(&hook->allocator)) return FALSE;
    if (!restore_site(&hook->capacity)) return FALSE;
    hook->installed = FALSE;
    return TRUE;
}

extern "C" DWORD __cdecl ep_midgate_expected_build() { return kBuild; }
extern "C" DWORD __cdecl ep_midgate_capacity_rva() { return kCapacityRva; }
extern "C" DWORD __cdecl ep_midgate_allocator_rva() { return kAllocatorRva; }
extern "C" DWORD __cdecl ep_midgate_capacity_span() { return static_cast<DWORD>(kCapacitySpan); }
extern "C" DWORD __cdecl ep_midgate_allocator_span() { return static_cast<DWORD>(kAllocatorSpan); }
extern "C" DWORD __cdecl ep_midgate_capacity_code_size() { return static_cast<DWORD>(kCapacityCodeSize); }
extern "C" DWORD __cdecl ep_midgate_allocator_code_size() { return static_cast<DWORD>(kAllocatorCodeSize); }
