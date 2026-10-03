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
    };
    for (const char* name : exports) assert(GetProcAddress(module, name) != nullptr);
    auto get_api = reinterpret_cast<get_plugin_api_export>(GetProcAddress(module, "get_plugin_api"));
    assert(get_api != nullptr);
    assert(get_api(EP_PLUGIN_API_ID) != nullptr);
    assert(get_api(0xFFFFFFFFu) == nullptr);
    FreeLibrary(module);
    return 0;
}
