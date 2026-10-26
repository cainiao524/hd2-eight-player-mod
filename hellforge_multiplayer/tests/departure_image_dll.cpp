/* Extend the existing synthetic library; emitted game code is never called. */
#include "property_image_dll.cpp"
#include "../mod/src/ep_departure_image.h"
extern "C" __declspec(dllexport) int departure_image_test_build(const EpDepartureAddresses* a,EpDepartureImage* out)
{return ep_departure_image_build(a,out);}
extern "C" __declspec(dllexport) int departure_image_test_prepare(uint32_t* checks)
{
    HfApi api={};int marker=0;HfMod* owner=(HfMod*)&marker;EpSessionCodeInfo info={},empty={};EpDepartureImage image;
    void* hint=VirtualAlloc(NULL,65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);*checks=0;
    if(!hint || !VirtualFree(hint,0,MEM_RELEASE))return -1;
    EpDepartureAddresses a={(uintptr_t)hint-0x10000000,(uintptr_t)hint,(uintptr_t)hint+0x10000000,
        (uintptr_t)hint+0x20000000,(uintptr_t)hint+0x30000,(uintptr_t)hint+0x10000};
    api.version=13;api.size=sizeof(api);api.build_id=Build;api.hook_ex=Hook;
#define CHECK(x) do {++*checks;if(!(x)){fail_free=fail_protect=false;if(info.handle)ep_session_code_discard(owner,info.handle);return __LINE__;}} while(0)
    CHECK(ep_departure_code_prepare(&api,owner,&a,&info)==EP_PROPERTY_OK);
    CHECK(info.base==a.code_address && info.state==EP_CODE_READY && info.registered && !info.pinned);
    CHECK(ep_departure_image_build(&a,&image)==EP_PROPERTY_OK && info.bytes==image.bytes && !memcmp((void*)info.base,image.data,image.bytes));
    RUNTIME_FUNCTION* rows=(RUNTIME_FUNCTION*)(image.data+image.table_offset);DWORD64 base=0;
    CHECK(image.function_count==14);
    for(unsigned i=0;i<image.function_count;i++)
        CHECK(RtlLookupFunctionEntry(info.base+rows[i].BeginAddress,&base,NULL)==(RUNTIME_FUNCTION*)(info.base+image.table_offset)+i && base==info.base);
    CHECK(ep_session_code_discard(owner,info.handle));info={};
    CHECK(RtlLookupFunctionEntry(a.code_address,&base,NULL)==NULL);
    for(unsigned variant=0;variant<9;variant++) {
        EpDepartureImage broken=image;RUNTIME_FUNCTION* r=(RUNTIME_FUNCTION*)(broken.data+broken.table_offset);
        uint8_t* primary=broken.data+r[1].UnwindData;uint8_t* chained=broken.data+r[2].UnwindData;
        uint8_t* xmm=broken.data+r[4].UnwindData;unsigned chain=4+((chained[2]+1u)&~1u)*2;
        if(variant==0)broken.data[r[0].UnwindData]=9; /* handler not preserved */
        if(variant==1)memcpy(chained+chain,&r[2],12); /* cycle */
        if(variant==2)memcpy(chained+chain,&r[13],12); /* forward chain */
        if(variant==3)primary[5]=0x11; /* unsupported unscaled large allocation */
        if(variant==4)primary[6]=primary[7]=0; /* zero allocation */
        if(variant==5)primary[2]=1; /* truncated allocation payload */
        if(variant==6)xmm[9]=0x58; /* volatile XMM5 */
        if(variant==7)xmm[2]=3; /* truncated XMM save payload */
        if(variant==8)r[3].UnwindData=r[2].UnwindData; /* aliased metadata */
        CHECK(ep_session_code_reserve(&api,owner,(uintptr_t)a.code_address,broken.bytes,&info));
        CHECK(!ep_session_code_seal_table(owner,info.handle,broken.data,broken.bytes,broken.table_offset,broken.function_count));
        CHECK(ep_session_code_discard(owner,info.handle));info={};
    }
    a.storage_address++;
    CHECK(ep_departure_code_prepare(&api,owner,&a,&info)==EP_PROPERTY_POINTER && !memcmp(&info,&empty,sizeof(info)));
    fail_free=true;
    CHECK(ep_departure_code_prepare(&api,owner,&a,&info)==EP_PROPERTY_CLEANUP && info.handle && !info.registered);
    fail_free=false;CHECK(ep_session_code_discard(owner,info.handle));info={};a.storage_address--;
    fail_protect=true;
    CHECK(ep_departure_code_prepare(&api,owner,&a,&info)==EP_PROPERTY_SEAL && !memcmp(&info,&empty,sizeof(info)));
    fail_protect=false;CHECK(!hook_calls);return 0;
#undef CHECK
}
