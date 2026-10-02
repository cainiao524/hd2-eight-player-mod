#pragma once

#include <windows.h>

// This is a deliberately small x64 hook boundary.  It only patches an
// explicitly supplied instruction boundary and refuses automatic disassembly.
// The production game call sites require a separately reviewed instruction
// map and owner/lifetime integration.
extern "C" {

typedef struct EP_HOOK {
    void* target;
    void* detour;
    void* trampoline;
    SIZE_T stolen_length;
    BYTE original[64];
    SIZE_T trampoline_length;
    RUNTIME_FUNCTION runtime_function;
    BOOL runtime_registered;
    BOOL installed;
} EP_HOOK;

// Install/remove a reversible absolute x64 jump.  stolen_length must be an
// instruction boundary and at least 14 bytes.  The caller owns the quiescence
// requirement: no thread may execute target while remove is in progress.
__declspec(dllexport) BOOL __cdecl ep_install_hook(void* target, void* detour,
                                                    SIZE_T stolen_length,
                                                    EP_HOOK* out_hook);
__declspec(dllexport) BOOL __cdecl ep_remove_hook(EP_HOOK* hook);

// Relocate a caller-supplied instruction span into a trampoline.  RIP-relative
// memory and rel32 CALL/JMP are adjusted; short and conditional branches, and
// unknown relative encodings, fail closed.  The caller still supplies a span
// ending at an instruction boundary.
__declspec(dllexport) BOOL __cdecl ep_relocate_block(const BYTE* source,
                                                     SIZE_T source_length,
                                                     UINT64 source_address,
                                                     BYTE* destination,
                                                     SIZE_T destination_capacity,
                                                     UINT64 destination_address,
                                                     SIZE_T* relocated_length);

// Verify a loaded module/site before production integration.  This performs no
// memory writes and intentionally has no function that patches a game RVA.
__declspec(dllexport) BOOL __cdecl ep_verify_loaded_site(HMODULE module,
                                                          DWORD rva,
                                                          const BYTE* expected,
                                                          SIZE_T expected_size);

// The first admission root with a normal function prologue.  The 18-byte
// boundary covers complete instructions and contains no relative operands;
// it is still only a validator until sidecar callbacks are wired.
__declspec(dllexport) BOOL __cdecl ep_verify_host_join_site(HMODULE module);
__declspec(dllexport) DWORD __cdecl ep_host_join_stolen_length();

// Returns the build/profile identity compiled into this scaffold.  These are
// data points for the outer fail-closed preflight, not an authorization to
// modify a process.
__declspec(dllexport) DWORD __cdecl ep_expected_steam_build();
__declspec(dllexport) DWORD __cdecl ep_expected_game_rva_host_capacity();
}
