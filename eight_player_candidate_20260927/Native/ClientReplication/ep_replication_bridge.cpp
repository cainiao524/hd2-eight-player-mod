#include "ep_replication_bridge.h"

#include <cstring>

namespace {

static_assert(EP_CR_CAPACITY == EP_SIDECAR_CAPACITY);

EP_REPLICATION_BRIDGE* adapter(void* owner) {
    auto* value = static_cast<EP_REPLICATION_BRIDGE*>(owner);
    return value && value->magic == EP_REPLICATION_BRIDGE_MAGIC ? value : nullptr;
}

bool matches(const EP_REPLICATION_BRIDGE_SLOT& record, UINT64 peer, UINT64 resource) {
    return record.peer_id == peer && record.resource_handle == resource;
}

// The outer bridge owns compensation and the owner lease. Convert a callback
// exception to a status so its existing cleanup/retry path is still reached.
template <typename Operation>
EP_BRIDGE_STATUS call(Operation operation) {
    try { return operation(); }
    catch (...) { return EP_BRIDGE_CALLBACK_REJECTED; }
}

EP_BRIDGE_STATUS __cdecl confirm(void* owner, UINT64 peer, UINT64 resource, UINT8 index) {
    auto* a = adapter(owner);
    if (!a || !peer || !resource || index >= EP_CR_CAPACITY)
        return EP_BRIDGE_INVALID_ARGUMENT;
    auto& record = a->slots[index];
    if (record.peer_id != 0) return EP_BRIDGE_INDEX_REJECTED;
    record.peer_id = peer;
    record.resource_handle = resource;
    UINT32 mask = 0;
    auto status = call([&] { return a->membership(a->downstream.owner, peer, resource, index, &mask); });
    if (status != EP_BRIDGE_OK) return status;
    if (!(mask & EP_CR_ARRAY_CONFIRMED_32) || (mask & ~EP_CR_ARRAY_ALL))
        return EP_BRIDGE_CALLBACK_REJECTED;

    // Record partial native work before dispatch, including a thrown callback.
    record.native_started = TRUE;
    status = call([&] { return a->downstream.confirm_peer(a->downstream.owner, peer, resource, index); });
    if (status != EP_BRIDGE_OK) return status;
    // CR returns a token even if its callback and compensation both fail.
    const auto replicated = ep_cr_append(&a->replication, index, peer, resource,
                                         mask, &record.replication_token);
    return replicated == EP_CR_OK ? EP_BRIDGE_OK : EP_BRIDGE_CALLBACK_REJECTED;
}

EP_BRIDGE_STATUS __cdecl create(void* owner, UINT64 peer, UINT64 resource, UINT8 index) {
    auto* a = adapter(owner);
    if (!a || index >= EP_CR_CAPACITY) return EP_BRIDGE_INVALID_ARGUMENT;
    auto& record = a->slots[index];
    if (!matches(record, peer, resource) || !record.native_started ||
        record.replication_token.generation == 0) return EP_BRIDGE_CALLBACK_REJECTED;
    const auto status = call([&] { return a->downstream.create_player(a->downstream.owner, peer, resource, index); });
    if (status != EP_BRIDGE_OK) return status;
    // Publish replication readiness only after native player creation. The
    // outer bridge publishes its own confirmed state only after this succeeds.
    return ep_cr_confirm(&a->replication, record.replication_token) == EP_CR_OK
        ? EP_BRIDGE_OK : EP_BRIDGE_CALLBACK_REJECTED;
}

EP_BRIDGE_STATUS __cdecl remove(void* owner, UINT64 peer, UINT64 resource, UINT8 index) {
    auto* a = adapter(owner);
    if (!a || index >= EP_CR_CAPACITY) return EP_BRIDGE_INVALID_ARGUMENT;
    auto& record = a->slots[index];
    if (!matches(record, peer, resource)) return EP_BRIDGE_CALLBACK_REJECTED;
    if (record.replication_token.generation != 0) {
        EP_CR_SLOT slot{};
        const auto found = ep_cr_get(&a->replication, index, &slot);
        if (found == EP_CR_OK) {
            if (slot.peer_id != peer || slot.resource_handle != resource ||
                slot.generation != record.replication_token.generation)
                return EP_BRIDGE_CALLBACK_REJECTED;
            const auto cleared = slot.state == EP_CR_ROLLBACK
                ? ep_cr_retry_rollback(&a->replication, record.replication_token)
                : ep_cr_remove(&a->replication, record.replication_token);
            if (cleared != EP_CR_OK) return EP_BRIDGE_CLEANUP_REQUIRED;
        } else if (found != EP_CR_NOT_FOUND) {
            return EP_BRIDGE_CLEANUP_REQUIRED;
        }
        // A failed append/confirm may already have completed compensation.
        record.replication_token = {};
    }
    if (record.native_started) {
        const auto status = call([&] { return a->downstream.remove_player(a->downstream.owner, peer, resource, index); });
        if (status != EP_BRIDGE_OK) return status;
        record.native_started = FALSE;
    }
    // Keep identity until allocator release succeeds. A release-only retry
    // must not dispatch client removal twice or lose the reserved index.
    return EP_BRIDGE_OK;
}

EP_BRIDGE_STATUS __cdecl allocate(void* owner, UINT64 peer, UINT64 resource, UINT8* index) {
    auto* a = adapter(owner);
    if (!a || !index) return EP_BRIDGE_INVALID_ARGUMENT;
    return call([&] { return a->downstream.allocate_index(a->downstream.owner, peer, resource, index); });
}

EP_BRIDGE_STATUS __cdecl release_index(void* owner, UINT64 peer, UINT64 resource,
                                      UINT8 index, UINT32 generation) {
    auto* a = adapter(owner);
    if (!a) return EP_BRIDGE_INVALID_ARGUMENT;
    EP_REPLICATION_BRIDGE_SLOT* record = index < EP_CR_CAPACITY ? &a->slots[index] : nullptr;
    if (record && record->peer_id != 0 &&
        (!matches(*record, peer, resource) || record->native_started ||
         record->replication_token.generation != 0)) return EP_BRIDGE_CLEANUP_REQUIRED;
    const auto status = call([&] { return a->downstream.release_index(a->downstream.owner, peer, resource, index, generation); });
    if (status == EP_BRIDGE_OK && record) *record = {};
    return status;
}

EP_BRIDGE_STATUS __cdecl retain(void* owner) {
    auto* a = adapter(owner);
    return a ? a->downstream.retain_owner(a->downstream.owner) : EP_BRIDGE_INVALID_CONTEXT;
}

void __cdecl release(void* owner) {
    auto* a = adapter(owner);
    if (a) a->downstream.release_owner(a->downstream.owner);
}

}  // namespace

extern "C" EP_BRIDGE_STATUS __cdecl ep_replication_bridge_init(
    EP_REPLICATION_BRIDGE* a, const EP_BRIDGE_CONFIG* downstream,
    const EP_CR_CALLBACKS* callbacks, EP_REPLICATION_MEMBERSHIP_CB membership,
    UINT64 owner_key, UINT32 owner_epoch) {
    if (!a || !downstream || !membership || !downstream->owner ||
        !downstream->confirm_peer || !downstream->create_player ||
        !downstream->remove_player || !downstream->allocate_index ||
        !downstream->release_index || !downstream->retain_owner ||
        !downstream->release_owner) return EP_BRIDGE_CALLBACK_MISSING;
    if (a->magic == EP_REPLICATION_BRIDGE_MAGIC) return EP_BRIDGE_ALREADY_READY;
    if (downstream->steam_build != EP_CR_BUILD) return EP_BRIDGE_BUILD_MISMATCH;
    // Never fall back to the bridge's legacy unlimited harness contract.
    if (!downstream->capacity) return EP_BRIDGE_CAPACITY_REJECTED;
    std::memset(a, 0, sizeof(*a));
    if (ep_cr_init(&a->replication, downstream->steam_build, callbacks,
                   owner_key, owner_epoch) != EP_CR_OK) return EP_BRIDGE_INVALID_ARGUMENT;
    a->downstream = *downstream;
    a->membership = membership;
    EP_BRIDGE_CONFIG wrapped = *downstream;
    wrapped.owner = a;
    wrapped.confirm_peer = confirm;
    wrapped.create_player = create;
    wrapped.remove_player = remove;
    wrapped.allocate_index = allocate;
    wrapped.release_index = release_index;
    wrapped.retain_owner = retain;
    wrapped.release_owner = release;
    const auto status = ep_bridge_init(&a->admission, &wrapped);
    if (status != EP_BRIDGE_OK) {
        ep_cr_destroy(&a->replication);
        return status;
    }
    a->magic = EP_REPLICATION_BRIDGE_MAGIC;
    return EP_BRIDGE_OK;
}

extern "C" EP_BRIDGE_STATUS __cdecl ep_replication_bridge_destroy(EP_REPLICATION_BRIDGE* a) {
    if (!adapter(a)) return EP_BRIDGE_INVALID_CONTEXT;
    if (ep_cr_validate(&a->replication) != EP_CR_OK || a->replication.active_count ||
        a->replication.callback_leases || a->replication.migration_in_progress)
        return EP_BRIDGE_CLEANUP_REQUIRED;
    for (const auto& record : a->slots)
        if (record.peer_id != 0) return EP_BRIDGE_CLEANUP_REQUIRED;
    const auto status = ep_bridge_destroy(&a->admission);
    if (status != EP_BRIDGE_OK) return status;
    if (ep_cr_destroy(&a->replication) != EP_CR_OK) return EP_BRIDGE_CLEANUP_REQUIRED;
    a->magic = 0;
    return EP_BRIDGE_OK;
}
