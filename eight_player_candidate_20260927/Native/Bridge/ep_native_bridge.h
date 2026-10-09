#pragma once

#include <windows.h>
#include "../Sidecar/ep_sidecar.h"
#include "../CapacityContract/ep_capacity_contract.h"

// This bridge is the narrow orchestration layer between the reviewed x64
// hook/sidecar components and the game-specific callbacks.  It deliberately
// does not discover symbols, patch an RVA, or invent a callback ABI.  A
// production installer must provide all callbacks and a matching build/site
// observation; otherwise preflight and admission fail closed.
#define EP_BRIDGE_MAGIC 0x45504252u /* "EPBR" */
#define EP_BRIDGE_VERSION 4u

extern "C" {

typedef enum EP_BRIDGE_STATUS : UINT32 {
    EP_BRIDGE_OK = 0,
    EP_BRIDGE_INVALID_ARGUMENT = 1,
    EP_BRIDGE_INVALID_CONTEXT = 2,
    EP_BRIDGE_BUILD_MISMATCH = 3,
    EP_BRIDGE_SITE_MISMATCH = 4,
    EP_BRIDGE_CALLBACK_MISSING = 5,
    EP_BRIDGE_NO_SLOT = 6,
    EP_BRIDGE_CALLBACK_REJECTED = 7,
    EP_BRIDGE_ROLLBACK_FAILED = 8,
    EP_BRIDGE_NOT_READY = 9,
    EP_BRIDGE_ALREADY_READY = 10,
    EP_BRIDGE_BUSY = 11,
    EP_BRIDGE_CLEANUP_REQUIRED = 12,
    EP_BRIDGE_INDEX_REJECTED = 13,
    EP_BRIDGE_INDEX_RELEASE_FAILED = 14,
    EP_BRIDGE_CAPACITY_REJECTED = 15,
} EP_BRIDGE_STATUS;

typedef struct EP_BRIDGE_SITE {
    UINT32 rva;
    const BYTE* expected;
    SIZE_T size;
} EP_BRIDGE_SITE;

typedef EP_BRIDGE_STATUS (__cdecl *EP_BRIDGE_CONFIRM_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index);
typedef EP_BRIDGE_STATUS (__cdecl *EP_BRIDGE_CREATE_PLAYER_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index);
typedef EP_BRIDGE_STATUS (__cdecl *EP_BRIDGE_REMOVE_PLAYER_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index);
// Callbacks are synchronous: OK means the operation is finished, not queued.
// remove_player must undo partial confirm/create and be safe to retry after
// failure. This is an integration contract, not a recovered game callback ABI.
// The game owner is an asynchronous object.  Every callback transaction must
// hold a reference so a departure or host migration cannot free it midway
// through confirm/create/remove.  The bridge never owns the object itself.
typedef EP_BRIDGE_STATUS (__cdecl *EP_BRIDGE_OWNER_RETAIN_CB)(void* owner);
typedef void (__cdecl *EP_BRIDGE_OWNER_RELEASE_CB)(void* owner);
// Session/Party owns the authoritative network index.  The bridge must use
// that exact index for every confirmed-peer and player-creation callback; it
// never substitutes the first locally free sidecar slot. The allocator must
// leave out_index=0xFF when no new reservation exists. If it partially reserves
// an index and returns an error, it must return that index for generation-zero
// compensation. Index 0xFF is reserved as the no-reservation sentinel.
typedef EP_BRIDGE_STATUS (__cdecl *EP_BRIDGE_ALLOCATE_INDEX_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8* out_index);
typedef EP_BRIDGE_STATUS (__cdecl *EP_BRIDGE_RELEASE_INDEX_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index,
    UINT32 generation);

typedef struct EP_BRIDGE_CONFIG {
    UINT32 steam_build;
    HMODULE game_module;
    const EP_BRIDGE_SITE* sites;
    UINT32 site_count;
    void* owner;
    EP_BRIDGE_CONFIRM_CB confirm_peer;
    EP_BRIDGE_CREATE_PLAYER_CB create_player;
    EP_BRIDGE_REMOVE_PLAYER_CB remove_player;
    EP_BRIDGE_OWNER_RETAIN_CB retain_owner;
    EP_BRIDGE_OWNER_RELEASE_CB release_owner;
    EP_BRIDGE_ALLOCATE_INDEX_CB allocate_index;
    EP_BRIDGE_RELEASE_INDEX_CB release_index;
    // Optional for backward-compatible offline harnesses.  When present, the
    // bridge must validate this contract before any callback is invoked.
    const EP_CAPACITY_CONTRACT* capacity;
} EP_BRIDGE_CONFIG;

typedef struct EP_BRIDGE_ADMISSION {
    UINT64 peer_id;
    UINT64 resource_handle;
    EP_SIDECAR_TOKEN token;
} EP_BRIDGE_ADMISSION;

typedef struct EP_NATIVE_BRIDGE {
    UINT32 magic;
    UINT32 version;
    UINT32 ready;
    UINT32 reserved;
    volatile LONG operation_busy;
    UINT32 cleanup_count;
    EP_BRIDGE_CONFIG config;
    EP_SIDECAR sidecar;
    // Failed cleanup keeps the slot AND an owner lease until explicit retry.
    // Neither its index nor its resource may be reused in the meantime.
    struct {
        UINT32 pending;
        UINT32 remove_done;
        UINT32 index_released;
        EP_BRIDGE_ADMISSION admission;
    } cleanup[EP_SIDECAR_CAPACITY];
} EP_NATIVE_BRIDGE;

__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_bridge_init(
    EP_NATIVE_BRIDGE* bridge, const EP_BRIDGE_CONFIG* config);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_bridge_preflight(
    EP_NATIVE_BRIDGE* bridge);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_bridge_admit(
    EP_NATIVE_BRIDGE* bridge, UINT64 peer_id, UINT64 resource_handle,
    EP_BRIDGE_ADMISSION* out_admission);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_bridge_depart(
    EP_NATIVE_BRIDGE* bridge, EP_BRIDGE_ADMISSION admission);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_bridge_reconnect(
    EP_NATIVE_BRIDGE* bridge, UINT64 peer_id, UINT64 resource_handle,
    EP_BRIDGE_ADMISSION* out_admission);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_bridge_destroy(
    EP_NATIVE_BRIDGE* bridge);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_bridge_retry_cleanup(
    EP_NATIVE_BRIDGE* bridge, EP_BRIDGE_ADMISSION admission);
__declspec(dllexport) UINT32 __cdecl ep_bridge_capacity();

}
