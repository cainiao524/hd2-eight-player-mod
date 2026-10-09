#include "ep_client_bridge_adapter.h"

#include <cstring>

namespace {
constexpr UINT32 kMagic = 0x45504341u; // EPCA
constexpr UINT32 kVersion = 5u;

EP_CLIENT_ADAPTER* as_adapter(void* owner) {
    auto* a = static_cast<EP_CLIENT_ADAPTER*>(owner);
    if (!a || a->magic != kMagic || a->version != kVersion || !a->initialized)
        return nullptr;
    return a;
}

EP_BRIDGE_STATUS map_status(EP_CLIENT_STATUS status) {
    return status == EP_CLIENT_OK ? EP_BRIDGE_OK : EP_BRIDGE_CALLBACK_REJECTED;
}

int free_overflow(const EP_CLIENT_ADAPTER* a) {
    for (UINT32 i = 0; i < EP_SIDECAR_CAPACITY; ++i)
        if (!a->overflow[i].valid) return static_cast<int>(i);
    return -1;
}

int matching_overflow(const EP_CLIENT_ADAPTER* a, UINT8 index,
                      UINT64 peer, UINT64 handle) {
    for (UINT32 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        const auto& item = a->overflow[i];
        if (item.valid && item.network_index == index &&
            item.peer_id == peer && item.resource_handle == handle)
            return static_cast<int>(i);
    }
    return -1;
}
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_init(
    EP_CLIENT_ADAPTER* a, void* native_owner,
    EP_CLIENT_NATIVE_CONFIRM_CB native_confirm,
    EP_CLIENT_NATIVE_CREATE_CB native_create,
    EP_CLIENT_NATIVE_REMOVE_CB native_remove,
    EP_CLIENT_NATIVE_ALLOCATE_INDEX_CB native_allocate_index,
    EP_CLIENT_NATIVE_RELEASE_INDEX_CB native_release_index,
    EP_CLIENT_NATIVE_RETAIN_CB native_retain,
    EP_CLIENT_NATIVE_RELEASE_CB native_release) {
    if (!a || !native_owner || !native_confirm || !native_create ||
        !native_remove || !native_allocate_index || !native_release_index ||
        !native_retain || !native_release)
        return EP_BRIDGE_INVALID_ARGUMENT;
    if (a->magic == kMagic && a->version == kVersion && a->initialized)
        return EP_BRIDGE_ALREADY_READY;
    std::memset(a, 0, sizeof(*a));
    a->magic = kMagic;
    a->version = kVersion;
    a->owner = a;
    a->native_owner = native_owner;
    a->native_confirm = native_confirm;
    a->native_create = native_create;
    a->native_remove = native_remove;
    a->native_allocate_index = native_allocate_index;
    a->native_release_index = native_release_index;
    a->native_retain = native_retain;
    a->native_release = native_release;
    if (ep_client_init(&a->client, EP_CLIENT_SIDECAR_BUILD) != EP_CLIENT_OK) {
        std::memset(a, 0, sizeof(*a));
        return EP_BRIDGE_INVALID_CONTEXT;
    }
    a->initialized = 1;
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_destroy(EP_CLIENT_ADAPTER* a) {
    if (!as_adapter(a)) return EP_BRIDGE_INVALID_CONTEXT;
    for (UINT32 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        if (a->native_confirmed[i] != 0) return EP_BRIDGE_CLEANUP_REQUIRED;
        if (a->index_reserved[i] != 0) return EP_BRIDGE_CLEANUP_REQUIRED;
        if (a->overflow[i].valid != 0) return EP_BRIDGE_CLEANUP_REQUIRED;
    }
    if (a->owner_refs != 0 || ep_client_validate(&a->client) != EP_CLIENT_OK ||
        ep_client_destroy(&a->client) != EP_CLIENT_OK) return EP_BRIDGE_CLEANUP_REQUIRED;
    a->initialized = 0;
    a->magic = 0;
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_allocate_index(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8* out_index) {
    auto* a = as_adapter(owner);
    if (!a || !out_index || peer_id == 0 || resource_handle == 0)
        return EP_BRIDGE_INVALID_ARGUMENT;
    *out_index = 0xFF;
    UINT8 index = 0xFF;
    const auto status = a->native_allocate_index(
        a->native_owner, peer_id, resource_handle, &index);
    // FF is the callback contract's no-reservation sentinel. A provider must
    // return every partially allocated index even when it reports failure.
    if (index == 0xFF)
        return status == EP_BRIDGE_OK ? EP_BRIDGE_INDEX_REJECTED : status;
    if (index >= EP_SIDECAR_CAPACITY) {
        const int overflow_slot = free_overflow(a);
        if (overflow_slot < 0) {
            // No local retry record remains.  Attempt immediate compensation;
            // keep the index visible if that release itself fails.
            if (a->native_release_index(a->native_owner, peer_id,
                                        resource_handle, index, 0) == EP_BRIDGE_OK)
                return status == EP_BRIDGE_OK ? EP_BRIDGE_INDEX_REJECTED : status;
            *out_index = index;
            return EP_BRIDGE_CLEANUP_REQUIRED;
        }
        for (const auto& item : a->overflow)
            if (item.valid && item.network_index == index)
                return EP_BRIDGE_INDEX_REJECTED;
        a->overflow[overflow_slot] = {1, index, 0, peer_id, resource_handle};
        *out_index = index;
        return status == EP_BRIDGE_OK ? EP_BRIDGE_INDEX_REJECTED : status;
    }
    if (a->index_reserved[index] != 0) {
        // This belongs to an existing admission. Never release that owner's
        // reservation in response to a colliding allocator result.
        return EP_BRIDGE_INDEX_REJECTED;
    }
    a->index_reserved[index] = 1;
    *out_index = index;
    return status;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_release_index(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index,
    UINT32 generation) {
    auto* a = as_adapter(owner);
    if (!a || peer_id == 0 || resource_handle == 0)
        return EP_BRIDGE_INVALID_ARGUMENT;
    if (network_index >= EP_SIDECAR_CAPACITY) {
        if (generation != 0) return EP_BRIDGE_INDEX_REJECTED;
        const int found = matching_overflow(a, network_index, peer_id, resource_handle);
        if (found < 0) return EP_BRIDGE_INDEX_REJECTED;
        const auto status = a->native_release_index(
            a->native_owner, peer_id, resource_handle, network_index, 0);
        if (status == EP_BRIDGE_OK) a->overflow[found] = {};
        return status;
    }
    if (a->index_reserved[network_index] == 0)
        return EP_BRIDGE_INDEX_REJECTED;
    const auto status = a->native_release_index(
        a->native_owner, peer_id, resource_handle, network_index, generation);
    if (status != EP_BRIDGE_OK) return status;
    a->index_reserved[network_index] = 0;
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_confirm(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index) {
    auto* a = as_adapter(owner);
    if (!a) return EP_BRIDGE_INVALID_CONTEXT;
    if (network_index >= EP_SIDECAR_CAPACITY ||
        a->index_reserved[network_index] == 0)
        return EP_BRIDGE_INDEX_REJECTED;
    UINT32 generation = 0;
    if (map_status(ep_client_append(&a->client, peer_id, resource_handle,
                                    network_index, &generation)) != EP_BRIDGE_OK)
        return EP_BRIDGE_CALLBACK_REJECTED;
    a->native_confirmed[network_index] = 0;
    const auto native = a->native_confirm(a->native_owner, peer_id,
                                          resource_handle, network_index);
    // The bridge owns compensation. Erasing the identity here would prevent
    // its remove callback from undoing partially completed native work.
    if (native != EP_BRIDGE_OK) return native;
    a->native_confirmed[network_index] = 1;
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_create(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index) {
    auto* a = as_adapter(owner);
    if (!a) return EP_BRIDGE_INVALID_CONTEXT;
    EP_CLIENT_RECORD record{};
    if (ep_client_get(&a->client, network_index, &record) != EP_CLIENT_OK ||
        record.peer_id != peer_id || record.resource_handle != resource_handle ||
        !a->native_confirmed[network_index])
        return EP_BRIDGE_CALLBACK_REJECTED;
    const auto gate = ep_client_creation_gate(&a->client, network_index);
    if (gate == EP_CLIENT_INDEX_REJECTED || gate == EP_CLIENT_INVALID_CONTEXT)
        return EP_BRIDGE_CALLBACK_REJECTED;
    // The sidecar deliberately cannot manufacture the native player.  Every
    // index, including the original four, must pass the reviewed callback so
    // the adapter cannot report a sidecar-only "created" player.
    return a->native_create(a->native_owner, peer_id, resource_handle, network_index);
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_remove(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index) {
    auto* a = as_adapter(owner);
    if (!a) return EP_BRIDGE_INVALID_CONTEXT;
    EP_CLIENT_RECORD record{};
    if (ep_client_get(&a->client, network_index, &record) != EP_CLIENT_OK ||
        record.peer_id != peer_id || record.resource_handle != resource_handle)
        return EP_BRIDGE_CALLBACK_REJECTED;
    const auto native = a->native_remove(a->native_owner, peer_id,
                                         resource_handle, network_index);
    if (native != EP_BRIDGE_OK) return native;
    const auto status = ep_client_remove(&a->client, network_index, record.generation);
    if (status == EP_CLIENT_OK) a->native_confirmed[network_index] = 0;
    return map_status(status);
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_client_adapter_retain(void* owner) {
    auto* a = as_adapter(owner);
    if (!a) return EP_BRIDGE_INVALID_CONTEXT;
    const auto status = a->native_retain(a->native_owner);
    if (status != EP_BRIDGE_OK) return status;
    InterlockedIncrement(&a->owner_refs);
    return EP_BRIDGE_OK;
}

extern "C" void __cdecl ep_client_adapter_release(void* owner) {
    auto* a = as_adapter(owner);
    if (!a) return;
    LONG refs = a->owner_refs;
    while (refs > 0) {
        const LONG prior = InterlockedCompareExchange(&a->owner_refs, refs - 1, refs);
        if (prior == refs) {
            a->native_release(a->native_owner);
            return;
        }
        refs = prior;
    }
}
