#pragma once

#include "ep_session_snapshot.h"
#include <windows.h>

namespace ep_session {
inline Snapshot capture_current_process() {
    // The documented globals live in data/game/game.dll, not the main EXE.
    HMODULE game = GetModuleHandleW(L"game.dll");
    return capture_game_context(reinterpret_cast<uintptr_t>(game),
        [](uintptr_t address, void* output, size_t size) {
            SIZE_T copied = 0;
            return ReadProcessMemory(GetCurrentProcess(),
                reinterpret_cast<const void*>(address), output, size, &copied) != FALSE &&
                copied == size;
        });
}
} // namespace ep_session
