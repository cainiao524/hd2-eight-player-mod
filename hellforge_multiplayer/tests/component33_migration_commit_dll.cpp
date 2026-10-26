/* SDK callbacks map an explicit list of test-owned regions only. No engine,
 * process inspection, sampling, real SDK hook or installation is performed. */
#include <windows.h>
static bool migration_alloc_fail;
static unsigned migration_allocations,migration_frees;
static void* MigrationAlloc(void* p,SIZE_T n,DWORD type,DWORD protection)
{void* result=migration_alloc_fail ? nullptr : VirtualAlloc(p,n,type,protection);migration_allocations+=result!=nullptr;return result;}
static BOOL MigrationFree(void* p,SIZE_T n,DWORD type)
{BOOL result=VirtualFree(p,n,type);migration_frees+=result!=FALSE;return result;}
#define VirtualAlloc MigrationAlloc
#define VirtualFree MigrationFree
#include "component33_publication_dll.cpp"
#undef VirtualAlloc
#undef VirtualFree
struct MigrationTest {
    PublicationTest pub;unsigned mode,data_calls,global_calls,requested;bool checked_stage;
    EpC33Snapshot source;EpC33ResourceSnapshot resources;uint8_t descriptor[28];
    uint8_t before_b[EP_COMPONENT33_STORAGE_BYTES],before_arena[48+24*512];
    EpC33Migration expected_b;alignas(8) uint8_t expected_arena[48+24*512];
};
static MigrationTest* migrating;
static int MigrationRead(uintptr_t address,void* out,size_t bytes)
{
    auto* t=migrating;auto* s=&t->pub.entry.native.p.test;++t->data_calls;t->requested+=(unsigned)bytes;
    Check(t->pub.lease && t->pub.group->switching && !t->pub.group->active && ep_roster_owner_native_status(s->mod,s->owner)==0,"migration read outside OLD exclusion");
    if ((t->mode==15 && t->data_calls==1) || (t->mode>=100 && t->data_calls==t->mode-99)) return 1;
    if (t->mode==16 && t->data_calls==5) RaiseException(0xe04333c1,0,0,nullptr);
    if (t->mode==27 && t->checked_stage) RaiseException(0xe04333c2,0,0,nullptr);
    if ((t->mode==29 && t->data_calls==5) || (t->mode==30 && t->checked_stage))
        Check(ep_roster_owner_call(s->mod,s->owner,1,NestedFailure,nullptr)==EP_OWNER_CALLBACK_FAILED,"nested SDK failure");
    if (address==0x1833267b8 && ++t->global_calls==2 && t->mode==17) t->source.component[0x98]^=1;
    Region regions[]={{0x1833267b8,8,&t->source.global_component},{0x183483c34,4,&t->source.invalid_entity_id},
        {0x200000000,EP_C33_SOURCE_BYTES,t->source.component},{0x183798180,28,t->descriptor},
        {0x18348ba88,8,&t->resources.queued},{0x280000000,sizeof(t->resources.entries),t->resources.entries},
        {0x183797550,sizeof(t->resources.queue),t->resources.queue}};
    for (const auto& r:regions) if (address>=r.address && address-r.address<=r.bytes && bytes<=r.bytes-(address-r.address)) {
        memcpy(out,(const uint8_t*)r.data+address-r.address,bytes);return 0;
    }
    for (const auto& e:t->source.entities) if (bytes==4 && (address==e.address+8 || address==e.address+20)) {
        memcpy(out,address==e.address+8 ? &e.id : &e.flags,4);return 0;
    }
    Check(false,"unlisted migration read");return 1;
}
static int MigrationCode(uintptr_t address,void* out,size_t bytes)
{migrating->requested+=(unsigned)bytes;return PubRead(address,out,bytes);}
static void CheckNewData(MigrationTest* t)
{
    auto* s=&t->pub.entry.native.p.test;
    Check(!memcmp((void*)(uintptr_t)s->storage.storage_address,t->expected_b.data,sizeof(t->expected_b.data)),"fresh component arrays not installed");
    Check(!memcmp((void*)(uintptr_t)s->resources.binding.address,t->expected_arena,sizeof(t->expected_arena)),"fresh resource ownership not migrated");
}
static int MigrationValidate(void* p,void* lease)
{
    auto* t=migrating;CheckNewData(t);t->checked_stage=true;int ok=PubValidate(p,lease);
    auto* s=&t->pub.entry.native.p.test;
    if (t->mode==18) t->source.component[0x99]^=1;
    if (t->mode==19) return 0;
    if (t->mode==20) RaiseException(0xe04333c3,0,0,nullptr);
    if (t->mode==21) ((uint8_t*)(uintptr_t)s->storage.storage_address)[0]^=1;
    if (t->mode==22) ((uint8_t*)(uintptr_t)s->resources.binding.address)[0]^=1;
    if (t->mode==25) {DWORD old;Check(VirtualProtect((void*)(uintptr_t)s->storage.storage_address,4096,PAGE_READONLY,&old),"protect rollback target");return 0;}
    return ok;
}
static void MigrationEnd(void* p,void* lease,uint32_t outcome)
{
    auto* t=migrating;auto* s=&t->pub.entry.native.p.test;
    if (outcome==EP_C33_COMMIT_NEW) CheckNewData(t);
    else {
        if (t->mode!=25) Check(!memcmp((void*)(uintptr_t)s->storage.storage_address,t->before_b,sizeof(t->before_b)),"component restore must precede end");
        Check(!memcmp((void*)(uintptr_t)s->resources.binding.address,t->before_arena,sizeof(t->before_arena)),"arena restore must precede end");
    }
    PubEnd(p,lease,outcome);
}
static void MigrationSourceSetup(MigrationTest* t)
{
    auto* s=&t->source;s->component_address=s->global_component=0x200000000;s->invalid_entity_id=UINT32_MAX;
    s->entity_count=t->mode==1 ? 0 : 4;W32(s->component+8,s->entity_count);W32(s->component+12,s->entity_count ? 3 : 0);W32(s->component+16,s->entity_count ? 2 : 0);
    W64(s->component+0x58,s->component_address+0x14);W32(s->component+0x60,8);W32(s->component+0x68,1);
    for (unsigned i=0;i<4;i++) {
        s->entities[i]={0x250000000+uint64_t(i)*64,50+i,i<2 ? 1u : 0u};W64(s->component+0x70+8*i,s->entities[i].address);
        if (s->entity_count) {W32(s->component+0x14+((50+i)&7)*8,50+i);W32(s->component+0x18+((50+i)&7)*8,i);}
    }
    for (unsigned i=0x90;i<EP_C33_SOURCE_BYTES;i++) s->component[i]=(uint8_t)(i*13+7);
    t->resources.seed=1;t->resources.entries[5]={901,7};t->resources.entries[6]={1030,0};t->resources.queued=1;t->resources.queue[0]=1030;
    if (t->mode==2) {
        t->resources={};t->resources.seed=1;t->resources.queued=128;
        for (unsigned i=0;i<128;i++) {t->resources.entries[(i+1)&127]={i+1,0};t->resources.queue[i]=i+1;}
    }
    W64(t->descriptor,0x280000000);W32(t->descriptor+8,128);W32(t->descriptor+12,0x96969696);W32(t->descriptor+24,1);
    // Independent expected four-array layout, including inactive old slots;
    // the new slots/padding remain zero. Resource rehash is separately tested.
    memcpy(t->expected_b.data,s->component+0x70,32);memcpy(t->expected_b.data+0x40,s->component+0x90,4);
    memcpy(t->expected_b.data+0x50,s->component+0x98,4*0x50);memcpy(t->expected_b.data+0x2d0,s->component+0x1d8,4*0x38);
    Check(ep_c33_resource_migrate(&t->pub.entry.native.p.test.resources.binding,&t->resources,t->expected_arena,sizeof(t->expected_arena))==0,"expected resource image");
    if (t->mode==3) s->global_component+=8;
    if (t->mode==4) W32(s->component+8,5);
    if (t->mode==5) W32(s->component+0x18+2*8,3);
    if (t->mode==6) W64(s->component+0x70,(UINT64_C(1)<<47)-4);
    if (t->mode==7) s->entities[0].id=UINT32_MAX;
    if (t->mode==8) s->entities[0].flags=0;
    if (t->mode==9) W32(t->descriptor+8,256);
    if (t->mode==10) W64(t->descriptor+16,1);
    if (t->mode==11) W64(t->descriptor,0);
    if (t->mode==12) t->resources.queued=129;
    if (t->mode==13) t->resources.entries[0].references=1;
    if (t->mode==14) {t->resources.queued=2;t->resources.queue[1]=1030;}
}
EXPORT unsigned c33_migration_commit_test(unsigned mode)
{
    Check(mode<=30 || (mode>=100 && mode<=144),"migration scenario");MigrationTest t={};t.mode=mode;migrating=&t;
    auto* p=&t.pub;auto* e=&p->entry;auto* n=&e->native;auto* s=&n->p.test;publishing=p;entryTest=e;NativeSetup(n,0);
    n->api.read=MigrationRead;n->api.read_code=MigrationCode;n->api.write=PubWrite;n->api.hook_ex=PubHook;
    p->guard={p,PubBegin,MigrationValidate,MigrationEnd};
    EpC33ResourceEntryBindings b={s->storage.handle,s->owner,{0x191000000,0x191010000,0x191020000,0x191030000},PubReject,p};
    EpC33CallerEntryConfig config={};config.core.leave={{{{0x191040000,0x191050000},{0x191060000,0x191070000},0x191080000},0x191090000,0x1910a0000},0x1910b0000,0x1910c0000};
    for (unsigned i=0;i<14;i++) config.core.desired_entries[i]=0x192000000+i*0x10000;
    for (unsigned i=0;i<3;i++) config.desired_entries[i]=0x193000000+i*0x10000;
    Check(ep_component33_resource_entries_prepare_transaction(&n->api,s->mod,&b,&config,&e->entries),"migration entry preparation");
    p->group=Find(s->mod,e->entries.handle);
    for (unsigned i=0;i<3;i++) {auto w=GetWindow(p->group,i);memcpy(p->windows[i],w.expected,w.bytes);}
    Check(ep_component33_resource_entries_retain(s->mod,e->entries.handle) && ep_component33_resource_entries_publish(s->mod,e->entries.handle,17),"migration publication");
    Check(!t.data_calls,"publication read original data");
    MigrationSourceSetup(&t);memcpy(t.before_b,(void*)(uintptr_t)s->storage.storage_address,sizeof(t.before_b));
    memcpy(t.before_arena,(void*)(uintptr_t)s->resources.binding.address,sizeof(t.before_arena));
    auto source_before=t.source;auto resources_before=t.resources;
    if (mode==23) p->mode=68;if (mode==24) p->mode=72;if (mode==28) p->mode=75;
    migration_alloc_fail=mode==26;EpC33MigrationCommitResult result={};
    bool committed=ep_component33_resource_entries_commit_migrated(s->mod,e->entries.handle,&p->guard,&result)!=0;migration_alloc_fail=false;
    bool unsafe=mode==16 || (mode>=20 && mode<=22) || mode==24 || mode==25 || (mode>=27 && mode<=30);
    Check(committed==(mode<=2),"migration commit result");
    Check(result.read_bytes==t.requested && result.read_bytes<=65536,"migration SDK budget accounting");
    if (mode==2) Check(result.read_bytes==11740,"maximum original snapshot budget");
    if (mode==29) Check(t.data_calls==5,"continued after nested read fault");
    if (mode==30) Check(t.data_calls==31,"continued after staged nested fault");
    Check(ep_component33_resource_entries_info(s->mod,e->entries.handle,&e->entries),"migration commit info");
    Check(e->entries.active==unsigned(committed || mode==28) && e->entries.commit_outcome==(unsafe ? EP_C33_COMMIT_UNSAFE : committed ? EP_C33_COMMIT_NEW : EP_C33_COMMIT_OLD),"migration outcome/latch");
    if (committed) {CheckNewData(&t);Check(!result.restored && result.status==EP_C33_MIGRATION_OK,"migration success diagnostics");}
    else if (mode!=28) {
        if (mode!=25) Check(!memcmp(t.before_b,(void*)(uintptr_t)s->storage.storage_address,sizeof(t.before_b)),"failed migration component bytes");
        Check(!memcmp(t.before_arena,(void*)(uintptr_t)s->resources.binding.address,sizeof(t.before_arena)),"failed migration arena bytes");
        if (t.checked_stage) Check(result.restored==(mode==25 ? 2u : 3u),"migration restoration coverage");
    }
    if (mode!=17 && mode!=18) Check(!memcmp(&source_before,&t.source,sizeof(t.source)),"migration wrote source component/entities");
    Check(!memcmp(&resources_before,&t.resources,sizeof(t.resources)) && !n->calls,"migration changed original globals or invoked services");
    EpRosterOwnerInfo owner={};Check(ep_roster_owner_info(s->mod,s->owner,&owner)==0 && bool(owner.fault)==unsafe,"migration quarantine");
    if (unsafe) Check(p->lease,"unsafe migration resumed");
    else Check(!p->lease,"finished migration retained lease");
    if (mode==25) {DWORD old;Check(VirtualProtect((void*)(uintptr_t)s->storage.storage_address,4096,PAGE_READWRITE,&old),"restore fixture protection");}
    if (!committed && !unsafe) {
        // Same published group can retry against a newly supplied current OLD
        // image; permanent retention must not pin stale preparation bytes.
        t.mode=p->mode=0;t.data_calls=t.global_calls=t.requested=0;t.checked_stage=false;p->reads=p->writes=p->restored=0;
        t.source={};t.resources={};memset(t.descriptor,0,sizeof(t.descriptor));t.expected_b={};MigrationSourceSetup(&t);
        Check(ep_component33_resource_entries_commit_migrated(s->mod,e->entries.handle,&p->guard,&result),"fresh migration retry");CheckNewData(&t);
    }
    unsigned reads=t.data_calls;Check(!ep_component33_resource_entries_commit_migrated(s->mod,e->entries.handle,&p->guard,&result) && t.data_calls==reads,"active/unsafe migration repeated");
    Check(!ep_roster_owner_in_scope() && !p->group->switching && !routeGroup,"migration scope leak");
    Check(ep_roster_owner_close(s->mod,s->owner)==0,"close migration owner");CloseHandle(s->entered);CloseHandle(s->proceed);
    Check(migration_allocations==migration_frees,"migration scratch leak");
    migrating=nullptr;publishing=nullptr;entryTest=nullptr;nativeTest=nullptr;active=nullptr;return checks;
}
