/* Actual session-code publication/entry execution, with a bounded SDK-chain
 * callback and window/data guard fixtures. No game process or installation.
 * SDK callbacks map ONLY the three supplied windows into test-owned buffers;
 * no real engine pause, ownership transfer or other subsystem is claimed. */
#include "component33_caller_entry_dll.cpp"
struct PublicationTest {
    EntryTest entry;EntryGroup* group;EpC33EntryCommitGuard guard;
    unsigned mode,index,hooked,old_calls,new_calls,reads,writes,begins,validations,ends;
    unsigned restore[3],restored;bool lease,staged,hold,alternate,write_failed,guard_reentry;uint32_t outcome;
    uint8_t windows[3][75];
};
static PublicationTest* publishing;
struct PubCall {PublicationTest* test;unsigned index;bool active;};
static int PubRun(void*);
static uint64_t PubProbe(bool next,uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f)
{
    auto* t=publishing;auto* s=&t->entry.native.p.test;
    Check(routeGroup==t->group && routeKinds && ep_roster_owner_native_status(s->mod,s->owner)==0,"published call outside owner");
    Check(bool(InterlockedCompareExchange(&t->group->active,0,0))==next,"mixed route selection");
    Check(a==0x1111222233334444 && b==0x5555666677778888 && c==0x9999aaaabbbbcccc && d==0xddddeeeeffff0000,"published register arguments");
    if (t->index==14) Check(e==0x123456789abcdef0 && f==0xfedcba9876543210,"published PROPERTY stack arguments");
    if (next) {++t->new_calls;Check(coreGroup==t->group,"NEW skipped managed core entry");}
    else {++t->old_calls;Check(!coreGroup,"OLD ran managed core");}
    if (t->hold) {SetEvent(s->entered);Check(WaitForSingleObject(s->proceed,5000)==WAIT_OBJECT_0,"old call wait");}
    return next ? 0x9111000011110001 : 0x1111000011110001;
}
static uint64_t PubOld(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f) {return PubProbe(false,a,b,c,d,e,f);}
static uint64_t PubNew(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f) {return PubProbe(true,a,b,c,d,e,f);}
static uint64_t PubAlternate(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f)
{publishing->alternate=true;return PubOld(a,b,c,d,e,f);}
static int PubRun(void* p)
{
    auto* c=(PubCall*)p;auto* t=c->test;t->index=c->index;
    auto fn=(uint64_t(*)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t))RouteCode(t->group,c->index)->base;
    uint64_t value=fn(0x1111222233334444,0x5555666677778888,0x9999aaaabbbbcccc,0xddddeeeeffff0000,0x123456789abcdef0,0xfedcba9876543210);
    Check(value==(c->active ? 0x9111000011110001 : 0x1111000011110001),"published return value");return 1;
}
static void PubReject(void* p,uint32_t,const EpC33ResourceProviderResult* result)
{auto* t=(PublicationTest*)p;++t->entry.rejected;t->entry.failure=*result;t->guard_reentry|=result->call.status==EP_C33_CALL_REENTRANT;Check(result->call.status,"published refusal diagnostics");}
static int PubHook(HfMod* mod,uintptr_t target,void* detour,void** original,int32_t priority)
{
    auto* t=publishing;unsigned index=t->hooked++;auto* s=&t->entry.native.p.test;
    Check(index<25 && mod==s->mod && priority==17 && target==RouteTarget(t->group,index) && detour==(void*)RouteCode(t->group,index)->base &&
        original==(void**)RouteCode(t->group,index)->next_pointer,"SDK publication binding");
    Check(!t->group->active && t->group->info.publication_state==EP_C33_PUBLISHING,"publication activated early");
    if (t->mode==52) Check(!ep_component33_resource_entries_publish(s->mod,t->entry.entries.handle,17) &&
        !ep_component33_resource_entries_commit(s->mod,t->entry.entries.handle,&t->guard),"reentrant publication accepted");
    if (t->mode>=1 && t->mode<=25 && index==t->mode-1) return 1;
    if (t->mode==51 && index==24) return 0;
    InterlockedExchangePointer(original,(void*)PubOld);
    // Simulate exposure after next is populated, including a subsequent SDK
    // error. All prior nodes must still forward through OLD, not their bodies.
    for (unsigned i=0;i<=index;i++) {PubCall call={t,i,false};PubRun(&call);}
    return t->mode>=26 && t->mode<=50 && index==t->mode-26 ? 1 : 0;
}
static unsigned WindowIndex(uintptr_t target,size_t bytes)
{
    for (unsigned i=0;i<3;i++) {auto w=GetWindow(publishing->group,i);if (target==w.target && bytes==w.bytes) return i;}
    Check(false,"unlisted SDK window read/write");return 0;
}
static int PubRead(uintptr_t target,void* out,size_t bytes)
{
    auto* t=publishing;unsigned i=WindowIndex(target,bytes);++t->reads;
    Check(t->lease && ep_roster_owner_native_status(t->entry.native.p.test.mod,t->entry.native.p.test.owner)==0,"window read outside exclusion");
    if (t->mode==66 && t->reads==1) return 1;
    if (t->mode==71 && t->reads==4) return 1;
    memcpy(out,t->windows[i],bytes);return 0;
}
static int PubWrite(uintptr_t target,const void* bytes,size_t length)
{
    auto* t=publishing;unsigned i=WindowIndex(target,length);++t->writes;auto w=GetWindow(t->group,i);
    Check(t->lease && t->staged && !t->group->active && t->group->switching &&
        ep_roster_owner_in_scope(),"window write outside staged exclusion");
    bool restore=!memcmp(bytes,w.expected,length);Check(restore || !memcmp(bytes,w.replacement,length),"unexpected window bytes");
    if (restore) {
        Check(t->restored<3,"excess restoration");t->restore[t->restored++]=i;
        if (t->mode==72 && i==1) return 1;
        if (t->mode==73 && i==1) RaiseException(0xe04333b1,0,0,nullptr);
        memcpy(t->windows[i],bytes,length);return 0;
    }
    unsigned failed_index=t->mode==67 || t->mode==70 || t->mode==71 ? 0 : t->mode==68 ? 1 : 2;
    bool fail=(t->mode>=67 && t->mode<=74) && i==failed_index;
    if (fail) {
        t->write_failed=true;
        if (t->mode==67) return 1;
        memcpy(t->windows[i],bytes,t->mode==68 || t->mode==74 ? length/2 : length);
        if (t->mode==70) {t->windows[i][0]^=1;return 0;}
        if (t->mode==71) return 0;
        if (t->mode==74) RaiseException(0xe04333b2,0,0,nullptr);
        return 1;
    }
    memcpy(t->windows[i],bytes,length);return 0;
}
static int PubBegin(void* p,void** lease)
{
    auto* t=(PublicationTest*)p;++t->begins;Check(!ep_roster_owner_in_scope(),"begin lock order");
    if (t->mode==60) return 0;if (t->mode==62) return 1;
    t->lease=true;*lease=t;
    if (t->mode==61) RaiseException(0xe04333b3,0,0,nullptr);return 1;
}
static int PubValidate(void* p,void* lease)
{
    auto* t=(PublicationTest*)p;++t->validations;
    Check(lease==t && t->lease && ep_roster_owner_in_scope() && t->group->switching && !t->group->active,"validate exclusion/latch");
    t->staged=true;
    if (t->mode==63) return 0;if (t->mode==64) RaiseException(0xe04333b4,0,0,nullptr);
    if (t->mode==76) {PubCall call={t,8,false};int fault=0;Check(!EpOwnerInvoke(PubRun,&call,&fault) && fault,"entry escaped staging");return 1;}
    if (t->mode==79) {auto* s=&t->entry.native.p.test;SetEvent(s->entered);Check(WaitForSingleObject(s->proceed,5000)==WAIT_OBJECT_0,"validate wait");}
    return 1;
}
static void PubEnd(void* p,void* lease,uint32_t outcome)
{
    auto* t=(PublicationTest*)p;++t->ends;t->outcome=outcome;
    Check((lease==t || t->mode==62) && outcome<=2,"end lease/outcome");
    if (t->mode!=77) Check(ep_roster_owner_in_scope(),"end outside owner");
    if (outcome==EP_C33_COMMIT_NEW) {
        Check(t->group->active==1 && t->staged,"NEW before data/latch");
        for (unsigned i=0;i<3;i++) {auto w=GetWindow(t->group,i);Check(!memcmp(t->windows[i],w.replacement,w.bytes),"NEW with mixed windows");}
        if (t->mode==75) RaiseException(0xe04333b5,0,0,nullptr);
        t->lease=false;
    } else if (outcome==EP_C33_COMMIT_OLD) {Check(!t->group->active,"OLD with active latch");t->staged=false;t->lease=false;}
    // UNSAFE deliberately keeps the simulated external lease. No resume.
}
static DWORD WINAPI PubCallThread(void* p) {PubRun(p);return 0;}
static DWORD WINAPI PubCommitThread(void* p)
{auto* t=(PublicationTest*)p;auto* s=&t->entry.native.p.test;return ep_component33_resource_entries_commit(s->mod,t->entry.entries.handle,&t->guard) ? 0 : 1;}
static int PubNativeGuard(void* p)
{
    auto* t=(PublicationTest*)p;
    if (t->mode==81) ((void(*)(uint64_t,float))t->entry.entries.update_entry.base)(0x200000000,0.25f);
    else ((void(*)(uint64_t))t->entry.entries.reset_entries[0].base)(0x200001100);
    return 1;
}
static void CheckLeaves(PublicationTest* t)
{
    for (unsigned i=0;i<25;i++) {
        auto code=*RouteCode(t->group,i);
        Check(code.bytes==(i==3 ? 112u : 80u),"routed reservation size");
        for (unsigned offset=0;offset<64;offset++) {
            DWORD64 base=0,frame=0;PVOID data=nullptr;auto* row=RtlLookupFunctionEntry(code.base+offset,&base,nullptr);
            Check(row && base==code.base && row->BeginAddress==0 && row->EndAddress==64,"routed/managed leaf unwind");
            uint64_t stack[]={0x123456780,0,0,0};CONTEXT c={};c.ContextFlags=CONTEXT_FULL;c.Rip=code.base+offset;c.Rsp=(uintptr_t)stack;c.Rbx=123;c.Rsi=456;
            RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,c.Rip,row,&c,&data,&frame,nullptr);
            Check(c.Rip==stack[0] && c.Rsp==(uintptr_t)(stack+1) && c.Rbx==123 && c.Rsi==456,"routed leaf restore");
        }
    }
    DWORD64 base=0;auto* row=RtlLookupFunctionEntry(t->entry.entries.update_entry.base+64,&base,nullptr);
    Check(row && row->BeginAddress==64 && row->EndAddress==76,"relocated UPDATE refusal unwind");
}
EXPORT unsigned c33_publication_test(unsigned mode)
{
    Check(mode<=52 || (mode>=60 && mode<=82) || mode==90 || mode==91,"publication scenario");
    PublicationTest t={};t.mode=mode;publishing=&t;entryTest=&t.entry;NativeSetup(&t.entry.native,0);
    auto* n=&t.entry.native;auto* s=&n->p.test;auto* e=&t.entry;n->api.read=EntryRead;n->api.read_code=PubRead;n->api.write=PubWrite;n->api.hook_ex=PubHook;
    t.guard={&t,PubBegin,PubValidate,PubEnd};
    EpC33ResourceEntryBindings b={s->storage.handle,s->owner,{0x191000000,0x191010000,0x191020000,0x191030000},PubReject,&t};
    EpC33CallerEntryConfig config={};config.core.leave={{{{0x191040000,0x191050000},{0x191060000,0x191070000},0x191080000},0x191090000,0x1910a0000},0x1910b0000,0x1910c0000};
    for (unsigned i=0;i<14;i++) config.core.desired_entries[i]=0x192000000+i*0x10000;
    for (unsigned i=0;i<3;i++) config.desired_entries[i]=0x193000000+i*0x10000;
    if (mode==90) n->api.write=nullptr;
    int prepared=ep_component33_resource_entries_prepare_transaction(&n->api,s->mod,&b,mode==91 ? nullptr : &config,&e->entries);
    Check(bool(prepared)==(mode<90) && !t.hooked && !t.reads && !t.writes && !e->sdk_bytes,"transaction preparation effects/result");
    if (!prepared) {Check(!e->entries.handle,"invalid transaction cleanup");Check(ep_roster_owner_close(s->mod,s->owner)==0,"close invalid transaction");CloseHandle(s->entered);CloseHandle(s->proceed);return checks;}
    t.group=Find(s->mod,e->entries.handle);Check(t.group!=nullptr,"transaction group");CheckLeaves(&t);
    for (unsigned i=0;i<3;i++) {auto w=GetWindow(t.group,i);memcpy(t.windows[i],w.expected,w.bytes);}
    Check(!ep_component33_resource_entries_publish(s->mod,e->entries.handle,17) && !ep_component33_resource_entries_commit(s->mod,e->entries.handle,&t.guard),"unretained transaction exposed");
    Check(ep_component33_resource_entries_retain(s->mod,e->entries.handle),"transaction retain");
    bool published=ep_component33_resource_entries_publish(s->mod,e->entries.handle,17)!=0;
    Check(published==(mode==0 || mode>=52),"publication result");
    Check(ep_component33_resource_entries_info(s->mod,e->entries.handle,&e->entries) && !e->entries.active,"publication info/early activation");
    Check(!ep_component33_resource_entries_publish(s->mod,e->entries.handle,17) && !ep_component33_resource_entries_cancel(s->mod,e->entries.handle),"publication retried/freed");
    if (!published) {
        unsigned attempted=mode<=25 ? mode : mode<=50 ? mode-25 : 25;
        Check(t.hooked==attempted && e->entries.published_attempts==attempted && e->entries.publication_state==EP_C33_PUBLISH_FAILED,"partial publication state");
        Check(!ep_component33_resource_entries_commit(s->mod,e->entries.handle,&t.guard) && !t.begins && !t.writes,"partial group committed");
        for (unsigned i=0;i<attempted;i++) if (*(uintptr_t*)RouteCode(t.group,i)->next_pointer) {PubCall call={&t,i,false};PubRun(&call);}
    } else {
        Check(t.hooked==25 && e->entries.publication_state==EP_C33_PUBLISH_READY,"complete publication count/state");
        if (mode!=78) {
            InterlockedExchangePointer((void* volatile*)RouteCode(t.group,0)->next_pointer,(void*)PubAlternate);PubCall current={&t,0,false};PubRun(&current);Check(t.alternate,"cached SDK next pointer");
        }
        for (auto& c:t.group->core) c.body=(uintptr_t)PubNew;
        if (mode==65) t.windows[0][0]^=1;
        if (mode==77) Check(ep_roster_owner_close(s->mod,s->owner)==0,"closed commit owner");
        if (mode==78) {auto* owner=OwnerAcquire(s->mod,s->owner);Check(owner!=nullptr,"commit revision access");owner->revision=UINT64_MAX;OwnerRelease(owner);}
        bool committed=false;
        if (mode==79 || mode==80) {
            PubCall call={&t,8,mode==79};HANDLE worker=nullptr,commit=nullptr;
            if (mode==80) {t.hold=true;worker=CreateThread(nullptr,0,PubCallThread,&call,0,nullptr);Check(worker && WaitForSingleObject(s->entered,5000)==WAIT_OBJECT_0,"old call entered");}
            commit=CreateThread(nullptr,0,PubCommitThread,&t,0,nullptr);Check(commit!=nullptr,"commit thread");
            if (mode==79) {Check(WaitForSingleObject(s->entered,5000)==WAIT_OBJECT_0,"commit validate entered");worker=CreateThread(nullptr,0,PubCallThread,&call,0,nullptr);Check(worker!=nullptr,"new caller thread");}
            ULONGLONG until=GetTickCount64()+5000;while (!Pending(s,false) && GetTickCount64()<until) Sleep(1);
            Check(Pending(s,false) && WaitForSingleObject(mode==79 ? worker : commit,0)==WAIT_TIMEOUT && !t.writes,"commit/call escaped exclusion");
            t.hold=false;SetEvent(s->proceed);Check(WaitForSingleObject(worker,5000)==WAIT_OBJECT_0 && WaitForSingleObject(commit,5000)==WAIT_OBJECT_0,"publication threads");
            DWORD status;Check(GetExitCodeThread(commit,&status) && status==0,"concurrent commit failed");CloseHandle(worker);CloseHandle(commit);committed=true;
        } else committed=ep_component33_resource_entries_commit(s->mod,e->entries.handle,&t.guard)!=0;
        bool safe_failure=mode==60 || mode==63 || mode==65 || mode==66 || (mode>=67 && mode<=71);
        bool unsafe=mode==61 || mode==62 || mode==64 || (mode>=72 && mode<=78);
        Check(committed==(!safe_failure && !unsafe),"commit result");
        Check(ep_component33_resource_entries_info(s->mod,e->entries.handle,&e->entries),"commit info");
        Check(e->entries.active==unsigned(committed || mode==75) && e->entries.commit_outcome==(unsafe ? EP_C33_COMMIT_UNSAFE : committed ? EP_C33_COMMIT_NEW : EP_C33_COMMIT_OLD),"commit latch/outcome");
        if (t.write_failed) {
            unsigned count=mode==67 || mode==70 || mode==71 ? 1 : mode==68 ? 2 : 3;
            Check(t.restored==count,"incomplete rollback attempts");for (unsigned i=0;i<count;i++) Check(t.restore[i]==count-1-i,"window rollback order");
        }
        if (unsafe) {
            Check(t.lease || mode==62,"unsafe failure resumed");
            Check(!ep_component33_resource_entries_commit(s->mod,e->entries.handle,&t.guard),"unsafe commit retried");
            if (mode!=77) {EpRosterOwnerInfo owner={};Check(ep_roster_owner_info(s->mod,s->owner,&owner)==0 && owner.fault,"unsafe owner not quarantined");}
        } else {
            if (safe_failure) {
                Check(e->entries.publication_state==EP_C33_PUBLISH_READY && !t.lease && !t.staged,"safe OLD failure state");
                if (mode==65) t.windows[0][0]^=1;
                for (unsigned i=0;i<3;i++) {auto w=GetWindow(t.group,i);Check(!memcmp(t.windows[i],w.expected,w.bytes),"rollback bytes");}
                t.mode=0;t.reads=t.writes=t.restored=0;
                Check(ep_component33_resource_entries_commit(s->mod,e->entries.handle,&t.guard),"safe commit retry");
            }
            if (mode==81 || mode==82) {
                void* component=OwnPage(0x200000000);void* global=OwnPage(0x183320000);void* invalid=OwnPage(0x183480000);
                W32((uint8_t*)component+8,9);W64((uint8_t*)global+0x67b8,0x200000000);W32((uint8_t*)invalid+0x3c34,0xffffffff);
                int fault=0;Check(!EpOwnerInvoke(PubNativeGuard,&t,&fault) && fault && e->rejected && !t.guard_reentry,"relocated native refusal reached wrong prefix");
                EpRosterOwnerInfo owner={};Check(ep_roster_owner_info(s->mod,s->owner,&owner)==0 && owner.fault,"native refusal quarantine");
                Check(VirtualFree(component,0,MEM_RELEASE) && VirtualFree(global,0,MEM_RELEASE) && VirtualFree(invalid,0,MEM_RELEASE),"native refusal pages");
            } else for (unsigned i=8;i<22;i++) {PubCall call={&t,i,true};PubRun(&call);}
            Check(!ep_component33_resource_entries_commit(s->mod,e->entries.handle,&t.guard),"active commit retried");
        }
    }
    Check(!routeGroup && !routeKinds && !coreGroup && !coreKinds && !updating && !callerGroup && !callerKinds && !ep_roster_owner_in_scope() && !t.group->switching,"publication TLS/owner leak");
    if (mode!=77) Check(ep_roster_owner_close(s->mod,s->owner)==0,"close publication owner");
    CloseHandle(s->entered);CloseHandle(s->proceed);Check(allocations==frees,"publication scratch leak");publishing=nullptr;entryTest=nullptr;nativeTest=nullptr;active=nullptr;return checks;
}
