#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>

// Build 25480438 only. This is the native equivalent of
// capture_live_session_snapshot_20261003.py. It reads the known game.dll
// globals and bounded context/roster fields. It never calls an engine
// function, follows an unknown pointer, or writes to the process.
namespace ep_session {

constexpr uint32_t kBuild = 25480438u;
constexpr uint32_t kGameTimestamp = 1790161983u;
constexpr uint32_t kGameImageSize = 74727424u;

constexpr uintptr_t kContextGlobalRva = 0x347CEF0;
constexpr uintptr_t kRosterGlobalRva = 0x347CED8;
constexpr uintptr_t kGameStateGlobalRva = 0x3326340;
constexpr uintptr_t kModeOffset = 0xAC21C;
constexpr uintptr_t kLocalOffset = 0xB398;
constexpr uintptr_t kHostOffset = 0xB3A8;
constexpr uintptr_t kSessionOwnerOffset = 0xB390;
constexpr uintptr_t kPeerCountOffset = 0x16390;
constexpr uintptr_t kPeersOffset = 0x16398;
constexpr uintptr_t kPeerStride = 0x20;
constexpr uintptr_t kPeerIndexOffset = 0x14;
constexpr uintptr_t kRosterStride = 0xC0;
constexpr uintptr_t kRosterIdOffset = 0;
constexpr uintptr_t kRosterNameOffset = 8;
constexpr size_t kRosterNameLimit = 0x78;
constexpr uint32_t kMaxSlots = 8;
constexpr uint32_t kDocumentedRosterSlots = 4;

struct PeerRecord {
    uint64_t peer_id{};
    uint32_t network_index{};
    uint32_t ordinal{};
    bool operator==(const PeerRecord&) const = default;
};

struct Snapshot {
    uintptr_t context{};
    uintptr_t roster{};
    uintptr_t game_state{};
    uintptr_t session_owner{};
    uint64_t local_peer{};
    uint64_t host_peer{};
    uint32_t mode{};
    uint32_t peer_count{};
    uint32_t roster_count{};
    std::array<PeerRecord, kMaxSlots> peers{};
    std::array<uint64_t, kDocumentedRosterSlots> roster_ids{};
    std::array<uint8_t, kDocumentedRosterSlots * kRosterNameLimit> roster_names{};
    const char* status{"unread"};
};

template<class Reader, class T>
bool read_at(Reader& read, uintptr_t base, uintptr_t offset, T& out) {
    if (base > std::numeric_limits<uintptr_t>::max() - offset) return false;
    return read(base + offset, &out, sizeof(out));
}

template<class Reader>
bool read_bytes_at(Reader& read, uintptr_t base, uintptr_t offset, void* out, size_t size) {
    if (base > std::numeric_limits<uintptr_t>::max() - offset) return false;
    const uintptr_t address = base + offset;
    if (size > std::numeric_limits<uintptr_t>::max() - address) return false;
    return read(address, out, size);
}

template<class Reader>
bool read_payload(Reader& read, uintptr_t image, Snapshot& out) {
    out = Snapshot{};
    out.status = "unread_context";
    if (!read_at(read, image, kContextGlobalRva, out.context) ||
        !read_at(read, image, kRosterGlobalRva, out.roster) ||
        !read_at(read, image, kGameStateGlobalRva, out.game_state)) {
        out.status = "unread_context_globals";
        return false;
    }
    if (!out.context) {
        out.status = "no_context";
        return false;
    }
    if (out.game_state && !read_at(read, out.game_state, kModeOffset, out.mode)) {
        out.status = "unread_game_state";
        return false;
    }
    if (!read_at(read, out.context, kLocalOffset, out.local_peer) ||
        !read_at(read, out.context, kHostOffset, out.host_peer) ||
        !read_at(read, out.context, kSessionOwnerOffset, out.session_owner) ||
        !read_at(read, out.context, kPeerCountOffset, out.peer_count)) {
        out.status = "unread_context_fields";
        return false;
    }
    if (out.peer_count > kMaxSlots) {
        out.status = "peer_count_over_capacity";
        return false;
    }
    uint8_t seen[kMaxSlots]{};
    for (uint32_t i = 0; i < out.peer_count; ++i) {
        const uintptr_t entry_offset = kPeersOffset + uintptr_t(i) * kPeerStride;
        uint32_t lo{}, hi{}, index{};
        if (!read_at(read, out.context, entry_offset, lo) ||
            !read_at(read, out.context, entry_offset + 4, hi) ||
            !read_at(read, out.context, entry_offset + kPeerIndexOffset, index)) {
            out.status = "unread_peer_record";
            return false;
        }
        if (index >= kMaxSlots) {
            out.status = "peer_index_invalid";
            return false;
        }
        if (seen[index]) {
            out.status = "peer_index_duplicate";
            return false;
        }
        seen[index] = 1;
        out.peers[i] = PeerRecord{(uint64_t(hi) << 32) | lo, index, i};
    }
    if (!out.roster) {
        out.status = "no_roster";
        return false;
    }
    out.roster_count = kDocumentedRosterSlots;
    for (uint32_t i = 0; i < kDocumentedRosterSlots; ++i) {
        const uintptr_t record_offset = uintptr_t(i) * kRosterStride;
        uintptr_t record{};
        if (out.roster > std::numeric_limits<uintptr_t>::max() - record_offset) {
            out.status = "unread_roster_record";
            return false;
        }
        record = out.roster + record_offset;
        if (!read_at(read, record, kRosterIdOffset, out.roster_ids[i]) ||
            !read_bytes_at(read, record, kRosterNameOffset,
                  out.roster_names.data() + size_t(i) * kRosterNameLimit,
                  kRosterNameLimit)) {
            out.status = "unread_roster_record";
            return false;
        }
    }
    out.status = "payload_read";
    return true;
}

inline bool payload_equal(const Snapshot& a, const Snapshot& b) {
    return a.context == b.context && a.roster == b.roster &&
        a.game_state == b.game_state && a.session_owner == b.session_owner &&
        a.local_peer == b.local_peer && a.host_peer == b.host_peer &&
        a.mode == b.mode && a.peer_count == b.peer_count &&
        a.roster_count == b.roster_count &&
        a.peers == b.peers && a.roster_ids == b.roster_ids &&
        a.roster_names == b.roster_names;
}

template<class Reader>
Snapshot capture_game_context(uintptr_t image, Reader read) {
    Snapshot out{};
    out.status = "image_identity_refused";
    uint16_t mz{}, machine{}, magic{};
    uint32_t pe{}, signature{}, timestamp{}, image_size{};
    if (!image || !read_at(read, image, 0, mz) || mz != 0x5a4d ||
        !read_at(read, image, 0x3c, pe) || pe > 0x1000 ||
        !read_at(read, image, pe, signature) || signature != 0x4550 ||
        !read_at(read, image, pe + 4, machine) || machine != 0x8664 ||
        !read_at(read, image, pe + 8, timestamp) || timestamp != kGameTimestamp ||
        !read_at(read, image, pe + 24, magic) || magic != 0x20b ||
        !read_at(read, image, pe + 24 + 56, image_size) || image_size != kGameImageSize) {
        return out;
    }
    Snapshot first{};
    if (!read_payload(read, image, first)) return first;
    Snapshot second{};
    if (!read_payload(read, image, second)) {
        second.status = "snapshot_changed";
        return second;
    }
    if (!payload_equal(first, second)) {
        first.status = "snapshot_changed";
        return first;
    }
    first.status = "observed_context_not_player_proof";
    return first;
}

} // namespace ep_session
