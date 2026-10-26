#include "multiplayer_commit_dll.cpp"
struct RosterMigrationTest {
    JointTest joint;EpRosterMigrationSnapshot source;uint8_t before[0x680],expected[0x680];
    unsigned mode,reads,requested,source_reads;uint64_t local,user;
};
static RosterMigrationTest* rosterMigrating;
static int RosterFixtureMap(uintptr_t a,void* out,size_t n)
{
    auto* t=rosterMigrating;auto* s=&t->joint.migration.pub.entry.native.p.test;
    Region regions[]={{s->roster.game+0x3326468,8,&t->source.global},{s->roster.game+0x3483c34,4,&t->source.invalid},
        {s->roster.roster,sizeof(t->source.source),t->source.source},{0x270000000,64,t->source.map},
        {s->roster.game+0x347cef0,8,&t->user},{0x28000b398,8,&t->local}};
    for (const auto& r:regions) if (a>=r.address && a-r.address<=r.bytes && n<=r.bytes-(a-r.address)) {
        memcpy(out,(const uint8_t*)r.data+a-r.address,n);return 0;
    }
    for (const auto& e:t->source.entities) if (n==4 && (a==e.address+8 || a==e.address+20)) {
        memcpy(out,a==e.address+8 ? &e.id : &e.flags,4);return 0;
    }
    Check(false,"unlisted roster source read");return 1;
}
static int RosterFixtureRead(uintptr_t a,void* out,size_t n)
{
    auto* t=rosterMigrating;auto* p=&t->joint.migration.pub;auto* s=&p->entry.native.p.test;
    ++t->reads;t->requested+=(unsigned)n;
    Check(p->lease && t->joint.group->switching && p->group->switching && ep_roster_owner_native_status(s->mod,s->owner)==0,"roster read outside joint freeze");
    if ((t->mode==120 && t->reads==1) || (t->mode>=1001 && t->reads==t->mode-1000)) return 1;
    if (t->mode==128 && t->reads==1) RaiseException(0xe04333e1,0,0,nullptr);
    if (t->mode==129 && t->reads==1) Check(ep_roster_owner_call(s->mod,s->owner,1,NestedFailure,nullptr)==EP_OWNER_CALLBACK_FAILED,"roster read nested fault");
    if (a==s->roster.roster && ++t->source_reads==2 && t->mode==121) t->source.source[0x108]^=1;
    return RosterFixtureMap(a,out,n);
}
static int RosterFixtureMemory(void*,uintptr_t a,void* out,size_t n)
{
    auto* s=&rosterMigrating->joint.migration.pub.entry.native.p.test;
    if (a==s->roster.storage && n==EP_NATIVE_ROSTER_BYTES) {memcpy(out,(void*)a,n);return 1;}
    return RosterFixtureMap(a,out,n)==0;
}
static int RosterFixtureValidate(void* p,void* lease)
{
    auto* t=rosterMigrating;auto* s=&t->joint.migration.pub.entry.native.p.test;
    Check(!memcmp((void*)s->roster.storage,t->expected,sizeof(t->expected)),"roster arrays not migrated before guard");
    int ok=JointUserValidate(p,lease);
    if (t->mode==122) t->source.source[0x108]^=1;
    if (t->mode==123) ((uint8_t*)s->roster.storage)[0]^=1;
    if (t->mode==124) return 0;
    if (t->mode==125) RaiseException(0xe04333e2,0,0,nullptr);
    if (t->mode==127) {DWORD old;Check(VirtualProtect((void*)s->roster.storage,4096,PAGE_READONLY,&old),"roster protect rollback");return 0;}
    if (t->mode==133) t->source.global+=8;
    return ok;
}
static int RosterFixtureWrite(uintptr_t a,const void* bytes,size_t n)
{
    int rc=PubWrite(a,bytes,n);
    if (rosterMigrating->mode==132) ((uint8_t*)rosterMigrating->joint.migration.pub.entry.native.p.test.roster.storage)[0]^=1;
    return rc;
}
static void RosterFixtureEnd(void* p,void* lease,uint32_t outcome)
{
    auto* t=rosterMigrating;auto* pub=&t->joint.migration.pub;auto* s=&pub->entry.native.p.test;
    if (outcome==EP_C33_COMMIT_NEW) Check(!memcmp((void*)s->roster.storage,t->expected,sizeof(t->expected)),"NEW roster bytes");
    else if (t->mode!=127 && t->mode!=132) Check(!memcmp((void*)s->roster.storage,t->before,sizeof(t->before)),"roster restore must precede external end");
    if (t->mode==132) {Check(outcome==EP_C33_COMMIT_UNSAFE && !t->joint.group->active && pub->group->active,"late corruption must not release mixed layouts");PubEnd(pub,lease,outcome);}
    else JointUserEnd(p,lease,outcome);
}
static int RosterNoop(void*,const EpNativeRosterView*) {return 1;}
EXPORT unsigned roster_migration_commit_test(unsigned mode)
{
    Check(mode<30 || (mode>=100 && mode<=134) || (mode>=1001 && mode<=1036),"roster migration scenario");
    RosterMigrationTest t={};rosterMigrating=&t;t.mode=mode;JointFixtureSetup(&t.joint,0);
    auto* j=&t.joint;auto* m=&j->migration;auto* p=&m->pub;auto* s=&p->entry.native.p.test;
    OwnPage(s->roster.storage);memset((void*)s->roster.storage,0xa7,sizeof(t.before));memset(t.before,0xa7,sizeof(t.before));
    unsigned count=4,prefix=2;bool inlined=false;
    if (mode<30) {unsigned shape=mode/2;inlined=mode&1;count=0;while (shape>count) shape-=++count;prefix=shape;}
    t.source.global=s->roster.roster;t.source.invalid=UINT32_MAX;t.user=0x280000000;t.local=count ? 100 : 0;
    auto* data=t.source.source;W32(data+0x80,count);W32(data+0x84,count);W32(data+0x88,prefix);
    W64(data+0xd0,inlined ? s->roster.roster+0x90 : 0x270000000);W32(data+0xd8,8);W32(data+0xe0,1);
    for (unsigned i=0xe8;i<sizeof(t.source.source);i++) data[i]=(uint8_t)(i*37+11);
    EpRosterIdentitySet ids={};ids.count=count;
    for (unsigned i=0;i<4;i++) {
        t.source.entities[i]={0x260000000+uint64_t(i)*64,1+8*i,unsigned(i<prefix)};
        W64(data+0xe8+8*i,t.source.entities[i].address);W64(data+0x2c8+0x38*i,100+i);W32(data+0x3a8+0x20*i+12,(i+1)%4);
        if (i<count) {W32(t.source.map+8*(i+1),1+8*i);W32(t.source.map+8*(i+1)+4,i);ids.tickets[count-1-i]={100+i,s->roster.epoch,1+8*i,(i+1)%4,10+i,0};}
    }
    if (inlined) memcpy(data+0x90,t.source.map,64);
    memcpy(t.expected,data+0xe8,32);memcpy(t.expected+0x40,data+0x108,4*0x70);memcpy(t.expected+0x3c0,data+0x2c8,4*0x38);memcpy(t.expected+0x580,data+0x3a8,4*0x20);
    if (mode==117) ids.tickets[0].player=999;if (mode==118) ids.count=3;
    EpRosterOwnerInfo owner={};Check(ep_roster_owner_info(s->mod,s->owner,&owner)==0 &&
        ep_roster_owner_mutate(s->mod,s->owner,owner.revision,&ids,RosterNoop,nullptr)==0,"fixture authoritative identity set");
    auto* real=OwnerAcquire(s->mod,s->owner);real->memory={nullptr,RosterFixtureMemory};OwnerRelease(real);
    if (mode==100) t.source.global+=8;if (mode==101) W32(data+0x80,5);if (mode==102) W32(data+0x84,3);if (mode==103) W32(data+0x88,5);
    if (mode==104) W32(data+0xd8,16);if (mode==105) W64(data+0xd0,0x270000001);if (mode==106) W64(data+0xd0,s->roster.roster+0x98);
    if (mode==107) W64(data+0xd0,s->roster.storage);if (mode==108) W64(data+0xe8,(UINT64_C(1)<<47)-8);
    if (mode==109) W64(data+0xf0,t.source.entities[0].address);if (mode==110) W32(t.source.map+2*8+4,0);
    if (mode==111) W32(t.source.map+8,UINT32_MAX);if (mode==112) {memcpy(t.source.map+6*8,t.source.map+8,8);memset(t.source.map+8,0,8);}
    if (mode==113) t.source.entities[0].id=0;if (mode==114) t.source.entities[0].flags=0;
    if (mode==115) W64(data+0x2c8,999);if (mode==116) W32(data+0x3a8+12,4);
    if (mode==119) {DWORD old;Check(VirtualProtect((void*)s->roster.storage,4096,PAGE_READONLY,&old),"roster protect stage");}
    if (mode==126) p->mode=75;if (mode==130) p->mode=68;if (mode==131) p->mode=72;
    if (mode==132) p->group->api.write=RosterFixtureWrite;
    if (mode==134) {
        EpCommitReadBudget budget={};EpC33MigrationCommitResult result={};EpC33EntryCommitGuard guard={p,PubBegin,MigrationValidate,MigrationEnd};
        Check(ep_commit_read_reserve(&budget,65530),"preceding subsystem budget");unsigned reads=m->requested;
        Check(!ep_component33_resource_entries_commit_budgeted(s->mod,p->entry.entries.handle,&guard,&budget,&result) && budget.used==65530 && !result.read_bytes && m->requested==reads,"component exceeded shared budget");
        budget.used=UINT32_MAX;Check(!ep_component33_resource_entries_commit_budgeted(s->mod,p->entry.entries.handle,&guard,&budget,&result) && result.status==EP_C33_MIGRATION_ARGUMENT,"invalid shared budget accepted");
    }
    HfApi api=p->entry.native.api;api.read=RosterFixtureRead;EpC33EntryCommitGuard guard={j,JointUserBegin,RosterFixtureValidate,RosterFixtureEnd};
    bool ok=ep_multiplayer_commit_migrated(&api,s->mod,j->roster.handle,p->entry.entries.handle,&guard,&j->result)!=0;
    bool success=mode<30 || mode==134,unsafe=mode==119 || (mode>=123 && mode<=129 && mode!=124) || mode==131 || mode==132;
    Check(ok==success && j->result.outcome==(success ? EP_C33_COMMIT_NEW : unsafe ? EP_C33_COMMIT_UNSAFE : EP_C33_COMMIT_OLD),"roster joint result");
    Check(j->result.total_read_bytes==m->requested+t.requested && j->result.total_read_bytes<=65536 &&
        j->result.roster_migration.read_bytes==t.requested && j->result.component_migration.read_bytes==m->requested,"shared actual requested bytes");
    if (success) {
        Check(j->result.roster_migration.status==EP_ROSTER_MIGRATION_OK && !j->result.roster_migration.restored,"roster success diagnostics");
        EpHfRosterSnapshot roster={};Check(ep_roster_owner_snapshot(s->mod,s->owner,s->roster.game,&roster)==EP_NATIVE_OK && roster.count==count,"actual migrated B through native provider");
        for (unsigned i=0;i<count;i++) Check(roster.players[i].peer==100+i && roster.players[i].player==1+8*i && roster.players[i].network_index==(i+1)%4 && roster.players[i].generation==10+i && bool(roster.players[i].local)==(i==0),"migrated identities/provider mapping");
        for (unsigned i=0;i<17;i++) JointRosterRun(i,true);
    } else {
        if (mode!=126 && mode!=127 && mode!=132) Check(!memcmp((void*)s->roster.storage,t.before,sizeof(t.before)),"roster final restoration");
        Check(ep_roster_owner_info(s->mod,s->owner,&owner)==0 && bool(owner.fault)==unsafe,"roster owner quarantine");
        if (unsafe) {Check(p->lease && j->group->switching,"unsafe roster released");JointRosterRun(0,false,true);}
        else {Check(!p->lease && !j->group->switching && !j->group->active && !p->group->active,"OLD roster resumed mixed");JointRosterRun(0,false);}
        if (mode==119 || mode==127) Check(j->result.roster_migration.status==EP_ROSTER_MIGRATION_RESTORE && !j->result.roster_migration.restored,"failed roster restoration diagnostics");
        if (mode==122 || mode==123 || mode==124 || mode==125 || mode==130 || mode==131 || mode==133 || mode>=1025)
            Check(j->result.roster_migration.restored,"missing roster rollback");
    }
    if (mode==124) {
        // A later attempt must use the current source, not the earlier stage.
        t.mode=0;t.source.source[0x108]^=0x5a;t.expected[0x40]^=0x5a;
        t.reads=t.requested=t.source_reads=0;m->requested=m->data_calls=m->global_calls=0;m->checked_stage=false;
        p->reads=p->writes=p->restored=0;
        Check(ep_multiplayer_commit_migrated(&api,s->mod,j->roster.handle,p->entry.entries.handle,&guard,&j->result),"fresh roster retry");
        Check(j->result.total_read_bytes==m->requested+t.requested && j->result.total_read_bytes<=65536 &&
            !memcmp((void*)s->roster.storage,t.expected,sizeof(t.expected)),"retry used stale roster/budget");
    }
    if (mode==119 || mode==127) {DWORD old;Check(VirtualProtect((void*)s->roster.storage,4096,PAGE_READWRITE,&old),"restore roster fixture protection");}
    Check(ep_roster_owner_close(s->mod,s->owner)==0,"close migrated roster owner");CloseHandle(s->entered);CloseHandle(s->proceed);
    Check(MigrationFree((void*)s->roster.storage,0,MEM_RELEASE),"free fixture roster B");Check(migration_allocations==migration_frees,"roster migration scratch leak");return checks;
}
