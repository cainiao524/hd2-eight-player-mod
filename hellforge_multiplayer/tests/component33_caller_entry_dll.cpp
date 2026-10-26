/* Whole-call scopes and exact interior windows in owned Windows memory.
 * Test next pointers are synthetic SDK chain slots. No hooks/game access.
 * Window fixtures supply a registered ABI frame; they do not execute the
 * unrelated engine code or claim the original creation/owner path works. */
#include "component33_core_entry_dll.cpp"
struct CallerTest {
    CoreTest core;unsigned mode,index,calls,children,returned;bool inner,alternate;
    uintptr_t windows[3];uint32_t count;
};
static CallerTest* calling;
static int CallerRun(void*);
static uint64_t CallerArgument(CallerTest* t) { return t->index==0 ? 0x200000000-0x3ca0 : 0x123456789abcdef0; }
static void CallerCheck()
{
    auto* t=calling;auto* s=&t->core.entry.native.p.test;
    Check(ep_roster_owner_native_status(s->mod,s->owner)==0 && callerGroup==t->core.group && callerKinds,"caller outside owner");
}
static uint64_t CallerChild()
{
    ++calling->children;
    if (calling->mode==6) {Check(coreGroup==calling->core.group && !callerGroup,"core callback setup");CallerRun(calling);}
    else CallerCheck();return 42;
}
static void CallerUpdate(uint64_t component,float delta)
{ CallerCheck();Check(component==0x200000000 && delta==0.25f,"caller UPDATE arguments");++calling->children; }
static uint64_t CallerProbe(uint64_t a,uint64_t b,uint64_t c,uint64_t d)
{
    auto* t=calling;auto* s=&t->core.entry.native.p.test;++t->calls;CallerCheck();
    Check(a==CallerArgument(t) && b==0x5555666677778888 && c==0x9999aaaabbbbcccc && d==0xddddeeeeffff0000,"caller argument ABI");
    CONTEXT context={};RtlCaptureContext(&context);auto* tib=(NT_TIB*)NtCurrentTeb();bool found=false;
    for (unsigned i=0;i<100;i++) {
        Check(context.Rsp>=(uintptr_t)tib->StackLimit && context.Rsp+8<(uintptr_t)tib->StackBase,"caller unwind stack");
        DWORD64 base=0,frame=0;PVOID data=nullptr;auto* row=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
        if (row && base+row->BeginAddress==(uintptr_t)EpC33CoreEntry) found=true;
        if (row) RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,row,&context,&data,&frame,nullptr);
        else {memcpy(&context.Rip,(void*)(uintptr_t)context.Rsp,8);context.Rsp+=8;}
        if (found) break;
    }
    Check(found,"caller registered bridge absent");
    if (t->mode==3) {
        Check(((uint64_t(*)())t->core.entry.entries.core_entries[0].base)()==42,"caller core result");
        ((void(*)(uint64_t,float))t->core.entry.entries.update_entry.base)(0x200000000,0.25f);CallerCheck();
    }
    if (t->mode==4) CallerRun(t);
    if (t->mode==5 && !t->inner) {t->inner=true;unsigned old=t->index;t->index=1;CallerRun(t);t->index=old;t->inner=false;CallerCheck();}
    if (t->mode==13 || t->mode==23) RaiseException(0xe04333d1,0,0,nullptr);
    if (t->mode==22) {SetEvent(s->entered);Check(WaitForSingleObject(s->proceed,5000)==WAIT_OBJECT_0,"caller wait");}
    if (t->mode>=24) {
        auto* B=(uint8_t*)s->storage.storage_address;
        if (!t->index) {
            ((void(*)(uint64_t))t->windows[0])(a);
            Check(*(uint32_t*)0x20000000c==t->count && *(uint32_t*)0x200000010==t->count,"caller promotion window");
        } else {
            unsigned ordinal=t->index==1 ? 4 : t->count-1;
            ((void(*)(uint64_t,uint64_t))t->windows[t->index])(0x200000000,ordinal);
            for (unsigned j=0;j<44;j++) Check(B[0x50+80*ordinal+j]==0xff,"caller reset fifth/eighth row");
            if (t->mode==26) {
                W32((void*)(0x200001000+(t->count-1)*64+8),999);
                ((void(*)(uint64_t,uint64_t))t->windows[t->index])(0x200000000,t->count-1);
                Check(false,"failed second reset resumed");
            }
        }
        CallerCheck();
    }
    return 0x12349876fedcba09;
}
static uint64_t CallerAlternate(uint64_t a,uint64_t b,uint64_t c,uint64_t d)
{ calling->alternate=true;return CallerProbe(a,b,c,d); }
static double CallerFloat(uint64_t a,double b,float c,double d)
{
    CallerCheck();Check(a==CallerArgument(calling) && c==1.25f && d==-4.75,"caller float arguments");uint64_t bits;memcpy(&bits,&b,8);
    Check(bits==0x8000000000000000,"caller float payload");return b;
}
static void CallerReject(void* p,uint32_t kind,const EpC33ResourceProviderResult* r)
{
    auto* t=(CallerTest*)p;++t->core.entry.rejected;t->core.entry.failure=*r;
    Check((kind>EP_C33_CALLER_REJECT_BASE && kind<=EP_C33_CALLER_REJECT_BASE+3) || kind==EP_C33_CORE_REJECT_BASE+1,"caller reject kind");
    Check(r->call.status,"caller reject status");if (t->mode==23) RaiseException(0xe04333d2,EXCEPTION_NONCONTINUABLE,0,nullptr);
}
static int CallerRun(void* p)
{
    auto* t=(CallerTest*)p;auto fn=(uint64_t(*)(uint64_t,uint64_t,uint64_t,uint64_t))t->core.entry.entries.caller_entries[t->index].base;
    uint64_t a=CallerArgument(t)+(t->mode==11 ? 8 : 0);
    Check(fn(a,0x5555666677778888,0x9999aaaabbbbcccc,0xddddeeeeffff0000)==0x12349876fedcba09,"caller integer result");++t->returned;return 1;
}
static DWORD WINAPI CallerThread(void* p) {CallerRun(p);return 0;}
static int CallerFromCore(void* p) {auto* t=(CallerTest*)p;((void(*)())t->core.entry.entries.core_entries[0].base)();return 1;}
static int CallerCollect(void* p,const EpC33ResourceScopeView*,EpC33AcquireSnapshot*) {return CallerRun(p);}
static void SetNext(CallerTest* t,unsigned i,uintptr_t value)
{ InterlockedExchangePointer((void* volatile*)t->core.entry.entries.caller_entries[i].next_pointer,(void*)value); }
static void CodePage(void* page,uint32_t bytes)
{ DWORD old;Check(VirtualProtect(page,bytes,PAGE_EXECUTE_READ,&old) && FlushInstructionCache(GetCurrentProcess(),page,bytes),"caller fixture RX"); }
static PRUNTIME_FUNCTION WindowPage(CallerTest* t,unsigned index,void** page)
{
    auto* e=&t->core.entry.entries;uint64_t target=index ? e->reader_windows[index-1].target : e->owner_window.target;
    unsigned bytes=index ? e->reader_windows[index-1].bytes : e->owner_window.bytes;
    const uint8_t* replacement=index ? e->reader_windows[index-1].replacement : e->owner_window.replacement;
    uintptr_t base=target&~UINT64_C(0xffff);*page=OwnPage(base);auto* raw=(uint8_t*)*page;unsigned start=(unsigned)(target-base)-32;
    const uint8_t prefix[]={0x53,0x56,0x57,0x48,0x83,0xec,0x20,0x48,0x89,0xcb,0x48,0x89,0xce,0x8b,0xfa};
    memset(raw+start,0x90,32);memcpy(raw+start,prefix,sizeof(prefix));memcpy((void*)target,replacement,bytes);unsigned end=(unsigned)(target-base)+bytes;
    if (!index) {const uint8_t dense[]={0x89,0x46,0x0c};memcpy(raw+end,dense,sizeof(dense));end+=sizeof(dense);}
    const uint8_t tail[]={0x48,0x83,0xc4,0x20,0x5f,0x5e,0x5b,0xc3};memcpy(raw+end,tail,sizeof(tail));end+=sizeof(tail);
    const uint8_t unwind[]={1,7,4,0,7,0x32,3,0x70,2,0x60,1,0x30};memcpy(raw+0x1000,unwind,sizeof(unwind));
    auto* row=(PRUNTIME_FUNCTION)(raw+0x1020);*row={start,end,0x1000};CodePage(*page,65536);
    Check(RtlAddFunctionTable(row,1,base)!=0,"caller window registration");t->windows[index]=base+start;return row;
}
EXPORT unsigned c33_caller_entries_test(unsigned mode,const uint8_t* maps,uint32_t bytes,uint32_t table,uint32_t rows)
{
    Check(mode<27,"caller scenario");CallerTest t={};t.mode=mode;calling=&t;entryTest=&t.core.entry;
    NativeSetup(&t.core.entry.native,mode==14 ? 28 : 0);auto* e=&t.core.entry;auto* n=&e->native;auto* s=&n->p.test;
    n->api.read=EntryRead;n->api.read_code=EntryCode;n->api.hook_ex=Hook;
    EpC33ResourceEntryBindings b={s->storage.handle,s->owner,{0x191000000,0x191010000,0x191020000,0x191030000},CallerReject,&t};
    EpC33CallerEntryConfig config={};config.core.leave={{{{0x191040000,0x191050000},{0x191060000,0x191070000},0x191080000},0x191090000,0x1910a0000},0x1910b0000,0x1910c0000};
    for (unsigned i=0;i<14;i++) config.core.desired_entries[i]=0x192000000+i*0x10000;
    for (unsigned i=0;i<3;i++) config.desired_entries[i]=0x193000000+i*0x10000;
    if (mode==19) config.desired_entries[0]=config.core.desired_entries[13];
    if (mode==20) config.desired_entries[2]=config.desired_entries[1];
    int prepared=ep_component33_resource_entries_prepare_callers(&n->api,s->mod,&b,mode==18 ? nullptr : &config,&e->entries);
    Check(bool(prepared)==!(mode>=18 && mode<=20),"caller prepare outcome");
    Check(!e->sdk_bytes && !hooks,"caller prepare source/hook access");
    if (!prepared) {
        Check(!e->entries.handle,"caller failed cleanup");config.desired_entries[0]=0x193000000;config.desired_entries[2]=0x193020000;
        Check(ep_component33_resource_entries_prepare_callers(&n->api,s->mod,&b,&config,&e->entries),"caller retry");
    }
    t.core.group=Find(s->mod,e->entries.handle);Check(t.core.group!=nullptr,"caller group");
    const uint32_t rvas[]={0x576cf0,0xaddc10,0xb62210};
    for (unsigned i=0;i<3;i++) {Check(e->entries.caller_targets[i]==0x180000000+rvas[i],"caller target");ResetLeaf(e->entries.caller_entries[i]);}
    Check(!memcmp(&e->entries.owner_window,&s->storage.family.owner_window,sizeof(e->entries.owner_window)) &&
        !memcmp(e->entries.reader_windows,s->storage.family.reader_windows,sizeof(e->entries.reader_windows)),"caller foreign window family");
    if (mode>=17 && mode<=20) {
        Check(ep_component33_resource_entries_cancel(s->mod,e->entries.handle),"caller cancel");DWORD64 base=0;
        for (auto c:e->entries.caller_entries) Check(!RtlLookupFunctionEntry(c.base,&base,nullptr),"caller unwind survived cancel");
        for (auto c:e->entries.core_entries) Check(!RtlLookupFunctionEntry(c.base,&base,nullptr),"caller core survived cancel");
        Check(!RtlLookupFunctionEntry(e->entries.leave_body.base,&base,nullptr),"caller lifecycle survived cancel");
        Check(ep_roster_owner_close(s->mod,s->owner)==0,"caller cancel close");CloseHandle(s->entered);CloseHandle(s->proceed);return checks;
    }
    if (mode!=16) {
        Check(ep_component33_resource_entries_retain(s->mod,e->entries.handle),"caller retain");Check(ep_component33_resource_entries_info(s->mod,e->entries.handle,&e->entries),"caller info");
        for (auto c:e->entries.caller_entries) Check(c.pinned,"caller partial retention");for (auto c:e->entries.core_entries) Check(c.pinned,"caller core retention");
        Check(e->entries.leave_body.pinned && e->entries.reset_body.pinned && e->entries.code[0].pinned && !ep_component33_resource_entries_cancel(s->mod,e->entries.handle),"caller dependency retention");
    }
    void* pages[8]={};PRUNTIME_FUNCTION functions[4]={};pages[0]=OwnPage(0x183320000);W64((uint8_t*)pages[0]+0x67b8,0x200000000);
    for (unsigned i=0;i<3;i++) SetNext(&t,i,(uintptr_t)CallerProbe);
    if (mode==3 || mode==6) t.core.group->core[0].body=(uintptr_t)CallerChild;
    if (mode==3) t.core.group->info.update_body.base=(uintptr_t)CallerUpdate;
    if (mode==8) SetNext(&t,0,0);if (mode==9) SetNext(&t,0,e->entries.caller_entries[0].base);
    if (mode==10) W64((uint8_t*)pages[0]+0x67b8,0x200000008);
    if (mode==12) {DWORD old;Check(VirtualProtect(pages[0],65536,PAGE_NOACCESS,&old),"caller bad global");}
    if (mode==15) Check(ep_roster_owner_close(s->mod,s->owner)==0,"caller closed owner");
    if (mode>=24) {
        pages[1]=OwnPage(0x200000000);pages[2]=OwnPage(0x183480000);pages[3]=OwnPage(0x1a0000000);W32((uint8_t*)pages[2]+0x3c34,0xffffffff);
        uint8_t jump[]={0x48,0xb8,0,0,0,0,0,0,0,0,0xff,0xe0};uintptr_t guard=(uintptr_t)CoreGuard;memcpy(jump+2,&guard,8);memcpy(pages[3],jump,sizeof(jump));CodePage(pages[3],65536);
        Check(bytes==65536 && table+rows*12<bytes,"caller saved maps");pages[4]=OwnPage(0x181720000);memcpy(pages[4],maps,bytes);CodePage(pages[4],bytes);
        functions[0]=(PRUNTIME_FUNCTION)((uint8_t*)pages[4]+table);Check(RtlAddFunctionTable(functions[0],rows,(DWORD64)pages[4]),"caller map table");
        t.count=mode==24 ? 5 : 8;CoreLifecycle(&t.core,t.count);W32((void*)0x20000000c,0);W32((void*)0x200000010,0);
        memset((uint8_t*)s->storage.storage_address+0x40,0xab,EP_COMPONENT33_STORAGE_BYTES-0x40);
        for (unsigned i=0;i<3;i++) functions[i+1]=WindowPage(&t,i,&pages[i+5]);
    }
    bool success=mode<=3 || mode==5 || mode==21 || mode==22 || mode==24 || mode==25;int result=1,fault=0;
    if (mode==0) {
        for (unsigned i=0;i<3;i++) {
            t.index=i;CallerRun(&t);++t.core.revisions;SetNext(&t,i,(uintptr_t)CallerFloat);uint64_t sign=0x8000000000000000;double x;memcpy(&x,&sign,8);
            double value=((double(*)(uint64_t,double,float,double))e->entries.caller_entries[i].base)(CallerArgument(&t),x,1.25f,-4.75);uint64_t bits;memcpy(&bits,&value,8);Check(bits==sign,"caller float return");++t.core.revisions;
            SetNext(&t,i,(uintptr_t)StateNew);EpRosterCallFrame frame={};frame.rcx=CallerArgument(&t);EpRosterCallTarget(&frame,e->entries.caller_entries[i].base,0);++t.core.revisions;
            const uint64_t expected[]={0x9111000011110001,0xa222000022220002,0xb333000033330003,0xc444000044440004,0xd555000055550005,0xe666000066660006,0xf777000077770007};
            Check(!memcmp(&frame,expected,sizeof(expected)),"caller volatile return registers");
            for (unsigned j=0;j<6;j++) {uint64_t pair[2];memcpy(pair,frame.xmm[j],16);Check(pair[0]==expected[j] && pair[1]==expected[j],"caller SIMD returns");}
            if (i) {uint8_t output[256]={};CallNonvolatile(e->entries.caller_entries[i].base,output);++t.core.revisions;
                for (unsigned j=0;j<8;j++) Check(*(uint64_t*)(output+8+j*8)==4096+j,"caller nonvolatile GPR");
                for (unsigned j=0;j<20;j++) Check(*(uint64_t*)(output+80+j*8)==8192,"caller nonvolatile XMM");}
            SetNext(&t,i,(uintptr_t)CallerProbe);
        }
    } else if (mode>=24) {
        for (unsigned i=0;i<3;i++) {t.index=i;result=EpOwnerInvoke(CallerRun,&t,&fault);if (!result) break;++t.core.revisions;}
        if (mode==26) {
            auto* B=(uint8_t*)s->storage.storage_address;for (unsigned j=0;j<44;j++) Check(B[0x50+4*80+j]==0xff && B[0x50+7*80+j]==0xab,"caller partial effects lost");
        }
    } else if (mode==22) {
        HANDLE worker=CreateThread(nullptr,0,CallerThread,&t,0,nullptr);Check(worker && WaitForSingleObject(s->entered,5000)==WAIT_OBJECT_0,"caller thread entered");
        Observer observer={};observer.test=s;HANDLE reader=CreateThread(nullptr,0,Observe,&observer,0,nullptr);Check(reader!=nullptr,"caller reader");
        ULONGLONG until=GetTickCount64()+5000;while (!Pending(s,false) && GetTickCount64()<until) Sleep(1);
        Check(Pending(s,false) && WaitForSingleObject(reader,0)==WAIT_TIMEOUT,"caller reader escaped");SetEvent(s->proceed);
        Check(WaitForSingleObject(worker,5000)==WAIT_OBJECT_0 && WaitForSingleObject(reader,5000)==WAIT_OBJECT_0 && observer.info.revision==2,"caller reader result");CloseHandle(worker);CloseHandle(reader);++t.core.revisions;
    } else if (mode==7) {
        EpC33ResourceAcquireOps ops={&t,CallerCollect,CoreExecute};EpC33ResourceCallResult r={};result=ep_component33_resource_acquire_call(s->mod,s->storage.handle,s->owner,&ops,&r)==0;fault=!result;
    } else {
        if (mode==1 || mode==2) t.index=mode;
        result=EpOwnerInvoke(mode==6 ? CallerFromCore : CallerRun,&t,&fault);if (success) ++t.core.revisions;
        if (mode==21) {SetNext(&t,0,(uintptr_t)CallerAlternate);CallerRun(&t);++t.core.revisions;Check(t.alternate,"caller stale SDK next");}
    }
    Check(bool(result)==success && bool(fault)==!success && bool(e->rejected)==!success,"caller outcome");
    Check(!callerGroup && !callerKinds && !updating && !coreGroup && !coreKinds && !resourceCall && !ep_roster_owner_in_scope(),"caller TLS leak");
    Check(!e->sdk_bytes && !hooks,"caller source read/hook");
    if (mode==3) Check(t.children==2,"caller nested core/lifecycle missing");if (mode==5) Check(t.calls==2 && t.returned==2,"caller distinct nesting");
    if ((mode>=6 && mode<=12) || (mode>=14 && mode<=16)) Check(!t.calls,"caller preflight executed original");
    if (mode!=15) {
        EpRosterOwnerInfo info={};Check(ep_roster_owner_info(s->mod,s->owner,&info)==0,"caller owner info");
        Check(bool(info.fault)==(!success && mode!=16) && info.revision==(mode==14 ? UINT64_MAX : 1+t.core.revisions),"caller revision/quarantine");
        if (!success) {unsigned before=t.calls;int again=0;Check(!EpOwnerInvoke(CallerRun,&t,&again) && again && before==t.calls && !callerKinds && !callerGroup,"caller failed retry");}
        if (mode==16) Check(ep_component33_resource_entries_cancel(s->mod,e->entries.handle),"caller unretained cleanup");
        Check(ep_roster_owner_close(s->mod,s->owner)==0,"caller close");
    }
    for (auto f:functions) if (f) Check(RtlDeleteFunctionTable(f)!=0,"caller table cleanup");
    for (auto p:pages) if (p) Check(VirtualFree(p,0,MEM_RELEASE)!=0,"caller page cleanup");
    CloseHandle(s->entered);CloseHandle(s->proceed);Check(allocations==frees,"caller scratch leak");calling=nullptr;entryTest=nullptr;nativeTest=nullptr;active=nullptr;return checks;
}
