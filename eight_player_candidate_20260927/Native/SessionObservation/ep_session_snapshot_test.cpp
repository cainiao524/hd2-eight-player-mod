#include "ep_session_snapshot.h"
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

struct Image {
    uintptr_t base = 0x10000000;
    std::vector<uint8_t> bytes = std::vector<uint8_t>(0x5000000);
    bool read(uintptr_t address, void* out, size_t size) {
        if (address < base || address - base > bytes.size() || size > bytes.size() - (address - base)) return false;
        std::memcpy(out, bytes.data() + (address - base), size); return true;
    }
    template<class T> void put(uintptr_t address, const T& value) {
        assert(address >= base && address - base + sizeof(T) <= bytes.size());
        std::memcpy(bytes.data() + (address - base), &value, sizeof(T));
    }
    void put_bytes(uintptr_t address, const void* value, size_t size) {
        assert(address >= base && address - base + size <= bytes.size());
        std::memcpy(bytes.data() + (address - base), value, size);
    }
};

int main() {
    Image image;
    const uintptr_t b = image.base;
    const uintptr_t context = b + 0x200000;
    const uintptr_t roster = b + 0x210000;
    const uintptr_t state = b + 0x220000;
    uint16_t mz = 0x5a4d, machine = 0x8664, magic = 0x20b;
    uint32_t pe = 0x1000, signature = 0x4550;
    image.put(b + 0, mz); image.put(b + 0x3c, pe);
    image.put(b + pe, signature); image.put(b + pe + 4, machine);
    image.put(b + pe + 8, ep_session::kGameTimestamp);
    image.put(b + pe + 24, magic);
    image.put(b + pe + 24 + 56, ep_session::kGameImageSize);
    image.put(b + ep_session::kContextGlobalRva, context);
    image.put(b + ep_session::kRosterGlobalRva, roster);
    image.put(b + ep_session::kGameStateGlobalRva, state);
    image.put(state + ep_session::kModeOffset, uint32_t(4));
    image.put(context + ep_session::kLocalOffset, uint64_t(0xaaa1));
    image.put(context + ep_session::kHostOffset, uint64_t(0xbbb2));
    image.put(context + ep_session::kSessionOwnerOffset, b + 0x230000);
    image.put(context + ep_session::kPeerCountOffset, uint32_t(2));
    for (uint32_t i = 0; i < 2; ++i) {
        const uintptr_t entry = context + ep_session::kPeersOffset + uintptr_t(i) * ep_session::kPeerStride;
        image.put(entry, uint32_t(0x1000 + i));
        image.put(entry + 4, uint32_t(0x2000 + i));
        image.put(entry + ep_session::kPeerIndexOffset, i);
    }
    for (uint32_t i = 0; i < ep_session::kDocumentedRosterSlots; ++i) {
        const uintptr_t record = roster + uintptr_t(i) * ep_session::kRosterStride;
        image.put(record, uint64_t(0x5000 + i));
        char name[ep_session::kRosterNameLimit]{};
        name[0] = char('A' + i);
        image.put_bytes(record + ep_session::kRosterNameOffset, name, sizeof(name));
    }
    auto read = [&](uintptr_t address, void* out, size_t size) { return image.read(address, out, size); };
    auto ok = ep_session::capture_game_context(b, read);
    assert(ok.status == std::string("observed_context_not_player_proof"));
    assert(ok.mode == 4 && ok.peer_count == 2 && ok.roster_count == 4);
    assert(ok.peers[0].peer_id == 0x200000001000ULL && ok.peers[0].network_index == 0);
    assert(ok.peers[1].peer_id == 0x200100001001ULL && ok.peers[1].network_index == 1);
    assert(ok.roster_ids[0] == 0x5000 && ok.roster_names[0] == 'A');

    image.put(context + ep_session::kPeerCountOffset, uint32_t(9));
    auto over = ep_session::capture_game_context(b, read);
    assert(over.status == std::string("peer_count_over_capacity"));

    image.put(context + ep_session::kPeerCountOffset, uint32_t(2));
    image.put(context + ep_session::kPeersOffset + ep_session::kPeerStride + ep_session::kPeerIndexOffset, uint32_t(0));
    auto duplicate = ep_session::capture_game_context(b, read);
    assert(duplicate.status == std::string("peer_index_duplicate"));

    image.put(context + ep_session::kPeersOffset + ep_session::kPeerStride + ep_session::kPeerIndexOffset, uint32_t(1));
    image.put(b + pe + 8, uint32_t(ep_session::kGameTimestamp + 1));
    auto mismatch = ep_session::capture_game_context(b, read);
    assert(mismatch.status == std::string("image_identity_refused"));

    image.put(b + pe + 8, ep_session::kGameTimestamp);
    image.put(context + ep_session::kPeersOffset + ep_session::kPeerStride + ep_session::kPeerIndexOffset, uint32_t(1));
    size_t reads = 0;
    auto unstable = [&](uintptr_t address, void* out, size_t size) {
        const bool result = image.read(address, out, size);
        ++reads;
        // The first successful payload has 22 bounded reads. Change a field
        // before the second payload to prove the stable reread gate rejects it.
        if (reads == 22) image.put(roster, uint64_t(0x5fff));
        return result;
    };
    auto changed = ep_session::capture_game_context(b, unstable);
    assert(changed.status == std::string("snapshot_changed"));
    std::cout << "session_snapshot_synthetic_passed\n";
}
