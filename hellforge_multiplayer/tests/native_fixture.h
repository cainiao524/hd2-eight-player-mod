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
