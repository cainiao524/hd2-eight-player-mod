#include "ep_native_bridge.h"

#include <cstring>
#include <limits>

namespace {

bool valid_context(const EP_NATIVE_BRIDGE* bridge) {
    return bridge != nullptr && bridge->magic == EP_BRIDGE_MAGIC &&
           bridge->version == EP_BRIDGE_VERSION && bridge->config.steam_build != 0 &&
           bridge->config.owner != nullptr;
}

bool callbacks_present(const EP_BRIDGE_CONFIG& config) {
    return config.confirm_peer != nullptr && config.create_player != nullptr &&
           config.remove_player != nullptr && config.retain_owner != nullptr &&
           config.release_owner != nullptr && config.allocate_index != nullptr &&
           config.release_index != nullptr;
}

struct OwnerLease {
    const EP_BRIDGE_CONFIG& config;
    bool held = false;
    bool acquire() {
        if (config.retain_owner(config.owner) != EP_BRIDGE_OK) return false;
        held = true;
        return true;
    }
    ~OwnerLease() {
        if (held) config.release_owner(config.owner);
    }
    void disarm() { held = false; }
};

struct OperationGuard {
    EP_NATIVE_BRIDGE* bridge;
    bool held = false;
    explicit OperationGuard(EP_NATIVE_BRIDGE* value) : bridge(value) {
        if (bridge != nullptr)
            held = InterlockedCompareExchange(&bridge->operation_busy, 1, 0) == 0;
    }
    ~OperationGuard() {
        if (held) InterlockedExchange(&bridge->operation_busy, 0);
    }
    explicit operator bool() const { return held; }
};

EP_BRIDGE_STATUS sidecar_status(EP_SIDECAR_STATUS status) {
    if (status == EP_SC_OK) return EP_BRIDGE_OK;
    if (status == EP_SC_FULL || status == EP_SC_GENERATION_EXHAUSTED)
        return EP_BRIDGE_NO_SLOT;
    if (status == EP_SC_INDEX_OCCUPIED) return EP_BRIDGE_INDEX_REJECTED;
    return EP_BRIDGE_CALLBACK_REJECTED;
}

bool sites_match(const EP_BRIDGE_CONFIG& config) {
    if (config.game_module == nullptr || config.sites == nullptr || config.site_count == 0)
        return false;
    const auto base = reinterpret_cast<const BYTE*>(config.game_module);
    for (UINT32 i = 0; i < config.site_count; ++i) {
        const EP_BRIDGE_SITE& site = config.sites[i];
        if (site.expected == nullptr || site.size == 0) return false;
        if (std::memcmp(base + site.rva, site.expected, site.size) != 0) return false;
    }
    return true;
}

int cleanup_for(const EP_NATIVE_BRIDGE* bridge, EP_BRIDGE_ADMISSION admission) {
    if (!bridge || admission.token.index >= EP_SIDECAR_CAPACITY) return -1;
    for (UINT32 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        const auto& item = bridge->cleanup[i];
        if (!item.pending) continue;
        const auto& saved = item.admission;
        if (saved.peer_id == admission.peer_id &&
            saved.resource_handle == admission.resource_handle &&
            saved.token.index == admission.token.index &&
            saved.token.generation == admission.token.generation)
            return static_cast<int>(i);
    }
    return -1;
}

bool remember_cleanup(EP_NATIVE_BRIDGE* bridge, EP_BRIDGE_ADMISSION admission,
                      OwnerLease& lease, UINT32 remove_done,
                      UINT32 index_released) {
    if (!bridge || admission.token.index >= EP_SIDECAR_CAPACITY) return false;
    if (cleanup_for(bridge, admission) >= 0) {
        // The retry record already owns one reference; release this new one.
        return true;
    }
    for (UINT32 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        if (bridge->cleanup[i].pending) continue;
        bridge->cleanup[i].pending = 1;
        bridge->cleanup[i].remove_done = remove_done;
        bridge->cleanup[i].index_released = index_released;
        bridge->cleanup[i].admission = admission;
        ++bridge->cleanup_count;
        // The owner reference now belongs to the retry record.
        lease.disarm();
        return true;
    }
    return false;
}

EP_BRIDGE_STATUS finish_cleanup(EP_NATIVE_BRIDGE* bridge,
                                EP_BRIDGE_ADMISSION admission,
                                UINT32* remove_done,
                                UINT32* index_released) {
    if (!bridge || !remove_done || !index_released) return EP_BRIDGE_INVALID_ARGUMENT;
    if (!*remove_done) {
        const EP_BRIDGE_STATUS removed = bridge->config.remove_player(
            bridge->config.owner, admission.peer_id, admission.resource_handle,
            admission.token.index);
        if (removed != EP_BRIDGE_OK) return removed;
        *remove_done = 1;
    }
    // Keep the sidecar token occupied until the authoritative allocator has
    // released the same index.  This prevents a failed release from allowing
    // a second admission to bind a different peer to the old network index.
    if (!*index_released) {
        const EP_BRIDGE_STATUS released = bridge->config.release_index(
            bridge->config.owner, admission.peer_id, admission.resource_handle,
            admission.token.index, admission.token.generation);
        if (released != EP_BRIDGE_OK) return EP_BRIDGE_INDEX_RELEASE_FAILED;
        *index_released = 1;
    }
    const EP_SIDECAR_STATUS removed = ep_sidecar_remove(
        &bridge->sidecar, admission.token);
    return removed == EP_SC_OK ? EP_BRIDGE_OK : EP_BRIDGE_ROLLBACK_FAILED;
}

EP_BRIDGE_STATUS remove_and_release(EP_NATIVE_BRIDGE* bridge,
                                    EP_BRIDGE_ADMISSION admission,
                                    OwnerLease& lease,
                                    EP_BRIDGE_STATUS failure_status) {
    UINT32 remove_done = 0;
    UINT32 index_released = 0;
    const EP_BRIDGE_STATUS result = finish_cleanup(
        bridge, admission, &remove_done, &index_released);
    if (result == EP_BRIDGE_OK) return failure_status;
    if (remember_cleanup(bridge, admission, lease, remove_done, index_released))
        return EP_BRIDGE_CLEANUP_REQUIRED;
    return EP_BRIDGE_ROLLBACK_FAILED;
}

bool find_identity(const EP_NATIVE_BRIDGE* bridge, UINT64 peer_id,
                   UINT64 resource_handle, EP_SIDECAR_TOKEN* out_token,
                   bool* out_conflict) {
    if (out_conflict) *out_conflict = false;
    if (!bridge || !out_token) return false;
    for (UINT8 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        EP_SIDECAR_SLOT slot{};
        if (ep_sidecar_get_slot(const_cast<EP_SIDECAR*>(&bridge->sidecar), i, &slot) != EP_SC_OK)
            return false;
        if (slot.state == EP_SC_SLOT_FREE) continue;
        if (slot.peer_id == peer_id && slot.resource_handle == resource_handle) {
            out_token->index = i;
            out_token->generation = slot.generation;
            return true;
        }
        if (slot.peer_id == peer_id || slot.resource_handle == resource_handle) {
            if (out_conflict) *out_conflict = true;
        }
    }
    return false;
}

int cleanup_for_identity(const EP_NATIVE_BRIDGE* bridge, UINT64 peer_id,
                         UINT64 resource_handle) {
    if (!bridge) return -1;
    for (UINT32 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        const auto& item = bridge->cleanup[i];
        if (item.pending && item.admission.peer_id == peer_id &&
            item.admission.resource_handle == resource_handle)
            return static_cast<int>(i);
    }
    return -1;
}

}

extern "C" EP_BRIDGE_STATUS __cdecl ep_bridge_init(
    EP_NATIVE_BRIDGE* bridge, const EP_BRIDGE_CONFIG* config) {
    if (bridge == nullptr || config == nullptr) return EP_BRIDGE_INVALID_ARGUMENT;
    if (bridge->magic == EP_BRIDGE_MAGIC && bridge->ready)
        return EP_BRIDGE_ALREADY_READY;
    if (!callbacks_present(*config)) return EP_BRIDGE_CALLBACK_MISSING;
    std::memset(bridge, 0, sizeof(*bridge));
    bridge->magic = EP_BRIDGE_MAGIC;
    bridge->version = EP_BRIDGE_VERSION;
    bridge->config = *config;
    if (ep_sidecar_init(&bridge->sidecar) != EP_SC_OK) {
        std::memset(bridge, 0, sizeof(*bridge));
        return EP_BRIDGE_INVALID_CONTEXT;
    }
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_bridge_preflight(EP_NATIVE_BRIDGE* bridge) {
    if (!valid_context(bridge)) return EP_BRIDGE_INVALID_CONTEXT;
    OperationGuard operation{bridge};
    if (!operation) return EP_BRIDGE_BUSY;
    if (bridge->config.steam_build != 25480438u) return EP_BRIDGE_BUILD_MISMATCH;
    if (!callbacks_present(bridge->config)) return EP_BRIDGE_CALLBACK_MISSING;
    if (!sites_match(bridge->config)) return EP_BRIDGE_SITE_MISMATCH;
    bridge->ready = 1;
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_bridge_admit(
    EP_NATIVE_BRIDGE* bridge, UINT64 peer_id, UINT64 resource_handle,
    EP_BRIDGE_ADMISSION* out_admission) {
    if (!valid_context(bridge) || out_admission == nullptr || peer_id == 0 || resource_handle == 0)
        return EP_BRIDGE_INVALID_ARGUMENT;
    if (!bridge->ready) return EP_BRIDGE_NOT_READY;
    OperationGuard operation{bridge};
    if (!operation) return EP_BRIDGE_BUSY;
    const int identity_cleanup = cleanup_for_identity(bridge, peer_id, resource_handle);
    if (identity_cleanup >= 0) {
        *out_admission = bridge->cleanup[identity_cleanup].admission;
        return EP_BRIDGE_CLEANUP_REQUIRED;
    }
    OwnerLease lease{bridge->config};
    if (!lease.acquire()) return EP_BRIDGE_CALLBACK_REJECTED;
    UINT8 network_index = 0xFF;
    const EP_BRIDGE_STATUS allocated = bridge->config.allocate_index(
        bridge->config.owner, peer_id, resource_handle, &network_index);
    if (allocated != EP_BRIDGE_OK)
        return allocated == EP_BRIDGE_NO_SLOT ? EP_BRIDGE_NO_SLOT : EP_BRIDGE_INDEX_REJECTED;
    if (network_index >= EP_SIDECAR_CAPACITY) {
        if (bridge->config.release_index(bridge->config.owner, peer_id,
                                         resource_handle, network_index, 0) != EP_BRIDGE_OK)
            return EP_BRIDGE_INDEX_RELEASE_FAILED;
        return EP_BRIDGE_INDEX_REJECTED;
    }
    EP_SIDECAR_TOKEN token{};
    EP_SIDECAR_STATUS status = ep_sidecar_reserve_at(
        &bridge->sidecar, network_index, peer_id, resource_handle, &token);
    if (status != EP_SC_OK) {
        if (bridge->config.release_index(bridge->config.owner, peer_id,
                                         resource_handle, network_index, 0) != EP_BRIDGE_OK)
            return EP_BRIDGE_INDEX_RELEASE_FAILED;
        return sidecar_status(status);
    }
    EP_BRIDGE_ADMISSION admission{peer_id, resource_handle, token};
    if (bridge->config.confirm_peer(bridge->config.owner, peer_id, resource_handle, token.index) != EP_BRIDGE_OK) {
        const EP_BRIDGE_STATUS result = remove_and_release(
            bridge, admission, lease, EP_BRIDGE_CALLBACK_REJECTED);
        if (result == EP_BRIDGE_CLEANUP_REQUIRED) *out_admission = admission;
        return result;
    }
    if (bridge->config.create_player(bridge->config.owner, peer_id, resource_handle, token.index) != EP_BRIDGE_OK) {
        const EP_BRIDGE_STATUS result = remove_and_release(
            bridge, admission, lease, EP_BRIDGE_CALLBACK_REJECTED);
        if (result == EP_BRIDGE_CLEANUP_REQUIRED) *out_admission = admission;
        return result;
    }
    // Publish bridge readiness only after the native player exists.
    status = ep_sidecar_confirm(&bridge->sidecar, token);
    if (status != EP_SC_OK) {
        const EP_BRIDGE_STATUS result = remove_and_release(
            bridge, admission, lease, sidecar_status(status));
        if (result == EP_BRIDGE_CLEANUP_REQUIRED) *out_admission = admission;
        return result;
    }
    *out_admission = admission;
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_bridge_depart(
    EP_NATIVE_BRIDGE* bridge, EP_BRIDGE_ADMISSION admission) {
    if (!valid_context(bridge) || !bridge->ready) return EP_BRIDGE_NOT_READY;
    OperationGuard operation{bridge};
    if (!operation) return EP_BRIDGE_BUSY;
    if (cleanup_for(bridge, admission) >= 0) return EP_BRIDGE_CLEANUP_REQUIRED;
    OwnerLease lease{bridge->config};
    if (!lease.acquire()) return EP_BRIDGE_CALLBACK_REJECTED;
    EP_SIDECAR_SLOT slot{};
    if (ep_sidecar_get_slot(&bridge->sidecar, admission.token.index, &slot) != EP_SC_OK ||
        slot.peer_id != admission.peer_id || slot.resource_handle != admission.resource_handle ||
        slot.generation != admission.token.generation || slot.state != EP_SC_SLOT_CONFIRMED)
        return EP_BRIDGE_INVALID_ARGUMENT;
    UINT32 remove_done = 0;
    UINT32 index_released = 0;
    const EP_BRIDGE_STATUS status = finish_cleanup(
        bridge, admission, &remove_done, &index_released);
    if (status == EP_BRIDGE_OK) return EP_BRIDGE_OK;
    if (remember_cleanup(bridge, admission, lease, remove_done, index_released))
        return EP_BRIDGE_CLEANUP_REQUIRED;
    return EP_BRIDGE_ROLLBACK_FAILED;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_bridge_reconnect(
    EP_NATIVE_BRIDGE* bridge, UINT64 peer_id, UINT64 resource_handle,
    EP_BRIDGE_ADMISSION* out_admission) {
    if (!valid_context(bridge) || !bridge->ready || out_admission == nullptr || peer_id == 0 || resource_handle == 0)
        return EP_BRIDGE_INVALID_ARGUMENT;
    OperationGuard operation{bridge};
    if (!operation) return EP_BRIDGE_BUSY;
    const int identity_cleanup = cleanup_for_identity(bridge, peer_id, resource_handle);
    if (identity_cleanup >= 0) {
        *out_admission = bridge->cleanup[identity_cleanup].admission;
        return EP_BRIDGE_CLEANUP_REQUIRED;
    }
    OwnerLease lease{bridge->config};
    if (!lease.acquire()) return EP_BRIDGE_CALLBACK_REJECTED;
    EP_SIDECAR_TOKEN token{};
    bool conflict = false;
    const bool existing = find_identity(bridge, peer_id, resource_handle,
                                        &token, &conflict);
    if (!existing && conflict) return EP_BRIDGE_CALLBACK_REJECTED;
    EP_SIDECAR_STATUS status = EP_SC_OK;
    if (!existing) {
        UINT8 network_index = 0xFF;
        const EP_BRIDGE_STATUS allocated = bridge->config.allocate_index(
            bridge->config.owner, peer_id, resource_handle, &network_index);
        if (allocated != EP_BRIDGE_OK)
            return allocated == EP_BRIDGE_NO_SLOT ? EP_BRIDGE_NO_SLOT : EP_BRIDGE_INDEX_REJECTED;
        if (network_index >= EP_SIDECAR_CAPACITY) {
            if (bridge->config.release_index(bridge->config.owner, peer_id,
                                             resource_handle, network_index, 0) != EP_BRIDGE_OK)
                return EP_BRIDGE_INDEX_RELEASE_FAILED;
            return EP_BRIDGE_INDEX_REJECTED;
        }
        status = ep_sidecar_reserve_at(&bridge->sidecar, network_index,
                                       peer_id, resource_handle, &token);
        if (status != EP_SC_OK) {
            if (bridge->config.release_index(bridge->config.owner, peer_id,
                                             resource_handle, network_index, 0) != EP_BRIDGE_OK)
                return EP_BRIDGE_INDEX_RELEASE_FAILED;
            return sidecar_status(status);
        }
    }
    EP_SIDECAR_SLOT slot{};
    if (ep_sidecar_get_slot(&bridge->sidecar, token.index, &slot) != EP_SC_OK)
        return EP_BRIDGE_ROLLBACK_FAILED;
    EP_BRIDGE_ADMISSION admission{peer_id, resource_handle, token};
    if (slot.state == EP_SC_SLOT_PENDING) {
        if (bridge->config.confirm_peer(bridge->config.owner, peer_id,
                                        resource_handle, token.index) != EP_BRIDGE_OK)
        {
            const EP_BRIDGE_STATUS result = remove_and_release(
                bridge, admission, lease, EP_BRIDGE_CALLBACK_REJECTED);
            if (result == EP_BRIDGE_CLEANUP_REQUIRED) *out_admission = admission;
            return result;
        }
        if (bridge->config.create_player(bridge->config.owner, peer_id,
                                         resource_handle, token.index) != EP_BRIDGE_OK)
        {
            const EP_BRIDGE_STATUS result = remove_and_release(
                bridge, admission, lease, EP_BRIDGE_CALLBACK_REJECTED);
            if (result == EP_BRIDGE_CLEANUP_REQUIRED) *out_admission = admission;
            return result;
        }
        status = ep_sidecar_confirm(&bridge->sidecar, token);
        if (status != EP_SC_OK)
        {
            const EP_BRIDGE_STATUS result = remove_and_release(
                bridge, admission, lease, sidecar_status(status));
            if (result == EP_BRIDGE_CLEANUP_REQUIRED) *out_admission = admission;
            return result;
        }
    }
    *out_admission = admission;
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_bridge_retry_cleanup(
    EP_NATIVE_BRIDGE* bridge, EP_BRIDGE_ADMISSION admission) {
    if (!valid_context(bridge) || !bridge->ready ||
        admission.token.index >= EP_SIDECAR_CAPACITY || admission.token.generation == 0)
        return EP_BRIDGE_INVALID_ARGUMENT;
    OperationGuard operation{bridge};
    if (!operation) return EP_BRIDGE_BUSY;
    // Index alone is insufficient: a delayed retry can address a new player
    // after the same slot is reused. Check the full identity and generation.
    const int found = cleanup_for(bridge, admission);
    if (found < 0) return EP_BRIDGE_INVALID_ARGUMENT;
    auto& item = bridge->cleanup[found];
    const EP_BRIDGE_STATUS status = finish_cleanup(
        bridge, admission, &item.remove_done, &item.index_released);
    if (status != EP_BRIDGE_OK) return status;
    bridge->cleanup[found].pending = 0;
    bridge->cleanup[found].remove_done = 0;
    bridge->cleanup[found].index_released = 0;
    std::memset(&bridge->cleanup[found].admission, 0,
                sizeof(bridge->cleanup[found].admission));
    --bridge->cleanup_count;
    bridge->config.release_owner(bridge->config.owner);
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_bridge_destroy(EP_NATIVE_BRIDGE* bridge) {
    if (!valid_context(bridge)) return EP_BRIDGE_INVALID_CONTEXT;
    OperationGuard operation{bridge};
    if (!operation) return EP_BRIDGE_BUSY;
    if (bridge->cleanup_count != 0) return EP_BRIDGE_CLEANUP_REQUIRED;
    if (bridge->sidecar.active_count != 0) return EP_BRIDGE_INVALID_CONTEXT;
    ep_sidecar_destroy(&bridge->sidecar);
    std::memset(bridge, 0, sizeof(*bridge));
    return EP_BRIDGE_OK;
}

extern "C" UINT32 __cdecl ep_bridge_capacity() { return EP_SIDECAR_CAPACITY; }
