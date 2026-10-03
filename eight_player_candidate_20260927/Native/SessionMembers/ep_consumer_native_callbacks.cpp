#include "ep_consumer_native_callbacks.h"

#include <atomic>
#include <cstdint>
#include <cstring>
#include <limits>

namespace {
constexpr unsigned long kBuild = 25480438u;
constexpr uintptr_t kModeFlagGlobalRva = 0x3326340;
constexpr uintptr_t kModeFlagOffset = 0xAC4D9;
constexpr uintptr_t kModeEnumGlobalRva = 0x3326E48;
constexpr uintptr_t kModeEnumOffset = 0x04;
constexpr uintptr_t kLookupGlobalRva = 0x3326308;
constexpr uintptr_t kLookupObjectOffset = 0xF8;
constexpr uintptr_t kLookupVtableOffset = 0x118;
constexpr uintptr_t kStatusRva = 0x20BDE78;
constexpr uintptr_t kTagRva = 0x2264210;
constexpr uintptr_t kIdentityOffset = 0xB398;
constexpr unsigned long kImageTimestamp = 1790161983u;
constexpr unsigned long kImageSize = 74727424u;

struct Binding {
    uintptr_t game{};
    EP_CONSUMER_SIDECAR_RESOLVER resolver{};
};
std::atomic<uintptr_t> g_game{0};
std::atomic<uintptr_t> g_resolver{0};

bool add_ok(uintptr_t base, uintptr_t offset) {
    return base && offset <= (std::numeric_limits<uintptr_t>::max() - base);
}

template <typename T>
bool read_ptr(uintptr_t address, T& out) {
    if (!address) return false;
    __try {
        std::memcpy(&out, reinterpret_cast<const void*>(address), sizeof(out));
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool module_identity(HMODULE module) {
    if (!module) return false;
    const uintptr_t base = reinterpret_cast<uintptr_t>(module);
    uint16_t mz{}; uint32_t pe{}; uint32_t signature{}; uint16_t machine{};
    uint32_t timestamp{}; uint16_t magic{}; uint32_t image_size{};
    if (!read_ptr(base, mz) || mz != 0x5a4d ||
        !read_ptr(base + 0x3c, pe) || pe > 0x1000 ||
        !add_ok(base, pe) || !read_ptr(base + pe, signature) || signature != 0x4550 ||
        !read_ptr(base + pe + 4, machine) || machine != 0x8664 ||
        !read_ptr(base + pe + 8, timestamp) || timestamp != kImageTimestamp ||
        !read_ptr(base + pe + 24, magic) || magic != 0x20b ||
        !read_ptr(base + pe + 24 + 56, image_size) || image_size != kImageSize) return false;
    return true;
}

bool bound(Binding& out) {
    const uintptr_t game = g_game.load(std::memory_order_acquire);
    const auto resolver = reinterpret_cast<EP_CONSUMER_SIDECAR_RESOLVER>(g_resolver.load(std::memory_order_acquire));
    if (!game || !resolver) return false;
    out = {game, resolver};
    return true;
}

bool mode_predicate(uintptr_t game) {
    uintptr_t state{};
    if (!add_ok(game, kModeFlagGlobalRva) || !read_ptr(game + kModeFlagGlobalRva, state) || !state) return false;
    unsigned char flag{};
    if (!read_ptr(state + kModeFlagOffset, flag)) return false;
    if (flag != 0) return true;
    uintptr_t enum_root{}; unsigned long value{};
    if (!add_ok(game, kModeEnumGlobalRva) || !read_ptr(game + kModeEnumGlobalRva, enum_root) || !enum_root ||
        !read_ptr(enum_root + kModeEnumOffset, value)) return false;
    unsigned long mapped = 5;
    if (value == 0) mapped = 2;
    else if (value == 1) mapped = 1;
    else if (value == 2) mapped = 4;
    else if (value == 4) mapped = 3;
    return mapped == 0;
}

extern "C" void* __cdecl native_resolver(void* owner) {
    Binding b{};
    if (!owner || !bound(b)) return nullptr;
    __try { return b.resolver(owner); } __except (EXCEPTION_EXECUTE_HANDLER) { return nullptr; }
}

extern "C" int __cdecl native_mode(void* owner) {
    Binding b{}; if (!owner || !bound(b)) return 0;
    __try { return mode_predicate(b.game) ? 1 : 0; } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
}

extern "C" unsigned long long __cdecl native_identity(void* owner) {
    Binding b{}; unsigned long long identity{};
    if (!owner || !bound(b)) return 0;
    __try {
        if (!read_ptr(reinterpret_cast<uintptr_t>(owner) + kIdentityOffset, identity)) return 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 0; }
    return identity;
}

extern "C" void* __cdecl native_lookup(void* platform, unsigned long long id, void* owner) {
    Binding b{}; if (!platform || !owner || !bound(b)) return nullptr;
    __try {
        uintptr_t root{}, lookup_object{}, vtable{}, fn_address{};
        if (!add_ok(b.game, kLookupGlobalRva) || !read_ptr(b.game + kLookupGlobalRva, root) || !root ||
            !read_ptr(root + kLookupObjectOffset, lookup_object) || !lookup_object ||
            !read_ptr(lookup_object + kLookupVtableOffset, fn_address) || !fn_address ||
            !add_ok(b.game, kTagRva)) return nullptr;
        using lookup_fn = void* (__cdecl *)(void*, unsigned long long, const void*);
        return reinterpret_cast<lookup_fn>(fn_address)(platform, id,
            reinterpret_cast<const void*>(b.game + kTagRva));
    } __except (EXCEPTION_EXECUTE_HANDLER) { return nullptr; }
}

extern "C" int __cdecl native_status(void* token) {
    Binding b{}; if (!token || !bound(b) || !add_ok(b.game, kStatusRva)) return 1;
    __try {
        using status_fn = int (__cdecl *)(void*);
        return reinterpret_cast<status_fn>(b.game + kStatusRva)(token);
    } __except (EXCEPTION_EXECUTE_HANDLER) { return 1; }
}
}

extern "C" EP_CONSUMER_NATIVE_STATUS __cdecl ep_consumer_native_bind(
    unsigned long steam_build, HMODULE game_module,
    EP_CONSUMER_SIDECAR_RESOLVER sidecar_resolver) {
    if (!game_module || !sidecar_resolver) return EP_CONSUMER_NATIVE_INVALID_ARGUMENT;
    if (steam_build != kBuild) return EP_CONSUMER_NATIVE_BUILD_MISMATCH;
    if (!module_identity(game_module)) return EP_CONSUMER_NATIVE_IMAGE_MISMATCH;
    g_game.store(reinterpret_cast<uintptr_t>(game_module), std::memory_order_release);
    g_resolver.store(reinterpret_cast<uintptr_t>(sidecar_resolver), std::memory_order_release);
    return EP_CONSUMER_NATIVE_OK;
}

extern "C" EP_CONSUMER_NATIVE_STATUS __cdecl ep_consumer_native_unbind() {
    g_resolver.store(0, std::memory_order_release);
    g_game.store(0, std::memory_order_release);
    return EP_CONSUMER_NATIVE_OK;
}

extern "C" EP_CONSUMER_NATIVE_STATUS __cdecl ep_consumer_native_get_callbacks(
    EP_CONSUMER_CALLBACKS* out_callbacks) {
    if (!out_callbacks) return EP_CONSUMER_NATIVE_INVALID_ARGUMENT;
    Binding b{};
    if (!bound(b)) { std::memset(out_callbacks, 0, sizeof(*out_callbacks)); return EP_CONSUMER_NATIVE_NOT_BOUND; }
    out_callbacks->resolver = reinterpret_cast<void*>(&native_resolver);
    out_callbacks->mode = reinterpret_cast<void*>(&native_mode);
    out_callbacks->identity = reinterpret_cast<void*>(&native_identity);
    out_callbacks->lookup = reinterpret_cast<void*>(&native_lookup);
    out_callbacks->status = reinterpret_cast<void*>(&native_status);
    return EP_CONSUMER_NATIVE_OK;
}

extern "C" unsigned long __cdecl ep_consumer_native_build() { return kBuild; }
