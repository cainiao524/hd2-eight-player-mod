#include "ep_session_record_semantics.h"

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
    image.put(vtable + ep_session_vtable::kCountSlot,
              b + ep_session_vtable::kCountFunctionRva);
    image.put(vtable + ep_session_vtable::kRecordSlot,
              b + ep_session_vtable::kRecordFunctionRva);
    image.put(vtable + ep_session_vtable::kOwnerSlot,
              b + ep_session_vtable::kOwnerFunctionRva);
    image.put(b + ep_session_vtable::kCountFunctionRva,
              ep_session_vtable::kCountFunctionPrefix);
    image.put(b + ep_session_vtable::kRecordFunctionRva,
              ep_session_vtable::kRecordFunctionPrefix);
    image.put(b + ep_session_vtable::kOwnerFunctionRva,
              ep_session_vtable::kOwnerFunctionPrefix);
    image.put(session + ep_session_vtable::kSessionOwnerOffset, uintptr_t(0xabc));
    image.put(session + ep_session_record::kSessionSelfKeyOffset,
              uintptr_t(0x1111));
    image.put(session + ep_session_vtable::kSessionCountOffset, uint32_t(2));
    image.put(session + ep_session_vtable::kSessionRecordsOffset, records);
    image.put(records, record0);
    image.put(records + ep_session_vtable::kRecordStride, record1);
    std::array<uint8_t, ep_session_record::kRecordSize> bytes0{};
    std::array<uint8_t, ep_session_record::kRecordSize> bytes1{};
    image.put_bytes(record0, bytes0.data(), bytes0.size());
    image.put_bytes(record1, bytes1.data(), bytes1.size());
    image.put(record0 + ep_session_record::kRecordIdentityTokenOffset,
              uintptr_t(0x1111));
    image.put(record1 + ep_session_record::kRecordIdentityTokenOffset,
              uintptr_t(0x2222));
    image.put(record0 + ep_session_record::kRecordObservedByteOffset,
              uint8_t(3));
    image.put(record1 + ep_session_record::kRecordObservedByteOffset,
              uint8_t(4));
    auto read = [&](uintptr_t address, void* out, size_t size) {
        return image.read(address, out, size);
    };
    auto snapshot = ep_session_vtable::capture(b, session, read);
    assert(snapshot.status ==
           std::string("opaque_session_records_not_player_proof"));
    ep_session_record::Result result{};
    assert(ep_session_record::verify(snapshot, read, result));
    assert(result.status ==
           std::string("opaque_record_relationships_verified"));
    assert(result.self_ordinal == 0 && result.records[1].observed_byte_29 == 4);

    image.put(session + ep_session_record::kSessionSelfKeyOffset,
              uintptr_t(0x3333));
    assert(!ep_session_record::verify(snapshot, read, result));
    assert(result.status == std::string("self_record_unresolved"));
    image.put(session + ep_session_record::kSessionSelfKeyOffset,
              uintptr_t(0x1111));
    image.put(record1 + ep_session_record::kRecordIdentityTokenOffset,
              uintptr_t(0x1111));
    assert(!ep_session_record::verify(snapshot, read, result));
    assert(result.status == std::string("duplicate_record_identity_token"));
    std::cout << "session_record_semantics_synthetic_passed\n";
}

