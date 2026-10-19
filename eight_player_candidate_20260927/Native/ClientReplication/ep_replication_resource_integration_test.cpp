#include "ep_replication_bridge.h"
#include "../PlayerResource/ep_resource_bridge_adapter.h"

#include <cstdio>

#define CHECK(expression) do { if (!(expression)) { \
    std::fprintf(stderr, "line %d: %s\n", __LINE__, #expression); return false; \
} } while (0)

struct Harness {
    bool allocated[EP_RESOURCE_CAPACITY]{};
    bool native_confirmed[EP_RESOURCE_CAPACITY]{};
    bool native_created[EP_RESOURCE_CAPACITY]{};
    bool fail_stage[3]{};
    unsigned confirms = 0, creates = 0, removes = 0, releases = 0;
    unsigned stages[3]{};
    int refs = 0;
    EP_CR_EVENT fail_replication_event = static_cast<EP_CR_EVENT>(0);
};

static EP_BRIDGE_STATUS __cdecl native_confirm(void* raw, UINT64, UINT64, UINT8 index) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.confirms;
    h.native_confirmed[index] = true;
    return EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl native_create(void* raw, UINT64, UINT64, UINT8 index) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.creates;
    if (!h.native_confirmed[index]) return EP_BRIDGE_CALLBACK_REJECTED;
    h.native_created[index] = true;
    return EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl native_remove(void* raw, UINT64, UINT64, UINT8 index) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.removes;
    h.native_confirmed[index] = false;
    h.native_created[index] = false;
    return EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl native_allocate(void* raw, UINT64, UINT64, UINT8* out) {
    auto& h = *static_cast<Harness*>(raw);
    for (UINT8 i = 0; i < EP_RESOURCE_CAPACITY; ++i) {
        if (h.allocated[i]) continue;
        h.allocated[i] = true;
        *out = i;
        return EP_BRIDGE_OK;
    }
    return EP_BRIDGE_NO_SLOT;
}
static EP_BRIDGE_STATUS __cdecl native_release(void* raw, UINT64, UINT64, UINT8 index, UINT32) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.releases;
    if (index >= EP_RESOURCE_CAPACITY || !h.allocated[index] ||
        h.native_confirmed[index] || h.native_created[index])
        return EP_BRIDGE_INDEX_REJECTED;
    h.allocated[index] = false;
    return EP_BRIDGE_OK;
}
static EP_BRIDGE_STATUS __cdecl native_retain(void* raw) {
    ++static_cast<Harness*>(raw)->refs;
    return EP_BRIDGE_OK;
}
static void __cdecl native_release_owner(void* raw) { --static_cast<Harness*>(raw)->refs; }

static EP_RESOURCE_STATUS __cdecl metadata(
    void* raw, UINT64 peer, UINT64, UINT8 index, UINT64* hash,
    UINT32* ordinal, UINT16* component) {
    auto& h = *static_cast<Harness*>(raw);
    (void)h;
    *hash = 0x100000 + peer;
    *ordinal = index;
    *component = 239;
    return EP_RS_OK;
}
static EP_RESOURCE_STATUS stage_call(void* raw, UINT8 stage_index) {
    auto& h = *static_cast<Harness*>(raw);
    ++h.stages[stage_index];
    return h.fail_stage[stage_index] ? EP_RS_CALLBACK_FAILED : EP_RS_OK;
}
static EP_RESOURCE_STATUS __cdecl stage_first(void* raw, UINT64, UINT64, UINT8, EP_RESOURCE_TOKEN) {
    return stage_call(raw, 0);
}
static EP_RESOURCE_STATUS __cdecl stage_second(void* raw, UINT64, UINT64, UINT8, EP_RESOURCE_TOKEN) {
    return stage_call(raw, 1);
}
static EP_RESOURCE_STATUS __cdecl stage_third(void* raw, UINT64, UINT64, UINT8, EP_RESOURCE_TOKEN) {
    return stage_call(raw, 2);
}

static EP_BRIDGE_STATUS __cdecl membership(
    void* raw, UINT64, UINT64, UINT8, UINT32* out_mask) {
    auto* adapter = static_cast<EP_RESOURCE_BRIDGE_ADAPTER*>(raw);
    if (!adapter || !adapter->config.native_owner)
        return EP_BRIDGE_INVALID_CONTEXT;
    *out_mask = EP_CR_ARRAY_ALL;
    return EP_BRIDGE_OK;
}
static EP_CR_STATUS __cdecl replication_slot(
    void* raw, EP_CR_EVENT event, const EP_CR_SLOT* slot, UINT32) {
    auto& h = *static_cast<Harness*>(raw);
    if (!slot || slot->network_index >= EP_RESOURCE_CAPACITY) return EP_CR_INVALID_ARGUMENT;
    if (event == h.fail_replication_event) return EP_CR_CALLBACK_REJECTED;
    if (event == EP_CR_EVENT_CONFIRM && !h.native_created[slot->network_index])
        return EP_CR_CALLBACK_REJECTED;
    return EP_CR_OK;
}
static EP_CR_STATUS __cdecl replication_owner(void*, EP_CR_EVENT, UINT64, UINT32) {
    return EP_CR_OK;
}

static bool run() {
    Harness h{};
    EP_RESOURCE_BRIDGE_CONFIG resource_config{};
    resource_config.version = EP_RESOURCE_BRIDGE_VERSION;
    resource_config.size = sizeof(resource_config);
    resource_config.steam_build = EP_RESOURCE_BRIDGE_BUILD;
    resource_config.owner_key = 0x7000;
    resource_config.native_owner = &h;
    resource_config.native_confirm_peer = native_confirm;
    resource_config.native_create_player = native_create;
    resource_config.native_remove_player = native_remove;
    resource_config.native_allocate_index = native_allocate;
    resource_config.native_release_index = native_release;
    resource_config.native_retain_owner = native_retain;
    resource_config.native_release_owner = native_release_owner;
    resource_config.metadata = metadata;
    resource_config.stages = {EP_RESOURCE_BRIDGE_CALLBACK_VERSION,
                              sizeof(EP_RESOURCE_BRIDGE_STAGE_CALLBACKS),
                              stage_first, stage_second, stage_third};

    EP_RESOURCE_BRIDGE_ADAPTER resource{};
    CHECK(ep_resource_bridge_init(&resource, &resource_config) == EP_BRIDGE_OK);
    BYTE image[] = {0x40, 0x55};
    EP_BRIDGE_SITE site{0, image, sizeof(image)};
    EP_BRIDGE_CONFIG downstream{};
    CHECK(ep_resource_bridge_configure(&resource, reinterpret_cast<HMODULE>(image),
                                       &site, 1, &downstream) == EP_BRIDGE_OK);
    EP_CAPACITY_CONTRACT capacity{};
    capacity.version = EP_CAPACITY_CONTRACT_VERSION;
    capacity.build = EP_CAPACITY_BUILD;
    capacity.configured_max_players = 8;
    capacity.peer_capacity = capacity.roster_capacity = capacity.entity_capacity =
        capacity.resource_capacity = capacity.network_capacity = capacity.verified_capacity = 8;
    capacity.allow_join_in_progress = capacity.require_same_mod_version = TRUE;
    capacity.quiescent = TRUE;
    downstream.capacity = &capacity;

    EP_CR_CALLBACKS callbacks{sizeof(EP_CR_CALLBACKS), EP_CR_VERSION, &h,
                              replication_slot, replication_owner};
    EP_REPLICATION_BRIDGE bridge{};
    CHECK(ep_replication_bridge_init(&bridge, &downstream, &callbacks,
                                     membership, 0x7000, 1) == EP_BRIDGE_OK);
    CHECK(ep_bridge_preflight(&bridge.admission) == EP_BRIDGE_OK);

    EP_BRIDGE_ADMISSION admissions[8]{};
    for (UINT8 i = 0; i < 8; ++i) {
        CHECK(ep_bridge_admit(&bridge.admission, 100 + i, 200 + i, &admissions[i]) == EP_BRIDGE_OK);
        CHECK(admissions[i].token.index == i);
        EP_RESOURCE_RECORD record{};
        CHECK(ep_resource_get(&resource.resource, i, &record) == EP_RS_OK &&
              record.state == EP_RS_CONFIRMED);
        CHECK(bridge.replication.slots[i].state == EP_CR_CONFIRMED);
    }
    EP_BRIDGE_ADMISSION ninth{};
    CHECK(ep_bridge_admit(&bridge.admission, 999, 1999, &ninth) == EP_BRIDGE_CAPACITY_REJECTED);

    CHECK(ep_bridge_depart(&bridge.admission, admissions[4]) == EP_BRIDGE_OK);
    EP_BRIDGE_ADMISSION reconnect{};
    CHECK(ep_bridge_reconnect(&bridge.admission, 104, 204, &reconnect) == EP_BRIDGE_OK);
    CHECK(reconnect.token.index == 4 &&
          reconnect.token.generation != admissions[4].token.generation);
    admissions[4] = reconnect;

    CHECK(ep_bridge_depart(&bridge.admission, admissions[7]) == EP_BRIDGE_OK);
    h.fail_stage[1] = true;
    EP_BRIDGE_ADMISSION failed{};
    CHECK(ep_bridge_admit(&bridge.admission, 900, 1900, &failed) == EP_BRIDGE_CALLBACK_REJECTED);
    h.fail_stage[1] = false;
    EP_RESOURCE_RECORD rolled_back{};
    CHECK(ep_resource_get(&resource.resource, 7, &rolled_back) == EP_RS_OK &&
          rolled_back.state == EP_RS_FREE && rolled_back.inflight == 0);

    for (UINT8 i = 0; i < 8; ++i) {
        if (i == 7) continue;
        CHECK(ep_bridge_depart(&bridge.admission, admissions[i]) == EP_BRIDGE_OK);
    }
    CHECK(bridge.admission.sidecar.active_count == 0);
    CHECK(ep_resource_validate(&resource.resource) == EP_RS_OK);
    CHECK(ep_replication_bridge_destroy(&bridge) == EP_BRIDGE_OK);
    CHECK(ep_resource_bridge_destroy(&resource) == EP_BRIDGE_OK);
    CHECK(h.refs == 0);
    return true;
}

int main() {
    if (!run()) return 1;
    std::puts("ep_replication_resource_integration_passed");
    return 0;
}
