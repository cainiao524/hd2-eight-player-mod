#pragma once

#include <stdint.h>

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

EP_PLUGIN_EXPORT void* get_plugin_api(unsigned api_id);
EP_PLUGIN_EXPORT unsigned ep_official_plugin_probe_state();
EP_PLUGIN_EXPORT uintptr_t ep_official_plugin_c_api_pointer();
