#pragma once
#include <array>
#include <cstdint>
#include <cstring>
#include <limits>

// Build 25480438 only. Reads bytes through an injected reader; never invokes an
// engine function. Source: live_engine_session_vtable_20261003.json.
namespace ep_session {
struct Snapshot {
    uintptr_t session{};
    uint64_t host_value{};
    uint32_t record_count{};
    std::array<uint64_t, 8> record_ids{};
    const char* status{"unread"};
};
template<class Reader, class T>
bool read_at(Reader& read, uintptr_t base, uintptr_t offset, T& out) {
    if (base > std::numeric_limits<uintptr_t>::max() - offset) return false;
    return read(base + offset, &out, sizeof(out));
}
template<class Reader, size_t N>
bool pin(Reader& read, uintptr_t base, uintptr_t offset, const uint8_t (&expected)[N]) {
    uint8_t actual[N]{};
    return read_at(read, base, offset, actual) && std::memcmp(actual, expected, N) == 0;
}
template<class Reader>
Snapshot capture(uintptr_t image, Reader read) {
    Snapshot out;
    out.status = "image_identity_refused";
    uint16_t mz{}, machine{}, magic{};
    uint32_t pe{}, signature{}, timestamp{}, size{};
    if (!image || !read_at(read,image,0,mz) || mz != 0x5a4d ||
        !read_at(read,image,0x3c,pe) || pe > 0x1000 ||
        !read_at(read,image,pe,signature) || signature != 0x4550 ||
        !read_at(read,image,pe+4,machine) || machine != 0x8664 ||
        !read_at(read,image,pe+8,timestamp) || timestamp != 1790149348u ||
        !read_at(read,image,pe+24,magic) || magic != 0x20b ||
        !read_at(read,image,pe+24+56,size) || size != 60719104u) return out;
    constexpr uint8_t getter[] = {0x48,0x8b,0x05,0x81,0x04,0x6c,0x01,0x48,0x8b,0x80,0xa8,0,0,0,0xc3};
    constexpr uint8_t count[] = {0x8b,0x81,0x38,0x01,0,0,0xc3};
    constexpr uint8_t peer[] = {0x8b,0xc2,0x48,0x8d,0x14,0x40,0x48,0x8b,0x81,0x40,0x01,0,0,0x48,0x03,0xd2,0x48,0x8b,0x04,0xd0,0xc3};
    constexpr uint8_t host[] = {0x48,0x8b,0x81,0x30,0x01,0,0,0xc3};
    out.status = "code_identity_refused";
    if (!pin(read,image,0x34fdf0,getter) || !pin(read,image,0x292be0,count) ||
        !pin(read,image,0x292bf0,peer) || !pin(read,image,0x292cc0,host)) return out;
    uintptr_t root{}, session{}, vtable{}, fn_count{}, fn_peer{}, fn_host{};
    out.status = "unreadable_root";
    if (!read_at(read,image,0x1a10278,root)) return out;
    if (!root) {out.status="no_root"; return out;}
    if (!read_at(read,root,0xa8,session)) return out;
    if (!session) {out.status="no_session"; return out;}
    out.status = "vtable_identity_refused";
    if (!read_at(read,session,0,vtable) || vtable != image+0x1675b70 ||
        !read_at(read,vtable,0x70,fn_count) || fn_count != image+0x292be0 ||
        !read_at(read,vtable,0x78,fn_peer) || fn_peer != image+0x292bf0 ||
        !read_at(read,vtable,0x98,fn_host) || fn_host != image+0x292cc0) return out;
    struct Header {uint64_t host; uint32_t count; uint32_t padding; uintptr_t data;};
    static_assert(sizeof(Header)==24);
    Header before{}, after{};
    out.status = "unreadable_header";
    if (!read_at(read,session,0x130,before)) return out;
    out.status = "count_exceeds_observation_bound";
    if (before.count > out.record_ids.size()) return out;
    out.status = "missing_record_storage";
    if (before.count && !before.data) return out;
    std::array<uint64_t,8> ids{};
    out.status = "unreadable_records";
    for (uint32_t i=0;i<before.count;++i) {
        if (!read_at(read,before.data,uintptr_t(i)*48,ids[i])) return out;
    }
    out.status = "snapshot_changed";
    for (uint32_t i=0;i<before.count;++i) {
        uint64_t again{};
        if (!read_at(read,before.data,uintptr_t(i)*48,again) || again != ids[i]) return out;
    }
    uintptr_t root_after{}, session_after{}, vtable_after{};
    if (!read_at(read,session,0x130,after) || std::memcmp(&before,&after,sizeof(before)) ||
        !read_at(read,image,0x1a10278,root_after) || root_after != root ||
        !read_at(read,root,0xa8,session_after) || session_after != session ||
        !read_at(read,session,0,vtable_after) || vtable_after != vtable) return out;
    out.session=session; out.host_value=before.host;
    out.record_count=before.count; out.record_ids=ids;
    out.status="stable_bounded_records_not_player_proof";
    return out;
}
} // namespace ep_session
