#include "ep_midgate_executor.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <windows.h>

namespace {
constexpr DWORD kCapacityRva = 0x108C18Fu;
constexpr DWORD kCapacityContinuationRva = 0x108C1BAu;
constexpr DWORD kAllocatorRva = 0x108C3D8u;
constexpr DWORD kAllocatorContinuationRva = 0x108C3F7u;
constexpr SIZE_T kImageAlloc = 0x4800000u;
constexpr BYTE kCapacityExpected[38] = {
    0x41,0x8b,0xc6,0x49,0x39,0x41,0x58,0x0f,0x95,0xc0,0xff,0xc4,
    0x4d,0x39,0xb1,0x90,0x00,0x00,0x00,0x8d,0x48,0x01,0x0f,0x44,
    0xc8,0x4d,0x39,0xb1,0xc8,0x00,0x00,0x00,0x8d,0x41,0x01,0x0f,
    0x44,0xc1};
constexpr BYTE kAllocatorExpected[15] = {
    0x44,0x38,0x30,0x74,0x0c,0xff,0xc1,0x48,0xff,0xc0,0x83,0xf9,0x04,0x72,0xf1};
unsigned char* g_owner = nullptr;

uint32_t __cdecl capacity_helper(void* owner, uint32_t) {
    return owner == g_owner ? *reinterpret_cast<uint32_t*>(owner) : 9u;
}
int32_t __cdecl allocator_helper(void* owner, uint32_t start) {
    if (owner != g_owner) return -1;
    return *reinterpret_cast<uint32_t*>(static_cast<unsigned char*>(owner) + 4) == 8u ? 8 : static_cast<int32_t>(start + 2);
}

void write_headers(unsigned char* image) {
    std::memset(image, 0, 0x200);
    *reinterpret_cast<WORD*>(image) = 0x5a4d;
    *reinterpret_cast<DWORD*>(image + 0x3c) = 0x80;
    unsigned char* nt = image + 0x80;
    *reinterpret_cast<DWORD*>(nt) = 0x4550;
    *reinterpret_cast<WORD*>(nt + 4) = 0x8664;
    *reinterpret_cast<DWORD*>(nt + 8) = 1790161983u;
    *reinterpret_cast<WORD*>(nt + 24) = 0x20b;
    *reinterpret_cast<DWORD*>(nt + 24 + 56) = 74727424u;
}

void write_abs_jump(unsigned char* at, void* target) {
    at[0] = 0xff; at[1] = 0x25; at[2] = 0; at[3] = 0; at[4] = 0; at[5] = 0;
    const UINT64 address = reinterpret_cast<UINT64>(target);
    std::memcpy(at + 6, &address, sizeof(address));
}

void write_wrapper(unsigned char* wrapper, void* target, bool capacity) {
    std::memset(wrapper, 0x90, 64);
    SIZE_T offset = 0;
    wrapper[offset++] = 0x41; wrapper[offset++] = 0x56; // preserve r14; target entry is 16-byte aligned
    wrapper[offset++] = 0x49; wrapper[offset++] = 0x89; wrapper[offset++] = 0xc9; // r9 <- rcx
    // Deliberately destroy RCX after saving the owner in R9.  The emitted
    // stub must perform mov rcx,r9 before invoking either helper.
    wrapper[offset++] = 0x31; wrapper[offset++] = 0xc9; // xor ecx,ecx
    if (capacity) {
        wrapper[offset++] = 0x41; wrapper[offset++] = 0x89; wrapper[offset++] = 0xd6; // r14d <- edx
        // The real patch begins before the original ecx=4 instruction.  The
        // emitted capacity stub supplies ecx=8 only after the helper returns,
        // so the helper must receive the untouched owner pointer in rcx.
    } else {
        wrapper[offset++] = 0x45; wrapper[offset++] = 0x89; wrapper[offset++] = 0xc6; // r14d <- r8d
    }
    write_abs_jump(wrapper + offset, target);
}

void write_continuations(unsigned char* image) {
    // The wrapper saves r14 before entering the patched site.  The original
    // continuation consumes that saved register before returning to the
    // wrapper caller.
    unsigned char capacity[] = {0x41,0x5e,0x29,0xc1,0x89,0xc8,0xc3};
    std::memcpy(image + kCapacityContinuationRva, capacity, sizeof(capacity));
    unsigned char allocator[] = {0x41,0x5e,0x44,0x89,0x02,0x44,0x89,0xc0,0xc3};
    std::memcpy(image + kAllocatorContinuationRva, allocator, sizeof(allocator));
}

bool check(bool value, const char* message) {
    if (!value) std::printf("failed:%s\n", message);
    return value;
}

int invoke_capacity(EP_MIDGATE_CAPACITY_HELPER fn, void* owner, uint32_t index) {
    return static_cast<int>(fn(owner, index));
}

int invoke_allocator(int (__cdecl *fn)(void*, void*, uint32_t), void* owner,
                     void* destination, uint32_t start) {
    return fn(owner, destination, start);
}

}

int main() {
    auto* image = static_cast<unsigned char*>(VirtualAlloc(nullptr, kImageAlloc,
        MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    auto* owner = static_cast<unsigned char*>(VirtualAlloc(nullptr, 0x1000,
        MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    auto* destination = static_cast<unsigned char*>(VirtualAlloc(nullptr, 0x100,
        MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    auto* capacity_wrapper = static_cast<unsigned char*>(VirtualAlloc(nullptr, 0x100,
        MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    auto* allocator_wrapper = static_cast<unsigned char*>(VirtualAlloc(nullptr, 0x100,
        MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (!check(image && owner && destination && capacity_wrapper && allocator_wrapper, "allocations")) return 10;
    write_headers(image);
    g_owner = owner;
    std::memcpy(image + kCapacityRva, kCapacityExpected, sizeof(kCapacityExpected));
    std::memcpy(image + kAllocatorRva, kAllocatorExpected, sizeof(kAllocatorExpected));
    write_continuations(image);
    write_wrapper(capacity_wrapper, image + kCapacityRva, true);
    write_wrapper(allocator_wrapper, image + kAllocatorRva, false);
    EP_MIDGATE_CALLBACKS callbacks{capacity_helper, allocator_helper};
    EP_MIDGATE_HOOK hook{};
    if (!check(!ep_midgate_install(25480437u, reinterpret_cast<HMODULE>(image), &callbacks, &hook), "build gate")) return 11;
    EP_MIDGATE_CALLBACKS missing{};
    if (!check(!ep_midgate_install(25480438u, reinterpret_cast<HMODULE>(image), &missing, &hook), "callback gate")) return 12;
    image[kAllocatorRva] ^= 1;
    if (!check(!ep_midgate_install(25480438u, reinterpret_cast<HMODULE>(image), &callbacks, &hook), "allocator fingerprint gate")) return 13;
    image[kAllocatorRva] ^= 1;
    if (!check(std::memcmp(image + kCapacityRva, kCapacityExpected, sizeof(kCapacityExpected)) == 0,
               "atomic failure restored capacity")) return 14;
    if (!check(!hook.installed, "atomic failure hook state")) return 15;
    if (!check(ep_midgate_install(25480438u, reinterpret_cast<HMODULE>(image), &callbacks, &hook), "install")) return 15;
    auto capacity_call = reinterpret_cast<int (__cdecl*)(void*, uint32_t)>(capacity_wrapper);
    auto allocator_call = reinterpret_cast<int (__cdecl*)(void*, void*, uint32_t)>(allocator_wrapper);
    *reinterpret_cast<uint32_t*>(owner) = 3;
    int capacity_result = invoke_capacity(
        reinterpret_cast<EP_MIDGATE_CAPACITY_HELPER>(capacity_call), owner, 1);
    if (!check(capacity_result == 5, "capacity result")) return 16;
    *reinterpret_cast<uint32_t*>(owner) = 9;
    if (!check(invoke_capacity(
                   reinterpret_cast<EP_MIDGATE_CAPACITY_HELPER>(capacity_call), owner, 1) == 0,
               "capacity clamp")) return 17;
    *reinterpret_cast<uint32_t*>(owner + 4) = 4;
    if (!check(invoke_allocator(allocator_call, owner, destination, 2) == 4,
               "allocator result")) return 18;
    *reinterpret_cast<uint32_t*>(owner + 4) = 8;
    if (!check(invoke_allocator(allocator_call, owner, destination, 2) == static_cast<int32_t>(-1),
               "allocator invalid clamp")) return 19;
    if (!check(ep_midgate_remove(&hook), "remove")) return 20;
    if (!check(std::memcmp(image + kCapacityRva, kCapacityExpected, sizeof(kCapacityExpected)) == 0 &&
               std::memcmp(image + kAllocatorRva, kAllocatorExpected, sizeof(kAllocatorExpected)) == 0,
               "original bytes restored")) return 21;
    // Exercise partial cleanup: an externally changed allocator site must not
    // prevent the independent capacity site from being restored.  Once the
    // original detour bytes reappear, a second remove retries the survivor.
    if (!check(ep_midgate_install(25480438u, reinterpret_cast<HMODULE>(image), &callbacks, &hook), "reinstall")) return 22;
    image[kAllocatorRva] ^= 1;
    if (!check(!ep_midgate_remove(&hook), "partial remove reports failure")) return 23;
    if (!check(hook.installed &&
               std::memcmp(image + kCapacityRva, kCapacityExpected, sizeof(kCapacityExpected)) == 0 &&
               image[kAllocatorRva] != 0xff,
               "partial remove restored independent site")) return 24;
    image[kAllocatorRva] ^= 1;
    if (!check(ep_midgate_remove(&hook), "retry remove")) return 25;
    if (!check(!hook.installed &&
               std::memcmp(image + kCapacityRva, kCapacityExpected, sizeof(kCapacityExpected)) == 0 &&
               std::memcmp(image + kAllocatorRva, kAllocatorExpected, sizeof(kAllocatorExpected)) == 0,
               "retry restored survivor")) return 26;
    VirtualFree(allocator_wrapper, 0, MEM_RELEASE);
    VirtualFree(capacity_wrapper, 0, MEM_RELEASE);
    VirtualFree(destination, 0, MEM_RELEASE);
    VirtualFree(owner, 0, MEM_RELEASE);
    VirtualFree(image, 0, MEM_RELEASE);
    std::puts("ep_midgate_executor_synthetic_passed");
    return 0;
}
