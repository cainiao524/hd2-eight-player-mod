/* Engine tables below contain only functions compiled into this test DLL.
 * SDK reads map fixture regions; no game process or installation is accessed. */
#include "component33_resource_drain_dll.cpp"
struct NativeTest {
    ProviderTest p;HfApi api;unsigned mode,contexts,resolvers,calls,native_reads;
    uint64_t engine,service_table,context_table,object_table,context_value;
    uint64_t load_target,dispose_target,context_target,resolver_target,gate;
    uint32_t blocked,operations[8];uint64_t keys[8];
};
static NativeTest* nativeTest;
static int NativeRun(NativeTest* t,EpC33ResourceProviderResult* out)
{
    auto* s=&t->p.test;
    if (t->mode==1 || t->mode==2) return ep_component33_resource_release_native_call(&t->api,s->mod,s->storage.handle,s->owner,4,t->mode==2,out);
    if (t->mode>=3 && t->mode<=5) return ep_component33_resource_drain_native_call(&t->api,s->mod,s->storage.handle,s->owner,out);
    return ep_component33_resource_acquire_native_call(&t->api,s->mod,s->storage.handle,s->owner,t->mode==27 ? 0x260009000 : 0x260000400,out);
}
static void NativeReenter(NativeTest* t)
{
    EpC33ResourceProviderResult r={};Check(NativeRun(t,&r)==EP_C33_CALL_REENTRANT,"native callback reentry accepted");
}
static uint64_t NativeContext(uint64_t engine)
{
    auto* t=nativeTest;++t->contexts;
    Check(engine==t->engine && ep_component33_resource_scope_ready(t->p.test.mod,t->p.test.owner),"context ABI/scope");
    if (t->mode==12) RaiseException(0xe00000c7,0,0,nullptr);
    if (t->mode==16) NativeReenter(t);
    if (t->mode==18) Check(ep_roster_owner_call(t->p.test.mod,t->p.test.owner,1,NestedFailure,nullptr)==EP_OWNER_CALLBACK_FAILED,"context nested fault");
    return t->context_value;
}
static uint64_t NativeResolve(uint64_t context,uint32_t handle)
{
    auto* t=nativeTest;++t->resolvers;
    Check(context==t->context_value && handle>=10 && handle<15 && handle!=11,"resolver ABI or sentinel");
    Check(ep_component33_resource_scope_ready(t->p.test.mod,t->p.test.owner),"resolver outside healthy scope");
    if (t->mode==13) RaiseException(0xe00000c7,0,0,nullptr);
    if (t->mode==17) NativeReenter(t);
    return 0x260000000+uint64_t(handle-10)*0x100;
}
static void NativeEffect(uint32_t op,uint64_t key,uint64_t table)
{
    auto* t=nativeTest;auto* s=&t->p.test;
    Check(table==t->service_table && ep_component33_resource_scope_ready(s->mod,s->owner),"service ABI/scope");
    Check(t->calls<8,"too many native effects");t->operations[t->calls]=op;t->keys[t->calls++]=key;
    if ((t->mode==14 && op==EP_RESOURCE_LOAD) || (t->mode==15 && op==EP_RESOURCE_DISPOSE)) RaiseException(0xe00000c7,0,0,nullptr);
    if (t->mode==19 && op==EP_RESOURCE_LOAD) NativeReenter(t);
    if (t->mode==20 && op==EP_RESOURCE_LOAD) W32((void*)(uintptr_t)(s->resources.binding.address+24),123);
    // A changed table is not a license to unload targets: the original code
    // lifetime is still required. This checks use of the frozen call selection.
    if (t->mode==25) t->load_target=t->dispose_target=0;
    if (t->mode==24 && op==EP_RESOURCE_LOAD && t->calls==2) {
        SetEvent(s->entered);Check(WaitForSingleObject(s->proceed,5000)==WAIT_OBJECT_0,"native effect wait");
    }
}
static void NativeLoad(uint64_t key,uint64_t table)
{ NativeEffect(EP_RESOURCE_LOAD,key,table);__asm__ volatile("xor %%eax,%%eax" ::: "rax"); }
static void NativeDispose(uint64_t key,uint64_t table)
{ NativeEffect(EP_RESOURCE_DISPOSE,key,table);__asm__ volatile("xor %%eax,%%eax" ::: "rax"); }
static int NativeRead(uintptr_t address,void* out,size_t bytes)
{
    auto* t=nativeTest;
    Check(!t->calls,"SDK data read after effects started");
    if (address==0x183326308 || (address>=0x2a0000000 && address<0x2a0040000)) ++t->native_reads;
    if (t->mode==9 && address==t->service_table+0x2f0) return 1;
    if (t->mode==21 && address>=t->p.manager+0x68 && address<t->p.manager+0x26688 && bytes==8) {
        uint64_t entity=0x250000000;memcpy(out,&entity,8);return 0;
    }
    return SdkRead(address,out,bytes);
}
static int NativeCode(uintptr_t address,void* out,size_t bytes)
{
    auto* t=nativeTest;Check(!t->calls,"SDK code read after effects started");
    const uint8_t* source=nullptr;
    if (address==0x180665704 && bytes==sizeof(ep_c33_native_resolve_source)) source=ep_c33_native_resolve_source;
    if (address==0x180665847 && bytes==sizeof(ep_c33_native_load_source)) source=ep_c33_native_load_source;
    if (address==0x180665ada && bytes==sizeof(ep_c33_native_dispose_source)) source=ep_c33_native_dispose_source;
    if (address==0x180664b2f && bytes==sizeof(ep_c33_drain_source)) source=ep_c33_drain_source;
    if (!source) return SdkCode(address,out,bytes);
    ++t->p.codes;Check(ep_component33_resource_scope_ready(t->p.test.mod,t->p.test.owner),"native code read outside scope");
    if (t->mode==10) return 1;
    memcpy(out,source,bytes);if (t->mode==11) ((uint8_t*)out)[0]^=1;return 0;
}
static void NativeSetup(NativeTest* t,unsigned mode)
{
    t->mode=mode;auto* p=&t->p;Setup(&p->test,0);active=p;nativeTest=t;
    p->global=0x200000000;p->invalid=UINT32_MAX;p->root=0x270000000;p->table=0x280000000;p->manager=0x290000000;p->count=mode==21 ? UINT32_MAX : 5;
    W32(p->header+8,5);W32(p->header+12,5);W32(p->header+16,2);W64(p->header+0x58,p->global+0x14);W32(p->header+0x60,8);W32(p->header+0x68,1);
    for (unsigned i=0;i<5;i++) {
        p->pointers[i]=p->threshold_pointers[i]=0x250000000+64*i;
        W64(p->entities[i],0x12000+i);W32(p->entities[i]+8,50+i);W32(p->entities[i]+16,i==1 ? 0x7fff : 10+i);W32(p->entities[i]+20,i<2);
        W32(p->header+0x14+((50+i)&7)*8,50+i);W32(p->header+0x18+((50+i)&7)*8,i);
    }
    memcpy((void*)(uintptr_t)p->test.storage.storage_address,p->pointers,sizeof(p->pointers));
    W64(p->packages,0x12004);uint8_t* package=p->packages+32;
    W32(package+0x800,7);
    for (unsigned i=0;i<3;i++) { W64(package+32*i,101+i);W32(package+32*i+16,10);W32(package+32*i+20,10); }
    uint8_t* row=p->thresholds+4*0x58;W32(row,1);W32(row+4,7);W32(row+0x30,10);
    RegionAdd(p,0x1833267b8,&p->global,8);RegionAdd(p,0x183483c34,&p->invalid,4);
    RegionAdd(p,p->global,p->header,sizeof(p->header));RegionAdd(p,p->test.storage.storage_address,p->pointers,sizeof(p->pointers));
    RegionAdd(p,0x250000000,p->entities,sizeof(p->entities));RegionAdd(p,0x18346bf98,&p->root,8);
    RegionAdd(p,p->root+0xf12580,&p->table,8);RegionAdd(p,p->table,p->packages,sizeof(p->packages));
    RegionAdd(p,0x183326998,&p->manager,8);RegionAdd(p,p->manager+8,&p->count,4);
    RegionAdd(p,p->manager+0x68,p->threshold_pointers,sizeof(p->threshold_pointers));RegionAdd(p,p->manager+0x26688,p->thresholds,sizeof(p->thresholds));
    t->engine=0x2a0000000;t->service_table=0x2a0010000;t->context_table=0x2a0020000;t->object_table=0x2a0030000;
    t->context_value=mode==26 ? 0 : 0x2b0000000;t->gate=0x2c0000000;t->blocked=mode==4;
    t->load_target=(uintptr_t)NativeLoad;t->dispose_target=(uintptr_t)NativeDispose;t->context_target=(uintptr_t)NativeContext;t->resolver_target=(uintptr_t)NativeResolve;
    t->api.version=13;t->api.size=mode==23 ? offsetof(HfApi,read_code) : sizeof(t->api);t->api.build_id=mode==22 ? WrongBuild : Build;t->api.read=NativeRead;t->api.read_code=NativeCode;
    auto* arena=(uint8_t*)(uintptr_t)p->test.resources.binding.address;W64(arena+32,mode==5 ? 0 : 1);W64(arena+48,102);
    W64(arena+48+512*8+101*16,101);W64(arena+48+512*8+101*16+8,1);W64(arena+48+512*8+102*16,102);
    if (mode==6) t->engine=0;
    if (mode==7) t->load_target=0;
    if (mode==8) t->service_table=(UINT64_C(1)<<47)-1;
    if (mode==28) { EpRosterOwner* owner=OwnerAcquire(p->test.mod,p->test.owner);Check(owner!=nullptr,"revision access");owner->revision=UINT64_MAX;OwnerRelease(owner); }
}
// Native links use individual owned scalars, avoiding any direct dereference
// of a numeric fixture address (including deliberately invalid test values).
static int NativeSdkRead(uintptr_t address,void* out,size_t bytes)
{
    auto* t=nativeTest;Check(!t->calls,"native table read after effects");
    Check(ep_component33_resource_scope_ready(t->p.test.mod,t->p.test.owner),"table read scope");
    struct LinkRow { uint64_t address;const uint64_t* value; };
    const LinkRow rows[]={{0x183326308,&t->engine},{t->engine+0x10,&t->service_table},{t->service_table+0x2f0,&t->load_target},
        {t->service_table+0x300,&t->dispose_target},{t->engine+0x38,&t->context_table},{t->engine+0x40,&t->object_table},
        {t->context_table+8,&t->context_target},{t->object_table+0x160,&t->resolver_target},{0x18346d530,&t->gate}};
    for (const auto& row:rows) if (address==row.address && bytes==8) {
        ++t->native_reads;++t->p.reads;if (t->mode==9 && address==t->service_table+0x2f0) return 1;
        memcpy(out,row.value,8);return 0;
    }
    if (address==t->gate+0x190c && bytes==4) { ++t->p.reads;memcpy(out,&t->blocked,4);return 0; }
    return NativeRead(address,out,bytes);
}
static DWORD WINAPI NativeThread(LPVOID opaque)
{ auto* t=(NativeTest*)opaque;NativeRun(t,&t->p.result);return 0; }
EXPORT unsigned c33_resource_native_test(unsigned mode)
{
    Check(mode<29,"mode");NativeTest t={};NativeSetup(&t,mode);t.api.read=NativeSdkRead;auto* s=&t.p.test;
    Check(!ep_component33_resource_scope_ready(s->mod,s->owner),"scope valid outside call");
    uint8_t before[48+512*24];memcpy(before,(void*)(uintptr_t)s->resources.binding.address,sizeof(before));
    if (mode==24) {
        HANDLE worker=CreateThread(nullptr,0,NativeThread,&t,0,nullptr);Check(worker!=nullptr,"native worker");
        Check(WaitForSingleObject(s->entered,5000)==WAIT_OBJECT_0,"native effect not entered");Observer observer={};observer.test=s;
        HANDLE other=CreateThread(nullptr,0,Observe,&observer,0,nullptr);Check(other!=nullptr,"roster reader");
        ULONGLONG until=GetTickCount64()+5000;while (!Pending(s,false) && GetTickCount64()<until) Sleep(1);
        Check(Pending(s,false) && WaitForSingleObject(other,0)==WAIT_TIMEOUT,"reader escaped native effects");
        SetEvent(s->proceed);Check(WaitForSingleObject(worker,5000)==WAIT_OBJECT_0 && WaitForSingleObject(other,5000)==WAIT_OBJECT_0,"native call did not drain");
        Check(observer.status==EP_OWNER_OK && observer.info.revision==2,"reader missed native commit");CloseHandle(worker);CloseHandle(other);
    } else NativeRun(&t,&t.p.result);
    bool success=mode<=5 || mode==24 || mode==25 || mode==26 || mode==27;
    bool fault=(mode>=12 && mode<=20) || mode==28;
    Check((t.p.result.call.status==EP_C33_CALL_OK)==success,"native result");
    Check(t.p.result.read_bytes<=65536,"native reads exceeded budget");
    unsigned expected=mode==0 || mode==24 || mode==25 || mode==26 ? 3 : mode==1 || mode==3 || mode==15 ? 1 : mode==14 || mode==19 || mode==20 ? 2 : 0;
    Check(t.calls==expected,"wrong native effect count");
    for (unsigned i=0;i<t.calls;i++) {
        Check(t.operations[i]==(i==0 ? EP_RESOURCE_DISPOSE : EP_RESOURCE_LOAD),"native service order");
        Check(t.keys[i]==(mode==3 ? 102 : i==2 ? 103 : 101),"native service key");
    }
    if (!t.p.result.call.executed) Check(!memcmp(before,(void*)(uintptr_t)s->resources.binding.address,sizeof(before)),"refusal changed resources");
    if (success && t.p.result.call.executed) {
        auto* arena=(uint8_t*)(uintptr_t)s->resources.binding.address;
        auto* buckets=(EpC33ResourceEntry*)(arena+48+512*8);uint64_t refs[3]={};
        for (unsigned i=0;i<512;i++) if (buckets[i].key>=101 && buckets[i].key<=103) refs[buckets[i].key-101]=buckets[i].references;
        bool acquire=mode==0 || mode>=24;
        Check(refs[0]==uint64_t(acquire || mode==3) && refs[1]==uint64_t(acquire) && refs[2]==uint64_t(acquire),"native resource reference totals");
        uint64_t queued=0;memcpy(&queued,arena+32,8);Check(queued==(mode==1 ? 1u : mode==2 ? 2u : 0u),"native deferred queue count");
        if (mode==2) { uint64_t queue[2];memcpy(queue,arena+48,16);Check(queue[0]==102 && queue[1]==101,"native deferred queue order"); }
    }
    if (mode==2) Check(t.native_reads==0 && t.contexts==0 && t.resolvers==0,"deferred release invoked engine");
    if (mode==4 || mode==5) Check(t.contexts==0 && t.resolvers==0 && t.p.codes==(mode==4 ? 1u : 0u),"idle drain bound engine functions");
    if (mode==0 || mode==24 || mode==25 || mode==26) Check(t.contexts==8 && t.resolvers==8,"fifth-entity/sentinel resolution");
    if (mode==16 || mode==18) Check(t.contexts==1 && !t.resolvers && t.p.result.source_status==EP_C33_PROVIDER_OWNER,"continued after getter failure/reentry");
    if (mode==12 || mode==13 || mode==17) Check(t.contexts==1 && t.resolvers==(mode==12 ? 0u : 1u),"continued after resolver fault");
    if (mode>=6 && mode<=11) Check(!t.contexts && !t.resolvers && t.p.result.source_status!=0,"binding refusal invoked engine");
    if (mode==21) Check(t.p.result.source_status==EP_C33_PROVIDER_BUDGET && t.p.result.read_bytes>65520,"shared SDK budget not exhausted");
    if (mode==22 || mode==23) Check(!t.p.codes && !t.p.reads && !t.contexts,"invalid SDK/build accessed data");
    EpRosterOwnerInfo info={};Check(ep_roster_owner_info(s->mod,s->owner,&info)==EP_OWNER_OK,"native owner info");
    Check(bool(info.fault)==fault,"native quarantine");
    Check(info.revision==(mode==28 ? UINT64_MAX : success && mode!=4 && mode!=5 && mode!=27 ? 2u : 1u),"native revision");
    if (fault) {
        unsigned calls=t.calls,contexts=t.contexts,reads=t.p.reads,codes=t.p.codes;EpC33ResourceProviderResult retry={};NativeRun(&t,&retry);
        Check(retry.call.owner_result==EP_OWNER_FAULTED && t.calls==calls && t.contexts==contexts && t.p.reads==reads && t.p.codes==codes,"faulted owner retried native functions");
    }
    Check(allocations==frees && !resourceCall && !ep_roster_owner_in_scope() && !hooks,"native lifetime or hook leak");
    Check(ep_roster_owner_close(s->mod,s->owner)==EP_OWNER_OK,"native owner close");CloseHandle(s->entered);CloseHandle(s->proceed);
    active=nullptr;nativeTest=nullptr;return checks;
}
