#include "ep_session_vtable_snapshot.h"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>

struct Image {
    uintptr_t base = 0x10000000;
    std::vector<uint8_t> bytes = std::vector<uint8_t>(0x5000000);
    bool read(uintptr_t address, void* out, size_t size) {
        if (address < base || address - base > bytes.size() ||
            size > bytes.size() - (address - base)) return false;
        std::memcpy(out, bytes.data() + (address - base), size);
        return true;
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
    const uintptr_t session = b + 0x200000;
    const uintptr_t vtable = b + 0x210000;
    const uintptr_t records = b + 0x220000;
    const uintptr_t record0 = b + 0x230000;
    const uintptr_t record1 = b + 0x230100;

    uint16_t mz = 0x5a4d, machine = 0x8664, magic = 0x20b;
    uint32_t pe = 0x1000, signature = 0x4550;
    image.put(b, mz);
    image.put(b + 0x3c, pe);
    image.put(b + pe, signature);
    image.put(b + pe + 4, machine);
    image.put(b + pe + 8, ep_session_vtable::kEngineTimestamp);
    image.put(b + pe + 24, magic);
    image.put(b + pe + 24 + 56, ep_session_vtable::kEngineImageSize);

    image.put(session, vtable);
    image.put(vtable + ep_session_vtable::kCountSlot, b + ep_session_vtable::kCountFunctionRva);
    image.put(vtable + ep_session_vtable::kRecordSlot, b + ep_session_vtable::kRecordFunctionRva);
    image.put(vtable + ep_session_vtable::kOwnerSlot, b + ep_session_vtable::kOwnerFunctionRva);
    image.put(b + ep_session_vtable::kCountFunctionRva,
              ep_session_vtable::kCountFunctionPrefix);
    image.put(b + ep_session_vtable::kRecordFunctionRva,
              ep_session_vtable::kRecordFunctionPrefix);
    image.put(b + ep_session_vtable::kOwnerFunctionRva,
              ep_session_vtable::kOwnerFunctionPrefix);
    image.put(session + ep_session_vtable::kSessionOwnerOffset, uint64_t(0xabc));
    image.put(session + ep_session_vtable::kSessionCountOffset, uint32_t(2));
    image.put(session + ep_session_vtable::kSessionRecordsOffset, records);
    image.put(records, record0);
    image.put(records + ep_session_vtable::kRecordStride, record1);
    std::array<uint8_t, ep_session_vtable::kOpaqueRecordSize> bytes0{};
    std::array<uint8_t, ep_session_vtable::kOpaqueRecordSize> bytes1{};
    bytes0[0] = 0x40; bytes1[0] = 0x41;
    image.put_bytes(record0, bytes0.data(), bytes0.size());
    image.put_bytes(record1, bytes1.data(), bytes1.size());

    auto read = [&](uintptr_t address, void* out, size_t size) {
        return image.read(address, out, size);
    };
    auto ok = ep_session_vtable::capture(b, session, read);
    assert(ok.status == std::string("opaque_session_records_not_player_proof"));
    assert(ok.count == 2 && ok.owner == 0xabc && ok.entries[0].address == record0);
    assert(ok.entries[1].bytes[0] == 0x41);

    image.put(session + ep_session_vtable::kSessionCountOffset, uint32_t(9));
    auto over = ep_session_vtable::capture(b, session, read);
    assert(over.status == std::string("record_count_over_capacity"));

    image.put(session + ep_session_vtable::kSessionCountOffset, uint32_t(2));
    image.put(records + ep_session_vtable::kRecordStride, record0);
    auto duplicate = ep_session_vtable::capture(b, session, read);
    assert(duplicate.status == std::string("duplicate_record_pointer"));

    image.put(records + ep_session_vtable::kRecordStride, record1);
    image.put(b + ep_session_vtable::kRecordFunctionRva, uint8_t(0x90));
    auto bad = ep_session_vtable::capture(b, session, read);
    assert(bad.status == std::string("vtable_fingerprint_refused"));
    std::cout << "session_vtable_snapshot_synthetic_passed\n";
}
