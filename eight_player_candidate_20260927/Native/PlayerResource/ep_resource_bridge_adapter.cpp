#include "ep_resource_bridge_adapter.h"

#include <cstring>

namespace {

bool stage_callbacks_valid(const EP_RESOURCE_BRIDGE_STAGE_CALLBACKS& stages) {
    return stages.version == EP_RESOURCE_BRIDGE_CALLBACK_VERSION &&
           stages.size == sizeof(EP_RESOURCE_BRIDGE_STAGE_CALLBACKS) &&
           stages.first != nullptr && stages.second != nullptr &&
           stages.third != nullptr;
}

bool config_valid(const EP_RESOURCE_BRIDGE_CONFIG& config) {
    return config.version == EP_RESOURCE_BRIDGE_VERSION &&
           config.size == sizeof(EP_RESOURCE_BRIDGE_CONFIG) &&
           config.steam_build == EP_RESOURCE_BRIDGE_BUILD &&
           config.owner_key != 0 && config.native_owner != nullptr &&
           config.native_confirm_peer != nullptr &&
           config.native_create_player != nullptr &&
           config.native_remove_player != nullptr &&
           config.native_allocate_index != nullptr &&
           config.native_release_index != nullptr &&
           config.native_retain_owner != nullptr &&
           config.native_release_owner != nullptr && config.metadata != nullptr &&
           stage_callbacks_valid(config.stages);
}

EP_RESOURCE_BRIDGE_ADAPTER* as_adapter(void* owner) {
    auto* adapter = static_cast<EP_RESOURCE_BRIDGE_ADAPTER*>(owner);
    if (!adapter || adapter->magic != EP_RESOURCE_BRIDGE_MAGIC ||
        adapter->version != EP_RESOURCE_BRIDGE_VERSION ||
        adapter->initialized != 1 || !config_valid(adapter->config))
        return nullptr;
    return adapter;
}

struct CallbackGuard {
    EP_RESOURCE_BRIDGE_ADAPTER* adapter;
    bool held;
    explicit CallbackGuard(EP_RESOURCE_BRIDGE_ADAPTER* value)
        : adapter(value), held(value != nullptr &&
            InterlockedCompareExchange(&value->callback_busy, 1, 0) == 0) {}
    ~CallbackGuard() {
        if (held) InterlockedExchange(&adapter->callback_busy, 0);
    }
    explicit operator bool() const { return held; }
};

EP_BRIDGE_STATUS map_resource(EP_RESOURCE_STATUS status) {
    return status == EP_RS_OK ? EP_BRIDGE_OK : EP_BRIDGE_CALLBACK_REJECTED;
}

EP_RESOURCE_STATUS find_token(EP_PLAYER_RESOURCE* resource, UINT64 peer_id,
                              UINT64 resource_handle, UINT8 network_index,
                              EP_RESOURCE_TOKEN* out_token,
                              EP_RESOURCE_RECORD* out_record) {
    if (!resource || !out_token || !out_record || !peer_id || !resource_handle)
        return EP_RS_INVALID_ARGUMENT;
    bool conflicting_identity = false;
    for (UINT8 i = 0; i < EP_RESOURCE_CAPACITY; ++i) {
        EP_RESOURCE_RECORD record{};
        const EP_RESOURCE_STATUS status = ep_resource_get(resource, i, &record);
        if (status != EP_RS_OK) continue;
        if (record.peer_id != peer_id && record.resource_handle != resource_handle)
            continue;
        if (record.peer_id != peer_id || record.resource_handle != resource_handle) {
            conflicting_identity = true;
            continue;
        }
        if (i != network_index) return EP_RS_DUPLICATE;
        out_token->index = i;
        std::memset(out_token->reserved, 0, sizeof(out_token->reserved));
        out_token->generation = record.generation;
        out_token->owner_epoch = record.owner_epoch;
        *out_record = record;
        return EP_RS_OK;
    }
    return conflicting_identity ? EP_RS_DUPLICATE : EP_RS_STALE_TOKEN;
}

EP_RESOURCE_STATUS run_stage(EP_RESOURCE_BRIDGE_ADAPTER* adapter,
                             EP_RESOURCE_STAGE stage, EP_RESOURCE_STAGE_CB cb,
                             UINT64 peer_id, UINT64 resource_handle,
                             UINT8 network_index, EP_RESOURCE_TOKEN token) {
    EP_RESOURCE_LEASE lease{};
    EP_RESOURCE_STATUS status = ep_resource_begin_callback(
        &adapter->resource, token, &lease);
    if (status != EP_RS_OK) return status;
    const EP_RESOURCE_STATUS callback = cb(
        adapter->config.native_owner, peer_id, resource_handle,
        network_index, token);
    const EP_RESOURCE_STATUS completed = ep_resource_complete_callback(
        &adapter->resource, lease, stage, callback == EP_RS_OK ? TRUE : FALSE);
    if (callback != EP_RS_OK) return callback;
    return completed;
}

EP_BRIDGE_STATUS native_remove_for(EP_RESOURCE_BRIDGE_ADAPTER* adapter,
                                   UINT64 peer_id, UINT64 resource_handle,
                                   UINT8 network_index) {
    return adapter->config.native_remove_player(
        adapter->config.native_owner, peer_id, resource_handle, network_index);
}

} // namespace

extern "C" EP_BRIDGE_STATUS __cdecl ep_resource_bridge_init(
    EP_RESOURCE_BRIDGE_ADAPTER* adapter,
    const EP_RESOURCE_BRIDGE_CONFIG* config) {
    if (!adapter || !config || !config_valid(*config))
        return EP_BRIDGE_CALLBACK_MISSING;
    if (adapter->magic == EP_RESOURCE_BRIDGE_MAGIC && adapter->initialized)
        return EP_BRIDGE_ALREADY_READY;
    std::memset(adapter, 0, sizeof(*adapter));
    adapter->magic = EP_RESOURCE_BRIDGE_MAGIC;
    adapter->version = EP_RESOURCE_BRIDGE_VERSION;
    adapter->config = *config;
    if (ep_resource_init(&adapter->resource, config->owner_key) != EP_RS_OK) {
        std::memset(adapter, 0, sizeof(*adapter));
        return EP_BRIDGE_INVALID_CONTEXT;
    }
    adapter->initialized = 1;
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_resource_bridge_destroy(
    EP_RESOURCE_BRIDGE_ADAPTER* adapter) {
    auto* value = as_adapter(adapter);
    if (!value) return EP_BRIDGE_INVALID_CONTEXT;
    if (value->callback_busy) return EP_BRIDGE_BUSY;
    const EP_RESOURCE_STATUS status = ep_resource_destroy(&value->resource);
    if (status != EP_RS_OK) return EP_BRIDGE_CLEANUP_REQUIRED;
    std::memset(value, 0, sizeof(*value));
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_resource_bridge_configure(
    EP_RESOURCE_BRIDGE_ADAPTER* adapter, HMODULE game_module,
    const EP_BRIDGE_SITE* sites, UINT32 site_count,
    EP_BRIDGE_CONFIG* out_bridge_config) {
    auto* value = as_adapter(adapter);
    if (!value || !game_module || !sites || site_count == 0 || !out_bridge_config)
        return EP_BRIDGE_INVALID_ARGUMENT;
    std::memset(out_bridge_config, 0, sizeof(*out_bridge_config));
    out_bridge_config->steam_build = value->config.steam_build;
    out_bridge_config->game_module = game_module;
    out_bridge_config->sites = sites;
    out_bridge_config->site_count = site_count;
    out_bridge_config->owner = value;
    out_bridge_config->confirm_peer = ep_resource_bridge_confirm;
    out_bridge_config->create_player = ep_resource_bridge_create;
    out_bridge_config->remove_player = ep_resource_bridge_remove;
    out_bridge_config->retain_owner = ep_resource_bridge_retain;
    out_bridge_config->release_owner = ep_resource_bridge_release;
    out_bridge_config->allocate_index = ep_resource_bridge_allocate_index;
    out_bridge_config->release_index = ep_resource_bridge_release_index;
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_resource_bridge_confirm(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index) {
    auto* adapter = as_adapter(owner);
    if (!adapter || !peer_id || !resource_handle || network_index >= EP_RESOURCE_CAPACITY)
        return EP_BRIDGE_INVALID_ARGUMENT;
    CallbackGuard guard{adapter};
    if (!guard) return EP_BRIDGE_BUSY;

    EP_RESOURCE_TOKEN token{};
    EP_RESOURCE_RECORD record{};
    EP_RESOURCE_STATUS status = find_token(
        &adapter->resource, peer_id, resource_handle, network_index,
        &token, &record);
    if (status == EP_RS_OK) {
        if (record.state != EP_RS_PENDING) return EP_BRIDGE_CALLBACK_REJECTED;
    } else if (status != EP_RS_STALE_TOKEN) {
        return EP_BRIDGE_CALLBACK_REJECTED;
    } else {
        UINT64 hash = 0;
        UINT32 ordinal = 0;
        UINT16 component = 0x7fff;
        status = adapter->config.metadata(
            adapter->config.native_owner, peer_id, resource_handle,
            network_index, &hash, &ordinal, &component);
        if (status != EP_RS_OK || !hash || component == 0xffffu)
            return EP_BRIDGE_CALLBACK_REJECTED;
        status = ep_resource_begin(&adapter->resource, network_index, peer_id,
                                   resource_handle, hash, ordinal, component,
                                   &token);
        if (status != EP_RS_OK) return EP_BRIDGE_CALLBACK_REJECTED;
    }
    return adapter->config.native_confirm_peer(
        adapter->config.native_owner, peer_id, resource_handle, network_index);
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_resource_bridge_create(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index) {
    auto* adapter = as_adapter(owner);
    if (!adapter || !peer_id || !resource_handle || network_index >= EP_RESOURCE_CAPACITY)
        return EP_BRIDGE_INVALID_ARGUMENT;
    CallbackGuard guard{adapter};
    if (!guard) return EP_BRIDGE_BUSY;

    EP_RESOURCE_TOKEN token{};
    EP_RESOURCE_RECORD record{};
    if (find_token(&adapter->resource, peer_id, resource_handle,
                   network_index, &token, &record) != EP_RS_OK ||
        record.state != EP_RS_PENDING)
        return EP_BRIDGE_CALLBACK_REJECTED;
    const EP_BRIDGE_STATUS created = adapter->config.native_create_player(
        adapter->config.native_owner, peer_id, resource_handle, network_index);
    if (created != EP_BRIDGE_OK) return created;

    const EP_RESOURCE_STAGE_CB stages[] = {
        adapter->config.stages.first, adapter->config.stages.second,
        adapter->config.stages.third,
    };
    for (UINT8 i = 0; i < 3; ++i) {
        const EP_RESOURCE_STATUS stage = run_stage(
            adapter, static_cast<EP_RESOURCE_STAGE>(i), stages[i], peer_id,
            resource_handle, network_index, token);
        if (stage != EP_RS_OK) return EP_BRIDGE_CALLBACK_REJECTED;
    }
    if (ep_resource_publish(&adapter->resource, token) != EP_RS_OK)
        return EP_BRIDGE_CALLBACK_REJECTED;
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_resource_bridge_remove(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index) {
    auto* adapter = as_adapter(owner);
    if (!adapter || !peer_id || !resource_handle || network_index >= EP_RESOURCE_CAPACITY)
        return EP_BRIDGE_INVALID_ARGUMENT;
    CallbackGuard guard{adapter};
    if (!guard) return EP_BRIDGE_BUSY;

    EP_RESOURCE_TOKEN token{};
    EP_RESOURCE_RECORD record{};
    const EP_RESOURCE_STATUS found = find_token(
        &adapter->resource, peer_id, resource_handle, network_index,
        &token, &record);
    if (found != EP_RS_OK && found != EP_RS_STALE_TOKEN)
        return EP_BRIDGE_CALLBACK_REJECTED;
    const EP_BRIDGE_STATUS removed = native_remove_for(
        adapter, peer_id, resource_handle, network_index);
    if (removed != EP_BRIDGE_OK) return removed;
    if (found == EP_RS_OK) {
        const EP_RESOURCE_STATUS released = ep_resource_release(
            &adapter->resource, token);
        if (released != EP_RS_OK && released != EP_RS_ALREADY_RELEASED)
            return EP_BRIDGE_CALLBACK_REJECTED;
    }
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_resource_bridge_allocate_index(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8* out_index) {
    auto* adapter = as_adapter(owner);
    if (!adapter || !out_index || !peer_id || !resource_handle)
        return EP_BRIDGE_INVALID_ARGUMENT;
    return adapter->config.native_allocate_index(
        adapter->config.native_owner, peer_id, resource_handle, out_index);
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_resource_bridge_release_index(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index,
    UINT32 generation) {
    auto* adapter = as_adapter(owner);
    if (!adapter || !peer_id || !resource_handle ||
        network_index >= EP_RESOURCE_CAPACITY)
        return EP_BRIDGE_INVALID_ARGUMENT;
    return adapter->config.native_release_index(
        adapter->config.native_owner, peer_id, resource_handle,
        network_index, generation);
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_resource_bridge_retain(void* owner) {
    auto* adapter = as_adapter(owner);
    if (!adapter) return EP_BRIDGE_INVALID_CONTEXT;
    return adapter->config.native_retain_owner(adapter->config.native_owner);
}

extern "C" void __cdecl ep_resource_bridge_release(void* owner) {
    auto* adapter = as_adapter(owner);
    if (adapter) adapter->config.native_release_owner(adapter->config.native_owner);
}

extern "C" UINT32 __cdecl ep_resource_bridge_version() {
    return EP_RESOURCE_BRIDGE_VERSION;
}

extern "C" UINT32 __cdecl ep_resource_bridge_build() {
    return EP_RESOURCE_BRIDGE_BUILD;
}
