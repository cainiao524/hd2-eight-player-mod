#pragma once

#include <windows.h>
#include "ep_player_resource.h"
#include "../Bridge/ep_native_bridge.h"

// This adapter binds the isolated three-stage player-resource transaction to
// the existing Native Bridge callback contract.  It never resolves an RVA,
// writes a game module, or calls game code on its own.
#define EP_RESOURCE_BRIDGE_MAGIC 0x45524241u /* "ERBA" */
#define EP_RESOURCE_BRIDGE_VERSION 1u
#define EP_RESOURCE_BRIDGE_BUILD 25480438u
#define EP_RESOURCE_BRIDGE_CALLBACK_VERSION 1u

extern "C" {

typedef EP_RESOURCE_STATUS (__cdecl *EP_RESOURCE_METADATA_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index,
    UINT64* out_resource_hash, UINT32* out_record_ordinal,
    UINT16* out_component_ordinal);

typedef EP_RESOURCE_STATUS (__cdecl *EP_RESOURCE_STAGE_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index,
    EP_RESOURCE_TOKEN token);

typedef struct EP_RESOURCE_BRIDGE_STAGE_CALLBACKS {
    UINT32 version;
    UINT32 size;
    EP_RESOURCE_STAGE_CB first;
    EP_RESOURCE_STAGE_CB second;
    EP_RESOURCE_STAGE_CB third;
} EP_RESOURCE_BRIDGE_STAGE_CALLBACKS;

typedef struct EP_RESOURCE_BRIDGE_CONFIG {
    UINT32 version;
    UINT32 size;
    UINT32 steam_build;
    UINT32 owner_key;
    void* native_owner;
    EP_BRIDGE_CONFIRM_CB native_confirm_peer;
    EP_BRIDGE_CREATE_PLAYER_CB native_create_player;
    EP_BRIDGE_REMOVE_PLAYER_CB native_remove_player;
    EP_BRIDGE_ALLOCATE_INDEX_CB native_allocate_index;
    EP_BRIDGE_RELEASE_INDEX_CB native_release_index;
    EP_BRIDGE_OWNER_RETAIN_CB native_retain_owner;
    EP_BRIDGE_OWNER_RELEASE_CB native_release_owner;
    EP_RESOURCE_METADATA_CB metadata;
    EP_RESOURCE_BRIDGE_STAGE_CALLBACKS stages;
} EP_RESOURCE_BRIDGE_CONFIG;

typedef struct EP_RESOURCE_BRIDGE_ADAPTER {
    UINT32 magic;
    UINT32 version;
    UINT32 initialized;
    UINT32 reserved;
    volatile LONG callback_busy;
    EP_RESOURCE_BRIDGE_CONFIG config;
    EP_PLAYER_RESOURCE resource;
} EP_RESOURCE_BRIDGE_ADAPTER;

__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_resource_bridge_init(
    EP_RESOURCE_BRIDGE_ADAPTER* adapter,
    const EP_RESOURCE_BRIDGE_CONFIG* config);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_resource_bridge_destroy(
    EP_RESOURCE_BRIDGE_ADAPTER* adapter);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_resource_bridge_configure(
    EP_RESOURCE_BRIDGE_ADAPTER* adapter, HMODULE game_module,
    const EP_BRIDGE_SITE* sites, UINT32 site_count,
    EP_BRIDGE_CONFIG* out_bridge_config);

// These functions are supplied directly to EP_BRIDGE_CONFIG by
// ep_resource_bridge_configure().  Their owner is the adapter, while native
// callbacks receive the caller's native_owner pointer.
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_resource_bridge_confirm(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_resource_bridge_create(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_resource_bridge_remove(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_resource_bridge_allocate_index(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8* out_index);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_resource_bridge_release_index(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index,
    UINT32 generation);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_resource_bridge_retain(
    void* owner);
__declspec(dllexport) void __cdecl ep_resource_bridge_release(void* owner);

__declspec(dllexport) UINT32 __cdecl ep_resource_bridge_version();
__declspec(dllexport) UINT32 __cdecl ep_resource_bridge_build();

}
