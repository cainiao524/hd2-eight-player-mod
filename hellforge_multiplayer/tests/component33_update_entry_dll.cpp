/* Executes the relocated UPDATE's empty-component path in this test process.
 * Every dereferenced S/global page is allocated below; engine/SDK calls are
 * test functions. No game process, installation or executable is opened. */
#include "component33_update_dll.cpp"
#include "../mod/src/ep_component33_resource_entries.cpp"
struct WholeUpdate { EntryTest entry;unsigned mode,delta,observed,returned;void* pages[3]; };
static WholeUpdate* whole;
static int WholeRun(void* p)
{
    auto* t=(WholeUpdate*)p;float delta;memcpy(&delta,&t->delta,4);
    ((void(*)(uint64_t,float))t->entry.entries.update_entry.base)(t->entry.component,delta);
    ++t->returned;return 1;
}
static int WholeNested(void* p,const EpNativeRosterView*) { return WholeRun(p); }
static DWORD WINAPI WholeThread(void* p) { WholeRun(p);return 0; }
static void WholeReject(void* p,uint32_t kind,const EpC33ResourceProviderResult* result)
{
    auto* t=(WholeUpdate*)p;++t->entry.rejected;t->entry.failure=*result;
    Check((kind==EP_C33_UPDATE || kind==EP_C33_RESOURCE_DRAIN) && result->call.status!=0,"whole UPDATE rejection");
    if (t->mode==17) RaiseException(0xe04333ff,EXCEPTION_NONCONTINUABLE,0,nullptr);
}
static __declspec(noinline) uint32_t SavedDelta()
{
    CONTEXT c={};RtlCaptureContext(&c);auto* tib=(NT_TIB*)NtCurrentTeb();
    for (unsigned i=0;i<128;i++) {
        Check(c.Rsp>=(uintptr_t)tib->StackLimit && c.Rsp+0xa0<(uintptr_t)tib->StackBase,"test unwind left own stack");
        const auto& body=whole->entry.entries.update_body;
        if (c.Rip>=body.base && c.Rip<body.base+body.bytes) {
            // Saved UPDATE: push 3 registers, sub rsp,70; initial MOVSS writes
            // entry RSP+10. Empty S takes the branch before any reused locals.
            uint32_t bits;memcpy(&bits,(void*)(uintptr_t)(c.Rsp+0x98),4);return bits;
        }
        DWORD64 base=0,frame=0;PVOID data=nullptr;auto* row=RtlLookupFunctionEntry(c.Rip,&base,nullptr);
        if (row) RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,c.Rip,row,&c,&data,&frame,nullptr);
        else { memcpy(&c.Rip,(void*)(uintptr_t)c.Rsp,8);c.Rsp+=8; }
    }
    Check(false,"relocated UPDATE absent from native stack");return 0;
}
static void WholeDispose(uint64_t key,uint64_t table)
{
    auto* t=whole;Check(SavedDelta()==t->delta,"XMM1 float bits changed across whole UPDATE");++t->observed;
    NativeDispose(key,table);
    if (t->mode==11) WholeRun(t);
    if (t->mode==10) { auto* s=&t->entry.native.p.test;SetEvent(s->entered);Check(WaitForSingleObject(s->proceed,5000)==WAIT_OBJECT_0,"whole UPDATE wait"); }
}
static void* OwnPage(uintptr_t address)
{
    void* page=VirtualAlloc((void*)address,65536,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    Check(page==(void*)address,"own UPDATE fixture page");return page;
}
static void CheckUpdateLeaf(const EpC33ResourceEntriesInfo& info)
{
    for (unsigned offset=0;offset<44;offset++) {
        auto& code=info.update_entry;DWORD64 base=0;auto* row=RtlLookupFunctionEntry(code.base+offset,&base,nullptr);
        Check(row && base==code.base && row->BeginAddress==(offset<32 ? 0u : 32u) && row->EndAddress==(offset<32 ? 32u : 44u),"UPDATE leaf registration");
        uint64_t stack[]={0x123456780,0,0,0};CONTEXT c={};c.ContextFlags=CONTEXT_FULL;c.Rip=code.base+offset;c.Rsp=(uintptr_t)stack;
        c.Rbx=101;c.Rbp=102;c.Rsi=103;c.Rdi=104;c.R12=105;c.R13=106;c.R14=107;c.R15=108;
        DWORD64 frame=0;PVOID data=nullptr;RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,c.Rip,row,&c,&data,&frame,nullptr);
        Check(c.Rip==stack[0] && c.Rsp==(uintptr_t)(stack+1) && c.Rbx==101 && c.Rbp==102 && c.Rsi==103 && c.Rdi==104 && c.R12==105 && c.R13==106 && c.R14==107 && c.R15==108,"UPDATE leaf unwind");
    }
}
EXPORT unsigned c33_resource_whole_update_test(unsigned mode)
{
    Check(mode<18,"whole UPDATE scenario");WholeUpdate t={};t.mode=mode;whole=&t;entryTest=&t.entry;t.entry.mode=200+mode;
    NativeSetup(&t.entry.native,mode==3 ? 4 : mode==4 ? 5 : mode==5 || mode==17 ? 15 : mode==9 ? 28 : 0);
    auto* e=&t.entry;auto* n=&e->native;auto* s=&n->p.test;
    n->api.read=EntryRead;n->api.read_code=EntryCode;n->api.hook_ex=Hook;n->dispose_target=(uintptr_t)WholeDispose;
    EpC33ResourceEntryBindings b={s->storage.handle,s->owner,{0x191000000,0x191010000,0x191020000,0x191030000},WholeReject,&t};
    EpC33UpdateEntryConfig config={0x191040000,mode==14 ? UINT64_C(0x191040000) : mode==15 ? UINT64_C(0x280000000) : UINT64_C(0x191050000)};
    bool prepared=ep_component33_resource_entries_prepare_update(&n->api,s->mod,&b,mode==16 ? nullptr : &config,&e->entries)!=0;
    Check(prepared==(mode!=14 && mode!=15 && mode!=16),"whole UPDATE prepare outcome");
    Check(!n->p.reads && !n->p.codes && !n->calls && !hooks,"whole UPDATE preparation accessed source");
    if (!prepared) {
        Check(!e->entries.handle,"whole UPDATE partial cleanup");
        config.desired_body=0x191050000;Check(ep_component33_resource_entries_prepare_update(&n->api,s->mod,&b,&config,&e->entries),"whole UPDATE preparation retry");
    }
    Check(e->entries.update_target==s->roster.game+0x664520 && e->entries.update_entry.registered && e->entries.update_body.registered,"whole UPDATE targets/unwind");
    UnwindEntries(e->entries);CheckUpdateLeaf(e->entries);
    if (mode>=13 && mode<=16) {
        auto old=e->entries;Check(ep_component33_resource_entries_cancel(s->mod,old.handle),"whole UPDATE cancel");
        DWORD64 base=0;Check(!RtlLookupFunctionEntry(old.update_entry.base,&base,nullptr) && !RtlLookupFunctionEntry(old.update_body.base,&base,nullptr),"whole UPDATE cancelled unwind still registered");
        Check(ep_roster_owner_close(s->mod,s->owner)==EP_OWNER_OK,"whole UPDATE preparation owner close");CloseHandle(s->entered);CloseHandle(s->proceed);return checks;
    }
    Check(ep_component33_resource_entries_retain(s->mod,e->entries.handle),"whole UPDATE retain");
    Check(ep_component33_resource_entries_info(s->mod,e->entries.handle,&e->entries),"whole UPDATE info");
    for (const auto& code:e->entries.code) Check(code.pinned && code.state==EP_CODE_RETAINED,"resource dependency not retained");
    Check(e->entries.update_body.pinned && e->entries.update_entry.pinned && !ep_component33_resource_entries_cancel(s->mod,e->entries.handle),"whole UPDATE incomplete lifetime");
    t.pages[0]=OwnPage(0x200000000);t.pages[1]=OwnPage(0x183320000);t.pages[2]=OwnPage(0x183480000);
    auto* component=(uint8_t*)t.pages[0];W64(component+0x58,0x200000014);W32(component+0x60,mode==7 ? 7 : 8);W32(component+0x68,1);
    W64((uint8_t*)t.pages[1]+0x67b8,0x200000000);W32((uint8_t*)t.pages[2]+0x3c34,0xffffffff);
    e->component=0x200000000+(mode==6 ? 8 : 0);t.delta=mode==1 ? 0x80000000 : mode==2 ? 0x7fc12345 : 0x3e99999a;
    if (mode==8) Check(ep_roster_owner_close(s->mod,s->owner)==EP_OWNER_OK,"whole UPDATE close before entry");
    uint8_t before[48+512*24];memcpy(before,(void*)(uintptr_t)s->resources.binding.address,sizeof(before));int fault=0,result=0;
    if (mode==12) { result=ep_roster_owner_call(s->mod,s->owner,0,WholeNested,&t)==EP_OWNER_OK;fault=!result; }
    else if (mode==10) {
        HANDLE worker=CreateThread(nullptr,0,WholeThread,&t,0,nullptr);Check(worker!=nullptr,"whole UPDATE worker");
        Check(WaitForSingleObject(s->entered,5000)==WAIT_OBJECT_0,"whole UPDATE dispose entered");Observer observer={};observer.test=s;
        HANDLE reader=CreateThread(nullptr,0,Observe,&observer,0,nullptr);Check(reader!=nullptr,"whole UPDATE reader");
        ULONGLONG until=GetTickCount64()+5000;while (!Pending(s,false) && GetTickCount64()<until) Sleep(1);
        Check(Pending(s,false) && WaitForSingleObject(reader,0)==WAIT_TIMEOUT,"reader escaped complete UPDATE");
        SetEvent(s->proceed);Check(WaitForSingleObject(worker,5000)==WAIT_OBJECT_0 && WaitForSingleObject(reader,5000)==WAIT_OBJECT_0,"whole UPDATE threads");
        Check(observer.status==EP_OWNER_OK && observer.info.revision==2,"whole UPDATE reader revision");CloseHandle(worker);CloseHandle(reader);result=1;
    } else result=EpOwnerInvoke(WholeRun,&t,&fault);
    bool success=mode<=4 || mode==10 || mode==12;
    Check(bool(result)==success && bool(fault)==!success && t.returned==unsigned(success),"whole UPDATE returned after failure");
    Check(bool(e->rejected)==!success && !updating && !resourceCall && !ep_roster_owner_in_scope(),"whole UPDATE TLS/rejection cleanup");
    unsigned effects=mode<=2 || mode==5 || mode==10 || mode==11 || mode==12 || mode==17 ? 1u : 0u;
    Check(n->calls==effects && t.observed==effects && !n->contexts && !n->resolvers && e->sdk_bytes<=65536,"whole UPDATE service/ABI/budget");
    if (success && effects) Check(*(uint64_t*)(uintptr_t)(s->resources.binding.address+32)==0,"whole UPDATE drain did not commit");
    else Check(!memcmp(before,(void*)(uintptr_t)s->resources.binding.address,sizeof(before)),"failed/blocked whole UPDATE changed arena");
    if (mode==6 || mode==7 || mode==8 || mode==9) Check(!n->p.reads && !n->p.codes,"refused whole UPDATE read SDK");
    if (mode!=8) {
        EpRosterOwnerInfo info={};Check(ep_roster_owner_info(s->mod,s->owner,&info)==EP_OWNER_OK,"whole UPDATE owner info");
        Check(bool(info.fault)==!success && info.revision==(mode==9 ? UINT64_MAX : success ? 2u : 1u),"whole UPDATE quarantine/revision");
        if (!success) { unsigned calls=n->calls,bytes=e->sdk_bytes;int again=0;Check(!EpOwnerInvoke(WholeRun,&t,&again) && again && !updating && n->calls==calls && e->sdk_bytes==bytes,"whole UPDATE retry after failure"); }
        Check(ep_roster_owner_close(s->mod,s->owner)==EP_OWNER_OK,"whole UPDATE close");
    }
    for (void* p:t.pages) Check(VirtualFree(p,0,MEM_RELEASE)!=0,"own UPDATE page cleanup");
    CloseHandle(s->entered);CloseHandle(s->proceed);Check(allocations==frees && !hooks,"whole UPDATE leak/publication");
    whole=nullptr;entryTest=nullptr;nativeTest=nullptr;active=nullptr;return checks;
}
