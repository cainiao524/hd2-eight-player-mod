#include "ep_client_replication_contract.h"

#include <cstring>

namespace {

bool valid_state(UINT8 state) {
    return state == EP_CR_FREE || state == EP_CR_PENDING ||
           state == EP_CR_CONFIRMED || state == EP_CR_ROLLBACK;
}

bool valid_identity(UINT64 peer, UINT64 resource) {
    return peer != 0 && resource != 0;
}

bool valid_token(const EP_CR_TOKEN& token) {
    return token.network_index < EP_CR_CAPACITY && token.generation != 0;
}

bool valid_callbacks(const EP_CR_CALLBACKS* callbacks) {
    return callbacks && callbacks->size >= sizeof(EP_CR_CALLBACKS) &&
           callbacks->version == EP_CR_VERSION && callbacks->slot_callback &&
           callbacks->owner_callback;
}

bool valid(const EP_CLIENT_REPLICATION_SIDECAR* s) {
    return s && s->magic == EP_CR_MAGIC && s->version == EP_CR_VERSION &&
           s->build == EP_CR_BUILD && s->initialized == 1 &&
           valid_callbacks(&s->callbacks);
}

EP_CR_STATUS validate_unlocked(const EP_CLIENT_REPLICATION_SIDECAR* s) {
    if (!valid(s) || s->active_count > EP_CR_CAPACITY ||
        s->confirmed_count > s->active_count ||
        s->callback_leases > EP_CR_CAPACITY ||
        (s->migration_in_progress != 0 && s->pending_transaction_id == 0)) {
        return EP_CR_INVALID_CONTEXT;
    }
    UINT32 active = 0;
    UINT32 confirmed = 0;
    UINT32 leases = 0;
    for (UINT32 i = 0; i < EP_CR_CAPACITY; ++i) {
        const EP_CR_SLOT& slot = s->slots[i];
        if (!valid_state(slot.state)) return EP_CR_INVARIANT_BROKEN;
        if (slot.state == EP_CR_FREE) {
            if (slot.peer_id != 0 || slot.resource_handle != 0 || s->lease_id[i] != 0)
                return EP_CR_INVARIANT_BROKEN;
            continue;
        }
        if (slot.generation == 0 || slot.generation != s->generation[i] ||
            slot.network_index != i ||
            (slot.array_membership_mask & EP_CR_ARRAY_CONFIRMED_32) == 0 ||
            (slot.array_membership_mask & ~EP_CR_ARRAY_ALL) != 0 ||
            !valid_identity(slot.peer_id, slot.resource_handle))
            return EP_CR_INVARIANT_BROKEN;
        ++active;
        if (slot.state == EP_CR_CONFIRMED) ++confirmed;
        if (s->lease_id[i] != 0) ++leases;
        for (UINT32 j = 0; j < i; ++j) {
            const EP_CR_SLOT& prior = s->slots[j];
            if (prior.state == EP_CR_FREE) continue;
            if (prior.peer_id == slot.peer_id ||
                prior.resource_handle == slot.resource_handle)
                return EP_CR_INVARIANT_BROKEN;
        }
    }
    for (UINT32 group = 0; group < 5; ++group) {
        if (s->array_count[group] > EP_CR_CAPACITY) return EP_CR_INVARIANT_BROKEN;
        UINT32 seen = 0;
        for (UINT32 ordinal = 0; ordinal < s->array_count[group]; ++ordinal) {
            UINT8 index = s->ordinal_to_index[group][ordinal];
            if (index >= EP_CR_CAPACITY || (seen & (1u << index)) != 0 ||
                s->slots[index].state == EP_CR_FREE ||
                (s->slots[index].array_membership_mask & (1u << group)) == 0)
                return EP_CR_INVARIANT_BROKEN;
            seen |= 1u << index;
        }
        for (UINT32 index = 0; index < EP_CR_CAPACITY; ++index) {
            bool member = s->slots[index].state != EP_CR_FREE &&
                (s->slots[index].array_membership_mask & (1u << group)) != 0;
            if (member != ((seen & (1u << index)) != 0)) return EP_CR_INVARIANT_BROKEN;
        }
        for (UINT32 ordinal = s->array_count[group]; ordinal < EP_CR_CAPACITY; ++ordinal)
            if (s->ordinal_to_index[group][ordinal] != EP_CR_CAPACITY)
                return EP_CR_INVARIANT_BROKEN;
    }
    for (UINT32 group = 0; group < 5; ++group) {
        if (s->array_count[group] > EP_CR_CAPACITY) return EP_CR_INVARIANT_BROKEN;
        UINT32 seen = 0;
        for (UINT32 ordinal = 0; ordinal < s->array_count[group]; ++ordinal) {
            UINT8 index = s->ordinal_to_index[group][ordinal];
            if (index >= EP_CR_CAPACITY || (seen & (1u << index)) != 0 ||
                s->slots[index].state == EP_CR_FREE ||
                (s->slots[index].array_membership_mask & (1u << group)) == 0)
                return EP_CR_INVARIANT_BROKEN;
            seen |= 1u << index;
        }
        for (UINT32 index = 0; index < EP_CR_CAPACITY; ++index) {
            bool member = s->slots[index].state != EP_CR_FREE &&
                (s->slots[index].array_membership_mask & (1u << group)) != 0;
            if (member != ((seen & (1u << index)) != 0)) return EP_CR_INVARIANT_BROKEN;
        }
        for (UINT32 ordinal = s->array_count[group]; ordinal < EP_CR_CAPACITY; ++ordinal)
            if (s->ordinal_to_index[group][ordinal] != EP_CR_CAPACITY)
                return EP_CR_INVARIANT_BROKEN;
    }
    if (active != s->active_count || confirmed != s->confirmed_count ||
        leases != s->callback_leases) return EP_CR_INVARIANT_BROKEN;
    return EP_CR_OK;
}

EP_CR_STATUS begin(EP_CLIENT_REPLICATION_SIDECAR* s) {
    if (!s) return EP_CR_INVALID_ARGUMENT;
    if (!TryAcquireSRWLockExclusive(&s->lock)) return EP_CR_QUIESCENCE_REQUIRED;
    const EP_CR_STATUS status = validate_unlocked(s);
    if (status != EP_CR_OK) {
        ReleaseSRWLockExclusive(&s->lock);
        return status;
    }
    return EP_CR_OK;
}

void release(EP_CLIENT_REPLICATION_SIDECAR* s) {
    ReleaseSRWLockExclusive(&s->lock);
}

EP_CR_STATUS clear_slot(EP_CLIENT_REPLICATION_SIDECAR* s, UINT8 index) {
    EP_CR_SLOT& slot = s->slots[index];
    if (slot.state == EP_CR_CONFIRMED) --s->confirmed_count;
    --s->active_count;
    slot.state = EP_CR_FREE;
    slot.peer_id = 0;
    slot.resource_handle = 0;
    s->lease_id[index] = 0;
    slot.array_membership_mask = 0;
    for (UINT32 group = 0; group < 5; ++group) {
        for (UINT32 ordinal = 0; ordinal < s->array_count[group]; ++ordinal) {
            if (s->ordinal_to_index[group][ordinal] != index) continue;
            for (UINT32 next = ordinal + 1; next < s->array_count[group]; ++next)
                s->ordinal_to_index[group][next - 1] = s->ordinal_to_index[group][next];
            s->ordinal_to_index[group][--s->array_count[group]] = EP_CR_CAPACITY;
            break;
        }
    }
    return EP_CR_OK;
}

EP_CR_STATUS callback_slot(EP_CLIENT_REPLICATION_SIDECAR* s, EP_CR_EVENT event,
                           const EP_CR_SLOT& slot) {
    try {
        return s->callbacks.slot_callback(s->callbacks.context, event, &slot,
            event == EP_CR_EVENT_RESET ? EP_CR_ARRAY_ALL : slot.array_membership_mask);
    } catch (...) { return EP_CR_CALLBACK_REJECTED; }
}

EP_CR_STATUS lookup_unlocked(EP_CLIENT_REPLICATION_SIDECAR* s,
                             const EP_CR_TOKEN& token, EP_CR_SLOT** out) {
    if (!valid_token(token)) return EP_CR_INDEX_REJECTED;
    EP_CR_SLOT& slot = s->slots[token.network_index];
    if (slot.generation != token.generation || slot.state == EP_CR_FREE)
        return EP_CR_STALE_GENERATION;
    if (out) *out = &slot;
    return EP_CR_OK;
}

}  // namespace

extern "C" EP_CR_STATUS __cdecl ep_cr_init(
    EP_CLIENT_REPLICATION_SIDECAR* s, UINT32 build,
    const EP_CR_CALLBACKS* callbacks, UINT64 owner_key, UINT32 owner_epoch) {
    if (!s || !valid_callbacks(callbacks) || owner_key == 0 || owner_epoch == 0)
        return EP_CR_INVALID_ARGUMENT;
    if (build != EP_CR_BUILD) return EP_CR_BUILD_MISMATCH;
    std::memset(s, 0, sizeof(*s));
    InitializeSRWLock(&s->lock);
    s->magic = EP_CR_MAGIC;
    s->version = EP_CR_VERSION;
    s->build = build;
    s->initialized = 1;
    s->owner_key = owner_key;
    s->owner_epoch = owner_epoch;
    s->next_lease_id = 1;
    s->callbacks = *callbacks;
    std::memset(s->ordinal_to_index, EP_CR_CAPACITY, sizeof(s->ordinal_to_index));
    std::memset(s->ordinal_to_index, EP_CR_CAPACITY, sizeof(s->ordinal_to_index));
    return EP_CR_OK;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_destroy(EP_CLIENT_REPLICATION_SIDECAR* s) {
    if (!s) return EP_CR_INVALID_ARGUMENT;
    if (!TryAcquireSRWLockExclusive(&s->lock)) return EP_CR_QUIESCENCE_REQUIRED;
    const auto status = validate_unlocked(s);
    if (status != EP_CR_OK) { release(s); return status; }
    if (s->active_count != 0 || s->callback_leases != 0 || s->migration_in_progress) {
        release(s); return EP_CR_QUIESCENCE_REQUIRED;
    }
    s->initialized = 0;
    s->magic = 0;
    s->version = 0;
    release(s);
    return EP_CR_OK;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_append(
    EP_CLIENT_REPLICATION_SIDECAR* s, UINT8 index, UINT64 peer, UINT64 resource,
    UINT32 membership, EP_CR_TOKEN* out) {
    if ((membership & EP_CR_ARRAY_CONFIRMED_32) == 0 || (membership & ~EP_CR_ARRAY_ALL) != 0)
        return EP_CR_INVALID_ARGUMENT;
    if (!s || !out || !valid_identity(peer, resource)) return EP_CR_INVALID_ARGUMENT;
    if (index >= EP_CR_CAPACITY) return EP_CR_INDEX_REJECTED;
    auto status = begin(s);
    if (status != EP_CR_OK) return status;
    if (s->callback_leases != 0) { release(s); return EP_CR_QUIESCENCE_REQUIRED; }
    std::memset(out, 0, sizeof(*out));
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    for (UINT32 i = 0; i < EP_CR_CAPACITY; ++i) {
        const auto& prior = s->slots[i];
        if (prior.state == EP_CR_FREE) continue;
        if (prior.peer_id == peer) { release(s); return EP_CR_DUPLICATE_PEER; }
        if (prior.resource_handle == resource) { release(s); return EP_CR_DUPLICATE_RESOURCE; }
    }
    auto& slot = s->slots[index];
    if (slot.state != EP_CR_FREE) { release(s); return EP_CR_INDEX_OCCUPIED; }
    if (s->generation[index] == 0xFFFFFFFFu) { release(s); return EP_CR_GENERATION_EXHAUSTED; }
    const UINT32 generation = ++s->generation[index];
    slot.state = EP_CR_PENDING;
    slot.generation = generation;
    slot.peer_id = peer;
    slot.resource_handle = resource;
    slot.network_index = index;
    slot.array_membership_mask = membership;
    for (UINT32 group = 0; group < 5; ++group)
        if ((membership & (1u << group)) != 0)
            s->ordinal_to_index[group][s->array_count[group]++] = index;
    ++s->active_count;
    // Publish the token before dispatch so a failed compensation can be
    // retried by the caller when the rollback callback itself fails.
    out->network_index = index;
    out->generation = generation;
    status = callback_slot(s, EP_CR_EVENT_APPEND, slot);
    if (status != EP_CR_OK) {
        const auto rollback_status = callback_slot(s, EP_CR_EVENT_ROLLBACK, slot);
        if (rollback_status == EP_CR_OK) clear_slot(s, index);
        else slot.state = EP_CR_ROLLBACK;
        release(s);
        return rollback_status == EP_CR_OK ? EP_CR_CALLBACK_REJECTED : EP_CR_ROLLBACK_REQUIRED;
    }
    release(s);
    return EP_CR_OK;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_confirm(
    EP_CLIENT_REPLICATION_SIDECAR* s, EP_CR_TOKEN token) {
    if (!s) return EP_CR_INVALID_ARGUMENT;
    auto status = begin(s);
    if (status != EP_CR_OK) return status;
    if (s->callback_leases != 0) { release(s); return EP_CR_QUIESCENCE_REQUIRED; }
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    EP_CR_SLOT* slot = nullptr;
    status = lookup_unlocked(s, token, &slot);
    if (status != EP_CR_OK) { release(s); return status; }
    if (slot->state == EP_CR_CONFIRMED) { release(s); return EP_CR_ALREADY_DONE; }
    if (slot->state != EP_CR_PENDING) { release(s); return EP_CR_ROLLBACK_REQUIRED; }
    status = callback_slot(s, EP_CR_EVENT_CONFIRM, *slot);
    if (status != EP_CR_OK) {
        const auto rollback_status = callback_slot(s, EP_CR_EVENT_ROLLBACK, *slot);
        if (rollback_status == EP_CR_OK) clear_slot(s, token.network_index);
        else slot->state = EP_CR_ROLLBACK;
        release(s);
        return rollback_status == EP_CR_OK ? EP_CR_CALLBACK_REJECTED : EP_CR_ROLLBACK_REQUIRED;
    }
    slot->state = EP_CR_CONFIRMED;
    ++s->confirmed_count;
    release(s);
    return EP_CR_OK;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_remove(
    EP_CLIENT_REPLICATION_SIDECAR* s, EP_CR_TOKEN token) {
    if (!s) return EP_CR_INVALID_ARGUMENT;
    auto status = begin(s);
    if (status != EP_CR_OK) return status;
    if (s->callback_leases != 0) { release(s); return EP_CR_QUIESCENCE_REQUIRED; }
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    EP_CR_SLOT* slot = nullptr;
    status = lookup_unlocked(s, token, &slot);
    if (status != EP_CR_OK) { release(s); return status; }
    if (s->lease_id[token.network_index] != 0) { release(s); return EP_CR_QUIESCENCE_REQUIRED; }
    if (slot->state == EP_CR_ROLLBACK) { release(s); return EP_CR_ROLLBACK_REQUIRED; }
    if (slot->state == EP_CR_ROLLBACK) { release(s); return EP_CR_ROLLBACK_REQUIRED; }
    status = callback_slot(s, EP_CR_EVENT_REMOVE, *slot);
    if (status == EP_CR_OK) clear_slot(s, token.network_index);
    release(s);
    return status == EP_CR_OK ? EP_CR_OK : EP_CR_CALLBACK_REJECTED;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_kick(
    EP_CLIENT_REPLICATION_SIDECAR* s, EP_CR_TOKEN token) {
    if (!s) return EP_CR_INVALID_ARGUMENT;
    auto status = begin(s);
    if (status != EP_CR_OK) return status;
    if (s->callback_leases != 0) { release(s); return EP_CR_QUIESCENCE_REQUIRED; }
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    EP_CR_SLOT* slot = nullptr;
    status = lookup_unlocked(s, token, &slot);
    if (status != EP_CR_OK) { release(s); return status; }
    if (s->lease_id[token.network_index] != 0) { release(s); return EP_CR_QUIESCENCE_REQUIRED; }
    if (slot->state == EP_CR_ROLLBACK) { release(s); return EP_CR_ROLLBACK_REQUIRED; }
    if (slot->state == EP_CR_ROLLBACK) { release(s); return EP_CR_ROLLBACK_REQUIRED; }
    status = callback_slot(s, EP_CR_EVENT_KICKED, *slot);
    if (status == EP_CR_OK) clear_slot(s, token.network_index);
    release(s);
    return status == EP_CR_OK ? EP_CR_OK : EP_CR_CALLBACK_REJECTED;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_retry_rollback(
    EP_CLIENT_REPLICATION_SIDECAR* s, EP_CR_TOKEN token) {
    if (!s) return EP_CR_INVALID_ARGUMENT;
    auto status = begin(s);
    if (status != EP_CR_OK) return status;
    if (s->callback_leases != 0) { release(s); return EP_CR_QUIESCENCE_REQUIRED; }
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    EP_CR_SLOT* slot = nullptr;
    status = lookup_unlocked(s, token, &slot);
    if (status != EP_CR_OK) { release(s); return status; }
    if (slot->state != EP_CR_ROLLBACK) { release(s); return EP_CR_ALREADY_DONE; }
    if (s->lease_id[token.network_index] != 0) { release(s); return EP_CR_QUIESCENCE_REQUIRED; }
    status = callback_slot(s, EP_CR_EVENT_ROLLBACK, *slot);
    if (status == EP_CR_OK) clear_slot(s, token.network_index);
    release(s);
    return status == EP_CR_OK ? EP_CR_OK : EP_CR_ROLLBACK_REQUIRED;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_reset(EP_CLIENT_REPLICATION_SIDECAR* s) {
    if (!s) return EP_CR_INVALID_ARGUMENT;
    auto status = begin(s);
    if (status != EP_CR_OK) return status;
    if (s->callback_leases != 0 || s->migration_in_progress) { release(s); return EP_CR_QUIESCENCE_REQUIRED; }
    EP_CR_SLOT marker{};
    status = callback_slot(s, EP_CR_EVENT_RESET, marker);
    if (status != EP_CR_OK) { release(s); return EP_CR_CALLBACK_REJECTED; }
    for (UINT32 i = 0; i < EP_CR_CAPACITY; ++i) {
        if (s->slots[i].state != EP_CR_FREE) clear_slot(s, static_cast<UINT8>(i));
    }
    release(s);
    return EP_CR_OK;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_callback_enter(
    EP_CLIENT_REPLICATION_SIDECAR* s, EP_CR_TOKEN token, UINT32* out_lease) {
    if (!s || !out_lease) return EP_CR_INVALID_ARGUMENT;
    auto status = begin(s);
    if (status != EP_CR_OK) return status;
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    EP_CR_SLOT* slot = nullptr;
    status = lookup_unlocked(s, token, &slot);
    if (status != EP_CR_OK) { release(s); return status; }
    if (s->migration_in_progress || s->lease_id[token.network_index] != 0) {
        release(s); return EP_CR_QUIESCENCE_REQUIRED;
    }
    if (slot->state != EP_CR_CONFIRMED) { release(s); return EP_CR_ROLLBACK_REQUIRED; }
    if (s->next_lease_id == 0xFFFFFFFFu) { release(s); return EP_CR_GENERATION_EXHAUSTED; }
    UINT32 id = s->next_lease_id++;
    s->lease_id[token.network_index] = id;
    ++s->callback_leases;
    *out_lease = id;
    release(s);
    return EP_CR_OK;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_callback_leave(
    EP_CLIENT_REPLICATION_SIDECAR* s, EP_CR_TOKEN token, UINT32 lease_id) {
    if (!s || lease_id == 0) return EP_CR_INVALID_ARGUMENT;
    auto status = begin(s);
    if (status != EP_CR_OK) return status;
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    if (s->migration_in_progress) { release(s); return EP_CR_MIGRATION_IN_PROGRESS; }
    EP_CR_SLOT* slot = nullptr;
    status = lookup_unlocked(s, token, &slot);
    if (status != EP_CR_OK) { release(s); return status; }
    if (s->lease_id[token.network_index] != lease_id) { release(s); return EP_CR_STALE_GENERATION; }
    s->lease_id[token.network_index] = 0;
    --s->callback_leases;
    release(s);
    return EP_CR_OK;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_migration_begin(
    EP_CLIENT_REPLICATION_SIDECAR* s, UINT64 owner_key, UINT32 owner_epoch,
    UINT32 transaction_id) {
    if (!s || owner_key == 0 || owner_epoch == 0 || transaction_id == 0)
        return EP_CR_INVALID_ARGUMENT;
    auto status = begin(s);
    if (status != EP_CR_OK) return status;
    if (s->migration_in_progress || s->callback_leases != 0) { release(s); return EP_CR_QUIESCENCE_REQUIRED; }
    if (owner_epoch <= s->owner_epoch) { release(s); return EP_CR_STALE_GENERATION; }
    for (const auto& slot : s->slots)
        if (slot.state == EP_CR_PENDING || slot.state == EP_CR_ROLLBACK) { release(s); return EP_CR_QUIESCENCE_REQUIRED; }
    status = s->callbacks.owner_callback(s->callbacks.context, EP_CR_EVENT_MIGRATION_BEGIN, owner_key, owner_epoch);
    if (status != EP_CR_OK) { release(s); return EP_CR_CALLBACK_REJECTED; }
    s->migration_in_progress = 1;
    s->pending_owner_key = owner_key;
    s->pending_owner_epoch = owner_epoch;
    s->pending_transaction_id = transaction_id;
    release(s);
    return EP_CR_OK;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_migration_commit(
    EP_CLIENT_REPLICATION_SIDECAR* s, UINT32 transaction_id) {
    if (!s || transaction_id == 0) return EP_CR_INVALID_ARGUMENT;
    auto status = begin(s);
    if (status != EP_CR_OK) return status;
    if (!s->migration_in_progress || s->pending_transaction_id != transaction_id) { release(s); return EP_CR_MIGRATION_NOT_PREPARED; }
    status = s->callbacks.owner_callback(s->callbacks.context, EP_CR_EVENT_MIGRATION_COMMIT, s->pending_owner_key, s->pending_owner_epoch);
    if (status != EP_CR_OK) { release(s); return EP_CR_CALLBACK_REJECTED; }
    s->owner_key = s->pending_owner_key;
    s->owner_epoch = s->pending_owner_epoch;
    s->migration_in_progress = 0;
    s->pending_owner_key = 0;
    s->pending_owner_epoch = 0;
    s->pending_transaction_id = 0;
    release(s);
    return EP_CR_OK;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_migration_abort(
    EP_CLIENT_REPLICATION_SIDECAR* s, UINT32 transaction_id) {
    if (!s || transaction_id == 0) return EP_CR_INVALID_ARGUMENT;
    auto status = begin(s);
    if (status != EP_CR_OK) return status;
    if (!s->migration_in_progress || s->pending_transaction_id != transaction_id) { release(s); return EP_CR_MIGRATION_NOT_PREPARED; }
    status = s->callbacks.owner_callback(s->callbacks.context, EP_CR_EVENT_MIGRATION_ABORT, s->pending_owner_key, s->pending_owner_epoch);
    if (status != EP_CR_OK) { release(s); return EP_CR_CALLBACK_REJECTED; }
    s->migration_in_progress = 0;
    s->pending_owner_key = 0;
    s->pending_owner_epoch = 0;
    s->pending_transaction_id = 0;
    release(s);
    return EP_CR_OK;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_get(
    EP_CLIENT_REPLICATION_SIDECAR* s, UINT8 index, EP_CR_SLOT* out) {
    if (!s || !out) return EP_CR_INVALID_ARGUMENT;
    if (index >= EP_CR_CAPACITY) return EP_CR_INDEX_REJECTED;
    auto status = begin(s);
    if (status != EP_CR_OK) return status;
    *out = s->slots[index];
    release(s);
    return out->state == EP_CR_FREE ? EP_CR_NOT_FOUND : EP_CR_OK;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_validate(EP_CLIENT_REPLICATION_SIDECAR* s) {
    if (!s) return EP_CR_INVALID_ARGUMENT;
    if (!TryAcquireSRWLockShared(&s->lock)) return EP_CR_QUIESCENCE_REQUIRED;
    auto status = validate_unlocked(s);
    ReleaseSRWLockShared(&s->lock);
    return status;
}

extern "C" EP_CR_STATUS __cdecl ep_cr_get_array(
    EP_CLIENT_REPLICATION_SIDECAR* s, UINT32 group, UINT8* out, UINT32* count) {
    if (!s || !out || !count || group >= 5) return EP_CR_INVALID_ARGUMENT;
    auto status = begin(s);
    if (status != EP_CR_OK) return status;
    std::memcpy(out, s->ordinal_to_index[group], EP_CR_CAPACITY);
    *count = s->array_count[group];
    release(s);
    return EP_CR_OK;
}
extern "C" UINT32 __cdecl ep_cr_production_enabled() { return 0; }
extern "C" UINT32 __cdecl ep_cr_capacity() { return EP_CR_CAPACITY; }
extern "C" UINT32 __cdecl ep_cr_array_group_mask() { return EP_CR_ARRAY_ALL; }
