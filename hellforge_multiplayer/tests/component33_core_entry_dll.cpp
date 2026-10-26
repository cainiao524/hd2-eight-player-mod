/* All memory and functions belong to this test process. SDK reads/hooks are
 * forbidden. ABI probes replace only private test context body pointers;
 * lifecycle cases execute the retained production bodies and saved hash code. */
#include "component33_leave_entry_dll.cpp"
extern "C" {
#include "roster_call_abi.h"
}
struct CoreTest { EntryTest entry;unsigned mode,index,calls,returned;bool inner;EntryGroup* group;uint64_t revisions; };
static CoreTest* coring;
static int CoreRun(void*);
static uint64_t CoreProbe(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f)
{
    auto* t=coring;auto* s=&t->entry.native.p.test;++t->calls;
    Check(a==0x1111222233334444 && b==0x5555666677778888 && c==0x9999aaaabbbbcccc && d==0xddddeeeeffff0000,"core register arguments");
    if (t->index==6) Check(e==0x123456789abcdef0 && f==0xfedcba9876543210,"core PROPERTY stack arguments");
    Check(ep_roster_owner_native_status(s->mod,s->owner)==0 && updating==t->group && coreGroup==t->group && coreKinds,"core body outside owner/TLS");
    CONTEXT context={};RtlCaptureContext(&context);auto* tib=(NT_TIB*)NtCurrentTeb();bool found=false;
    for (unsigned i=0;i<100;i++) {
        Check(context.Rsp>=(uintptr_t)tib->StackLimit && context.Rsp+8<(uintptr_t)tib->StackBase,"core unwind stack");
        DWORD64 base=0,frame=0;PVOID data=nullptr;auto* row=RtlLookupFunctionEntry(context.Rip,&base,nullptr);
        if (row && base+row->BeginAddress==(uintptr_t)EpC33CoreEntry) found=true;
        if (row) RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,context.Rip,row,&context,&data,&frame,nullptr);
        else {memcpy(&context.Rip,(void*)(uintptr_t)context.Rsp,8);context.Rsp+=8;}
        if (found) break;
    }
    Check(found,"core bridge absent from real unwind");
    if (t->mode==4 || t->mode==18) RaiseException(0xe04333f1,0,0,nullptr);
    if (t->mode==5) CoreRun(t);
    if (t->mode==6 && !t->inner) {t->inner=true;unsigned old=t->index;t->index=1;CoreRun(t);t->index=old;t->inner=false;}
    if (t->mode==7) ((void(*)(uint64_t))t->entry.entries.refresh_entry.base)(1);
    if (t->mode==3) {SetEvent(s->entered);Check(WaitForSingleObject(s->proceed,5000)==WAIT_OBJECT_0,"core probe wait");}
    return 0x12349876fedcba09;
}
static double CoreFloat(double a,float b,double c,float d)
{
    uint64_t bits;memcpy(&bits,&a,8);Check(bits==0x8000000000000000 && b==1.25f && c==3.5 && d==-4.75f,"core XMM arguments");return a;
}
static void CoreReject(void* p,uint32_t kind,const EpC33ResourceProviderResult* r)
{
    auto* t=(CoreTest*)p;++t->entry.rejected;t->entry.failure=*r;
    Check((kind>=EP_C33_CORE_REJECT_BASE+1 && kind<=EP_C33_CORE_REJECT_BASE+14) || kind==EP_C33_RESOURCE_REFRESH,"core reject kind");
    Check(r->call.status,"core reject status");
    if (t->mode==18) RaiseException(0xe04333f2,EXCEPTION_NONCONTINUABLE,0,nullptr);
}
static int CoreRun(void* p)
{
    auto* t=(CoreTest*)p;auto address=t->entry.entries.core_entries[t->index].base;
    auto fn=(uint64_t(*)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t))address;
    if (t->mode==16) fn(0,0,0,0,0,0);
    else if (t->mode==17) fn(0x200000000,0x200001100,0,0x200005000,0x200004000,0x200006000);
    else Check(fn(0x1111222233334444,0x5555666677778888,0x9999aaaabbbbcccc,0xddddeeeeffff0000,0x123456789abcdef0,0xfedcba9876543210)==0x12349876fedcba09,"core return value");
    ++t->returned;return 1;
}
static DWORD WINAPI CoreThread(void* p) {CoreRun(p);return 0;}
static int CoreCollect(void* p,const EpC33ResourceScopeView*,EpC33AcquireSnapshot*) {CoreRun(p);Check(false,"resource callback resumed");return 0;}
static int CoreExecute(void*,const EpC33ResourceScopeView*,const EpC33AcquireSnapshot*,const EpC33AcquireDemand*) {Check(false,"resource execute after refusal");return 0;}
static void CoreGuard() {RaiseException(0xe04333f3,EXCEPTION_NONCONTINUABLE,0,nullptr);}
static uint64_t CoreActual(CoreTest* t,unsigned kind,uint64_t a,uint64_t b=0,uint64_t c=0)
{
    auto fn=(uint64_t(*)(uint64_t,uint64_t,uint64_t))t->entry.entries.core_entries[kind-1].base;
    auto result=fn(a,b,c);++t->revisions;return result;
}
static void CoreLifecycle(CoreTest* t,unsigned count)
{
    auto* s=&t->entry.native.p.test;auto* component=(uint8_t*)0x200000000;auto* storage=(uint8_t*)s->storage.storage_address;
    memset(component,0,0x2b8);memset(storage,0,EP_COMPONENT33_STORAGE_BYTES);
    W64(component+0x58,0x200000014);W32(component+0x60,8);W32(component+0x68,1);
    for (unsigned i=0;i<count;i++) {
        uint64_t entity=0x200001000+i*64;W32((void*)(entity+8),50+i);W32((void*)(entity+16),10+i);W32((void*)(entity+20),0);
        if (i%2) CoreActual(t,EP_COMPONENT33_DIRECT_APPEND,0,entity);else CoreActual(t,EP_COMPONENT33_APPEND,entity);
        Check(*(uint32_t*)(component+8)==i+1 && *(uint64_t*)(storage+i*8)==entity,"core append fifth/eighth");
    }
    for (unsigned i=0;i<count;i++) W32((void*)(0x200001000+i*64+20),1);
    Check(CoreActual(t,EP_COMPONENT33_PROMOTE_PENDING,0x200000000)==count,"core promote count");
    Check(*(uint32_t*)(component+12)==count && *(uint32_t*)(component+16)==count,"core promote partition");
    uint64_t last=0x200001000+(count-1)*64;
    Check(CoreActual(t,EP_COMPONENT33_DIRECT_REMOVE,0,last)==10+count-1,"core remove return ABI");
    Check(*(uint32_t*)(component+8)==count-1 && *(uint32_t*)(component+12)==count-1,"core remove count");
    W32((void*)(last+20),0);CoreActual(t,EP_COMPONENT33_DIRECT_APPEND,0,last);W32((void*)(last+20),1);
    CoreActual(t,EP_COMPONENT33_PROMOTE_PENDING,0x200000000);
    for (unsigned i=0;i<count;i++) {
        Check(*(uint64_t*)(storage+i*8)==0x200001000+i*64,"core lifecycle identity");
        Check(*(uint32_t*)(component+0x18+((50+i)&7)*8)==i,"core lifecycle map ordinal");
    }
}
EXPORT unsigned c33_core_entries_test(unsigned mode,const uint8_t* maps,uint32_t bytes,uint32_t table,uint32_t rows)
{
    Check(mode<19,"core scenario");CoreTest t={};t.mode=mode;coring=&t;entryTest=&t.entry;
    NativeSetup(&t.entry.native,mode==9 ? 28 : 0);auto* e=&t.entry;auto* n=&e->native;auto* s=&n->p.test;
    n->api.read=EntryRead;n->api.read_code=EntryCode;n->api.hook_ex=Hook;
    EpC33ResourceEntryBindings b={s->storage.handle,s->owner,{0x191000000,0x191010000,0x191020000,0x191030000},CoreReject,&t};
    EpC33CoreEntryConfig config={{{{{0x191040000,0x191050000},{0x191060000,0x191070000},0x191080000},0x191090000,0x1910a0000},0x1910b0000,0x1910c0000},{}};
    for (unsigned i=0;i<14;i++) config.desired_entries[i]=0x192000000+i*0x10000;
    if (mode==13) config.desired_entries[0]=config.leave.desired_body;
    if (mode==14) config.desired_entries[13]=config.desired_entries[0];
    int prepared=ep_component33_resource_entries_prepare_core(&n->api,s->mod,&b,mode==15 ? nullptr : &config,&e->entries);
    Check(bool(prepared)==!(mode>=13 && mode<=15),"core prepare outcome");
    Check(!e->sdk_bytes && !n->calls && !hooks,"core prepare source/hook access");
    if (!prepared) {
        Check(!e->entries.handle,"core incomplete cleanup");config.desired_entries[0]=0x192000000;config.desired_entries[13]=0x1920d0000;
        Check(ep_component33_resource_entries_prepare_core(&n->api,s->mod,&b,&config,&e->entries),"core prepare retry");
    }
    t.group=Find(s->mod,e->entries.handle);Check(t.group!=nullptr,"core group missing");
    const uint32_t rvas[]={0x665fe0,0x51abf0,0x51ac70,0x51ad30,0x666a90,0x666dd0,0x6661a0,0x664430,0x666710,0x6667d0,0x666a00,0x6642c0,0x665ec0,0x666850};
    for (unsigned i=0;i<14;i++) {
        Check(e->entries.core_targets[i]==s->roster.game+rvas[i] && t.group->core[i].body==s->storage.family.code[i].base,"core family binding");
        ResetLeaf(e->entries.core_entries[i]);
    }
    if (mode>=12 && mode<=15) {
        Check(ep_component33_resource_entries_cancel(s->mod,e->entries.handle),"core cancel");
        for (auto c:e->entries.core_entries) {DWORD64 base=0;Check(!RtlLookupFunctionEntry(c.base,&base,nullptr),"core cancel unwind survived");}
        DWORD64 base=0;Check(!RtlLookupFunctionEntry(e->entries.leave_body.base,&base,nullptr) && !RtlLookupFunctionEntry(e->entries.refresh_body.base,&base,nullptr),"core cancel lifecycle survived");
        Check(ep_roster_owner_close(s->mod,s->owner)==0,"core cancel owner");CloseHandle(s->entered);CloseHandle(s->proceed);return checks;
    }
    if (mode!=11) {
        Check(ep_component33_resource_entries_retain(s->mod,e->entries.handle),"core retain");
        Check(ep_component33_resource_entries_info(s->mod,e->entries.handle,&e->entries),"core info");
        for (auto code:e->entries.core_entries) Check(code.pinned,"core retained lifetime");
        Check(e->entries.leave_body.pinned && e->entries.refresh_body.pinned && e->entries.reset_body.pinned && e->entries.code[0].pinned,"core lifetime dependencies");
    }
    void* pages[5]={};PRUNTIME_FUNCTION functions=nullptr;
    if (mode==1 || mode==2 || mode==16 || mode==17) {
        pages[0]=OwnPage(0x200000000);pages[1]=OwnPage(0x183320000);pages[2]=OwnPage(0x183480000);pages[3]=OwnPage(0x1a0000000);
        W64((uint8_t*)pages[1]+0x67b8,0x200000000);W32((uint8_t*)pages[2]+0x3c34,0xffffffff);
        uint8_t jump[]={0x48,0xb8,0,0,0,0,0,0,0,0,0xff,0xe0};uintptr_t target=(uintptr_t)CoreGuard;memcpy(jump+2,&target,8);memcpy(pages[3],jump,sizeof(jump));DWORD old;
        Check(VirtualProtect(pages[3],0x10000,PAGE_EXECUTE_READ,&old) && FlushInstructionCache(GetCurrentProcess(),pages[3],0x10000),"core guard RX");
        Check(bytes==0x10000 && table+rows*12<bytes,"saved map fixture shape");pages[4]=OwnPage(0x181720000);memcpy(pages[4],maps,bytes);functions=(PRUNTIME_FUNCTION)((uint8_t*)pages[4]+table);
        Check(VirtualProtect(pages[4],bytes,PAGE_EXECUTE_READ,&old) && FlushInstructionCache(GetCurrentProcess(),pages[4],bytes) && RtlAddFunctionTable(functions,rows,(DWORD64)pages[4]),"saved map registration");
        CoreLifecycle(&t,mode==2 ? 8 : 5);
        if (mode==16) t.index=13;
        if (mode==17) {t.index=6;W32((void*)0x200004000,125);}
    } else for (auto& context:t.group->core) context.body=(uintptr_t)CoreProbe;
    int result=1,fault=0;bool success=mode<=3 || mode==6;
    if (mode==0) {
        for (unsigned i=0;i<14;i++) {
            t.index=i;CoreRun(&t);++t.revisions;
            t.group->core[i].body=(uintptr_t)CoreFloat;uint64_t sign=0x8000000000000000;double a;memcpy(&a,&sign,8);
            double value=((double(*)(double,float,double,float))e->entries.core_entries[i].base)(a,1.25f,3.5,-4.75f);uint64_t bits;memcpy(&bits,&value,8);
            Check(bits==sign,"core floating return bits");++t.revisions;
            t.group->core[i].body=(uintptr_t)StateNew;EpRosterCallFrame frame={};uint64_t stack[7]={};frame.entry_stack=(uintptr_t)stack;
            EpRosterCallTarget(&frame,e->entries.core_entries[i].base,i==6 ? 2 : 0);++t.revisions;
            const uint64_t expected[]={0x9111000011110001,0xa222000022220002,0xb333000033330003,0xc444000044440004,0xd555000055550005,0xe666000066660006,0xf777000077770007};
            Check(!memcmp(&frame,expected,sizeof(expected)),"core volatile return registers");
            for (unsigned x=0;x<6;x++) {uint64_t pair[2];memcpy(pair,frame.xmm[x],16);Check(pair[0]==expected[x] && pair[1]==expected[x],"core XMM return registers");}
            uint8_t output[256]={};CallNonvolatile(e->entries.core_entries[i].base,output);++t.revisions;
            for (unsigned x=0;x<8;x++) Check(*(uint64_t*)(output+8+x*8)==4096+x,"core nonvolatile GPR");
            for (unsigned x=0;x<20;x++) Check(*(uint64_t*)(output+80+x*8)==8192,"core nonvolatile XMM");
            t.group->core[i].body=(uintptr_t)CoreProbe;
        }
    } else if (mode==1 || mode==2) {}
    else if (mode==3) {
        HANDLE worker=CreateThread(nullptr,0,CoreThread,&t,0,nullptr);Check(worker && WaitForSingleObject(s->entered,5000)==WAIT_OBJECT_0,"core worker entered");Observer observer={};observer.test=s;
        HANDLE reader=CreateThread(nullptr,0,Observe,&observer,0,nullptr);Check(reader!=nullptr,"core reader");
        ULONGLONG until=GetTickCount64()+5000;while (!Pending(s,false) && GetTickCount64()<until) Sleep(1);
        Check(Pending(s,false) && WaitForSingleObject(reader,0)==WAIT_TIMEOUT,"core reader escaped");SetEvent(s->proceed);
        Check(WaitForSingleObject(worker,5000)==WAIT_OBJECT_0 && WaitForSingleObject(reader,5000)==WAIT_OBJECT_0 && observer.info.revision==2,"core reader result");CloseHandle(worker);CloseHandle(reader);++t.revisions;
    } else if (mode==8) {
        EpC33ResourceAcquireOps ops={&t,CoreCollect,CoreExecute};EpC33ResourceCallResult r={};result=ep_component33_resource_acquire_call(s->mod,s->storage.handle,s->owner,&ops,&r)==EP_C33_CALL_OK;
        Check(!result && !t.calls && r.owner_result!=EP_OWNER_OK,"core resource callback refused");
    } else {
        if (mode==10) Check(ep_roster_owner_close(s->mod,s->owner)==0,"core closed owner");
        result=EpOwnerInvoke(CoreRun,&t,&fault);if (success) ++t.revisions;
        Check(bool(fault)==!success,"core fault boundary");
    }
    Check(bool(result)==success && bool(e->rejected)==!success,"core outcome");
    Check(!updating && !coreGroup && !coreKinds && !resourceCall && !ep_roster_owner_in_scope(),"core TLS leak");
    Check(!e->sdk_bytes && !hooks,"core source read/hook");
    if (mode==6) Check(t.calls==2 && t.returned==2,"different core nesting lost");
    if (mode==9 || mode==10 || mode==11) Check(!t.calls,"unavailable core executed");
    if (mode!=10) {
        EpRosterOwnerInfo info={};Check(ep_roster_owner_info(s->mod,s->owner,&info)==0,"core owner info");
        Check(bool(info.fault)==(!success && mode!=11) && info.revision==(mode==9 ? UINT64_MAX : 1+t.revisions),"core revision/quarantine");
        if (!success) {unsigned calls=t.calls;int again=0;Check(!EpOwnerInvoke(CoreRun,&t,&again) && again && calls==t.calls && !coreKinds && !updating,"core fault retry");}
        if (mode==11) Check(ep_component33_resource_entries_cancel(s->mod,e->entries.handle),"core unretained cleanup");
        Check(ep_roster_owner_close(s->mod,s->owner)==0,"core owner close");
    }
    if (functions) Check(RtlDeleteFunctionTable(functions)!=0,"saved map table cleanup");
    for (auto page:pages) if (page) Check(VirtualFree(page,0,MEM_RELEASE)!=0,"core page cleanup");
    CloseHandle(s->entered);CloseHandle(s->proceed);Check(allocations==frees,"core scratch leak");
    coring=nullptr;entryTest=nullptr;nativeTest=nullptr;active=nullptr;return checks;
}
