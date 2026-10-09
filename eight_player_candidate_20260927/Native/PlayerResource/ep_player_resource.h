#pragma once

#include <windows.h>
#include "../CapacityContract/ep_capacity_contract.h"

// Offline native-shaped player-resource transaction table.  It mirrors the
// fixed-build callback ordering discovered in the ABI audit, but it never
// resolves an RVA, calls game code, or writes a game process.
#define EP_RESOURCE_CAPACITY EP_CAPACITY_HARD_LIMIT
#define EP_RESOURCE_MAGIC 0x45505253u /* "EPRS" */
#define EP_RESOURCE_VERSION 2u
#define EP_RESOURCE_MAX_CALLBACKS 3u

extern "C" {

typedef enum EP_RESOURCE_STATUS : UINT32 {
    EP_RS_OK = 0,
    EP_RS_INVALID_ARGUMENT = 1,
    EP_RS_INVALID_CONTEXT = 2,
    EP_RS_DUPLICATE = 3,
    EP_RS_FULL = 4,
    EP_RS_GENERATION_EXHAUSTED = 5,
    EP_RS_STALE_TOKEN = 6,
    EP_RS_INVALID_STATE = 7,
    EP_RS_CALLBACK_ORDER = 8,
    EP_RS_CALLBACK_FAILED = 9,
    EP_RS_BUSY = 10,
    EP_RS_OWNER_MISMATCH = 11,
    EP_RS_ALREADY_RELEASED = 12,
    EP_RS_INVARIANT_BROKEN = 13,
} EP_RESOURCE_STATUS;

typedef enum EP_RESOURCE_STATE : UINT8 {
    EP_RS_FREE = 0,
    EP_RS_PENDING = 1,
    EP_RS_ACTIVE = 2,
    EP_RS_CONFIRMED = 3,
    EP_RS_ROLLING_BACK = 4,
    EP_RS_RELEASED = 5,
} EP_RESOURCE_STATE;

typedef enum EP_RESOURCE_STAGE : UINT8 {
    EP_RS_STAGE_FIRST = 0,
    EP_RS_STAGE_SECOND = 1,
    EP_RS_STAGE_THIRD = 2,
} EP_RESOURCE_STAGE;

typedef struct EP_RESOURCE_TOKEN {
    UINT8 index;
    UINT8 reserved[3];
    UINT32 generation;
    UINT32 owner_epoch;
} EP_RESOURCE_TOKEN;

typedef struct EP_RESOURCE_LEASE {
    UINT32 lease_id;
    EP_RESOURCE_TOKEN token;
} EP_RESOURCE_LEASE;

typedef struct EP_RESOURCE_RECORD {
    UINT8 state;
    UINT8 applied_callbacks;
    UINT8 inflight;
    UINT8 reserved;
    UINT32 generation;
    UINT32 owner_epoch;
    UINT64 peer_id;
    UINT64 resource_handle;
    UINT64 resource_hash;
    UINT32 record_ordinal;
    UINT16 component_ordinal;
    UINT16 reserved2;
} EP_RESOURCE_RECORD;

typedef struct EP_RESOURCE_HISTORY {
    UINT8 valid;
    UINT8 reserved[3];
    EP_RESOURCE_TOKEN token;
} EP_RESOURCE_HISTORY;

typedef struct EP_PLAYER_RESOURCE {
    UINT32 magic;
    UINT32 version;
    UINT32 initialized;
    UINT32 owner_key;
    UINT32 owner_epoch;
    UINT32 inflight;
    UINT32 next_lease_id;
    UINT32 quiesced;
    SRWLOCK lock;
    UINT32 generations[EP_RESOURCE_CAPACITY];
    EP_RESOURCE_RECORD records[EP_RESOURCE_CAPACITY];
    EP_RESOURCE_HISTORY history[EP_RESOURCE_CAPACITY];
    EP_RESOURCE_LEASE leases[EP_RESOURCE_CAPACITY];
} EP_PLAYER_RESOURCE;

__declspec(dllexport) EP_RESOURCE_STATUS __cdecl ep_resource_init(
    EP_PLAYER_RESOURCE* resource, UINT32 owner_key);
__declspec(dllexport) EP_RESOURCE_STATUS __cdecl ep_resource_destroy(
    EP_PLAYER_RESOURCE* resource);
__declspec(dllexport) EP_RESOURCE_STATUS __cdecl ep_resource_begin(
    EP_PLAYER_RESOURCE* resource, UINT8 network_index, UINT64 peer_id,
    UINT64 resource_handle, UINT64 resource_hash, UINT32 record_ordinal,
    UINT16 component_ordinal, EP_RESOURCE_TOKEN* out_token);
__declspec(dllexport) EP_RESOURCE_STATUS __cdecl ep_resource_begin_callback(
    EP_PLAYER_RESOURCE* resource, EP_RESOURCE_TOKEN token,
    EP_RESOURCE_LEASE* out_lease);
__declspec(dllexport) EP_RESOURCE_STATUS __cdecl ep_resource_complete_callback(
    EP_PLAYER_RESOURCE* resource, EP_RESOURCE_LEASE lease,
    EP_RESOURCE_STAGE stage, BOOL succeeded);
__declspec(dllexport) EP_RESOURCE_STATUS __cdecl ep_resource_publish(
    EP_PLAYER_RESOURCE* resource, EP_RESOURCE_TOKEN token);
__declspec(dllexport) EP_RESOURCE_STATUS __cdecl ep_resource_release(
    EP_PLAYER_RESOURCE* resource, EP_RESOURCE_TOKEN token);
__declspec(dllexport) EP_RESOURCE_STATUS __cdecl ep_resource_quiesce(
    EP_PLAYER_RESOURCE* resource);
__declspec(dllexport) EP_RESOURCE_STATUS __cdecl ep_resource_migrate_owner(
    EP_PLAYER_RESOURCE* resource, UINT32 new_owner_key);
__declspec(dllexport) EP_RESOURCE_STATUS __cdecl ep_resource_get(
    EP_PLAYER_RESOURCE* resource, UINT8 network_index,
    EP_RESOURCE_RECORD* out_record);
__declspec(dllexport) EP_RESOURCE_STATUS __cdecl ep_resource_validate(
    EP_PLAYER_RESOURCE* resource);
__declspec(dllexport) UINT32 __cdecl ep_resource_capacity();

}
