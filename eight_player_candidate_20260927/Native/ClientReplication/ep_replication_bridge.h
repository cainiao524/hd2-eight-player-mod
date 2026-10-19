#pragma once

#include "ep_client_replication_contract.h"
#include "../Bridge/ep_native_bridge.h"

// Composes the existing admission bridge with the client replication table.
// Call ep_bridge_* on admission; all downstream callbacks remain mandatory.
// This is a local synchronous integration boundary, not a network transport.
#define EP_REPLICATION_BRIDGE_MAGIC 0x45505242u

extern "C" {

// Array membership is supplied for each peer; it is not inferred from index.
typedef EP_BRIDGE_STATUS (__cdecl *EP_REPLICATION_MEMBERSHIP_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT8 network_index,
    UINT32* out_mask);

typedef struct EP_REPLICATION_BRIDGE_SLOT {
    UINT64 peer_id;
    UINT64 resource_handle;
    EP_CR_TOKEN replication_token;
    BOOL native_started;
} EP_REPLICATION_BRIDGE_SLOT;

typedef struct EP_REPLICATION_BRIDGE {
    UINT32 magic;
    EP_BRIDGE_CONFIG downstream;
    EP_REPLICATION_MEMBERSHIP_CB membership;
    EP_NATIVE_BRIDGE admission;
    EP_CLIENT_REPLICATION_SIDECAR replication;
    EP_REPLICATION_BRIDGE_SLOT slots[EP_CR_CAPACITY];
} EP_REPLICATION_BRIDGE;

// Storage must be zero-initialized. The caller owns all callback contexts and
// serializes lifecycle operations, including destroy and direct ep_cr_* use.
// Downstream sites/capacity are still validated by the admission bridge.
// Downstream remove must undo partial confirm/create and be safe to retry;
// retain/release must not throw. Callbacks complete synchronously.
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_replication_bridge_init(
    EP_REPLICATION_BRIDGE* adapter, const EP_BRIDGE_CONFIG* downstream,
    const EP_CR_CALLBACKS* replication_callbacks,
    EP_REPLICATION_MEMBERSHIP_CB membership, UINT64 owner_key, UINT32 owner_epoch);
__declspec(dllexport) EP_BRIDGE_STATUS __cdecl ep_replication_bridge_destroy(
    EP_REPLICATION_BRIDGE* adapter);

}
