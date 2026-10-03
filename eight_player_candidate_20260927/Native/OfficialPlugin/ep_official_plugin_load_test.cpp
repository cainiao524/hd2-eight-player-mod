#include "ep_official_plugin.h"

#include <cassert>
#include <windows.h>

typedef void* (__cdecl *get_plugin_api_export)(unsigned);

int main() {
    HMODULE module = LoadLibraryW(L"ep_official_plugin.dll");
    assert(module != nullptr);
    auto get_api = reinterpret_cast<get_plugin_api_export>(GetProcAddress(module, "get_plugin_api"));
    assert(get_api != nullptr);
    assert(get_api(EP_PLUGIN_API_ID) != nullptr);
    assert(get_api(0xFFFFFFFFu) == nullptr);
    FreeLibrary(module);
    return 0;
}
