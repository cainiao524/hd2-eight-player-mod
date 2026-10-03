#include "ep_official_plugin.h"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <windows.h>

static void* runtime_resolver(void* owner) {
    return *reinterpret_cast<void**>(static_cast<unsigned char*>(owner) + 8);
}
static int runtime_mode(void*) { return 1; }
static UINT64 runtime_identity(void*) { return 1; }
static void* runtime_lookup(void* platform, UINT64 id, void* owner) {
    return platform && owner && id >= 2 && id <= 8 ? reinterpret_cast<void*>(id) : nullptr;
}
static int runtime_status(void* token) { return token ? 0 : 1; }

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

    constexpr DWORD rva = 0x1093590u;
    constexpr SIZE_T module_size = 0x10a0000u;
    const auto module = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, module_size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    const auto owner = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, 0x2000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    const auto platform = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, 0x2000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    const auto sidecar = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, 0x100, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    assert(module && owner && platform && sidecar);
    const unsigned char original[14] = {
        0xB8,0xFF,0xFF,0xFF,0xFF,0xC3,0x90,0x90,0x90,0x90,0x90,0x90,0x90,0x90};
    unsigned char* target = module + rva;
    std::memcpy(target, original, sizeof(original));
    *reinterpret_cast<void**>(owner) = platform;
    *reinterpret_cast<void**>(owner + 8) = sidecar;
    owner[0x1ba6] = 1;
    for (unsigned i = 0; i < 8; ++i)
        *reinterpret_cast<UINT64*>(sidecar + i * 8) = i + 1;
    *reinterpret_cast<UINT32*>(sidecar + 0x40) = 8;
    EP_CONSUMER_CALLBACKS callbacks{
        reinterpret_cast<void*>(&runtime_resolver),
        reinterpret_cast<void*>(&runtime_mode),
        reinterpret_cast<void*>(&runtime_identity),
        reinterpret_cast<void*>(&runtime_lookup),
        reinterpret_cast<void*>(&runtime_status)};
    EP_RUNTIME_PREFLIGHT report{};
    assert(ep_official_plugin_runtime_preflight(
        25480438u, reinterpret_cast<HMODULE>(module), rva, original,
        sizeof(original), &callbacks, &report));
    assert(report.ready && report.build_ok && report.module_ok && report.entry_ok &&
           report.target_ok && report.callback_ok && report.executor_abi_ok);
    EP_RUNTIME_PREFLIGHT rejected{};
    assert(!ep_official_plugin_runtime_preflight(
        25480438u, reinterpret_cast<HMODULE>(module), rva, original,
        sizeof(original), nullptr, &rejected));
    assert(!rejected.ready && !rejected.callback_ok);
    EP_CONSUMER_HOOK hook{};
    assert(ep_official_plugin_runtime_install(
        25480438u, reinterpret_cast<HMODULE>(module), rva, original,
        sizeof(original), &callbacks, &hook));
    auto consumer = reinterpret_cast<int (__cdecl*)(void*)>(target);
    assert(consumer(owner) == 1);
    *reinterpret_cast<UINT32*>(sidecar + 0x40) = 9;
    assert(consumer(owner) == -1);
    assert(ep_official_plugin_runtime_remove(&hook));
    assert(consumer(owner) == -1);
    target[0] ^= 1;
    assert(!ep_official_plugin_runtime_preflight(
        25480438u, reinterpret_cast<HMODULE>(module), rva, original,
        sizeof(original), &callbacks, &rejected));
    assert(!rejected.ready && !rejected.target_ok);
    VirtualFree(sidecar, 0, MEM_RELEASE);
    VirtualFree(platform, 0, MEM_RELEASE);
    VirtualFree(owner, 0, MEM_RELEASE);
    VirtualFree(module, 0, MEM_RELEASE);
    return 0;
}
