#include "ep_client_sidecar.h"

#include <cstring>

namespace {

bool valid(const EP_CLIENT_SIDECAR* s) {
    return s != nullptr && s->magic == EP_CLIENT_SIDECAR_MAGIC &&
           s->version == EP_CLIENT_SIDECAR_VERSION &&
           s->build == EP_CLIENT_SIDECAR_BUILD && s->initialized != 0;
}

bool lock(volatile LONG* value) {
    for (unsigned i = 0; i < 1000; ++i) {
        if (InterlockedCompareExchange(value, 1, 0) == 0) return true;
        YieldProcessor();
    }
    return false;
}

void unlock(volatile LONG* value) { InterlockedExchange(value, 0); }

void clear_entry(EP_CLIENT_SIDE_ENTRY& e) { std::memset(&e, 0, sizeof(e)); }

void mirror(EP_CLIENT_SIDECAR* s, UINT32 i, UINT64 peer, UINT32 present) {
    EP_CLIENT_SIDE_ENTRY* entries[] = {
        &s->adjacent_8[i], &s->adjacent_16[i], &s->adjacent_16b[i],
        &s->confirmed_32[i], &s->peer_keyed[i],
    };
    for (auto* e : entries) {
        e->peer_id = peer;
        e->network_index = i;
        e->present = present;
    }
}

} // namespace

extern "C" EP_CLIENT_STATUS __cdecl ep_client_init(
    EP_CLIENT_SIDECAR* s, UINT32 build) {
    if (!s) return EP_CLIENT_INVALID_ARGUMENT;
    if (build != EP_CLIENT_SIDECAR_BUILD) return EP_CLIENT_INVALID_ARGUMENT;
    std::memset(s, 0, sizeof(*s));
    s->magic = EP_CLIENT_SIDECAR_MAGIC;
    s->version = EP_CLIENT_SIDECAR_VERSION;
    s->build = build;
    s->initialized = 1;
    InitializeSRWLock(&s->lock);
    return EP_CLIENT_OK;
}

extern "C" EP_CLIENT_STATUS __cdecl ep_client_destroy(EP_CLIENT_SIDECAR* s) {
    if (!valid(s)) return EP_CLIENT_INVALID_CONTEXT;
    if (s->confirmed_count != 0) return EP_CLIENT_INVALID_CONTEXT;
    s->initialized = 0;
    s->magic = 0;
    return EP_CLIENT_OK;
}

extern "C" EP_CLIENT_STATUS __cdecl ep_client_append(
    EP_CLIENT_SIDECAR* s, UINT64 peer_id, UINT64 resource_handle,
    UINT32 network_index, UINT32* out_generation) {
    if (!valid(s) || !out_generation || peer_id == 0 || resource_handle == 0)
        return EP_CLIENT_INVALID_ARGUMENT;
    if (network_index >= EP_CLIENT_CAPACITY) return EP_CLIENT_INDEX_REJECTED;
    if (!lock(reinterpret_cast<volatile LONG*>(&s->lock)))
        return EP_CLIENT_INVALID_CONTEXT;
    for (UINT32 i = 0; i < EP_CLIENT_CAPACITY; ++i) {
        if (!s->records[i].present) continue;
        if (s->records[i].peer_id == peer_id) {
            unlock(reinterpret_cast<volatile LONG*>(&s->lock));
            return EP_CLIENT_DUPLICATE_PEER;
        }
        if (s->records[i].resource_handle == resource_handle) {
            unlock(reinterpret_cast<volatile LONG*>(&s->lock));
            return EP_CLIENT_DUPLICATE_RESOURCE;
        }
    }
    if (s->records[network_index].present) {
        unlock(reinterpret_cast<volatile LONG*>(&s->lock));
        return EP_CLIENT_FULL;
    }
    UINT32 generation = s->generation[network_index];
    if (generation == 0xFFFFFFFFu) {
        unlock(reinterpret_cast<volatile LONG*>(&s->lock));
        return EP_CLIENT_STALE_GENERATION;
    }
    ++generation;
    s->generation[network_index] = generation;
    s->records[network_index] = {peer_id, resource_handle, network_index,
                                  generation, 1, 0};
    mirror(s, network_index, peer_id, 1);
    ++s->confirmed_count;
    *out_generation = generation;
    unlock(reinterpret_cast<volatile LONG*>(&s->lock));
    return EP_CLIENT_OK;
}

extern "C" EP_CLIENT_STATUS __cdecl ep_client_remove(
    EP_CLIENT_SIDECAR* s, UINT32 network_index, UINT32 generation) {
    if (!valid(s)) return EP_CLIENT_INVALID_CONTEXT;
    if (network_index >= EP_CLIENT_CAPACITY) return EP_CLIENT_INDEX_REJECTED;
    if (!lock(reinterpret_cast<volatile LONG*>(&s->lock)))
        return EP_CLIENT_INVALID_CONTEXT;
    const EP_CLIENT_RECORD& r = s->records[network_index];
    if (!r.present) {
        unlock(reinterpret_cast<volatile LONG*>(&s->lock));
        return EP_CLIENT_NOT_FOUND;
    }
    if (r.generation != generation) {
        unlock(reinterpret_cast<volatile LONG*>(&s->lock));
        return EP_CLIENT_STALE_GENERATION;
    }
    std::memset(&s->records[network_index], 0, sizeof(s->records[network_index]));
    mirror(s, network_index, 0, 0);
    --s->confirmed_count;
    unlock(reinterpret_cast<volatile LONG*>(&s->lock));
    return EP_CLIENT_OK;
}

extern "C" EP_CLIENT_STATUS __cdecl ep_client_get(
    EP_CLIENT_SIDECAR* s, UINT32 network_index, EP_CLIENT_RECORD* out) {
    if (!valid(s) || !out) return EP_CLIENT_INVALID_ARGUMENT;
    if (network_index >= EP_CLIENT_CAPACITY) return EP_CLIENT_INDEX_REJECTED;
    if (!lock(reinterpret_cast<volatile LONG*>(&s->lock)))
        return EP_CLIENT_INVALID_CONTEXT;
    *out = s->records[network_index];
    unlock(reinterpret_cast<volatile LONG*>(&s->lock));
    return out->present ? EP_CLIENT_OK : EP_CLIENT_NOT_FOUND;
}

extern "C" EP_CLIENT_STATUS __cdecl ep_client_reset(EP_CLIENT_SIDECAR* s) {
    if (!valid(s)) return EP_CLIENT_INVALID_CONTEXT;
    if (!lock(reinterpret_cast<volatile LONG*>(&s->lock)))
        return EP_CLIENT_INVALID_CONTEXT;
    for (UINT32 i = 0; i < EP_CLIENT_CAPACITY; ++i) {
        std::memset(&s->records[i], 0, sizeof(s->records[i]));
        clear_entry(s->adjacent_8[i]);
        clear_entry(s->adjacent_16[i]);
        clear_entry(s->adjacent_16b[i]);
        clear_entry(s->confirmed_32[i]);
        clear_entry(s->peer_keyed[i]);
    }
    s->confirmed_count = 0;
    unlock(reinterpret_cast<volatile LONG*>(&s->lock));
    return EP_CLIENT_OK;
}

extern "C" EP_CLIENT_STATUS __cdecl ep_client_creation_gate(
    EP_CLIENT_SIDECAR* s, UINT32 network_index) {
    if (!valid(s)) return EP_CLIENT_INVALID_CONTEXT;
    if (network_index >= EP_CLIENT_CAPACITY) return EP_CLIENT_INDEX_REJECTED;
    return network_index >= 4 ? EP_CLIENT_CREATION_REQUIRED : EP_CLIENT_OK;
}

extern "C" EP_CLIENT_STATUS __cdecl ep_client_validate(EP_CLIENT_SIDECAR* s) {
    if (!valid(s)) return EP_CLIENT_INVALID_CONTEXT;
    if (!lock(reinterpret_cast<volatile LONG*>(&s->lock)))
        return EP_CLIENT_INVALID_CONTEXT;
    UINT32 count = 0;
    for (UINT32 i = 0; i < EP_CLIENT_CAPACITY; ++i) {
        const auto& r = s->records[i];
        if (!r.present) {
            if (s->adjacent_8[i].present || s->adjacent_16[i].present ||
                s->adjacent_16b[i].present || s->confirmed_32[i].present ||
                s->peer_keyed[i].present) {
                unlock(reinterpret_cast<volatile LONG*>(&s->lock));
                return EP_CLIENT_INVARIANT_BROKEN;
            }
            continue;
        }
        if (r.network_index != i || r.generation == 0 ||
            !s->adjacent_8[i].present || !s->adjacent_16[i].present ||
            !s->adjacent_16b[i].present || !s->confirmed_32[i].present ||
            !s->peer_keyed[i].present) {
            unlock(reinterpret_cast<volatile LONG*>(&s->lock));
            return EP_CLIENT_INVARIANT_BROKEN;
        }
        ++count;
    }
    const auto status = count == s->confirmed_count
        ? EP_CLIENT_OK : EP_CLIENT_INVARIANT_BROKEN;
    unlock(reinterpret_cast<volatile LONG*>(&s->lock));
    return status;
}

extern "C" UINT32 __cdecl ep_client_capacity() { return EP_CLIENT_CAPACITY; }
