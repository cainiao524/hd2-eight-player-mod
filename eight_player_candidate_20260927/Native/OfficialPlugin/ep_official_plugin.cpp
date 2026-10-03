#include "ep_official_plugin.h"
#include "../SessionObservation/ep_session_snapshot_windows.h"

#include <atomic>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <windows.h>

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
    if (get_engine_api != nullptr) {
        const auto c_api = reinterpret_cast<ep_script_api_prefix*>(get_engine_api(EP_C_API_ID));
        g_c_api.store(reinterpret_cast<uintptr_t>(c_api), std::memory_order_release);
        if (c_api != nullptr) {
            // Read the two public C API table pointers only; no table function is called.
            g_network_table.store(reinterpret_cast<uintptr_t>(c_api->slots[7]), std::memory_order_release);
            g_game_session_table.store(reinterpret_cast<uintptr_t>(c_api->slots[8]), std::memory_order_release);
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

void observe_snapshot() {
    const auto snapshot = ep_session::capture_current_process();
    const auto old_session = g_last_snapshot_session.exchange(snapshot.session_owner, std::memory_order_acq_rel);
    const auto old_count = g_last_snapshot_count.exchange(snapshot.peer_count, std::memory_order_acq_rel);
    if (old_session != snapshot.session_owner || old_count != snapshot.peer_count ||
        std::strcmp(snapshot.status, "observed_context_not_player_proof") != 0) {
        write_snapshot_log(snapshot);
    }
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
    const uintptr_t network = g_network_table.load(std::memory_order_acquire);
    const uintptr_t session_table = g_game_session_table.load(std::memory_order_acquire);
    if (network == 0 || session_table == 0) return;
    using game_session_fn = void* (*)();
    const auto game_session = *reinterpret_cast<game_session_fn*>(network + sizeof(void*));
    if (game_session == nullptr) return;
    void* session = game_session();
    g_session.store(reinterpret_cast<uintptr_t>(session), std::memory_order_release);
    write_session_log(reinterpret_cast<uintptr_t>(session));
    observe_snapshot();
}

void update_game(float) {
    // Poll only a bounded read-only getter path so a later mission/session can be
    // observed without creating a session or touching any replicated state.
    const unsigned tick = g_update_ticks.fetch_add(1, std::memory_order_relaxed) + 1;
    if ((tick % 60u) != 0u) return;
    const uintptr_t network = g_network_table.load(std::memory_order_acquire);
    const uintptr_t session_table = g_game_session_table.load(std::memory_order_acquire);
    if (network == 0 || session_table == 0) return;
    using game_session_fn = void* (*)();
    const auto game_session = *reinterpret_cast<game_session_fn*>(network + sizeof(void*));
    if (game_session == nullptr) return;
    void* session = game_session();
    const uintptr_t old_session = g_session.exchange(reinterpret_cast<uintptr_t>(session), std::memory_order_acq_rel);
    if (old_session != reinterpret_cast<uintptr_t>(session)) {
        write_session_log(reinterpret_cast<uintptr_t>(session));
    }
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
    if (mbi.RegionSize > UINTPTR_MAX - region_begin) return false;
    const uintptr_t region_end = region_begin + mbi.RegionSize;
    return begin >= region_begin && begin + size <= region_end;
}

bool safe_target_matches(const BYTE* target, const BYTE* expected, SIZE_T size) {
    if (!readable_bytes(target, size) || !expected) return false;
    __try {
        return std::memcmp(target, expected, size) == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
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
