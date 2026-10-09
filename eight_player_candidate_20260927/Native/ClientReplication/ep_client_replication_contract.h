#pragma once

#include <windows.h>
#include "../CapacityContract/ep_capacity_contract.h"

// Offline-only contract for the client confirmed-peer replication sidecar.
// It owns an isolated table and never locates, patches, injects, or writes a
// game process.  A native bridge must provide reviewed callbacks before this
// model can be used as an integration boundary.
#define EP_CR_MAGIC 0x45504352u /* EPCR */
#define EP_CR_VERSION 2u
#define EP_CR_BUILD 25480438u
#define EP_CR_CAPACITY EP_CAPACITY_HARD_LIMIT
#define EP_CR_ARRAY_ADJACENT_8 (1u << 0)
#define EP_CR_ARRAY_ADJACENT_16 (1u << 1)
#define EP_CR_ARRAY_ADJACENT_16B (1u << 2)
#define EP_CR_ARRAY_CONFIRMED_32 (1u << 3)
#define EP_CR_ARRAY_PEER_KEYED (1u << 4)
#define EP_CR_ARRAY_ALL (EP_CR_ARRAY_ADJACENT_8 | EP_CR_ARRAY_ADJACENT_16 | \
                         EP_CR_ARRAY_ADJACENT_16B | EP_CR_ARRAY_CONFIRMED_32 | \
                         EP_CR_ARRAY_PEER_KEYED)

extern "C" {

typedef enum EP_CR_STATUS : UINT32 {
    EP_CR_OK = 0,
    EP_CR_INVALID_ARGUMENT = 1,
    EP_CR_INVALID_CONTEXT = 2,
    EP_CR_BUILD_MISMATCH = 3,
    EP_CR_INDEX_REJECTED = 4,
    EP_CR_DUPLICATE_PEER = 5,
    EP_CR_DUPLICATE_RESOURCE = 6,
    EP_CR_INDEX_OCCUPIED = 7,
    EP_CR_STALE_GENERATION = 8,
    EP_CR_NOT_FOUND = 9,
    EP_CR_CALLBACK_REJECTED = 10,
    EP_CR_ROLLBACK_REQUIRED = 11,
    EP_CR_QUIESCENCE_REQUIRED = 12,
    EP_CR_MIGRATION_IN_PROGRESS = 13,
    EP_CR_MIGRATION_NOT_PREPARED = 14,
    EP_CR_GENERATION_EXHAUSTED = 15,
    EP_CR_ALREADY_DONE = 16,
    EP_CR_INVARIANT_BROKEN = 17,
} EP_CR_STATUS;

typedef enum EP_CR_SLOT_STATE : UINT8 {
    EP_CR_FREE = 0,
    EP_CR_PENDING = 1,
    EP_CR_CONFIRMED = 2,
    EP_CR_ROLLBACK = 3,
} EP_CR_SLOT_STATE;

typedef enum EP_CR_EVENT : UINT32 {
    EP_CR_EVENT_APPEND = 1,
    EP_CR_EVENT_CONFIRM = 2,
    EP_CR_EVENT_REMOVE = 3,
    EP_CR_EVENT_KICKED = 4,
    EP_CR_EVENT_RESET = 5,
    EP_CR_EVENT_ROLLBACK = 6,
    EP_CR_EVENT_MIGRATION_BEGIN = 7,
    EP_CR_EVENT_MIGRATION_COMMIT = 8,
    EP_CR_EVENT_MIGRATION_ABORT = 9,
} EP_CR_EVENT;

typedef struct EP_CR_TOKEN {
    UINT8 network_index;
    UINT8 reserved[3];
    UINT32 generation;
} EP_CR_TOKEN;

typedef struct EP_CR_SLOT {
    UINT8 state;
    UINT8 reserved[3];
    UINT32 generation;
    UINT64 peer_id;
    UINT64 resource_handle;
    UINT32 network_index;
    UINT32 array_membership_mask;
} EP_CR_SLOT;

typedef EP_CR_STATUS (__cdecl *EP_CR_SLOT_CALLBACK)(
    void* context, EP_CR_EVENT event, const EP_CR_SLOT* slot,
    UINT32 array_group_mask);
typedef EP_CR_STATUS (__cdecl *EP_CR_OWNER_CALLBACK)(
    void* context, EP_CR_EVENT event, UINT64 owner_key, UINT32 owner_epoch);

typedef struct EP_CR_CALLBACKS {
    UINT32 size;
    UINT32 version;
    void* context;
    EP_CR_SLOT_CALLBACK slot_callback;
    EP_CR_OWNER_CALLBACK owner_callback;
} EP_CR_CALLBACKS;

typedef struct EP_CLIENT_REPLICATION_SIDECAR {
    UINT32 magic;
    UINT32 version;
    UINT32 build;
    UINT32 initialized;
    UINT32 active_count;
    UINT32 confirmed_count;
    UINT32 callback_leases;
    UINT32 migration_in_progress;
    UINT64 owner_key;
    UINT32 owner_epoch;
    UINT32 next_lease_id;
    UINT64 pending_owner_key;
    UINT32 pending_owner_epoch;
    UINT32 pending_transaction_id;
    SRWLOCK lock;
    EP_CR_CALLBACKS callbacks;
    UINT32 generation[EP_CR_CAPACITY];
    UINT32 lease_id[EP_CR_CAPACITY];
    EP_CR_SLOT slots[EP_CR_CAPACITY];
    // Independent ordinal views. An entry is a stable network index, never
    // another array's ordinal. Each count is independent.
    UINT32 array_count[5];
    UINT8 ordinal_to_index[5][EP_CR_CAPACITY];
} EP_CLIENT_REPLICATION_SIDECAR;

__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_init(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar, UINT32 build,
    const EP_CR_CALLBACKS* callbacks, UINT64 owner_key, UINT32 owner_epoch);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_destroy(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_append(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar, UINT8 network_index,
    UINT64 peer_id, UINT64 resource_handle, UINT32 array_membership_mask,
    EP_CR_TOKEN* out_token);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_confirm(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar, EP_CR_TOKEN token);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_remove(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar, EP_CR_TOKEN token);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_kick(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar, EP_CR_TOKEN token);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_retry_rollback(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar, EP_CR_TOKEN token);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_reset(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_callback_enter(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar, EP_CR_TOKEN token,
    UINT32* out_lease_id);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_callback_leave(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar, EP_CR_TOKEN token,
    UINT32 lease_id);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_migration_begin(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar, UINT64 owner_key,
    UINT32 owner_epoch, UINT32 transaction_id);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_migration_commit(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar, UINT32 transaction_id);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_migration_abort(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar, UINT32 transaction_id);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_get(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar, UINT8 network_index,
    EP_CR_SLOT* out_slot);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_validate(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar);
__declspec(dllexport) EP_CR_STATUS __cdecl ep_cr_get_array(
    EP_CLIENT_REPLICATION_SIDECAR* sidecar, UINT32 array_group,
    UINT8* out_network_indexes, UINT32* out_count);
// This offline contract cannot authorize production, regardless of callbacks.
__declspec(dllexport) UINT32 __cdecl ep_cr_production_enabled();
__declspec(dllexport) UINT32 __cdecl ep_cr_capacity();
__declspec(dllexport) UINT32 __cdecl ep_cr_array_group_mask();

}
