/* Real patched loader functions, synthetic buffers in THIS process only.
 * Never call hellforge_loader_start, Watch, ActionsTick or hook installation. */
#include "hellforge_modloader.c"
static unsigned checks, spawns, downs, heals;
#define CHECK(x) do { checks++; if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); exit(1); } } while (0)
static EpHfRosterSnapshot frame;
static uint64_t lease;
static int available = 1, reenter;
static HANDLE entered, releaseRead, unbindStarted;
static uintptr_t fixtureGame;
static int ReadFixture(void* context, uintptr_t game, EpHfRosterSnapshot* out)
{
    (void)context; (void)game;
    if (reenter)
    {
        EpHfRosterSnapshot nested;
        CHECK(!EpRosterUnbind(&g_mods[0], lease));
        CHECK(EpRosterRead(game, &nested) == -1);
    }
    if (entered) { SetEvent(entered); if (WaitForSingleObject(releaseRead, 5000) != WAIT_OBJECT_0) return 0; }
    *out = frame;
    return available;
}
static void FixtureFrame(unsigned count)
{
    memset(&frame, 0, sizeof frame);
    frame.size = sizeof frame; frame.version = 1; frame.capacity = 16; frame.count = count; frame.epoch = 1;
    for (unsigned i = 0; i < count; i++)
        frame.players[i] = (EpHfPlayer){100 + i, 1000 + i, 2000 + i, 3, i == count - 1, i, 1, 0x7FFF, 0};
}
static void Heard(HfMod* mod, const HfEventInfo* e, void* user)
{
    (void)mod; (void)user;
    if (e->kind == HF_ON_PLAYER_SPAWN) spawns++;
    if (e->kind == HF_ON_PLAYER_DOWN) downs++;
    if (e->kind == HF_ON_HEAL) heals++;
}
static DWORD WINAPI Reader(void* p) { EpHfRosterSnapshot out; (void)p; return EpRosterRead(fixtureGame, &out) == 8 ? 0 : 1; }
static DWORD WINAPI Unbinder(void* p) { (void)p; SetEvent(unbindStarted); return EpRosterUnbind(&g_mods[0], lease) ? 0 : 1; }
static void Fixture32(uint8_t* p, size_t at, uint32_t v) { memcpy(p + at, &v, 4); }
static void FixturePtr(uint8_t* p, size_t at, void* v) { memcpy(p + at, &v, sizeof v); }
static void FixtureHash(uint8_t* h, uint32_t* slots, unsigned count)
{
    FixturePtr(h, 0, slots); Fixture32(h, 8, count); Fixture32(h, 12, 0); Fixture32(h, 16, 1);
}
int main(int argc, char** argv)
{
    CHECK(argc == 2);
    /* DLL has no DllMain. LoadLibrary here resolves its private API without starting it. */
    HMODULE built = LoadLibraryA(argv[1]); CHECK(built != NULL);
    const EpHfRosterApi* (*apiFn)(void) = (const EpHfRosterApi* (*)(void))GetProcAddress(built, "hellforge_ep_roster_api_v1");
    CHECK(apiFn != NULL && apiFn()->magic == EP_HF_ROSTER_MAGIC && apiFn()->limit == 16);
    CHECK(FreeLibrary(built));
    g_modCount = 2; g_mods[0].loaded = 1;
    uint8_t* game = calloc(1, 0x3500000);
    uint8_t* manager = calloc(1, 0x430);
    uint8_t* user = calloc(1, 0xB3A0);
    uint8_t* custom = calloc(1, 4096);
    CHECK(game && manager && user && custom); fixtureGame = (uintptr_t)game;
    FixturePtr(game, EVT_PLAYERS, manager); FixturePtr(game, EVT_LOCAL_PEER, user); FixturePtr(game, PSV_MANAGER, custom);
    Fixture32(manager, 0x84, 4);
    for (unsigned i = 0; i < 4; i++) { uint64_t peer = 100 + i; memcpy(manager + 0x2C8 + 0x38 * i, &peer, 8); Fixture32(manager, 0x2E0 + 0x38 * i, 3); }
    EpHfRosterSnapshot out;
    CHECK(EpRosterRead(fixtureGame, &out) == 4 && out.binding == 0);
    Fixture32(manager, 0x84, 5); CHECK(EpRosterRead(fixtureGame, &out) == -1 && out.count == 0);
    Fixture32(manager, 0x84, 4);
    memset(manager + 0x2C8, 0, 8); CHECK(ActPlayerCount(fixtureGame) == 4); /* vacant IDs must not enable solo */
    FixtureFrame(8);
    EpHfRosterProvider provider = {sizeof provider, 1, 16, 0, &frame, ReadFixture};
    CHECK(!EpRosterBind(&g_mods[0], &provider)); /* unknown build */
    strcpy(g_build, "25480438");
    HfMod outsider = {0}; CHECK(!EpRosterBind(&outsider, &provider));
    provider.version = 2; CHECK(!EpRosterBind(&g_mods[0], &provider)); provider.version = 1;
    provider.capacity = 17; CHECK(!EpRosterBind(&g_mods[0], &provider)); provider.capacity = 16;
    lease = EpRosterBind(&g_mods[0], &provider); CHECK(lease != 0);
    CHECK(!EpRosterBind(&g_mods[1], &provider));
    CHECK(!EpRosterUnbind(&g_mods[1], lease) && !EpRosterUnbind(&g_mods[0], lease + 1));
    CHECK(EpRosterRead(fixtureGame, &out) == 8 && out.binding == lease);
    EvpPlayer players[EVT_MAX_PLAYERS];
    CHECK(EvpPlayers(fixtureGame, players) == 8 && ActPlayerCount(fixtureGame) == 8);
    for (unsigned i = 0; i < 8; i++) CHECK(players[i].peer == 100 + i && players[i].avatar == 2000 + i && players[i].local == (i == 7));
    frame.players[7].network_index = 15; CHECK(EpRosterRead(fixtureGame, &out) == 8 && out.players[7].network_index == 15);
    const EpHfRosterSnapshot good = frame;
    for (unsigned bad = 0; bad < 14; bad++)
    {
        frame = good;
        switch (bad) {
        case 0: frame.count = 17; break; case 1: frame.capacity = 8; break;
        case 2: frame.size--; break; case 3: frame.version++; break; case 4: frame.epoch = 0; break;
        case 5: frame.players[7].peer = frame.players[0].peer; break;
        case 6: frame.players[7].network_index = 0; break;
        case 7: frame.players[0].local = 1; break; case 8: frame.players[0].local = 2; break;
        case 9: frame.players[0].generation = 0; break;
        case 10: frame.players[0].player = frame.players[7].player; break;
        case 11: frame.players[0].avatar = frame.players[7].avatar; break;
        case 12: frame.binding = 1; break; case 13: frame.players[0].network_index = 16; break;
        }
        CHECK(EpRosterRead(fixtureGame, &out) == -1 && out.count == 0);
        CHECK(ActPlayerCount(fixtureGame) == -1); /* no four-player fallback */
    }
    frame = good; available = 0; CHECK(EpRosterRead(fixtureGame, &out) == -1); available = 1;
    reenter = 1; CHECK(EpRosterRead(fixtureGame, &out) == 8); reenter = 0;
    CHECK(ApiSubscribe(&g_mods[0], HF_ON_PLAYER_SPAWN, Heard, NULL, 0));
    CHECK(ApiSubscribe(&g_mods[0], HF_ON_PLAYER_DOWN, Heard, NULL, 0));
    CHECK(ApiSubscribe(&g_mods[0], HF_ON_HEAL, Heard, NULL, 0));
    PollPlayers(fixtureGame); CHECK(spawns == 8 && g_playerCount == 8);
    PollPlayers(fixtureGame); CHECK(spawns == 8);
    frame.players[7].life = 2; PollPlayers(fixtureGame); CHECK(downs == 1);
    frame.players[7].life = 3; PollPlayers(fixtureGame); CHECK(spawns == 9);
    frame.players[7].generation++; PollPlayers(fixtureGame); CHECK(spawns == 10);
    EpHfPlayer swap = frame.players[0]; frame.players[0] = frame.players[7]; frame.players[7] = swap;
    PollPlayers(fixtureGame); CHECK(spawns == 10 && downs == 1);
    frame.count = 7; PollPlayers(fixtureGame); CHECK(g_playerCount == 7);
    frame.count = 8; PollPlayers(fixtureGame); CHECK(spawns == 11);
    frame.epoch++; PollPlayers(fixtureGame); CHECK(spawns == 19);
    FixtureFrame(16); PollPlayers(fixtureGame); CHECK(g_playerCount == 16 && ActPlayerCount(fixtureGame) == 16);
    FixtureFrame(8);
    /* Actual heal poll observes eighth avatar, via synthetic manager/hash/records. */
    uint8_t healthManager[0x1100] = {0}, healthRecords[8 * 0x1B8] = {0}; uint32_t healthMap[32] = {0};
    FixturePtr(game, EVP_HEALTH, healthManager); Fixture32(healthManager, 0x1020, 8); FixturePtr(healthManager, 0x1058, healthRecords);
    FixtureHash(healthManager + 0x1030, healthMap, 16);
    for (unsigned i = 0; i < 8; i++) { unsigned b = (2000 + i) % 16; healthMap[b * 2] = 2000 + i; healthMap[b * 2 + 1] = i; Fixture32(healthRecords, i * 0x1B8 + 0x14, 50); }
    PollHeal(fixtureGame); CHECK(g_evpHealthCount == 8 && heals == 0);
    Fixture32(healthRecords, 7 * 0x1B8 + 0x14, 70); PollHeal(fixtureGame); CHECK(heals == 1);
    frame.epoch++; Fixture32(healthRecords, 7 * 0x1B8 + 0x14, 90);
    PollHeal(fixtureGame); CHECK(heals == 1 && g_evpHealthCount == 8); /* session reset is not healing */
    /* Local eighth participant may still have a native customization index <4.
     * Its independent four-record guard must remain. Never execute a passive write. */
    uint32_t map[4] = {0, 0, 1007, 0}; uint8_t desc[16] = {0}, kit[44] = {0}; void* kits[1] = {kit};
    Fixture32(custom, PSV_PASSIVE_COUNT, 1); Fixture32(custom, PSV_RECORD_COUNT, 1); FixtureHash(custom + PSV_MAP, map, 2);
    Fixture32(desc, 8, 1007); FixturePtr(custom, PSV_DESCRIPTORS, desc);
    FixturePtr(custom, PSV_KITS, kits); Fixture32(custom, PSV_KIT_COUNT, 1); Fixture32(kit, 0, 99);
    Fixture32(custom, PSV_APPLIED + PSV_ARMOR_KIT, 99);
    LocalPassives local; const char* why = NULL;
    CHECK(PassivesLocal(fixtureGame, &local, &why) && local.players == 8);
    Fixture32(custom, PSV_RECORD_COUNT, 5); CHECK(!PassivesLocal(fixtureGame, &local, &why)); Fixture32(custom, PSV_RECORD_COUNT, 1);
    frame.count = 0; CHECK(EpRosterRead(fixtureGame, &out) == 0 && ActPlayerCount(fixtureGame) == 0);
    FixtureFrame(8);
    CHECK(EpRosterUnbind(&g_mods[0], lease)); CHECK(ActPlayerCount(fixtureGame) == 4);
    uint64_t oldLease = lease; lease = EpRosterBind(&g_mods[0], &provider); CHECK(lease > oldLease);
    CHECK(!EpRosterUnbind(&g_mods[0], oldLease));
    unsigned before = spawns; PollPlayers(fixtureGame); CHECK(spawns == before + 8); /* new binding invalidates cache */
    entered = CreateEventW(NULL, TRUE, FALSE, NULL); releaseRead = CreateEventW(NULL, TRUE, FALSE, NULL);
    unbindStarted = CreateEventW(NULL, TRUE, FALSE, NULL); CHECK(entered && releaseRead && unbindStarted);
    HANDLE reader = CreateThread(NULL, 0, Reader, NULL, 0, NULL); CHECK(reader != NULL);
    CHECK(WaitForSingleObject(entered, 2000) == WAIT_OBJECT_0);
    HANDLE unbinder = CreateThread(NULL, 0, Unbinder, NULL, 0, NULL); CHECK(unbinder != NULL);
    CHECK(WaitForSingleObject(unbindStarted, 2000) == WAIT_OBJECT_0);
    CHECK(WaitForSingleObject(unbinder, 50) == WAIT_TIMEOUT); /* callback still owns context */
    SetEvent(releaseRead);
    CHECK(WaitForSingleObject(reader, 2000) == WAIT_OBJECT_0 && WaitForSingleObject(unbinder, 2000) == WAIT_OBJECT_0);
    DWORD code; CHECK(GetExitCodeThread(reader, &code) && code == 0); CHECK(GetExitCodeThread(unbinder, &code) && code == 0);
    CloseHandle(reader); CloseHandle(unbinder); CloseHandle(entered); CloseHandle(releaseRead); CloseHandle(unbindStarted);
    entered = NULL;
    CHECK(ActPlayerCount(fixtureGame) == 4);
    provider.capacity = 8; frame.capacity = 8; frame.count = 9;
    lease = EpRosterBind(&g_mods[0], &provider); CHECK(lease != 0);
    CHECK(EpRosterRead(fixtureGame, &out) == -1); frame.count = 8;
    CHECK(EpRosterRead(fixtureGame, &out) == 8); CHECK(EpRosterUnbind(&g_mods[0], lease));
    lease = EpRosterBind(&g_mods[0], &provider); CHECK(lease != 0);
    g_mods[0].loaded = 0; CHECK(EpRosterRead(fixtureGame, &out) == -1);
    EpRosterDeclined(&g_mods[0]); CHECK(ActPlayerCount(fixtureGame) == 4);
    CHECK(!EpRosterBind(&g_mods[0], &provider));
    free(custom); free(user); free(manager); free(game);
    printf("engine roster: %u checks passed; real patched consumers, synthetic process only\n", checks);
    return 0;
}
