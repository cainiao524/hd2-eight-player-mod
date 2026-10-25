#include <windows.h>
#include <string.h>
#include "property_group_dll.h"
static unsigned failures;
static bool preparing_getter;
static BOOL TestFree(LPVOID p,SIZE_T n,DWORD flags) { return failures&1 ? FALSE : VirtualFree(p,n,flags); }
static BOOL TestProtect(LPVOID p,SIZE_T n,DWORD flags,PDWORD old) { return (failures&2) || ((failures&16) && preparing_getter) ? FALSE : VirtualProtect(p,n,flags,old); }
#define VirtualFree TestFree
#define VirtualProtect TestProtect
#include "../mod/src/ep_session_code.cpp"
#undef VirtualFree
#undef VirtualProtect
/* Actual emitter still runs and validates its bindings. Replace only the
 * candidate body for host-native tests: sum ABI arguments + a known constant.
 * Never execute the saved game function body on the Windows host. */
static EpPropertyResult FixtureBuild(uint32_t kind,const EpPropertyAddresses* a,EpPropertyImage* out)
{
    EpPropertyResult result=ep_property_image_build(kind,a,out);
    if (result!=EP_PROPERTY_OK) return result;
    if ((failures&4) && kind==2) { memset(out,0,sizeof(*out)); return EP_PROPERTY_POINTER; }
    const uint8_t sum[]={0x48,0x89,0xC8,0x48,0x01,0xD0,0x4C,0x01,0xC0,0x4C,0x01,0xC8};
    const uint8_t producer[]={0x48,0x03,0x44,0x24,0x60,0x48,0x03,0x44,0x24,0x68,0x48,0x05,0xE8,3,0,0,
        0x48,0x8B,0x5C,0x24,0x40,0x48,0x8B,0x6C,0x24,0x48,0x48,0x8B,0x74,0x24,0x50,
        0x48,0x83,0xC4,0x20,0x41,0x5F,0x41,0x5E,0x5F,0xC3};
    const uint8_t receiver[]={0x48,0x05,0xD0,7,0,0,
        0x48,0x8B,0x5C,0x24,0x10,0x48,0x8B,0x74,0x24,0x18,0x48,0x8B,0x7C,0x24,0x20,
        0x48,0x8B,0x6C,0x24,0x28,0x41,0x5E,0xC3};
    unsigned at=kind==1 ? 24 : 22;
    memset(out->data+at,0x90,out->code_bytes-at); memcpy(out->data+at,sum,sizeof(sum)); at+=sizeof(sum);
    memcpy(out->data+at,kind==1 ? producer : receiver,kind==1 ? sizeof(producer) : sizeof(receiver));
    return EP_PROPERTY_OK;
}
static EpPropertyResult FixtureGetter(const EpGetterAddresses* a,EpPropertyImage* out)
{
    EpPropertyResult result=ep_getter_image_build(a,out);
    if (result!=EP_PROPERTY_OK) return result;
    preparing_getter=true;
    if (failures&8) { memset(out,0,sizeof(*out)); return EP_PROPERTY_POINTER; }
    const uint8_t body[]={0x48,0x89,0xC8,0x48,0x01,0xD0,0x4C,0x01,0xC0,0x4C,0x01,0xC8,
        0x48,0x05,0xB8,0x0B,0,0,0x48,0x8B,0x5C,0x24,8,0x48,0x8B,0x6C,0x24,0x10,
        0x48,0x8B,0x74,0x24,0x18,0x48,0x8B,0x7C,0x24,0x20,0xC3};
    memset(out->data+20,0x90,out->code_bytes-20); memcpy(out->data+20,body,sizeof(body));
    return EP_PROPERTY_OK;
}
#define ep_property_image_build FixtureBuild
#define ep_getter_image_build FixtureGetter
#include "../mod/src/ep_property_gate.cpp"
#undef ep_property_image_build
#undef ep_getter_image_build
#include "../mod/src/ep_property_group.cpp"
static void SetFailure(unsigned value) { failures=value; preparing_getter=false; }
extern "C" __declspec(dllexport) const PropertyGroupTestApi* property_group_test_api(void)
{
    static const PropertyGroupTestApi api={ep_property_group_prepare,ep_property_group_info,ep_property_group_publish,
        ep_property_group_commit,ep_property_group_cancel,ep_session_code_reserve,ep_session_code_seal_table,
        ep_session_code_discard,ep_property_gate_build,SetFailure};
    return &api;
}
