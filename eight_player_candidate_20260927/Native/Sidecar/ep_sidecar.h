#pragma once

#include <windows.h>

// The sidecar owns only an isolated, caller-provided table.  It never locates
// or writes a game module.  A production bridge must still wire each result
// into the reviewed Session/Party/roster call sites.
#define EP_SIDECAR_CAPACITY 8u
#define EP_SIDECAR_MAGIC 0x45505343u /* "EPSC" */
#define EP_SIDECAR_VERSION 1u

extern "C" {

typedef enum EP_SIDECAR_STATUS : UINT32 {
    EP_SC_OK = 0,
    EP_SC_INVALID_ARGUMENT = 1,
    EP_SC_INVALID_CONTEXT = 2,
    EP_SC_DUPLICATE_IDENTITY = 3,
    EP_SC_DUPLICATE_RESOURCE = 4,
    EP_SC_FULL = 5,
    EP_SC_GENERATION_EXHAUSTED = 6,
    EP_SC_INVALID_TOKEN = 7,
    EP_SC_STALE_TOKEN = 8,
    EP_SC_INVALID_STATE = 9,
    EP_SC_ALREADY_CONFIRMED = 10,
    EP_SC_INVARIANT_BROKEN = 11,
} EP_SIDECAR_STATUS;

typedef enum EP_SIDECAR_SLOT_STATE : UINT8 {
    EP_SC_SLOT_FREE = 0,
    EP_SC_SLOT_PENDING = 1,
    EP_SC_SLOT_CONFIRMED = 2,
} EP_SIDECAR_SLOT_STATE;

typedef struct EP_SIDECAR_TOKEN {
    UINT8 index;
    UINT8 reserved[3];
    UINT32 generation;
} EP_SIDECAR_TOKEN;

typedef struct EP_SIDECAR_SLOT {
    UINT8 state;
    UINT8 reserved[3];
    UINT32 generation;
    UINT64 peer_id;
    UINT64 resource_handle;
} EP_SIDECAR_SLOT;

typedef struct EP_SIDECAR {
    UINT32 magic;
    UINT32 version;
    UINT32 initialized;
    UINT32 active_count;
    UINT32 confirmed_count;
    UINT32 reserved;
    SRWLOCK lock;
    EP_SIDECAR_SLOT slots[EP_SIDECAR_CAPACITY];
} EP_SIDECAR;

__declspec(dllexport) EP_SIDECAR_STATUS __cdecl ep_sidecar_init(EP_SIDECAR* sidecar);
__declspec(dllexport) EP_SIDECAR_STATUS __cdecl ep_sidecar_destroy(EP_SIDECAR* sidecar);
__declspec(dllexport) EP_SIDECAR_STATUS __cdecl ep_sidecar_reserve(
    EP_SIDECAR* sidecar, UINT64 peer_id, UINT64 resource_handle,
    EP_SIDECAR_TOKEN* out_token);
__declspec(dllexport) EP_SIDECAR_STATUS __cdecl ep_sidecar_confirm(
    EP_SIDECAR* sidecar, EP_SIDECAR_TOKEN token);
__declspec(dllexport) EP_SIDECAR_STATUS __cdecl ep_sidecar_remove(
    EP_SIDECAR* sidecar, EP_SIDECAR_TOKEN token);
// Reconnect returns the existing token when the identity is still present.
// After departure it reserves a new generation, preserving all other slots.
__declspec(dllexport) EP_SIDECAR_STATUS __cdecl ep_sidecar_reconnect(
    EP_SIDECAR* sidecar, UINT64 peer_id, UINT64 resource_handle,
    EP_SIDECAR_TOKEN* out_token);
__declspec(dllexport) EP_SIDECAR_STATUS __cdecl ep_sidecar_get_slot(
    EP_SIDECAR* sidecar, UINT8 index, EP_SIDECAR_SLOT* out_slot);
__declspec(dllexport) EP_SIDECAR_STATUS __cdecl ep_sidecar_validate(
    EP_SIDECAR* sidecar);
__declspec(dllexport) UINT32 __cdecl ep_sidecar_capacity();

}
