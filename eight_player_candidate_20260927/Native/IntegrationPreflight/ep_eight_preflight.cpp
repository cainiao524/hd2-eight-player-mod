#include "ep_eight_preflight.h"

#include <cstring>

namespace {

bool all_capacities_are_eight(const EP_EIGHT_PREFLIGHT_INPUT& input) {
    return input.bridge_capacity == EP_EIGHT_PREFLIGHT_CAPACITY &&
           input.client_capacity == EP_EIGHT_PREFLIGHT_CAPACITY &&
           input.resource_capacity == EP_EIGHT_PREFLIGHT_CAPACITY &&
           input.replication_capacity == EP_EIGHT_PREFLIGHT_CAPACITY &&
           input.player_creation_capacity == EP_EIGHT_PREFLIGHT_CAPACITY &&
           input.session_capacity == EP_EIGHT_PREFLIGHT_CAPACITY &&
           input.official_plugin_capacity == EP_EIGHT_PREFLIGHT_CAPACITY;
}

bool callbacks_are_ready(const EP_EIGHT_PREFLIGHT_INPUT& input) {
    return input.bridge_callbacks_ready && input.client_callbacks_ready &&
           input.resource_callbacks_ready && input.replication_callbacks_ready &&
           input.player_creation_callbacks_ready;
}

EP_EIGHT_PREFLIGHT_STATUS first_failure(UINT32 mask) {
    if (mask & EP_EIGHT_PREFLIGHT_FAIL_BUILD) return EP_EIGHT_PREFLIGHT_BUILD_MISMATCH;
    if (mask & EP_EIGHT_PREFLIGHT_FAIL_CAPACITY) return EP_EIGHT_PREFLIGHT_CAPACITY_MISMATCH;
    if (mask & EP_EIGHT_PREFLIGHT_FAIL_CALLBACKS) return EP_EIGHT_PREFLIGHT_CALLBACK_MISSING;
    if (mask & EP_EIGHT_PREFLIGHT_FAIL_INDEX) return EP_EIGHT_PREFLIGHT_INDEX_CONTRACT_MISSING;
    if (mask & EP_EIGHT_PREFLIGHT_FAIL_ORDINAL) return EP_EIGHT_PREFLIGHT_ORDINAL_CONTRACT_MISSING;
    if (mask & EP_EIGHT_PREFLIGHT_FAIL_HOLES) return EP_EIGHT_PREFLIGHT_HOLE_CONTRACT_MISSING;
    if (mask & EP_EIGHT_PREFLIGHT_FAIL_HOST_CLIENT) return EP_EIGHT_PREFLIGHT_HOST_CLIENT_MISMATCH;
    return EP_EIGHT_PREFLIGHT_OK;
}

}

extern "C" EP_EIGHT_PREFLIGHT_STATUS __cdecl
ep_eight_preflight_validate(const EP_EIGHT_PREFLIGHT_INPUT* input,
                            EP_EIGHT_PREFLIGHT_REPORT* out_report) {
    if (!input || !out_report) return EP_EIGHT_PREFLIGHT_INVALID_ARGUMENT;
    std::memset(out_report, 0, sizeof(*out_report));
    out_report->version = input->version;
    out_report->build = input->build;
    out_report->required_capacity = EP_EIGHT_PREFLIGHT_CAPACITY;
    out_report->build_ok = input->version == EP_EIGHT_PREFLIGHT_VERSION &&
                           input->build == EP_EIGHT_PREFLIGHT_BUILD;
    out_report->capacities_ok = all_capacities_are_eight(*input);
    out_report->callbacks_ok = callbacks_are_ready(*input);
    out_report->index_contract_ok = input->authoritative_index_source != FALSE;
    out_report->ordinal_contract_ok = input->compact_ordinal_separate != FALSE;
    out_report->hole_contract_ok = input->holes_preserved != FALSE;
    out_report->host_client_ok = input->host_client_same_build != FALSE;
    UINT32 failures = 0;
    if (!out_report->build_ok) failures |= EP_EIGHT_PREFLIGHT_FAIL_BUILD;
    if (!out_report->capacities_ok) failures |= EP_EIGHT_PREFLIGHT_FAIL_CAPACITY;
    if (!out_report->callbacks_ok) failures |= EP_EIGHT_PREFLIGHT_FAIL_CALLBACKS;
    if (!out_report->index_contract_ok) failures |= EP_EIGHT_PREFLIGHT_FAIL_INDEX;
    if (!out_report->ordinal_contract_ok) failures |= EP_EIGHT_PREFLIGHT_FAIL_ORDINAL;
    if (!out_report->hole_contract_ok) failures |= EP_EIGHT_PREFLIGHT_FAIL_HOLES;
    if (!out_report->host_client_ok) failures |= EP_EIGHT_PREFLIGHT_FAIL_HOST_CLIENT;
    out_report->failure_mask = failures;
    out_report->ready = failures == 0;
    return first_failure(failures);
}

extern "C" UINT32 __cdecl ep_eight_preflight_build() {
    return EP_EIGHT_PREFLIGHT_BUILD;
}

extern "C" UINT32 __cdecl ep_eight_preflight_capacity() {
    return EP_EIGHT_PREFLIGHT_CAPACITY;
}
