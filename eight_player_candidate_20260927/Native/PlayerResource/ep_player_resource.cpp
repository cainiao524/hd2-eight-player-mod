#include "ep_player_resource.h"
#include <cstring>

namespace {
constexpr UINT32 kMaxGeneration = 0xffffffffu;
constexpr UINT32 kMaxOwnerEpoch = 0xffffffffu;

bool token_shape(const EP_RESOURCE_TOKEN& token) {
    return token.index < EP_RESOURCE_CAPACITY && token.generation != 0 && token.owner_epoch != 0;
}
bool token_equal(const EP_RESOURCE_TOKEN& a, const EP_RESOURCE_TOKEN& b) {
    return a.index == b.index && a.generation == b.generation && a.owner_epoch == b.owner_epoch;
}
EP_RESOURCE_STATUS validate_context(const EP_PLAYER_RESOURCE* r) {
    if (!r || r->magic != EP_RESOURCE_MAGIC || r->version != EP_RESOURCE_VERSION || !r->initialized) {
        return EP_RS_INVALID_CONTEXT;
    }
    return EP_RS_OK;
}
EP_RESOURCE_STATUS current_record(EP_PLAYER_RESOURCE* r, const EP_RESOURCE_TOKEN& token,
                                  EP_RESOURCE_RECORD** out) {
    if (!token_shape(token)) return EP_RS_INVALID_ARGUMENT;
    if (token.owner_epoch != r->owner_epoch) return EP_RS_OWNER_MISMATCH;
    EP_RESOURCE_RECORD* rec = &r->records[token.index];
    if (rec->state == EP_RS_FREE || rec->generation != token.generation ||
        rec->owner_epoch != token.owner_epoch) {
        if (r->history[token.index].valid && token_equal(r->history[token.index].token, token)) {
            return EP_RS_ALREADY_RELEASED;
        }
        return EP_RS_STALE_TOKEN;
    }
    *out = rec;
    return EP_RS_OK;
}
void reset_record(EP_RESOURCE_RECORD& rec) { std::memset(&rec, 0, sizeof(rec)); }
EP_RESOURCE_STATUS validate_unlocked(const EP_PLAYER_RESOURCE* r) {
    UINT32 inflight = 0;
    for (UINT32 i = 0; i < EP_RESOURCE_CAPACITY; ++i) {
        const auto& rec = r->records[i];
        if (rec.state == EP_RS_FREE) {
            if (rec.inflight || rec.applied_callbacks) return EP_RS_INVARIANT_BROKEN;
            continue;
        }
        if (!rec.generation || rec.owner_epoch != r->owner_epoch || rec.applied_callbacks > 3 || rec.inflight > 1) {
            return EP_RS_INVARIANT_BROKEN;
        }
        inflight += rec.inflight;
        if (rec.state == EP_RS_CONFIRMED && rec.applied_callbacks != 3) return EP_RS_INVARIANT_BROKEN;
    }
    if (inflight != r->inflight) return EP_RS_INVARIANT_BROKEN;
    if (r->quiesced && (r->inflight != 0)) return EP_RS_INVARIANT_BROKEN;
    UINT32 lease_count = 0;
    for (const auto& lease : r->leases) if (lease.lease_id) ++lease_count;
    if (lease_count != r->inflight) return EP_RS_INVARIANT_BROKEN;
    return EP_RS_OK;
}
EP_RESOURCE_STATUS finish_release_unlocked(EP_PLAYER_RESOURCE* r, EP_RESOURCE_RECORD* rec) {
    if (rec->inflight) return EP_RS_BUSY;
    EP_RESOURCE_TOKEN token{static_cast<UINT8>(rec - r->records), {}, rec->generation, rec->owner_epoch};
    r->history[token.index].valid = 1;
    r->history[token.index].token = token;
    reset_record(*rec);
    return EP_RS_OK;
}
}

extern "C" {

EP_RESOURCE_STATUS __cdecl ep_resource_init(EP_PLAYER_RESOURCE* r, UINT32 owner_key) {
    if (!r || owner_key == 0) return EP_RS_INVALID_ARGUMENT;
    // Initialization owns the caller-provided storage.  Never erase a live
    // resource table: doing so would invalidate active generation tokens and
    // silently lose the owner leases tracked by the bridge.  The caller must
    // destroy a live table before reusing its storage.
    if (r->magic == EP_RESOURCE_MAGIC) return EP_RS_BUSY;
    std::memset(r, 0, sizeof(*r));
    r->magic = EP_RESOURCE_MAGIC; r->version = EP_RESOURCE_VERSION; r->initialized = 1;
    r->owner_key = owner_key; r->owner_epoch = 1; r->next_lease_id = 1; InitializeSRWLock(&r->lock);
    return EP_RS_OK;
}

EP_RESOURCE_STATUS __cdecl ep_resource_destroy(EP_PLAYER_RESOURCE* r) {
    auto status = validate_context(r); if (status != EP_RS_OK) return status;
    AcquireSRWLockExclusive(&r->lock);
    status = validate_unlocked(r);
    if (status == EP_RS_OK) {
        for (const auto& rec : r->records) if (rec.state != EP_RS_FREE) { status = EP_RS_BUSY; break; }
        if (status == EP_RS_OK) { r->initialized = 0; r->magic = 0; }
    }
    ReleaseSRWLockExclusive(&r->lock); return status;
}

EP_RESOURCE_STATUS __cdecl ep_resource_begin(EP_PLAYER_RESOURCE* r, UINT8 index, UINT64 peer,
                                             UINT64 handle, UINT64 hash, UINT32 ordinal,
                                             UINT16 component, EP_RESOURCE_TOKEN* out) {
    auto status = validate_context(r);
    if (status != EP_RS_OK || !out || index >= EP_RESOURCE_CAPACITY || !peer || !handle || !hash) return EP_RS_INVALID_ARGUMENT;
    AcquireSRWLockExclusive(&r->lock);
    if (r->quiesced) status = EP_RS_BUSY;
    else if (r->records[index].state != EP_RS_FREE) status = EP_RS_DUPLICATE;
    else if (r->generations[index] == kMaxGeneration) status = EP_RS_GENERATION_EXHAUSTED;
    else {
        ++r->generations[index]; auto& rec = r->records[index]; reset_record(rec);
        rec.state = EP_RS_PENDING; rec.generation = r->generations[index]; rec.owner_epoch = r->owner_epoch;
        rec.peer_id = peer; rec.resource_handle = handle; rec.resource_hash = hash;
        rec.record_ordinal = ordinal; rec.component_ordinal = component;
        out->index = index; std::memset(out->reserved, 0, sizeof(out->reserved));
        out->generation = rec.generation; out->owner_epoch = rec.owner_epoch;
        status = validate_unlocked(r);
    }
    ReleaseSRWLockExclusive(&r->lock); return status;
}

EP_RESOURCE_STATUS __cdecl ep_resource_begin_callback(EP_PLAYER_RESOURCE* r, EP_RESOURCE_TOKEN token,
                                                      EP_RESOURCE_LEASE* out) {
    auto status = validate_context(r); if (status != EP_RS_OK || !out) return EP_RS_INVALID_ARGUMENT;
    AcquireSRWLockExclusive(&r->lock);
    EP_RESOURCE_RECORD* rec = nullptr; status = current_record(r, token, &rec);
    if (status == EP_RS_OK) {
        if (rec->state != EP_RS_PENDING && rec->state != EP_RS_ACTIVE || rec->inflight || rec->applied_callbacks >= 3) status = EP_RS_INVALID_STATE;
        else {
            UINT32 lease_id = r->next_lease_id++;
            if (!lease_id) status = EP_RS_GENERATION_EXHAUSTED;
            else { *out = {lease_id, token}; r->leases[token.index] = *out; rec->inflight = 1; ++r->inflight; rec->state = EP_RS_ACTIVE; status = validate_unlocked(r); }
        }
    }
    ReleaseSRWLockExclusive(&r->lock); return status;
}

EP_RESOURCE_STATUS __cdecl ep_resource_complete_callback(EP_PLAYER_RESOURCE* r, EP_RESOURCE_LEASE lease,
                                                         EP_RESOURCE_STAGE stage, BOOL succeeded) {
    auto status = validate_context(r); if (status != EP_RS_OK || stage > EP_RS_STAGE_THIRD || !lease.lease_id) return EP_RS_INVALID_ARGUMENT;
    AcquireSRWLockExclusive(&r->lock);
    EP_RESOURCE_RECORD* rec = nullptr; status = current_record(r, lease.token, &rec);
    if (status == EP_RS_OK) {
        if (r->leases[lease.token.index].lease_id != lease.lease_id || !token_equal(r->leases[lease.token.index].token, lease.token)) status = EP_RS_STALE_TOKEN;
        else {
            r->leases[lease.token.index] = {}; rec->inflight = 0; --r->inflight;
            if (stage != static_cast<EP_RESOURCE_STAGE>(rec->applied_callbacks)) {
                // A callback-order violation is a transaction failure.  The
                // lease has already been consumed, so unwind the record just
                // like any other atomic callback rejection.
                status = finish_release_unlocked(r, rec);
                if (status == EP_RS_OK) status = EP_RS_CALLBACK_ORDER;
            }
            else if (!succeeded) { status = finish_release_unlocked(r, rec); }
            else { ++rec->applied_callbacks; status = validate_unlocked(r); }
        }
    }
    ReleaseSRWLockExclusive(&r->lock); return status;
}

EP_RESOURCE_STATUS __cdecl ep_resource_publish(EP_PLAYER_RESOURCE* r, EP_RESOURCE_TOKEN token) {
    auto status = validate_context(r); if (status != EP_RS_OK) return status;
    AcquireSRWLockExclusive(&r->lock); EP_RESOURCE_RECORD* rec = nullptr; status = current_record(r, token, &rec);
    if (status == EP_RS_OK) {
        if (r->inflight || rec->inflight || rec->applied_callbacks != 3 || rec->state != EP_RS_ACTIVE) status = EP_RS_INVALID_STATE;
        else { rec->state = EP_RS_CONFIRMED; status = validate_unlocked(r); }
    }
    ReleaseSRWLockExclusive(&r->lock); return status;
}

EP_RESOURCE_STATUS __cdecl ep_resource_release(EP_PLAYER_RESOURCE* r, EP_RESOURCE_TOKEN token) {
    auto status = validate_context(r); if (status != EP_RS_OK) return status;
    AcquireSRWLockExclusive(&r->lock); EP_RESOURCE_RECORD* rec = nullptr; status = current_record(r, token, &rec);
    if (status == EP_RS_ALREADY_RELEASED) { ReleaseSRWLockExclusive(&r->lock); return EP_RS_ALREADY_RELEASED; }
    if (status == EP_RS_OK) status = finish_release_unlocked(r, rec);
    if (status == EP_RS_OK) status = validate_unlocked(r);
    ReleaseSRWLockExclusive(&r->lock); return status;
}

EP_RESOURCE_STATUS __cdecl ep_resource_quiesce(EP_PLAYER_RESOURCE* r) {
    auto status = validate_context(r); if (status != EP_RS_OK) return status;
    AcquireSRWLockExclusive(&r->lock); status = validate_unlocked(r);
    if (status == EP_RS_OK) {
        for (const auto& rec : r->records) if (rec.state != EP_RS_FREE) { status = EP_RS_BUSY; break; }
        if (status == EP_RS_OK) r->quiesced = 1;
    }
    ReleaseSRWLockExclusive(&r->lock); return status;
}

EP_RESOURCE_STATUS __cdecl ep_resource_migrate_owner(EP_PLAYER_RESOURCE* r, UINT32 new_owner) {
    auto status = validate_context(r); if (status != EP_RS_OK || !new_owner || new_owner == r->owner_key) return EP_RS_INVALID_ARGUMENT;
    AcquireSRWLockExclusive(&r->lock); status = validate_unlocked(r);
    if (status == EP_RS_OK && !r->quiesced) status = EP_RS_BUSY;
    if (status == EP_RS_OK && r->owner_epoch == kMaxOwnerEpoch) status = EP_RS_GENERATION_EXHAUSTED;
    if (status == EP_RS_OK) { r->owner_key = new_owner; ++r->owner_epoch; r->quiesced = 0; }
    ReleaseSRWLockExclusive(&r->lock); return status;
}

EP_RESOURCE_STATUS __cdecl ep_resource_get(EP_PLAYER_RESOURCE* r, UINT8 index, EP_RESOURCE_RECORD* out) {
    auto status = validate_context(r); if (status != EP_RS_OK || !out || index >= EP_RESOURCE_CAPACITY) return EP_RS_INVALID_ARGUMENT;
    AcquireSRWLockShared(&r->lock); *out = r->records[index]; ReleaseSRWLockShared(&r->lock); return EP_RS_OK;
}

EP_RESOURCE_STATUS __cdecl ep_resource_validate(EP_PLAYER_RESOURCE* r) {
    auto status = validate_context(r); if (status != EP_RS_OK) return status;
    AcquireSRWLockShared(&r->lock); status = validate_unlocked(r); ReleaseSRWLockShared(&r->lock); return status;
}

UINT32 __cdecl ep_resource_capacity() { return EP_RESOURCE_CAPACITY; }

}
