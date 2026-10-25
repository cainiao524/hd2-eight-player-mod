#include "ep_hellforge.h"
#include <cstdio>
#include <cstdlib>
#include <map>
#include <vector>

struct HfMod { int synthetic; };
static unsigned checks;
static void log_stub(HfMod*, const char*, ...) {}
static void check(bool ok, const char* what) {
    ++checks;
    if (!ok) { std::fprintf(stderr, "FAIL: %s\n", what); std::exit(1); }
}
struct Registration { HfListener fn; void* user; };
struct Fixture {
    HfApi api{};
    HfMod mod{};
    HfSession session{};
    uint32_t state = HF_STATE_SHIP;
    const char* build = "25480438";
    int fail_kind = -1, tick_success = 1;
    HfTickCallback tick = nullptr;
    void* tick_user = nullptr;
    std::map<uint32_t, Registration> listeners;
    unsigned reads = 0, writes = 0, hooks = 0;
    static Fixture* current;
    Fixture() {
        current = this;
        api.version = 13; api.size = sizeof api;
        api.log = log_stub;
        api.build_id = []() -> const char* { return current->build; };
        api.session = [](HfMod*, HfSession* out) { *out = current->session; };
        api.game_state = [](HfMod*) { return current->state; };
        api.subscribe = [](HfMod*, uint32_t kind, HfListener f, void* u, int32_t) {
            if (static_cast<int>(kind) == current->fail_kind) return 0;
            current->listeners[kind] = {f, u}; return 1;
        };
        api.on_game_thread = [](HfMod*, HfTickCallback f, void* u) {
            current->tick = f; current->tick_user = u; return current->tick_success;
        };
        api.read = [](uintptr_t, void*, size_t) { ++current->reads; return 1; };
        api.write = [](uintptr_t, const void*, size_t) { ++current->writes; return 1; };
        api.hook = [](HfMod*, uintptr_t, void*, void**) { ++current->hooks; return 1; };
    }
    void emit(const HfEventInfo* info, uint32_t registered_kind) {
        auto r = listeners.at(registered_kind); r.fn(&mod, info, r.user);
    }
    void step() { tick(&mod, 0.016f, tick_user); }
};
Fixture* Fixture::current = nullptr;

int main(int argc, char** argv) {
    { Fixture f; EpHellforgeAdapter a; check(a.init(nullptr, &f.mod) != 0, "null API"); }
    { Fixture f; EpHellforgeAdapter a; f.api.version = 12;
      check(a.init(&f.api, &f.mod) != 0 && f.listeners.empty(), "old SDK before callbacks"); }
    { Fixture f; EpHellforgeAdapter a; f.api.size = offsetof(HfApi, game_state);
      check(a.init(&f.api, &f.mod) != 0 && f.listeners.empty(), "truncated table"); }
    { Fixture f; EpHellforgeAdapter a; f.build = "25480439";
      check(a.init(&f.api, &f.mod) != 0 && f.listeners.empty(), "wrong build"); }
    { Fixture f; EpHellforgeAdapter a; f.build = nullptr;
      check(a.init(&f.api, &f.mod) != 0, "missing build"); }
    { Fixture f; EpHellforgeAdapter a; f.api.session = nullptr;
      check(a.init(&f.api, &f.mod) != 0 && f.listeners.empty(), "missing session API"); }
    { Fixture f; EpHellforgeAdapter a; f.fail_kind = HF_ON_PLAYER_DOWN;
      check(a.init(&f.api, &f.mod) != 0 && !a.snapshot().active, "partial registration disables adapter");
      HfPlayerEvent e{{sizeof e, HF_ON_PLAYER_SPAWN, 1}, 11, 12, 1};
      f.emit(&e.info, HF_ON_PLAYER_SPAWN);
      check(a.snapshot().spawn_events == 0, "surviving callback inert after failure");
      f.fail_kind = -1; check(a.init(&f.api, &f.mod) != 0, "failed init cannot be retried"); }
    { Fixture f; EpHellforgeAdapter a; f.tick_success = 0;
      check(a.init(&f.api, &f.mod) != 0 && !a.snapshot().active, "tick failure");
      f.step(); check(a.snapshot().game_state == HF_STATE_NONE, "failed tick remains inert"); }
    { Fixture f; EpHellforgeAdapter a;
      check(a.init(&f.api, &f.mod) == 0 && a.snapshot().active, "SDK init succeeds");
      check(a.init(&f.api, &f.mod) != 0 && a.snapshot().active, "duplicate init preserves existing adapter");
      f.step(); check(a.snapshot().game_state == HF_STATE_SHIP, "game thread observes state");
      for (uint64_t i = 1; i <= 8; ++i) {
          HfPlayerEvent e{{sizeof e, HF_ON_PLAYER_SPAWN, i}, i, static_cast<uint32_t>(i), 0};
          f.emit(&e.info, HF_ON_PLAYER_SPAWN);
      }
      check(a.snapshot().spawn_events == 8, "events counted without four-entry local array");
      HfPlayerEvent down{{sizeof down, HF_ON_PLAYER_DOWN, 9}, 1, 1, 0};
      f.emit(&down.info, HF_ON_PLAYER_DOWN); check(a.snapshot().down_events == 1, "down observation");
      HfEventInfo short_event{sizeof(HfEventInfo), HF_ON_PLAYER_SPAWN, 10};
      f.emit(&short_event, HF_ON_PLAYER_SPAWN); f.emit(nullptr, HF_ON_PLAYER_SPAWN);
      check(a.snapshot().rejected_events == 2 && a.snapshot().spawn_events == 8, "malformed events rejected");
      f.session.role = HF_SESSION_JOINER; f.session.version = 2; f.step();
      check(a.snapshot().role == HF_SESSION_JOINER && a.snapshot().spawn_events == 0, "role/version invalidates observations");
      check(a.snapshot().applied_players == 0 && !a.snapshot().provider_bound && !a.snapshot().runtime_verified,
            "events never grant capacity or proof");
      check(a.snapshot().request_status == EP_CAPACITY_CONFIGURED_EXCEEDS_VERIFIED, "original contract rejects eight");
      f.session.role = 99; f.step(); check(!a.snapshot().active, "unknown role disables adapter");
      check(f.reads == 0 && f.writes == 0 && f.hooks == 0, "no raw memory or hook API used"); }
    if (argc == 2) {
        auto dll = LoadLibraryA(argv[1]);
        check(dll != nullptr, "built DLL loads in synthetic test process");
        auto init = reinterpret_cast<int (*)(const HfApi*, HfMod*)>(GetProcAddress(dll, "hellforge_mod_init"));
        check(init != nullptr, "HellForge C ABI export");
        Fixture f;
        check(init(&f.api, &f.mod) == 0, "built DLL initializes with fake SDK only");
        f.step();
        check(f.reads == 0 && f.writes == 0 && f.hooks == 0, "built DLL uses no raw memory or hook API");
        FreeLibrary(dll);
    }
    std::printf("{\"suite\":\"hellforge_adapter\",\"checks\":%u,\"passed\":true,\"game_access\":false}\n", checks);
}
