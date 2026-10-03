#pragma once

#include <stdint.h>
#include <stddef.h>
#include "../SessionMembers/ep_consumer_executor.h"
#include "../SessionMembers/ep_consumer_native_callbacks.h"

#ifdef _WIN32
#define EP_PLUGIN_EXPORT extern "C" __declspec(dllexport)
#else
#define EP_PLUGIN_EXPORT extern "C"
#endif

// Stable Stingray plugin ABI surface used by the official get_plugin_api export.
// The function-pointer order matches Autodesk's public engine_plugin_api/plugin_api.h.
using ep_get_api_fn = void* (*)(unsigned api_id);
using ep_loaded_fn = void (*)(ep_get_api_fn get_engine_api);

struct ep_plugin_api {
    const char* (*get_name)();
    ep_loaded_fn loaded;
    void (*unloaded)();
    void* (*start_reload)(ep_get_api_fn);
    void (*finish_reload)(ep_get_api_fn, void*);
    void (*setup_data_compiler)(ep_get_api_fn);
    void (*shutdown_data_compiler)();
    void (*setup_resources)(ep_get_api_fn);
    void (*shutdown_resources)();
    int (*can_refresh)(uint64_t type);
    void (*refresh)(uint64_t type, uint64_t name);
    void (*setup_game)(ep_get_api_fn);
    void (*update_game)(float dt);
    void (*shutdown_game)();
    void (*register_world)(void* world);
    void (*unregister_world)(void* world);
    void (*units_spawned)(void** units, unsigned count);
    void (*units_unspawned)(void** units, unsigned count);
    void (*debug_draw)(void* world, void* stream);
    void* (*get_render_env)();
    void (*render)(void* arguments);
    void* reserved[32];
};

constexpr unsigned EP_PLUGIN_API_ID = 0;
constexpr unsigned EP_C_API_ID = 31;

// Public Stingray C API prefix: Network is slot 7 and GameSession slot 8.
// The exported pointer helpers only expose computed addresses. setup_game and
// update_game use the separate read-only getter gate before any function call.
struct ep_script_api_prefix {
    void* slots[9];
};
static_assert(offsetof(ep_script_api_prefix, slots[7]) == 0x38, "network slot drift");
static_assert(offsetof(ep_script_api_prefix, slots[8]) == 0x40, "game session slot drift");

EP_PLUGIN_EXPORT void* get_plugin_api(unsigned api_id);
EP_PLUGIN_EXPORT unsigned ep_official_plugin_probe_state();
EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_c_api_pointer();
EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_network_api_pointer();
EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_game_session_api_pointer();
EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_network_table_pointer();
EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_game_session_table_pointer();
EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_session_pointer();
EP_PLUGIN_EXPORT unsigned ep_official_plugin_peer_count();
EP_PLUGIN_EXPORT unsigned ep_official_plugin_update_ticks();
EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_last_snapshot_session();
EP_PLUGIN_EXPORT unsigned ep_official_plugin_last_snapshot_count();

// Read-only gate and reversible bridge for the fixed-build consumer candidate.
// Preflight never writes game memory. Install/remove remain disabled to callers
// until the caller supplies the versioned callback ABI and owns thread quiescence.
typedef struct EP_RUNTIME_PREFLIGHT {
    DWORD steam_build;
    DWORD entry_rva;
    DWORD expected_entry_size;
    DWORD expected_stolen_size;
    DWORD expected_code_size;
    BOOL build_ok;
    BOOL module_ok;
    BOOL entry_ok;
    BOOL target_ok;
    BOOL callback_ok;
    BOOL executor_abi_ok;
    BOOL ready;
} EP_RUNTIME_PREFLIGHT;

EP_PLUGIN_EXPORT BOOL __cdecl ep_official_plugin_runtime_preflight(
    DWORD steam_build, HMODULE game_module, DWORD entry_rva,
    const BYTE* expected_entry, SIZE_T expected_size,
    const EP_CONSUMER_CALLBACKS* callbacks, EP_RUNTIME_PREFLIGHT* out);
EP_PLUGIN_EXPORT BOOL __cdecl ep_official_plugin_runtime_install(
    DWORD steam_build, HMODULE game_module, DWORD entry_rva,
    const BYTE* expected_entry, SIZE_T expected_size,
    const EP_CONSUMER_CALLBACKS* callbacks, EP_CONSUMER_HOOK* out_hook);
EP_PLUGIN_EXPORT BOOL __cdecl ep_official_plugin_runtime_remove(EP_CONSUMER_HOOK* hook);
EP_PLUGIN_EXPORT EP_CONSUMER_NATIVE_STATUS __cdecl ep_official_plugin_runtime_bind_native_callbacks(
    unsigned long steam_build, HMODULE game_module,
    EP_CONSUMER_SIDECAR_RESOLVER sidecar_resolver);
EP_PLUGIN_EXPORT EP_CONSUMER_NATIVE_STATUS __cdecl ep_official_plugin_runtime_get_native_callbacks(
    EP_CONSUMER_CALLBACKS* out_callbacks);
EP_PLUGIN_EXPORT EP_CONSUMER_NATIVE_STATUS __cdecl ep_official_plugin_runtime_unbind_native_callbacks();
