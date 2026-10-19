#include "ep_replication_bridge.h"
#include "../ClientSidecar/ep_client_bridge_adapter.h"

#include <cstdio>
#include <stdexcept>

#define CHECK(expression) do { if (!(expression)) { \
    std::fprintf(stderr, "line %d: %s\n", __LINE__, #expression); return false; \
} } while (0)

struct Fixture {
    EP_CLIENT_ADAPTER client{};
    EP_REPLICATION_BRIDGE adapter{};
    EP_CAPACITY_CONTRACT capacity{};
    BYTE image[2]{0x40, 0x55};
    EP_BRIDGE_SITE site{0, image, sizeof(image)};
    UINT64 allocated[EP_CR_CAPACITY]{};
    UINT64 native_peers[EP_CR_CAPACITY]{};
    UINT64 replicated[EP_CR_CAPACITY]{};
    bool created[EP_CR_CAPACITY]{};
    int native_failure = 0;  // 1=confirm, 2=create, 3=remove, 4=index release
    bool native_throws = false;
    EP_CR_EVENT replication_failure = static_cast<EP_CR_EVENT>(0);
    bool rollback_fails = false;
    bool invalid_mask = false;
    bool order_error = false;
    UINT8 forced_index = 0xFF;
    unsigned native_removes = 0, replication_removes = 0;
    int refs = 0;

    bool failing(int event) {
        if (native_failure != event) return false;
        if (native_throws) throw std::runtime_error("native fixture failure");
        return true;
    }
    static EP_BRIDGE_STATUS __cdecl retain(void* raw) {
        ++static_cast<Fixture*>(raw)->refs;
        return EP_BRIDGE_OK;
    }
    static void __cdecl release(void* raw) { --static_cast<Fixture*>(raw)->refs; }
    static EP_BRIDGE_STATUS __cdecl allocate(void* raw, UINT64 peer, UINT64, UINT8* out) {
        auto& f = *static_cast<Fixture*>(raw);
        for (UINT8 i = 0; i < EP_CR_CAPACITY; ++i) {
            if (f.forced_index != 0xFF && i != f.forced_index) continue;
            if (f.allocated[i]) continue;
            f.allocated[i] = peer;
            *out = i;
            return EP_BRIDGE_OK;
        }
        return EP_BRIDGE_NO_SLOT;
    }
    static EP_BRIDGE_STATUS __cdecl free_index(void* raw, UINT64 peer, UINT64, UINT8 i, UINT32) {
        auto& f = *static_cast<Fixture*>(raw);
        if (f.failing(4)) return EP_BRIDGE_CALLBACK_REJECTED;
        if (i >= EP_CR_CAPACITY || f.allocated[i] != peer) return EP_BRIDGE_INDEX_REJECTED;
        if (f.native_peers[i] || f.replicated[i] || f.created[i]) f.order_error = true;
        f.allocated[i] = 0;
        return EP_BRIDGE_OK;
    }
    static EP_BRIDGE_STATUS __cdecl confirm(void* raw, UINT64 peer, UINT64, UINT8 i) {
        auto& f = *static_cast<Fixture*>(raw);
        f.native_peers[i] = peer;  // Partial work must also be compensated.
        return f.failing(1) ? EP_BRIDGE_CALLBACK_REJECTED : EP_BRIDGE_OK;
    }
    static EP_BRIDGE_STATUS __cdecl create(void* raw, UINT64, UINT64, UINT8 i) {
        auto& f = *static_cast<Fixture*>(raw);
        if (!f.native_peers[i]) f.order_error = true;
        f.created[i] = true;
        return f.failing(2) ? EP_BRIDGE_CALLBACK_REJECTED : EP_BRIDGE_OK;
    }
    static EP_BRIDGE_STATUS __cdecl remove(void* raw, UINT64, UINT64, UINT8 i) {
        auto& f = *static_cast<Fixture*>(raw);
        ++f.native_removes;
        if (f.replicated[i]) f.order_error = true;
        if (f.failing(3)) return EP_BRIDGE_CALLBACK_REJECTED;
        f.native_peers[i] = 0;
        f.created[i] = false;
        return EP_BRIDGE_OK;
    }
    static EP_BRIDGE_STATUS __cdecl membership(void* raw, UINT64 peer, UINT64, UINT8, UINT32* out) {
        auto& f = *static_cast<Fixture*>(static_cast<EP_CLIENT_ADAPTER*>(raw)->native_owner);
        *out = f.invalid_mask ? 0 : (peer % 2 ? EP_CR_ARRAY_CONFIRMED_32 : EP_CR_ARRAY_ALL);
        return EP_BRIDGE_OK;
    }
    static EP_CR_STATUS __cdecl replicate(void* raw, EP_CR_EVENT event, const EP_CR_SLOT* slot, UINT32) {
        auto& f = *static_cast<Fixture*>(raw);
        const UINT8 i = static_cast<UINT8>(slot->network_index);
        if (event == EP_CR_EVENT_APPEND) {
            if (f.native_peers[i] != slot->peer_id) f.order_error = true;
            f.replicated[i] = slot->peer_id;
        }
        if (event == EP_CR_EVENT_CONFIRM && !f.created[i]) f.order_error = true;
        if (event == f.replication_failure || (event == EP_CR_EVENT_ROLLBACK && f.rollback_fails))
            return EP_CR_CALLBACK_REJECTED;
        if (event == EP_CR_EVENT_REMOVE || event == EP_CR_EVENT_ROLLBACK) {
            ++f.replication_removes;
            f.replicated[i] = 0;
        }
        return EP_CR_OK;
    }
    static EP_CR_STATUS __cdecl owner(void*, EP_CR_EVENT, UINT64, UINT32) { return EP_CR_OK; }

    bool init(UINT32 limit = 8) {
        CHECK(ep_client_adapter_init(&client, this, confirm, create, remove,
            allocate, free_index, retain, release) == EP_BRIDGE_OK);
        capacity.version = EP_CAPACITY_CONTRACT_VERSION;
        capacity.build = EP_CAPACITY_BUILD;
        capacity.configured_max_players = limit;
        capacity.peer_capacity = capacity.roster_capacity = capacity.entity_capacity =
            capacity.resource_capacity = capacity.network_capacity = capacity.verified_capacity = limit;
        capacity.quiescent = TRUE;
        capacity.allow_join_in_progress = capacity.require_same_mod_version = TRUE;
        const EP_BRIDGE_CONFIG downstream{EP_CR_BUILD, reinterpret_cast<HMODULE>(image), &site, 1,
            &client, ep_client_adapter_confirm, ep_client_adapter_create, ep_client_adapter_remove,
            ep_client_adapter_retain, ep_client_adapter_release,
            ep_client_adapter_allocate_index, ep_client_adapter_release_index, &capacity};
        const EP_CR_CALLBACKS callbacks{sizeof(EP_CR_CALLBACKS), EP_CR_VERSION, this, replicate, owner};
        CHECK(ep_replication_bridge_init(&adapter, &downstream, &callbacks, membership, 0x100, 1) == EP_BRIDGE_OK);
        CHECK(ep_bridge_preflight(&adapter.admission) == EP_BRIDGE_OK);
        return true;
    }
    bool clean() {
        CHECK(ep_cr_validate(&adapter.replication) == EP_CR_OK);
        CHECK(ep_client_validate(&client.client) == EP_CLIENT_OK);
        CHECK(adapter.admission.sidecar.active_count == 0 && adapter.admission.cleanup_count == 0);
        CHECK(adapter.replication.active_count == 0 && client.client.confirmed_count == 0);
        CHECK(refs == 0 && client.owner_refs == 0 && !order_error);
        for (UINT8 i = 0; i < EP_CR_CAPACITY; ++i)
            CHECK(!allocated[i] && !native_peers[i] && !replicated[i] && !created[i]);
        CHECK(ep_replication_bridge_destroy(&adapter) == EP_BRIDGE_OK);
        CHECK(ep_client_adapter_destroy(&client) == EP_BRIDGE_OK);
        return true;
    }
};

static bool capacity_and_reconnect(UINT32 limit) {
    Fixture f;
    CHECK(f.init(limit));
    EP_BRIDGE_ADMISSION members[EP_CR_CAPACITY]{};
    for (UINT8 i = 0; i < limit; ++i) {
        CHECK(ep_bridge_admit(&f.adapter.admission, 100 + i, 200 + i, &members[i]) == EP_BRIDGE_OK);
        CHECK(members[i].token.index == i);
        CHECK(f.adapter.replication.slots[i].network_index == i);
        CHECK(f.adapter.replication.slots[i].state == EP_CR_CONFIRMED);
    }
    CHECK(f.adapter.replication.confirmed_count == limit && f.client.client.confirmed_count == limit);
    EP_BRIDGE_ADMISSION excess{};
    const auto rejected = ep_bridge_admit(&f.adapter.admission, 999, 1999, &excess);
    CHECK(rejected == (limit == EP_CR_CAPACITY ? EP_BRIDGE_NO_SLOT : EP_BRIDGE_CAPACITY_REJECTED));
    CHECK(f.adapter.replication.confirmed_count == limit);

    const UINT8 hole = static_cast<UINT8>(limit - 2);
    const auto old_token = f.adapter.replication.slots[hole].generation;
    CHECK(ep_bridge_depart(&f.adapter.admission, members[hole]) == EP_BRIDGE_OK);
    CHECK(f.adapter.replication.slots[limit - 1].network_index == limit - 1);
    EP_BRIDGE_ADMISSION new_member{};
    CHECK(ep_bridge_reconnect(&f.adapter.admission, 1000 + hole, 2000 + hole, &new_member) == EP_BRIDGE_OK);
    CHECK(new_member.token.index == hole && new_member.token.generation != members[hole].token.generation);
    CHECK(f.adapter.replication.slots[hole].generation != old_token);
    CHECK(ep_bridge_depart(&f.adapter.admission, members[hole]) == EP_BRIDGE_INVALID_ARGUMENT);
    members[hole] = new_member;
    const auto events = f.replication_removes;
    CHECK(ep_bridge_reconnect(&f.adapter.admission, new_member.peer_id, new_member.resource_handle, &excess) == EP_BRIDGE_OK);
    CHECK(excess.token.generation == new_member.token.generation && f.replication_removes == events);
    CHECK(ep_cr_validate(&f.adapter.replication) == EP_CR_OK);
    for (UINT8 i = 0; i < limit; ++i)
        CHECK(ep_bridge_depart(&f.adapter.admission, members[i]) == EP_BRIDGE_OK);
    return f.clean();
}

static bool failed_admissions() {
    for (int stage = 1; stage <= 4; ++stage) {
        for (int throws = 0; throws < (stage <= 2 ? 2 : 1); ++throws) {
            Fixture f;
            CHECK(f.init());
            if (stage <= 2) { f.native_failure = stage; f.native_throws = throws != 0; }
            else f.replication_failure = stage == 3 ? EP_CR_EVENT_APPEND : EP_CR_EVENT_CONFIRM;
            EP_BRIDGE_ADMISSION member{};
            CHECK(ep_bridge_admit(&f.adapter.admission, 100, 200, &member) == EP_BRIDGE_CALLBACK_REJECTED);
            CHECK(f.native_removes == 1);
            f.native_failure = 0;
            f.replication_failure = static_cast<EP_CR_EVENT>(0);
            CHECK(ep_bridge_admit(&f.adapter.admission, 101, 201, &member) == EP_BRIDGE_OK);
            CHECK(ep_bridge_depart(&f.adapter.admission, member) == EP_BRIDGE_OK);
            CHECK(f.clean());
        }
    }
    return true;
}

static bool rollback_and_cleanup_retries() {
    for (int stage = 0; stage < 5; ++stage) {
        Fixture f;
        CHECK(f.init());
        EP_BRIDGE_ADMISSION member{};
        if (stage < 2) {
            f.replication_failure = stage == 0 ? EP_CR_EVENT_APPEND : EP_CR_EVENT_CONFIRM;
            f.rollback_fails = true;
            CHECK(ep_bridge_admit(&f.adapter.admission, 100, 200, &member) == EP_BRIDGE_CLEANUP_REQUIRED);
            CHECK(f.adapter.replication.slots[0].state == EP_CR_ROLLBACK);
            CHECK(f.native_removes == 0);
        } else {
            CHECK(ep_bridge_admit(&f.adapter.admission, 100, 200, &member) == EP_BRIDGE_OK);
            if (stage == 4) f.replication_failure = EP_CR_EVENT_REMOVE;
            else f.native_failure = stage == 2 ? 3 : 4;
            CHECK(ep_bridge_depart(&f.adapter.admission, member) == EP_BRIDGE_CLEANUP_REQUIRED);
        }
        CHECK(f.allocated[0] == 100 && f.adapter.admission.cleanup_count == 1);
        CHECK(f.refs == 1 && f.client.owner_refs == 1);
        CHECK(ep_replication_bridge_destroy(&f.adapter) == EP_BRIDGE_CLEANUP_REQUIRED);
        CHECK(ep_bridge_retry_cleanup(&f.adapter.admission, member) != EP_BRIDGE_OK);
        CHECK(f.refs == 1 && f.adapter.admission.cleanup_count == 1 && f.allocated[0] == 100);
        const auto already_removed = f.replication_removes;
        const auto native_removes = f.native_removes;
        f.replication_failure = static_cast<EP_CR_EVENT>(0);
        f.rollback_fails = false;
        f.native_failure = 0;
        CHECK(ep_bridge_retry_cleanup(&f.adapter.admission, member) == EP_BRIDGE_OK);
        if (stage == 2 || stage == 3) CHECK(f.replication_removes == already_removed);
        if (stage == 3) CHECK(f.native_removes == native_removes);
        CHECK(f.clean());
    }
    return true;
}

static bool initialization_contract() {
    Fixture f;
    CHECK(f.init());
    auto downstream = f.adapter.downstream;
    const EP_CR_CALLBACKS callbacks{sizeof(EP_CR_CALLBACKS), EP_CR_VERSION, &f,
        Fixture::replicate, Fixture::owner};
    EP_REPLICATION_BRIDGE candidate{};
    CHECK(ep_replication_bridge_init(&f.adapter, &downstream, &callbacks,
        Fixture::membership, 0x100, 1) == EP_BRIDGE_ALREADY_READY);
    downstream.capacity = nullptr;
    CHECK(ep_replication_bridge_init(&candidate, &downstream, &callbacks,
        Fixture::membership, 0x100, 1) == EP_BRIDGE_CAPACITY_REJECTED);
    downstream.capacity = &f.capacity;
    downstream.create_player = nullptr;
    CHECK(ep_replication_bridge_init(&candidate, &downstream, &callbacks,
        Fixture::membership, 0x100, 1) == EP_BRIDGE_CALLBACK_MISSING);
    downstream = f.adapter.downstream;
    auto incomplete = callbacks;
    incomplete.slot_callback = nullptr;
    CHECK(ep_replication_bridge_init(&candidate, &downstream, &incomplete,
        Fixture::membership, 0x100, 1) == EP_BRIDGE_INVALID_ARGUMENT);
    f.capacity.verified_capacity = 4;
    CHECK(ep_replication_bridge_init(&candidate, &downstream, &callbacks,
        Fixture::membership, 0x100, 1) == EP_BRIDGE_CAPACITY_REJECTED);
    CHECK(candidate.magic == 0 && candidate.replication.initialized == 0);
    return f.clean();
}

static bool lease_and_membership() {
    Fixture f;
    CHECK(f.init());
    EP_BRIDGE_ADMISSION member{};
    f.invalid_mask = true;
    CHECK(ep_bridge_admit(&f.adapter.admission, 100, 200, &member) == EP_BRIDGE_CALLBACK_REJECTED);
    CHECK(f.native_removes == 0);
    f.invalid_mask = false;
    f.forced_index = 7;
    CHECK(ep_bridge_admit(&f.adapter.admission, 101, 201, &member) == EP_BRIDGE_OK);
    CHECK(member.token.index == 7 && f.adapter.replication.slots[7].array_membership_mask == EP_CR_ARRAY_CONFIRMED_32);
    UINT8 view[EP_CR_CAPACITY]{};
    UINT32 count = 0;
    CHECK(ep_cr_get_array(&f.adapter.replication, 0, view, &count) == EP_CR_OK && count == 0);
    CHECK(ep_cr_get_array(&f.adapter.replication, 3, view, &count) == EP_CR_OK && count == 1 && view[0] == 7);
    const EP_CR_TOKEN token = f.adapter.slots[7].replication_token;
    UINT32 lease = 0;
    CHECK(ep_cr_callback_enter(&f.adapter.replication, token, &lease) == EP_CR_OK);
    CHECK(ep_bridge_depart(&f.adapter.admission, member) == EP_BRIDGE_CLEANUP_REQUIRED);
    CHECK(f.native_removes == 0 && f.allocated[7] == 101);
    CHECK(ep_cr_callback_leave(&f.adapter.replication, token, lease) == EP_CR_OK);
    CHECK(ep_bridge_retry_cleanup(&f.adapter.admission, member) == EP_BRIDGE_OK);
    return f.clean();
}

int main() {
    if (!capacity_and_reconnect(4) || !capacity_and_reconnect(8) || !capacity_and_reconnect(16) ||
        !failed_admissions() || !rollback_and_cleanup_retries() || !lease_and_membership() ||
        !initialization_contract()) return 1;
    std::puts("ep_replication_bridge_integration_passed");
    return 0;
}
