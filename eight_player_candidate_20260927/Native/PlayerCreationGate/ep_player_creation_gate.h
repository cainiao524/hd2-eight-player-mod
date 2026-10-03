#pragma once

#include <windows.h>
#include <stdint.h>

// Fixed-build player-creation adapter.  This is deliberately separate from
// the broad capacity patch: the gate is only safe to widen after the resource,
// component and roster continuations have been supplied by the caller.
#define EP_PC_MAGIC 0x45504347u /* EPCG */
#define EP_PC_VERSION 3u
#define EP_PC_BUILD 25480438u
#define EP_PC_GATE_RVA 0x1086460u
#define EP_PC_RESOURCE_RVA 0xFDC140u
#define EP_PC_ROSTER_RVA 0x608B60u
#define EP_PC_CAPACITY 8u
#define EP_PC_SITE_MAX 3u
#define EP_PC_GATE_BYTES 9u

#ifdef _WIN32
#define EP_PC_EXPORT extern "C" __declspec(dllexport)
#else
#define EP_PC_EXPORT extern "C"
#endif

extern "C" {

typedef enum EP_PC_STATUS : UINT32 {
    EP_PC_OK = 0,
    EP_PC_INVALID_ARGUMENT = 1,
    EP_PC_INVALID_CONTEXT = 2,
    EP_PC_BUILD_MISMATCH = 3,
    EP_PC_SITE_MISMATCH = 4,
    EP_PC_DOWNSTREAM_UNREADY = 5,
    EP_PC_CALLBACK_MISSING = 6,
    EP_PC_INDEX_REJECTED = 7,
    EP_PC_DUPLICATE = 8,
    EP_PC_FULL = 9,
    EP_PC_CALLBACK_REJECTED = 10,
    EP_PC_ROLLBACK_FAILED = 11,
    EP_PC_STALE_TOKEN = 12,
    EP_PC_ALREADY_RELEASED = 13,
    EP_PC_BUSY = 14,
    EP_PC_NOT_PATCHED = 15,
    EP_PC_PATCHED = 16,
    EP_PC_WRITE_FAILED = 17,
    EP_PC_QUIESCE_FAILED = 18,
    EP_PC_INVARIANT_BROKEN = 19,
} EP_PC_STATUS;

typedef enum EP_PC_SLOT_STATE : UINT8 {
    EP_PC_FREE = 0,
    EP_PC_PENDING = 1,
    EP_PC_ACTIVE = 2,
    EP_PC_REMOVING = 3,
} EP_PC_SLOT_STATE;

typedef struct EP_PC_TOKEN {
    UINT8 index;
    UINT8 reserved[3];
    UINT32 generation;
    UINT32 owner_epoch;
} EP_PC_TOKEN;

typedef struct EP_PC_RESOURCE {
    UINT8 network_index;
    UINT8 reserved[3];
    UINT32 generation;
    UINT64 peer_id;
    UINT64 resource_handle;
    UINT64 resource_hash;
    UINT64 opaque;
} EP_PC_RESOURCE;

// These callbacks are the missing runtime ABI boundary.  The adapter owns
// ordering, generation and rollback; a production provider must implement
// them against the actual 25480438 host/client objects.
typedef EP_PC_STATUS (__cdecl *EP_PC_RETAIN_CB)(void* owner);
typedef void (__cdecl *EP_PC_RELEASE_OWNER_CB)(void* owner);
typedef EP_PC_STATUS (__cdecl *EP_PC_RESOLVE_RESOURCE_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT64 resource_hash,
    UINT8 network_index, UINT32 generation, EP_PC_RESOURCE* out_resource);
typedef EP_PC_STATUS (__cdecl *EP_PC_COMPONENTS_CB)(
    void* owner, const EP_PC_RESOURCE* resource);
typedef EP_PC_STATUS (__cdecl *EP_PC_ROSTER_CB)(
    void* owner, const EP_PC_RESOURCE* resource);
typedef EP_PC_STATUS (__cdecl *EP_PC_CLEANUP_CB)(
    void* owner, const EP_PC_RESOURCE* resource);
typedef EP_PC_STATUS (__cdecl *EP_PC_ROLLBACK_CB)(
    void* owner, const EP_PC_RESOURCE* resource, UINT32 completed_mask);

typedef struct EP_PC_CALLBACKS {
    void* owner;
    EP_PC_RETAIN_CB retain_owner;
    EP_PC_RELEASE_OWNER_CB release_owner;
    EP_PC_RESOLVE_RESOURCE_CB resolve_resource;
    EP_PC_COMPONENTS_CB dispatch_components;
    EP_PC_ROSTER_CB insert_roster;
    EP_PC_CLEANUP_CB cleanup_roster;
    EP_PC_CLEANUP_CB cleanup_components;
    EP_PC_ROLLBACK_CB rollback;
} EP_PC_CALLBACKS;

// A patch writer is intentionally injected by the caller.  The module never
// obtains a process handle or changes memory by itself.  quiesce/resume must
// stop all callers of the gate before writing/restoring the nine-byte site.
typedef EP_PC_STATUS (__cdecl *EP_PC_QUIESCE_CB)(void* owner);
typedef void (__cdecl *EP_PC_RESUME_CB)(void* owner);
typedef EP_PC_STATUS (__cdecl *EP_PC_WRITE_CB)(void* owner, uintptr_t address,
                                                const BYTE* bytes, SIZE_T size);
typedef EP_PC_STATUS (__cdecl *EP_PC_DOWNSTREAM_READY_CB)(void* owner);

typedef struct EP_PC_PATCH_BACKEND {
    void* owner;
    EP_PC_QUIESCE_CB quiesce;
    EP_PC_RESUME_CB resume;
    EP_PC_WRITE_CB write;
    EP_PC_DOWNSTREAM_READY_CB downstream_ready;
} EP_PC_PATCH_BACKEND;

typedef struct EP_PC_SITE {
    UINT32 rva;
    const BYTE* expected;
    SIZE_T size;
} EP_PC_SITE;

typedef struct EP_PC_PREFLIGHT {
    UINT32 build;
    UINT32 gate_rva;
    UINT32 resource_rva;
    UINT32 roster_rva;
    BOOL build_ok;
    BOOL image_ok;
    BOOL gate_ok;
    BOOL downstream_sites_ok;
    BOOL callbacks_ok;
    BOOL backend_ok;
    BOOL downstream_ready;
    BOOL ready;
} EP_PC_PREFLIGHT;

typedef struct EP_PC_SLOT {
    UINT8 state;
    UINT8 completed_mask;
    UINT8 owner_held;
    // A failed admission rollback is a different cleanup transaction from a
    // normal departure.  Keep the distinction in the slot so a retry cannot
    // accidentally invoke roster/component departure callbacks for a
    // resource whose creation transaction never committed.
    UINT8 rollback_pending;
    UINT32 generation;
    UINT32 owner_epoch;
    EP_PC_RESOURCE resource;
} EP_PC_SLOT;

typedef struct EP_PLAYER_CREATION_ADAPTER {
    UINT32 magic;
    UINT32 version;
    UINT32 build;
    UINT32 initialized;
    // Synchronous mutators include external callbacks; overlapping calls return BUSY.
    volatile LONG operation_busy;
    UINT32 owner_epoch;
    UINT32 inflight;
    UINT32 gate_patched;
    UINT32 patch_size;
    uintptr_t patch_address;
    BYTE original_gate[EP_PC_GATE_BYTES];
    BYTE patched_gate[EP_PC_GATE_BYTES];
    EP_PC_CALLBACKS callbacks;
    EP_PC_PATCH_BACKEND backend;
    SRWLOCK lock;
    UINT32 generations[EP_PC_CAPACITY];
    EP_PC_SLOT slots[EP_PC_CAPACITY];
} EP_PLAYER_CREATION_ADAPTER;

EP_PC_EXPORT EP_PC_STATUS __cdecl ep_pc_init(
    EP_PLAYER_CREATION_ADAPTER* adapter, UINT32 build,
    const EP_PC_CALLBACKS* callbacks);
EP_PC_EXPORT EP_PC_STATUS __cdecl ep_pc_destroy(
    EP_PLAYER_CREATION_ADAPTER* adapter);
EP_PC_EXPORT EP_PC_STATUS __cdecl ep_pc_preflight(
    UINT32 build, const BYTE* image_base, SIZE_T image_size,
    const EP_PC_SITE* gate_site, const EP_PC_SITE* downstream_sites,
    UINT32 downstream_count, const EP_PC_CALLBACKS* callbacks,
    const EP_PC_PATCH_BACKEND* backend, EP_PC_PREFLIGHT* out);
EP_PC_EXPORT EP_PC_STATUS __cdecl ep_pc_prepare_patch(
    EP_PLAYER_CREATION_ADAPTER* adapter, UINT32 build,
    const BYTE* image_base, SIZE_T image_size,
    const EP_PC_SITE* gate_site, const EP_PC_SITE* downstream_sites,
    UINT32 downstream_count, const EP_PC_PATCH_BACKEND* backend,
    EP_PC_PREFLIGHT* out);
EP_PC_EXPORT EP_PC_STATUS __cdecl ep_pc_install_gate_patch(
    EP_PLAYER_CREATION_ADAPTER* adapter);
EP_PC_EXPORT EP_PC_STATUS __cdecl ep_pc_remove_gate_patch(
    EP_PLAYER_CREATION_ADAPTER* adapter);
EP_PC_EXPORT EP_PC_STATUS __cdecl ep_pc_admit(
    EP_PLAYER_CREATION_ADAPTER* adapter, UINT8 network_index,
    UINT64 peer_id, UINT64 resource_handle, UINT64 resource_hash,
    EP_PC_TOKEN* out_token);
EP_PC_EXPORT EP_PC_STATUS __cdecl ep_pc_depart(
    EP_PLAYER_CREATION_ADAPTER* adapter, EP_PC_TOKEN token);
EP_PC_EXPORT EP_PC_STATUS __cdecl ep_pc_get(
    EP_PLAYER_CREATION_ADAPTER* adapter, UINT8 network_index,
    EP_PC_SLOT* out_slot);
EP_PC_EXPORT EP_PC_STATUS __cdecl ep_pc_validate(
    EP_PLAYER_CREATION_ADAPTER* adapter);
EP_PC_EXPORT UINT32 __cdecl ep_pc_capacity();

}
