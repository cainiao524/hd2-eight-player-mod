#include "ep_official_plugin.h"

#include <atomic>

namespace {
std::atomic<uintptr_t> g_c_api{0};
std::atomic<uintptr_t> g_network_table{0};
std::atomic<uintptr_t> g_game_session_table{0};

const char* plugin_name() {
    return "eight_player_official_plugin_probe";
}

void loaded(ep_get_api_fn get_engine_api) {
    // The only operation performed at plugin load is a versioned API lookup.
    // No game function, memory write, hook, peer admission or player creation is called.
    if (get_engine_api != nullptr) {
        const auto c_api = reinterpret_cast<ep_script_api_prefix*>(get_engine_api(EP_C_API_ID));
        g_c_api.store(reinterpret_cast<uintptr_t>(c_api), std::memory_order_release);
        if (c_api != nullptr) {
            // Read the two public C API table pointers only; no table function is called.
            g_network_table.store(reinterpret_cast<uintptr_t>(c_api->slots[7]), std::memory_order_release);
            g_game_session_table.store(reinterpret_cast<uintptr_t>(c_api->slots[8]), std::memory_order_release);
        }
    }
}

void unloaded() {
    g_c_api.store(0, std::memory_order_release);
    g_network_table.store(0, std::memory_order_release);
    g_game_session_table.store(0, std::memory_order_release);
}

ep_plugin_api& api() {
    static ep_plugin_api value{};
    static bool initialized = false;
    if (!initialized) {
        value.get_name = &plugin_name;
        value.loaded = &loaded;
        value.unloaded = &unloaded;
        initialized = true;
    }
    return value;
}
}

EP_PLUGIN_EXPORT void* get_plugin_api(unsigned api_id) {
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
