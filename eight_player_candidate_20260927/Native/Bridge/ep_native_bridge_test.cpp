#include "ep_native_bridge.h"

#include <cstdio>
#include <cstring>

struct Harness {
    UINT32 confirmed = 0;
    UINT32 created = 0;
    UINT32 removed = 0;
    UINT8 indexes[EP_SIDECAR_CAPACITY]{};
    UINT8 allocated[EP_SIDECAR_CAPACITY]{};
    UINT32 allocated_count = 0;
    UINT32 released_indexes = 0;
    UINT32 retained = 0;
    UINT32 released = 0;
    bool fail_confirm = false;
    bool fail_create = false;
    bool fail_remove = false;
};

static EP_BRIDGE_STATUS __cdecl confirm_cb(void* raw, UINT64, UINT64, UINT8 index) {
    auto* h = static_cast<Harness*>(raw);
    if (h->fail_confirm) return EP_BRIDGE_CALLBACK_REJECTED;
    h->confirmed++; h->indexes[index] = index; return EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl create_cb(void* raw, UINT64, UINT64, UINT8) {
    auto* h = static_cast<Harness*>(raw);
    if (h->fail_create) return EP_BRIDGE_CALLBACK_REJECTED;
    h->created++; return EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl remove_cb(void* raw, UINT64, UINT64, UINT8) {
    auto* h = static_cast<Harness*>(raw);
    if (h->fail_remove) return EP_BRIDGE_CALLBACK_REJECTED;
    h->removed++; return EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl retain_cb(void* raw) {
    static_cast<Harness*>(raw)->retained++; return EP_BRIDGE_OK;
}
static void __cdecl release_cb(void* raw) {
    static_cast<Harness*>(raw)->released++;
}
static EP_BRIDGE_STATUS __cdecl allocate_index_cb(
    void* raw, UINT64, UINT64, UINT8* out_index) {
    auto* h = static_cast<Harness*>(raw);
    for (UINT8 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        if (h->allocated[i]) continue;
        h->allocated[i] = 1;
        ++h->allocated_count;
        *out_index = i;
        return EP_BRIDGE_OK;
    }
    return EP_BRIDGE_NO_SLOT;
}
static EP_BRIDGE_STATUS __cdecl release_index_cb(
    void* raw, UINT64, UINT64, UINT8 index, UINT32) {
    auto* h = static_cast<Harness*>(raw);
    if (index >= EP_SIDECAR_CAPACITY || !h->allocated[index])
        return EP_BRIDGE_INDEX_REJECTED;
    h->allocated[index] = 0;
    ++h->released_indexes;
    return EP_BRIDGE_OK;
}

static bool check(bool ok, const char* what) {
    if (!ok) std::fprintf(stderr, "failed: %s\n", what);
    return ok;
}

int main() {
    BYTE site_bytes[] = {0x40, 0x55, 0x53, 0x56};
    EP_BRIDGE_SITE site{0, site_bytes, sizeof(site_bytes)};
    Harness harness{};
    EP_BRIDGE_CONFIG config{};
    config.steam_build = 25480438u;
    config.game_module = reinterpret_cast<HMODULE>(site_bytes);
    config.sites = &site;
    config.site_count = 1;
    config.owner = &harness;
    config.confirm_peer = confirm_cb;
    config.create_player = create_cb;
    config.remove_player = remove_cb;
    config.retain_owner = retain_cb;
    config.release_owner = release_cb;
    config.allocate_index = allocate_index_cb;
    config.release_index = release_index_cb;
    EP_NATIVE_BRIDGE bridge{};
    bool ok = true;
    ok &= check(ep_bridge_init(&bridge, &config) == EP_BRIDGE_OK, "init");
    ok &= check(ep_bridge_preflight(&bridge) == EP_BRIDGE_OK, "preflight");
    EP_BRIDGE_ADMISSION admissions[EP_SIDECAR_CAPACITY]{};
    // A failed create must call the compensating remove.  If remove also
    // fails, the slot and owner lease remain pinned until explicit retry.
    harness.fail_create = true;
    harness.fail_remove = true;
    EP_BRIDGE_ADMISSION failed{};
    ok &= check(ep_bridge_admit(&bridge, 90, 190, &failed) == EP_BRIDGE_CLEANUP_REQUIRED,
                "failed create pins cleanup");
    ok &= check(bridge.sidecar.active_count == 1 && bridge.cleanup_count == 1,
                "failed create keeps slot");
    ok &= check(harness.retained == 1 && harness.released == 0,
                "failed create keeps owner lease");
    EP_BRIDGE_ADMISSION duplicate_pending{};
    ok &= check(ep_bridge_admit(&bridge, 90, 190, &duplicate_pending) ==
                    EP_BRIDGE_CLEANUP_REQUIRED &&
                duplicate_pending.token.index == failed.token.index &&
                duplicate_pending.token.generation == failed.token.generation,
                "pending cleanup blocks duplicate admission");
    EP_BRIDGE_ADMISSION stale = failed;
    stale.peer_id++;
    ok &= check(ep_bridge_retry_cleanup(&bridge, stale) == EP_BRIDGE_INVALID_ARGUMENT,
                "stale retry identity rejected");
    ok &= check(bridge.cleanup_count == 1 && bridge.sidecar.active_count == 1,
                "stale retry leaves cleanup pinned");
    harness.fail_create = false;
    harness.fail_remove = false;
    ok &= check(ep_bridge_retry_cleanup(&bridge, failed) == EP_BRIDGE_OK,
                "retry cleanup");
    ok &= check(bridge.sidecar.active_count == 0 && bridge.cleanup_count == 0,
                "retry frees slot");
    ok &= check(harness.retained == harness.released,
                "retry releases owner lease");
    for (UINT8 i = 0; i < EP_SIDECAR_CAPACITY; ++i)
        ok &= check(ep_bridge_admit(&bridge, 100 + i, 200 + i, &admissions[i]) == EP_BRIDGE_OK, "admit");
    ok &= check(ep_bridge_admit(&bridge, 999, 999, &admissions[0]) == EP_BRIDGE_NO_SLOT, "ninth rejected");
    ok &= check(harness.confirmed == 9 && harness.created == 8, "callbacks");
    ok &= check(harness.retained == 10 && harness.released == 10, "owner lease admission");
    ok &= check(ep_bridge_depart(&bridge, admissions[4]) == EP_BRIDGE_OK, "depart");
    EP_BRIDGE_ADMISSION reconnect{};
    ok &= check(ep_bridge_reconnect(&bridge, 1004, 2004, &reconnect) == EP_BRIDGE_OK, "reconnect");
    ok &= check(reconnect.token.index == 4 && reconnect.token.generation != admissions[4].token.generation, "hole generation");
    for (UINT8 i = 0; i < EP_SIDECAR_CAPACITY; ++i) if (i != 4)
        ok &= check(ep_bridge_depart(&bridge, admissions[i]) == EP_BRIDGE_OK, "cleanup");
    ok &= check(ep_bridge_depart(&bridge, reconnect) == EP_BRIDGE_OK, "cleanup reconnect");
    ok &= check(harness.retained == harness.released, "owner lease balanced");
    ok &= check(harness.allocated_count == harness.released_indexes &&
                harness.allocated_count == 10, "authoritative index reservations balanced");
    ok &= check(ep_bridge_destroy(&bridge) == EP_BRIDGE_OK, "destroy");
    if (!ok) return 1;
    std::puts("ep_native_bridge_synthetic_passed");
    return 0;
}
