#include "ep_native_bridge.h"
#include "../ClientSidecar/ep_client_bridge_adapter.h"
#include <cstdio>

struct NativeFixture {
    bool reject_confirm = false;
    bool reject_create = false;
    bool reject_remove = false;
    unsigned confirms = 0, creates = 0, removes = 0, retains = 0, releases = 0;
};
static EP_BRIDGE_STATUS __cdecl confirm(void* owner, UINT64, UINT64, UINT8) {
    auto& f = *static_cast<NativeFixture*>(owner);
    ++f.confirms;
    return f.reject_confirm ? EP_BRIDGE_CALLBACK_REJECTED : EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl create(void* owner, UINT64, UINT64, UINT8) {
    auto& f = *static_cast<NativeFixture*>(owner);
    ++f.creates;
    return f.reject_create ? EP_BRIDGE_CALLBACK_REJECTED : EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl remove(void* owner, UINT64, UINT64, UINT8) {
    auto& f = *static_cast<NativeFixture*>(owner);
    ++f.removes;
    return f.reject_remove ? EP_BRIDGE_CALLBACK_REJECTED : EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl retain(void* owner) {
    ++static_cast<NativeFixture*>(owner)->retains;
    return EP_BRIDGE_OK;
}
static void __cdecl release(void* owner) { ++static_cast<NativeFixture*>(owner)->releases; }
static bool check(bool passed, const char* label) {
    if (!passed) std::fprintf(stderr, "failed: %s\n", label);
    return passed;
}

int main() {
    NativeFixture f;
    EP_CLIENT_ADAPTER client{};
    EP_NATIVE_BRIDGE bridge{};
    BYTE image[] = {0x40, 0x55};
    EP_BRIDGE_SITE site{0, image, sizeof(image)};
    bool ok = check(ep_client_adapter_init(&client, &f, confirm, create, remove, retain, release)
                    == EP_BRIDGE_OK, "adapter init");
    EP_BRIDGE_CONFIG config{25480438u, reinterpret_cast<HMODULE>(image), &site, 1, &client,
        ep_client_adapter_confirm, ep_client_adapter_create, ep_client_adapter_remove,
        ep_client_adapter_retain, ep_client_adapter_release};
    ok &= check(ep_bridge_init(&bridge, &config) == EP_BRIDGE_OK, "bridge init");
    ok &= check(ep_bridge_preflight(&bridge) == EP_BRIDGE_OK, "preflight");

    f.reject_confirm = true;
    EP_BRIDGE_ADMISSION rejected{};
    ok &= check(ep_bridge_admit(&bridge, 10, 20, &rejected) == EP_BRIDGE_CALLBACK_REJECTED,
                "failed native confirm propagates after successful compensation");
    ok &= check(f.removes == 1 && f.creates == 0, "partial native confirm compensated without creating player");
    ok &= check(bridge.cleanup_count == 0 && bridge.sidecar.active_count == 0 &&
                client.client.confirmed_count == 0 && client.owner_refs == 0,
                "failed native confirm clears both registries and owner lease");
    ok &= check(f.retains == f.releases, "confirm failure balances native owner");
    if (!ok) return 1;
    ok &= check(ep_bridge_destroy(&bridge) == EP_BRIDGE_OK, "bridge destroy");
    ok &= check(ep_client_adapter_destroy(&client) == EP_BRIDGE_OK, "client destroy");
    if (!ok) return 1;
    std::puts("ep_bridge_client_integration_passed");
    return 0;
}
