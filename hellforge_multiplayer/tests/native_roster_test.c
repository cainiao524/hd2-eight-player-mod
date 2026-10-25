/* All addresses come from a synthetic emulator image; ReadMemory never calls
 * a process API. Real patched loader consumers are included below. */
#include "hellforge_modloader.c"
#include "../mod/src/ep_native_roster.cpp"
static unsigned checks, acquired, released, reads, readBytes, failAt, spawns;
static int unavailable, changeBinding;
static EpNativeRosterView view;
typedef struct Region { uint64_t address; uint32_t size; unsigned char data[2048]; } Region;
static Region regions[32]; static unsigned regionCount;
#define CHECK(x) do { checks++; if (!(x)) { fprintf(stderr,"FAIL %d: %s\n",__LINE__,#x); exit(1); } } while(0)
static int Begin(void* c, uintptr_t game, EpNativeRosterView* out)
{
    (void)c; if (unavailable || game != view.game) return 0;
    *out = view; out->lease = &view; acquired++; reads = readBytes = 0; return 1;
}
static int ReadMemory(void* c, void* lease, uintptr_t a, void* out, size_t n)
{
    (void)c; CHECK(lease == &view && acquired == released + 1);
    reads++; readBytes += (unsigned)n;
    if (failAt == reads) return 0;
    if (changeBinding && a == view.game + 0x3326468 && reads > 1) { memset(out, 0, n); return 1; }
    for (unsigned i = 0; i < regionCount; i++)
        if (a >= regions[i].address && a - regions[i].address <= regions[i].size && n <= regions[i].size - (a - regions[i].address))
        { memcpy(out, regions[i].data + a - regions[i].address, n); return 1; }
    return 0;
}
static void End(void* c, void* lease) { (void)c; CHECK(lease == &view); released++; }
static void Write32(unsigned region, unsigned offset, uint32_t v) { memcpy(regions[region].data + offset, &v, 4); }
static void Heard(HfMod* mod, const HfEventInfo* event, void* user)
{ (void)mod; (void)user; if (event->kind == HF_ON_PLAYER_SPAWN) spawns++; }
static EpNativeRosterStatus Snapshot(EpNativeRosterSource* source, EpHfRosterSnapshot* out)
{
    EpNativeRosterStatus status = ep_native_roster_snapshot(source, view.game, out);
    CHECK(acquired == released && readBytes <= EP_NATIVE_ROSTER_READ_BUDGET);
    if (status != EP_NATIVE_OK) CHECK(out->count == 0 && out->epoch == 0);
    return status;
}
static void LoadFixture(const char* path)
{
    FILE* f = fopen(path, "rb"); CHECK(f != NULL);
    unsigned char magic[8]; CHECK(fread(magic,8,1,f)==1 && !memcmp(magic,"EPNATV1\0",8));
    CHECK(fread(&view.game,8,1,f)==1 && fread(&view.roster,8,1,f)==1 && fread(&view.storage,8,1,f)==1);
    CHECK(fread(&regionCount,4,1,f)==1 && regionCount <= 32);
    for (unsigned i=0;i<regionCount;i++)
    {
        CHECK(fread(&regions[i].address,8,1,f)==1 && fread(&regions[i].size,4,1,f)==1 && regions[i].size <= 2048);
        CHECK(fread(regions[i].data,regions[i].size,1,f)==1);
    }
    CHECK(fgetc(f)==EOF); fclose(f);
}
int main(int argc, char** argv)
{
    CHECK(argc == 4); LoadFixture(argv[1]);
    view.epoch=42; view.build=25480438; view.ticket_count=8;
    for (unsigned i=0;i<8;i++) view.tickets[i]=(EpNativeTicket){100+i,42,1+8*i,(3*i+2)%8,10+i,0};
    EpNativeRosterSource source={NULL,Begin,ReadMemory,End}; EpHfRosterSnapshot out;
    CHECK(Snapshot(&source,&out)==EP_NATIVE_OK && out.count==8 && out.capacity==8);
    CHECK(readBytes == 2024);
    for(unsigned i=0;i<8;i++) CHECK(out.players[i].player==1+8*i && out.players[i].peer==100+i &&
        out.players[i].network_index==(3*i+2)%8 && out.players[i].network_id==0x1000+i &&
        out.players[i].generation==10+i && out.players[i].local==(i==7));
    unsigned successfulReads=reads;
    for(unsigned i=1;i<=successfulReads;i++) { failAt=i; CHECK(Snapshot(&source,&out)==EP_NATIVE_READ_FAILED); }
    failAt=0; unavailable=1; CHECK(Snapshot(&source,&out)==EP_NATIVE_UNAVAILABLE); unavailable=0;
    changeBinding=1; CHECK(Snapshot(&source,&out)==EP_NATIVE_BINDING_CHANGED); changeBinding=0;
    view.build=1; CHECK(Snapshot(&source,&out)==EP_NATIVE_LAYOUT); view.build=25480438;
    view.storage++; CHECK(Snapshot(&source,&out)==EP_NATIVE_LAYOUT); view.storage--;
    Write32(0,0x80,9); CHECK(Snapshot(&source,&out)==EP_NATIVE_LAYOUT); Write32(0,0x80,8);
    Write32(0,0x84,1); Write32(0,0x88,1); CHECK(Snapshot(&source,&out)==EP_NATIVE_PENDING);
    Write32(0,0x84,8); Write32(0,0x88,9); CHECK(Snapshot(&source,&out)==EP_NATIVE_LAYOUT); Write32(0,0x88,8);
    Write32(0,0xD8,16); CHECK(Snapshot(&source,&out)==EP_NATIVE_LAYOUT); Write32(0,0xD8,8);
    uint32_t saved=NativeU32(regions[2].data+12); Write32(2,12,7);
    CHECK(Snapshot(&source,&out)==EP_NATIVE_MAP_MISMATCH); Write32(2,12,saved);
    view.tickets[7].network_index=0; CHECK(Snapshot(&source,&out)==EP_NATIVE_TICKET_MISMATCH); view.tickets[7].network_index=7;
    view.tickets[7].epoch=41; CHECK(Snapshot(&source,&out)==EP_NATIVE_TICKET_MISMATCH); view.tickets[7].epoch=42;
    view.tickets[7].generation=0; CHECK(Snapshot(&source,&out)==EP_NATIVE_TICKET_MISMATCH); view.tickets[7].generation=17;
    view.ticket_count=7; CHECK(Snapshot(&source,&out)==EP_NATIVE_TICKET_MISMATCH); view.ticket_count=8;
    Write32(1,0x580+7*0x20+0xC,8); CHECK(Snapshot(&source,&out)==EP_NATIVE_TICKET_MISMATCH);
    Write32(1,0x580+7*0x20+0xC,7);
    /* Real private engine provider consumes the emitted storage, not a prebuilt EpHf snapshot. */
    strcpy(g_build,"25480438"); g_modCount=1; g_mods[0].loaded=1;
    EpHfRosterProvider provider={sizeof provider,1,8,0,&source,ep_native_roster_read};
    uint64_t lease=EpRosterBind(&g_mods[0],&provider); CHECK(lease!=0);
    CHECK(EpRosterRead(view.game,&out)==8 && out.binding==lease && out.players[7].network_index==7);
    CHECK(ApiSubscribe(&g_mods[0],HF_ON_PLAYER_SPAWN,Heard,NULL,0));
    PollPlayers(view.game); CHECK(spawns==8 && g_playerCount==8);
    PollPlayers(view.game); CHECK(spawns==8);
    view.tickets[7].generation++; PollPlayers(view.game); CHECK(spawns==9);
    unavailable=1; CHECK(EpRosterRead(view.game,&out)==-1); PollPlayers(view.game); CHECK(spawns==9); unavailable=0;
    CHECK(ActPlayerCount(view.game)==8);
    LoadFixture(argv[2]);
    CHECK(Snapshot(&source,&out)==EP_NATIVE_OK && out.count==7);
    CHECK(out.players[4].peer==107 && out.players[4].network_index==7 && out.players[4].local);
    for(unsigned i=0;i<out.count;i++) CHECK(out.players[i].peer!=104);
    PollPlayers(view.game); CHECK(g_playerCount==7 && spawns==9);
    LoadFixture(argv[3]); view.tickets[4].generation++;
    CHECK(Snapshot(&source,&out)==EP_NATIVE_OK && out.count==8);
    CHECK(out.players[7].peer==104 && out.players[7].network_index==6 && out.players[7].generation==15);
    CHECK(out.players[4].peer==107 && out.players[4].network_index==7 && out.players[4].local);
    PollPlayers(view.game); CHECK(g_playerCount==8 && spawns==10);
    CHECK(EpRosterUnbind(&g_mods[0],lease)); CHECK(acquired==released);
    printf("native roster source: %u checks passed; emitted native insert storage to real loader consumers\n",checks);
    return 0;
}
