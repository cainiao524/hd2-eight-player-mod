/* Both actual RESET entry ABIs and the emitted per-entity body execute only
 * in pages owned by this test process. No game/client/install access. */
#include "component33_update_entry_dll.cpp"
struct ResetTest { EntryTest entry;unsigned mode,returned,index;uint64_t entity;void* pages[3]; };
static ResetTest* resetting;
static int ResetRun(void* p)
{
    auto* t=(ResetTest*)p;
    ((void(*)(uint64_t,uint64_t))t->entry.entries.reset_entries[t->index].base)(t->index ? UINT64_C(0xbad) : t->entity,t->index ? t->entity : UINT64_C(0xbad));
    ++t->returned;return 1;
}
static int ResetNested(void* p,const EpNativeRosterView*) { return ResetRun(p); }
static DWORD WINAPI ResetThread(void* p) { ResetRun(p);return 0; }
static void ResetReject(void* p,uint32_t kind,const EpC33ResourceProviderResult* r)
{
    auto* t=(ResetTest*)p;++t->entry.rejected;t->entry.failure=*r;
    Check((kind==EP_COMPONENT33_RESET || kind==EP_C33_UPDATE || kind==EP_C33_RESOURCE_DRAIN) && r->call.status,"RESET rejection");
    if (t->mode==23) RaiseException(0xe04333fe,EXCEPTION_NONCONTINUABLE,0,nullptr);
}
static int ResetCollect(void* p,const EpC33ResourceScopeView*,EpC33AcquireSnapshot*) { return ResetRun(p); }
static int ResetUnusedService(void*,const EpC33ResourceScopeView*,uint32_t,uint64_t) { Check(false,"RESET reentry continued resource effects");return 0; }
static void ResetDispose(uint64_t key,uint64_t table) { NativeDispose(key,table);ResetRun(resetting); }
static int ResetViaUpdate(void* p)
{
    auto* t=(ResetTest*)p;((void(*)(uint64_t,float))t->entry.entries.update_entry.base)(0x200000000,0.25f);return 1;
}
static int ResetHold(void* p,const EpNativeRosterView*)
{
    auto* s=(Test*)p;SetEvent(s->entered);Check(WaitForSingleObject(s->proceed,5000)==WAIT_OBJECT_0,"RESET hold timeout");return 1;
}
static DWORD WINAPI ResetHoldThread(void* p)
{
    auto* s=(Test*)p;Check(ep_roster_owner_call(s->mod,s->owner,0,ResetHold,s)==EP_OWNER_OK,"RESET holding owner");return 0;
}
static void ResetLeaf(const EpSessionCodeInfo& code)
{
    for (unsigned offset=0;offset<32;offset++) {
        DWORD64 base=0;auto* row=RtlLookupFunctionEntry(code.base+offset,&base,nullptr);
        Check(row && base==code.base && !row->BeginAddress && row->EndAddress==32,"RESET leaf registration");
        uint64_t stack[]={0x123456780,0,0,0};CONTEXT c={};c.ContextFlags=CONTEXT_FULL;c.Rip=code.base+offset;c.Rsp=(uintptr_t)stack;
        c.Rbx=101;c.Rbp=102;c.Rsi=103;c.Rdi=104;c.R12=105;c.R13=106;c.R14=107;c.R15=108;
        DWORD64 frame=0;PVOID data=nullptr;RtlVirtualUnwind(UNW_FLAG_NHANDLER,base,c.Rip,row,&c,&data,&frame,nullptr);
        Check(c.Rip==stack[0] && c.Rsp==(uintptr_t)(stack+1) && c.Rbx==101 && c.Rbp==102 && c.Rsi==103 && c.Rdi==104 && c.R12==105 && c.R13==106 && c.R14==107 && c.R15==108,"RESET leaf unwind");
    }
}
EXPORT int c33_resource_reset_idle(const EpC33ResourceBinding* b,void* p,uint32_t bytes) { return ep_c33_resource_reset_idle(b,p,bytes); }
EXPORT unsigned c33_resource_whole_reset_test(unsigned mode)
{
    Check(mode<24,"RESET scenario");ResetTest t={};t.mode=mode;t.index=mode%2;resetting=&t;entryTest=&t.entry;
    NativeSetup(&t.entry.native,mode==10 ? 28 : 0);auto* e=&t.entry;auto* n=&e->native;auto* s=&n->p.test;
    n->api.read=EntryRead;n->api.read_code=EntryCode;n->api.hook_ex=Hook;n->dispose_target=(uintptr_t)ResetDispose;
    EpC33ResourceEntryBindings b={s->storage.handle,s->owner,{0x191000000,0x191010000,0x191020000,0x191030000},ResetReject,&t};
    EpC33LifecycleEntryConfig config={{0x191040000,0x191050000},{0x191060000,0x191070000},0x191080000};
    if (mode==17) config.reset_entries[0]=config.update.desired_body;
    if (mode==18) config.reset_entries[1]=config.reset_entries[0];
    if (mode==19) config.reset_body=config.reset_entries[1];
    if (mode==20) config.reset_body=0x280000000;
    bool prepared=ep_component33_resource_entries_prepare_lifecycle(&n->api,s->mod,&b,mode==21 ? nullptr : &config,&e->entries)!=0;
    Check(prepared==!(mode>=17 && mode<=21),"RESET prepare outcome");
    Check(!n->p.reads && !n->p.codes && !n->calls && !hooks,"RESET prepare accessed source");
    if (!prepared) {
        Check(!e->entries.handle,"RESET incomplete cleanup");config.reset_entries[0]=0x191060000;config.reset_entries[1]=0x191070000;config.reset_body=0x191080000;
        Check(ep_component33_resource_entries_prepare_lifecycle(&n->api,s->mod,&b,&config,&e->entries),"RESET prepare retry");
    }
    Check(e->entries.reset_targets[0]==0x18051ade0 && e->entries.reset_targets[1]==0x180664210 && e->entries.reset_body.registered,"RESET targets");
    for (const auto& entry:e->entries.reset_entries) ResetLeaf(entry);
    if (mode>=16 && mode<=21) {
        auto old=e->entries;Check(ep_component33_resource_entries_cancel(s->mod,old.handle),"RESET cancel");
        DWORD64 base=0;for (const auto& entry:old.reset_entries) Check(!RtlLookupFunctionEntry(entry.base,&base,nullptr),"RESET entry survived cancel");
        Check(!RtlLookupFunctionEntry(old.reset_body.base,&base,nullptr) && !RtlLookupFunctionEntry(old.update_entry.base,&base,nullptr),"RESET dependencies survived cancel");
        Check(ep_roster_owner_close(s->mod,s->owner)==0,"RESET cancel close");CloseHandle(s->entered);CloseHandle(s->proceed);return checks;
    }
    Check(ep_component33_resource_entries_retain(s->mod,e->entries.handle),"RESET retain");
    Check(ep_component33_resource_entries_info(s->mod,e->entries.handle,&e->entries),"RESET info");
    for (const auto& code:e->entries.code) Check(code.pinned,"RESET resource lifetime");
    for (const auto& code:e->entries.reset_entries) Check(code.pinned,"RESET wrapper lifetime");
    Check(e->entries.reset_body.pinned && e->entries.update_body.pinned && e->entries.update_entry.pinned && !ep_component33_resource_entries_cancel(s->mod,e->entries.handle),"RESET atomic lifetime");
    t.pages[0]=OwnPage(0x200000000);t.pages[1]=OwnPage(0x183320000);t.pages[2]=OwnPage(0x183480000);
    auto* component=(uint8_t*)t.pages[0];auto* storage=(uint8_t*)(uintptr_t)s->storage.storage_address;
    W32(component+8,8);W32(component+12,8);W32(component+16,8);W64(component+0x58,0x200000014);W32(component+0x60,8);W32(component+0x68,1);
    W64((uint8_t*)t.pages[1]+0x67b8,mode==7 ? 0 : 0x200000000);W32((uint8_t*)t.pages[2]+0x3c34,0xffffffff);
    for (unsigned i=0;i<8;i++) {
        uint64_t entity=0x200001000+i*64;W32((void*)(uintptr_t)(entity+8),50+i);W32((void*)(uintptr_t)(entity+20),1);
        W64(storage+i*8,entity);W32(component+0x14+((50+i)&7)*8,50+i);W32(component+0x18+((50+i)&7)*8,i);
    }
    for (unsigned i=0x40;i<EP_COMPONENT33_STORAGE_BYTES;i++) storage[i]=(uint8_t)(i*13+7);
    unsigned ordinal=t.index ? 7 : 4;t.entity=0x200001000+ordinal*64;
    if (mode==6 || mode==23) W32((void*)(uintptr_t)(t.entity+8),999);
    if (mode==11) W32(component+0x18+((50+ordinal)&7)*8,8);
    if (mode==12) t.entity=0;
    auto* arena=(uint8_t*)(uintptr_t)s->resources.binding.address;
    if (mode==2 || mode==4 || mode==5) W64(arena+32,0);
    if (mode==3 || mode==4 || mode==5) W64(arena+48+512*8+101*16+8,0);
    if (mode==8) W64(arena,0);
    if (mode==15) { W32(component+8,0);W32(component+12,0);W32(component+16,0);memset(component+0x14,0,64); }
    if (mode==9) Check(ep_roster_owner_close(s->mod,s->owner)==0,"RESET closed owner");
    uint8_t before[48+512*24],old[EP_COMPONENT33_STORAGE_BYTES],header[EP_C33_SOURCE_BYTES];
    memcpy(before,arena,sizeof(before));memcpy(old,storage,sizeof(old));memcpy(header,component,sizeof(header));
    int result=0,fault=0;
    if (mode==13) { result=ep_roster_owner_call(s->mod,s->owner,0,ResetNested,&t)==0;fault=!result; }
    else if (mode==14) {
        EpC33ResourceServiceOps ops={&t,ResetCollect,ResetUnusedService};EpC33ResourceCallResult call={};
        result=ep_component33_resource_release_services_call(s->mod,s->storage.handle,s->owner,0,&ops,&call)==0;fault=!result;
    } else if (mode==15) result=EpOwnerInvoke(ResetViaUpdate,&t,&fault);
    else if (mode==22) {
        HANDLE holder=CreateThread(nullptr,0,ResetHoldThread,s,0,nullptr);Check(holder!=nullptr,"RESET holder thread");
        Check(WaitForSingleObject(s->entered,5000)==WAIT_OBJECT_0,"RESET holder entry");
        HANDLE reset=CreateThread(nullptr,0,ResetThread,&t,0,nullptr);Check(reset!=nullptr,"RESET worker thread");
        ULONGLONG until=GetTickCount64()+5000;while (!Pending(s,false) && GetTickCount64()<until) Sleep(1);
        Check(Pending(s,false) && WaitForSingleObject(reset,0)==WAIT_TIMEOUT && !memcmp(old,storage,sizeof(old)) && !memcmp(before,arena,sizeof(before)),"RESET escaped existing owner");
        SetEvent(s->proceed);Check(WaitForSingleObject(holder,5000)==WAIT_OBJECT_0 && WaitForSingleObject(reset,5000)==WAIT_OBJECT_0,"RESET wait completion");
        CloseHandle(holder);CloseHandle(reset);result=1;
    } else result=EpOwnerInvoke(ResetRun,&t,&fault);
    bool success=mode<=5 || mode==13 || mode==22;
    Check(bool(result)==success && bool(fault)==!success && t.returned==unsigned(success),"RESET return/failure");
    Check(bool(e->rejected)==!success && !updating && !resourceCall && !ep_roster_owner_in_scope(),"RESET refusal/TLS cleanup");
    if (success) memset(old+0x50+80*ordinal,0xff,44);
    Check(!memcmp(old,storage,sizeof(old)) && !memcmp(header,component,sizeof(header)),"RESET touched other player/array/header");
    if (mode==4 || mode==5) {
        memset(before,0,sizeof(before));W64(before,s->resources.binding.address+48+512*8);W32(before+8,512);W32(before+24,2);
    }
    Check(!memcmp(before,arena,sizeof(before)),"RESET lost live claims/queue or failed idle initialization");
    Check(e->sdk_bytes<=65536 && !hooks && !n->contexts && !n->resolvers && n->calls==(mode==15 ? 1u : 0u),"RESET unexpected engine access");
    if (mode!=15) Check(!n->p.reads && !n->p.codes,"RESET wrapper made SDK reads");
    if (mode!=9) {
        EpRosterOwnerInfo info={};Check(ep_roster_owner_info(s->mod,s->owner,&info)==0,"RESET owner info");
        Check(bool(info.fault)==!success && info.revision==(mode==10 ? UINT64_MAX : success ? 2u : 1u),"RESET quarantine/revision");
        if (!success) { unsigned calls=n->calls;int again=0;Check(!EpOwnerInvoke(ResetRun,&t,&again) && again && !updating && n->calls==calls,"RESET retried effects after failure"); }
        Check(ep_roster_owner_close(s->mod,s->owner)==0,"RESET owner close");
    }
    for (void* page:t.pages) Check(VirtualFree(page,0,MEM_RELEASE)!=0,"RESET fixture cleanup");
    CloseHandle(s->entered);CloseHandle(s->proceed);Check(allocations==frees,"RESET scratch leak");
    resetting=nullptr;entryTest=nullptr;nativeTest=nullptr;active=nullptr;return checks;
}
