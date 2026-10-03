#pragma once

#include <windows.h>

// Cross-component preflight only.  It validates that the offline adapters
// agree on the fixed build, eight-slot contract and callback prerequisites.
// It never resolves a game address, calls a native game function, or writes
// a process.  A true result is necessary for activation but is not runtime
// or multiplayer evidence.
#define EP_EIGHT_PREFLIGHT_VERSION 1u
#define EP_EIGHT_PREFLIGHT_BUILD 25480438u
#define EP_EIGHT_PREFLIGHT_CAPACITY 8u

extern "C" {

typedef enum EP_EIGHT_PREFLIGHT_STATUS : UINT32 {
    EP_EIGHT_PREFLIGHT_OK = 0,
    EP_EIGHT_PREFLIGHT_INVALID_ARGUMENT = 1,
    EP_EIGHT_PREFLIGHT_BUILD_MISMATCH = 2,
    EP_EIGHT_PREFLIGHT_CAPACITY_MISMATCH = 3,
    EP_EIGHT_PREFLIGHT_CALLBACK_MISSING = 4,
    EP_EIGHT_PREFLIGHT_INDEX_CONTRACT_MISSING = 5,
    EP_EIGHT_PREFLIGHT_ORDINAL_CONTRACT_MISSING = 6,
    EP_EIGHT_PREFLIGHT_HOLE_CONTRACT_MISSING = 7,
    EP_EIGHT_PREFLIGHT_HOST_CLIENT_MISMATCH = 8,
} EP_EIGHT_PREFLIGHT_STATUS;

typedef struct EP_EIGHT_PREFLIGHT_INPUT {
    UINT32 version;
    UINT32 build;
    UINT32 bridge_capacity;
    UINT32 client_capacity;
    UINT32 resource_capacity;
    UINT32 replication_capacity;
    UINT32 player_creation_capacity;
    UINT32 session_capacity;
    UINT32 official_plugin_capacity;
    BOOL bridge_callbacks_ready;
    BOOL client_callbacks_ready;
    BOOL resource_callbacks_ready;
    BOOL replication_callbacks_ready;
    BOOL player_creation_callbacks_ready;
    BOOL authoritative_index_source;
    BOOL compact_ordinal_separate;
    BOOL holes_preserved;
    BOOL host_client_same_build;
} EP_EIGHT_PREFLIGHT_INPUT;

typedef struct EP_EIGHT_PREFLIGHT_REPORT {
    UINT32 version;
    UINT32 build;
    UINT32 required_capacity;
    UINT32 failure_mask;
    BOOL build_ok;
    BOOL capacities_ok;
    BOOL callbacks_ok;
    BOOL index_contract_ok;
    BOOL ordinal_contract_ok;
    BOOL hole_contract_ok;
    BOOL host_client_ok;
    BOOL ready;
} EP_EIGHT_PREFLIGHT_REPORT;

enum : UINT32 {
    EP_EIGHT_PREFLIGHT_FAIL_BUILD = 1u << 0,
    EP_EIGHT_PREFLIGHT_FAIL_CAPACITY = 1u << 1,
    EP_EIGHT_PREFLIGHT_FAIL_CALLBACKS = 1u << 2,
    EP_EIGHT_PREFLIGHT_FAIL_INDEX = 1u << 3,
    EP_EIGHT_PREFLIGHT_FAIL_ORDINAL = 1u << 4,
    EP_EIGHT_PREFLIGHT_FAIL_HOLES = 1u << 5,
    EP_EIGHT_PREFLIGHT_FAIL_HOST_CLIENT = 1u << 6,
};

__declspec(dllexport) EP_EIGHT_PREFLIGHT_STATUS __cdecl
ep_eight_preflight_validate(const EP_EIGHT_PREFLIGHT_INPUT* input,
                            EP_EIGHT_PREFLIGHT_REPORT* out_report);
__declspec(dllexport) UINT32 __cdecl ep_eight_preflight_build();
__declspec(dllexport) UINT32 __cdecl ep_eight_preflight_capacity();

}
