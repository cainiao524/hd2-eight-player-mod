#include "native_hook_scaffold.h"

#include <bcrypt.h>
#include <cstring>
#include <cstdint>

#pragma comment(lib, "bcrypt.lib")

namespace {

constexpr DWORD kSteamBuild = 25480438;
constexpr DWORD kHostCapacityRva = 0x108C18F;
constexpr DWORD kHostJoinRva = 0x108BC70;
constexpr SIZE_T kAbsoluteJumpSize = 14;

// push rbp; push rbx; push rsi; push r12; lea rbp,[rsp-0x17];
// sub rsp,0xc8.  This is the smallest complete (18-byte) prologue boundary at the
// captured host-join root.  Keeping it here makes accidental mid-instruction
// patching impossible for a future production caller.
constexpr BYTE kHostJoinPrologue[] = {
    0x40, 0x55, 0x53, 0x56, 0x41, 0x54,
    0x48, 0x8D, 0x6C, 0x24, 0xE9,
    0x48, 0x81, 0xEC, 0xC8, 0x00, 0x00, 0x00,
};

bool writable(void* address, SIZE_T length, DWORD* old_protect) {
    return VirtualProtect(address, length, PAGE_EXECUTE_READWRITE, old_protect) != 0;
}

void write_absolute_jump(BYTE* at, const void* destination) {
    // FF 25 00 00 00 00 ; qword destination
    at[0] = 0xFF;
    at[1] = 0x25;
    at[2] = 0x00;
    at[3] = 0x00;
    at[4] = 0x00;
    at[5] = 0x00;
    std::memcpy(at + 6, &destination, sizeof(destination));
}

bool register_unwind(EP_HOOK* hook) {
    // The trampoline has no prologue of its own: the copied span is restricted
    // to instruction forms that do not allocate stack or save nonvolatile
    // registers.  It is still a non-leaf code range when the copied span
    // contains a CALL, so register a valid version-1, zero-code UNWIND_INFO
    // instead of four zero bytes (version 0 is invalid on x64).
    const SIZE_T unwind_offset = (hook->trampoline_length + 3u) & ~SIZE_T(3u);
    BYTE* unwind = static_cast<BYTE*>(hook->trampoline) + unwind_offset;
    const BYTE unwind_info[] = {0x01, 0x00, 0x00, 0x00};
    std::memcpy(unwind, unwind_info, sizeof(unwind_info));
    hook->runtime_function.BeginAddress = 0;
    hook->runtime_function.EndAddress = static_cast<DWORD>(hook->trampoline_length);
    hook->runtime_function.UnwindData = static_cast<DWORD>(unwind_offset);
    hook->runtime_registered = RtlAddFunctionTable(&hook->runtime_function, 1,
                                                    reinterpret_cast<DWORD64>(hook->trampoline)) != FALSE;
    return hook->runtime_registered;
}

void unregister_unwind(EP_HOOK* hook) {
    if (hook->runtime_registered) {
        RtlDeleteFunctionTable(&hook->runtime_function);
        hook->runtime_registered = FALSE;
    }
}

bool is_prefix(BYTE byte) {
    return (byte >= 0x40 && byte <= 0x4F) || byte == 0x66 || byte == 0x67 ||
           byte == 0xF0 || byte == 0xF2 || byte == 0xF3 ||
           byte == 0x2E || byte == 0x36 || byte == 0x3E || byte == 0x26 ||
           byte == 0x64 || byte == 0x65;
}

bool is_short_branch(BYTE op) {
    return op == 0xEB || op == 0xE0 || op == 0xE1 || op == 0xE2 || op == 0xE3 ||
           (op >= 0x70 && op <= 0x7F);
}

bool fits_rel32(INT64 value) {
    return value >= INT32_MIN && value <= INT32_MAX;
}

bool modrm_length(const BYTE* bytes, SIZE_T available, SIZE_T modrm_offset,
                  SIZE_T* length, bool* rip_relative) {
    if (!bytes || !length || !rip_relative || modrm_offset >= available) return false;
    const BYTE modrm = bytes[modrm_offset];
    const BYTE mod = static_cast<BYTE>(modrm >> 6);
    const BYTE rm = static_cast<BYTE>(modrm & 7);
    SIZE_T cursor = modrm_offset + 1;
    *rip_relative = (mod == 0 && rm == 5);
    if (mod == 0) {
        if (rm == 4) {
            if (cursor >= available) return false;
            const BYTE sib = bytes[cursor++];
            if ((sib & 7) == 5) {
                // SIB base=5 with mod=0 is an absolute disp32 in 64-bit mode,
                // not RIP-relative.
                if (cursor + 4 > available) return false;
                cursor += 4;
            }
        } else if (rm == 5) {
            if (cursor + 4 > available) return false;
            cursor += 4;
        }
    } else if (mod == 1) {
        if (rm == 4) {
            if (cursor >= available) return false;
            ++cursor;
        }
        if (cursor + 1 > available) return false;
        ++cursor;
    } else if (mod == 2) {
        if (rm == 4) {
            if (cursor >= available) return false;
            ++cursor;
        }
        if (cursor + 4 > available) return false;
        cursor += 4;
    }
    *length = cursor - modrm_offset;
    return true;
}

// The relocation decoder is intentionally bounded.  It handles the forms
// present in the captured prologues and rejects branch encodings whose target
// or condition cannot be proven by this small decoder.
bool relocate_one(const BYTE* source, SIZE_T available, UINT64 source_address,
                  BYTE* destination, SIZE_T destination_capacity,
                  UINT64 destination_address, SIZE_T* consumed) {
    if (!source || !destination || !consumed || available == 0) return false;
    const BYTE op = source[0];
    if (op == 0xE8 || op == 0xE9) {
        if (available < 5 || destination_capacity < 5) return false;
        INT32 old_disp = 0;
        std::memcpy(&old_disp, source + 1, sizeof(old_disp));
        const INT64 target = static_cast<INT64>(source_address + 5) + old_disp;
        const INT64 new_disp = target - static_cast<INT64>(destination_address + 5);
        if (!fits_rel32(new_disp)) return false;
        std::memcpy(destination, source, 5);
        const INT32 narrowed = static_cast<INT32>(new_disp);
        std::memcpy(destination + 1, &narrowed, sizeof(narrowed));
        *consumed = 5;
        return true;
    }
    if (is_short_branch(op) || op == 0x9A || op == 0xEA) return false;
    if (op == 0x0F && available >= 2 && source[1] >= 0x80 && source[1] <= 0x8F) {
        // Conditional rel32 branches need a condition-aware continuation and
        // are deliberately rejected by this helper.
        return false;
    }

    SIZE_T prefix = 0;
    while (prefix < available && is_prefix(source[prefix])) ++prefix;
    if (prefix >= available) return false;
    const BYTE primary = source[prefix];
    SIZE_T opcode_length = 1;
    bool has_modrm = false;
    SIZE_T immediate = 0;
    if (primary == 0x0F) {
        if (prefix + 1 >= available) return false;
        const BYTE secondary = source[prefix + 1];
        if (secondary >= 0x80 && secondary <= 0x8F) return false;
        opcode_length = 2;
        has_modrm = secondary == 0x10 || secondary == 0x11 || secondary == 0x2F ||
                    secondary == 0x57 || secondary == 0x58 || secondary == 0x59;
    } else {
        has_modrm = primary == 0x03 || primary == 0x08 || primary == 0x09 ||
                    primary == 0x0B || primary == 0x21 || primary == 0x23 ||
                    primary == 0x2B || primary == 0x39 || primary == 0x3B ||
                    primary == 0x3D || primary == 0x69 || primary == 0x6B ||
                    primary == 0x80 || primary == 0x81 || primary == 0x83 ||
                    primary == 0x85 || primary == 0x87 || primary == 0x89 ||
                    primary == 0x8B || primary == 0x8D || primary == 0x8F ||
                    primary == 0xC0 || primary == 0xC1 || primary == 0xC6 ||
                    primary == 0xC7 || primary == 0xD1 || primary == 0xD3 ||
                    primary == 0xF6 || primary == 0xF7 || primary == 0xFE ||
                    primary == 0xFF;
        if (primary == 0x80 || primary == 0x83 || primary == 0xC0 || primary == 0xC1 || primary == 0xC6) immediate = 1;
        if (primary == 0x69 || primary == 0x81 || primary == 0xC7) immediate = 4;
        if (primary == 0x6B) immediate = 1;
    }
    if (has_modrm) {
        const SIZE_T modrm_offset = prefix + opcode_length;
        SIZE_T modrm_bytes = 0;
        bool rip_relative = false;
        if (!modrm_length(source, available, modrm_offset, &modrm_bytes, &rip_relative)) return false;
        SIZE_T total = modrm_offset + modrm_bytes + immediate;
        if (total > available || total > destination_capacity) return false;
        std::memcpy(destination, source, total);
        if (rip_relative) {
            // Address-size override changes rm=5 semantics; reject rather than
            // accidentally treating an absolute disp32 as RIP-relative.
            if (std::memchr(source, 0x67, prefix) != nullptr) return false;
            const SIZE_T displacement_offset = modrm_offset + 1;
            INT32 old_disp = 0;
            std::memcpy(&old_disp, source + displacement_offset, sizeof(old_disp));
            const INT64 target = static_cast<INT64>(source_address + total) + old_disp;
            const INT64 new_disp = target - static_cast<INT64>(destination_address + total);
            if (!fits_rel32(new_disp)) return false;
            const INT32 narrowed = static_cast<INT32>(new_disp);
            std::memcpy(destination + displacement_offset, &narrowed, sizeof(narrowed));
        }
        *consumed = total;
        return true;
    }

    // Known one-byte instructions and register-immediate moves.  Unknown bytes
    // are copied one at a time only after all relative branch opcodes above
    // have been rejected; the caller remains responsible for the boundary.
    SIZE_T total = prefix + 1;
    if (primary >= 0xB8 && primary <= 0xBF) {
        total += (prefix && (source[0] & 8)) ? 8 : 4;
    } else if (primary == 0x68) {
        total += 4;
    } else if (primary == 0x6A) {
        total += 1;
    }
    if (total > available || total > destination_capacity) return false;
    std::memcpy(destination, source, total);
    *consumed = total;
    return true;
}

extern "C" __declspec(dllexport)
BOOL __cdecl ep_relocate_block(const BYTE* source, SIZE_T source_length,
                               UINT64 source_address, BYTE* destination,
                               SIZE_T destination_capacity, UINT64 destination_address,
                               SIZE_T* relocated_length) {
    if (!source || source_length == 0 || !destination || destination_capacity < source_length || !relocated_length) return FALSE;
    SIZE_T src_offset = 0;
    SIZE_T dst_offset = 0;
    while (src_offset < source_length) {
        SIZE_T consumed = 0;
        if (!relocate_one(source + src_offset, source_length - src_offset,
                          source_address + src_offset, destination + dst_offset,
                          destination_capacity - dst_offset, destination_address + dst_offset,
                          &consumed) || consumed == 0) {
            return FALSE;
        }
        src_offset += consumed;
        dst_offset += consumed;
    }
    *relocated_length = dst_offset;
    return TRUE;
}

} // namespace

extern "C" __declspec(dllexport)
BOOL __cdecl ep_install_hook(void* target, void* detour, SIZE_T stolen_length,
                             EP_HOOK* out_hook) {
    if (!target || !detour || !out_hook || stolen_length < kAbsoluteJumpSize || stolen_length > sizeof(out_hook->original)) {
        return FALSE;
    }
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(target, &mbi, sizeof(mbi)) != sizeof(mbi) ||
        mbi.State != MEM_COMMIT ||
        (mbi.Protect & (PAGE_EXECUTE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY)) == 0) {
        return FALSE;
    }
    std::memset(out_hook, 0, sizeof(*out_hook));
    out_hook->target = target;
    out_hook->detour = detour;
    out_hook->stolen_length = stolen_length;
    std::memcpy(out_hook->original, target, stolen_length);

    out_hook->trampoline_length = stolen_length + kAbsoluteJumpSize;
    const SIZE_T allocation_size = out_hook->trampoline_length + 4;
    out_hook->trampoline = VirtualAlloc(nullptr, allocation_size, MEM_COMMIT | MEM_RESERVE,
                                        PAGE_EXECUTE_READWRITE);
    if (!out_hook->trampoline) {
        return FALSE;
    }
    SIZE_T relocated = 0;
    if (!ep_relocate_block(out_hook->original, stolen_length,
                           reinterpret_cast<UINT64>(target),
                           static_cast<BYTE*>(out_hook->trampoline),
                           out_hook->trampoline_length,
                           reinterpret_cast<UINT64>(out_hook->trampoline), &relocated) || relocated != stolen_length) {
        VirtualFree(out_hook->trampoline, 0, MEM_RELEASE);
        out_hook->trampoline = nullptr;
        return FALSE;
    }
    write_absolute_jump(static_cast<BYTE*>(out_hook->trampoline) + stolen_length,
                        static_cast<BYTE*>(target) + stolen_length);
    if (!register_unwind(out_hook)) {
        VirtualFree(out_hook->trampoline, 0, MEM_RELEASE);
        out_hook->trampoline = nullptr;
        return FALSE;
    }

    DWORD old_protect = 0;
    if (!writable(target, stolen_length, &old_protect)) {
        unregister_unwind(out_hook);
        VirtualFree(out_hook->trampoline, 0, MEM_RELEASE);
        out_hook->trampoline = nullptr;
        return FALSE;
    }
    write_absolute_jump(static_cast<BYTE*>(target), detour);
    for (SIZE_T i = kAbsoluteJumpSize; i < stolen_length; ++i) {
        static_cast<BYTE*>(target)[i] = 0x90;
    }
    FlushInstructionCache(GetCurrentProcess(), target, stolen_length);
    DWORD ignored = 0;
    VirtualProtect(target, stolen_length, old_protect, &ignored);
    out_hook->installed = TRUE;
    return TRUE;
}

extern "C" __declspec(dllexport)
BOOL __cdecl ep_remove_hook(EP_HOOK* hook) {
    if (!hook || !hook->installed || !hook->target || !hook->trampoline) {
        return FALSE;
    }
    // The owner must suspend/quiesce all threads before calling this function.
    DWORD old_protect = 0;
    if (!writable(hook->target, hook->stolen_length, &old_protect)) {
        return FALSE;
    }
    std::memcpy(hook->target, hook->original, hook->stolen_length);
    FlushInstructionCache(GetCurrentProcess(), hook->target, hook->stolen_length);
    DWORD ignored = 0;
    VirtualProtect(hook->target, hook->stolen_length, old_protect, &ignored);
    unregister_unwind(hook);
    VirtualFree(hook->trampoline, 0, MEM_RELEASE);
    hook->trampoline = nullptr;
    hook->installed = FALSE;
    return TRUE;
}

extern "C" __declspec(dllexport)
BOOL __cdecl ep_verify_loaded_site(HMODULE module, DWORD rva,
                                   const BYTE* expected, SIZE_T expected_size) {
    if (!module || !expected || expected_size == 0 || expected_size > 0x10000) {
        return FALSE;
    }
    const BYTE* base = reinterpret_cast<const BYTE*>(module);
    __try {
        const BYTE* site = base + rva;
        return std::memcmp(site, expected, expected_size) == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return FALSE;
    }
}

extern "C" __declspec(dllexport)
DWORD __cdecl ep_expected_steam_build() { return kSteamBuild; }

extern "C" __declspec(dllexport)
DWORD __cdecl ep_expected_game_rva_host_capacity() { return kHostCapacityRva; }

extern "C" __declspec(dllexport)
BOOL __cdecl ep_verify_host_join_site(HMODULE module) {
    return ep_verify_loaded_site(module, kHostJoinRva, kHostJoinPrologue,
                                 sizeof(kHostJoinPrologue));
}

extern "C" __declspec(dllexport)
DWORD __cdecl ep_host_join_stolen_length() {
    return static_cast<DWORD>(sizeof(kHostJoinPrologue));
}
