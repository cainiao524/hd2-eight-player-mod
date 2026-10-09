#include "ep_capacity_contract.h"

#include <cassert>
#include <cstdio>

namespace {

EP_CAPACITY_CONTRACT base(UINT32 capacity, UINT32 joined = 0) {
    EP_CAPACITY_CONTRACT c{};
    c.version = EP_CAPACITY_CONTRACT_VERSION;
    c.build = EP_CAPACITY_BUILD;
    c.configured_max_players = capacity;
    c.peer_capacity = capacity;
    c.roster_capacity = capacity;
    c.entity_capacity = capacity;
    c.resource_capacity = capacity;
    c.network_capacity = capacity;
    c.verified_capacity = capacity;
    c.joined_players = joined;
    c.generation = 0;
    c.allow_join_in_progress = TRUE;
    c.require_same_mod_version = TRUE;
    c.quiescent = TRUE;
    c.apply_mode = EP_CAPACITY_NEXT_LOBBY;
    return c;
}

void test_supported_capacities() {
    const UINT32 values[] = {4u, 5u, 8u, 12u, 16u};
    for (UINT32 value : values) {
        auto c = base(value);
        EP_CAPACITY_REPORT report{};
        assert(ep_capacity_validate(&c, &report) == EP_CAPACITY_OK);
        assert(report.ready && report.effective_max_players == value);
    }
}

void test_minimum_component_wins() {
    auto c = base(8);
    c.peer_capacity = 5;
    EP_CAPACITY_REPORT report{};
    assert(ep_capacity_validate(&c, &report) == EP_CAPACITY_OK);
    assert(report.effective_max_players == 5);
}

void test_duplicate_or_out_of_range_configuration_rejected() {
    auto c = base(8);
    EP_CAPACITY_REQUEST request{EP_CAPACITY_CONTRACT_VERSION, EP_CAPACITY_BUILD,
                                9, TRUE, TRUE, EP_CAPACITY_NEXT_LOBBY};
    EP_CAPACITY_RESERVATION reservation{TRUE, TRUE};
    EP_CAPACITY_REPORT report{};
    assert(ep_capacity_apply(&c, &request, &reservation, TRUE, &report) ==
           EP_CAPACITY_CONFIGURED_EXCEEDS_VERIFIED);
    assert(c.configured_max_players == 8);
}

void test_mission_rules_are_atomic() {
    auto c = base(8, 5);
    c.mission_active = TRUE;
    EP_CAPACITY_REQUEST decrease{EP_CAPACITY_CONTRACT_VERSION, EP_CAPACITY_BUILD,
                                 4, TRUE, TRUE, EP_CAPACITY_NEXT_MISSION};
    EP_CAPACITY_RESERVATION ready{TRUE, TRUE};
    EP_CAPACITY_REPORT report{};
    assert(ep_capacity_apply(&c, &decrease, &ready, TRUE, &report) ==
           EP_CAPACITY_MISSION_DECREASE);
    assert(c.configured_max_players == 8);

    EP_CAPACITY_REQUEST increase{EP_CAPACITY_CONTRACT_VERSION, EP_CAPACITY_BUILD,
                                 12, TRUE, TRUE, EP_CAPACITY_NEXT_MISSION};
    assert(ep_capacity_apply(&c, &increase, &ready, TRUE, &report) ==
           EP_CAPACITY_CONFIGURED_EXCEEDS_VERIFIED);
    assert(c.configured_max_players == 8);
}

void test_live_increase_requires_reservation_and_quiescence() {
    auto c = base(8, 5);
    c.verified_capacity = 12;
    c.peer_capacity = c.roster_capacity = c.entity_capacity = 12;
    c.resource_capacity = c.network_capacity = 12;
    c.mission_active = TRUE;
    EP_CAPACITY_REQUEST request{EP_CAPACITY_CONTRACT_VERSION, EP_CAPACITY_BUILD,
                                12, TRUE, TRUE, EP_CAPACITY_NEXT_MISSION};
    EP_CAPACITY_RESERVATION not_ready{FALSE, TRUE};
    EP_CAPACITY_REPORT report{};
    assert(ep_capacity_apply(&c, &request, &not_ready, TRUE, &report) ==
           EP_CAPACITY_RESERVATION_REQUIRED);
    assert(c.configured_max_players == 8);
    EP_CAPACITY_RESERVATION ready{TRUE, TRUE};
    assert(ep_capacity_apply(&c, &request, &ready, TRUE, &report) == EP_CAPACITY_OK);
    assert(c.configured_max_players == 12 && c.generation == 1);
}

void test_client_cannot_apply() {
    auto c = base(8);
    EP_CAPACITY_REQUEST request{EP_CAPACITY_CONTRACT_VERSION, EP_CAPACITY_BUILD,
                                8, TRUE, TRUE, EP_CAPACITY_NEXT_LOBBY};
    EP_CAPACITY_RESERVATION ready{TRUE, TRUE};
    EP_CAPACITY_REPORT report{};
    assert(ep_capacity_apply(&c, &request, &ready, FALSE, &report) ==
           EP_CAPACITY_AUTHORITY_REQUIRED);
    assert(c.generation == 0);
}

}

int main() {
    test_supported_capacities();
    test_minimum_component_wins();
    test_duplicate_or_out_of_range_configuration_rejected();
    test_mission_rules_are_atomic();
    test_live_increase_requires_reservation_and_quiescence();
    test_client_cannot_apply();
    std::puts("ep_capacity_contract_passed");
    return 0;
}
