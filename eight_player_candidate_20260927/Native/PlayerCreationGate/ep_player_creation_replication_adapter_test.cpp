#include "ep_player_creation_replication_adapter.h"

#include <cstdio>

#define CHECK(expression) do { if (!(expression)) { \
    std::fprintf(stderr, "line %d: %s\n", __LINE__, #expression); return false; \
} } while (0)

struct Harness {
    EP_REPLICATION_BRIDGE replication{};
    EP_PLAYER_CREATION_REPLICATION_ADAPTER creation{};
    EP_CAPACITY_CONTRACT capacity{};
    BYTE image[2]{0x40, 0x55};
    EP_BRIDGE_SITE site{0, image, sizeof(image)};
    UINT64 allocated[EP_CR_CAPACITY]{};
    UINT64 native_peers[EP_CR_CAPACITY]{};
    UINT64 replicated[EP_CR_CAPACITY]{};
    bool created[EP_CR_CAPACITY]{};
    bool component_failure = false;
    bool cleanup_component_failure = false;
    int native_failure = 0; // 1=confirm, 2=create, 3=remove, 4=index release
    EP_CR_EVENT replication_failure = static_cast<EP_CR_EVENT>(0);
    bool rollback_failure = false;
    UINT8 forced_index = 0xFF;
    int refs = 0;
    unsigned components = 0;
    unsigned component_cleanups = 0;
    unsigned native_confirms = 0, native_creates = 0, native_removes = 0;
    unsigned replication_events = 0;

    static EP_BRIDGE_STATUS __cdecl retain(void* raw) {
        ++static_cast<Harness*>(raw)->refs;
        return EP_BRIDGE_OK;
    }
    static void __cdecl release(void* raw) { --static_cast<Harness*>(raw)->refs; }
    static EP_PC_STATUS __cdecl pcr_retain(void* raw) {
        return retain(raw) == EP_BRIDGE_OK ? EP_PC_OK : EP_PC_CALLBACK_REJECTED;
    }
    static void __cdecl pcr_release(void* raw) { release(raw); }

    static EP_BRIDGE_STATUS __cdecl allocate(void* raw, UINT64 peer, UINT64,
                                             UINT8* out) {
        auto& h = *static_cast<Harness*>(raw);
        for (UINT8 i = 0; i < EP_CR_CAPACITY; ++i) {
            if (h.forced_index != 0xFF && i != h.forced_index) continue;
            if (h.allocated[i]) continue;
            h.allocated[i] = peer;
            *out = i;
            return EP_BRIDGE_OK;
        }
        return EP_BRIDGE_NO_SLOT;
    }
    static EP_BRIDGE_STATUS __cdecl release_index(void* raw, UINT64 peer, UINT64,
                                                   UINT8 index, UINT32) {
        auto& h = *static_cast<Harness*>(raw);
        if (h.native_failure == 4) return EP_BRIDGE_CALLBACK_REJECTED;
        if (index >= EP_CR_CAPACITY || h.allocated[index] != peer ||
            h.native_peers[index] || h.created[index] || h.replicated[index])
            return EP_BRIDGE_INDEX_REJECTED;
        h.allocated[index] = 0;
        return EP_BRIDGE_OK;
    }
    static EP_BRIDGE_STATUS __cdecl confirm(void* raw, UINT64 peer, UINT64,
                                             UINT8 index) {
        auto& h = *static_cast<Harness*>(raw);
        ++h.native_confirms;
        h.native_peers[index] = peer;
        return h.native_failure == 1 ? EP_BRIDGE_CALLBACK_REJECTED : EP_BRIDGE_OK;
    }
    static EP_BRIDGE_STATUS __cdecl create(void* raw, UINT64, UINT64, UINT8 index) {
        auto& h = *static_cast<Harness*>(raw);
        ++h.native_creates;
        if (!h.native_peers[index]) return EP_BRIDGE_CALLBACK_REJECTED;
        h.created[index] = true;
        return h.native_failure == 2 ? EP_BRIDGE_CALLBACK_REJECTED : EP_BRIDGE_OK;
    }
    static EP_BRIDGE_STATUS __cdecl remove(void* raw, UINT64, UINT64, UINT8 index) {
        auto& h = *static_cast<Harness*>(raw);
        ++h.native_removes;
        if (h.native_failure == 3) return EP_BRIDGE_CALLBACK_REJECTED;
        h.native_peers[index] = 0;
        h.created[index] = false;
        return EP_BRIDGE_OK;
    }
    static EP_BRIDGE_STATUS __cdecl membership(void*, UINT64, UINT64, UINT8,
                                               UINT32* out_mask) {
        *out_mask = EP_CR_ARRAY_ALL;
        return EP_BRIDGE_OK;
    }
    static EP_CR_STATUS __cdecl replication_slot(
        void* raw, EP_CR_EVENT event, const EP_CR_SLOT* slot, UINT32) {
        auto& h = *static_cast<Harness*>(raw);
        ++h.replication_events;
        if (!slot || slot->network_index >= EP_CR_CAPACITY)
            return EP_CR_INVALID_ARGUMENT;
        const UINT8 index = static_cast<UINT8>(slot->network_index);
        if (event == EP_CR_EVENT_CONFIRM && !h.created[index])
            return EP_CR_CALLBACK_REJECTED;
        if (event == EP_CR_EVENT_APPEND) h.replicated[index] = slot->peer_id;
        if (event == EP_CR_EVENT_REMOVE || event == EP_CR_EVENT_ROLLBACK)
            h.replicated[index] = 0;
        if (event == h.replication_failure ||
            (event == EP_CR_EVENT_ROLLBACK && h.rollback_failure))
            return EP_CR_CALLBACK_REJECTED;
        return EP_CR_OK;
    }
    static EP_CR_STATUS __cdecl replication_owner(void*, EP_CR_EVENT, UINT64,
                                                  UINT32) { return EP_CR_OK; }

    static EP_PC_STATUS __cdecl resolve_resource(
        void*, UINT64 peer, UINT64 handle, UINT64 hash, UINT8 index,
        UINT32 generation, EP_PC_RESOURCE* out) {
        if (!out) return EP_PC_INVALID_ARGUMENT;
        out->network_index = index;
        out->generation = generation;
        out->peer_id = peer;
        out->resource_handle = handle;
        out->resource_hash = hash;
        out->opaque = 0xfeed0000u + index;
        return EP_PC_OK;
    }
    static EP_PC_STATUS __cdecl dispatch_components(void* raw,
                                                    const EP_PC_RESOURCE*) {
        auto& h = *static_cast<Harness*>(raw);
        ++h.components;
        return h.component_failure ? EP_PC_CALLBACK_REJECTED : EP_PC_OK;
    }
    static EP_PC_STATUS __cdecl cleanup_components(void* raw,
                                                   const EP_PC_RESOURCE*) {
        auto& h = *static_cast<Harness*>(raw);
        ++h.component_cleanups;
        return h.cleanup_component_failure ? EP_PC_CALLBACK_REJECTED : EP_PC_OK;
    }

    bool init() {
        capacity.version = EP_CAPACITY_CONTRACT_VERSION;
        capacity.build = EP_CAPACITY_BUILD;
        capacity.configured_max_players = 8;
        capacity.peer_capacity = capacity.roster_capacity = capacity.entity_capacity =
            capacity.resource_capacity = capacity.network_capacity =
            capacity.verified_capacity = 8;
        capacity.allow_join_in_progress = TRUE;
        capacity.require_same_mod_version = TRUE;
        capacity.quiescent = TRUE;
        const EP_BRIDGE_CONFIG downstream{
            EP_CR_BUILD, reinterpret_cast<HMODULE>(image), &site, 1, this,
            confirm, create, remove, retain, release, allocate, release_index,
            &capacity};
        const EP_CR_CALLBACKS callbacks{
            sizeof(EP_CR_CALLBACKS), EP_CR_VERSION, this, replication_slot,
            replication_owner};
        CHECK(ep_replication_bridge_init(&replication, &downstream, &callbacks,
                                         membership, 0x9000, 1) == EP_BRIDGE_OK);
        CHECK(ep_bridge_preflight(&replication.admission) == EP_BRIDGE_OK);
        const EP_PCR_CONFIG config{
            EP_PCR_CALLBACK_VERSION, sizeof(EP_PCR_CONFIG), this, pcr_retain,
            pcr_release, resolve_resource, dispatch_components, cleanup_components};
        CHECK(ep_pcr_init(&creation, &replication, &config) == EP_PC_OK);
        return true;
    }

    bool clean() {
        CHECK(ep_pcr_validate(&creation) == EP_PC_OK);
        CHECK(ep_pcr_destroy(&creation) == EP_PC_OK);
        CHECK(replication.admission.sidecar.active_count == 0);
        CHECK(replication.admission.cleanup_count == 0);
        CHECK(replication.replication.active_count == 0);
        CHECK(refs == 0);
        for (UINT8 i = 0; i < EP_CR_CAPACITY; ++i)
            CHECK(!allocated[i] && !native_peers[i] && !replicated[i] && !created[i]);
        CHECK(ep_replication_bridge_destroy(&replication) == EP_BRIDGE_OK);
        return true;
    }
};

static bool capacity_and_reconnect() {
    Harness h;
    CHECK(h.init());
    EP_PC_TOKEN tokens[EP_PC_CAPACITY]{};
    for (UINT8 i = 0; i < EP_PC_CAPACITY; ++i) {
        CHECK(ep_pcr_admit(&h.creation, i, 100 + i, 200 + i, 300 + i,
                           &tokens[i]) == EP_PC_OK);
        CHECK(h.replication.replication.slots[i].state == EP_CR_CONFIRMED);
    }
    EP_PC_TOKEN rejected{};
    CHECK(ep_pcr_admit(&h.creation, 8, 999, 1999, 2999, &rejected) ==
          EP_PC_INDEX_REJECTED);
    CHECK(ep_pcr_validate(&h.creation) == EP_PC_OK);
    const UINT32 old_generation = tokens[3].generation;
    CHECK(ep_pcr_depart(&h.creation, tokens[3]) == EP_PC_OK);
    CHECK(ep_pcr_admit(&h.creation, 3, 1003, 2003, 3003, &tokens[3]) == EP_PC_OK);
    CHECK(tokens[3].generation != old_generation);
    const EP_PC_STATUS stale_depart = ep_pcr_depart(&h.creation, rejected);
    CHECK(stale_depart == EP_PC_INVALID_ARGUMENT ||
          stale_depart == EP_PC_STALE_TOKEN);
    for (UINT8 i = 0; i < EP_PC_CAPACITY; ++i)
        CHECK(ep_pcr_depart(&h.creation, tokens[i]) == EP_PC_OK);
    return h.clean();
}

static bool callback_failure_rolls_back() {
    Harness h;
    CHECK(h.init());
    h.component_failure = true;
    EP_PC_TOKEN token{};
    CHECK(ep_pcr_admit(&h.creation, 0, 100, 200, 300, &token) ==
          EP_PC_CALLBACK_REJECTED);
    EP_PC_SLOT slot{};
    CHECK(ep_pcr_get(&h.creation, 0, &slot) == EP_PC_OK &&
          slot.state == EP_PC_FREE && h.replication.replication.active_count == 0);
    h.component_failure = false;
    return h.clean();
}

static bool index_mismatch_compensates() {
    Harness h;
    CHECK(h.init());
    h.forced_index = 1;
    EP_PC_TOKEN token{};
    CHECK(ep_pcr_admit(&h.creation, 0, 100, 200, 300, &token) ==
          EP_PC_CALLBACK_REJECTED);
    EP_PC_SLOT slot{};
    CHECK(ep_pcr_get(&h.creation, 0, &slot) == EP_PC_OK &&
          slot.state == EP_PC_FREE && h.replication.admission.sidecar.active_count == 0 &&
          h.replication.admission.cleanup_count == 0 && !h.allocated[1]);
    CHECK(h.native_confirms == 0 && h.native_creates == 0 &&
          h.native_removes == 0 && h.replication_events == 0);
    return h.clean();
}

static bool index_mismatch_release_retry() {
    Harness h;
    CHECK(h.init());
    h.forced_index = 1;
    h.native_failure = 4;
    EP_PC_TOKEN token{};
    CHECK(ep_pcr_admit(&h.creation, 0, 100, 200, 300, &token) ==
          EP_PC_ROLLBACK_FAILED);
    EP_PC_SLOT slot{};
    CHECK(ep_pcr_get(&h.creation, 0, &slot) == EP_PC_OK &&
          slot.state == EP_PC_REMOVING && slot.rollback_pending == 1 &&
          h.replication.admission.cleanup_count == 1 &&
          h.native_confirms == 0 && h.native_creates == 0 &&
          h.native_removes == 0 && h.replication_events == 0);
    h.native_failure = 0;
    CHECK(ep_pcr_depart(&h.creation, token) == EP_PC_OK);
    return h.clean();
}

static bool rollback_cleanup_cross_layer() {
    Harness h;
    CHECK(h.init());
    h.replication_failure = EP_CR_EVENT_APPEND;
    h.rollback_failure = true;
    EP_PC_TOKEN token{};
    CHECK(ep_pcr_admit(&h.creation, 0, 100, 200, 300, &token) ==
          EP_PC_ROLLBACK_FAILED);
    EP_PC_SLOT slot{};
    CHECK(ep_pcr_get(&h.creation, 0, &slot) == EP_PC_OK &&
          slot.state == EP_PC_REMOVING && slot.rollback_pending == 1 &&
          h.replication.admission.cleanup_count == 1);
    h.replication_failure = static_cast<EP_CR_EVENT>(0);
    h.rollback_failure = false;
    CHECK(ep_pcr_depart(&h.creation, token) == EP_PC_OK);
    return h.clean();
}

static bool departure_cleanup_retry() {
    Harness h;
    CHECK(h.init());
    EP_PC_TOKEN token{};
    CHECK(ep_pcr_admit(&h.creation, 0, 100, 200, 300, &token) == EP_PC_OK);
    h.native_failure = 3;
    CHECK(ep_pcr_depart(&h.creation, token) == EP_PC_CALLBACK_REJECTED);
    CHECK(h.replication.admission.cleanup_count == 1);
    h.native_failure = 0;
    CHECK(ep_pcr_depart(&h.creation, token) == EP_PC_OK);
    return h.clean();
}

int main() {
    if (!capacity_and_reconnect() || !callback_failure_rolls_back() ||
        !index_mismatch_compensates() || !index_mismatch_release_retry() ||
        !rollback_cleanup_cross_layer() || !departure_cleanup_retry()) return 1;
    std::puts("ep_player_creation_replication_adapter_integration_passed");
    return 0;
}
