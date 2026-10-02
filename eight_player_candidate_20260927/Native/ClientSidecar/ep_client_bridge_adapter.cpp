#include "ep_client_bridge_adapter.h"

#include <cstring>

namespace {
constexpr UINT32 kMagic = 0x45504341u; // EPCA
constexpr UINT32 kVersion = 1u;

EP_CLIENT_ADAPTER* as_adapter(void* owner) {
    auto* a = static_cast<EP_CLIENT_ADAPTER*>(owner);
    if (!a || a->magic != kMagic || a->version != kVersion || !a->initialized)
        return nullptr;
    return a;
}

EP_BRIDGE_STATUS map_status(EP_CLIENT_STATUS status) {
    return status == EP_CLIENT_OK ? EP_BRIDGE_OK : EP_BRIDGE_CALLBACK_REJECTED;
}
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_init(
    EP_CLIENT_ADAPTER* a, void* owner, EP_CLIENT_NATIVE_CREATE_CB native_create) {
    if (!a || owner != a) return EP_BRIDGE_INVALID_ARGUMENT;
    std::memset(a, 0, sizeof(*a));
    a->magic = kMagic;
    a->version = kVersion;
    a->owner = owner;
    a->native_create = native_create;
    if (ep_client_init(&a->client, EP_CLIENT_SIDECAR_BUILD) != EP_CLIENT_OK) {
        std::memset(a, 0, sizeof(*a));
        return EP_BRIDGE_INVALID_CONTEXT;
    }
    a->initialized = 1;
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_destroy(EP_CLIENT_ADAPTER* a) {
    if (!as_adapter(a)) return EP_BRIDGE_INVALID_CONTEXT;
    if (a->owner_refs != 0 || ep_client_validate(&a->client) != EP_CLIENT_OK ||
        ep_client_destroy(&a->client) != EP_CLIENT_OK) return EP_BRIDGE_CLEANUP_REQUIRED;
    a->initialized = 0;
    a->magic = 0;
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_confirm(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index) {
    auto* a = as_adapter(owner);
    if (!a) return EP_BRIDGE_INVALID_CONTEXT;
    UINT32 generation = 0;
    return map_status(ep_client_append(&a->client, peer_id, resource_handle,
                                        network_index, &generation));
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_create(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index) {
    auto* a = as_adapter(owner);
    if (!a) return EP_BRIDGE_INVALID_CONTEXT;
    EP_CLIENT_RECORD record{};
    if (ep_client_get(&a->client, network_index, &record) != EP_CLIENT_OK ||
        record.peer_id != peer_id || record.resource_handle != resource_handle)
        return EP_BRIDGE_CALLBACK_REJECTED;
    const auto gate = ep_client_creation_gate(&a->client, network_index);
    if (gate == EP_CLIENT_INDEX_REJECTED || gate == EP_CLIENT_INVALID_CONTEXT)
        return EP_BRIDGE_CALLBACK_REJECTED;
    if (network_index < 4) return EP_BRIDGE_OK;
    // The sidecar deliberately cannot manufacture the native player.  A
    // reviewed callback supplied by the production bridge must do it.
    return a->native_create
        ? a->native_create(a->owner, peer_id, resource_handle, network_index)
        : EP_BRIDGE_CALLBACK_REJECTED;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_remove(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index) {
    auto* a = as_adapter(owner);
    if (!a) return EP_BRIDGE_INVALID_CONTEXT;
    EP_CLIENT_RECORD record{};
    if (ep_client_get(&a->client, network_index, &record) != EP_CLIENT_OK ||
        record.peer_id != peer_id || record.resource_handle != resource_handle)
        return EP_BRIDGE_CALLBACK_REJECTED;
    return map_status(ep_client_remove(&a->client, network_index, record.generation));
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_retain(void* owner) {
    auto* a = as_adapter(owner);
    if (!a) return EP_BRIDGE_INVALID_CONTEXT;
    InterlockedIncrement(&a->owner_refs);
    return EP_BRIDGE_OK;
}

extern "C" void __cdecl ep_client_adapter_release(void* owner) {
    auto* a = as_adapter(owner);
    if (!a) return;
    LONG refs = a->owner_refs;
    while (refs > 0) {
        const LONG prior = InterlockedCompareExchange(&a->owner_refs, refs - 1, refs);
        if (prior == refs) return;
        refs = prior;
    }
}
