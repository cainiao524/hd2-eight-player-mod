#pragma once

#include <windows.h>
#include "ep_client_sidecar.h"
#include "../Bridge/ep_native_bridge.h"

// Narrow callback adapter for the existing native bridge.  The adapter only
// owns the isolated client sidecar.  A real player-creation callback is
// mandatory for every network index, including 4..7; absent that callback the
// adapter rejects the operation instead of pretending that a player was created.
extern "C" {

typedef EP_BRIDGE_STATUS (__cdecl *EP_CLIENT_NATIVE_CREATE_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index);
typedef EP_BRIDGE_STATUS (__cdecl *EP_CLIENT_NATIVE_CONFIRM_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index);
typedef EP_BRIDGE_STATUS (__cdecl *EP_CLIENT_NATIVE_REMOVE_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index);
typedef EP_BRIDGE_STATUS (__cdecl *EP_CLIENT_NATIVE_RETAIN_CB)(void* owner);
typedef void (__cdecl *EP_CLIENT_NATIVE_RELEASE_CB)(void* owner);

typedef struct EP_CLIENT_ADAPTER {
    UINT32 magic;
    UINT32 version;
    UINT32 initialized;
    UINT32 reserved;
    volatile LONG owner_refs;
    // `owner` is the bridge callback identity (the adapter itself).  The
    // native object is kept separate so a callback cannot accidentally treat
    // the sidecar allocation as a game object.
    void* owner;
    void* native_owner;
    EP_CLIENT_NATIVE_CONFIRM_CB native_confirm;
    EP_CLIENT_NATIVE_CREATE_CB native_create;
    EP_CLIENT_NATIVE_REMOVE_CB native_remove;
    EP_CLIENT_NATIVE_RETAIN_CB native_retain;
    EP_CLIENT_NATIVE_RELEASE_CB native_release;
    EP_CLIENT_SIDECAR client;
    // A rejected native confirm still needs compensating remove. Keep its
    // identity but disallow creation until native confirmation succeeds.
    BYTE native_confirmed[EP_SIDECAR_CAPACITY];
} EP_CLIENT_ADAPTER;

__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_client_adapter_init(
    EP_CLIENT_ADAPTER* adapter, void* native_owner,
    EP_CLIENT_NATIVE_CONFIRM_CB native_confirm,
    EP_CLIENT_NATIVE_CREATE_CB native_create,
    EP_CLIENT_NATIVE_REMOVE_CB native_remove,
    EP_CLIENT_NATIVE_RETAIN_CB native_retain,
    EP_CLIENT_NATIVE_RELEASE_CB native_release);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_client_adapter_destroy(
    EP_CLIENT_ADAPTER* adapter);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_client_adapter_confirm(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_client_adapter_create(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_client_adapter_remove(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_client_adapter_retain(void* owner);
__declspec(dllexport) void __cdecl ep_client_adapter_release(void* owner);

}
