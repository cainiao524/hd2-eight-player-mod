#pragma once

#include "ep_player_creation_gate.h"
#include "../ClientReplication/ep_replication_bridge.h"

#define EP_PCR_MAGIC 0x45504352u /* "EPCR" */
#define EP_PCR_VERSION 1u
#define EP_PCR_CALLBACK_VERSION 1u

extern "C" {

typedef EP_PC_STATUS (__cdecl *EP_PCR_RESOLVE_CB)(
    void* owner, UINT64 peer_id, UINT64 resource_handle, UINT64 resource_hash,
    UINT8 network_index, UINT32 generation, EP_PC_RESOURCE* out_resource);
typedef EP_PC_STATUS (__cdecl *EP_PCR_COMPONENT_CB)(
    void* owner, const EP_PC_RESOURCE* resource);
typedef EP_PC_STATUS (__cdecl *EP_PCR_RETAIN_CB)(void* owner);
typedef void (__cdecl *EP_PCR_RELEASE_CB)(void* owner);

// This adapter composes the fixed-index creation transaction with the
// replication bridge.  The replication bridge remains the owner of its
// authoritative index allocator, resource callbacks and replication table;
// this layer only verifies that the caller-supplied creation index is the same
// index returned by that bridge and carries cleanup retries across both state
// machines.
typedef struct EP_PCR_CONFIG {
    UINT32 version;
    UINT32 size;
    void* owner;
    EP_PCR_RETAIN_CB retain_owner;
    EP_PCR_RELEASE_CB release_owner;
    EP_PCR_RESOLVE_CB resolve_resource;
    EP_PCR_COMPONENT_CB dispatch_components;
    EP_PCR_COMPONENT_CB cleanup_components;
} EP_PCR_CONFIG;

typedef struct EP_PLAYER_CREATION_REPLICATION_ADAPTER {
    UINT32 magic;
    UINT32 version;
    UINT32 initialized;
    UINT32 reserved;
    EP_REPLICATION_BRIDGE* replication;
    EP_PCR_CONFIG config;
    EP_PC_CALLBACKS callbacks;
    EP_PLAYER_CREATION_ADAPTER creation;
    EP_BRIDGE_ADMISSION admissions[EP_PC_CAPACITY];
    UINT8 bridge_state[EP_PC_CAPACITY];
} EP_PLAYER_CREATION_REPLICATION_ADAPTER;

__declspec(dllexport) EP_PC_STATUS __cdecl ep_pcr_init(
    EP_PLAYER_CREATION_REPLICATION_ADAPTER* adapter,
    EP_REPLICATION_BRIDGE* replication, const EP_PCR_CONFIG* config);
__declspec(dllexport) EP_PC_STATUS __cdecl ep_pcr_destroy(
    EP_PLAYER_CREATION_REPLICATION_ADAPTER* adapter);
__declspec(dllexport) EP_PC_STATUS __cdecl ep_pcr_admit(
    EP_PLAYER_CREATION_REPLICATION_ADAPTER* adapter, UINT8 network_index,
    UINT64 peer_id, UINT64 resource_handle, UINT64 resource_hash,
    EP_PC_TOKEN* out_token);
__declspec(dllexport) EP_PC_STATUS __cdecl ep_pcr_depart(
    EP_PLAYER_CREATION_REPLICATION_ADAPTER* adapter, EP_PC_TOKEN token);
__declspec(dllexport) EP_PC_STATUS __cdecl ep_pcr_get(
    EP_PLAYER_CREATION_REPLICATION_ADAPTER* adapter, UINT8 network_index,
    EP_PC_SLOT* out_slot);
__declspec(dllexport) EP_PC_STATUS __cdecl ep_pcr_validate(
    EP_PLAYER_CREATION_REPLICATION_ADAPTER* adapter);
__declspec(dllexport) UINT32 __cdecl ep_pcr_capacity();

}
