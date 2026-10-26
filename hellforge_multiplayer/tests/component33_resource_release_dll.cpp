/* Only owned allocations and fake SDK regions. No captured code runs natively. */
#include "component33_resource_provider_dll.cpp"
static unsigned releaseMode;
static int ReleaseService(void* opaque,const EpC33ResourceScopeView*,uint32_t op,uint64_t key)
{
    auto* t=(ProviderTest*)opaque;
    Check(op==EP_RESOURCE_DISPOSE && t->services<2,"release service operation");
    Check(ep_roster_owner_native_status(t->test.mod,t->test.owner)==EP_OWNER_OK,"release outside owner");
    t->service_keys[t->services++]=key;
    if (releaseMode==3) return 0;
    if (releaseMode==4) RaiseException(0xe00000c6,0,0,nullptr);
    if (releaseMode==5) Check(ep_roster_owner_call(t->test.mod,t->test.owner,1,NestedFailure,nullptr)==EP_OWNER_CALLBACK_FAILED,"release nested fault");
    if (releaseMode==6) {
        EpC33ResourceServiceOps ops={&t->test,Collect,nullptr};EpC33ResourceCallResult out={};
        Check(ep_component33_resource_release_services_call(t->test.mod,t->test.storage.handle,t->test.owner,1,&ops,&out)==EP_C33_CALL_REENTRANT,"release recursion accepted");
    }
    return 1;
}
static uint64_t References(ProviderTest* t,uint64_t key)
{
    auto* table=(EpC33ResourceEntry*)(uintptr_t)(t->test.resources.binding.address+48+8*t->test.resources.binding.capacity);
    for (unsigned i=0;i<t->test.resources.binding.capacity;i++) if (table[i].key==key) return table[i].references;
    Check(false,"release erased an existing key");return 0;
}
EXPORT unsigned c33_resource_release_test(unsigned mode)
{
    ProviderTest t={};Setup(&t.test,0);active=&t;releaseMode=mode;t.mode=mode==7 ? 2 : mode==8 ? 4 : 0;
    t.global=0x200000000;t.invalid=UINT32_MAX;t.root=0x270000000;t.table=0x280000000;t.manager=0x290000000;t.count=0;
    W32(t.header+8,8);W32(t.header+12,mode==9 ? 7 : 8);W32(t.header+16,4);W64(t.header+0x58,t.global+0x14);W32(t.header+0x60,8);W32(t.header+0x68,1);
    for (unsigned i=0;i<8;i++) {
        t.pointers[i]=0x250000000+64*i;W64(t.entities[i],0x12000+i);W32(t.entities[i]+8,50+i);W32(t.entities[i]+16,10+i);W32(t.entities[i]+20,i<4);
        W32(t.header+0x14+((50+i)&7)*8,50+i);W32(t.header+0x18+((50+i)&7)*8,i);
    }
    memcpy((void*)(uintptr_t)t.test.storage.storage_address,t.pointers,sizeof(t.pointers));
    W64(t.packages,0x12007);W32(t.packages+8,1);W64(t.packages+16,0x12005);
    const uint64_t keys[]={101,102,101,103,104};auto* package=t.packages+32+0x3030;W32(package+0x800,1);
    for (unsigned i=0;i<5;i++) W64(package+i*0x20,keys[i]);
    W64(package+0x808,104); /* Disabled group must not release this key. */
    if (mode==14) W32(t.header+0x18+((50+7)&7)*8,0);
    RegionAdd(&t,0x1833267b8,&t.global,8);RegionAdd(&t,0x183483c34,&t.invalid,4);
    RegionAdd(&t,t.global,t.header,sizeof(t.header));RegionAdd(&t,t.test.storage.storage_address,(const void*)(uintptr_t)t.test.storage.storage_address,64);
    RegionAdd(&t,0x250000000,t.entities,sizeof(t.entities));RegionAdd(&t,0x18346bf98,&t.root,8);RegionAdd(&t,t.root+0xf12580,&t.table,8);RegionAdd(&t,t.table,t.packages,sizeof(t.packages));
    RegionAdd(&t,0x183326998,&t.manager,8);RegionAdd(&t,t.manager+8,&t.count,4);
    auto* arena=(void*)(uintptr_t)t.test.resources.binding.address;EpC33ResourceSnapshot state={};state.seed=1;
    const uint64_t counts[]={2,1,0,3,0};for (unsigned i=0;i<5;i++) state.entries[101+i]={101+i,counts[i]};state.queued=1;state.queue[0]=103;
    Check(ep_c33_resource_migrate(&t.test.resources.binding,&state,arena,t.test.resources.arena_bytes)==0,"release initial arena");
    uint8_t before[48+512*24];memcpy(before,arena,sizeof(before));
    HfApi api={};api.version=13;api.size=sizeof(api);api.build_id=Build;api.read=SdkRead;api.read_code=SdkCode;
    unsigned deferred=(mode==1 || mode==2) ? 1 : mode==11 ? 2 : 0;
    EpC33ResourceProviderOps ops={&t,mode==12 ? ResolveObject : nullptr,(deferred || mode==13) ? nullptr : ReleaseService};
    ep_component33_resource_release_provider_call(&api,t.test.mod,t.test.storage.handle,t.test.owner,mode==10 ? 8 : 7,deferred,&ops,&t.result);
    bool success=mode<=2 || mode==12;bool fault=mode>=3 && mode<=6;
    Check((t.result.call.status==EP_C33_CALL_OK)==(success || mode==9),"release status");
    Check(!t.resolves && !t.result.resolve_calls && !t.result.call.demand_count,"release resolved or admitted acquisition");
    Check(t.result.read_bytes<=65536,"release budget");
    Check(t.services==(mode==0 || mode==12 ? 2u : fault ? 1u : 0u),"release service count");
    if (t.services) Check(t.service_keys[0]==102,"first release service key");
    if (t.services==2) Check(t.service_keys[1]==101,"second release service key");
    if (success) {
        Check(t.result.read_bytes==12871 && t.codes==1,"release read unused threshold code/data");
        Check(References(&t,101)==0 && References(&t,102)==0 && References(&t,103)==0 && References(&t,104)==2 && References(&t,105)==0,"release reference result");
        uint64_t queued;memcpy(&queued,(uint8_t*)arena+32,8);auto* q=(uint64_t*)((uint8_t*)arena+48);
        Check(queued==(deferred ? 3u : 1u) && q[0]==103,"release existing queue");
        if (deferred) Check(q[1]==102 && q[2]==101,"deferred append order");
    } else if (!fault) Check(!memcmp(before,arena,sizeof(before)),"release refusal mutated arena");
    if (fault) Check(References(&t,101)==1 && References(&t,102)==0 && References(&t,104)==3,"release partial effects");
    EpRosterOwnerInfo info={};Check(ep_roster_owner_info(t.test.mod,t.test.owner,&info)==EP_OWNER_OK,"release owner info");
    Check(bool(info.fault)==fault && info.revision==(success ? 2u : 1u),"release owner fault/revision");
    if (mode==2) {
        ops.resolve=ResolveObject;ops.service=ReleaseService;
        Check(ep_component33_resource_acquire_provider_call(&api,t.test.mod,t.test.storage.handle,t.test.owner,0x260000700,&ops,&t.result)==EP_C33_CALL_OK,"queued reacquire");
        Check(!t.services && References(&t,101)==2 && References(&t,102)==1 && References(&t,103)==1 && References(&t,104)==2,"queued reacquire references/services");
        uint64_t queued;memcpy(&queued,(uint8_t*)arena+32,8);Check(!queued,"reacquire did not cancel queue");
        Check(ep_roster_owner_info(t.test.mod,t.test.owner,&info)==EP_OWNER_OK && info.revision==3,"reacquire revision");
    }
    Check(ep_c33_resource_validate(&t.test.resources.binding,arena,t.test.resources.arena_bytes)==0,"release left invalid arena");
    Check(allocations==frees && !resourceCall && !ep_roster_owner_in_scope() && !hooks,"release scope leak/hooks");
    Check(ep_roster_owner_close(t.test.mod,t.test.owner)==EP_OWNER_OK,"release owner close");CloseHandle(t.test.entered);CloseHandle(t.test.proceed);active=nullptr;return checks;
}
EXPORT int c33_resource_release(const EpC33ResourceBinding* b,void* p,uint32_t bytes,const uint64_t* keys,uint32_t count,uint32_t deferred,void* scratch,uint32_t scratch_bytes,EpC33ResourceService service,void* context)
{ return ep_c33_resource_release(b,p,bytes,keys,count,deferred,scratch,scratch_bytes,service,context); }
