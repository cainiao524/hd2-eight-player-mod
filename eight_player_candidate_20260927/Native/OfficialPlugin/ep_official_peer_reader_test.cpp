#include "ep_official_peer_reader.h"

#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>

using namespace ep_official_peer_reader;

namespace {
BuildIdentity pinned_identity() {
    return {kSteamBuild, kExeTimestamp, kExeImageSize, kGameTimestamp,
            kGameImageSize, kExeSha256, kGameSha256};
}

struct Guard {
    bool acquire_ok = true;
    bool live_ok = true;
    bool quiesce_ok = true;
    bool cleanup_ok = true;
    unsigned acquires = 0;
    unsigned releases = 0;
    unsigned quiesce_begins = 0;
    unsigned quiesce_ends = 0;
    unsigned cleanups = 0;
};

bool owner_acquire(void* raw, uintptr_t session, uintptr_t owner) {
    auto& guard = *static_cast<Guard*>(raw);
    ++guard.acquires;
    return session != 0 && owner != 0 && guard.acquire_ok;
}

bool owner_live(void* raw, uintptr_t session, uintptr_t owner) {
    auto& guard = *static_cast<Guard*>(raw);
    return session != 0 && owner != 0 && guard.live_ok;
}

void owner_release(void* raw, uintptr_t, uintptr_t) {
    ++static_cast<Guard*>(raw)->releases;
}

bool quiescence_begin(void* raw, uintptr_t session, uintptr_t owner) {
    auto& guard = *static_cast<Guard*>(raw);
    ++guard.quiesce_begins;
    return session != 0 && owner != 0 && guard.quiesce_ok;
}

void quiescence_end(void* raw, uintptr_t, uintptr_t) {
    ++static_cast<Guard*>(raw)->quiesce_ends;
}

bool cleanup(void* raw, uintptr_t session, uintptr_t owner) {
    auto& guard = *static_cast<Guard*>(raw);
    ++guard.cleanups;
    return session != 0 && owner != 0 && guard.cleanup_ok;
}

OwnerCallbacks callbacks(Guard& guard) {
    return {&guard, &owner_acquire, &owner_live, &owner_release,
            &quiescence_begin, &quiescence_end, &cleanup};
}

void make_observation(ep_session_vtable::Snapshot& snapshot,
                      ep_session_record::Result& semantics) {
    snapshot.session = 0x1000;
    snapshot.owner = 0x2000;
    snapshot.count = 2;
    snapshot.status = "opaque_session_records_not_player_proof";
    snapshot.entries[0].address = 0x3000;
    snapshot.entries[1].address = 0x3100;
    semantics.count = 2;
    semantics.owner_opaque = 0x2000;
    semantics.self_match_count = 1;
    semantics.self_ordinal = 0;
    semantics.status = "opaque_record_relationships_verified";
    semantics.records[0] = {0x3000, 0x1111, 3};
    semantics.records[1] = {0x3100, 0x2222, 4};
}
} // namespace

int main() {
    ep_session_vtable::Snapshot snapshot{};
    ep_session_record::Result semantics{};
    make_observation(snapshot, semantics);
    Guard guard{};

    Adapter reader;
    assert(reader.enable(pinned_identity(), snapshot, semantics,
                         OwnerCallbacks{}) == Status::kCallbacksMissing);

    auto identity = pinned_identity();
    identity.steam_build++;
    assert(reader.enable(identity, snapshot, semantics, callbacks(guard)) ==
           Status::kVersionMismatch);

    identity = pinned_identity();
    assert(reader.enable(identity, snapshot, semantics, callbacks(guard)) ==
           Status::kReady);
    assert(reader.enabled() && reader.session() == 0x1000 &&
           reader.owner() == 0x2000 && reader.self_ordinal() == 0);
    assert(guard.acquires == 1 && guard.quiesce_begins == 1 &&
           guard.quiesce_ends == 1);

    uint32_t count = 0;
    assert(reader.get_peer_count(count) == Status::kReady && count == 2);
    PeerRecord record{};
    assert(reader.get_peer_record(1, record) == Status::kReady);
    assert(record.address == 0x3100 && record.identity_token == 0x2222 &&
           record.observed_byte_29 == 4);
    assert(reader.get_peer_record(2, record) == Status::kIndexInvalid);
    assert(guard.quiesce_begins == 2 && guard.quiesce_ends == 2);
    assert(reader.enable(pinned_identity(), snapshot, semantics,
                         callbacks(guard)) == Status::kAlreadyEnabled);

    guard.live_ok = false;
    assert(reader.get_peer_count(count) == Status::kOwnerLost);
    guard.live_ok = true;
    guard.cleanup_ok = true;
    assert(reader.close() == Status::kClosed);
    assert(!reader.enabled() && guard.cleanups == 1 && guard.releases == 1);
    assert(reader.get_peer_count(count) == Status::kDisabled);

    // Every lifecycle callback is mandatory even though the adapter itself
    // has no writer function.  A missing cleanup callback must refuse enable.
    Guard missing_guard{};
    auto incomplete = callbacks(missing_guard);
    incomplete.cleanup = nullptr;
    Adapter rejected;
    assert(rejected.enable(pinned_identity(), snapshot, semantics, incomplete) ==
           Status::kCallbacksMissing);

    snapshot.count = kMaxPeers + 1;
    Adapter over_capacity;
    assert(over_capacity.enable(pinned_identity(), snapshot, semantics,
                                callbacks(missing_guard)) ==
           Status::kRecordCountInvalid);

    make_observation(snapshot, semantics);
    semantics.status = "self_record_unresolved";
    Adapter unproven;
    assert(unproven.enable(pinned_identity(), snapshot, semantics,
                           callbacks(missing_guard)) ==
           Status::kSnapshotUnproven);

    make_observation(snapshot, semantics);
    semantics.owner_opaque = 0x3000;
    Adapter owner_mismatch;
    assert(owner_mismatch.enable(pinned_identity(), snapshot, semantics,
                                 callbacks(missing_guard)) ==
           Status::kOwnerInvalid);

    std::cout << "official_peer_reader_contract_synthetic_passed\n";
}
