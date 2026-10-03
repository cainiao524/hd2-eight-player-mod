#include "ep_official_plugin.h"

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
