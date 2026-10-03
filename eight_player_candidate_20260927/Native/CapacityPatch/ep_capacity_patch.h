#pragma once
#include <stdint.h>
#ifdef _WIN32
#define EP_CAP_EXPORT extern "C" __declspec(dllexport)
#else
#define EP_CAP_EXPORT extern "C"
#endif
using ep_cap_get_api_fn = void* (*)(unsigned);
struct ep_cap_plugin_api {
    const char* (*get_name)();
    void (*loaded)(ep_cap_get_api_fn);
    void (*unloaded)();
    void* (*start_reload)(ep_cap_get_api_fn);
    void (*finish_reload)(ep_cap_get_api_fn, void*);
    void (*setup_data_compiler)(ep_cap_get_api_fn);
    void (*shutdown_data_compiler)();
    void (*setup_resources)(ep_cap_get_api_fn);
    void (*shutdown_resources)();
    int (*can_refresh)(uint64_t);
    void (*refresh)(uint64_t,uint64_t);
    void (*setup_game)(ep_cap_get_api_fn);
    void (*update_game)(float);
    void (*shutdown_game)();
    void (*register_world)(void*);
    void (*unregister_world)(void*);
    void (*units_spawned)(void**,unsigned);
    void (*units_unspawned)(void**,unsigned);
    void (*debug_draw)(void*,void*);
    void* (*get_render_env)();
    void (*render)(void*);
    void* reserved[32];
};
constexpr unsigned EP_CAP_PLUGIN_API_ID=0;
EP_CAP_EXPORT void* get_plugin_api(unsigned);
EP_CAP_EXPORT unsigned ep_capacity_patch_state();
EP_CAP_EXPORT unsigned ep_capacity_patch_count();
