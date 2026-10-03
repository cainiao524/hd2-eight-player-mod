#pragma once

#include "ep_session_vtable_snapshot.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>

// Static, no-call interpretation boundary for the record bytes exposed by the
// captured session methods.  This intentionally names only relationships that
// the saved disassembly proves.  It does not call a vtable or assign a PeerId,
// player slot, network index, or owner meaning to any field.
namespace ep_session_record {

constexpr uintptr_t kSessionSelfKeyOffset = 0x20;
constexpr uintptr_t kRecordIdentityTokenOffset = 0x00;
constexpr uintptr_t kRecordObservedByteOffset = 0x29;
constexpr size_t kRecordSize = ep_session_vtable::kOpaqueRecordSize;

struct DecodedRecord {
    uintptr_t address{};
    uintptr_t identity_token{};
    uint8_t observed_byte_29{};
};

struct Result {
    uint32_t count{};
    uintptr_t owner_opaque{};
    uintptr_t session_self_key{};
    uint32_t self_match_count{};
    uint32_t self_ordinal{std::numeric_limits<uint32_t>::max()};
    std::array<DecodedRecord, ep_session_vtable::kMaxRecords> records{};
    const char* status{"unread"};
};

template<class Reader>
bool verify(const ep_session_vtable::Snapshot& snapshot, Reader read,
            Result& out) {
    out = Result{};
    out.count = snapshot.count;
    out.owner_opaque = snapshot.owner;
    out.status = "invalid_snapshot";
    if (snapshot.status !=
        std::string("opaque_session_records_not_player_proof")) {
        out.status = "snapshot_not_proven_stable";
        return false;
    }
    if (snapshot.count > ep_session_vtable::kMaxRecords || !snapshot.session) {
        out.status = "record_count_over_capacity";
        return false;
    }

    if (!ep_session_vtable::read_offset(read, snapshot.session,
                                        kSessionSelfKeyOffset,
                                        out.session_self_key)) {
        out.status = "unread_session_self_key";
        return false;
    }
    for (uint32_t i = 0; i < snapshot.count; ++i) {
        const uintptr_t record_address = snapshot.entries[i].address;
        uintptr_t token{};
        uint8_t byte29{};
        if (!record_address ||
            !ep_session_vtable::read_offset(read, record_address,
                                            kRecordIdentityTokenOffset,
                                            token) ||
            !ep_session_vtable::read_offset(read, record_address,
                                            kRecordObservedByteOffset,
                                            byte29)) {
            out.status = "unread_record_semantic_boundary";
            return false;
        }
        out.records[i] = {record_address, token, byte29};
        for (uint32_t prior = 0; prior < i; ++prior) {
            if (out.records[prior].identity_token == token) {
                out.status = "duplicate_record_identity_token";
                return false;
            }
        }
        if (token == out.session_self_key) {
            ++out.self_match_count;
            out.self_ordinal = i;
        }
    }
    // The captured membership predicate can identify at most one self record.
    // A missing match is also refused: it cannot be safely mapped to a local
    // player slot without calling the unknown runtime method.
    if (out.self_match_count != 1) {
        out.status = "self_record_unresolved";
        return false;
    }
    out.status = "opaque_record_relationships_verified";
    return true;
}

} // namespace ep_session_record
