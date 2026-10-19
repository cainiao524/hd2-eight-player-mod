#include "ep_official_plugin.h"

#include <cassert>
#include <windows.h>

typedef void* (__cdecl *get_plugin_api_export)(unsigned);

int main() {
    HMODULE module = LoadLibraryW(L"ep_official_plugin.dll");
    assert(module != nullptr);
    const char* exports[] = {
        "get_plugin_api",
        "ep_official_plugin_runtime_preflight",
        "ep_official_plugin_runtime_install",
        "ep_official_plugin_runtime_remove",
        "ep_official_plugin_runtime_bind_native_callbacks",
        "ep_official_plugin_runtime_get_native_callbacks",
        "ep_official_plugin_runtime_unbind_native_callbacks",
        "ep_official_plugin_session_pointer",
        "ep_official_plugin_peer_count",
        "ep_official_plugin_update_ticks",
        "ep_official_plugin_last_snapshot_session",
        "ep_official_plugin_last_snapshot_count",
        "ep_replication_bridge_init",
        "ep_replication_bridge_destroy",
        "ep_resource_bridge_init",
        "ep_resource_bridge_configure",
        "ep_resource_bridge_destroy",
        "ep_pcr_init",
        "ep_pcr_destroy",
        "ep_pcr_admit",
        "ep_pcr_depart",
        "ep_pcr_validate",
        "ep_bridge_admit_at",
    };
    for (const char* name : exports) assert(GetProcAddress(module, name) != nullptr);
    auto get_api = reinterpret_cast<get_plugin_api_export>(GetProcAddress(module, "get_plugin_api"));
    assert(get_api != nullptr);
    assert(get_api(EP_PLUGIN_API_ID) != nullptr);
    assert(get_api(0xFFFFFFFFu) == nullptr);
    FreeLibrary(module);
    return 0;
}
