/* Execute the registry traversal and controlled acquisition only in owned
 * test pages, SDK fixture buffers and native test functions. */
#include "component33_reset_entry_dll.cpp"
struct RefreshTest { EntryTest entry;unsigned mode,returned,effects;uint32_t ops[24];uint64_t keys[24],object;void* pages[3]; };
static RefreshTest* refreshing;
static int RefreshRun(void* p)
{
    auto* t=(RefreshTest*)p;((void(*)(uint64_t))t->entry.entries.refresh_entry.base)(t->object);++t->returned;return 1;
}
static int RefreshNested(void* p,const EpNativeRosterView*) { return RefreshRun(p); }
static DWORD WINAPI RefreshThread(void* p) { RefreshRun(p);return 0; }
static void RefreshReject(void* p,uint32_t kind,const EpC33ResourceProviderResult* result)
{
    auto* t=(RefreshTest*)p;++t->entry.rejected;t->entry.failure=*result;
    Check((kind==EP_C33_RESOURCE_REFRESH || kind==EP_C33_ACQUIRE) && result->call.status,"refresh refusal diagnostic");
    if (t->mode==22) RaiseException(0xe04333fd,EXCEPTION_NONCONTINUABLE,0,nullptr);
}
static void RefreshStack()
{
    CONTEXT c={};RtlCaptureContext(&c);auto* tib=(NT_TIB*)NtCurrentTeb();bool found=false;
    for (unsigned i=0;i<128;i++) {
        Check(c.Rsp>=(uintptr_t)tib->StackLimit && c.Rsp+8<(uintptr_t)tib->StackBase,"refresh unwind escaped stack");
        const auto& body=refreshing->entry.entries.refresh_body;
        bool current=c.Rip>=body.base && c.Rip<body.base+body.bytes;
        DWORD64 base=0,frame=0;PVOID data=nullptr;auto* row=RtlLookupFunctionEntry(c.Rip,&base,nullptr);
        if (row) RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,c.Rip,row,&c,&data,&frame,nullptr);
        else { memcpy(&c.Rip,(void*)(uintptr_t)c.Rsp,8);c.Rsp+=8; }
        if (current) { Check(row && base==body.base && (c.Rip<body.base || c.Rip>=body.base+body.bytes),"refresh unwind did not leave frame");found=true;break; }
    }
    Check(found,"owned refresh frame absent");
}
static uint64_t RefreshContext(uint64_t engine)
{
    RefreshStack();auto* t=refreshing;
    if (t->mode==12) RefreshRun(t);
    return NativeContext(engine);
}
static uint64_t RefreshResolve(uint64_t context,uint32_t handle)
{
    auto* n=&refreshing->entry.native;++n->resolvers;
    Check(context==n->context_value && handle>=10 && handle<18 && handle!=11 && ep_component33_resource_scope_ready(n->p.test.mod,n->p.test.owner),"refresh resolver ABI");
    return 0x260000000+uint64_t(handle-10)*0x100;
}
static void RefreshEffect(uint32_t op,uint64_t key,uint64_t table)
{
    auto* t=refreshing;auto* n=&t->entry.native;auto* s=&n->p.test;RefreshStack();
    Check(table==n->service_table && ep_component33_resource_scope_ready(s->mod,s->owner) && t->effects<24,"refresh service ABI");
    t->ops[t->effects]=op;t->keys[t->effects++]=key;
    if (t->mode==11 && op==EP_RESOURCE_LOAD) RaiseException(0xe04333fc,0,0,nullptr);
    if (t->mode==13 && t->effects==2) { SetEvent(s->entered);Check(WaitForSingleObject(s->proceed,5000)==WAIT_OBJECT_0,"refresh effect wait"); }
}
static void RefreshLoad(uint64_t key,uint64_t table) { RefreshEffect(EP_RESOURCE_LOAD,key,table); }
static void RefreshDispose(uint64_t key,uint64_t table) { RefreshEffect(EP_RESOURCE_DISPOSE,key,table); }
EXPORT unsigned c33_resource_whole_refresh_test(unsigned mode)
{
    Check(mode<25,"refresh scenario");RefreshTest t={};t.mode=mode;refreshing=&t;entryTest=&t.entry;
    NativeSetup(&t.entry.native,mode==10 ? 12 : mode==15 ? 28 : 0);auto* e=&t.entry;auto* n=&e->native;auto* p=&n->p;auto* s=&p->test;
    n->api.read=EntryRead;n->api.read_code=EntryCode;n->api.hook_ex=Hook;n->context_target=(uintptr_t)RefreshContext;n->resolver_target=(uintptr_t)RefreshResolve;
    n->load_target=(uintptr_t)RefreshLoad;n->dispose_target=(uintptr_t)RefreshDispose;
    EpC33ResourceEntryBindings b={s->storage.handle,s->owner,{0x191000000,0x191010000,0x191020000,0x191030000},RefreshReject,&t};
    EpC33RefreshEntryConfig config={{{0x191040000,0x191050000},{0x191060000,0x191070000},0x191080000},0x191090000,0x1910a0000};
    if (mode==18) config.desired_entry=config.lifecycle.reset_body;
    if (mode==19) config.desired_body=config.desired_entry;
    if (mode==20) config.desired_body=0x280000000;
    bool prepared=ep_component33_resource_entries_prepare_refresh(&n->api,s->mod,&b,mode==21 ? nullptr : &config,&e->entries)!=0;
    Check(prepared==!(mode>=18 && mode<=21),"refresh prepare outcome");
    Check(!p->reads && !p->codes && !t.effects && !hooks,"refresh prepare accessed source");
    if (!prepared) {
        Check(!e->entries.handle,"refresh incomplete cleanup");config.desired_entry=0x191090000;config.desired_body=0x1910a0000;
        Check(ep_component33_resource_entries_prepare_refresh(&n->api,s->mod,&b,&config,&e->entries),"refresh prepare retry");
    }
    Check(e->entries.refresh_target==0x180b5e710 && e->entries.refresh_body.registered,"refresh target/unwind");ResetLeaf(e->entries.refresh_entry);
    if (mode>=17 && mode<=21) {
        auto old=e->entries;Check(ep_component33_resource_entries_cancel(s->mod,old.handle),"refresh cancel");DWORD64 base=0;
        Check(!RtlLookupFunctionEntry(old.refresh_entry.base,&base,nullptr) && !RtlLookupFunctionEntry(old.refresh_body.base,&base,nullptr) && !RtlLookupFunctionEntry(old.reset_body.base,&base,nullptr),"refresh dependency survived cancel");
        Check(ep_roster_owner_close(s->mod,s->owner)==0,"refresh cancel owner");CloseHandle(s->entered);CloseHandle(s->proceed);return checks;
    }
    Check(ep_component33_resource_entries_retain(s->mod,e->entries.handle),"refresh retain");
    Check(ep_component33_resource_entries_info(s->mod,e->entries.handle,&e->entries),"refresh info");
    for (const auto& code:e->entries.code) Check(code.pinned,"refresh resource lifetime");
    for (const auto& code:e->entries.reset_entries) Check(code.pinned,"refresh reset lifetime");
    Check(e->entries.refresh_body.pinned && e->entries.refresh_entry.pinned && e->entries.update_body.pinned && e->entries.update_entry.pinned && e->entries.reset_body.pinned && !ep_component33_resource_entries_cancel(s->mod,e->entries.handle),"refresh complete lifetime");
    t.pages[0]=OwnPage(0x200000000);t.pages[1]=OwnPage(0x183320000);t.pages[2]=OwnPage(0x2d0000000);
    auto* component=(uint8_t*)t.pages[0];auto* registry=(uint8_t*)t.pages[2];
    W64((uint8_t*)t.pages[1]+0x6e68,mode==7 ? 0 : 0x2d0000000);W32(component+12,mode==4 ? 0 : 8);W32(component+0x100+12,5);
    W32(registry+0x1f78,mode==2 ? 0 : mode==23 || mode==24 ? 4 : 3);
    // Foreign registry tags are skipped without dereferencing their pointer.
    W64(registry+0x1f80,0xbad);W32(registry+0x1f88,0x11);
    W64(registry+0x1f90,0x200000000+(mode==6 ? 0x100 : 0));W32(registry+0x1f98,mode==3 ? 0x12 : 0x7c);
    W64(registry+0x1fa0,0xbad);W32(registry+0x1fa8,0x33);
    W64(registry+0x1fb0,mode==24 ? 0x200000100 : 0x200000000);W32(registry+0x1fb8,0x7c);
    unsigned ordinal=mode==1 ? 7 : 4;
    if (mode==1) {
        W32(p->header+8,8);W32(p->header+12,8);p->count=8;
        for (unsigned i=5;i<8;i++) {
            p->pointers[i]=p->threshold_pointers[i]=0x250000000+64*i;
            W64(p->entities[i],0x12000+i);W32(p->entities[i]+8,50+i);W32(p->entities[i]+16,10+i);
            W32(p->header+0x14+((50+i)&7)*8,50+i);W32(p->header+0x18+((50+i)&7)*8,i);
        }
        W64(p->packages,0);W64(p->packages+16,0x12007);W64(p->packages+24,0);
        memcpy(p->thresholds+7*0x58,p->thresholds+4*0x58,0x58);
    }
    t.object=mode==5 ? 0x260009000 : 0x260000000+ordinal*0x100;
    if (mode==8 || mode==22) W32(p->header+8,9);
    auto* arena=(uint8_t*)(uintptr_t)s->resources.binding.address;
    if (mode==9) {
        memset(arena+32,0,s->resources.arena_bytes-32);
        for (unsigned i=0;i<512;i++) { unsigned at=(1024+i)&511;W64(arena+48+512*8+at*16,1024+i);W64(arena+48+512*8+at*16+8,1); }
    }
    if (mode==16) Check(ep_roster_owner_close(s->mod,s->owner)==0,"refresh closed owner");
    uint8_t before[48+512*24],old[EP_COMPONENT33_STORAGE_BYTES];memcpy(before,arena,sizeof(before));memcpy(old,(void*)(uintptr_t)s->storage.storage_address,sizeof(old));
    int result=0,fault=0;
    if (mode==14) { result=ep_roster_owner_call(s->mod,s->owner,0,RefreshNested,&t)==0;fault=!result; }
    else if (mode==13) {
        HANDLE worker=CreateThread(nullptr,0,RefreshThread,&t,0,nullptr);Check(worker!=nullptr,"refresh worker");
        Check(WaitForSingleObject(s->entered,5000)==WAIT_OBJECT_0,"refresh load entered");Observer observer={};observer.test=s;
        HANDLE reader=CreateThread(nullptr,0,Observe,&observer,0,nullptr);Check(reader!=nullptr,"refresh reader");
        ULONGLONG until=GetTickCount64()+5000;while (!Pending(s,false) && GetTickCount64()<until) Sleep(1);
        Check(Pending(s,false) && WaitForSingleObject(reader,0)==WAIT_TIMEOUT,"reader escaped refresh frame");
        SetEvent(s->proceed);Check(WaitForSingleObject(worker,5000)==WAIT_OBJECT_0 && WaitForSingleObject(reader,5000)==WAIT_OBJECT_0,"refresh wait");
        Check(observer.status==0 && observer.info.revision==2,"refresh reader revision");CloseHandle(worker);CloseHandle(reader);result=1;
    } else result=EpOwnerInvoke(RefreshRun,&t,&fault);
    bool success=mode<=5 || mode==13 || mode==14 || mode==23;bool wrote=mode<=1 || mode==13 || mode==14 || mode==23;
    Check(bool(result)==success && bool(fault)==!success && t.returned==unsigned(success),"refresh returned after failure");
    Check(bool(e->rejected)==!success && !updating && !resourceCall && !ep_roster_owner_in_scope(),"refresh TLS/rejection");
    unsigned effects=mode==23 ? 9 : wrote || mode==24 ? 3 : mode==11 ? 2 : 0;
    Check(t.effects==effects && e->sdk_bytes<=65536 && !hooks,"refresh effects/budget/publication");
    if (effects>=3) {
        Check(t.ops[0]==EP_RESOURCE_DISPOSE && t.keys[0]==101 && t.ops[1]==EP_RESOURCE_LOAD && t.keys[1]==101 && t.ops[2]==EP_RESOURCE_LOAD && t.keys[2]==103,"refresh effect order");
        auto* buckets=(EpC33ResourceEntry*)(arena+48+512*8);uint64_t refs[3]={};
        for (unsigned i=0;i<512;i++) if (buckets[i].key>=101 && buckets[i].key<=103) refs[buckets[i].key-101]=buckets[i].references;
        Check(refs[0]==1 && refs[1]==1 && refs[2]==1 && !*(uint64_t*)(arena+32),"refresh reference/queue totals");
        if (mode==23) for (unsigned i=3;i<9;i++) Check(t.ops[i]==(i<6 ? EP_RESOURCE_DISPOSE : EP_RESOURCE_LOAD) && t.keys[i]==101+(i%3),"second registry row resource order");
    } else if (!effects) Check(!memcmp(before,arena,sizeof(before)),"refused/empty refresh changed resources");
    Check(!memcmp(old,(void*)(uintptr_t)s->storage.storage_address,sizeof(old)),"refresh changed player arrays");
    if (mode==2 || mode==3 || mode==4 || mode==6 || mode==7 || mode==16) Check(!p->reads && !p->codes,"skipped/refused registry read SDK");
    if (mode!=16) {
        EpRosterOwnerInfo info={};Check(ep_roster_owner_info(s->mod,s->owner,&info)==0,"refresh owner info");
        Check(bool(info.fault)==!success && info.revision==(mode==15 ? UINT64_MAX : wrote ? 2u : 1u),"refresh quarantine/revision");
        if (!success) { unsigned old_effects=t.effects;int again=0;Check(!EpOwnerInvoke(RefreshRun,&t,&again) && again && !updating && t.effects==old_effects,"refresh retried after fault"); }
        Check(ep_roster_owner_close(s->mod,s->owner)==0,"refresh owner close");
    }
    for (void* page:t.pages) Check(VirtualFree(page,0,MEM_RELEASE)!=0,"refresh owned page cleanup");
    CloseHandle(s->entered);CloseHandle(s->proceed);Check(allocations==frees,"refresh scratch leak");
    refreshing=nullptr;entryTest=nullptr;nativeTest=nullptr;active=nullptr;return checks;
}
EXPORT int c33_refresh_build(const EpC33RefreshAddresses* a,EpComponent33Image* image) { return ep_component33_refresh_build(a,image); }
