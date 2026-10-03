#pragma once

#include "ep_official_peer_reader.h"
#include <limits>

namespace ep_official_session_getter {
constexpr uintptr_t kGetterRva = 0x34fdf0;
constexpr uintptr_t kGetterSlot = sizeof(uintptr_t);
constexpr std::array<uint8_t, 15> kGetterBytes{
    0x48, 0x8b, 0x05, 0x81, 0x04, 0x6c, 0x01,
    0x48, 0x8b, 0x80, 0xa8, 0, 0, 0, 0xc3};

struct Result {
    const char* status{"unverified"};
    uintptr_t network{};
    uintptr_t game_session{};
    uintptr_t function{};
    bool ready{};
};

template<class Read, class T>
bool at(Read& read, uintptr_t base, uintptr_t offset, T& out) {
    return base && offset <= UINTPTR_MAX - base &&
        sizeof(T) <= UINTPTR_MAX - (base + offset) &&
        read(base + offset, &out, sizeof(T));
}

// No engine function is called here. The supplied reader must copy exactly
// the requested bytes, never dereference an untrusted pointer directly.
template<class Read, class Executable>
Result inspect(const ep_official_peer_reader::BuildIdentity& build,
               uintptr_t image, uintptr_t c_api, Read read, Executable executable) {
    Result out{};
    if (!build.matches_pinned()) { out.status = "build_identity_mismatch"; return out; }
    if (!image || image > UINTPTR_MAX - build.game_image_size ||
        kGetterRva + kGetterBytes.size() > build.game_image_size) {
        out.status = "invalid_game_image"; return out;
    }
    uint16_t mz{}, machine{}, magic{};
    uint32_t pe_offset{}, signature{}, timestamp{}, image_size{};
    if (!at(read, image, 0, mz) || mz != 0x5a4d ||
        !at(read, image, 0x3c, pe_offset) || pe_offset > 0x1000 ||
        !at(read, image, pe_offset, signature) || signature != 0x4550 ||
        !at(read, image, pe_offset + 4, machine) || machine != 0x8664 ||
        !at(read, image, pe_offset + 8, timestamp) || timestamp != build.game_timestamp ||
        !at(read, image, pe_offset + 24, magic) || magic != 0x20b ||
        !at(read, image, pe_offset + 24 + 56, image_size) || image_size != build.game_image_size) {
        out.status = "unread_or_unknown_game_image"; return out;
    }
    std::array<uintptr_t, 9> prefix{}, repeat{};
    if (!at(read, c_api, 0, prefix) || !prefix[7] || !prefix[8]) {
        out.status = "unread_or_missing_c_api_tables"; return out;
    }
    uintptr_t function{}, repeat_function{}, session_prefix{};
    if (!at(read, prefix[7], kGetterSlot, function) ||
        !at(read, prefix[8], 0, session_prefix)) {
        out.status = "unread_api_table"; return out;
    }
    // Bytes alone are insufficient: an arbitrary function or copied wrapper
    // outside the pinned game.dll RVA must never be invoked.
    if (function != image + kGetterRva) {
        out.status = "unknown_getter_address"; return out;
    }
    std::array<uint8_t, kGetterBytes.size()> bytes{};
    if (!at(read, function, 0, bytes) || bytes != kGetterBytes ||
        !executable(function, bytes.size())) {
        out.status = "unread_or_unknown_getter_code"; return out;
    }
    if (!at(read, c_api, 0, repeat) || repeat != prefix ||
        !at(read, prefix[7], kGetterSlot, repeat_function) || repeat_function != function) {
        out.status = "unstable_api_tables"; return out;
    }
    out.network = prefix[7];
    out.game_session = prefix[8];
    out.function = function;
    out.ready = true;
    out.status = "pinned_session_getter_not_peer_proof";
    return out;
}
} // namespace ep_official_session_getter
