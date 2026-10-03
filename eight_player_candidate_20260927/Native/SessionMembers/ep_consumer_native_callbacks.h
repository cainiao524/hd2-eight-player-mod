#pragma once

#include "ep_consumer_executor.h"
#include <cstddef>

extern "C" {

typedef enum EP_CONSUMER_NATIVE_STATUS : unsigned long {
    EP_CONSUMER_NATIVE_OK = 0,
    EP_CONSUMER_NATIVE_INVALID_ARGUMENT = 1,
    EP_CONSUMER_NATIVE_BUILD_MISMATCH = 2,
    EP_CONSUMER_NATIVE_IMAGE_MISMATCH = 3,
    EP_CONSUMER_NATIVE_NOT_BOUND = 4,
    EP_CONSUMER_NATIVE_CALLBACK_MISSING = 5,
} EP_CONSUMER_NATIVE_STATUS;

// The resolver result is the compact view consumed by the replacement stub:
// ids[0..7] at +0x00 and count at +0x40.  It is deliberately separate from
// EP_SIDECAR, whose slot records and SRWLOCK do not have this layout.
typedef struct EP_CONSUMER_MEMBER_VIEW {
    UINT64 ids[8];
    UINT32 count;
} EP_CONSUMER_MEMBER_VIEW;
static_assert(offsetof(EP_CONSUMER_MEMBER_VIEW, count) == 0x40,
              "consumer member view layout drift");

typedef void* (__cdecl *EP_CONSUMER_SIDECAR_RESOLVER)(void* owner);

// The resolver must return a stable EP_CONSUMER_MEMBER_VIEW for the complete
// callback transaction; its owner/lifetime and publication rules are caller-owned.
// Binds only the callback shapes that are directly recoverable from the
// fixed-build consumer body.  It performs no game call and installs no hook.
__declspec(dllexport) EP_CONSUMER_NATIVE_STATUS __cdecl ep_consumer_native_bind(
    unsigned long steam_build, HMODULE game_module,
    EP_CONSUMER_SIDECAR_RESOLVER sidecar_resolver);
__declspec(dllexport) EP_CONSUMER_NATIVE_STATUS __cdecl ep_consumer_native_unbind();
__declspec(dllexport) EP_CONSUMER_NATIVE_STATUS __cdecl ep_consumer_native_get_callbacks(
    EP_CONSUMER_CALLBACKS* out_callbacks);
__declspec(dllexport) unsigned long __cdecl ep_consumer_native_build();

}
