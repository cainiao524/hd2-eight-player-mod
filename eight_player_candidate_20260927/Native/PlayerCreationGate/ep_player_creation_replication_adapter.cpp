#include "ep_player_creation_replication_adapter.h"

#include <cstring>

namespace {

constexpr UINT8 kBridgeNone = 0;
constexpr UINT8 kBridgeLive = 1;
constexpr UINT8 kBridgeCleanupPending = 2;
constexpr UINT8 kComponentsDone = 1u;

bool valid_context(const EP_PLAYER_CREATION_REPLICATION_ADAPTER* a) {
    return a != nullptr && a->magic == EP_PCR_MAGIC &&
           a->version == EP_PCR_VERSION && a->initialized == 1 &&
           a->replication != nullptr &&
           a->replication->magic == EP_REPLICATION_BRIDGE_MAGIC;
}

bool config_valid(const EP_PCR_CONFIG& c) {
    return c.version == EP_PCR_CALLBACK_VERSION &&
           c.size == sizeof(EP_PCR_CONFIG) && c.owner != nullptr &&
           c.retain_owner != nullptr && c.release_owner != nullptr &&
           c.resolve_resource != nullptr && c.dispatch_components != nullptr &&
           c.cleanup_components != nullptr;
}

EP_PC_STATUS map_bridge(EP_BRIDGE_STATUS status) {
    switch (status) {
    case EP_BRIDGE_OK: return EP_PC_OK;
    case EP_BRIDGE_BUSY: return EP_PC_BUSY;
    case EP_BRIDGE_BUILD_MISMATCH: return EP_PC_BUILD_MISMATCH;
    case EP_BRIDGE_INDEX_REJECTED: return EP_PC_INDEX_REJECTED;
    case EP_BRIDGE_NO_SLOT:
    case EP_BRIDGE_CAPACITY_REJECTED: return EP_PC_FULL;
    case EP_BRIDGE_CLEANUP_REQUIRED:
    case EP_BRIDGE_INDEX_RELEASE_FAILED:
    case EP_BRIDGE_ROLLBACK_FAILED: return EP_PC_ROLLBACK_FAILED;
    default: return EP_PC_CALLBACK_REJECTED;
    }
}

EP_PLAYER_CREATION_REPLICATION_ADAPTER* as_adapter(void* owner) {
    auto* a = static_cast<EP_PLAYER_CREATION_REPLICATION_ADAPTER*>(owner);
    return valid_context(a) ? a : nullptr;
}

bool cleanup_pending_status(EP_BRIDGE_STATUS status) {
    return status == EP_BRIDGE_CLEANUP_REQUIRED ||
           status == EP_BRIDGE_INDEX_RELEASE_FAILED ||
           status == EP_BRIDGE_ROLLBACK_FAILED;
}

void clear_bridge(EP_PLAYER_CREATION_REPLICATION_ADAPTER* a, UINT8 index) {
    a->bridge_state[index] = kBridgeNone;
    std::memset(&a->admissions[index], 0, sizeof(a->admissions[index]));
}

void remember_bridge_cleanup(EP_PLAYER_CREATION_REPLICATION_ADAPTER* a,
                             UINT8 index, EP_BRIDGE_ADMISSION admission) {
    a->admissions[index] = admission;
    a->bridge_state[index] = kBridgeCleanupPending;
}

EP_BRIDGE_STATUS depart_bridge(EP_PLAYER_CREATION_REPLICATION_ADAPTER* a,
                               UINT8 index) {
    if (a->bridge_state[index] == kBridgeCleanupPending) {
        return ep_bridge_retry_cleanup(&a->replication->admission,
                                       a->admissions[index]);
    }
    if (a->bridge_state[index] == kBridgeLive) {
        return ep_bridge_depart(&a->replication->admission,
                                a->admissions[index]);
    }
    return EP_BRIDGE_OK;
}

EP_PC_STATUS __cdecl retain_owner(void* owner) {
    auto* a = as_adapter(owner);
    if (!a) return EP_PC_INVALID_CONTEXT;
    try { return a->config.retain_owner(a->config.owner); }
    catch (...) { return EP_PC_CALLBACK_REJECTED; }
}

void __cdecl release_owner(void* owner) {
    auto* a = as_adapter(owner);
    if (!a) return;
    try { a->config.release_owner(a->config.owner); }
    catch (...) {}
}

EP_PC_STATUS __cdecl resolve_resource(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT64 resource_hash,
    UINT8 network_index, UINT32 generation, EP_PC_RESOURCE* out_resource) {
    auto* a = as_adapter(owner);
    if (!a || !out_resource) return EP_PC_INVALID_CONTEXT;
    try {
        return a->config.resolve_resource(a->config.owner, peer_id,
                                          resource_handle, resource_hash,
                                          network_index, generation,
                                          out_resource);
    } catch (...) {
        return EP_PC_CALLBACK_REJECTED;
    }
}

EP_PC_STATUS __cdecl dispatch_components(void* owner,
                                         const EP_PC_RESOURCE* resource) {
    auto* a = as_adapter(owner);
    if (!a || !resource) return EP_PC_INVALID_CONTEXT;
    try { return a->config.dispatch_components(a->config.owner, resource); }
    catch (...) { return EP_PC_CALLBACK_REJECTED; }
}

EP_PC_STATUS __cdecl insert_roster(void* owner,
                                   const EP_PC_RESOURCE* resource) {
    auto* a = as_adapter(owner);
    if (!a || !resource || resource->network_index >= EP_PC_CAPACITY)
        return EP_PC_INVALID_CONTEXT;
    const UINT8 index = resource->network_index;
    if (a->bridge_state[index] != kBridgeNone)
        return EP_PC_DUPLICATE;

    EP_BRIDGE_ADMISSION admission{};
    EP_BRIDGE_STATUS status = EP_BRIDGE_CALLBACK_REJECTED;
    try {
        status = ep_bridge_admit_at(&a->replication->admission,
                                 resource->peer_id, resource->resource_handle,
                                 index, &admission);
    } catch (...) {
        status = EP_BRIDGE_CALLBACK_REJECTED;
    }
    if (status != EP_BRIDGE_OK) {
        if (cleanup_pending_status(status) && admission.peer_id != 0)
            remember_bridge_cleanup(a, index, admission);
        return map_bridge(status);
    }

    // The bridge has checked the allocator's index before any confirm/create
    // or replication callbacks. Save the matching admission for departure.
    a->admissions[index] = admission;
    a->bridge_state[index] = kBridgeLive;
    return EP_PC_OK;
}

EP_PC_STATUS __cdecl cleanup_roster(void* owner,
                                    const EP_PC_RESOURCE* resource) {
    auto* a = as_adapter(owner);
    if (!a || !resource || resource->network_index >= EP_PC_CAPACITY)
        return EP_PC_INVALID_CONTEXT;
    const UINT8 index = resource->network_index;
    if (a->bridge_state[index] == kBridgeNone) return EP_PC_OK;

    EP_BRIDGE_STATUS status = EP_BRIDGE_ROLLBACK_FAILED;
    try { status = depart_bridge(a, index); }
    catch (...) { status = EP_BRIDGE_CALLBACK_REJECTED; }
    if (status == EP_BRIDGE_OK) {
        clear_bridge(a, index);
        return EP_PC_OK;
    }
    if (cleanup_pending_status(status))
        a->bridge_state[index] = kBridgeCleanupPending;
    return map_bridge(status);
}

EP_PC_STATUS __cdecl cleanup_components(void* owner,
                                        const EP_PC_RESOURCE* resource) {
    auto* a = as_adapter(owner);
    if (!a || !resource) return EP_PC_INVALID_CONTEXT;
    try { return a->config.cleanup_components(a->config.owner, resource); }
    catch (...) { return EP_PC_CALLBACK_REJECTED; }
}

EP_PC_STATUS __cdecl rollback(void* owner, const EP_PC_RESOURCE* resource,
                              UINT32 completed_mask) {
    auto* a = as_adapter(owner);
    if (!a || !resource || resource->network_index >= EP_PC_CAPACITY)
        return EP_PC_INVALID_CONTEXT;
    const UINT8 index = resource->network_index;
    if (a->bridge_state[index] != kBridgeNone) {
        EP_BRIDGE_STATUS status = EP_BRIDGE_ROLLBACK_FAILED;
        try { status = depart_bridge(a, index); }
        catch (...) { status = EP_BRIDGE_CALLBACK_REJECTED; }
        if (status != EP_BRIDGE_OK) {
            if (cleanup_pending_status(status))
                a->bridge_state[index] = kBridgeCleanupPending;
            return map_bridge(status);
        }
        clear_bridge(a, index);
    }
    if ((completed_mask & kComponentsDone) == 0) return EP_PC_OK;
    try { return a->config.cleanup_components(a->config.owner, resource); }
    catch (...) { return EP_PC_CALLBACK_REJECTED; }
}

} // namespace

extern "C" EP_PC_STATUS __cdecl ep_pcr_init(
    EP_PLAYER_CREATION_REPLICATION_ADAPTER* a,
    EP_REPLICATION_BRIDGE* replication, const EP_PCR_CONFIG* config) {
    if (!a || !replication || !config || !config_valid(*config))
        return EP_PC_CALLBACK_MISSING;
    if (a->magic == EP_PCR_MAGIC) return EP_PC_BUSY;
    if (replication->magic != EP_REPLICATION_BRIDGE_MAGIC ||
        !replication->admission.ready)
        return EP_PC_INVALID_CONTEXT;
    std::memset(a, 0, sizeof(*a));
    a->magic = EP_PCR_MAGIC;
    a->version = EP_PCR_VERSION;
    a->replication = replication;
    a->config = *config;
    a->callbacks = {a, retain_owner, release_owner, resolve_resource,
                    dispatch_components, insert_roster, cleanup_roster,
                    cleanup_components, rollback};
    const EP_PC_STATUS status = ep_pc_init(&a->creation, EP_PC_BUILD,
                                           &a->callbacks);
    if (status != EP_PC_OK) {
        std::memset(a, 0, sizeof(*a));
        return status;
    }
    a->initialized = 1;
    return EP_PC_OK;
}

extern "C" EP_PC_STATUS __cdecl ep_pcr_destroy(
    EP_PLAYER_CREATION_REPLICATION_ADAPTER* a) {
    if (!valid_context(a)) return EP_PC_INVALID_CONTEXT;
    for (UINT8 i = 0; i < EP_PC_CAPACITY; ++i)
        if (a->bridge_state[i] != kBridgeNone) return EP_PC_BUSY;
    const EP_PC_STATUS status = ep_pc_destroy(&a->creation);
    if (status != EP_PC_OK) return status;
    std::memset(a, 0, sizeof(*a));
    return EP_PC_OK;
}

extern "C" EP_PC_STATUS __cdecl ep_pcr_admit(
    EP_PLAYER_CREATION_REPLICATION_ADAPTER* a, UINT8 network_index,
    UINT64 peer_id, UINT64 resource_handle, UINT64 resource_hash,
    EP_PC_TOKEN* out_token) {
    if (!valid_context(a)) return EP_PC_INVALID_CONTEXT;
    return ep_pc_admit(&a->creation, network_index, peer_id, resource_handle,
                       resource_hash, out_token);
}

extern "C" EP_PC_STATUS __cdecl ep_pcr_depart(
    EP_PLAYER_CREATION_REPLICATION_ADAPTER* a, EP_PC_TOKEN token) {
    if (!valid_context(a)) return EP_PC_INVALID_CONTEXT;
    return ep_pc_depart(&a->creation, token);
}

extern "C" EP_PC_STATUS __cdecl ep_pcr_get(
    EP_PLAYER_CREATION_REPLICATION_ADAPTER* a, UINT8 network_index,
    EP_PC_SLOT* out_slot) {
    if (!valid_context(a)) return EP_PC_INVALID_CONTEXT;
    return ep_pc_get(&a->creation, network_index, out_slot);
}

extern "C" EP_PC_STATUS __cdecl ep_pcr_validate(
    EP_PLAYER_CREATION_REPLICATION_ADAPTER* a) {
    if (!valid_context(a)) return EP_PC_INVALID_CONTEXT;
    const EP_PC_STATUS status = ep_pc_validate(&a->creation);
    if (status != EP_PC_OK) return status;
    for (UINT8 i = 0; i < EP_PC_CAPACITY; ++i) {
        EP_PC_SLOT slot{};
        if (ep_pc_get(&a->creation, i, &slot) != EP_PC_OK)
            return EP_PC_INVARIANT_BROKEN;
        if (slot.state == EP_PC_FREE && a->bridge_state[i] != kBridgeNone)
            return EP_PC_INVARIANT_BROKEN;
        if (slot.state == EP_PC_ACTIVE && a->bridge_state[i] != kBridgeLive)
            return EP_PC_INVARIANT_BROKEN;
    }
    return EP_PC_OK;
}

extern "C" UINT32 __cdecl ep_pcr_capacity() { return EP_PC_CAPACITY; }
