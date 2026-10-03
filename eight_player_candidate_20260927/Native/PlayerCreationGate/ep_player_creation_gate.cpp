#include "ep_player_creation_gate.h"

#include <cstring>
#include <limits>

namespace {
constexpr UINT32 kMaxGeneration = 0xffffffffu;
constexpr BYTE kGateImmediateOffset = 8u;
constexpr BYTE kGateExpectedImmediate = 4u;
constexpr BYTE kGatePatchedImmediate = 8u;
constexpr UINT8 kComponentsDone = 1u;
constexpr UINT8 kRosterDone = 2u;

bool valid_context(const EP_PLAYER_CREATION_ADAPTER* a) {
    return a != nullptr && a->magic == EP_PC_MAGIC &&
           a->version == EP_PC_VERSION && a->initialized &&
           a->build == EP_PC_BUILD;
}

bool valid_index(UINT8 i) { return i < EP_PC_CAPACITY; }

bool complete_callbacks(const EP_PC_CALLBACKS* c) {
    return c && c->owner && c->retain_owner && c->release_owner &&
           c->resolve_resource && c->dispatch_components && c->insert_roster &&
           c->cleanup_roster && c->cleanup_components && c->rollback;
}

bool complete_backend(const EP_PC_PATCH_BACKEND* b) {
    return b && b->owner && b->quiesce && b->resume && b->write &&
           b->downstream_ready;
}

bool range_ok(SIZE_T image_size, UINT32 rva, SIZE_T size) {
    return size != 0 && static_cast<SIZE_T>(rva) <= image_size &&
           size <= image_size - static_cast<SIZE_T>(rva);
}

bool site_matches(const BYTE* image, SIZE_T image_size, const EP_PC_SITE& site) {
    if (!image || !site.expected || !range_ok(image_size, site.rva, site.size)) return false;
    return std::memcmp(image + site.rva, site.expected, site.size) == 0;
}

bool find_downstream(const EP_PC_SITE* sites, UINT32 count, UINT32 rva) {
    if (!sites) return false;
    for (UINT32 i = 0; i < count; ++i) {
        if (sites[i].rva == rva && sites[i].size != 0 && sites[i].expected) return true;
    }
    return false;
}

EP_PC_STATUS check_adapter(const EP_PLAYER_CREATION_ADAPTER* a) {
    return valid_context(a) ? EP_PC_OK : EP_PC_INVALID_CONTEXT;
}

void clear_slot(EP_PC_SLOT& slot) { std::memset(&slot, 0, sizeof(slot)); }

bool same_identity(const EP_PC_SLOT& slot, UINT64 peer, UINT64 handle) {
    return slot.state != EP_PC_FREE &&
           (slot.resource.peer_id == peer || slot.resource.resource_handle == handle);
}

EP_PC_STATUS validate_locked(const EP_PLAYER_CREATION_ADAPTER* a) {
    UINT32 inflight = 0;
    for (UINT32 i = 0; i < EP_PC_CAPACITY; ++i) {
        const EP_PC_SLOT& slot = a->slots[i];
        if (slot.state == EP_PC_FREE) {
            if (slot.completed_mask || slot.owner_held) return EP_PC_INVARIANT_BROKEN;
            continue;
        }
        if (slot.generation == 0 || slot.owner_epoch != a->owner_epoch ||
            slot.resource.network_index != i || slot.completed_mask > 3 ||
            slot.owner_held != 1) return EP_PC_INVARIANT_BROKEN;
        ++inflight;
        if (slot.state == EP_PC_ACTIVE && slot.completed_mask != 3) return EP_PC_INVARIANT_BROKEN;
        if (slot.state == EP_PC_PENDING && slot.completed_mask == 3) return EP_PC_INVARIANT_BROKEN;
    }
    return inflight == a->inflight ? EP_PC_OK : EP_PC_INVARIANT_BROKEN;
}

EP_PC_STATUS token_slot(EP_PLAYER_CREATION_ADAPTER* a, EP_PC_TOKEN token,
                        EP_PC_SLOT** out) {
    if (!out || !valid_index(token.index) || token.generation == 0 || token.owner_epoch == 0)
        return EP_PC_INVALID_ARGUMENT;
    if (token.owner_epoch != a->owner_epoch) return EP_PC_STALE_TOKEN;
    EP_PC_SLOT* slot = &a->slots[token.index];
    if (slot->state == EP_PC_FREE || slot->generation != token.generation ||
        slot->owner_epoch != token.owner_epoch) return EP_PC_STALE_TOKEN;
    *out = slot;
    return EP_PC_OK;
}

EP_PC_STATUS finish_failed_admit(EP_PLAYER_CREATION_ADAPTER* a, UINT8 index,
                                 const EP_PC_TOKEN& token, UINT8 completed_mask,
                                 EP_PC_STATUS original, bool owner_held) {
    EP_PC_RESOURCE resource{};
    EP_PC_STATUS rollback_status = EP_PC_OK;
    {
        AcquireSRWLockShared(&a->lock);
        const EP_PC_SLOT& slot = a->slots[index];
        resource = slot.resource;
        ReleaseSRWLockShared(&a->lock);
    }
    if (completed_mask) rollback_status = a->callbacks.rollback(
        a->callbacks.owner, &resource, completed_mask);
    AcquireSRWLockExclusive(&a->lock);
    EP_PC_SLOT& slot = a->slots[index];
    if (slot.generation != token.generation || slot.owner_epoch != token.owner_epoch) {
        ReleaseSRWLockExclusive(&a->lock);
        return EP_PC_INVARIANT_BROKEN;
    }
    if (rollback_status == EP_PC_OK) {
        clear_slot(slot);
        if (a->inflight) --a->inflight;
        ReleaseSRWLockExclusive(&a->lock);
        if (owner_held) a->callbacks.release_owner(a->callbacks.owner);
        return original;
    }
    slot.state = EP_PC_REMOVING;
    slot.completed_mask = completed_mask;
    ReleaseSRWLockExclusive(&a->lock);
    return EP_PC_ROLLBACK_FAILED;
}
}

extern "C" {

EP_PC_STATUS __cdecl ep_pc_init(EP_PLAYER_CREATION_ADAPTER* a, UINT32 build,
                                const EP_PC_CALLBACKS* callbacks) {
    if (!a || build != EP_PC_BUILD || !complete_callbacks(callbacks)) {
        return build != EP_PC_BUILD ? EP_PC_BUILD_MISMATCH : EP_PC_CALLBACK_MISSING;
    }
    std::memset(a, 0, sizeof(*a));
    a->magic = EP_PC_MAGIC;
    a->version = EP_PC_VERSION;
    a->build = build;
    a->initialized = 1;
    a->owner_epoch = 1;
    a->callbacks = *callbacks;
    InitializeSRWLock(&a->lock);
    return EP_PC_OK;
}

EP_PC_STATUS __cdecl ep_pc_destroy(EP_PLAYER_CREATION_ADAPTER* a) {
    auto status = check_adapter(a);
    if (status != EP_PC_OK) return status;
    AcquireSRWLockExclusive(&a->lock);
    status = validate_locked(a);
    for (UINT32 i = 0; status == EP_PC_OK && i < EP_PC_CAPACITY; ++i) {
        if (a->slots[i].state != EP_PC_FREE) status = EP_PC_BUSY;
    }
    if (status == EP_PC_OK && a->gate_patched) status = EP_PC_BUSY;
    if (status == EP_PC_OK) {
        a->initialized = 0;
        a->magic = 0;
    }
    ReleaseSRWLockExclusive(&a->lock);
    return status;
}

EP_PC_STATUS __cdecl ep_pc_preflight(
    UINT32 build, const BYTE* image_base, SIZE_T image_size,
    const EP_PC_SITE* gate_site, const EP_PC_SITE* downstream_sites,
    UINT32 downstream_count, const EP_PC_CALLBACKS* callbacks,
    const EP_PC_PATCH_BACKEND* backend, EP_PC_PREFLIGHT* out) {
    if (!out) return EP_PC_INVALID_ARGUMENT;
    std::memset(out, 0, sizeof(*out));
    out->build = build;
    out->gate_rva = EP_PC_GATE_RVA;
    out->resource_rva = EP_PC_RESOURCE_RVA;
    out->roster_rva = EP_PC_ROSTER_RVA;
    out->build_ok = build == EP_PC_BUILD;
    out->image_ok = image_base != nullptr && image_size != 0;
    out->gate_ok = gate_site && gate_site->rva == EP_PC_GATE_RVA &&
                   gate_site->size == EP_PC_GATE_BYTES &&
                   site_matches(image_base, image_size, *gate_site) &&
                   gate_site->expected[kGateImmediateOffset] == kGateExpectedImmediate;
    out->downstream_sites_ok = downstream_count == 2 &&
        find_downstream(downstream_sites, downstream_count, EP_PC_RESOURCE_RVA) &&
        find_downstream(downstream_sites, downstream_count, EP_PC_ROSTER_RVA);
    if (out->downstream_sites_ok) {
        for (UINT32 i = 0; i < downstream_count; ++i) {
            if (!site_matches(image_base, image_size, downstream_sites[i])) {
                out->downstream_sites_ok = FALSE;
                break;
            }
        }
    }
    out->callbacks_ok = complete_callbacks(callbacks);
    out->backend_ok = complete_backend(backend);
    out->ready = out->build_ok && out->image_ok && out->gate_ok &&
                 out->downstream_sites_ok && out->callbacks_ok && out->backend_ok;
    // downstream_ready is a runtime provider assertion and is intentionally not
    // called by preflight; calling it may touch game state.
    out->downstream_ready = FALSE;
    return out->ready ? EP_PC_OK : EP_PC_SITE_MISMATCH;
}

EP_PC_STATUS __cdecl ep_pc_prepare_patch(
    EP_PLAYER_CREATION_ADAPTER* a, UINT32 build,
    const BYTE* image_base, SIZE_T image_size,
    const EP_PC_SITE* gate_site, const EP_PC_SITE* downstream_sites,
    UINT32 downstream_count, const EP_PC_PATCH_BACKEND* backend,
    EP_PC_PREFLIGHT* out) {
    auto status = check_adapter(a);
    if (status != EP_PC_OK) return status;
    status = ep_pc_preflight(build, image_base, image_size, gate_site,
                             downstream_sites, downstream_count, &a->callbacks,
                             backend, out);
    if (status != EP_PC_OK) return status;
    if (backend->owner != a->callbacks.owner) return EP_PC_INVALID_ARGUMENT;
    AcquireSRWLockExclusive(&a->lock);
    if (a->gate_patched) {
        ReleaseSRWLockExclusive(&a->lock);
        return EP_PC_PATCHED;
    }
    a->backend = *backend;
    a->patch_address = reinterpret_cast<uintptr_t>(image_base) + gate_site->rva;
    a->patch_size = static_cast<UINT32>(gate_site->size);
    std::memcpy(a->original_gate, gate_site->expected, EP_PC_GATE_BYTES);
    std::memcpy(a->patched_gate, gate_site->expected, EP_PC_GATE_BYTES);
    a->patched_gate[kGateImmediateOffset] = kGatePatchedImmediate;
    ReleaseSRWLockExclusive(&a->lock);
    return EP_PC_OK;
}

EP_PC_STATUS __cdecl ep_pc_install_gate_patch(EP_PLAYER_CREATION_ADAPTER* a) {
    auto status = check_adapter(a);
    if (status != EP_PC_OK) return status;
    AcquireSRWLockShared(&a->lock);
    if (!a->patch_address || a->patch_size != EP_PC_GATE_BYTES) {
        ReleaseSRWLockShared(&a->lock);
        return EP_PC_NOT_PATCHED;
    }
    if (a->gate_patched) {
        ReleaseSRWLockShared(&a->lock);
        return EP_PC_PATCHED;
    }
    EP_PC_PATCH_BACKEND backend = a->backend;
    BYTE patched[EP_PC_GATE_BYTES]{};
    std::memcpy(patched, a->patched_gate, sizeof(patched));
    ReleaseSRWLockShared(&a->lock);
    if (backend.downstream_ready(backend.owner) != EP_PC_OK) return EP_PC_DOWNSTREAM_UNREADY;
    status = backend.quiesce(backend.owner);
    if (status != EP_PC_OK) return EP_PC_QUIESCE_FAILED;
    status = backend.write(backend.owner, a->patch_address, patched, sizeof(patched));
    backend.resume(backend.owner);
    if (status != EP_PC_OK) return EP_PC_WRITE_FAILED;
    AcquireSRWLockExclusive(&a->lock);
    a->gate_patched = 1;
    ReleaseSRWLockExclusive(&a->lock);
    return EP_PC_OK;
}

EP_PC_STATUS __cdecl ep_pc_remove_gate_patch(EP_PLAYER_CREATION_ADAPTER* a) {
    auto status = check_adapter(a);
    if (status != EP_PC_OK) return status;
    AcquireSRWLockShared(&a->lock);
    if (!a->gate_patched) {
        ReleaseSRWLockShared(&a->lock);
        return EP_PC_NOT_PATCHED;
    }
    EP_PC_PATCH_BACKEND backend = a->backend;
    BYTE original[EP_PC_GATE_BYTES]{};
    std::memcpy(original, a->original_gate, sizeof(original));
    ReleaseSRWLockShared(&a->lock);
    status = backend.quiesce(backend.owner);
    if (status != EP_PC_OK) return EP_PC_QUIESCE_FAILED;
    status = backend.write(backend.owner, a->patch_address, original, sizeof(original));
    backend.resume(backend.owner);
    if (status != EP_PC_OK) return EP_PC_WRITE_FAILED;
    AcquireSRWLockExclusive(&a->lock);
    a->gate_patched = 0;
    ReleaseSRWLockExclusive(&a->lock);
    return EP_PC_OK;
}

EP_PC_STATUS __cdecl ep_pc_admit(
    EP_PLAYER_CREATION_ADAPTER* a, UINT8 index, UINT64 peer,
    UINT64 handle, UINT64 hash, EP_PC_TOKEN* out_token) {
    auto status = check_adapter(a);
    if (status != EP_PC_OK) return status;
    if (!valid_index(index) || !peer || !handle || !hash || !out_token) return EP_PC_INDEX_REJECTED;
    EP_PC_TOKEN token{};
    AcquireSRWLockExclusive(&a->lock);
    for (UINT32 i = 0; status == EP_PC_OK && i < EP_PC_CAPACITY; ++i) {
        if (same_identity(a->slots[i], peer, handle)) status = EP_PC_DUPLICATE;
    }
    if (status == EP_PC_OK && a->inflight >= EP_PC_CAPACITY) status = EP_PC_FULL;
    EP_PC_SLOT* slot = status == EP_PC_OK ? &a->slots[index] : nullptr;
    if (status == EP_PC_OK && slot->state != EP_PC_FREE) status = EP_PC_DUPLICATE;
    if (status == EP_PC_OK && a->generations[index] == 0xffffffffu) status = EP_PC_BUSY;
    if (status == EP_PC_OK) {
        ++a->generations[index];
        clear_slot(*slot);
        slot->state = EP_PC_PENDING;
        slot->generation = a->generations[index];
        slot->owner_epoch = a->owner_epoch;
        slot->owner_held = 1;
        slot->resource.network_index = index;
        slot->resource.generation = slot->generation;
        slot->resource.peer_id = peer;
        slot->resource.resource_handle = handle;
        slot->resource.resource_hash = hash;
        ++a->inflight;
        token.index = index;
        token.generation = slot->generation;
        token.owner_epoch = slot->owner_epoch;
        *out_token = token;
        status = validate_locked(a);
    }
    ReleaseSRWLockExclusive(&a->lock);
    if (status != EP_PC_OK) return status;

    status = a->callbacks.retain_owner(a->callbacks.owner);
    if (status != EP_PC_OK) {
        return finish_failed_admit(a, index, token, 0, EP_PC_CALLBACK_REJECTED, false);
    }
    EP_PC_RESOURCE resource{};
    status = a->callbacks.resolve_resource(a->callbacks.owner, peer, handle, hash, index,
                                           token.generation, &resource);
    if (status == EP_PC_OK && (resource.network_index != index || resource.generation != token.generation ||
                               resource.peer_id != peer || resource.resource_handle != handle ||
                               resource.resource_hash != hash)) {
        status = EP_PC_CALLBACK_REJECTED;
    }
    if (status != EP_PC_OK) {
        return finish_failed_admit(a, index, token, 0, EP_PC_CALLBACK_REJECTED, true);
    }
    AcquireSRWLockExclusive(&a->lock);
    a->slots[index].resource = resource;
    a->slots[index].resource.network_index = index;
    a->slots[index].resource.generation = token.generation;
    ReleaseSRWLockExclusive(&a->lock);

    status = a->callbacks.dispatch_components(a->callbacks.owner, &resource);
    UINT8 completed = 0;
    if (status == EP_PC_OK) completed |= kComponentsDone;
    if (status == EP_PC_OK) status = a->callbacks.insert_roster(a->callbacks.owner, &resource);
    if (status == EP_PC_OK) completed |= kRosterDone;
    if (status != EP_PC_OK) {
        return finish_failed_admit(a, index, token, completed, EP_PC_CALLBACK_REJECTED, true);
    }
    AcquireSRWLockExclusive(&a->lock);
    EP_PC_SLOT& committed = a->slots[index];
    if (committed.generation != token.generation || committed.owner_epoch != token.owner_epoch ||
        committed.state != EP_PC_PENDING) {
        ReleaseSRWLockExclusive(&a->lock);
        a->callbacks.rollback(a->callbacks.owner, &resource, completed);
        return EP_PC_INVARIANT_BROKEN;
    }
    committed.completed_mask = completed;
    committed.state = EP_PC_ACTIVE;
    status = validate_locked(a);
    ReleaseSRWLockExclusive(&a->lock);
    if (status != EP_PC_OK) return status;
    return EP_PC_OK;
}

EP_PC_STATUS __cdecl ep_pc_depart(EP_PLAYER_CREATION_ADAPTER* a, EP_PC_TOKEN token) {
    auto status = check_adapter(a);
    if (status != EP_PC_OK) return status;
    EP_PC_RESOURCE resource{};
    UINT8 mask = 0;
    AcquireSRWLockExclusive(&a->lock);
    EP_PC_SLOT* slot = nullptr;
    status = token_slot(a, token, &slot);
    if (status == EP_PC_OK) {
        if (slot->state == EP_PC_PENDING) status = EP_PC_BUSY;
        else if (slot->state != EP_PC_ACTIVE && slot->state != EP_PC_REMOVING) status = EP_PC_INVALID_CONTEXT;
        else {
            resource = slot->resource;
            mask = slot->completed_mask;
            slot->state = EP_PC_REMOVING;
        }
    }
    ReleaseSRWLockExclusive(&a->lock);
    if (status != EP_PC_OK) return status;

    EP_PC_STATUS first_failure = EP_PC_OK;
    if ((mask & kRosterDone) != 0) {
        status = a->callbacks.cleanup_roster(a->callbacks.owner, &resource);
        if (status == EP_PC_OK) mask &= static_cast<UINT8>(~kRosterDone);
        else first_failure = status;
    }
    if (first_failure == EP_PC_OK && (mask & kComponentsDone) != 0) {
        status = a->callbacks.cleanup_components(a->callbacks.owner, &resource);
        if (status == EP_PC_OK) mask &= static_cast<UINT8>(~kComponentsDone);
        else first_failure = status;
    }
    AcquireSRWLockExclusive(&a->lock);
    slot = &a->slots[token.index];
    if (slot->generation != token.generation || slot->owner_epoch != token.owner_epoch) {
        ReleaseSRWLockExclusive(&a->lock);
        return EP_PC_INVARIANT_BROKEN;
    }
    slot->completed_mask = mask;
    if (first_failure != EP_PC_OK) {
        ReleaseSRWLockExclusive(&a->lock);
        return EP_PC_CALLBACK_REJECTED;
    }
    const bool held = slot->owner_held != 0;
    clear_slot(*slot);
    if (a->inflight) --a->inflight;
    status = validate_locked(a);
    ReleaseSRWLockExclusive(&a->lock);
    if (held) a->callbacks.release_owner(a->callbacks.owner);
    return status;
}

EP_PC_STATUS __cdecl ep_pc_get(EP_PLAYER_CREATION_ADAPTER* a, UINT8 index, EP_PC_SLOT* out) {
    auto status = check_adapter(a);
    if (status != EP_PC_OK) return status;
    if (!out || !valid_index(index)) return EP_PC_INVALID_ARGUMENT;
    AcquireSRWLockShared(&a->lock);
    *out = a->slots[index];
    ReleaseSRWLockShared(&a->lock);
    return EP_PC_OK;
}

EP_PC_STATUS __cdecl ep_pc_validate(EP_PLAYER_CREATION_ADAPTER* a) {
    auto status = check_adapter(a);
    if (status != EP_PC_OK) return status;
    AcquireSRWLockShared(&a->lock);
    status = validate_locked(a);
    ReleaseSRWLockShared(&a->lock);
    return status;
}

UINT32 __cdecl ep_pc_capacity() { return EP_PC_CAPACITY; }

}
