/* Reuse actual retained storage/owner setup; SDK reads map only owned fixtures. */
#include "component33_resource_call_dll.cpp"
#include "../mod/src/ep_component33_resource_provider.h"
#include "../mod/src/ep_component33_resource_provider_template.h"
struct Region { uint64_t address;uint32_t bytes;const void* data; };
struct ProviderTest {
    Test test;unsigned mode,region_count,reads,codes,resolves,services;
    Region regions[16];uint8_t header[0x70],entities[8][64],packages[32+2*0x3030],thresholds[8*0x58];
    uint64_t global,root,table,manager,pointers[8],threshold_pointers[8],service_keys[384];
    uint32_t invalid,count;EpC33ResourceProviderResult result;
};
static ProviderTest* active;
static void RegionAdd(ProviderTest* t,uint64_t address,const void* p,uint32_t bytes)
{ Check(t->region_count<16,"region capacity");t->regions[t->region_count++]={address,bytes,p}; }
static int SdkRead(uintptr_t address,void* out,size_t bytes)
{
    auto* t=active;++t->reads;
    Check(ep_roster_owner_native_status(t->test.mod,t->test.owner)==EP_OWNER_OK,"SDK data read outside owner");
    if (t->mode==4 && address==t->table+32+0x3030) return 1;
    if (t->mode==10 && address>=t->manager+0x68 && address<t->manager+0x68+uint64_t(UINT32_MAX)*8 && bytes==8) {
        uint64_t value=0x250000000;memcpy(out,&value,8);return 0;
    }
    for (unsigned i=0;i<t->region_count;i++) {
        const auto& r=t->regions[i];
        if (address>=r.address && address-r.address<=r.bytes && bytes<=r.bytes-(address-r.address)) {
            memcpy(out,(const uint8_t*)r.data+(address-r.address),bytes);return 0;
        }
    }
    return 1;
}
static int SdkCode(uintptr_t address,void* out,size_t bytes)
{
    auto* t=active;++t->codes;Check(ep_roster_owner_in_scope(),"code check outside owner");
    const uint8_t* source=nullptr;
    if (address==0x1804f6430 && bytes==sizeof(ep_c33_package_source)) source=ep_c33_package_source;
    if (address==0x1807af0a0 && bytes==sizeof(ep_c33_threshold_source)) source=ep_c33_threshold_source;
    Check(source!=nullptr,"unexpected code read");
    if (t->mode==3) return 1;
    memcpy(out,source,bytes);if (t->mode==2) ((uint8_t*)out)[0]^=1;return 0;
}
static int ResolveObject(void* context,uint32_t handle,uint64_t* object)
{
    auto* t=(ProviderTest*)context;++t->resolves;
    Check(handle>=10 && handle<18,"invalid handle sent to resolver");
    if (t->mode==11) return 0;
    if (t->mode==12) RaiseException(0xe00000c5,0,0,nullptr);
    if (t->mode==13) Check(ep_roster_owner_call(t->test.mod,t->test.owner,1,NestedFailure,nullptr)==EP_OWNER_CALLBACK_FAILED,"nested fault");
    *object=0x260000000+uint64_t(handle-10)*0x100;return 1;
}
static int ProviderService(void* context,const EpC33ResourceScopeView*,uint32_t operation,uint64_t key)
{
    auto* t=(ProviderTest*)context;
    Check(ep_roster_owner_native_status(t->test.mod,t->test.owner)==EP_OWNER_OK,"service outside owner");
    Check(operation==EP_RESOURCE_LOAD && t->services<384,"unexpected service");t->service_keys[t->services++]=key;
    if (t->mode==14) return 0;
    if (t->mode==16) RaiseException(0xe00000c5,0,0,nullptr);return 1;
}
static const char* WrongBuild() { return "unsupported"; }
struct Probe { uint32_t checks,keys;EpC33ResourceProviderResult result;uint64_t service_keys[384]; };
EXPORT void c33_resource_provider_test(unsigned mode,Probe* out)
{
    ProviderTest t={};t.mode=mode;Setup(&t.test,0);active=&t;
    t.global=0x200000000;t.invalid=UINT32_MAX;t.root=0x270000000;t.table=0x280000000;t.manager=0x290000000;t.count=8;
    W32(t.header+8,8);W32(t.header+12,8);W32(t.header+16,4);W64(t.header+0x58,t.global+0x14);W32(t.header+0x60,8);W32(t.header+0x68,1);
    const unsigned order[]={0,1,2,3,4,6,7,5};
    for (unsigned i=0;i<8;i++) {
        t.pointers[i]=0x250000000+64*i;t.threshold_pointers[i]=0x250000000+64*order[i];
        W64(t.entities[i],0x12000+i);W32(t.entities[i]+8,50+i);W32(t.entities[i]+16,i==1 ? 0x7fff : 10+i);W32(t.entities[i]+20,i<4);
        W32(t.header+0x14+((50+i)&7)*8,50+i);W32(t.header+0x18+((50+i)&7)*8,i);
    }
    memcpy((void*)(uintptr_t)t.test.storage.storage_address,t.pointers,sizeof(t.pointers));
    W64(t.packages,0x12007);W32(t.packages+8,1);W64(t.packages+16,0x12005);
    uint8_t* package=t.packages+32+0x3030;uint8_t* row=t.thresholds+6*0x58;
    W32(row,6);const uint32_t values[]={100,0,1,0x7fffffff,0x80000000,0xffffffff};
    for (unsigned g=0;g<6;g++) {
        W32(row+4+g*4,101+g);W32(row+0x30+g*4,values[g]);W32(package+g*0x808+0x800,101+g);
        for (unsigned i=0;i<64;i++) { uint8_t* record=package+g*0x808+i*0x20;W64(record,999+g*64+i);W32(record+16,values[g]);W32(record+20,values[g]); }
    }
    if (mode==5) W64(t.packages,0);
    if (mode==6) W32(t.header+0x18+((50+7)&7)*8,0);
    if (mode==7) for (unsigned g=0;g<6;g++) W32(package+g*0x808+0x800,0);
    if (mode==8) t.count=6;
    if (mode==9) for (unsigned g=0;g<6;g++) W32(row+4+g*4,9999);
    if (mode==10) t.count=UINT32_MAX;
    if (mode==17) t.global+=8;
    if (mode==18) { t.table=(UINT64_C(1)<<47)-0x10000;W32(t.packages+8,UINT32_MAX); }
    if (mode==19) W32(t.header+8,9);
    RegionAdd(&t,0x1833267b8,&t.global,8);RegionAdd(&t,0x183483c34,&t.invalid,4);
    RegionAdd(&t,0x200000000,t.header,sizeof(t.header));RegionAdd(&t,t.test.storage.storage_address,(const void*)(uintptr_t)t.test.storage.storage_address,64);
    RegionAdd(&t,0x250000000,t.entities,sizeof(t.entities));RegionAdd(&t,0x18346bf98,&t.root,8);
    RegionAdd(&t,t.root+0xf12580,&t.table,8);RegionAdd(&t,t.table,t.packages,sizeof(t.packages));
    RegionAdd(&t,0x183326998,&t.manager,8);RegionAdd(&t,t.manager+8,&t.count,4);
    RegionAdd(&t,t.manager+0x68,t.threshold_pointers,sizeof(t.threshold_pointers));RegionAdd(&t,t.manager+0x26688,t.thresholds,sizeof(t.thresholds));
    HfApi api={};api.version=13;api.size=mode==20 ? offsetof(HfApi,read_code) : sizeof(api);api.build_id=mode==15 ? WrongBuild : Build;api.read=SdkRead;api.read_code=SdkCode;
    EpC33ResourceProviderOps ops={&t,ResolveObject,ProviderService};
    void* arena=(void*)(uintptr_t)t.test.resources.binding.address;uint8_t before[48+512*24];memcpy(before,arena,sizeof(before));
    ep_component33_resource_acquire_provider_call(&api,t.test.mod,t.test.storage.handle,t.test.owner,
        mode==1 ? 0x260009000 : 0x260000700,&ops,&t.result);
    bool success=mode==0 || mode==7 || mode==8 || mode==9;bool fault=mode==12 || mode==13 || mode==14 || mode==16;
    Check((t.result.call.status==EP_C33_CALL_OK)==(success || mode==1),"provider operation result");
    const uint32_t statuses[]={0,6,2,2,3,8,5,0,0,0,4,7,0,9,0,2,0,5,5,5,1};
    Check(t.result.source_status==statuses[mode],"provider diagnosis");
    Check(t.result.read_bytes<=65536,"read budget escaped");
    Check(t.result.resolve_calls==t.resolves,"resolution accounting");
    Check(t.services==(mode==0 ? 384u : mode==8 || mode==9 ? 64u : mode==14 || mode==16 ? 1u : 0u),"provider selection");
    for (unsigned i=0;i<t.services;i++) Check(t.service_keys[i]==999+i+(mode==8 || mode==9 ? 64 : 0),"wrong selected package or threshold");
    if (!t.result.call.executed) Check(!memcmp(before,arena,sizeof(before)),"provider refusal changed arena");
    if (mode==2 || mode==3) Check(!t.reads && !t.resolves && t.codes==1,"data read after source rejection");
    if (mode==10) Check(t.result.read_bytes>65520,"budget test did not reach limit");
    if (mode==12 || mode==13) Check(t.resolves==1,"continued after resolver fault");
    EpRosterOwnerInfo info={};Check(ep_roster_owner_info(t.test.mod,t.test.owner,&info)==EP_OWNER_OK,"provider owner info");
    Check(bool(info.fault)==fault && info.revision==(success ? 2u : 1u),"provider owner revision/fault");
    Check(allocations==(mode==15 || mode==20 ? 0u : 1u) && allocations==frees && !resourceCall && !ep_roster_owner_in_scope(),"provider lifetime leak");
    Check(!hooks,"provider installed a hook");Check(ep_roster_owner_close(t.test.mod,t.test.owner)==EP_OWNER_OK,"provider owner close");
    CloseHandle(t.test.entered);CloseHandle(t.test.proceed);out->checks=checks;out->keys=t.services;out->result=t.result;
    memcpy(out->service_keys,t.service_keys,sizeof(t.service_keys));active=nullptr;
}
