#include "ep_capacity_control.h"
#include <cstring>
#include <cstdint>

namespace {
volatile LONG busy = 0;
EP_NATIVE_BRIDGE* bridge = nullptr;
EP_CONTROL_PROVIDER provider{};
UINT32 epoch = 0, pending_authority = 0, pending_generation = 0;
EP_CAPACITY_REQUEST pending_request{};
bool pending = false, rollback_needed = false;
EP_CAPACITY_CONTRACT rollback_before{};
EP_CONTROL_STATUS last_result = EP_CTL_UNBOUND;
struct Guard {
    volatile LONG* lock;
    bool held;
    explicit Guard(volatile LONG* p) : lock(p), held(InterlockedCompareExchange(p, 1, 0) == 0) {}
    ~Guard() { if (held) InterlockedExchange(lock, 0); }
};
bool flag(BOOL b) { return b == FALSE || b == TRUE; }
EP_CONTROL_STATUS inspect(EP_CONTROL_ENVIRONMENT& env, EP_CAPACITY_CONTRACT& c) {
    if (!bridge || bridge->magic != EP_BRIDGE_MAGIC || bridge->version != EP_BRIDGE_VERSION)
        return EP_CTL_UNBOUND;
    if (!provider.inspect(bridge->config.owner, &env) || env.authority_epoch == 0 ||
        !flag(env.host_authority) || !flag(env.client_compatible) ||
        !flag(env.mission_active) || !flag(env.quiescent) ||
        env.build_verified != TRUE || env.bindings_ready != TRUE || !bridge->ready)
        return EP_CTL_NOT_READY;
    c = bridge->capacity_snapshot;
    c.joined_players = bridge->sidecar.active_count;
    c.mission_active = env.mission_active;
    c.quiescent = env.quiescent;
    EP_CAPACITY_REPORT report{};
    if (bridge->config.capacity != &bridge->capacity_snapshot ||
        ep_capacity_validate(&c, &report) != EP_CAPACITY_OK ||
        report.effective_max_players != bridge->sidecar.capacity ||
        ep_sidecar_validate(&bridge->sidecar) != EP_SC_OK)
        return EP_CTL_NOT_READY;
    c.effective_max_players = report.effective_max_players;
    return EP_CTL_OK;
}
bool request_valid(const EP_CAPACITY_REQUEST& r, const EP_CAPACITY_CONTRACT& current) {
    if (r.version != EP_CAPACITY_CONTRACT_VERSION || r.build != EP_CAPACITY_BUILD ||
        r.apply_mode > EP_CAPACITY_RESTART_REQUIRED ||
        !flag(r.allow_join_in_progress) || !flag(r.require_same_mod_version) ||
        (current.mission_active && r.configured_max_players < current.configured_max_players))
        return false;
    auto c = current;
    c.configured_max_players = r.configured_max_players;
    EP_CAPACITY_REPORT report{};
    if (ep_capacity_validate(&c, &report) != EP_CAPACITY_OK) return false;
    // Sparse network indexes are not ordinal counts; shrinking must not hide
    // an occupied high index even if the total count would fit.
    for (UINT32 i = report.effective_max_players; i < EP_SIDECAR_CAPACITY; ++i)
        if (bridge->sidecar.slots[i].state != EP_SC_SLOT_FREE) return false;
    return current.generation != UINT32_MAX;
}
EP_CONTROL_STATUS compensate() {
    if (!provider.rollback(bridge->config.owner, &rollback_before)) {
        rollback_needed = true;
        bridge->reserved |= EP_BRIDGE_CONTROL_FAULT;
        return EP_CTL_ROLLBACK_REQUIRED;
    }
    rollback_needed = false;
    bridge->reserved &= ~EP_BRIDGE_CONTROL_FAULT;
    return EP_CTL_REJECTED;
}
}

EP_CONTROL_STATUS ep_control_bind(EP_NATIVE_BRIDGE* value, const EP_CONTROL_PROVIDER* p) {
    Guard guard(&busy); if (!guard.held) return EP_CTL_BUSY;
    if (bridge) return EP_CTL_BUSY;
    if (!value || !p || p->size != sizeof(*p) || p->abi != EP_CONTROL_ABI ||
        !p->inspect || !p->commit || !p->rollback ||
        value->magic != EP_BRIDGE_MAGIC || value->version != EP_BRIDGE_VERSION ||
        !value->config.retain_owner || !value->config.release_owner || epoch == UINT32_MAX)
        return EP_CTL_INVALID;
    Guard operation(&value->operation_busy); if (!operation.held) return EP_CTL_BUSY;
    if (value->reserved || value->cleanup_count) return EP_CTL_NOT_READY;
    if (value->config.retain_owner(value->config.owner) != EP_BRIDGE_OK) return EP_CTL_NOT_READY;
    bridge = value; provider = *p;
    EP_CONTROL_ENVIRONMENT env{}; EP_CAPACITY_CONTRACT current{};
    const auto result = inspect(env, current);
    if (result != EP_CTL_OK) {
        bridge = nullptr; provider = {};
        value->config.release_owner(value->config.owner);
        return result;
    }
    ++epoch; pending = rollback_needed = false; pending_request = {};
    value->reserved |= EP_BRIDGE_CONTROL_BOUND;
    return last_result = EP_CTL_OK;
}

EP_CONTROL_STATUS ep_control_unbind() {
    Guard guard(&busy); if (!guard.held) return EP_CTL_BUSY;
    if (!bridge) return EP_CTL_UNBOUND;
    Guard operation(&bridge->operation_busy); if (!operation.held) return EP_CTL_BUSY;
    if (rollback_needed) return EP_CTL_ROLLBACK_REQUIRED;
    auto* previous = bridge;
    previous->reserved &= ~EP_BRIDGE_CONTROL_BOUND;
    bridge = nullptr; provider = {}; pending = false; pending_request = {};
    last_result = EP_CTL_UNBOUND;
    previous->config.release_owner(previous->config.owner);
    return EP_CTL_OK;
}

extern "C" UINT32 __cdecl ep_control_snapshot(EP_CONTROL_SNAPSHOT* out, UINT32 size) {
    if (!out || size != sizeof(*out)) return EP_CTL_ABI_MISMATCH;
    *out = {}; out->size = sizeof(*out); out->abi = EP_CONTROL_ABI;
    Guard guard(&busy); if (!guard.held) return out->status = EP_CTL_BUSY;
    if (!bridge) return out->status = EP_CTL_UNBOUND;
    Guard operation(&bridge->operation_busy); if (!operation.held) return out->status = EP_CTL_BUSY;
    EP_CONTROL_ENVIRONMENT env{}; EP_CAPACITY_CONTRACT current{};
    const auto result = inspect(env, current);
    out->binding_epoch = epoch; out->last_result = last_result;
    if (result != EP_CTL_OK) return out->status = result;
    out->authority_epoch = env.authority_epoch;
    out->host_authority = env.host_authority;
    out->client_compatible = env.client_compatible;
    out->capacity = current;
    if (pending && (env.authority_epoch != pending_authority ||
                    current.generation != pending_generation || !env.host_authority)) {
        pending = false; last_result = EP_CTL_STALE; out->last_result = last_result;
    }
    out->pending = pending;
    if (pending) out->pending_config = pending_request;
    return out->status = rollback_needed ? EP_CTL_ROLLBACK_REQUIRED : EP_CTL_OK;
}

extern "C" UINT32 __cdecl ep_control_submit(const EP_CONTROL_REQUEST* request, UINT32 size) {
    if (!request || size != sizeof(*request) || request->size != size || request->abi != EP_CONTROL_ABI)
        return EP_CTL_ABI_MISMATCH;
    Guard guard(&busy); if (!guard.held) return EP_CTL_BUSY;
    if (!bridge) return EP_CTL_UNBOUND;
    Guard operation(&bridge->operation_busy); if (!operation.held) return EP_CTL_BUSY;
    if (rollback_needed) return last_result = EP_CTL_ROLLBACK_REQUIRED;
    EP_CONTROL_ENVIRONMENT env{}; EP_CAPACITY_CONTRACT current{};
    const auto result = inspect(env, current);
    if (result != EP_CTL_OK) return last_result = result;
    if (!env.host_authority) return last_result = EP_CTL_HOST_REQUIRED;
    if (!env.client_compatible || bridge->cleanup_count) return last_result = EP_CTL_NOT_READY;
    if (request->binding_epoch != epoch || request->authority_epoch != env.authority_epoch ||
        request->expected_generation != current.generation) return last_result = EP_CTL_STALE;
    if (!request_valid(request->config, current)) return last_result = EP_CTL_INVALID;
    pending_request = request->config; pending = true;
    pending_generation = current.generation; pending_authority = env.authority_epoch;
    return last_result = EP_CTL_PENDING;
}

EP_CONTROL_STATUS ep_control_boundary(EP_CAPACITY_APPLY_MODE boundary) {
    Guard guard(&busy); if (!guard.held) return EP_CTL_BUSY;
    if (!bridge) return EP_CTL_UNBOUND;
    Guard operation(&bridge->operation_busy); if (!operation.held) return EP_CTL_BUSY;
    EP_CONTROL_ENVIRONMENT env{}; EP_CAPACITY_CONTRACT current{};
    const auto result = inspect(env, current);
    if (result != EP_CTL_OK) return last_result = result;
    if (!env.quiescent) return last_result = EP_CTL_NOT_READY;
    if (rollback_needed) return last_result = compensate();
    if (!pending) return EP_CTL_OK;
    if (!env.host_authority || env.authority_epoch != pending_authority || current.generation != pending_generation) {
        pending = false; return last_result = EP_CTL_STALE;
    }
    if (boundary != pending_request.apply_mode) return EP_CTL_PENDING;
    if (!env.client_compatible || env.all_layers_reserved != TRUE || bridge->cleanup_count)
        return last_result = EP_CTL_NOT_READY;
    if (!request_valid(pending_request, current)) { pending = false; return last_result = EP_CTL_INVALID; }
    auto candidate = current;
    EP_CAPACITY_RESERVATION reservation{TRUE, TRUE}; EP_CAPACITY_REPORT report{};
    if (ep_capacity_apply(&candidate, &pending_request, &reservation, TRUE, &report) != EP_CAPACITY_OK) {
        pending = false; return last_result = EP_CTL_REJECTED;
    }
    rollback_before = current; pending = false;
    if (!provider.commit(bridge->config.owner, &current, &candidate))
        return last_result = compensate();
    // All game consumers and metadata have committed; admission reads this
    // exact owned snapshot and bound. No Lua-owned contract pointer is stored.
    AcquireSRWLockExclusive(&bridge->sidecar.lock);
    bridge->sidecar.capacity = report.effective_max_players;
    bridge->capacity_snapshot = candidate;
    ReleaseSRWLockExclusive(&bridge->sidecar.lock);
    return last_result = EP_CTL_OK;
}
extern "C" UINT32 __cdecl ep_control_abi() { return EP_CONTROL_ABI; }
extern "C" UINT32 __cdecl ep_control_snapshot_size() { return sizeof(EP_CONTROL_SNAPSHOT); }
extern "C" UINT32 __cdecl ep_control_request_size() { return sizeof(EP_CONTROL_REQUEST); }
