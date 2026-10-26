/* Native execution uses owned leaf bridges and compiler-built test callbacks.
 * Saved UPDATE is emitted here but executed only by the Unicorn driver. */
#include "component33_resource_entries_dll.cpp"
#include "component33_resources_dll.cpp"
EXPORT int component33_image_test_build(uint32_t k,const EpComponent33Addresses* a,EpComponent33Image* out)
{ return ep_component33_image_build(k,a,out); }
EXPORT int c33_consumer_build(uint32_t k,const EpC33ConsumerAddresses* a,EpComponent33Image* out)
{ return ep_component33_consumer_build(k,a,out); }
EXPORT int c33_update_drain_build(const EpC33ConsumerAddresses* a,uint64_t drain,EpComponent33Image* out)
{ return ep_component33_update_drain_build(a,drain,out); }
static int UpdateCode(uintptr_t address,void* out,size_t bytes)
{
    int rc=EntryCode(address,out,bytes);
    if (!rc && entryTest->mode==105 && address==0x180664b2f) ((uint8_t*)out)[0]^=1;
    return rc;
}
static void UpdateDispose(uint64_t key,uint64_t table)
{
    NativeDispose(key,table);auto* t=entryTest;auto* s=&t->native.p.test;
    if (t->mode==106) NativeReenter(&t->native);
    if (t->mode==109 && t->native.calls==2) RaiseException(0xe00000c9,0,0,nullptr);
    if (t->mode==107) { SetEvent(s->entered);Check(WaitForSingleObject(s->proceed,5000)==WAIT_OBJECT_0,"UPDATE dispose wait"); }
}
static int UpdateOuter(void* p,const EpNativeRosterView*) { return InvokeEntry(p); }
static DWORD WINAPI UpdateThread(void* p)
{
    auto* t=(EntryTest*)p;auto* s=&t->native.p.test;
    Check(ep_roster_owner_call(s->mod,s->owner,1,UpdateOuter,t)==EP_OWNER_OK,"UPDATE worker scope");return 0;
}
EXPORT unsigned c33_resource_update_entry_test(unsigned mode)
{
    Check(mode<10,"UPDATE entry scenario");EntryTest t={};t.mode=100+mode;t.index=3;entryTest=&t;
    NativeSetup(&t.native,mode==1 ? 4 : mode==2 ? 5 : mode==4 ? 15 : 0);
    auto* n=&t.native;auto* s=&n->p.test;n->api.read=EntryRead;n->api.read_code=UpdateCode;n->api.hook_ex=Hook;
    n->dispose_target=(uintptr_t)UpdateDispose;
    EpC33ResourceEntryBindings b={s->storage.handle,s->owner,{0x191000000,0x191010000,0x191020000,0x191030000},Rejected,&t};
    Check(ep_component33_resource_entries_prepare(&n->api,s->mod,&b,&t.entries),"UPDATE prepare");
    Check(ep_component33_resource_entries_retain(s->mod,t.entries.handle),"UPDATE retain");
    Check(!n->p.reads && !n->p.codes && !n->calls && !hooks,"UPDATE prepare accessed source");
    t.component=n->p.global+(mode==8 ? 8 : 0);t.value=UINT64_MAX;t.flag=UINT64_MAX;
    if (mode==9) {
        EpC33ResourceSnapshot state={};state.seed=1;state.entries[101]={101,1};state.entries[102]={102,0};state.entries[103]={103,0};
        state.queued=2;state.queue[0]=102;state.queue[1]=103;
        Check(ep_c33_resource_migrate(&s->resources.binding,&state,(void*)(uintptr_t)s->resources.binding.address,s->resources.arena_bytes)==0,"UPDATE two-dispose setup");
    }
    uint8_t before[48+512*24];memcpy(before,(void*)(uintptr_t)s->resources.binding.address,sizeof(before));int result=0;
    if (mode==3) { int fault=0;Check(!EpOwnerInvoke(InvokeEntry,&t,&fault) && fault,"unscoped DRAIN continued"); }
    else if (mode==7) {
        HANDLE worker=CreateThread(nullptr,0,UpdateThread,&t,0,nullptr);Check(worker!=nullptr,"UPDATE worker");
        Check(WaitForSingleObject(s->entered,5000)==WAIT_OBJECT_0,"UPDATE dispose entered");Observer observer={};observer.test=s;
        HANDLE reader=CreateThread(nullptr,0,Observe,&observer,0,nullptr);Check(reader!=nullptr,"UPDATE reader");
        ULONGLONG until=GetTickCount64()+5000;while (!Pending(s,false) && GetTickCount64()<until) Sleep(1);
        Check(Pending(s,false) && WaitForSingleObject(reader,0)==WAIT_TIMEOUT,"UPDATE reader escaped outer scope");
        SetEvent(s->proceed);Check(WaitForSingleObject(worker,5000)==WAIT_OBJECT_0 && WaitForSingleObject(reader,5000)==WAIT_OBJECT_0,"UPDATE threads");
        Check(observer.status==EP_OWNER_OK && observer.info.revision==2,"UPDATE observer revision");CloseHandle(worker);CloseHandle(reader);result=1;
    } else result=ep_roster_owner_call(s->mod,s->owner,1,UpdateOuter,&t)==EP_OWNER_OK;
    bool success=mode<3 || mode==7;Check(bool(result)==success && t.returned==success && t.rejected==unsigned(!success),"UPDATE continued after failed drain");
    Check(n->calls==(mode==0 || mode==4 || mode==6 || mode==7 ? 1u : mode==9 ? 2u : 0u),"UPDATE dispose count");
    Check(!n->contexts && !n->resolvers && t.sdk_bytes<=65536,"UPDATE selected entities or exceeded SDK budget");
    if (mode==2 || mode==3 || mode==8) Check(!n->p.reads && !n->p.codes,"UPDATE unnecessary SDK access");
    auto* arena=(uint8_t*)(uintptr_t)s->resources.binding.address;
    if (mode==0 || mode==7) { for (unsigned i=0;i<512*8;i++) Check(arena[48+i]==0,"UPDATE queue not cleared");Check(*(uint64_t*)(arena+32)==0,"UPDATE queue count"); }
    else Check(!memcmp(before,arena,sizeof(before)),"deferred/failed UPDATE drain changed arena");
    EpRosterOwnerInfo info={};Check(ep_roster_owner_info(s->mod,s->owner,&info)==EP_OWNER_OK,"UPDATE owner info");
    Check(bool(info.fault)==(!success && mode!=3) && info.revision==(success ? 2u : 1u),"UPDATE quarantine/revision");
    if (info.fault) {
        unsigned calls=n->calls,bytes=t.sdk_bytes;
        Check(ep_roster_owner_call(s->mod,s->owner,1,UpdateOuter,&t)==EP_OWNER_FAULTED && n->calls==calls && t.sdk_bytes==bytes,"UPDATE retry after partial effects");
    }
    Check(ep_roster_owner_close(s->mod,s->owner)==EP_OWNER_OK,"UPDATE close");
    Check(!hooks && !resourceCall && !ep_roster_owner_in_scope() && allocations==frees,"UPDATE scope leak/publication");
    CloseHandle(s->entered);CloseHandle(s->proceed);entryTest=nullptr;nativeTest=nullptr;active=nullptr;return checks;
}
