#include "ep_sidecar.h"

#include <cstring>

namespace {

bool valid_identity(UINT64 peer_id, UINT64 resource_handle) {
    return peer_id != 0 && resource_handle != 0;
}

bool valid_state(UINT8 state) {
    return state == EP_SC_SLOT_FREE || state == EP_SC_SLOT_PENDING ||
           state == EP_SC_SLOT_CONFIRMED;
}

bool valid_token(const EP_SIDECAR_TOKEN& token) {
    return token.index < EP_SIDECAR_CAPACITY && token.generation != 0;
}

EP_SIDECAR_STATUS validate_unlocked(const EP_SIDECAR* sidecar) {
    if (!sidecar || sidecar->magic != EP_SIDECAR_MAGIC ||
        sidecar->version != EP_SIDECAR_VERSION || sidecar->initialized != 1 ||
        sidecar->reserved != 0 || sidecar->active_count > EP_SIDECAR_CAPACITY ||
        sidecar->confirmed_count > sidecar->active_count) {
        return EP_SC_INVALID_CONTEXT;
    }

    UINT32 active = 0;
    UINT32 confirmed = 0;
    for (UINT32 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        const EP_SIDECAR_SLOT& slot = sidecar->slots[i];
        if (!valid_state(slot.state)) return EP_SC_INVARIANT_BROKEN;
        if (slot.state == EP_SC_SLOT_FREE) {
            // A freed slot may retain its last generation so stale tokens can
            // never become valid again.  Its identity must be gone.
            if (slot.peer_id != 0 || slot.resource_handle != 0) {
                return EP_SC_INVARIANT_BROKEN;
            }
            continue;
        }
        if (slot.generation == 0 || !valid_identity(slot.peer_id, slot.resource_handle)) {
            return EP_SC_INVARIANT_BROKEN;
        }
        ++active;
        if (slot.state == EP_SC_SLOT_CONFIRMED) ++confirmed;
        for (UINT32 j = 0; j < i; ++j) {
            const EP_SIDECAR_SLOT& prior = sidecar->slots[j];
            if (prior.state == EP_SC_SLOT_FREE) continue;
            if (prior.peer_id == slot.peer_id) return EP_SC_INVARIANT_BROKEN;
            if (prior.resource_handle == slot.resource_handle) return EP_SC_INVARIANT_BROKEN;
        }
    }
    if (active != sidecar->active_count || confirmed != sidecar->confirmed_count) {
        return EP_SC_INVARIANT_BROKEN;
    }
    return EP_SC_OK;
}

EP_SIDECAR_STATUS begin_exclusive(EP_SIDECAR* sidecar) {
    if (!sidecar) return EP_SC_INVALID_ARGUMENT;
    AcquireSRWLockExclusive(&sidecar->lock);
    const EP_SIDECAR_STATUS status = validate_unlocked(sidecar);
    if (status != EP_SC_OK) {
        ReleaseSRWLockExclusive(&sidecar->lock);
        return status;
    }
    return EP_SC_OK;
}

EP_SIDECAR_STATUS reserve_at_unlocked(EP_SIDECAR* sidecar, UINT8 index,
                                      UINT64 peer_id, UINT64 resource_handle,
                                      EP_SIDECAR_TOKEN* out_token);

EP_SIDECAR_STATUS reserve_unlocked(EP_SIDECAR* sidecar, UINT64 peer_id,
                                   UINT64 resource_handle,
                                   EP_SIDECAR_TOKEN* out_token) {
    if (!valid_identity(peer_id, resource_handle) || !out_token) {
        return EP_SC_INVALID_ARGUMENT;
    }
    std::memset(out_token, 0, sizeof(*out_token));

    bool free_slot_seen = false;
    for (UINT32 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        const EP_SIDECAR_SLOT& slot = sidecar->slots[i];
        if (slot.state == EP_SC_SLOT_FREE) {
            free_slot_seen = true;
            continue;
        }
        if (slot.peer_id == peer_id) return EP_SC_DUPLICATE_IDENTITY;
        if (slot.resource_handle == resource_handle) return EP_SC_DUPLICATE_RESOURCE;
    }
    if (!free_slot_seen) return EP_SC_FULL;

    for (UINT32 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        EP_SIDECAR_SLOT& slot = sidecar->slots[i];
        if (slot.state != EP_SC_SLOT_FREE) continue;
        const EP_SIDECAR_STATUS result = reserve_at_unlocked(
            sidecar, static_cast<UINT8>(i), peer_id, resource_handle, out_token);
        if (result == EP_SC_OK) return result;
        if (result != EP_SC_GENERATION_EXHAUSTED) return result;
    }
    return EP_SC_GENERATION_EXHAUSTED;
}

EP_SIDECAR_STATUS reserve_at_unlocked(EP_SIDECAR* sidecar, UINT8 index,
                                      UINT64 peer_id, UINT64 resource_handle,
                                      EP_SIDECAR_TOKEN* out_token) {
    if (!valid_identity(peer_id, resource_handle) || !out_token) {
        return EP_SC_INVALID_ARGUMENT;
    }
    if (index >= EP_SIDECAR_CAPACITY) return EP_SC_INVALID_TOKEN;
    std::memset(out_token, 0, sizeof(*out_token));
    for (UINT32 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        const EP_SIDECAR_SLOT& slot = sidecar->slots[i];
        if (slot.state == EP_SC_SLOT_FREE) continue;
        if (slot.peer_id == peer_id) return EP_SC_DUPLICATE_IDENTITY;
        if (slot.resource_handle == resource_handle) return EP_SC_DUPLICATE_RESOURCE;
    }
    EP_SIDECAR_SLOT& slot = sidecar->slots[index];
    if (slot.state != EP_SC_SLOT_FREE) return EP_SC_INDEX_OCCUPIED;
    if (slot.generation == 0xFFFFFFFFu) return EP_SC_GENERATION_EXHAUSTED;
    const UINT32 generation = slot.generation + 1;
    slot.state = EP_SC_SLOT_PENDING;
    slot.generation = generation;
    slot.peer_id = peer_id;
    slot.resource_handle = resource_handle;
    ++sidecar->active_count;
    out_token->index = index;
    out_token->generation = generation;
    return EP_SC_OK;
}

EP_SIDECAR_STATUS check_token_unlocked(const EP_SIDECAR* sidecar,
                                       const EP_SIDECAR_TOKEN& token,
                                       EP_SIDECAR_SLOT** out_slot) {
    if (!valid_token(token)) return EP_SC_INVALID_TOKEN;
    EP_SIDECAR_SLOT* slot = const_cast<EP_SIDECAR_SLOT*>(&sidecar->slots[token.index]);
    if (slot->generation != token.generation) return EP_SC_STALE_TOKEN;
    if (slot->state == EP_SC_SLOT_FREE) return EP_SC_STALE_TOKEN;
    if (out_slot) *out_slot = slot;
    return EP_SC_OK;
}

}  // namespace

extern "C" EP_SIDECAR_STATUS __cdecl ep_sidecar_init(EP_SIDECAR* sidecar) {
    if (!sidecar) return EP_SC_INVALID_ARGUMENT;
    // Initialization is a caller-owned quiescent operation.  The sidecar has
    // no heap allocations and can be placed in a host or client-owned arena.
    std::memset(sidecar, 0, sizeof(*sidecar));
    InitializeSRWLock(&sidecar->lock);
    sidecar->magic = EP_SIDECAR_MAGIC;
    sidecar->version = EP_SIDECAR_VERSION;
    sidecar->initialized = 1;
    return EP_SC_OK;
}

extern "C" EP_SIDECAR_STATUS __cdecl ep_sidecar_destroy(EP_SIDECAR* sidecar) {
    if (!sidecar) return EP_SC_INVALID_ARGUMENT;
    AcquireSRWLockExclusive(&sidecar->lock);
    const EP_SIDECAR_STATUS valid = validate_unlocked(sidecar);
    if (valid != EP_SC_OK) {
        ReleaseSRWLockExclusive(&sidecar->lock);
        return valid;
    }
    for (EP_SIDECAR_SLOT& slot : sidecar->slots) {
        slot.state = EP_SC_SLOT_FREE;
        slot.peer_id = 0;
        slot.resource_handle = 0;
    }
    sidecar->active_count = 0;
    sidecar->confirmed_count = 0;
    sidecar->initialized = 0;
    sidecar->magic = 0;
    sidecar->version = 0;
    sidecar->reserved = 0;
    ReleaseSRWLockExclusive(&sidecar->lock);
    return EP_SC_OK;
}

extern "C" EP_SIDECAR_STATUS __cdecl ep_sidecar_reserve(
    EP_SIDECAR* sidecar, UINT64 peer_id, UINT64 resource_handle,
    EP_SIDECAR_TOKEN* out_token) {
    if (!sidecar) return EP_SC_INVALID_ARGUMENT;
    const EP_SIDECAR_STATUS status = begin_exclusive(sidecar);
    if (status != EP_SC_OK) return status;
    const EP_SIDECAR_STATUS result = reserve_unlocked(sidecar, peer_id, resource_handle, out_token);
    ReleaseSRWLockExclusive(&sidecar->lock);
    return result;
}

extern "C" EP_SIDECAR_STATUS __cdecl ep_sidecar_reserve_at(
    EP_SIDECAR* sidecar, UINT8 index, UINT64 peer_id, UINT64 resource_handle,
    EP_SIDECAR_TOKEN* out_token) {
    if (!sidecar) return EP_SC_INVALID_ARGUMENT;
    const EP_SIDECAR_STATUS status = begin_exclusive(sidecar);
    if (status != EP_SC_OK) return status;
    const EP_SIDECAR_STATUS result = reserve_at_unlocked(
        sidecar, index, peer_id, resource_handle, out_token);
    ReleaseSRWLockExclusive(&sidecar->lock);
    return result;
}

extern "C" EP_SIDECAR_STATUS __cdecl ep_sidecar_confirm(
    EP_SIDECAR* sidecar, EP_SIDECAR_TOKEN token) {
    if (!sidecar) return EP_SC_INVALID_ARGUMENT;
    const EP_SIDECAR_STATUS status = begin_exclusive(sidecar);
    if (status != EP_SC_OK) return status;
    EP_SIDECAR_SLOT* slot = nullptr;
    EP_SIDECAR_STATUS result = check_token_unlocked(sidecar, token, &slot);
    if (result == EP_SC_OK) {
        if (slot->state == EP_SC_SLOT_CONFIRMED) {
            result = EP_SC_ALREADY_CONFIRMED;
        } else if (slot->state != EP_SC_SLOT_PENDING) {
            result = EP_SC_INVALID_STATE;
        } else {
            slot->state = EP_SC_SLOT_CONFIRMED;
            ++sidecar->confirmed_count;
        }
    }
    ReleaseSRWLockExclusive(&sidecar->lock);
    return result;
}

extern "C" EP_SIDECAR_STATUS __cdecl ep_sidecar_remove(
    EP_SIDECAR* sidecar, EP_SIDECAR_TOKEN token) {
    if (!sidecar) return EP_SC_INVALID_ARGUMENT;
    const EP_SIDECAR_STATUS status = begin_exclusive(sidecar);
    if (status != EP_SC_OK) return status;
    EP_SIDECAR_SLOT* slot = nullptr;
    EP_SIDECAR_STATUS result = check_token_unlocked(sidecar, token, &slot);
    if (result == EP_SC_OK) {
        if (slot->state == EP_SC_SLOT_CONFIRMED) --sidecar->confirmed_count;
        --sidecar->active_count;
        slot->state = EP_SC_SLOT_FREE;
        slot->peer_id = 0;
        slot->resource_handle = 0;
    }
    ReleaseSRWLockExclusive(&sidecar->lock);
    return result;
}

extern "C" EP_SIDECAR_STATUS __cdecl ep_sidecar_reconnect(
    EP_SIDECAR* sidecar, UINT64 peer_id, UINT64 resource_handle,
    EP_SIDECAR_TOKEN* out_token) {
    if (!sidecar) return EP_SC_INVALID_ARGUMENT;
    const EP_SIDECAR_STATUS status = begin_exclusive(sidecar);
    if (status != EP_SC_OK) return status;
    if (!valid_identity(peer_id, resource_handle) || !out_token) {
        ReleaseSRWLockExclusive(&sidecar->lock);
        return EP_SC_INVALID_ARGUMENT;
    }
    std::memset(out_token, 0, sizeof(*out_token));
    for (UINT32 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        const EP_SIDECAR_SLOT& slot = sidecar->slots[i];
        if (slot.state == EP_SC_SLOT_FREE) continue;
        if (slot.peer_id == peer_id && slot.resource_handle == resource_handle) {
            out_token->index = static_cast<UINT8>(i);
            out_token->generation = slot.generation;
            ReleaseSRWLockExclusive(&sidecar->lock);
            return EP_SC_OK;
        }
        if (slot.peer_id == peer_id) {
            ReleaseSRWLockExclusive(&sidecar->lock);
            return EP_SC_DUPLICATE_IDENTITY;
        }
        if (slot.resource_handle == resource_handle) {
            ReleaseSRWLockExclusive(&sidecar->lock);
            return EP_SC_DUPLICATE_RESOURCE;
        }
    }
    const EP_SIDECAR_STATUS result = reserve_unlocked(sidecar, peer_id, resource_handle, out_token);
    ReleaseSRWLockExclusive(&sidecar->lock);
    return result;
}

extern "C" EP_SIDECAR_STATUS __cdecl ep_sidecar_get_slot(
    EP_SIDECAR* sidecar, UINT8 index, EP_SIDECAR_SLOT* out_slot) {
    if (!sidecar || !out_slot) return EP_SC_INVALID_ARGUMENT;
    std::memset(out_slot, 0, sizeof(*out_slot));
    const EP_SIDECAR_STATUS status = begin_exclusive(sidecar);
    if (status != EP_SC_OK) return status;
    if (index >= EP_SIDECAR_CAPACITY) {
        ReleaseSRWLockExclusive(&sidecar->lock);
        return EP_SC_INVALID_ARGUMENT;
    }
    *out_slot = sidecar->slots[index];
    ReleaseSRWLockExclusive(&sidecar->lock);
    return EP_SC_OK;
}

extern "C" EP_SIDECAR_STATUS __cdecl ep_sidecar_validate(EP_SIDECAR* sidecar) {
    if (!sidecar) return EP_SC_INVALID_ARGUMENT;
    AcquireSRWLockShared(&sidecar->lock);
    const EP_SIDECAR_STATUS result = validate_unlocked(sidecar);
    ReleaseSRWLockShared(&sidecar->lock);
    return result;
}

extern "C" UINT32 __cdecl ep_sidecar_capacity() {
    return EP_SIDECAR_CAPACITY;
}
