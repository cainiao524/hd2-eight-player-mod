#include "ep_official_plugin.h"

#include <cassert>

static ep_script_api_prefix fake_script{};
static void* stub_api(unsigned id) {
    return id == EP_C_API_ID ? &fake_script : nullptr;
}

int main() {
    auto* table = static_cast<ep_plugin_api*>(get_plugin_api(EP_PLUGIN_API_ID));
    assert(table != nullptr);
    assert(get_plugin_api(0xFFFFFFFFu) == nullptr);
    assert(table->get_name != nullptr);
    assert(table->loaded != nullptr);
    fake_script.slots[7] = reinterpret_cast<void*>(static_cast<uintptr_t>(0xABC00000));
    fake_script.slots[8] = reinterpret_cast<void*>(static_cast<uintptr_t>(0xDEF00000));
    table->loaded(&stub_api);
    assert(ep_official_plugin_probe_state() == 1u);
    assert(ep_official_plugin_c_api_pointer() == reinterpret_cast<uintptr_t>(&fake_script));
    assert(ep_official_plugin_network_table_pointer() == static_cast<uintptr_t>(0xABC00000));
    assert(ep_official_plugin_game_session_table_pointer() == static_cast<uintptr_t>(0xDEF00000));
    assert(ep_official_plugin_network_api_pointer() == reinterpret_cast<uintptr_t>(&fake_script) + 0x38);
    assert(ep_official_plugin_game_session_api_pointer() == reinterpret_cast<uintptr_t>(&fake_script) + 0x40);
    table->unloaded();
    assert(ep_official_plugin_probe_state() == 0u);
    assert(ep_official_plugin_network_table_pointer() == 0u);
    assert(ep_official_plugin_game_session_table_pointer() == 0u);
    return 0;
}
