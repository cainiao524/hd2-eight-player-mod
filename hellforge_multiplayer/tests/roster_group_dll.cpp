#include <windows.h>
#include <string.h>
#include "roster_group_dll.h"
static unsigned failing_step,preparing_step;
static uint64_t prepared_mover,expected_association;
static int failing_free;
static BOOL TestFree(LPVOID p,SIZE_T bytes,DWORD flags) {return failing_free ? FALSE : VirtualFree(p,bytes,flags);}
static BOOL TestProtect(LPVOID p,SIZE_T bytes,DWORD flags,PDWORD old)
{return failing_step && failing_step==preparing_step ? FALSE : VirtualProtect(p,bytes,flags,old);}
#define VirtualFree TestFree
#define VirtualProtect TestProtect
#include "../mod/src/ep_session_code.cpp"
#undef VirtualFree
#undef VirtualProtect
/* Execute only a tiny synthetic return body on the Windows host. Production
 * emitter executes first; keep the actual switch and its leaf unwind region.
 * Real candidate bodies and all their unwind PCs are tested separately. A
 * single indirect tail jump at body offset zero leaves the original prologue
 * unexecuted; compiler-generated leaf targets keep their own unwind contract. */
#define LEAF(n) static uint64_t Leaf##n(void) {return 1000+n;}
LEAF(1) LEAF(2) LEAF(3) LEAF(4) LEAF(5) LEAF(6) LEAF(7) LEAF(8) LEAF(9) LEAF(10) LEAF(11) LEAF(12) LEAF(13) LEAF(14)
#undef LEAF
static EpPropertyResult FixtureGate(uint32_t kind,const EpInsertAddresses* a,uint64_t control,uint64_t next,EpRosterGateImage* out)
{
    EpPropertyResult rc=ep_roster_gate_build(kind,a,control,next,out);preparing_step=kind;
    if (rc!=EP_PROPERTY_OK) return rc;
    if (kind==EP_ROSTER_MOVER) prepared_mover=a->code_address+32;
    if (kind>=5 && kind<=10 && a->move_code_address!=prepared_mover) return EP_PROPERTY_ARGUMENT;
    if (kind==EP_ROSTER_REGISTRY_UPDATE) expected_association=a->move_code_address;
    if (kind==EP_ROSTER_ASSOCIATION && a->code_address+32!=expected_association) return EP_PROPERTY_ARGUMENT;
    static uint64_t (*const leaf[])(void)={Leaf1,Leaf2,Leaf3,Leaf4,Leaf5,Leaf6,Leaf7,Leaf8,Leaf9,Leaf10,Leaf11,Leaf12,Leaf13,Leaf14};
    const uint8_t jump[]={0xFF,0x25,0,0,0,0};uintptr_t target=(uintptr_t)leaf[kind-1];
    memcpy(out->data+32,jump,6);memcpy(out->data+38,&target,8);
    return rc;
}
#define ep_roster_gate_build FixtureGate
#include "../mod/src/ep_roster_group.cpp"
#undef ep_roster_gate_build
static void Failure(unsigned step,int free_failure) {failing_step=step;failing_free=free_failure;preparing_step=0;}
extern "C" __declspec(dllexport) const RosterGroupTestApi* roster_group_test_api(void)
{
    static const RosterGroupTestApi api={ep_roster_group_prepare,ep_roster_group_info,ep_roster_group_publish,
        ep_roster_group_commit,ep_roster_group_cancel,ep_roster_gate_layout,ep_session_code_reserve,
        ep_session_code_seal_table,ep_session_code_discard,Failure};return &api;
}
