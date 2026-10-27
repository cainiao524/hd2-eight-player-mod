/* Only fixture-owned code/data and declared SDK maps. No game access, process
 * enumeration, installation, original engine pause, or native UI validation. */
#include "component33_migration_commit_dll.cpp"
#include "../mod/src/ep_multiplayer_commit.h"
#include "../mod/src/ep_roster_gate.h"
static uint64_t JointRosterNew(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
static EpPropertyResult JointFixtureGate(uint32_t kind,const EpInsertAddresses* a,uint64_t control,uint64_t next,EpRosterGateImage* out)
{
    auto rc=ep_roster_gate_build(kind,a,control,next,out);if (rc!=EP_PROPERTY_OK) return rc;
    const uint8_t jump[]={0xff,0x25,0,0,0,0};uintptr_t body=(uintptr_t)JointRosterNew;
    memcpy(out->data+32,jump,6);memcpy(out->data+38,&body,8);return rc;
}
#define ep_roster_gate_build JointFixtureGate
#include "../mod/src/ep_roster_group.cpp"
#undef ep_roster_gate_build
struct JointTest {
    MigrationTest migration;EpRosterGroupInfo roster;EpRosterGroup* group;
    EpC33EntryCommitGuard guard;EpMultiplayerCommitResult result;
    unsigned mode,index,hooks,old_calls,new_calls,failures;bool hold,nest;
};
static JointTest* joint;
static uint64_t JointRosterProbe(bool next,uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f)
{
    auto* t=joint;auto* p=&t->migration.pub;auto* s=&p->entry.native.p.test;
    Check(ep_roster_owner_native_status(s->mod,s->owner)==0,"roster outside joint owner");
    Check(t->group->active==p->group->active && !t->group->switching && !p->group->switching,"mixed joint layouts/barrier escape");
    Check(next==bool(t->group->active && t->index+1!=EP_ROSTER_ENTITY_REMOVE),"roster selection");
    Check(a==11 && b==23 && c==37 && d==53,"joint roster register ABI");
    if (t->index+1==EP_ROSTER_SEND) Check(e==71 && f==97,"joint roster producer stack ABI");
    if (next) ++t->new_calls;else ++t->old_calls;
    if (t->nest) {PubCall call={p,8,true};PubRun(&call);}
    if (t->hold) {SetEvent(s->entered);Check(WaitForSingleObject(s->proceed,5000)==WAIT_OBJECT_0,"joint old call release");}
    return next ? 1001 : 1000;
}
static uint64_t JointRosterNew(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f) {return JointRosterProbe(true,a,b,c,d,e,f);}
static uint64_t JointRosterOld(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f) {return JointRosterProbe(false,a,b,c,d,e,f);}
static void JointRosterFailure(void* p,uint32_t,EpRosterOwnerResult status,EpRosterCallFrame* f)
{auto* t=(JointTest*)p;++t->failures;Check(status!=EP_OWNER_OK,"missing joint failure");f->rax=9000;}
static void JointRosterRun(unsigned index,bool next,bool failure=false)
{
    joint->index=index;auto fn=(uint64_t(*)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t))joint->roster.code[index].base;
    Check(fn(11,23,37,53,71,97)==(failure ? 9000u : next && index+1!=EP_ROSTER_ENTITY_REMOVE ? 1001u : 1000u),"joint roster return");
}
static int JointRosterHook(HfMod* mod,uintptr_t target,void* detour,void** original,int32_t priority)
{
    auto* t=joint;unsigned i=t->hooks++;
    Check(i<EP_ROSTER_ENTRIES && mod==t->group->owner && target==t->group->targets[i] && detour==(void*)t->roster.code[i].base &&
        original==(void**)t->roster.code[i].next_pointer && priority==17,"joint roster publication binding");
    if (t->mode==16 && i==8) return 1;
    InterlockedExchangePointer(original,(void*)JointRosterOld);
    if (t->mode!=17 && t->mode!=18) for (unsigned j=0;j<=i;j++) JointRosterRun(j,false);
    return 0;
}
static int JointUserBegin(void* p,void** lease)
{auto* t=(JointTest*)p;int ok=PubBegin(&t->migration.pub,lease);return t->mode==28 ? 0 : ok;}
static int UnreachableBegin(void*,void**) {Check(false,"independent commit entered guard");return 0;}
static int UnreachableValidate(void*,void*) {Check(false,"independent commit validated");return 0;}
static void UnreachableEnd(void*,void*,int) {Check(false,"independent commit ended");}
static int JointUserValidate(void* p,void* lease)
{
    auto* t=(JointTest*)p;Check(t->group->switching && !t->group->active,"roster not staged with component");
    int ok=MigrationValidate(&t->migration.pub,lease);
    if (t->mode==10) JointRosterRun(0,false,true);
    if (t->mode==23) {
        auto* s=&t->migration.pub.entry.native.p.test;EpMultiplayerCommitResult result={};
        EpPropertyCommitGuard independent={nullptr,UnreachableBegin,UnreachableValidate,UnreachableEnd};
        Check(!ep_roster_group_commit(s->mod,t->roster.handle,&independent) && !ep_roster_group_cancel(s->mod,t->roster.handle),"claimed roster management allowed");
        Check(!ep_multiplayer_commit(s->mod,t->roster.handle,t->migration.pub.entry.entries.handle,&t->guard,&result),"recursive joint commit accepted");
    }
    return ok;
}
static void JointUserEnd(void* p,void* lease,uint32_t outcome)
{
    auto* t=(JointTest*)p;auto* pub=&t->migration.pub;
    Check(t->group->switching && (outcome==EP_C33_COMMIT_NEW)==bool(t->group->active),"end before joint latch/barrier");
    if (t->mode==11 || t->mode==27) {
        JointRosterRun(0,false,true);++pub->ends;pub->outcome=outcome;return; // ignored nested failure must quarantine both
    }
    if (t->mode==28) JointRosterRun(0,false,true); // invalid begin never entered; UNSAFE must already block it
    MigrationEnd(pub,lease,outcome);
}
static DWORD WINAPI JointCommitThread(void* p)
{
    auto* t=(JointTest*)p;auto* s=&t->migration.pub.entry.native.p.test;
    return ep_multiplayer_commit(s->mod,t->roster.handle,t->migration.pub.entry.entries.handle,&t->guard,&t->result) ? 0 : 1;
}
static DWORD WINAPI JointCallThread(void* p) {auto* t=(JointTest*)p;JointRosterRun(0,t->mode==25);return 0;}
static void JointFixtureSetup(JointTest* test,unsigned mode)
{
    JointTest& t=*test;t.mode=mode;joint=&t;migrating=&t.migration;
    auto* m=&t.migration;auto* p=&m->pub;auto* e=&p->entry;auto* n=&e->native;auto* s=&n->p.test;
    publishing=p;entryTest=e;NativeSetup(n,0);n->api.read=MigrationRead;n->api.read_code=MigrationCode;n->api.write=PubWrite;n->api.hook_ex=PubHook;
    t.guard={&t,JointUserBegin,JointUserValidate,JointUserEnd};
    EpC33ResourceEntryBindings bindings={s->storage.handle,s->owner,{0x191000000,0x191010000,0x191020000,0x191030000},PubReject,p};
    EpC33CallerEntryConfig config={};config.core.leave={{{{0x191040000,0x191050000},{0x191060000,0x191070000},0x191080000},0x191090000,0x1910a0000},0x1910b0000,0x1910c0000};
    for (unsigned i=0;i<14;i++) config.core.desired_entries[i]=0x192000000+i*0x10000;
    for (unsigned i=0;i<3;i++) config.desired_entries[i]=0x193000000+i*0x10000;
    Check(ep_component33_resource_entries_prepare_transaction(&n->api,s->mod,&bindings,&config,&e->entries),"joint component prepare");
    p->group=Find(s->mod,e->entries.handle);for (unsigned i=0;i<3;i++) {auto w=GetWindow(p->group,i);memcpy(p->windows[i],w.expected,w.bytes);}
    p->mode=mode==15 ? 1 : 0;
    Check(ep_component33_resource_entries_retain(s->mod,e->entries.handle),"joint component retain");
    Check(bool(ep_component33_resource_entries_publish(s->mod,e->entries.handle,17))==(mode!=15),"joint component publish");p->mode=0;
    for (auto& c:p->group->core) c.body=(uintptr_t)PubNew;
    n->api.hook_ex=JointRosterHook;EpRosterGroupBindings roster={};
    uint64_t other=0;auto view=s->roster;
    if (mode==18) {view.game+=0x10000000;view.roster+=0x10000000;view.storage+=0x10000000;EpRosterMemory memory={nullptr,Read};
        Check(ep_roster_owner_create(s->mod,&view,&memory,&other)==0,"separate owner fixture");}
    roster.game_base=view.game;roster.roster_address=view.roster;roster.storage_address=view.storage;
    // Keep the original roster/storage RIP-relative references within 2 GiB.
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {roster.desired_code[i]=0x1c4000000+uint64_t(mode==18)*0x10000000+i*0x10000;roster.reject[i]=0x1e4000000+i*0x10000;}
    EpRosterCallPolicy policy={JointRosterFailure,&t,nullptr};
    Check(mode==17 ? ep_roster_group_prepare(&n->api,s->mod,&roster,&t.roster) :
        ep_roster_group_prepare_owned(&n->api,s->mod,&roster,other ? other : s->owner,&policy,&t.roster),"joint roster prepare");
    t.group=EpGroupFind(s->mod,t.roster.handle);
    Check(bool(ep_roster_group_publish(s->mod,t.roster.handle,17))==(mode!=16),"joint roster publish");
    MigrationSourceSetup(m);memcpy(m->before_b,(void*)(uintptr_t)s->storage.storage_address,sizeof(m->before_b));
    memcpy(m->before_arena,(void*)(uintptr_t)s->resources.binding.address,sizeof(m->before_arena));
}
EXPORT unsigned multiplayer_commit_test(unsigned mode)
{
    Check(mode<=29,"joint scenario");JointTest t={};JointFixtureSetup(&t,mode);
    uint64_t other=mode==18 ? t.group->storage_owner : 0;
    auto* m=&t.migration;auto* p=&m->pub;auto* e=&p->entry;auto* n=&e->native;auto* s=&n->p.test;
    auto old_source=m->source;auto old_resources=m->resources;
    if (mode==1 || mode==27) m->mode=19;if (mode==2) m->mode=15;if (mode==3) p->mode=68;if (mode==4) p->mode=72;
    if (mode>=5 && mode<=7) p->mode=mode+55;if (mode==8) p->mode=75;if (mode==9) m->mode=20;if (mode==12) p->mode=76;
    if (mode==13) {Check(ep_roster_owner_close(s->mod,s->owner)==0,"joint closed owner");p->mode=77;}
    if (mode==14) {auto* owner=OwnerAcquire(s->mod,s->owner);Check(owner!=nullptr,"joint revision access");owner->revision=UINT64_MAX;OwnerRelease(owner);}
    if (mode==19) t.group->calls[0].game+=0x1000;
    if (mode==20) InterlockedExchangePointer((void* volatile*)t.roster.code[16].next_pointer,nullptr);
    if (mode==22) {
        EpRosterGroupTransition a={},b={};Check(ep_roster_group_transition_claim(s->mod,t.roster.handle,s->owner,s->roster.game,&a),"first claim");
        Check(ep_roster_group_transition_finish(s->mod,&a,EP_ROSTER_TRANSITION_OLD),"abandon unentered claim");
        Check(ep_roster_group_transition_claim(s->mod,t.roster.handle,s->owner,s->roster.game,&b),"second claim");
        Check(a.sequence!=b.sequence && !ep_roster_group_transition_finish(s->mod,&a,EP_ROSTER_TRANSITION_OLD),"stale token ended new attempt");
        Check(ep_roster_group_transition_finish(s->mod,&b,EP_ROSTER_TRANSITION_OLD),"finish current token");
    }
    migration_alloc_fail=mode==21;bool committed=false;
    if (mode==24 || mode==25) {
        HANDLE call=nullptr,commit=nullptr;
        if (mode==24) {t.hold=true;call=CreateThread(nullptr,0,JointCallThread,&t,0,nullptr);Check(call && WaitForSingleObject(s->entered,5000)==WAIT_OBJECT_0,"old roster entered");}
        else p->mode=79;
        commit=CreateThread(nullptr,0,JointCommitThread,&t,0,nullptr);Check(commit!=nullptr,"joint commit thread");
        if (mode==25) {Check(WaitForSingleObject(s->entered,5000)==WAIT_OBJECT_0,"joint validate entered");call=CreateThread(nullptr,0,JointCallThread,&t,0,nullptr);Check(call!=nullptr,"queued roster call");}
        ULONGLONG until=GetTickCount64()+5000;while (!Pending(s,false) && GetTickCount64()<until) Sleep(1);
        Check(Pending(s,false) && WaitForSingleObject(mode==24 ? commit : call,0)==WAIT_TIMEOUT && !p->writes,"joint exclusion failed");
        t.hold=false;SetEvent(s->proceed);Check(WaitForSingleObject(call,5000)==WAIT_OBJECT_0 && WaitForSingleObject(commit,5000)==WAIT_OBJECT_0,"joint threads finished");
        DWORD rc=1;Check(GetExitCodeThread(commit,&rc) && !rc,"joint concurrent result");CloseHandle(call);CloseHandle(commit);committed=true;
    } else committed=ep_multiplayer_commit(s->mod,t.roster.handle,mode==29 ? UINT64_MAX : e->entries.handle,&t.guard,&t.result)!=0;
    migration_alloc_fail=false;
    bool success=mode==0 || (mode>=22 && mode<=26),unsafe=mode==4 || (mode>=6 && mode<=14) || mode==27 || mode==28;
    bool untouched=(mode>=15 && mode<=20) || mode==21 || mode==29;
    Check(committed==success,"joint commit result");
    Check(t.result.outcome==(success ? EP_C33_COMMIT_NEW : unsafe ? EP_C33_COMMIT_UNSAFE : EP_C33_COMMIT_OLD),"joint outcome");
    Check(t.result.component_migration.read_bytes==m->requested && m->requested<=65536,"joint component read cap");
    Check(ep_roster_group_info(s->mod,t.roster.handle,&t.roster) && ep_component33_resource_entries_info(s->mod,e->entries.handle,&e->entries),"joint info");
    Check(t.roster.active==e->entries.active && t.roster.active==unsigned(success || mode==8 || mode==11),"joint final latches");
    Check(t.group->switching==LONG(unsafe),"joint final roster barrier");
    if (untouched) Check(!p->begins && !m->data_calls && !p->reads && !p->writes && !p->ends,"invalid group accessed data/guard");
    if (mode==21) Check(t.result.roster_claimed && !t.group->transition && t.roster.state==EP_GROUP_READY &&
        e->entries.publication_state==EP_C33_PUBLISH_READY,"allocation failure stranded roster claim");
    if (unsafe) {
        Check(p->lease || mode==7,"joint unsafe resumed");
        if (mode!=13) {EpRosterOwnerInfo info={};Check(ep_roster_owner_info(s->mod,s->owner,&info)==0 && info.fault,"joint owner quarantine");}
        unsigned calls=t.old_calls+t.new_calls;JointRosterRun(0,false,true);Check(t.old_calls+t.new_calls==calls,"quarantined roster ran body");
    } else if (!untouched) {
        Check(!p->lease,"joint lease not released");
        if (!success) {
            Check(t.roster.state==EP_GROUP_READY && e->entries.publication_state==EP_C33_PUBLISH_READY,"joint safe retry state");
            for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) JointRosterRun(i,false);
            m->mode=p->mode=0;m->requested=m->data_calls=m->global_calls=0;m->checked_stage=false;p->reads=p->writes=p->restored=0;t.mode=0;
            Check(ep_multiplayer_commit(s->mod,t.roster.handle,e->entries.handle,&t.guard,&t.result),"joint safe retry");
        }
        for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) JointRosterRun(i,true);
        for (unsigned i=8;i<22;i++) {PubCall call={p,i,true};PubRun(&call);}
        if (mode==26) {EpRosterOwnerInfo before={},after={};Check(ep_roster_owner_info(s->mod,s->owner,&before)==0,"joint nested before");
            t.nest=true;JointRosterRun(0,true);t.nest=false;Check(ep_roster_owner_info(s->mod,s->owner,&after)==0 && after.revision==before.revision+1,"joint nested one revision");}
        unsigned begins=p->begins;Check(!ep_multiplayer_commit(s->mod,t.roster.handle,e->entries.handle,&t.guard,&t.result) && p->begins==begins,"active joint retry");
    }
    Check(!memcmp(&old_source,&m->source,sizeof(old_source)) && !memcmp(&old_resources,&m->resources,sizeof(old_resources)) && !n->calls,"joint changed original data/called services");
    Check(!ep_roster_owner_in_scope() && !routeGroup && !p->group->switching,"joint scope leak");
    if (mode!=13) Check(ep_roster_owner_close(s->mod,s->owner)==0,"close joint owner");if (other) Check(ep_roster_owner_close(s->mod,other)==0,"close unrelated owner");
    CloseHandle(s->entered);CloseHandle(s->proceed);Check(migration_allocations==migration_frees,"joint scratch leak");return checks;
}
