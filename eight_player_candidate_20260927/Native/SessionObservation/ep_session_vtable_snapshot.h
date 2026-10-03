#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>

// Fixed-build, no-call observation of the underlying GameSession object.
// The public GameSession C API table is a wrapper and is intentionally not
// called here.  This contract only copies the bounded opaque records used by
// the captured vtable implementation; it does not assign player semantics.
namespace ep_session_vtable {

constexpr uint32_t kBuild = 25480438u;
constexpr uint32_t kEngineTimestamp = 1790149348u;
constexpr uint32_t kEngineImageSize = 60719104u;

constexpr uintptr_t kCountSlot = 0x70;
constexpr uintptr_t kRecordSlot = 0x78;
constexpr uintptr_t kOwnerSlot = 0x98;
constexpr uintptr_t kCountFunctionRva = 0x292BE0;
constexpr uintptr_t kRecordFunctionRva = 0x292BF0;
constexpr uintptr_t kOwnerFunctionRva = 0x292CC0;
constexpr uintptr_t kSessionOwnerOffset = 0x130;
constexpr uintptr_t kSessionCountOffset = 0x138;
constexpr uintptr_t kSessionRecordsOffset = 0x140;
constexpr uintptr_t kRecordStride = 0x30;
constexpr size_t kOpaqueRecordSize = 0x30;
constexpr uint32_t kMaxRecords = 8;

constexpr std::array<uint8_t, 7> kCountFunctionPrefix{
    0x8B, 0x81, 0x38, 0x01, 0x00, 0x00, 0xC3};
constexpr std::array<uint8_t, 21> kRecordFunctionPrefix{
    0x8B, 0xC2, 0x48, 0x8D, 0x14, 0x40, 0x48, 0x8B, 0x81, 0x40, 0x01,
    0x00, 0x00, 0x48, 0x03, 0xD2, 0x48, 0x8B, 0x04, 0xD0, 0xC3};
constexpr std::array<uint8_t, 7> kOwnerFunctionPrefix{
    0x48, 0x8B, 0x81, 0x30, 0x01, 0x00, 0x00};

struct OpaqueRecord {
    uintptr_t address{};
    std::array<uint8_t, kOpaqueRecordSize> bytes{};
    bool operator==(const OpaqueRecord&) const = default;
};

struct Snapshot {
    uintptr_t session{};
    uintptr_t vtable{};
    uintptr_t owner{};
    uintptr_t records{};
    uint32_t count{};
    std::array<OpaqueRecord, kMaxRecords> entries{};
    const char* status{"unread"};
};

template<class Reader, class T>
bool read_at(Reader& read, uintptr_t address, T& out) {
    if (!address) return false;
    return read(address, &out, sizeof(out));
}

inline bool add_ok(uintptr_t base, uintptr_t offset, uintptr_t& out) {
    if (offset > std::numeric_limits<uintptr_t>::max() - base) return false;
    out = base + offset;
    return true;
}

template<class Reader, class T>
bool read_offset(Reader& read, uintptr_t base, uintptr_t offset, T& out) {
    uintptr_t address{};
    return add_ok(base, offset, address) && read_at(read, address, out);
}

template<class Reader>
bool read_bytes(Reader& read, uintptr_t address, void* out, size_t size) {
    if (!address || !out || size == 0) return false;
    return read(address, out, size);
}

template<size_t N, class Reader>
bool function_prefix_matches(Reader& read, uintptr_t module, uintptr_t rva,
                             const std::array<uint8_t, N>& expected) {
    uintptr_t address{};
    if (!add_ok(module, rva, address)) return false;
    std::array<uint8_t, N> actual{};
    return read_bytes(read, address, actual.data(), actual.size()) &&
           actual == expected;
}

template<size_t N, class Reader>
bool function_pointer_matches(Reader& read, uintptr_t module, uintptr_t pointer,
                              uintptr_t rva,
                              const std::array<uint8_t, N>& expected) {
    uintptr_t expected_pointer{};
    return add_ok(module, rva, expected_pointer) && pointer == expected_pointer &&
        function_prefix_matches(read, module, rva, expected);
}

template<class Reader>
bool engine_identity_matches(Reader& read, uintptr_t module) {
    uint16_t mz{}, machine{}, magic{};
    uint32_t pe{}, signature{}, timestamp{}, image_size{};
    return read_at(read, module, mz) && mz == 0x5A4D &&
        read_offset(read, module, 0x3C, pe) && pe <= 0x1000 &&
        read_offset(read, module, pe, signature) && signature == 0x4550 &&
        read_offset(read, module, pe + 4, machine) && machine == 0x8664 &&
        read_offset(read, module, pe + 8, timestamp) && timestamp == kEngineTimestamp &&
        read_offset(read, module, pe + 24, magic) && magic == 0x20B &&
        read_offset(read, module, pe + 24 + 56, image_size) &&
        image_size == kEngineImageSize;
}

template<class Reader>
bool read_once(Reader& read, uintptr_t module, uintptr_t session, Snapshot& out) {
    out = Snapshot{};
    out.session = session;
    out.status = "unread_session";
    if (!module || !session) return false;

    uintptr_t vtable{};
    if (!read_at(read, session, vtable) || !vtable) {
        out.status = "unread_vtable";
        return false;
    }
    out.vtable = vtable;
    uintptr_t count_fn{}, record_fn{}, owner_fn{};
    if (!read_offset(read, vtable, kCountSlot, count_fn) ||
        !read_offset(read, vtable, kRecordSlot, record_fn) ||
        !read_offset(read, vtable, kOwnerSlot, owner_fn) ||
        !function_pointer_matches(read, module, count_fn, kCountFunctionRva,
                                  kCountFunctionPrefix) ||
        !function_pointer_matches(read, module, record_fn, kRecordFunctionRva,
                                  kRecordFunctionPrefix) ||
        !function_pointer_matches(read, module, owner_fn, kOwnerFunctionRva,
                                  kOwnerFunctionPrefix)) {
        out.status = "vtable_fingerprint_refused";
        return false;
    }

    if (!read_offset(read, session, kSessionOwnerOffset, out.owner) ||
        !read_offset(read, session, kSessionCountOffset, out.count) ||
        !read_offset(read, session, kSessionRecordsOffset, out.records)) {
        out.status = "unread_session_fields";
        return false;
    }
    if (out.count > kMaxRecords) {
        out.status = "record_count_over_capacity";
        return false;
    }
    if (out.count && !out.records) {
        out.status = "null_record_table";
        return false;
    }

    for (uint32_t i = 0; i < out.count; ++i) {
        uintptr_t offset{};
        uintptr_t record_address{};
        if (i > std::numeric_limits<uintptr_t>::max() / kRecordStride ||
            !add_ok(out.records, uintptr_t(i) * kRecordStride, offset) ||
            !read_at(read, offset, record_address) || !record_address) {
            out.status = "unread_record_pointer";
            return false;
        }
        for (uint32_t prior = 0; prior < i; ++prior) {
            if (out.entries[prior].address == record_address) {
                out.status = "duplicate_record_pointer";
                return false;
            }
        }
        out.entries[i].address = record_address;
        if (!read_bytes(read, record_address, out.entries[i].bytes.data(),
                        out.entries[i].bytes.size())) {
            out.status = "unread_opaque_record";
            return false;
        }
    }
    out.status = "opaque_records_read";
    return true;
}

template<class Reader>
Snapshot capture(uintptr_t module, uintptr_t session, Reader read) {
    Snapshot out{};
    out.status = "image_identity_refused";
    if (!engine_identity_matches(read, module)) return out;
    Snapshot first{};
    if (!read_once(read, module, session, first)) return first;
    Snapshot second{};
    if (!read_once(read, module, session, second)) {
        second.status = "snapshot_changed";
        return second;
    }
    if (first.session != second.session || first.vtable != second.vtable ||
        first.owner != second.owner || first.records != second.records ||
        first.count != second.count || first.entries != second.entries) {
        first.status = "snapshot_changed";
        return first;
    }
    first.status = "opaque_session_records_not_player_proof";
    return first;
}

} // namespace ep_session_vtable
