#include "roster_owner_dll.h"
#include "../mod/src/ep_native_roster.cpp"
#include "../mod/src/ep_roster_owner.cpp"
static uint32_t Pending(HfMod* mod,uint64_t id,int* closing)
{
    uint32_t refs=0;*closing=0;
    AcquireSRWLockExclusive(&epOwnersLock);EpRosterOwner* o=OwnerFind(mod,id);
    if (o) {refs=o->refs;*closing=o->closing;}
    ReleaseSRWLockExclusive(&epOwnersLock);return refs;
}
extern "C" __declspec(dllexport) const RosterOwnerTestApi* roster_owner_test_api(void)
{
    static const RosterOwnerTestApi api={ep_roster_owner_create,ep_roster_owner_info,ep_roster_owner_mutate,
        ep_roster_owner_snapshot,ep_roster_owner_provider,ep_roster_owner_close,Pending};return &api;
}
