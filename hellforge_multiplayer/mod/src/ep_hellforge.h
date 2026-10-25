#pragma once
#include <atomic>
#include <hellforge_mod.h>
#include "core/ep_capacity_contract.h"

// This is observation, not an authoritative roster or a capacity provider.
struct EpHellforgeSnapshot {
    bool active = false;
    uint32_t role = HF_SESSION_SOLO, session_version = 0, game_state = HF_STATE_NONE;
    uint64_t spawn_events = 0, down_events = 0, rejected_events = 0;
    uint32_t requested_players = 8, applied_players = 0;
    bool provider_bound = false, runtime_verified = false;
    EP_CAPACITY_STATUS request_status = EP_CAPACITY_CONFIGURED_EXCEEDS_VERIFIED;
};

class EpHellforgeAdapter {
public:
    int init(const HfApi* api, HfMod* mod);
    const EpHellforgeSnapshot& snapshot() const { return state_; }
private:
    const HfApi* api_ = nullptr;
    HfMod* mod_ = nullptr;
    bool attempted_ = false, have_session_ = false;
    // init runs on the loader thread; callbacks run on the game thread.
    std::atomic<bool> enabled_{false};
    EpHellforgeSnapshot state_{};
    void refresh();
    static void tick(HfMod*, float, void*);
    static void event(HfMod*, const HfEventInfo*, void*);
};
