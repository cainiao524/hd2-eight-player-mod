#include "ep_hellforge.h"
#include <cstring>
#include <initializer_list>

int EpHellforgeAdapter::init(const HfApi* api, HfMod* mod) {
    // Some registrations may survive a failed init. Never reactivate them by retrying.
    if (attempted_) return 1;
    attempted_ = true;
    if (!api || !mod || api->version < 13 ||
        api->size < offsetof(HfApi, game_state) + sizeof(api->game_state)) return 1;
    if (!api->log || !api->build_id || !api->session || !api->subscribe ||
        !api->on_game_thread || !api->game_state) return 1;
    const char* build = api->build_id();
    if (!build || std::strcmp(build, "25480438") != 0) return 1;
    api_ = api;
    mod_ = mod;

    // Reuse the original contract unchanged. This baseline is a conservative
    // policy ceiling from the old project, NOT HellForge runtime verification.
    EP_CAPACITY_CONTRACT candidate{};
    candidate.version = EP_CAPACITY_CONTRACT_VERSION;
    candidate.build = EP_CAPACITY_BUILD;
    candidate.configured_max_players = state_.requested_players;
    candidate.peer_capacity = candidate.roster_capacity = candidate.entity_capacity = 4;
    candidate.resource_capacity = candidate.network_capacity = candidate.verified_capacity = 4;
    EP_CAPACITY_REPORT report{};
    state_.request_status = ep_capacity_validate(&candidate, &report);
    if (state_.request_status != EP_CAPACITY_CONFIGURED_EXCEEDS_VERIFIED) return 1;

    for (uint32_t kind : {HF_ON_STATE, HF_ON_PLAYER_SPAWN, HF_ON_PLAYER_DOWN}) {
        if (!api_->subscribe(mod_, kind, event, this, 0)) {
            api_->log(mod_, "EP_HF inactive: event registration failed; no capacity changes applied.");
            return 1;
        }
    }
    // Both subscribe and on_game_thread return 1 on success (unlike api->on).
    if (!api_->on_game_thread(mod_, tick, this)) {
        api_->log(mod_, "EP_HF inactive: tick registration failed; no capacity changes applied.");
        return 1;
    }
    state_.active = true;
    enabled_.store(true, std::memory_order_release);
    api_->log(mod_, "EP_HF research adapter ready: requested=8 applied=0 provider=unbound runtime_verified=false.");
    return 0;
}

void EpHellforgeAdapter::refresh() {
    HfSession session{};
    api_->session(mod_, &session);
    if (session.role > HF_SESSION_JOINER) {
        state_.active = false;
        enabled_.store(false, std::memory_order_release);
        api_->log(mod_, "EP_HF inactive: unknown session role.");
        return;
    }
    if (!have_session_ || state_.role != session.role || state_.session_version != session.version) {
        state_.spawn_events = state_.down_events = 0;
        state_.role = session.role;
        state_.session_version = session.version;
        have_session_ = true;
        // Do not log host names, peer IDs or paths; role/version suffice for this adapter.
        api_->log(mod_, "EP_HF session role=%u version=%u; observation counters reset; provider=unbound.",
                  state_.role, state_.session_version);
    }
    state_.game_state = api_->game_state(mod_);
}

void EpHellforgeAdapter::tick(HfMod* mod, float, void* user) {
    auto* self = static_cast<EpHellforgeAdapter*>(user);
    if (!self || !self->enabled_.load(std::memory_order_acquire) || mod != self->mod_) return;
    self->refresh();
}

void EpHellforgeAdapter::event(HfMod* mod, const HfEventInfo* info, void* user) {
    auto* self = static_cast<EpHellforgeAdapter*>(user);
    if (!self || !self->enabled_.load(std::memory_order_acquire) || mod != self->mod_) return;
    if (!info || info->size < sizeof(HfEventInfo)) { ++self->state_.rejected_events; return; }
    self->refresh();
    if (!self->state_.active) return;
    if (info->kind == HF_ON_STATE) {
        if (info->size < sizeof(HfStateEvent)) { ++self->state_.rejected_events; return; }
        const auto* e = reinterpret_cast<const HfStateEvent*>(info);
        self->api_->log(mod, "EP_HF state %u -> %u; mission/roster acceptance remains unverified.", e->from, e->to);
    } else if (info->kind == HF_ON_PLAYER_SPAWN || info->kind == HF_ON_PLAYER_DOWN) {
        if (info->size < sizeof(HfPlayerEvent)) { ++self->state_.rejected_events; return; }
        // Events are observations only. Spawn can mean reinforcement, and no SDK
        // leave event gives a complete roster. Never derive joined_players here.
        auto& count = info->kind == HF_ON_PLAYER_SPAWN ? self->state_.spawn_events : self->state_.down_events;
        ++count;
        self->api_->log(mod, "EP_HF player event kind=%u count=%llu; not a roster admission.",
                       info->kind, static_cast<unsigned long long>(count));
    } else ++self->state_.rejected_events;
}

static EpHellforgeAdapter adapter;
extern "C" HF_MOD_EXPORT int hellforge_mod_init(const HfApi* api, HfMod* mod) {
    return adapter.init(api, mod);
}
