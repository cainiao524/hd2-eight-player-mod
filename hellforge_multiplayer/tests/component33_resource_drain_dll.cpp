/* Real retained allocations/shared owner, synthetic SDK data only. */
#include "component33_resource_provider_dll.cpp"
struct DrainTest { ProviderTest p;unsigned mode,service_count;uint64_t keys[512],manager;uint32_t blocked;HfApi api;EpC33ResourceProviderOps ops; };
static DrainTest* draining;
static int DrainCode(uintptr_t address,void* out,size_t bytes)
{
    auto* t=draining;++t->p.codes;
    Check(ep_roster_owner_in_scope() && address==0x180664b2f && bytes==sizeof(ep_c33_drain_source),"unexpected drain code access");
    if (t->mode==8) return 1;
    memcpy(out,ep_c33_drain_source,bytes);if (t->mode==7) ((uint8_t*)out)[0]^=1;return 0;
}
static int DrainRead(uintptr_t address,void* out,size_t bytes)
{
    auto* t=draining;
    if (t->mode==14) RaiseException(0xe00000c7,0,0,nullptr);
    if (t->mode==15) W64((void*)(uintptr_t)(t->p.test.resources.binding.address+40),1);
    return SdkRead(address,out,bytes);
}
static int DrainService(void* context,const EpC33ResourceScopeView* v,uint32_t op,uint64_t key)
{
    auto* t=(DrainTest*)context;
    Check(ep_roster_owner_native_status(t->p.test.mod,t->p.test.owner)==EP_OWNER_OK,"drain outside owner");
    Check(op==EP_RESOURCE_DISPOSE && t->service_count<512,"drain service operation");t->keys[t->service_count++]=key;
    if (t->mode==23 && t->service_count==1) {
        SetEvent(t->p.test.entered);Check(WaitForSingleObject(t->p.test.proceed,5000)==WAIT_OBJECT_0,"drain service wait");
    }
    if (t->mode==22) t->blocked=1; /* Original gate is read once, before services. */
    if (t->mode==16) return 0;
    if (t->service_count!=2) return 1;
    if (t->mode==9) return 0;
    if (t->mode==10) RaiseException(0xe00000c7,0,0,nullptr);
    if (t->mode==11) W64((void*)(uintptr_t)(v->resources.address+40),1);
    if (t->mode==12) {
        EpC33ResourceProviderResult out={};
        Check(ep_component33_resource_drain_provider_call(&t->api,t->p.test.mod,t->p.test.storage.handle,t->p.test.owner,&t->ops,&out)==EP_C33_CALL_REENTRANT,"drain recursion accepted");
    }
    if (t->mode==13) Check(ep_roster_owner_call(t->p.test.mod,t->p.test.owner,1,NestedFailure,nullptr)==EP_OWNER_CALLBACK_FAILED,"drain nested fault");
    return 1;
}
static DWORD WINAPI RunDrain(void* opaque)
{
    auto* t=(DrainTest*)opaque;
    ep_component33_resource_drain_provider_call(&t->api,t->p.test.mod,t->p.test.storage.handle,t->p.test.owner,&t->ops,&t->p.result);return 0;
}
static int NestedDrain(void* context,const EpNativeRosterView*) { RunDrain(context);return 1; }
EXPORT unsigned c33_resource_drain_test(unsigned mode)
{
    DrainTest t={};t.mode=mode;Setup(&t.p.test,mode==17 ? 18 : 0);active=&t.p;draining=&t;
    t.manager=mode==5 ? 0 : 0x270000000;t.blocked=mode==1 ? 1 : mode==2 ? UINT32_MAX : 0;
    if (mode!=4) RegionAdd(&t.p,0x18346d530,&t.manager,8);
    if (mode!=6) RegionAdd(&t.p,t.manager+0x190c,&t.blocked,4);
    auto& test=t.p.test;auto* arena=(uint8_t*)(uintptr_t)test.resources.binding.address;auto* queue=(uint64_t*)(arena+48);
    EpC33ResourceSnapshot state={};state.seed=1;state.entries[101]={101,0};state.entries[102]={102,0};state.entries[103]={103,0};state.entries[104]={104,7};
    state.queued=mode==3 ? 0 : 3;state.queue[0]=103;state.queue[1]=101;state.queue[2]=102;
    Check(ep_c33_resource_migrate(&test.resources.binding,&state,arena,test.resources.arena_bytes)==0,"drain arena setup");queue[7]=0xabcdef;
    if (mode==20) {
        memset(&state,0,sizeof(state));state.seed=1;
        Check(ep_c33_resource_migrate(&test.resources.binding,&state,arena,test.resources.arena_bytes)==0,"full drain setup");
        uint64_t keys[512];for (unsigned i=0;i<512;i++) keys[i]=i+1;
        uint8_t scratch[48+512*24];
        Check(ep_c33_resource_reserve(&test.resources.binding,arena,test.resources.arena_bytes,keys,512,scratch,sizeof(scratch))==0,"full drain table");
        W64(arena+32,512);memcpy(queue,keys,sizeof(keys));
    }
    uint8_t before[48+512*24];memcpy(before,arena,sizeof(before));
    t.api.version=13;t.api.size=sizeof(t.api);t.api.build_id=mode==18 ? WrongBuild : Build;t.api.read=DrainRead;t.api.read_code=DrainCode;
    t.ops={&t,nullptr,mode==19 ? nullptr : DrainService};
    if (mode==21) Check(ep_roster_owner_call(test.mod,test.owner,0,NestedDrain,&t)==EP_OWNER_OK,"outer drain scope");
    else if (mode==23) {
        HANDLE worker=CreateThread(nullptr,0,RunDrain,&t,0,nullptr);Check(worker!=nullptr,"drain thread");
        Check(WaitForSingleObject(test.entered,5000)==WAIT_OBJECT_0,"drain service entered");
        Observer observer={&test};HANDLE reader=CreateThread(nullptr,0,Observe,&observer,0,nullptr);Check(reader!=nullptr,"drain observer");
        bool pending=false;for (unsigned i=0;i<5000;i++) { if (Pending(&test,false)) { pending=true;break; }Sleep(1); }
        Check(pending && WaitForSingleObject(reader,0)==WAIT_TIMEOUT,"drain did not exclude roster read");SetEvent(test.proceed);
        Check(WaitForSingleObject(worker,5000)==WAIT_OBJECT_0 && WaitForSingleObject(reader,5000)==WAIT_OBJECT_0,"drain threads finish");
        Check(observer.status==EP_OWNER_OK && observer.info.revision==2,"drain observer revision");CloseHandle(worker);CloseHandle(reader);
    } else RunDrain(&t);
    bool success=mode==0 || mode>=20;bool skip=mode>=1 && mode<=3;bool fault=(mode>=9 && mode<=17);
    Check((t.p.result.call.status==EP_C33_CALL_OK)==(success || skip),"drain status");
    Check(t.service_count==(success ? mode==20 ? 512u : 3u : mode==16 ? 1u : mode>=9 && mode<=13 ? 2u : 0u),"drain service count");
    for (unsigned i=0;i<t.service_count;i++) Check(t.keys[i]==(mode==20 ? i+1 : i==0 ? 103u : i==1 ? 101u : 102u),"drain service order");
    Check(!t.p.resolves && !t.p.result.resolve_calls && !t.p.result.call.demand_count,"drain used acquisition data");
    if (success || mode==1 || mode==2) Check(t.p.result.read_bytes==134 && t.p.codes==1 && t.p.reads==2,"drain read scope");
    if (mode==3 || mode==18 || mode==19) Check(!t.p.result.read_bytes && !t.p.reads && !t.p.codes,"early drain accessed SDK");
    if (success) {
        W64(before+32,0);memset(before+48,0,512*8);Check(!memcmp(before,arena,sizeof(before)),"drain changed nonqueue bytes");
    } else if (mode!=11 && mode!=15) Check(!memcmp(before,arena,sizeof(before)),"drain refusal/failure cleared queue");
    EpRosterOwnerInfo info={};Check(ep_roster_owner_info(test.mod,test.owner,&info)==EP_OWNER_OK,"drain owner info");
    Check(bool(info.fault)==fault && info.revision==(mode==17 ? UINT64_MAX : success ? 2u : 1u),"drain owner fault/revision");
    if (fault) {
        unsigned calls=t.service_count,reads=t.p.reads,codes=t.p.codes;RunDrain(&t);
        Check(t.p.result.call.owner_result==EP_OWNER_FAULTED && t.service_count==calls && t.p.reads==reads && t.p.codes==codes,"faulted drain retried effects");
    }
    Check(allocations==frees && !resourceCall && !ep_roster_owner_in_scope() && !hooks,"drain scope leak");
    Check(ep_roster_owner_close(test.mod,test.owner)==EP_OWNER_OK,"drain owner close");CloseHandle(test.entered);CloseHandle(test.proceed);draining=nullptr;active=nullptr;return checks;
}
EXPORT int c33_resource_drain(const EpC33ResourceBinding* b,void* p,uint32_t bytes,void* scratch,uint32_t scratch_bytes,EpC33ResourceService service,void* context)
{ return ep_c33_resource_drain(b,p,bytes,scratch,scratch_bytes,service,context); }
