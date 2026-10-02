#pragma once

#include <windows.h>
#include "ep_client_sidecar.h"
#include "../Bridge/ep_native_bridge.h"

// Narrow callback adapter for the existing native bridge.  The adapter only
// owns the isolated client sidecar.  A real player-creation callback is
// mandatory for indexes 4..7; absent that callback the adapter rejects the
// operation instead of pretending that a player was created.
extern "C" {

typedef EP_BRIDGE_STATUS (__cdecl *EP_CLIENT_NATIVE_CREATE_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index);

typedef struct EP_CLIENT_ADAPTER {
    UINT32 magic;
    UINT32 version;
    UINT32 initialized;
    UINT32 reserved;
    volatile LONG owner_refs;
    void* owner;
    EP_CLIENT_NATIVE_CREATE_CB native_create;
    EP_CLIENT_SIDECAR client;
} EP_CLIENT_ADAPTER;

__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_client_adapter_init(
    EP_CLIENT_ADAPTER* adapter, void* owner, EP_CLIENT_NATIVE_CREATE_CB native_create);
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
