#pragma once
#include "ep_session_snapshot.h"
#include <windows.h>
namespace ep_session {
inline Snapshot capture_current_process() {
    return capture(reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr)),
        [](uintptr_t address, void* output, size_t size) {
            SIZE_T copied=0;
            return ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<const void*>(address),
                output, size, &copied) != FALSE && copied == size;
        });
}
} // namespace ep_session
