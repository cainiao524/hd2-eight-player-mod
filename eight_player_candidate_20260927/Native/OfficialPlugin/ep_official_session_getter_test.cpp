#include "ep_official_session_getter.h"

#include <cassert>
#include <cstring>
#include <cstdio>
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
        (mbi.Protect & PAGE_GUARD) != 0 || size > UINTPTR_MAX - address ||
        address < reinterpret_cast<uintptr_t>(mbi.BaseAddress) ||
        size > mbi.RegionSize ||
        address + size > reinterpret_cast<uintptr_t>(mbi.BaseAddress) + mbi.RegionSize) {
        return false;
    }
    std::memcpy(output, reinterpret_cast<const void*>(address), size);
    return true;
}

int main() {
    constexpr SIZE_T image_size = ep_official_peer_reader::kGameImageSize;
    auto* game_image = static_cast<BYTE*>(
        VirtualAlloc(nullptr, image_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    auto* executable_image = static_cast<BYTE*>(
        VirtualAlloc(nullptr, image_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    assert(game_image && executable_image);
    auto* c_api = static_cast<uintptr_t*>(
        VirtualAlloc(nullptr, sizeof(uintptr_t) * 9, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    auto* network = static_cast<uintptr_t*>(
        VirtualAlloc(nullptr, sizeof(uintptr_t) * 2, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    auto* session = static_cast<uintptr_t*>(
        VirtualAlloc(nullptr, sizeof(uintptr_t), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    assert(c_api && network && session);

    auto init_image = [](BYTE* image, DWORD timestamp, DWORD image_size) {
        *reinterpret_cast<WORD*>(image) = IMAGE_DOS_SIGNATURE;
        *reinterpret_cast<DWORD*>(image + 0x3c) = 0x100;
        *reinterpret_cast<DWORD*>(image + 0x100) = IMAGE_NT_SIGNATURE;
        *reinterpret_cast<WORD*>(image + 0x104) = IMAGE_FILE_MACHINE_AMD64;
        *reinterpret_cast<DWORD*>(image + 0x108) = timestamp;
        *reinterpret_cast<WORD*>(image + 0x118) = IMAGE_NT_OPTIONAL_HDR64_MAGIC;
        *reinterpret_cast<DWORD*>(image + 0x150) = image_size;
    };
    init_image(game_image, ep_official_peer_reader::kGameTimestamp,
                ep_official_peer_reader::kGameImageSize);
    init_image(executable_image, ep_official_peer_reader::kExeTimestamp,
                ep_official_peer_reader::kExeImageSize);

    std::memcpy(executable_image + ep_official_session_getter::kGetterRva,
                ep_official_session_getter::kGetterBytes.data(),
                ep_official_session_getter::kGetterBytes.size());
    c_api[7] = reinterpret_cast<uintptr_t>(network);
    c_api[8] = reinterpret_cast<uintptr_t>(session);
    network[1] = reinterpret_cast<uintptr_t>(executable_image) +
                ep_official_session_getter::kGetterRva;

    const auto executable = [](uintptr_t, size_t) { return true; };
    Result result = ep_official_session_getter::inspect(
        pinned(), reinterpret_cast<uintptr_t>(game_image),
        reinterpret_cast<uintptr_t>(executable_image), reinterpret_cast<uintptr_t>(c_api),
        safe_read, executable);
    assert(result.ready && result.status &&
           std::strcmp(result.status, "pinned_session_getter_not_peer_proof") == 0);

    network[1] += 1;
    result = ep_official_session_getter::inspect(
        pinned(), reinterpret_cast<uintptr_t>(game_image),
        reinterpret_cast<uintptr_t>(executable_image), reinterpret_cast<uintptr_t>(c_api),
        safe_read, executable);
    assert(!result.ready && std::strcmp(result.status, "unknown_getter_address") == 0);

    network[1] = reinterpret_cast<uintptr_t>(executable_image) +
                 ep_official_session_getter::kGetterRva;
    c_api[7] = 0x1000;
    result = ep_official_session_getter::inspect(
        pinned(), reinterpret_cast<uintptr_t>(game_image),
        reinterpret_cast<uintptr_t>(executable_image), reinterpret_cast<uintptr_t>(c_api),
        safe_read, executable);
    assert(!result.ready && std::strcmp(result.status, "unread_api_table") == 0);

    c_api[7] = reinterpret_cast<uintptr_t>(network);
    auto wrong_build = pinned();
    wrong_build.steam_build += 1;
    result = ep_official_session_getter::inspect(
        wrong_build, reinterpret_cast<uintptr_t>(game_image),
        reinterpret_cast<uintptr_t>(executable_image), reinterpret_cast<uintptr_t>(c_api),
        safe_read, executable);
    assert(!result.ready && std::strcmp(result.status, "build_identity_mismatch") == 0);

    auto inspect = [&](auto reader, auto exec) {
        return ep_official_session_getter::inspect(pinned(),
            reinterpret_cast<uintptr_t>(game_image),
            reinterpret_cast<uintptr_t>(executable_image),
            reinterpret_cast<uintptr_t>(c_api), reader, exec);
    };
    auto rejected = [](const Result& got, const char* status) {
        assert(!got.ready && std::strcmp(got.status, status) == 0);
        assert(!got.network && !got.game_session && !got.function);
    };
    // The old wrong-module path must not become accepted even with identical bytes.
    std::memcpy(game_image + ep_official_session_getter::kGetterRva,
                ep_official_session_getter::kGetterBytes.data(),
                ep_official_session_getter::kGetterBytes.size());
    network[1] = reinterpret_cast<uintptr_t>(game_image) + ep_official_session_getter::kGetterRva;
    rejected(inspect(safe_read, executable), "unknown_getter_address");
    network[1] = reinterpret_cast<uintptr_t>(executable_image) + ep_official_session_getter::kGetterRva;

    rejected(ep_official_session_getter::inspect(pinned(),
        reinterpret_cast<uintptr_t>(executable_image), reinterpret_cast<uintptr_t>(game_image),
        reinterpret_cast<uintptr_t>(c_api), safe_read, executable), "unread_or_unknown_game_image");
    *reinterpret_cast<DWORD*>(executable_image + 0x108) += 1;
    rejected(inspect(safe_read, executable), "unread_or_unknown_executable_image");
    *reinterpret_cast<DWORD*>(executable_image + 0x108) -= 1;
    *reinterpret_cast<DWORD*>(game_image + 0x150) += 1;
    rejected(inspect(safe_read, executable), "unread_or_unknown_game_image");
    *reinterpret_cast<DWORD*>(game_image + 0x150) -= 1;
    rejected(inspect(safe_read, [](uintptr_t, size_t) { return false; }),
             "unread_or_unknown_getter_code");
    executable_image[ep_official_session_getter::kGetterRva] ^= 1;
    rejected(inspect(safe_read, executable), "unread_or_unknown_getter_code");
    executable_image[ep_official_session_getter::kGetterRva] ^= 1;
    for (unsigned mutation = 0; mutation < 4; ++mutation) {
        const uintptr_t address = mutation == 0 ? reinterpret_cast<uintptr_t>(c_api) :
            mutation == 1 ? reinterpret_cast<uintptr_t>(network + 1) :
            mutation == 2 ? reinterpret_cast<uintptr_t>(session) : network[1];
        unsigned reads = 0;
        auto changing_reader = [&](uintptr_t source, void* output, size_t size) {
            if (!safe_read(source, output, size)) return false;
            if (source == address && ++reads == 2) *static_cast<BYTE*>(output) ^= 1;
            return true;
        };
        rejected(inspect(changing_reader, executable), "unstable_api_tables");
    }
    DWORD prior{};
    assert(VirtualProtect(session, sizeof(uintptr_t), PAGE_READWRITE | PAGE_GUARD, &prior));
    rejected(inspect(safe_read, executable), "unread_api_table");
    assert(VirtualProtect(session, sizeof(uintptr_t), prior, &prior));
    assert(inspect(safe_read, executable).ready);
    puts("ep_official_session_getter_module_boundary_passed");

    VirtualFree(session, 0, MEM_RELEASE);
    VirtualFree(network, 0, MEM_RELEASE);
    VirtualFree(c_api, 0, MEM_RELEASE);
    VirtualFree(executable_image, 0, MEM_RELEASE);
    VirtualFree(game_image, 0, MEM_RELEASE);
    return 0;
}
