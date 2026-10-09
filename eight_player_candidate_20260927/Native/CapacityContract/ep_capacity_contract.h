#pragma once

#include <windows.h>

// Versioned, game-independent capacity contract.  This is the boundary that
// Session/Party, roster, entity and resource adapters must all satisfy before
// any game callback is allowed to run.
#define EP_CAPACITY_CONTRACT_VERSION 1u
#define EP_CAPACITY_BUILD 25480438u
#define EP_CAPACITY_HARD_LIMIT 16u

extern "C" {

typedef enum EP_CAPACITY_STATUS : UINT32 {
    EP_CAPACITY_OK = 0,
    EP_CAPACITY_INVALID_ARGUMENT = 1,
    EP_CAPACITY_VERSION_MISMATCH = 2,
    EP_CAPACITY_BUILD_MISMATCH = 3,
    EP_CAPACITY_VALUE_INVALID = 4,
    EP_CAPACITY_CONFIGURED_EXCEEDS_VERIFIED = 5,
    EP_CAPACITY_JOINED_EXCEEDS_EFFECTIVE = 6,
    EP_CAPACITY_MISSION_DECREASE = 7,
    EP_CAPACITY_RESERVATION_REQUIRED = 8,
    EP_CAPACITY_QUIESCENCE_REQUIRED = 9,
    EP_CAPACITY_AUTHORITY_REQUIRED = 10,
    EP_CAPACITY_APPLY_MODE_INVALID = 11,
} EP_CAPACITY_STATUS;

typedef enum EP_CAPACITY_APPLY_MODE : UINT32 {
    EP_CAPACITY_NEXT_LOBBY = 0,
    EP_CAPACITY_NEXT_MISSION = 1,
    EP_CAPACITY_RESTART_REQUIRED = 2,
} EP_CAPACITY_APPLY_MODE;

typedef struct EP_CAPACITY_CONTRACT {
    UINT32 version;
    UINT32 build;
    UINT32 configured_max_players;
    UINT32 effective_max_players;
    UINT32 peer_capacity;
    UINT32 roster_capacity;
    UINT32 entity_capacity;
    UINT32 resource_capacity;
    UINT32 network_capacity;
    UINT32 verified_capacity;
    UINT32 joined_players;
    UINT32 generation;
    BOOL allow_join_in_progress;
    BOOL require_same_mod_version;
    BOOL mission_active;
    BOOL quiescent;
    EP_CAPACITY_APPLY_MODE apply_mode;
} EP_CAPACITY_CONTRACT;

typedef struct EP_CAPACITY_REQUEST {
    UINT32 version;
    UINT32 build;
    UINT32 configured_max_players;
    BOOL allow_join_in_progress;
    BOOL require_same_mod_version;
    EP_CAPACITY_APPLY_MODE apply_mode;
} EP_CAPACITY_REQUEST;

typedef struct EP_CAPACITY_RESERVATION {
    BOOL ready;
    BOOL quiescent;
} EP_CAPACITY_RESERVATION;

typedef struct EP_CAPACITY_REPORT {
    UINT32 version;
    UINT32 build;
    UINT32 effective_max_players;
    UINT32 failure_mask;
    BOOL version_ok;
    BOOL component_capacities_ok;
    BOOL configured_ok;
    BOOL joined_ok;
    BOOL ready;
} EP_CAPACITY_REPORT;

enum : UINT32 {
    EP_CAPACITY_FAIL_VERSION = 1u << 0,
    EP_CAPACITY_FAIL_COMPONENT = 1u << 1,
    EP_CAPACITY_FAIL_CONFIGURED = 1u << 2,
    EP_CAPACITY_FAIL_JOINED = 1u << 3,
};

__declspec(dllexport) EP_CAPACITY_STATUS __cdecl ep_capacity_validate(
    const EP_CAPACITY_CONTRACT* contract, EP_CAPACITY_REPORT* report);

__declspec(dllexport) EP_CAPACITY_STATUS __cdecl ep_capacity_apply(
    EP_CAPACITY_CONTRACT* current, const EP_CAPACITY_REQUEST* request,
    const EP_CAPACITY_RESERVATION* reservation, BOOL host_authority,
    EP_CAPACITY_REPORT* report);

__declspec(dllexport) UINT32 __cdecl ep_capacity_effective(
    const EP_CAPACITY_CONTRACT* contract);

__declspec(dllexport) UINT32 __cdecl ep_capacity_build();
__declspec(dllexport) UINT32 __cdecl ep_capacity_hard_limit();

}
