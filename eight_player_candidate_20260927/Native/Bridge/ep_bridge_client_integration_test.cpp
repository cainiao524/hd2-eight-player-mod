#include "ep_native_bridge.h"
#include "../ClientSidecar/ep_client_bridge_adapter.h"
#include <cstdio>

struct NativeFixture {
    bool reject_confirm = false;
    bool reject_create = false;
    bool reject_remove = false;
    unsigned confirms = 0, creates = 0, removes = 0, retains = 0, releases = 0;
    bool allocated[EP_SIDECAR_CAPACITY]{};
    UINT8 forced_index = 0xFF;
    EP_BRIDGE_STATUS forced_allocate_status = EP_BRIDGE_OK;
    bool fail_overflow_release = false;
    bool overflow_allocated[256]{};
    unsigned allocate_calls = 0, release_index_calls = 0;
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
static EP_BRIDGE_STATUS __cdecl allocate_index(
    void* owner, UINT64, UINT64, UINT8* out_index) {
    auto& f = *static_cast<NativeFixture*>(owner);
    ++f.allocate_calls;
    if (f.forced_index != 0xFF) {
        *out_index = f.forced_index;
        if (f.forced_index >= EP_SIDECAR_CAPACITY)
            f.overflow_allocated[f.forced_index] = true;
        else if (!f.allocated[f.forced_index])
            f.allocated[f.forced_index] = true;
        return f.forced_allocate_status;
    }
    for (UINT8 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        if (f.allocated[i]) continue;
        f.allocated[i] = true;
        *out_index = i;
        return EP_BRIDGE_OK;
    }
    return EP_BRIDGE_INDEX_REJECTED;
}
static EP_BRIDGE_STATUS __cdecl release_index(
    void* owner, UINT64, UINT64, UINT8 index, UINT32) {
    auto& f = *static_cast<NativeFixture*>(owner);
    ++f.release_index_calls;
    if (index >= EP_SIDECAR_CAPACITY) {
        if (f.fail_overflow_release || !f.overflow_allocated[index])
            return EP_BRIDGE_INDEX_REJECTED;
        f.overflow_allocated[index] = false;
        return EP_BRIDGE_OK;
    }
    if (!f.allocated[index]) return EP_BRIDGE_INDEX_REJECTED;
    f.allocated[index] = false;
    return EP_BRIDGE_OK;
}
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
    bool ok = check(ep_client_adapter_init(&client, &f, confirm, create, remove,
                    allocate_index, release_index, retain, release)
                    == EP_BRIDGE_OK, "adapter init");
    EP_BRIDGE_CONFIG config{25480438u, reinterpret_cast<HMODULE>(image), &site, 1, &client,
        ep_client_adapter_confirm, ep_client_adapter_create, ep_client_adapter_remove,
        ep_client_adapter_retain, ep_client_adapter_release,
        ep_client_adapter_allocate_index, ep_client_adapter_release_index};
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

    // A provider can hand back an authoritative index outside the local
    // client table.  The adapter keeps it for generation-zero compensation,
    // and the bridge must retry a failed release without creating a sidecar
    // record.
    f.forced_index = 16;
    f.forced_allocate_status = EP_BRIDGE_INDEX_REJECTED;
    EP_BRIDGE_ADMISSION overflow{};
    ok &= check(ep_bridge_admit(&bridge, 30, 40, &overflow) == EP_BRIDGE_INDEX_REJECTED,
                "out-of-range allocator result rejected after release");
    ok &= check(!f.overflow_allocated[16] && bridge.cleanup_count == 0 &&
                client.client.confirmed_count == 0,
                "out-of-range reservation compensated");
    f.forced_index = 17;
    f.fail_overflow_release = true;
    EP_BRIDGE_ADMISSION overflow_retry{};
    ok &= check(ep_bridge_admit(&bridge, 31, 41, &overflow_retry) ==
                    EP_BRIDGE_CLEANUP_REQUIRED &&
                overflow_retry.token.index == 17 &&
                    overflow_retry.token.generation == 0 &&
                    bridge.cleanup_count == 1,
                "out-of-range release failure retained");
    f.fail_overflow_release = false;
    ok &= check(ep_bridge_retry_cleanup(&bridge, overflow_retry) == EP_BRIDGE_OK &&
                !f.overflow_allocated[17] && bridge.cleanup_count == 0,
                "out-of-range release retry completes");
    f.forced_index = 0xFF;
    f.forced_allocate_status = EP_BRIDGE_OK;

    f.reject_confirm = false;
    EP_BRIDGE_ADMISSION admissions[EP_SIDECAR_CAPACITY]{};
    for (UINT8 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        ok &= check(ep_bridge_admit(&bridge, 100 + i, 200 + i, &admissions[i]) == EP_BRIDGE_OK,
                    "sixteen client admissions");
        ok &= check(admissions[i].token.index == i, "stable network index");
    }
    ok &= check(bridge.sidecar.active_count == EP_SIDECAR_CAPACITY &&
                client.client.confirmed_count == EP_SIDECAR_CAPACITY,
                "native and client registries hold sixteen players");
    const unsigned releases_before_collision = f.release_index_calls;
    f.forced_index = 0;
    EP_BRIDGE_ADMISSION collision{};
    ok &= check(ep_bridge_admit(&bridge, 500, 600, &collision) ==
                    EP_BRIDGE_INDEX_REJECTED &&
                f.release_index_calls == releases_before_collision &&
                client.client.confirmed_count == EP_SIDECAR_CAPACITY,
                "reserved index collision is not released");
    f.forced_index = 0xFF;
    ok &= check(ep_bridge_depart(&bridge, admissions[4]) == EP_BRIDGE_OK,
                "client departure keeps a hole");
    EP_BRIDGE_ADMISSION reconnected{};
    ok &= check(ep_bridge_reconnect(&bridge, 1004, 2004, &reconnected) == EP_BRIDGE_OK,
                "client reconnect");
    ok &= check(reconnected.token.index == 4 &&
                reconnected.token.generation != admissions[4].token.generation,
                "client reconnect generation");
    for (UINT8 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        if (i == 4) continue;
        ok &= check(ep_bridge_depart(&bridge, admissions[i]) == EP_BRIDGE_OK,
                    "client cleanup");
    }
    ok &= check(ep_bridge_depart(&bridge, reconnected) == EP_BRIDGE_OK,
                "client reconnect cleanup");
    ok &= check(bridge.sidecar.active_count == 0 && client.client.confirmed_count == 0,
                "both registries fully cleaned");
    ok &= check(f.retains == f.releases, "sixteen-player owner leases balanced");
    ok &= check(f.allocate_calls == f.release_index_calls &&
                f.allocate_calls == EP_SIDECAR_CAPACITY + 5 && f.release_index_calls == EP_SIDECAR_CAPACITY + 5,
                "authoritative index reservations balanced");
    ok &= check(ep_bridge_destroy(&bridge) == EP_BRIDGE_OK, "bridge destroy");
    ok &= check(ep_client_adapter_destroy(&client) == EP_BRIDGE_OK, "client destroy");
    if (!ok) return 1;
    std::puts("ep_bridge_client_integration_passed");
    return 0;
}
