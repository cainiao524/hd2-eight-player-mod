#include "ep_eight_preflight.h"

#include <cstdio>

static EP_EIGHT_PREFLIGHT_INPUT good_input() {
    EP_EIGHT_PREFLIGHT_INPUT input{};
    input.version = EP_EIGHT_PREFLIGHT_VERSION;
    input.build = EP_EIGHT_PREFLIGHT_BUILD;
    input.bridge_capacity = EP_EIGHT_PREFLIGHT_CAPACITY;
    input.client_capacity = EP_EIGHT_PREFLIGHT_CAPACITY;
    input.resource_capacity = EP_EIGHT_PREFLIGHT_CAPACITY;
    input.replication_capacity = EP_EIGHT_PREFLIGHT_CAPACITY;
    input.player_creation_capacity = EP_EIGHT_PREFLIGHT_CAPACITY;
    input.session_capacity = EP_EIGHT_PREFLIGHT_CAPACITY;
    input.official_plugin_capacity = EP_EIGHT_PREFLIGHT_CAPACITY;
    input.bridge_callbacks_ready = TRUE;
    input.client_callbacks_ready = TRUE;
    input.resource_callbacks_ready = TRUE;
    input.replication_callbacks_ready = TRUE;
    input.player_creation_callbacks_ready = TRUE;
    input.authoritative_index_source = TRUE;
    input.compact_ordinal_separate = TRUE;
    input.holes_preserved = TRUE;
    input.host_client_same_build = TRUE;
    return input;
}

static bool check(bool ok, const char* label) {
    if (!ok) std::fprintf(stderr, "failed: %s\n", label);
    return ok;
}

int main() {
    bool ok = true;
    EP_EIGHT_PREFLIGHT_REPORT report{};
    EP_EIGHT_PREFLIGHT_INPUT input = good_input();
    ok &= check(ep_eight_preflight_validate(&input, &report) == EP_EIGHT_PREFLIGHT_OK &&
                    report.ready && report.failure_mask == 0,
                "all components ready");

    input.client_capacity = 4;
    ok &= check(ep_eight_preflight_validate(&input, &report) ==
                    EP_EIGHT_PREFLIGHT_CAPACITY_MISMATCH &&
                    !report.ready && (report.failure_mask & EP_EIGHT_PREFLIGHT_FAIL_CAPACITY),
                "client four-slot capacity rejected");
    input = good_input();
    input.build += 1;
    ok &= check(ep_eight_preflight_validate(&input, &report) ==
                    EP_EIGHT_PREFLIGHT_BUILD_MISMATCH &&
                    (report.failure_mask & EP_EIGHT_PREFLIGHT_FAIL_BUILD),
                "build mismatch rejected");
    input = good_input();
    input.resource_callbacks_ready = FALSE;
    ok &= check(ep_eight_preflight_validate(&input, &report) ==
                    EP_EIGHT_PREFLIGHT_CALLBACK_MISSING &&
                    (report.failure_mask & EP_EIGHT_PREFLIGHT_FAIL_CALLBACKS),
                "resource callback missing rejected");
    input = good_input();
    input.authoritative_index_source = FALSE;
    input.compact_ordinal_separate = FALSE;
    input.holes_preserved = FALSE;
    input.host_client_same_build = FALSE;
    ok &= check(ep_eight_preflight_validate(&input, &report) ==
                    EP_EIGHT_PREFLIGHT_INDEX_CONTRACT_MISSING &&
                    (report.failure_mask & EP_EIGHT_PREFLIGHT_FAIL_INDEX) &&
                    (report.failure_mask & EP_EIGHT_PREFLIGHT_FAIL_ORDINAL) &&
                    (report.failure_mask & EP_EIGHT_PREFLIGHT_FAIL_HOLES) &&
                    (report.failure_mask & EP_EIGHT_PREFLIGHT_FAIL_HOST_CLIENT),
                "index and host/client contracts rejected");
    ok &= check(ep_eight_preflight_validate(nullptr, &report) ==
                    EP_EIGHT_PREFLIGHT_INVALID_ARGUMENT,
                "null input rejected");
    if (!ok) return 1;
    std::puts("ep_eight_preflight_synthetic_passed");
    return 0;
}
