#pragma once
#include "../Bridge/ep_native_bridge.h"

// Our Lua/native ABI, not a recovered HD2 ABI. Only a reviewed native adapter
// may bind the controller; Lua can query or queue a versioned request only.
#define EP_CONTROL_ABI 1u
enum EP_CONTROL_STATUS : UINT32 {
    EP_CTL_OK, EP_CTL_UNBOUND, EP_CTL_BUSY, EP_CTL_ABI_MISMATCH,
    EP_CTL_NOT_READY, EP_CTL_HOST_REQUIRED, EP_CTL_STALE, EP_CTL_INVALID,
    EP_CTL_REJECTED, EP_CTL_PENDING, EP_CTL_ROLLBACK_REQUIRED
};
struct EP_CONTROL_REQUEST {
    UINT32 size, abi, binding_epoch, authority_epoch, expected_generation;
    EP_CAPACITY_REQUEST config;
};
struct EP_CONTROL_SNAPSHOT {
    UINT32 size, abi, status, binding_epoch, authority_epoch;
    UINT32 host_authority, client_compatible, pending, last_result;
    EP_CAPACITY_CONTRACT capacity;
    EP_CAPACITY_REQUEST pending_config;
};
struct EP_CONTROL_ENVIRONMENT {
    UINT32 authority_epoch;
    BOOL host_authority, client_compatible, build_verified, bindings_ready;
    BOOL mission_active, quiescent, all_layers_reserved;
};
struct EP_CONTROL_PROVIDER {
    UINT32 size, abi;
    // Must freshly check authority, fingerprints, ABI and native lifetime.
    // No callback may reenter or mutate the bridge's sidecar/contract.
    BOOL (__cdecl *inspect)(void* owner, EP_CONTROL_ENVIRONMENT* out);
    // Success means ALL Session/Party/Peer/Roster/Entity/resource capacities,
    // host metadata and client acknowledgements committed synchronously.
    // Returning false (including partial work) is always followed by rollback.
    BOOL (__cdecl *commit)(void* owner, const EP_CAPACITY_CONTRACT* before,
                          const EP_CAPACITY_CONTRACT* after);
    // Idempotent, synchronous compensation for both preparation and commit.
    BOOL (__cdecl *rollback)(void* owner, const EP_CAPACITY_CONTRACT* before);
};

// Native lifecycle entry points are deliberately not exported to Lua.
EP_CONTROL_STATUS ep_control_bind(EP_NATIVE_BRIDGE*, const EP_CONTROL_PROVIDER*);
EP_CONTROL_STATUS ep_control_unbind();
EP_CONTROL_STATUS ep_control_boundary(EP_CAPACITY_APPLY_MODE);

extern "C" {
__declspec(dllexport) UINT32 __cdecl ep_control_abi();
__declspec(dllexport) UINT32 __cdecl ep_control_snapshot_size();
__declspec(dllexport) UINT32 __cdecl ep_control_request_size();
__declspec(dllexport) UINT32 __cdecl ep_control_snapshot(EP_CONTROL_SNAPSHOT*, UINT32 size);
__declspec(dllexport) UINT32 __cdecl ep_control_submit(const EP_CONTROL_REQUEST*, UINT32 size);
}
