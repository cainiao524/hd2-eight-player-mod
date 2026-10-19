#include "ep_player_creation_replication_adapter.h"
#include "../PlayerResource/ep_resource_bridge_adapter.h"

#include <cstdio>

#define CHECK(expression) do { if (!(expression)) { \
    std::fprintf(stderr, "line %d: %s\n", __LINE__, #expression); return false; \
} } while (0)

struct Harness {
    EP_RESOURCE_BRIDGE_ADAPTER resource{};
    EP_REPLICATION_BRIDGE replication{};
    EP_PLAYER_CREATION_REPLICATION_ADAPTER creation{};
    EP_CAPACITY_CONTRACT capacity{};
    BYTE image[2]{0x40, 0x55};
    EP_BRIDGE_SITE site{0, image, sizeof(image)};
    bool allocated[EP_RESOURCE_CAPACITY]{};
    bool native_confirmed[EP_RESOURCE_CAPACITY]{};
    bool native_created[EP_RESOURCE_CAPACITY]{};
    bool fail_stage[3]{};
    unsigned stages[3]{};
    unsigned component_calls = 0;
    unsigned component_cleanups = 0;
    int refs = 0;

    static EP_BRIDGE_STATUS __cdecl native_confirm(void* raw, UINT64, UINT64,
                                                   UINT8 index) {
        auto& h = *static_cast<Harness*>(raw);
        h.native_confirmed[index] = true;
        return EP_BRIDGE_OK;
    }
    static EP_BRIDGE_STATUS __cdecl native_create(void* raw, UINT64, UINT64,
                                                  UINT8 index) {
        auto& h = *static_cast<Harness*>(raw);
        if (!h.native_confirmed[index]) return EP_BRIDGE_CALLBACK_REJECTED;
        h.native_created[index] = true;
        return EP_BRIDGE_OK;
    }
    static EP_BRIDGE_STATUS __cdecl native_remove(void* raw, UINT64, UINT64,
                                                  UINT8 index) {
        auto& h = *static_cast<Harness*>(raw);
        h.native_confirmed[index] = false;
        h.native_created[index] = false;
        return EP_BRIDGE_OK;
    }
    static EP_BRIDGE_STATUS __cdecl native_allocate(void* raw, UINT64, UINT64,
                                                    UINT8* out) {
        auto& h = *static_cast<Harness*>(raw);
        for (UINT8 i = 0; i < EP_RESOURCE_CAPACITY; ++i) {
            if (h.allocated[i]) continue;
            h.allocated[i] = true;
            *out = i;
            return EP_BRIDGE_OK;
        }
        return EP_BRIDGE_NO_SLOT;
    }
    static EP_BRIDGE_STATUS __cdecl native_release(void* raw, UINT64, UINT64,
                                                    UINT8 index, UINT32) {
        auto& h = *static_cast<Harness*>(raw);
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
    static void __cdecl native_release_owner(void* raw) {
        --static_cast<Harness*>(raw)->refs;
    }
    static EP_RESOURCE_STATUS __cdecl metadata(
        void*, UINT64 peer, UINT64, UINT8 index, UINT64* hash,
        UINT32* ordinal, UINT16* component) {
        *hash = 0x100000u + peer;
        *ordinal = index;
        *component = 239;
        return EP_RS_OK;
    }
    static EP_RESOURCE_STATUS stage(void* raw, UINT8 index) {
        auto& h = *static_cast<Harness*>(raw);
        ++h.stages[index];
        return h.fail_stage[index] ? EP_RS_CALLBACK_FAILED : EP_RS_OK;
    }
    static EP_RESOURCE_STATUS __cdecl stage_first(void* raw, UINT64, UINT64,
                                                  UINT8, EP_RESOURCE_TOKEN) {
        return stage(raw, 0);
    }
    static EP_RESOURCE_STATUS __cdecl stage_second(void* raw, UINT64, UINT64,
                                                   UINT8, EP_RESOURCE_TOKEN) {
        return stage(raw, 1);
    }
    static EP_RESOURCE_STATUS __cdecl stage_third(void* raw, UINT64, UINT64,
                                                  UINT8, EP_RESOURCE_TOKEN) {
        return stage(raw, 2);
    }
    static EP_BRIDGE_STATUS __cdecl membership(
        void* raw, UINT64, UINT64, UINT8, UINT32* out_mask) {
        auto* resource = static_cast<EP_RESOURCE_BRIDGE_ADAPTER*>(raw);
        if (!resource || !resource->config.native_owner) return EP_BRIDGE_INVALID_CONTEXT;
        *out_mask = EP_CR_ARRAY_ALL;
        return EP_BRIDGE_OK;
    }
    static EP_CR_STATUS __cdecl replication_slot(
        void* raw, EP_CR_EVENT event, const EP_CR_SLOT* slot, UINT32) {
        auto& h = *static_cast<Harness*>(raw);
        if (!slot || slot->network_index >= EP_RESOURCE_CAPACITY)
            return EP_CR_INVALID_ARGUMENT;
        if (event == EP_CR_EVENT_CONFIRM &&
            !h.native_created[static_cast<UINT8>(slot->network_index)])
            return EP_CR_CALLBACK_REJECTED;
        return EP_CR_OK;
    }
    static EP_CR_STATUS __cdecl replication_owner(void*, EP_CR_EVENT, UINT64,
                                                  UINT32) { return EP_CR_OK; }

    static EP_PC_STATUS __cdecl pcr_retain(void* raw) {
        return native_retain(raw) == EP_BRIDGE_OK ? EP_PC_OK : EP_PC_CALLBACK_REJECTED;
    }
    static void __cdecl pcr_release(void* raw) { native_release_owner(raw); }
    static EP_PC_STATUS __cdecl resolve_resource(
        void*, UINT64 peer, UINT64 handle, UINT64 hash, UINT8 index,
        UINT32 generation, EP_PC_RESOURCE* out) {
        if (!out) return EP_PC_INVALID_ARGUMENT;
        out->network_index = index;
        out->generation = generation;
        out->peer_id = peer;
        out->resource_handle = handle;
        out->resource_hash = hash;
        return EP_PC_OK;
    }
    static EP_PC_STATUS __cdecl components(void* raw, const EP_PC_RESOURCE*) {
        ++static_cast<Harness*>(raw)->component_calls;
        return EP_PC_OK;
    }
    static EP_PC_STATUS __cdecl cleanup_components(void* raw,
                                                   const EP_PC_RESOURCE*) {
        ++static_cast<Harness*>(raw)->component_cleanups;
        return EP_PC_OK;
    }

    bool init() {
        const EP_RESOURCE_BRIDGE_CONFIG resource_config{
            EP_RESOURCE_BRIDGE_VERSION, sizeof(EP_RESOURCE_BRIDGE_CONFIG),
            EP_RESOURCE_BRIDGE_BUILD, 0x7000, this, native_confirm,
            native_create, native_remove, native_allocate, native_release,
            native_retain, native_release_owner, metadata,
            {EP_RESOURCE_BRIDGE_CALLBACK_VERSION,
             sizeof(EP_RESOURCE_BRIDGE_STAGE_CALLBACKS), stage_first,
             stage_second, stage_third}};
        CHECK(ep_resource_bridge_init(&resource, &resource_config) == EP_BRIDGE_OK);
        EP_BRIDGE_CONFIG downstream{};
        CHECK(ep_resource_bridge_configure(&resource,
            reinterpret_cast<HMODULE>(image), &site, 1, &downstream) == EP_BRIDGE_OK);
        capacity.version = EP_CAPACITY_CONTRACT_VERSION;
        capacity.build = EP_CAPACITY_BUILD;
        capacity.configured_max_players = 8;
        capacity.peer_capacity = capacity.roster_capacity = capacity.entity_capacity =
            capacity.resource_capacity = capacity.network_capacity =
            capacity.verified_capacity = 8;
        capacity.allow_join_in_progress = TRUE;
        capacity.require_same_mod_version = TRUE;
        capacity.quiescent = TRUE;
        downstream.capacity = &capacity;
        const EP_CR_CALLBACKS callbacks{
            sizeof(EP_CR_CALLBACKS), EP_CR_VERSION, this, replication_slot,
            replication_owner};
        CHECK(ep_replication_bridge_init(&replication, &downstream, &callbacks,
                                         membership, 0x7000, 1) == EP_BRIDGE_OK);
        CHECK(ep_bridge_preflight(&replication.admission) == EP_BRIDGE_OK);
        const EP_PCR_CONFIG config{
            EP_PCR_CALLBACK_VERSION, sizeof(EP_PCR_CONFIG), this, pcr_retain,
            pcr_release, resolve_resource, components, cleanup_components};
        CHECK(ep_pcr_init(&creation, &replication, &config) == EP_PC_OK);
        return true;
    }

    bool clean() {
        CHECK(ep_pcr_validate(&creation) == EP_PC_OK);
        CHECK(ep_pcr_destroy(&creation) == EP_PC_OK);
        CHECK(replication.replication.active_count == 0);
        CHECK(replication.admission.cleanup_count == 0);
        CHECK(ep_replication_bridge_destroy(&replication) == EP_BRIDGE_OK);
        CHECK(ep_resource_validate(&resource.resource) == EP_RS_OK);
        CHECK(ep_resource_bridge_destroy(&resource) == EP_BRIDGE_OK);
        CHECK(refs == 0);
        for (UINT8 i = 0; i < EP_RESOURCE_CAPACITY; ++i)
            CHECK(!allocated[i] && !native_confirmed[i] && !native_created[i]);
        return true;
    }
};

static bool full_resource_backed_admission() {
    Harness h;
    CHECK(h.init());
    EP_PC_TOKEN tokens[EP_PC_CAPACITY]{};
    for (UINT8 i = 0; i < EP_PC_CAPACITY; ++i) {
        CHECK(ep_pcr_admit(&h.creation, i, 100 + i, 200 + i, 0x100000 + 100 + i,
                           &tokens[i]) == EP_PC_OK);
        EP_RESOURCE_RECORD record{};
        CHECK(ep_resource_get(&h.resource.resource, i, &record) == EP_RS_OK &&
              record.state == EP_RS_CONFIRMED);
        CHECK(h.replication.replication.slots[i].state == EP_CR_CONFIRMED);
    }
    EP_PC_TOKEN rejected{};
    CHECK(ep_pcr_admit(&h.creation, 8, 999, 1999, 2999, &rejected) ==
          EP_PC_INDEX_REJECTED);
    for (UINT8 i = 0; i < EP_PC_CAPACITY; ++i)
        CHECK(ep_pcr_depart(&h.creation, tokens[i]) == EP_PC_OK);
    return h.clean();
}

static bool resource_stage_failure_unwinds_creation() {
    Harness h;
    CHECK(h.init());
    h.fail_stage[1] = true;
    EP_PC_TOKEN token{};
    CHECK(ep_pcr_admit(&h.creation, 0, 100, 200, 0x100064, &token) ==
          EP_PC_CALLBACK_REJECTED);
    EP_PC_SLOT slot{};
    EP_RESOURCE_RECORD resource{};
    CHECK(ep_pcr_get(&h.creation, 0, &slot) == EP_PC_OK &&
          slot.state == EP_PC_FREE);
    CHECK(ep_resource_get(&h.resource.resource, 0, &resource) == EP_RS_OK &&
          resource.state == EP_RS_FREE && resource.inflight == 0);
    CHECK(h.replication.admission.sidecar.active_count == 0);
    return h.clean();
}

int main() {
    if (!full_resource_backed_admission() ||
        !resource_stage_failure_unwinds_creation()) return 1;
    std::puts("ep_player_creation_resource_integration_passed");
    return 0;
}
