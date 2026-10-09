#include "ep_resource_bridge_adapter.h"

#include <cstdio>

struct Harness {
    bool fail_confirm = false;
    bool fail_create = false;
    bool fail_remove = false;
    bool fail_release_index = false;
    bool fail_stage[3]{};
    bool allocated[EP_RESOURCE_CAPACITY]{};
    UINT32 metadata_calls = 0;
    UINT32 stage_calls[3]{};
    UINT32 confirms = 0;
    UINT32 creates = 0;
    UINT32 removes = 0;
    UINT32 allocates = 0;
    UINT32 releases = 0;
    UINT32 retained = 0;
    UINT32 released_owner = 0;
};

static bool check(bool ok, const char* label) {
    if (!ok) std::fprintf(stderr, "failed: %s\n", label);
    return ok;
}

static EP_BRIDGE_STATUS __cdecl native_confirm(void* raw, UINT64, UINT64, UINT8) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.confirms;
    return h.fail_confirm ? EP_BRIDGE_CALLBACK_REJECTED : EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl native_create(void* raw, UINT64, UINT64, UINT8) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.creates;
    return h.fail_create ? EP_BRIDGE_CALLBACK_REJECTED : EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl native_remove(void* raw, UINT64, UINT64, UINT8) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.removes;
    return h.fail_remove ? EP_BRIDGE_CALLBACK_REJECTED : EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl native_allocate(void* raw, UINT64, UINT64, UINT8* out) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.allocates;
    for (UINT8 i = 0; i < EP_RESOURCE_CAPACITY; ++i) {
        if (h.allocated[i]) continue;
        h.allocated[i] = true;
        *out = i;
        return EP_BRIDGE_OK;
    }
    return EP_BRIDGE_NO_SLOT;
}
static EP_BRIDGE_STATUS __cdecl native_release_index(
    void* raw, UINT64, UINT64, UINT8 index, UINT32) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.releases;
    if (h.fail_release_index) return EP_BRIDGE_INDEX_RELEASE_FAILED;
    if (index >= EP_RESOURCE_CAPACITY || !h.allocated[index])
        return EP_BRIDGE_INDEX_REJECTED;
    h.allocated[index] = false;
    return EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl native_retain(void* raw) {
    ++static_cast<Harness*>(raw)->retained;
    return EP_BRIDGE_OK;
}
static void __cdecl native_release_owner(void* raw) {
    ++static_cast<Harness*>(raw)->released_owner;
}
static EP_RESOURCE_STATUS __cdecl metadata(
    void* raw, UINT64 peer, UINT64 handle, UINT8 index, UINT64* hash,
    UINT32* ordinal, UINT16* component) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.metadata_calls;
    *hash = 0xB000 + peer;
    *ordinal = index;
    *component = 239;
    (void)handle;
    return EP_RS_OK;
}
static EP_RESOURCE_STATUS __cdecl stage_first(
    void* raw, UINT64, UINT64, UINT8, EP_RESOURCE_TOKEN) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.stage_calls[0];
    return h.fail_stage[0] ? EP_RS_CALLBACK_FAILED : EP_RS_OK;
}
static EP_RESOURCE_STATUS __cdecl stage_second(
    void* raw, UINT64, UINT64, UINT8, EP_RESOURCE_TOKEN) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.stage_calls[1];
    return h.fail_stage[1] ? EP_RS_CALLBACK_FAILED : EP_RS_OK;
}
static EP_RESOURCE_STATUS __cdecl stage_third(
    void* raw, UINT64, UINT64, UINT8, EP_RESOURCE_TOKEN) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.stage_calls[2];
    return h.fail_stage[2] ? EP_RS_CALLBACK_FAILED : EP_RS_OK;
}

int main() {
    Harness h{};
    EP_RESOURCE_BRIDGE_CONFIG config{};
    config.version = EP_RESOURCE_BRIDGE_VERSION;
    config.size = sizeof(config);
    config.steam_build = EP_RESOURCE_BRIDGE_BUILD;
    config.owner_key = 0x7000;
    config.native_owner = &h;
    config.native_confirm_peer = native_confirm;
    config.native_create_player = native_create;
    config.native_remove_player = native_remove;
    config.native_allocate_index = native_allocate;
    config.native_release_index = native_release_index;
    config.native_retain_owner = native_retain;
    config.native_release_owner = native_release_owner;
    config.metadata = metadata;
    config.stages = {EP_RESOURCE_BRIDGE_CALLBACK_VERSION,
                     sizeof(EP_RESOURCE_BRIDGE_STAGE_CALLBACKS),
                     stage_first, stage_second, stage_third};

    EP_RESOURCE_BRIDGE_ADAPTER adapter{};
    bool ok = check(ep_resource_bridge_init(&adapter, &config) == EP_BRIDGE_OK,
                    "adapter init");
    BYTE image[] = {0x40, 0x55, 0x53, 0x56};
    EP_BRIDGE_SITE site{0, image, sizeof(image)};
    EP_BRIDGE_CONFIG bridge_config{};
    ok &= check(ep_resource_bridge_configure(&adapter,
                    reinterpret_cast<HMODULE>(image), &site, 1,
                    &bridge_config) == EP_BRIDGE_OK, "configure bridge");
    EP_NATIVE_BRIDGE bridge{};
    ok &= check(ep_bridge_init(&bridge, &bridge_config) == EP_BRIDGE_OK,
                "bridge init");
    ok &= check(ep_bridge_preflight(&bridge) == EP_BRIDGE_OK,
                "bridge preflight");

    EP_BRIDGE_ADMISSION admissions[EP_RESOURCE_CAPACITY]{};
    for (UINT8 i = 0; i < EP_RESOURCE_CAPACITY; ++i) {
        ok &= check(ep_bridge_admit(&bridge, 100 + i, 200 + i, &admissions[i]) == EP_BRIDGE_OK,
                    "eight resource-backed admissions");
        ok &= check(admissions[i].token.index == i, "authoritative resource index");
        EP_RESOURCE_RECORD record{};
        ok &= check(ep_resource_get(&adapter.resource, i, &record) == EP_RS_OK &&
                    record.state == EP_RS_CONFIRMED && record.component_ordinal == 239,
                    "resource published after three stages");
    }
    ok &= check(h.metadata_calls == EP_RESOURCE_CAPACITY && h.stage_calls[0] == EP_RESOURCE_CAPACITY &&
                h.stage_calls[1] == EP_RESOURCE_CAPACITY && h.stage_calls[2] == EP_RESOURCE_CAPACITY,
                "metadata and stage callbacks");
    ok &= check(ep_resource_validate(&adapter.resource) == EP_RS_OK,
                "resource invariant after eight");

    ok &= check(ep_bridge_depart(&bridge, admissions[4]) == EP_BRIDGE_OK,
                "departure releases resource");
    EP_RESOURCE_RECORD removed{};
    ok &= check(ep_resource_get(&adapter.resource, 4, &removed) == EP_RS_OK &&
                removed.state == EP_RS_FREE, "resource hole preserved");
    EP_BRIDGE_ADMISSION reconnect{};
    ok &= check(ep_bridge_reconnect(&bridge, 104, 204, &reconnect) == EP_BRIDGE_OK,
                "reconnect resource transaction");
    ok &= check(reconnect.token.index == 4 &&
                reconnect.token.generation != admissions[4].token.generation,
                "reconnect generation and index");

    ok &= check(ep_bridge_depart(&bridge, admissions[3]) == EP_BRIDGE_OK,
                "free failure-test index");
    h.fail_stage[1] = true;
    EP_BRIDGE_ADMISSION failed{};
    ok &= check(ep_bridge_admit(&bridge, 900, 1900, &failed) == EP_BRIDGE_CALLBACK_REJECTED,
                "stage failure rejects admission");
    h.fail_stage[1] = false;
    EP_RESOURCE_RECORD rolled_back{};
    ok &= check(ep_resource_get(&adapter.resource, 3, &rolled_back) == EP_RS_OK &&
                rolled_back.state == EP_RS_FREE, "stage failure rolls back resource");
    ok &= check(bridge.sidecar.active_count == EP_RESOURCE_CAPACITY - 1,
                "stage failure leaves no peer slot");

    for (UINT8 i = 0; i < EP_RESOURCE_CAPACITY; ++i) {
        if (i == 3) continue;
        const EP_BRIDGE_ADMISSION& admission = i == 4 ? reconnect : admissions[i];
        ok &= check(ep_bridge_depart(&bridge, admission) == EP_BRIDGE_OK,
                    "cleanup resource-backed admission");
    }
    ok &= check(bridge.sidecar.active_count == 0 &&
                ep_resource_validate(&adapter.resource) == EP_RS_OK &&
                h.retained == h.released_owner,
                "bridge and resource cleanup balanced");
    ok &= check(ep_bridge_destroy(&bridge) == EP_BRIDGE_OK, "bridge destroy");
    ok &= check(ep_resource_bridge_destroy(&adapter) == EP_BRIDGE_OK,
                "resource adapter destroy");
    if (!ok) return 1;
    std::puts("ep_resource_bridge_adapter_synthetic_passed");
    return 0;
}
