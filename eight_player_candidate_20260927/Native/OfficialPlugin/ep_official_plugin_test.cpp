#include "ep_official_plugin.h"

#include <cassert>

static void* stub_api(unsigned id) {
    return id == EP_C_API_ID ? reinterpret_cast<void*>(static_cast<uintptr_t>(0x12345000)) : nullptr;
}

int main() {
    auto* table = static_cast<ep_plugin_api*>(get_plugin_api(EP_PLUGIN_API_ID));
    assert(table != nullptr);
    assert(get_plugin_api(0xFFFFFFFFu) == nullptr);
    assert(table->get_name != nullptr);
    assert(table->loaded != nullptr);
    table->loaded(&stub_api);
    assert(ep_official_plugin_probe_state() == 1u);
    assert(ep_official_plugin_c_api_pointer() == static_cast<uintptr_t>(0x12345000));
    assert(ep_official_plugin_network_api_pointer() == static_cast<uintptr_t>(0x12345038));
    assert(ep_official_plugin_game_session_api_pointer() == static_cast<uintptr_t>(0x12345040));
    table->unloaded();
    assert(ep_official_plugin_probe_state() == 0u);
    return 0;
}
