#include "ep_capacity_contract.h"

#include <algorithm>
#include <cstring>

#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif

namespace {

bool value_ok(UINT32 value) {
    return value >= 1u && value <= EP_CAPACITY_HARD_LIMIT;
}

bool apply_mode_ok(EP_CAPACITY_APPLY_MODE mode) {
    return mode == EP_CAPACITY_NEXT_LOBBY ||
           mode == EP_CAPACITY_NEXT_MISSION ||
           mode == EP_CAPACITY_RESTART_REQUIRED;
}

UINT32 component_min(const EP_CAPACITY_CONTRACT& c) {
    return std::min({c.peer_capacity, c.roster_capacity, c.entity_capacity,
                     c.resource_capacity, c.network_capacity,
                     c.verified_capacity, EP_CAPACITY_HARD_LIMIT});
}

EP_CAPACITY_STATUS first_failure(UINT32 mask) {
    if (mask & EP_CAPACITY_FAIL_VERSION) return EP_CAPACITY_VERSION_MISMATCH;
    if (mask & EP_CAPACITY_FAIL_COMPONENT) return EP_CAPACITY_VALUE_INVALID;
    if (mask & EP_CAPACITY_FAIL_CONFIGURED)
        return EP_CAPACITY_CONFIGURED_EXCEEDS_VERIFIED;
    if (mask & EP_CAPACITY_FAIL_JOINED)
        return EP_CAPACITY_JOINED_EXCEEDS_EFFECTIVE;
    return EP_CAPACITY_OK;
}

void clear_report(EP_CAPACITY_REPORT* report, const EP_CAPACITY_CONTRACT* c) {
    std::memset(report, 0, sizeof(*report));
    report->version = c ? c->version : 0;
    report->build = c ? c->build : 0;
}

}

extern "C" EP_CAPACITY_STATUS __cdecl ep_capacity_validate(
    const EP_CAPACITY_CONTRACT* c, EP_CAPACITY_REPORT* report) {
    if (!c || !report) return EP_CAPACITY_INVALID_ARGUMENT;
    clear_report(report, c);
    report->version_ok = c->version == EP_CAPACITY_CONTRACT_VERSION &&
                         c->build == EP_CAPACITY_BUILD;
    const bool components = value_ok(c->peer_capacity) &&
                            value_ok(c->roster_capacity) &&
                            value_ok(c->entity_capacity) &&
                            value_ok(c->resource_capacity) &&
                            value_ok(c->network_capacity) &&
                            value_ok(c->verified_capacity);
    report->component_capacities_ok = components;
    report->configured_ok = value_ok(c->configured_max_players) &&
                            c->configured_max_players <= c->verified_capacity;
    const UINT32 effective = components && report->configured_ok
        ? std::min(c->configured_max_players, component_min(*c)) : 0u;
    report->effective_max_players = effective;
    report->joined_ok = c->joined_players <= effective;
    UINT32 failures = 0;
    if (!report->version_ok) failures |= EP_CAPACITY_FAIL_VERSION;
    if (!components) failures |= EP_CAPACITY_FAIL_COMPONENT;
    if (!report->configured_ok) failures |= EP_CAPACITY_FAIL_CONFIGURED;
    if (!report->joined_ok) failures |= EP_CAPACITY_FAIL_JOINED;
    report->failure_mask = failures;
    report->ready = failures == 0;
    return first_failure(failures);
}

extern "C" EP_CAPACITY_STATUS __cdecl ep_capacity_apply(
    EP_CAPACITY_CONTRACT* current, const EP_CAPACITY_REQUEST* request,
    const EP_CAPACITY_RESERVATION* reservation, BOOL host_authority,
    EP_CAPACITY_REPORT* report) {
    if (!current || !request || !reservation || !report)
        return EP_CAPACITY_INVALID_ARGUMENT;
    if (!host_authority) return EP_CAPACITY_AUTHORITY_REQUIRED;
    EP_CAPACITY_REPORT current_report{};
    const EP_CAPACITY_STATUS current_status = ep_capacity_validate(current, &current_report);
    if (current_status != EP_CAPACITY_OK) {
        *report = current_report;
        return current_status;
    }
    if (request->version != EP_CAPACITY_CONTRACT_VERSION)
        return EP_CAPACITY_VERSION_MISMATCH;
    if (request->build != EP_CAPACITY_BUILD)
        return EP_CAPACITY_BUILD_MISMATCH;
    if (!value_ok(request->configured_max_players) ||
        request->configured_max_players > current->verified_capacity)
        return EP_CAPACITY_CONFIGURED_EXCEEDS_VERIFIED;
    if (!apply_mode_ok(request->apply_mode)) return EP_CAPACITY_APPLY_MODE_INVALID;
    if (current->mission_active &&
        request->configured_max_players < current->configured_max_players)
        return EP_CAPACITY_MISSION_DECREASE;
    if (current->mission_active &&
        request->configured_max_players > current->configured_max_players) {
        if (request->apply_mode != EP_CAPACITY_NEXT_MISSION)
            return EP_CAPACITY_RESERVATION_REQUIRED;
        if (!reservation->ready) return EP_CAPACITY_RESERVATION_REQUIRED;
        if (!reservation->quiescent || !current->quiescent)
            return EP_CAPACITY_QUIESCENCE_REQUIRED;
    }

    EP_CAPACITY_CONTRACT candidate = *current;
    candidate.version = request->version;
    candidate.build = request->build;
    candidate.configured_max_players = request->configured_max_players;
    candidate.apply_mode = request->apply_mode;
    candidate.allow_join_in_progress = request->allow_join_in_progress;
    candidate.require_same_mod_version = request->require_same_mod_version;
    candidate.effective_max_players = std::min(
        candidate.configured_max_players, component_min(candidate));
    if (candidate.joined_players > candidate.effective_max_players)
        return EP_CAPACITY_JOINED_EXCEEDS_EFFECTIVE;
    if (candidate.generation == UINT32_MAX) return EP_CAPACITY_VALUE_INVALID;
    candidate.generation += 1;
    EP_CAPACITY_REPORT candidate_report{};
    const EP_CAPACITY_STATUS candidate_status = ep_capacity_validate(
        &candidate, &candidate_report);
    if (candidate_status != EP_CAPACITY_OK) {
        *report = candidate_report;
        return candidate_status;
    }
    *current = candidate;
    *report = candidate_report;
    return EP_CAPACITY_OK;
}

extern "C" UINT32 __cdecl ep_capacity_effective(
    const EP_CAPACITY_CONTRACT* c) {
    if (!c) return 0;
    EP_CAPACITY_REPORT report{};
    return ep_capacity_validate(c, &report) == EP_CAPACITY_OK
        ? report.effective_max_players : 0u;
}

extern "C" UINT32 __cdecl ep_capacity_build() { return EP_CAPACITY_BUILD; }
extern "C" UINT32 __cdecl ep_capacity_hard_limit() { return EP_CAPACITY_HARD_LIMIT; }
