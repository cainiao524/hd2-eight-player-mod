#include "roster_call_dll.h"
#include "../mod/src/ep_native_roster.cpp"
#include "../mod/src/ep_roster_owner.cpp"
#include "../mod/src/ep_roster_call.cpp"
#include "../mod/src/ep_session_code.cpp"
static uintptr_t fixture_targets[EP_ROSTER_ENTRIES];
static EpPropertyResult FixtureGate(uint32_t kind,const EpInsertAddresses* a,uint64_t control,uint64_t next,EpRosterGateImage* out)
{
    EpPropertyResult rc=ep_roster_gate_build(kind,a,control,next,out);if(rc!=EP_PROPERTY_OK) return rc;
    /* Production emitter, prefix and registration; substitute only the body
     * with a tail jump to our own process's ordinary C/assembly functions. */
    const uint8_t jump[]={0xFF,0x25,0,0,0,0};memcpy(out->data+32,jump,6);memcpy(out->data+38,&fixture_targets[kind-1],8);return rc;
}
#define ep_roster_gate_build FixtureGate
#include "../mod/src/ep_roster_group.cpp"
#undef ep_roster_gate_build
static uint32_t Pending(HfMod* mod,uint64_t id,int* closing)
{
    uint32_t refs=0;*closing=0;AcquireSRWLockExclusive(&epOwnersLock);EpRosterOwner* o=OwnerFind(mod,id);
    if(o){refs=o->refs;*closing=o->closing;}ReleaseSRWLockExclusive(&epOwnersLock);return refs;
}
static void Targets(const uintptr_t t[EP_ROSTER_ENTRIES]) {memcpy(fixture_targets,t,sizeof(fixture_targets));}
static uintptr_t Entry(void) {return (uintptr_t)EpRosterCallEntry;}
static void Revision(HfMod* mod,uint64_t id,uint64_t revision)
{EpRosterOwner* o=OwnerAcquire(mod,id);if(o){o->revision=revision;OwnerRelease(o);}}
extern "C" __declspec(dllexport) const RosterCallTestApi* roster_call_test_api(void)
{
    static const RosterCallTestApi api={ep_roster_group_prepare_owned,ep_roster_group_info,ep_roster_group_publish,
        ep_roster_group_commit,ep_roster_group_cancel,ep_roster_gate_layout,ep_roster_owner_create,ep_roster_owner_info,
        ep_roster_owner_call,ep_roster_owner_snapshot,ep_roster_owner_close,Pending,Targets,EpRosterCallTarget,Entry,Revision};return &api;
}
