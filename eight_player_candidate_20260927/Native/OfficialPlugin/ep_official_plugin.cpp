#include "ep_official_plugin.h"
#include "ep_official_session_getter.h"
#include "../SessionObservation/ep_session_snapshot_windows.h"

#include <atomic>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <windows.h>
#include <bcrypt.h>

#pragma comment(lib, "bcrypt.lib")

namespace {
std::atomic<uintptr_t> g_c_api{0};
std::atomic<uintptr_t> g_network_table{0};
std::atomic<uintptr_t> g_game_session_table{0};
std::atomic<unsigned> g_last_api_id{0xFFFFFFFFu};
std::atomic<uintptr_t> g_session{0};
std::atomic<unsigned> g_peer_count{0xFFFFFFFFu};
std::atomic<unsigned> g_update_ticks{0};
std::atomic<uintptr_t> g_last_snapshot_session{0};
std::atomic<unsigned> g_last_snapshot_count{0xFFFFFFFFu};

bool readable_bytes(const void* address, SIZE_T size);
bool executable_bytes(const void* address, SIZE_T size);

bool read_current(const void* address, void* output, SIZE_T size) {
    if (!readable_bytes(address, size) || !output) return false;
    __try {
        std::memcpy(output, address, size);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

void clear_observation_state() {
    g_session.store(0, std::memory_order_release);
    g_peer_count.store(0xFFFFFFFFu, std::memory_order_release);
    g_update_ticks.store(0, std::memory_order_release);
    g_last_snapshot_session.store(0, std::memory_order_release);
    g_last_snapshot_count.store(0xFFFFFFFFu, std::memory_order_release);
}

void observe_snapshot();

const char* plugin_name() {
    return "eight_player_official_plugin_probe";
}

void write_probe_log(const char* event, bool loaded_state) {
    char path[32768]{};
    DWORD n = GetEnvironmentVariableA("EP_OFFICIAL_PLUGIN_PROBE_LOG", path, sizeof(path));
    if (n == 0 || n >= sizeof(path)) {
        n = GetTempPathA(sizeof(path), path);
        if (n == 0 || n >= sizeof(path)) {
            return;
        }
        constexpr char suffix[] = "hd2_eight_player_plugin_runtime_probe.json";
        const size_t used = static_cast<size_t>(n);
        if (used + sizeof(suffix) > sizeof(path)) {
            return;
        }
        memcpy(path + used, suffix, sizeof(suffix));
    }
    const auto hex = [](uintptr_t value) {
        std::ostringstream out;
        out << "0x" << std::hex << value;
        return out.str();
    };
    std::ofstream out(path, std::ios::app);
    if (!out) {
        return;
    }
    out << "{\n"
        << "  \"schema\": \"hd2_official_plugin_runtime_probe_v1\",\n"
        << "  \"event\": \"" << event << "\",\n"
        << "  \"loaded\": " << (loaded_state ? "true" : "false") << ",\n"
        << "  \"last_api_id\": " << g_last_api_id.load(std::memory_order_acquire) << ",\n"
        << "  \"c_api\": \"" << hex(g_c_api.load(std::memory_order_acquire)) << "\",\n"
        << "  \"network_table\": \"" << hex(g_network_table.load(std::memory_order_acquire)) << "\",\n"
        << "  \"game_session_table\": \"" << hex(g_game_session_table.load(std::memory_order_acquire)) << "\",\n"
        << "  \"process_id\": " << GetCurrentProcessId() << ",\n"
        << "  \"memory_writes\": false,\n"
        << "  \"game_calls\": false\n"
        << "}\n";
}

void query_c_api(ep_get_api_fn get_engine_api, const char* event) {
    // The only operation performed at plugin load is a versioned API lookup.
    // No game function, memory write, hook, peer admission or player creation is called.
    g_last_api_id.store(EP_PLUGIN_API_ID, std::memory_order_release);
    g_c_api.store(0, std::memory_order_release);
    g_network_table.store(0, std::memory_order_release);
    g_game_session_table.store(0, std::memory_order_release);
    clear_observation_state();
    if (get_engine_api != nullptr &&
        executable_bytes(reinterpret_cast<const void*>(get_engine_api), 1)) {
        void* raw = get_engine_api(EP_C_API_ID);
        ep_script_api_prefix prefix{};
        if (raw != nullptr && read_current(raw, &prefix, sizeof(prefix)) &&
            prefix.slots[7] != nullptr && prefix.slots[8] != nullptr) {
            g_c_api.store(reinterpret_cast<uintptr_t>(raw), std::memory_order_release);
            g_network_table.store(reinterpret_cast<uintptr_t>(prefix.slots[7]), std::memory_order_release);
            g_game_session_table.store(reinterpret_cast<uintptr_t>(prefix.slots[8]), std::memory_order_release);
        }
    }
    write_probe_log(event, true);
}

void write_session_log(uintptr_t session) {
    char path[32768]{};
    DWORD n = GetEnvironmentVariableA("EP_OFFICIAL_PLUGIN_PROBE_LOG", path, sizeof(path));
    if (n == 0 || n >= sizeof(path)) {
        n = GetTempPathA(sizeof(path), path);
        if (n == 0 || n >= sizeof(path)) return;
        constexpr char suffix[] = "hd2_eight_player_plugin_runtime_probe.json";
        const size_t used = static_cast<size_t>(n);
        if (used + sizeof(suffix) > sizeof(path)) return;
        memcpy(path + used, suffix, sizeof(suffix));
    }
    std::ofstream out(path, std::ios::app);
    if (!out) return;
    out << "{\n"
        << "  \"schema\": \"hd2_official_plugin_runtime_probe_v1\",\n"
        << "  \"event\": \"session_observe\",\n"
        << "  \"session\": \"0x" << std::hex << session << "\",\n"
        << "  \"peer_state_read\": false,\n"
        << "  \"process_id\": " << GetCurrentProcessId() << ",\n"
        << "  \"memory_writes\": false,\n"
        << "  \"game_calls\": true\n"
        << "}\n";
}

void write_snapshot_log(const ep_session::Snapshot& snapshot) {
    char path[32768]{};
    DWORD n = GetEnvironmentVariableA("EP_OFFICIAL_PLUGIN_PROBE_LOG", path, sizeof(path));
    if (n == 0 || n >= sizeof(path)) {
        n = GetTempPathA(sizeof(path), path);
        if (n == 0 || n >= sizeof(path)) return;
        constexpr char suffix[] = "hd2_eight_player_plugin_runtime_probe.json";
        const size_t used = static_cast<size_t>(n);
        if (used + sizeof(suffix) > sizeof(path)) return;
        memcpy(path + used, suffix, sizeof(suffix));
    }
    std::ofstream out(path, std::ios::app);
    if (!out) return;
    out << "{\n"
        << "  \"schema\": \"hd2_official_plugin_session_snapshot_v2\",\n"
        << "  \"event\": \"session_snapshot\",\n"
        << "  \"status\": \"" << snapshot.status << "\",\n"
        << "  \"context\": \"0x" << std::hex << snapshot.context << "\",\n"
        << "  \"roster\": \"0x" << snapshot.roster << "\",\n"
        << "  \"game_state\": \"0x" << snapshot.game_state << "\",\n"
        << "  \"session_owner\": \"0x" << snapshot.session_owner << "\",\n"
        << "  \"local_peer\": \"0x" << snapshot.local_peer << "\",\n"
        << "  \"host_peer\": \"0x" << snapshot.host_peer << "\",\n"
        << "  \"mode\": " << std::dec << snapshot.mode << ",\n"
        << "  \"peer_count\": " << snapshot.peer_count << ",\n"
        << "  \"peers\": [";
    for (uint32_t i = 0; i < snapshot.peer_count && i < snapshot.peers.size(); ++i) {
        if (i) out << ",";
        out << "{\"ordinal\":" << snapshot.peers[i].ordinal
            << ",\"peer_id\":\"0x" << std::hex << snapshot.peers[i].peer_id
            << "\",\"network_index\":" << std::dec << snapshot.peers[i].network_index << "}";
    }
    out << "],\n"
        << "  \"roster_count\": " << snapshot.roster_count << ",\n"
        << "  \"documented_roster_slots\": 4,\n"
        << "  \"roster_slots_4_to_7_in_contract\": false,\n"
        << "  \"game_dll_context_offsets\": true,\n"
        << "  \"engine_functions_called\": false,\n"
        << "  \"memory_writes\": false,\n"
        << "  \"process_id\": " << std::dec << GetCurrentProcessId() << "\n"
        << "}\n";
}

void loaded(ep_get_api_fn get_engine_api) {
    // Some builds invoke loaded before the gameplay services are available.
    // Keep this query read-only and repeat it from setup_game below.
    query_c_api(get_engine_api, "loaded");
}

void setup_game(ep_get_api_fn get_engine_api) {
    // The public Stingray ABI calls setup_game after the game services are set up.
    // This is the first legal place to re-check C_API_ID without calling a table.
    query_c_api(get_engine_api, "setup_game");
    observe_snapshot();
}

void update_game(float) {
    // Poll only a bounded read-only getter path so a later mission/session can be
    // observed without creating a session or touching any replicated state.
    const unsigned tick = g_update_ticks.fetch_add(1, std::memory_order_relaxed) + 1;
    if ((tick % 60u) != 0u) return;
    observe_snapshot();
}

bool readable_bytes(const void* address, SIZE_T size) {
    if (!address || size == 0) return false;
    const uintptr_t begin = reinterpret_cast<uintptr_t>(address);
    if (size > UINTPTR_MAX - begin) return false;
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(address, &mbi, sizeof(mbi)) != sizeof(mbi) ||
        mbi.State != MEM_COMMIT) return false;
    const DWORD protect = mbi.Protect & 0xffu;
    if (protect == PAGE_NOACCESS || protect == PAGE_GUARD) return false;
    const uintptr_t region_begin = reinterpret_cast<uintptr_t>(mbi.BaseAddress);
    if (mbi.RegionSize > UINTPTR_MAX - region_begin ||
        size > UINTPTR_MAX - begin) return false;
    const uintptr_t region_end = region_begin + mbi.RegionSize;
    return begin >= region_begin && begin + size <= region_end;
}

bool executable_bytes(const void* address, SIZE_T size) {
    if (!readable_bytes(address, size)) return false;
    MEMORY_BASIC_INFORMATION mbi{};
    if (VirtualQuery(address, &mbi, sizeof(mbi)) != sizeof(mbi)) return false;
    const DWORD protect = mbi.Protect & 0xffu;
    return (protect & PAGE_EXECUTE) != 0 || (protect & PAGE_EXECUTE_READ) != 0 ||
           (protect & PAGE_EXECUTE_READWRITE) != 0 ||
           (protect & PAGE_EXECUTE_WRITECOPY) != 0;
}

bool safe_target_matches(const BYTE* target, const BYTE* expected, SIZE_T size) {
    if (!readable_bytes(target, size) || !expected) return false;
    __try {
        return std::memcmp(target, expected, size) == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool file_sha256(HMODULE module, std::array<uint8_t, 32>& digest) {
    wchar_t path[32768]{};
    const DWORD length = GetModuleFileNameW(module, path, static_cast<DWORD>(std::size(path)));
    if (length == 0 || length >= std::size(path)) return false;
    HANDLE file = CreateFileW(path, GENERIC_READ,
                              FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                              nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    BCRYPT_HASH_HANDLE hash = nullptr;
    bool ok = BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) == 0 &&
              BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) == 0;
    std::array<BYTE, 1 << 16> buffer{};
    DWORD got = 0;
    while (ok) {
        if (!ReadFile(file, buffer.data(), static_cast<DWORD>(buffer.size()), &got, nullptr)) {
            ok = false;
            break;
        }
        if (got == 0) break;
        ok = BCryptHashData(hash, buffer.data(), got, 0) == 0;
    }
    if (ok) {
        ok = BCryptFinishHash(hash, digest.data(), static_cast<ULONG>(digest.size()), 0) == 0;
    }
    if (hash) BCryptDestroyHash(hash);
    if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
    CloseHandle(file);
    return ok;
}

bool runtime_build_identity(ep_official_peer_reader::BuildIdentity& identity) {
    HMODULE game = GetModuleHandleA("game.dll");
    HMODULE exe = GetModuleHandleA(nullptr);
    if (!game || !exe) return false;
    auto read_pe = [](HMODULE module, DWORD expected_timestamp, DWORD expected_size) {
        const auto base = reinterpret_cast<const BYTE*>(module);
        IMAGE_DOS_HEADER dos{};
        IMAGE_NT_HEADERS64 nt{};
        if (!read_current(base, &dos, sizeof(dos)) || dos.e_magic != IMAGE_DOS_SIGNATURE ||
            dos.e_lfanew < 0 || static_cast<size_t>(dos.e_lfanew) > 0x1000 ||
            !read_current(base + dos.e_lfanew, &nt, sizeof(nt)) ||
            nt.Signature != IMAGE_NT_SIGNATURE ||
            nt.FileHeader.Machine != IMAGE_FILE_MACHINE_AMD64 ||
            nt.FileHeader.TimeDateStamp != expected_timestamp ||
            nt.OptionalHeader.SizeOfImage != expected_size) {
            return false;
        }
        return true;
    };
    if (!read_pe(game, ep_official_peer_reader::kGameTimestamp,
                 ep_official_peer_reader::kGameImageSize) ||
        !read_pe(exe, ep_official_peer_reader::kExeTimestamp,
                 ep_official_peer_reader::kExeImageSize)) {
        return false;
    }
    identity.steam_build = ep_official_peer_reader::kSteamBuild;
    identity.exe_timestamp = ep_official_peer_reader::kExeTimestamp;
    identity.exe_image_size = ep_official_peer_reader::kExeImageSize;
    identity.game_timestamp = ep_official_peer_reader::kGameTimestamp;
    identity.game_image_size = ep_official_peer_reader::kGameImageSize;
    return file_sha256(exe, identity.exe_sha256) &&
           file_sha256(game, identity.game_sha256);
}

void observe_snapshot() {
    ep_official_peer_reader::BuildIdentity identity{};
    const uintptr_t c_api = g_c_api.load(std::memory_order_acquire);
    const uintptr_t image = reinterpret_cast<uintptr_t>(GetModuleHandleA("game.dll"));
    if (!runtime_build_identity(identity) || c_api == 0 || image == 0) return;
    const auto read = [](uintptr_t address, void* output, size_t size) {
        return read_current(reinterpret_cast<const void*>(address), output, size);
    };
    const auto executable = [](uintptr_t address, size_t size) {
        return executable_bytes(reinterpret_cast<const void*>(address), size);
    };
    const auto getter = ep_official_session_getter::inspect(
        identity, image, c_api, read, executable);
    if (!getter.ready) return;
    using game_session_fn = void* (*)();
    game_session_fn function{};
    if (!read_current(reinterpret_cast<const void*>(getter.network + sizeof(void*)),
                      &function, sizeof(function)) ||
        !function) {
        return;
    }
    void* session = function();
    const uintptr_t old_session =
        g_session.exchange(reinterpret_cast<uintptr_t>(session), std::memory_order_acq_rel);
    if (old_session != reinterpret_cast<uintptr_t>(session)) {
        write_session_log(reinterpret_cast<uintptr_t>(session));
    }
    const auto snapshot = ep_session::capture_current_process();
    g_peer_count.store(snapshot.peer_count, std::memory_order_release);
    const auto old = g_last_snapshot_session.exchange(
        snapshot.session_owner, std::memory_order_acq_rel);
    const auto old_count = g_last_snapshot_count.exchange(
        snapshot.peer_count, std::memory_order_acq_rel);
    if (old != snapshot.session_owner || old_count != snapshot.peer_count ||
        std::strcmp(snapshot.status, "observed_context_not_player_proof") != 0) {
        write_snapshot_log(snapshot);
    }
}

bool callbacks_complete(const EP_CONSUMER_CALLBACKS* callbacks) {
    return callbacks != nullptr && callbacks->resolver != nullptr &&
           callbacks->mode != nullptr && callbacks->identity != nullptr &&
           callbacks->lookup != nullptr && callbacks->status != nullptr;
}

void unloaded() {
    write_probe_log("unloaded", false);
    g_c_api.store(0, std::memory_order_release);
    g_network_table.store(0, std::memory_order_release);
    g_game_session_table.store(0, std::memory_order_release);
    g_last_api_id.store(0xFFFFFFFFu, std::memory_order_release);
    clear_observation_state();
}

void shutdown_game() {
    unloaded();
}

ep_plugin_api& api() {
    static ep_plugin_api value{};
    static bool initialized = false;
    if (!initialized) {
        value.get_name = &plugin_name;
        value.loaded = &loaded;
        value.unloaded = &unloaded;
        value.setup_game = &setup_game;
        value.update_game = &update_game;
        value.shutdown_game = &shutdown_game;
        initialized = true;
    }
    return value;
}
}

EP_PLUGIN_EXPORT void* get_plugin_api(unsigned api_id) {
    g_last_api_id.store(api_id, std::memory_order_release);
    write_probe_log("api_query", false);
    if (api_id == EP_PLUGIN_API_ID) {
        return &api();
    }
    return nullptr;
}

EP_PLUGIN_EXPORT unsigned ep_official_plugin_probe_state() {
    return g_c_api.load(std::memory_order_acquire) != 0 ? 1u : 0u;
}

EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_c_api_pointer() {
    return g_c_api.load(std::memory_order_acquire);
}

EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_network_api_pointer() {
    const auto base = g_c_api.load(std::memory_order_acquire);
    return base == 0 ? 0 : base + offsetof(ep_script_api_prefix, slots[7]);
}

EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_game_session_api_pointer() {
    const auto base = g_c_api.load(std::memory_order_acquire);
    return base == 0 ? 0 : base + offsetof(ep_script_api_prefix, slots[8]);
}

EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_network_table_pointer() {
    return g_network_table.load(std::memory_order_acquire);
}

EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_game_session_table_pointer() {
    return g_game_session_table.load(std::memory_order_acquire);
}

EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_session_pointer() {
    return g_session.load(std::memory_order_acquire);
}

EP_PLUGIN_EXPORT unsigned ep_official_plugin_peer_count() {
    return g_peer_count.load(std::memory_order_acquire);
}

EP_PLUGIN_EXPORT unsigned ep_official_plugin_update_ticks() {
    return g_update_ticks.load(std::memory_order_acquire);
}

EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_last_snapshot_session() {
    return g_last_snapshot_session.load(std::memory_order_acquire);
}

EP_PLUGIN_EXPORT unsigned ep_official_plugin_last_snapshot_count() {
    return g_last_snapshot_count.load(std::memory_order_acquire);
}

EP_PLUGIN_EXPORT BOOL __cdecl ep_official_plugin_runtime_preflight(
    DWORD steam_build, HMODULE game_module, DWORD entry_rva,
    const BYTE* expected_entry, SIZE_T expected_size,
    const EP_CONSUMER_CALLBACKS* callbacks, EP_RUNTIME_PREFLIGHT* out) {
    if (!out) return FALSE;
    std::memset(out, 0, sizeof(*out));
    out->steam_build = steam_build;
    out->entry_rva = entry_rva;
    out->expected_entry_size = expected_size > UINT32_MAX ? 0 : static_cast<DWORD>(expected_size);
    out->expected_stolen_size = ep_consumer_stolen_size();
    out->expected_code_size = ep_consumer_code_size();
    out->build_ok = steam_build == ep_consumer_expected_build();
    out->module_ok = game_module != nullptr;
    out->entry_ok = entry_rva == ep_consumer_expected_entry_rva();
    out->target_ok = out->module_ok && out->entry_ok &&
        expected_size == ep_consumer_stolen_size() &&
        expected_entry != nullptr &&
        safe_target_matches(reinterpret_cast<const BYTE*>(game_module) + entry_rva,
                            expected_entry, expected_size);
    out->callback_ok = callbacks_complete(callbacks);
    out->executor_abi_ok = ep_consumer_expected_build() == 25480438u &&
        ep_consumer_expected_entry_rva() == 0x1093590u &&
        ep_consumer_code_size() == 270u && ep_consumer_stolen_size() == 14u;
    out->ready = out->build_ok && out->module_ok && out->entry_ok &&
        out->target_ok && out->callback_ok && out->executor_abi_ok;
    return out->ready;
}

EP_PLUGIN_EXPORT BOOL __cdecl ep_official_plugin_runtime_install(
    DWORD steam_build, HMODULE game_module, DWORD entry_rva,
    const BYTE* expected_entry, SIZE_T expected_size,
    const EP_CONSUMER_CALLBACKS* callbacks, EP_CONSUMER_HOOK* out_hook) {
    EP_RUNTIME_PREFLIGHT report{};
    if (!out_hook || !ep_official_plugin_runtime_preflight(
            steam_build, game_module, entry_rva, expected_entry, expected_size,
            callbacks, &report)) return FALSE;
    return ep_consumer_install(steam_build, game_module, entry_rva,
                               expected_entry, expected_size, callbacks, out_hook);
}

EP_PLUGIN_EXPORT BOOL __cdecl ep_official_plugin_runtime_remove(EP_CONSUMER_HOOK* hook) {
    return ep_consumer_remove(hook);
}

EP_PLUGIN_EXPORT EP_CONSUMER_NATIVE_STATUS __cdecl
ep_official_plugin_runtime_bind_native_callbacks(
    unsigned long steam_build, HMODULE game_module,
    EP_CONSUMER_SIDECAR_RESOLVER sidecar_resolver) {
    return ep_consumer_native_bind(steam_build, game_module, sidecar_resolver);
}

EP_PLUGIN_EXPORT EP_CONSUMER_NATIVE_STATUS __cdecl
ep_official_plugin_runtime_get_native_callbacks(EP_CONSUMER_CALLBACKS* out_callbacks) {
    return ep_consumer_native_get_callbacks(out_callbacks);
}

EP_PLUGIN_EXPORT EP_CONSUMER_NATIVE_STATUS __cdecl
ep_official_plugin_runtime_unbind_native_callbacks() {
    return ep_consumer_native_unbind();
}
