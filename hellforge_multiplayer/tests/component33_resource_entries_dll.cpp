#include "component33_resource_native_dll.cpp"
#include "../mod/src/ep_component33_resource_entries.h"
struct EntryTest {
    NativeTest native;EpC33ResourceEntriesInfo entries;unsigned mode,index,rejected,sdk_bytes;
    uint64_t component,value,flag;bool returned;EpC33ResourceProviderResult failure;
};
static EntryTest* entryTest;
static int EntryRead(uintptr_t address,void* out,size_t bytes)
{ entryTest->sdk_bytes+=(unsigned)bytes;return NativeSdkRead(address,out,bytes); }
static int EntryCode(uintptr_t address,void* out,size_t bytes)
{
    entryTest->sdk_bytes+=(unsigned)bytes;
    if (address==0x180665985 && bytes==sizeof(ep_c33_native_defer_source)) {
        auto* t=entryTest;++t->native.p.codes;
        Check(ep_component33_resource_scope_ready(t->native.p.test.mod,t->native.p.test.owner),"DEFER source outside scope");
        memcpy(out,ep_c33_native_defer_source,bytes);if (t->mode==10) ((uint8_t*)out)[0]^=1;return 0;
    }
    return NativeCode(address,out,bytes);
}
static void Rejected(void* context,uint32_t kind,const EpC33ResourceProviderResult* result)
{
    auto* t=(EntryTest*)context;++t->rejected;t->failure=*result;
    Check(kind==EP_C33_ACQUIRE+t->index && result->call.status!=0,"entry refusal diagnostics");
    if (t->mode==11) RaiseException(0xe0433302,EXCEPTION_NONCONTINUABLE,0,nullptr);
    // Deliberately return: production dispatch must raise its own abort.
}
static int InvokeEntry(void* context)
{
    auto* t=(EntryTest*)context;
    ((void (*)(uint64_t,uint64_t,uint64_t))t->entries.code[t->index].base)(t->component,t->value,t->flag);
    t->returned=true;return 1;
}
static int NestedEntry(void* context,const EpNativeRosterView*) { return InvokeEntry(context); }
static DWORD WINAPI EntryThread(void* context) { InvokeEntry(context);return 0; }
static void UnwindEntries(const EpC33ResourceEntriesInfo& info)
{
    for (const auto& code:info.code) for (unsigned offset=0;offset<32;offset++) {
        DWORD64 base=0;auto* fn=RtlLookupFunctionEntry(code.base+offset,&base,nullptr);
        Check(fn && base==code.base && fn->BeginAddress==0 && fn->EndAddress==32,"registered entry unwind");
        uint64_t stack[]={0x123456780,0,0,0};CONTEXT c={};c.ContextFlags=CONTEXT_FULL;c.Rip=code.base+offset;c.Rsp=(uintptr_t)stack;
        c.Rbx=101;c.Rbp=102;c.Rsi=103;c.Rdi=104;c.R12=105;c.R13=106;c.R14=107;c.R15=108;
        PVOID handler=nullptr;DWORD64 establisher=0;
        RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,c.Rip,fn,&c,&handler,&establisher,nullptr);
        Check(c.Rip==stack[0] && c.Rsp==(uintptr_t)(stack+1),"entry unwind stack");
        Check(c.Rbx==101 && c.Rbp==102 && c.Rsi==103 && c.Rdi==104 && c.R12==105 && c.R13==106 && c.R14==107 && c.R15==108,"entry unwind nonvolatiles");
    }
}
EXPORT unsigned c33_resource_entries_test(unsigned mode)
{
    Check(mode<29,"entry mode");EntryTest t={};t.mode=mode;entryTest=&t;
    unsigned native_mode=mode==7 || mode==11 || mode==17 ? 7 : mode==8 ? 14 : mode==9 ? 13 : mode==15 ? 21 : mode==18 ? 24 : mode==19 ? 28 : mode==27 ? 20 : mode==28 ? 16 : 0;
    NativeSetup(&t.native,native_mode);auto* n=&t.native;auto* s=&n->p.test;n->api.read=EntryRead;n->api.read_code=EntryCode;n->api.hook_ex=Hook;
    EpC33ResourceEntryBindings b={s->storage.handle,s->owner,{0x191000000,0x191010000,0x191020000,0x191030000},Rejected,&t};
    if (mode==23) b.storage=UINT64_MAX;
    if (mode==24) b.reject=nullptr;
    if (mode==25) n->api.size=offsetof(HfApi,read_code);
    if (mode==26) n->api.build_id=WrongBuild;
    if (mode==22) b.desired_code[1]=b.desired_code[0];
    bool prepared=ep_component33_resource_entries_prepare(&n->api,s->mod,&b,&t.entries)!=0;
    Check(prepared==(mode<22 || mode>26),"entry preparation result");
    Check(!n->p.reads && !n->p.codes && !n->contexts && !n->resolvers && !n->calls && !hooks,"prepare accessed source or published");
    if (!prepared) {
        Check(!t.entries.handle,"failed prepare retained partial entry set");
        if (mode==22) {
            b.desired_code[1]=0x191010000;Check(ep_component33_resource_entries_prepare(&n->api,s->mod,&b,&t.entries),"partial allocation cleanup/retry");
            Check(ep_component33_resource_entries_cancel(s->mod,t.entries.handle),"cancel retried entry set");
        }
        Check(ep_roster_owner_close(s->mod,s->owner)==0,"close preparation owner");CloseHandle(s->entered);CloseHandle(s->proceed);return checks;
    }
    Check(t.entries.state==EP_C33_ENTRIES_PREPARED,"prepared state");
    const uint32_t rvas[]={0x6656c0,0x665940,0x6659e0,0};
    for (unsigned i=0;i<EP_C33_RESOURCE_ENTRY_COUNT;i++) {
        Check(t.entries.targets[i]==(rvas[i] ? s->roster.game+rvas[i] : 0) && t.entries.code[i].registered && t.entries.code[i].state==EP_CODE_READY,"entry target/state");
        MEMORY_BASIC_INFORMATION memory={};Check(VirtualQuery((void*)t.entries.code[i].base,&memory,sizeof(memory)) && memory.Protect==PAGE_EXECUTE_READ,"entry not RX");
    }
    UnwindEntries(t.entries);
    EpC33ResourceEntriesInfo copy={};Check(ep_component33_resource_entries_info(s->mod,t.entries.handle,&copy) && !memcmp(&copy,&t.entries,sizeof(copy)),"entry info");
    if (mode==13) {
        auto old=t.entries;Check(ep_component33_resource_entries_cancel(s->mod,t.entries.handle),"prepared cancellation");
        Check(!ep_component33_resource_entries_info(s->mod,old.handle,&copy),"cancelled entry remained visible");
        for (const auto& c:old.code) { DWORD64 base=0;Check(!RtlLookupFunctionEntry(c.base,&base,nullptr),"cancelled unwind remained registered"); }
        Check(ep_roster_owner_close(s->mod,s->owner)==0,"close cancelled owner");CloseHandle(s->entered);CloseHandle(s->proceed);return checks;
    }
    if (mode==21) Check(!ep_component33_resource_entries_prepare(&n->api,s->mod,&b,&copy) && !copy.handle,"duplicate entry preparation");
    Check(ep_component33_resource_entries_retain(s->mod,t.entries.handle),"entry retention");
    Check(ep_component33_resource_entries_info(s->mod,t.entries.handle,&t.entries) && t.entries.state==EP_C33_ENTRIES_RETAINED,"retained state");
    for (const auto& c:t.entries.code) Check(c.pinned && c.state==EP_CODE_RETAINED,"partial entry retention");
    Check(!ep_component33_resource_entries_cancel(s->mod,t.entries.handle) && !ep_component33_resource_entries_retain(s->mod,t.entries.handle),"retained entry cancelled or retained twice");
    t.component=n->p.global;t.value=0x260000400;
    if (mode==1 || mode==10 || mode==20) t.index=1;
    if (mode==2 || mode==3 || mode==5) { t.index=2;t.value=(UINT64_C(0x12345678)<<32)|(mode==5 ? 8 : 4);t.flag=mode==3 ? 0x80 : 0x100; }
    if (mode==4) t.component+=8;
    if (mode==6) t.value=0x260009000;
    if (mode==20) n->service_table=n->load_target=n->dispose_target=0;
    if (mode==14) { n->api.read=nullptr;n->api.read_code=nullptr;n->api.size=0; }
    if (mode==12) Check(ep_roster_owner_close(s->mod,s->owner)==EP_OWNER_OK,"close before entry");
    uint8_t before[48+512*24];memcpy(before,(void*)(uintptr_t)s->resources.binding.address,sizeof(before));
    int fault=0,result;
    if (mode==16 || mode==17) {
        auto rc=ep_roster_owner_call(s->mod,s->owner,0,NestedEntry,&t);result=rc==EP_OWNER_OK;fault=!result;
    } else if (mode==18) {
        HANDLE worker=CreateThread(nullptr,0,EntryThread,&t,0,nullptr);Check(worker!=nullptr,"entry thread");
        Check(WaitForSingleObject(s->entered,5000)==WAIT_OBJECT_0,"entry service not reached");Observer observer={};observer.test=s;
        HANDLE reader=CreateThread(nullptr,0,Observe,&observer,0,nullptr);Check(reader!=nullptr,"entry reader");
        ULONGLONG until=GetTickCount64()+5000;while (!Pending(s,false) && GetTickCount64()<until) Sleep(1);
        Check(Pending(s,false) && WaitForSingleObject(reader,0)==WAIT_TIMEOUT,"reader escaped entry scope");
        SetEvent(s->proceed);Check(WaitForSingleObject(worker,5000)==WAIT_OBJECT_0 && WaitForSingleObject(reader,5000)==WAIT_OBJECT_0,"entry threads did not finish");
        Check(observer.status==EP_OWNER_OK && observer.info.revision==2,"entry reader revision");CloseHandle(worker);CloseHandle(reader);result=1;
    } else result=EpOwnerInvoke(InvokeEntry,&t,&fault);
    bool success=mode<=3 || mode==6 || mode==14 || mode==16 || mode==18 || mode==20 || mode==21;
    Check(bool(result)==success && bool(fault)==!success && t.returned==success && t.rejected==unsigned(!success),"entry failure returned to caller");
    unsigned effects=mode==0 || mode==14 || mode==16 || mode==18 || mode==21 ? 3 : mode==2 ? 1 : mode==8 || mode==27 ? 2 : 0;
    Check(n->calls==effects && t.sdk_bytes<=65536,"entry effects/budget");
    if (mode==1 || mode==3 || mode==20) {
        uint64_t queue[3];memcpy(queue,(void*)(uintptr_t)(s->resources.binding.address+32),8);memcpy(queue+1,(void*)(uintptr_t)(s->resources.binding.address+48),16);
        Check(queue[0]==2 && queue[1]==102 && queue[2]==101,"DEFER/flag queue result");
        Check(n->contexts==(mode==3 ? 0u : 4u) && n->resolvers==n->contexts,"DEFER used ordinal or thresholds");
    }
    if (!success && mode!=8 && mode!=27) Check(!memcmp(before,(void*)(uintptr_t)s->resources.binding.address,sizeof(before)),"entry preeffect refusal changed arena");
    if (mode==4 || mode==5 || mode==12) Check(!n->p.reads && !n->p.codes && !n->contexts,"bad entry binding accessed SDK");
    if (mode==15) Check(t.failure.source_status==EP_C33_PROVIDER_BUDGET && t.failure.read_bytes>65520 && t.failure.read_bytes<=65536,"entry budget refusal");
    if (mode==28) Check(n->contexts==1 && n->resolvers==0,"entry continued after swallowed reentry");
    if (mode!=12) {
        EpRosterOwnerInfo owner={};Check(ep_roster_owner_info(s->mod,s->owner,&owner)==EP_OWNER_OK,"entry owner info");
        Check(bool(owner.fault)==!success && owner.revision==(mode==19 ? UINT64_MAX : success && mode!=6 ? 2u : 1u),"entry quarantine/revision");
        if (!success) {
            unsigned calls=n->calls,reads=n->p.reads,codes=n->p.codes;int retry_fault=0;
            Check(EpOwnerInvoke(InvokeEntry,&t,&retry_fault)==0 && retry_fault && n->calls==calls && n->p.reads==reads && n->p.codes==codes,"entry retried faulted owner");
        }
        Check(ep_roster_owner_close(s->mod,s->owner)==EP_OWNER_OK,"entry owner close");
    }
    Check(!hooks && !resourceCall && !ep_roster_owner_in_scope() && allocations==frees,"entry hook/scope/lifetime leak");
    CloseHandle(s->entered);CloseHandle(s->proceed);active=nullptr;nativeTest=nullptr;entryTest=nullptr;return checks;
}
