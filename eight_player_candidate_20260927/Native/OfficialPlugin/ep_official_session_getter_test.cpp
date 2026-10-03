#include "ep_official_session_getter.h"

#include <cassert>
#include <cstring>
#include <windows.h>

using ep_official_peer_reader::BuildIdentity;
using ep_official_session_getter::Result;

static BuildIdentity pinned() {
    BuildIdentity id{};
    id.steam_build = ep_official_peer_reader::kSteamBuild;
    id.exe_timestamp = ep_official_peer_reader::kExeTimestamp;
    id.exe_image_size = ep_official_peer_reader::kExeImageSize;
    id.game_timestamp = ep_official_peer_reader::kGameTimestamp;
    id.game_image_size = ep_official_peer_reader::kGameImageSize;
    id.exe_sha256 = ep_official_peer_reader::kExeSha256;
    id.game_sha256 = ep_official_peer_reader::kGameSha256;
    return id;
}

static bool safe_read(uintptr_t address, void* output, size_t size) {
    if (!output || !address || size == 0) return false;
    MEMORY_BASIC_INFORMATION mbi{};
    if (!VirtualQuery(reinterpret_cast<const void*>(address), &mbi, sizeof(mbi)) ||
        mbi.State != MEM_COMMIT || (mbi.Protect & 0xffu) == PAGE_NOACCESS ||
        address < reinterpret_cast<uintptr_t>(mbi.BaseAddress) ||
        size > mbi.RegionSize ||
        address + size > reinterpret_cast<uintptr_t>(mbi.BaseAddress) + mbi.RegionSize) {
        return false;
    }
    std::memcpy(output, reinterpret_cast<const void*>(address), size);
    return true;
}

int main() {
    constexpr SIZE_T image_size = 0x3500000;
    auto* image = static_cast<BYTE*>(
        VirtualAlloc(nullptr, image_size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    assert(image);
    auto* c_api = static_cast<uintptr_t*>(
        VirtualAlloc(nullptr, sizeof(uintptr_t) * 9, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    auto* network = static_cast<uintptr_t*>(
        VirtualAlloc(nullptr, sizeof(uintptr_t) * 2, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    auto* session = static_cast<uintptr_t*>(
        VirtualAlloc(nullptr, sizeof(uintptr_t), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    assert(c_api && network && session);

    *reinterpret_cast<WORD*>(image) = IMAGE_DOS_SIGNATURE;
    *reinterpret_cast<DWORD*>(image + 0x3c) = 0x100;
    *reinterpret_cast<DWORD*>(image + 0x100) = IMAGE_NT_SIGNATURE;
    *reinterpret_cast<WORD*>(image + 0x104) = IMAGE_FILE_MACHINE_AMD64;
    *reinterpret_cast<DWORD*>(image + 0x108) = ep_official_peer_reader::kGameTimestamp;
    *reinterpret_cast<WORD*>(image + 0x118) = IMAGE_NT_OPTIONAL_HDR64_MAGIC;
    *reinterpret_cast<DWORD*>(image + 0x150) = ep_official_peer_reader::kGameImageSize;

    std::memcpy(image + ep_official_session_getter::kGetterRva,
                ep_official_session_getter::kGetterBytes.data(),
                ep_official_session_getter::kGetterBytes.size());
    c_api[7] = reinterpret_cast<uintptr_t>(network);
    c_api[8] = reinterpret_cast<uintptr_t>(session);
    network[1] = reinterpret_cast<uintptr_t>(image) +
                ep_official_session_getter::kGetterRva;

    const auto executable = [](uintptr_t, size_t) { return true; };
    Result result = ep_official_session_getter::inspect(
        pinned(), reinterpret_cast<uintptr_t>(image), reinterpret_cast<uintptr_t>(c_api),
        safe_read, executable);
    assert(result.ready && result.status &&
           std::strcmp(result.status, "pinned_session_getter_not_peer_proof") == 0);

    network[1] += 1;
    result = ep_official_session_getter::inspect(
        pinned(), reinterpret_cast<uintptr_t>(image), reinterpret_cast<uintptr_t>(c_api),
        safe_read, executable);
    assert(!result.ready && std::strcmp(result.status, "unknown_getter_address") == 0);

    network[1] = reinterpret_cast<uintptr_t>(image) +
                 ep_official_session_getter::kGetterRva;
    c_api[7] = 0x1000;
    result = ep_official_session_getter::inspect(
        pinned(), reinterpret_cast<uintptr_t>(image), reinterpret_cast<uintptr_t>(c_api),
        safe_read, executable);
    assert(!result.ready && std::strcmp(result.status, "unread_api_table") == 0);

    c_api[7] = reinterpret_cast<uintptr_t>(network);
    auto wrong_build = pinned();
    wrong_build.steam_build += 1;
    result = ep_official_session_getter::inspect(
        wrong_build, reinterpret_cast<uintptr_t>(image), reinterpret_cast<uintptr_t>(c_api),
        safe_read, executable);
    assert(!result.ready && std::strcmp(result.status, "build_identity_mismatch") == 0);

    VirtualFree(session, 0, MEM_RELEASE);
    VirtualFree(network, 0, MEM_RELEASE);
    VirtualFree(c_api, 0, MEM_RELEASE);
    VirtualFree(image, 0, MEM_RELEASE);
    return 0;
}
