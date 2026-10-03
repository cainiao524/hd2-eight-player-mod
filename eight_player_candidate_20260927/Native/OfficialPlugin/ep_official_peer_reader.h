#pragma once

// Read-only GameSession peer/record adapter for the pinned HD2 build.
//
// This header deliberately exposes no GameSession vtable writer and no
// add_peer/remove_peer/create_game_object entry point.  It accepts only the
// bounded, no-call snapshots produced by SessionObservation.  A caller must
// prove owner lifetime, thread quiescence and cleanup callbacks before the
// adapter can be enabled.  Missing proof leaves the adapter disabled.

#include "../SessionObservation/ep_session_record_semantics.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>

namespace ep_official_peer_reader {

constexpr uint32_t kSteamBuild = 25480438u;
constexpr uint32_t kExeTimestamp = 1790149348u;
constexpr uint32_t kExeImageSize = 60719104u;
constexpr uint32_t kGameTimestamp = 1790161983u;
constexpr uint32_t kGameImageSize = 74727424u;
constexpr uint32_t kMaxPeers = 8u;
constexpr uintptr_t kNetworkSlotOffset = 0x38;
constexpr uintptr_t kGameSessionSlotOffset = 0x40;

// The public Autodesk table describes these offsets.  They are retained as
// documentation only: this adapter never dereferences or calls them.
constexpr uintptr_t kPublicPeerGetterOffset = 0x48;
constexpr uintptr_t kPublicPeerCountGetterOffset = 0x50;
constexpr uintptr_t kForbiddenAddPeerOffset = 0x40;
constexpr uintptr_t kForbiddenCreateGameObjectOffset = 0x70;
constexpr uintptr_t kForbiddenRemovePeerOffset = 0x88;

constexpr std::array<uint8_t, 32> kExeSha256{
    0xf5, 0xfe, 0xe0, 0x3d, 0xcf, 0xdb, 0x2e, 0x55,
    0x3a, 0x47, 0x52, 0x28, 0x35, 0x90, 0x95, 0x0a,
    0xac, 0x13, 0x31, 0x6b, 0x37, 0x6d, 0x81, 0x96,
    0xaa, 0x55, 0x6f, 0xf0, 0x40, 0x0d, 0x5f, 0x06};
constexpr std::array<uint8_t, 32> kGameSha256{
    0x2e, 0x2c, 0x3b, 0x7c, 0x25, 0x00, 0x64, 0x6d,
    0xad, 0xd5, 0xf2, 0xb4, 0xc6, 0xe0, 0x50, 0x4d,
    0xb7, 0xe7, 0x89, 0x61, 0x39, 0xf6, 0x4c, 0xdd,
    0xc0, 0xd1, 0x81, 0x3c, 0x71, 0x8f, 0x51, 0xe0};

struct BuildIdentity {
    uint32_t steam_build{};
    uint32_t exe_timestamp{};
    uint32_t exe_image_size{};
    uint32_t game_timestamp{};
    uint32_t game_image_size{};
    std::array<uint8_t, 32> exe_sha256{};
    std::array<uint8_t, 32> game_sha256{};

    bool matches_pinned() const {
        return steam_build == kSteamBuild &&
               exe_timestamp == kExeTimestamp &&
               exe_image_size == kExeImageSize &&
               game_timestamp == kGameTimestamp &&
               game_image_size == kGameImageSize &&
               exe_sha256 == kExeSha256 && game_sha256 == kGameSha256;
    }
};

// These callbacks are lifetime and synchronization obligations of the host
// bridge.  They do not expose any GameSession mutation operation.  The
// adapter refuses to enable when any callback is absent.
using owner_acquire_fn = bool (*)(void* context, uintptr_t session,
                                  uintptr_t owner);
using owner_live_fn = bool (*)(void* context, uintptr_t session,
                               uintptr_t owner);
using owner_release_fn = void (*)(void* context, uintptr_t session,
                                  uintptr_t owner);
using quiescence_begin_fn = bool (*)(void* context, uintptr_t session,
                                     uintptr_t owner);
using quiescence_end_fn = void (*)(void* context, uintptr_t session,
                                   uintptr_t owner);
using cleanup_fn = bool (*)(void* context, uintptr_t session,
                            uintptr_t owner);

struct OwnerCallbacks {
    void* context{};
    owner_acquire_fn owner_acquire{};
    owner_live_fn owner_live{};
    owner_release_fn owner_release{};
    quiescence_begin_fn quiescence_begin{};
    quiescence_end_fn quiescence_end{};
    cleanup_fn cleanup{};

    bool complete() const {
        return context != nullptr && owner_acquire != nullptr &&
               owner_live != nullptr && owner_release != nullptr &&
               quiescence_begin != nullptr && quiescence_end != nullptr &&
               cleanup != nullptr;
    }
};

struct PeerRecord {
    uintptr_t address{};
    uintptr_t identity_token{};
    uint8_t observed_byte_29{};
};

enum class Status : uint32_t {
    kReady = 0,
    kClosed,
    kDisabled,
    kVersionMismatch,
    kCallbacksMissing,
    kSnapshotUnproven,
    kRecordCountInvalid,
    kOwnerInvalid,
    kOwnerUnavailable,
    kQuiescenceFailed,
    kIndexInvalid,
    kCleanupFailed,
    kOwnerLost,
    kAlreadyEnabled,
};

inline const char* status_name(Status status) {
    switch (status) {
    case Status::kReady: return "ready";
    case Status::kClosed: return "closed";
    case Status::kDisabled: return "disabled";
    case Status::kVersionMismatch: return "version_mismatch";
    case Status::kCallbacksMissing: return "callbacks_missing";
    case Status::kSnapshotUnproven: return "snapshot_unproven";
    case Status::kRecordCountInvalid: return "record_count_invalid";
    case Status::kOwnerInvalid: return "owner_invalid";
    case Status::kOwnerUnavailable: return "owner_unavailable";
    case Status::kQuiescenceFailed: return "quiescence_failed";
    case Status::kIndexInvalid: return "index_invalid";
    case Status::kCleanupFailed: return "cleanup_failed";
    case Status::kOwnerLost: return "owner_lost";
    case Status::kAlreadyEnabled: return "already_enabled";
    }
    return "unknown";
}

class Adapter final {
public:
    Adapter() = default;
    Adapter(const Adapter&) = delete;
    Adapter& operator=(const Adapter&) = delete;

    // Enable from two independent, stable, no-call observations.  No
    // GameSession function is invoked here.  The lifecycle callbacks are
    // called only to acquire a lifetime lease and establish quiescence while
    // the bounded records are copied.
    Status enable(const BuildIdentity& identity,
                  const ep_session_vtable::Snapshot& snapshot,
                  const ep_session_record::Result& semantics,
                  const OwnerCallbacks& callbacks) {
        if (enabled_) return Status::kAlreadyEnabled;
        reset_without_callbacks();
        if (!identity.matches_pinned()) return Status::kVersionMismatch;
        if (!callbacks.complete()) return Status::kCallbacksMissing;
        if (snapshot.status !=
                std::string("opaque_session_records_not_player_proof") ||
            semantics.status !=
                std::string("opaque_record_relationships_verified")) {
            return Status::kSnapshotUnproven;
        }
        if (!snapshot.session || !snapshot.owner ||
            snapshot.count > kMaxPeers || semantics.count != snapshot.count ||
            semantics.self_match_count != 1 ||
            semantics.self_ordinal >= snapshot.count) {
            return snapshot.count > kMaxPeers ? Status::kRecordCountInvalid
                                               : Status::kOwnerInvalid;
        }
        for (uint32_t i = 0; i < snapshot.count; ++i) {
            if (!snapshot.entries[i].address ||
                !semantics.records[i].address ||
                snapshot.entries[i].address != semantics.records[i].address ||
                !semantics.records[i].identity_token) {
                return Status::kSnapshotUnproven;
            }
            for (uint32_t prior = 0; prior < i; ++prior) {
                if (snapshot.entries[prior].address ==
                        snapshot.entries[i].address ||
                    semantics.records[prior].identity_token ==
                        semantics.records[i].identity_token) {
                    return Status::kSnapshotUnproven;
                }
            }
        }
        if (!callbacks.owner_acquire(callbacks.context, snapshot.session,
                                     snapshot.owner)) {
            return Status::kOwnerUnavailable;
        }
        if (!callbacks.owner_live(callbacks.context, snapshot.session,
                                  snapshot.owner)) {
            callbacks.owner_release(callbacks.context, snapshot.session,
                                    snapshot.owner);
            return Status::kOwnerLost;
        }
        if (!callbacks.quiescence_begin(callbacks.context, snapshot.session,
                                        snapshot.owner)) {
            callbacks.owner_release(callbacks.context, snapshot.session,
                                    snapshot.owner);
            return Status::kQuiescenceFailed;
        }
        identity_ = identity;
        callbacks_ = callbacks;
        session_ = snapshot.session;
        owner_ = snapshot.owner;
        count_ = snapshot.count;
        self_ordinal_ = semantics.self_ordinal;
        for (uint32_t i = 0; i < count_; ++i) {
            records_[i] = {semantics.records[i].address,
                           semantics.records[i].identity_token,
                           semantics.records[i].observed_byte_29};
        }
        callbacks.quiescence_end(callbacks.context, snapshot.session,
                                 snapshot.owner);
        enabled_ = true;
        return Status::kReady;
    }

    Status get_peer_count(uint32_t& out) const {
        if (!enabled_) return Status::kDisabled;
        if (!callbacks_.owner_live(callbacks_.context, session_, owner_)) {
            return Status::kOwnerLost;
        }
        out = count_;
        return Status::kReady;
    }

    // The returned record remains an opaque identity relationship.  It is not
    // a PeerId, player slot, network index, or permission to create entities.
    Status get_peer_record(uint32_t index, PeerRecord& out) const {
        if (!enabled_) return Status::kDisabled;
        if (index >= count_ || index >= kMaxPeers) return Status::kIndexInvalid;
        if (!callbacks_.owner_live(callbacks_.context, session_, owner_)) {
            return Status::kOwnerLost;
        }
        if (!callbacks_.quiescence_begin(callbacks_.context, session_,
                                         owner_)) {
            return Status::kQuiescenceFailed;
        }
        out = records_[index];
        callbacks_.quiescence_end(callbacks_.context, session_, owner_);
        return Status::kReady;
    }

    uint32_t self_ordinal() const { return self_ordinal_; }
    uintptr_t session() const { return enabled_ ? session_ : 0; }
    uintptr_t owner() const { return enabled_ ? owner_ : 0; }
    bool enabled() const { return enabled_; }

    // Disable always clears local state first.  The cleanup callback is a
    // required host-bridge obligation; this adapter itself performs no
    // GameSession mutation and exposes no add/remove/create operation.
    Status close() {
        if (!enabled_) return Status::kDisabled;
        const uintptr_t session = session_;
        const uintptr_t owner = owner_;
        const OwnerCallbacks callbacks = callbacks_;
        enabled_ = false;
        session_ = 0;
        owner_ = 0;
        count_ = 0;
        self_ordinal_ = 0;
        records_ = {};
        const bool quiesced = callbacks.quiescence_begin(
            callbacks.context, session, owner);
        bool cleaned = false;
        if (quiesced) {
            cleaned = callbacks.cleanup(callbacks.context, session, owner);
            callbacks.quiescence_end(callbacks.context, session, owner);
        }
        callbacks.owner_release(callbacks.context, session, owner);
        return quiesced && cleaned ? Status::kClosed
                                   : (quiesced ? Status::kCleanupFailed
                                               : Status::kQuiescenceFailed);
    }

private:
    void reset_without_callbacks() {
        enabled_ = false;
        session_ = 0;
        owner_ = 0;
        count_ = 0;
        self_ordinal_ = 0;
        records_ = {};
        identity_ = {};
        callbacks_ = {};
    }

    BuildIdentity identity_{};
    OwnerCallbacks callbacks_{};
    uintptr_t session_{};
    uintptr_t owner_{};
    uint32_t count_{};
    uint32_t self_ordinal_{};
    std::array<PeerRecord, kMaxPeers> records_{};
    bool enabled_{};
};

} // namespace ep_official_peer_reader
