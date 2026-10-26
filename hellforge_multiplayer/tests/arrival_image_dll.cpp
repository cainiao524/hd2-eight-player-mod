/* Own test process only; no generated game instructions execute natively. */
#include "departure_image_dll.cpp"
#include "../mod/src/ep_arrival_image.h"
extern "C" __declspec(dllexport) int arrival_image_test_build(const EpArrivalAddresses* a,EpArrivalImage* out)
{return ep_arrival_image_build(a,out);}
extern "C" __declspec(dllexport) int arrival_image_test_prepare(uint32_t* checks)
{
    HfApi api={};int marker=0;HfMod* owner=(HfMod*)&marker;EpSessionCodeInfo info={},empty={};EpArrivalImage image;
    void* hint=VirtualAlloc(NULL,65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);*checks=0;
    if(!hint || !VirtualFree(hint,0,MEM_RELEASE))return -1;
    EpArrivalAddresses a={(uintptr_t)hint-0x10000000,(uintptr_t)hint,(uintptr_t)hint+0x10000000,
        (uintptr_t)hint+0x20000000,(uintptr_t)hint+0x10000};
    api.version=13;api.size=sizeof(api);api.build_id=Build;api.hook_ex=Hook;
#define CHECK(x) do {++*checks;if(!(x)){fail_free=fail_protect=false;if(info.handle)ep_session_code_discard(owner,info.handle);return __LINE__;}} while(0)
    CHECK(ep_arrival_code_prepare(&api,owner,&a,&info)==EP_PROPERTY_OK);
    CHECK(info.base==a.code_address && info.state==EP_CODE_READY && info.registered && !info.pinned);
    CHECK(ep_arrival_image_build(&a,&image)==EP_PROPERTY_OK && info.bytes==image.bytes && !memcmp((void*)info.base,image.data,image.bytes));
    RUNTIME_FUNCTION* rows=(RUNTIME_FUNCTION*)(image.data+image.table_offset);DWORD64 base=0;
    CHECK(image.function_count==3);
    for(unsigned i=0;i<image.function_count;i++)
        CHECK(RtlLookupFunctionEntry(info.base+rows[i].BeginAddress,&base,NULL)==(RUNTIME_FUNCTION*)(info.base+image.table_offset)+i && base==info.base);
    CHECK(ep_session_code_discard(owner,info.handle));info={};
    CHECK(RtlLookupFunctionEntry(a.code_address+496,&base,NULL)==NULL);
    for(unsigned variant=0;variant<15;variant++) {
        EpArrivalImage broken=image;RUNTIME_FUNCTION* r=(RUNTIME_FUNCTION*)(broken.data+broken.table_offset);
        uint8_t* body=broken.data+r[1].UnwindData;
        EpSessionGsCheck gs={1,1920,(uintptr_t)a.game_base+0x21044a0};
        if(variant==1)body[0]=1; /* handler silently discarded */
        if(variant==2)body[0]=9; /* missing unwind handler */
        if(variant==3)body[32]=104; /* wrong cookie offset */
        if(variant==4)body[32]=100; /* unsupported aligned frame */
        if(variant==5)body[28]++; /* handler not the owned thunk */
        if(variant==6)broken.data[1920]=0x90;
        if(variant==7)broken.data[1921]^=1;
        if(variant==8)r[2].EndAddress++;
        if(variant==9)body[1]++;
        if(variant==10)body[3]=5;
        if(variant==11)gs.function_index=3;
        if(variant==12)gs.handler_offset=0xffffffff;
        if(variant==13)gs.handler_target=a.code_address+1920;
        if(variant==14)gs.handler_target=(uintptr_t)1<<47;
        CHECK(ep_session_code_reserve(&api,owner,(uintptr_t)a.code_address,broken.bytes,&info));
        CHECK(!ep_session_code_seal_gs_table(owner,info.handle,broken.data,broken.bytes,broken.table_offset,broken.function_count,variant?&gs:NULL));
        CHECK(ep_session_code_discard(owner,info.handle));info={};
    }
    a.storage_address++;
    CHECK(ep_arrival_code_prepare(&api,owner,&a,&info)==EP_PROPERTY_POINTER && !memcmp(&info,&empty,sizeof(info)));
    fail_free=true;
    CHECK(ep_arrival_code_prepare(&api,owner,&a,&info)==EP_PROPERTY_CLEANUP && info.handle && !info.registered);
    fail_free=false;CHECK(ep_session_code_discard(owner,info.handle));info={};a.storage_address--;
    fail_protect=true;
    CHECK(ep_arrival_code_prepare(&api,owner,&a,&info)==EP_PROPERTY_SEAL && !memcmp(&info,&empty,sizeof(info)));
    fail_protect=false;CHECK(!hook_calls);return 0;
#undef CHECK
}
