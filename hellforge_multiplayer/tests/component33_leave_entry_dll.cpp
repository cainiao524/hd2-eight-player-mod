/* B51DE0 uses owned registry/S pages and SDK fixture buffers only. */
#include "component33_refresh_entry_dll.cpp"
struct LeaveTest { EntryTest entry;unsigned mode,returned;uint64_t object;void* pages[3]; };
static LeaveTest* leaving;
static int LeaveRun(void* p)
{
    auto* t=(LeaveTest*)p;((void(*)(uint64_t,uint32_t))t->entry.entries.leave_entry.base)(t->object,0xfedcba91);++t->returned;return 1;
}
static int LeaveNested(void* p,const EpNativeRosterView*) { return LeaveRun(p); }
static DWORD WINAPI LeaveThread(void* p) { LeaveRun(p);return 0; }
static void LeaveReject(void* p,uint32_t kind,const EpC33ResourceProviderResult* result)
{
    auto* t=(LeaveTest*)p;++t->entry.rejected;t->entry.failure=*result;
    Check((kind==EP_C33_RESOURCE_LEAVE || kind==EP_C33_DEFER || kind==EP_C33_RESOURCE_REFRESH) && result->call.status,"leave refusal diagnostic");
    if (t->mode==22) RaiseException(0xe04333fe,EXCEPTION_NONCONTINUABLE,0,nullptr);
}
static void LeaveStack()
{
    CONTEXT c={};RtlCaptureContext(&c);auto* tib=(NT_TIB*)NtCurrentTeb();bool found=false;
    for (unsigned i=0;i<128;i++) {
        Check(c.Rsp>=(uintptr_t)tib->StackLimit && c.Rsp+8<(uintptr_t)tib->StackBase,"leave unwind escaped stack");
        const auto& body=leaving->entry.entries.leave_body;bool current=c.Rip>=body.base && c.Rip<body.base+body.bytes;
        DWORD64 base=0,frame=0;PVOID data=nullptr;auto* row=RtlLookupFunctionEntry(c.Rip,&base,nullptr);
        if (row) RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,c.Rip,row,&c,&data,&frame,nullptr);
        else { memcpy(&c.Rip,(void*)(uintptr_t)c.Rsp,8);c.Rsp+=8; }
        if (current) { Check(row && base==body.base && (c.Rip<body.base || c.Rip>=body.base+body.bytes),"leave unwind did not leave frame");found=true;break; }
    }
    Check(found,"owned leave frame absent");
}
static uint64_t LeaveContext(uint64_t engine)
{
    LeaveStack();auto* t=leaving;auto* n=&t->entry.native;auto* s=&n->p.test;
    if (t->mode==12) LeaveRun(t);
    if (t->mode==29) ((void(*)(uint64_t))t->entry.entries.refresh_entry.base)(t->object);
    if (t->mode==13 && !n->contexts) { SetEvent(s->entered);Check(WaitForSingleObject(s->proceed,5000)==WAIT_OBJECT_0,"leave context wait"); }
    return NativeContext(engine);
}
static uint64_t LeaveResolve(uint64_t context,uint32_t handle)
{
    auto* n=&leaving->entry.native;++n->resolvers;
    Check(context==n->context_value && handle>=10 && handle<18 && handle!=11 && ep_component33_resource_scope_ready(n->p.test.mod,n->p.test.owner),"leave resolver ABI");
    if (leaving->mode==11) RaiseException(0xe04333ff,0,0,nullptr);
    return 0x260000000+uint64_t(handle-10)*0x100;
}
EXPORT unsigned c33_resource_whole_leave_test(unsigned mode)
{
    Check(mode<30,"leave scenario");LeaveTest t={};t.mode=mode;leaving=&t;entryTest=&t.entry;
    NativeSetup(&t.entry.native,mode==10 ? 12 : mode==15 ? 28 : 0);auto* e=&t.entry;auto* n=&e->native;auto* p=&n->p;auto* s=&p->test;
    n->api.read=EntryRead;n->api.read_code=EntryCode;n->api.hook_ex=Hook;n->context_target=(uintptr_t)LeaveContext;n->resolver_target=(uintptr_t)LeaveResolve;
    // Deferred release does not need a load/dispose table or either service.
    n->load_target=n->dispose_target=n->service_table=0;
    EpC33ResourceEntryBindings b={s->storage.handle,s->owner,{0x191000000,0x191010000,0x191020000,0x191030000},LeaveReject,&t};
    EpC33LeaveEntryConfig config={{{{0x191040000,0x191050000},{0x191060000,0x191070000},0x191080000},0x191090000,0x1910a0000},0x1910b0000,0x1910c0000};
    if (mode==18) config.desired_entry=config.refresh.desired_body;
    if (mode==19) config.desired_body=config.desired_entry;
    if (mode==20) config.desired_body=0x280000000;
    bool prepared=ep_component33_resource_entries_prepare_leave(&n->api,s->mod,&b,mode==21 ? nullptr : &config,&e->entries)!=0;
    Check(prepared==!(mode>=18 && mode<=21),"leave prepare outcome");
    Check(!p->reads && !p->codes && !n->contexts && !n->calls && !hooks,"leave prepare accessed source");
    if (!prepared) {
        Check(!e->entries.handle,"leave incomplete cleanup");config.desired_entry=0x1910b0000;config.desired_body=0x1910c0000;
        Check(ep_component33_resource_entries_prepare_leave(&n->api,s->mod,&b,&config,&e->entries),"leave prepare retry");
    }
    Check(e->entries.leave_target==0x180b51de0 && e->entries.leave_body.registered,"leave target/unwind");ResetLeaf(e->entries.leave_entry);
    EpSessionCodeInfo* all[]={&e->entries.code[0],&e->entries.code[1],&e->entries.code[2],&e->entries.code[3],
        &e->entries.update_entry,&e->entries.update_body,&e->entries.reset_entries[0],&e->entries.reset_entries[1],&e->entries.reset_body,
        &e->entries.refresh_entry,&e->entries.refresh_body,&e->entries.leave_entry,&e->entries.leave_body};
    if (mode>=17 && mode<=21) {
        Check(ep_component33_resource_entries_cancel(s->mod,e->entries.handle),"leave cancel");
        for (const auto* code:all) { DWORD64 base=0;Check(!RtlLookupFunctionEntry(code->base,&base,nullptr),"leave dependency survived cancel"); }
        Check(ep_roster_owner_close(s->mod,s->owner)==0,"leave cancel owner");CloseHandle(s->entered);CloseHandle(s->proceed);return checks;
    }
    if (mode!=28) {
        Check(ep_component33_resource_entries_retain(s->mod,e->entries.handle),"leave retain");
        Check(ep_component33_resource_entries_info(s->mod,e->entries.handle,&e->entries),"leave info");
        for (const auto* code:all) Check(code->pinned && code->registered,"leave dependency lifetime");
        Check(!ep_component33_resource_entries_cancel(s->mod,e->entries.handle),"leave retained cancellation");
    }
    t.pages[0]=OwnPage(0x200000000);t.pages[1]=OwnPage(0x183320000);t.pages[2]=OwnPage(0x2d0000000);
    auto* component=(uint8_t*)t.pages[0];auto* registry=(uint8_t*)t.pages[2];
    W64((uint8_t*)t.pages[1]+0x6e68,mode==7 ? 0 : 0x2d0000000);W32(component+12,mode==4 ? 0 : 8);W32(component+0x100+12,5);
    W32(registry+0xd10,mode==2 ? 0 : mode==23 || mode==24 ? 4 : 3);
    // Default tags must bypass bad pointers; native 119 uses a separate owned
    // row, proving that non-component33 writes survive copying and faults.
    W64(registry+0xd18,mode==25 || mode==26 ? 0x200000200 : 0xbad);W32(registry+0xd20,mode==25 || mode==26 ? 0x119 : 0);
    W64(registry+0xd28,0x200000000+(mode==6 || mode==26 ? 0x100 : 0));W32(registry+0xd30,mode==3 ? 0 : 0x7c);
    W64(registry+0xd38,0xbad);W32(registry+0xd40,0xffffffff);
    W64(registry+0xd48,mode==24 ? 0x200000100 : 0x200000000);W32(registry+0xd50,0x7c);
    unsigned ordinal=mode==1 ? 7 : 4;
    if (mode==1) {
        W32(p->header+8,8);W32(p->header+12,8);p->count=8;
        for (unsigned i=5;i<8;i++) {
            p->pointers[i]=p->threshold_pointers[i]=0x250000000+64*i;
            W64(p->entities[i],0x12000+i);W32(p->entities[i]+8,50+i);W32(p->entities[i]+16,10+i);
            W32(p->header+0x14+((50+i)&7)*8,50+i);W32(p->header+0x18+((50+i)&7)*8,i);
        }
        W64(p->packages,0);W64(p->packages+16,0x12007);W64(p->packages+24,0);
        memcpy((void*)(uintptr_t)s->storage.storage_address,p->pointers,sizeof(p->pointers));
    }
    t.object=mode==5 ? 0x260009000 : 0x260000000+ordinal*0x100;
    W64(component+0x220,t.object);memset(component+0x228,0xa5,24);
    if (mode==8 || mode==22) W32(p->header+8,9);
    if (mode==27) e->mode=10;
    auto* arena=(uint8_t*)(uintptr_t)s->resources.binding.address;
    if (mode==9) W64(arena+32,513);
    if (mode==23) W64(arena+48+512*8+101*16+8,2);
    if (mode==16) Check(ep_roster_owner_close(s->mod,s->owner)==0,"leave closed owner");
    uint8_t before[48+512*24],old[EP_COMPONENT33_STORAGE_BYTES];memcpy(before,arena,sizeof(before));memcpy(old,(void*)(uintptr_t)s->storage.storage_address,sizeof(old));
    int result=0,fault=0;
    if (mode==14) { result=ep_roster_owner_call(s->mod,s->owner,0,LeaveNested,&t)==0;fault=!result; }
    else if (mode==13) {
        HANDLE worker=CreateThread(nullptr,0,LeaveThread,&t,0,nullptr);Check(worker!=nullptr,"leave worker");
        Check(WaitForSingleObject(s->entered,5000)==WAIT_OBJECT_0,"leave context entered");Observer observer={};observer.test=s;
        HANDLE reader=CreateThread(nullptr,0,Observe,&observer,0,nullptr);Check(reader!=nullptr,"leave reader");
        ULONGLONG until=GetTickCount64()+5000;while (!Pending(s,false) && GetTickCount64()<until) Sleep(1);
        Check(Pending(s,false) && WaitForSingleObject(reader,0)==WAIT_TIMEOUT,"reader escaped leave frame");
        SetEvent(s->proceed);Check(WaitForSingleObject(worker,5000)==WAIT_OBJECT_0 && WaitForSingleObject(reader,5000)==WAIT_OBJECT_0,"leave wait");
        Check(observer.status==0 && observer.info.revision==2,"leave reader revision");CloseHandle(worker);CloseHandle(reader);result=1;
    } else result=EpOwnerInvoke(LeaveRun,&t,&fault);
    bool success=mode<=5 || mode==13 || mode==14 || mode==23 || mode==25;
    bool released=mode<=1 || mode==13 || mode==14 || mode==23 || mode==24 || mode==25;
    Check(bool(result)==success && bool(fault)==!success && t.returned==unsigned(success),"leave returned after failure");
    Check(bool(e->rejected)==!success && !updating && !resourceCall && !ep_roster_owner_in_scope(),"leave TLS/rejection");
    Check(!n->calls && e->sdk_bytes<=65536 && !hooks,"leave service/budget/publication");
    if (released) {
        uint64_t q[2];memcpy(q,arena+48,16);
        Check(*(uint64_t*)(arena+32)==2 && q[0]==102 && q[1]==101 && !*(uint64_t*)(arena+48+512*8+101*16+8),"leave queue/reference totals");
        Check(n->contexts==(mode==1 ? 7u : mode==23 ? 8u : 4u) && n->resolvers==n->contexts,"leave selected ordinal/duplicate rows");
    } else Check(!memcmp(before,arena,sizeof(before)),"refused/empty leave changed resources");
    Check(!memcmp(old,(void*)(uintptr_t)s->storage.storage_address,sizeof(old)),"leave changed player arrays");
    if (mode==25 || mode==26) for (unsigned i=0;i<32;i++) Check(!component[0x220+i],"leave lost earlier native tag119 effects");
    if (mode==2 || mode==3 || mode==4 || mode==6 || mode==7 || mode==15 || mode==16 || mode==26 || mode==28) Check(!p->reads && !p->codes,"skipped/refused leave read SDK");
    if (mode!=16) {
        EpRosterOwnerInfo info={};Check(ep_roster_owner_info(s->mod,s->owner,&info)==0,"leave owner info");
        Check(bool(info.fault)==(!success && mode!=28) && info.revision==(mode==15 ? UINT64_MAX : success ? 2u : 1u),"leave quarantine/revision");
        if (!success) { unsigned old_reads=p->reads;int again=0;Check(!EpOwnerInvoke(LeaveRun,&t,&again) && again && !updating && p->reads==old_reads,"leave retried after fault"); }
        if (mode==28) Check(ep_component33_resource_entries_cancel(s->mod,e->entries.handle),"leave unretained cleanup");
        Check(ep_roster_owner_close(s->mod,s->owner)==0,"leave owner close");
    }
    for (void* page:t.pages) Check(VirtualFree(page,0,MEM_RELEASE)!=0,"leave owned page cleanup");
    CloseHandle(s->entered);CloseHandle(s->proceed);Check(allocations==frees,"leave scratch leak");
    leaving=nullptr;entryTest=nullptr;nativeTest=nullptr;active=nullptr;return checks;
}
EXPORT int c33_leave_build(const EpC33LeaveAddresses* a,EpComponent33Image* image) { return ep_component33_leave_build(a,image); }
