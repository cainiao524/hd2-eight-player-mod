#pragma once

#include <windows.h>
#include "../CapacityContract/ep_capacity_contract.h"

// This is an isolated model of the client-side peer structures observed in
// build 25480438.  It never locates or writes a game object.  The native
// bridge must still supply the reviewed callbacks for each patch site.
#define EP_CLIENT_SIDECAR_MAGIC 0x45504353u /* EPCS */
#define EP_CLIENT_SIDECAR_VERSION 2u
#define EP_CLIENT_SIDECAR_BUILD 25480438u
// Storage follows the versioned hard capacity contract.  Native client
// creation remains separately gated by the reviewed build-specific adapter.
#define EP_CLIENT_CAPACITY EP_CAPACITY_HARD_LIMIT

extern "C" {

typedef enum EP_CLIENT_STATUS : UINT32 {
    EP_CLIENT_OK = 0,
    EP_CLIENT_INVALID_ARGUMENT = 1,
    EP_CLIENT_INVALID_CONTEXT = 2,
    EP_CLIENT_INDEX_REJECTED = 3,
    EP_CLIENT_DUPLICATE_PEER = 4,
    EP_CLIENT_DUPLICATE_RESOURCE = 5,
    EP_CLIENT_FULL = 6,
    EP_CLIENT_NOT_FOUND = 7,
    EP_CLIENT_STALE_GENERATION = 8,
    EP_CLIENT_CREATION_REQUIRED = 9,
    EP_CLIENT_INVARIANT_BROKEN = 10,
} EP_CLIENT_STATUS;

typedef struct EP_CLIENT_RECORD {
    UINT64 peer_id;
    UINT64 resource_handle;
    UINT32 network_index;
    UINT32 generation;
    UINT32 present;
    UINT32 reserved;
} EP_CLIENT_RECORD;

typedef struct EP_CLIENT_SIDE_ENTRY {
    UINT64 peer_id;
    UINT32 network_index;
    UINT32 present;
} EP_CLIENT_SIDE_ENTRY;

typedef struct EP_CLIENT_SIDECAR {
    UINT32 magic;
    UINT32 version;
    UINT32 build;
    UINT32 initialized;
    UINT32 confirmed_count;
    UINT32 generation[EP_CLIENT_CAPACITY];
    SRWLOCK lock;
    // Stable network-index storage.  Removal leaves a hole; no compaction is
    // allowed to change the network index assigned by Session/Party.
    EP_CLIENT_RECORD records[EP_CLIENT_CAPACITY];
    // Sidecar equivalents for the four adjacent fixed arrays observed at
    // +0x18, +0x40, +0x88 and +0xD0, plus the separate +0x150 search area.
    EP_CLIENT_SIDE_ENTRY adjacent_8[EP_CLIENT_CAPACITY];
    EP_CLIENT_SIDE_ENTRY adjacent_16[EP_CLIENT_CAPACITY];
    EP_CLIENT_SIDE_ENTRY adjacent_16b[EP_CLIENT_CAPACITY];
    EP_CLIENT_SIDE_ENTRY confirmed_32[EP_CLIENT_CAPACITY];
    EP_CLIENT_SIDE_ENTRY peer_keyed[EP_CLIENT_CAPACITY];
} EP_CLIENT_SIDECAR;

__declspec(dllexport) EP_CLIENT_STATUS __cdecl ep_client_init(
    EP_CLIENT_SIDECAR* sidecar, UINT32 build);
__declspec(dllexport) EP_CLIENT_STATUS __cdecl ep_client_destroy(
    EP_CLIENT_SIDECAR* sidecar);
__declspec(dllexport) EP_CLIENT_STATUS __cdecl ep_client_append(
    EP_CLIENT_SIDECAR* sidecar, UINT64 peer_id, UINT64 resource_handle,
    UINT32 network_index, UINT32* out_generation);
__declspec(dllexport) EP_CLIENT_STATUS __cdecl ep_client_remove(
    EP_CLIENT_SIDECAR* sidecar, UINT32 network_index, UINT32 generation);
__declspec(dllexport) EP_CLIENT_STATUS __cdecl ep_client_get(
    EP_CLIENT_SIDECAR* sidecar, UINT32 network_index,
    EP_CLIENT_RECORD* out_record);
__declspec(dllexport) EP_CLIENT_STATUS __cdecl ep_client_reset(
    EP_CLIENT_SIDECAR* sidecar);
// The original player creation gate rejects unsigned network indexes >= 4.
// This helper is the explicit sidecar contract for indexes 4..7; it does not
// call the game and therefore cannot prove that native creation succeeds.
__declspec(dllexport) EP_CLIENT_STATUS __cdecl ep_client_creation_gate(
    EP_CLIENT_SIDECAR* sidecar, UINT32 network_index);
__declspec(dllexport) EP_CLIENT_STATUS __cdecl ep_client_validate(
    EP_CLIENT_SIDECAR* sidecar);
__declspec(dllexport) UINT32 __cdecl ep_client_capacity();

}
