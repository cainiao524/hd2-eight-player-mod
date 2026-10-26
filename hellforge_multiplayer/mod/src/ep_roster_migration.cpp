#include "ep_roster_migration.h"
#include <string.h>
static uint32_t RosterD(const void* p) {uint32_t v;memcpy(&v,p,4);return v;}
static uint64_t RosterQ(const void* p) {uint64_t v;memcpy(&v,p,8);return v;}
static bool RosterRange(uint64_t a,uint64_t n,unsigned alignment=1) {return a>=0x10000 && a<=(UINT64_C(1)<<47)-n && !(a%alignment);}
static bool RosterOverlap(uint64_t a,uint64_t n,uint64_t b,uint64_t m) {return a<b+m && b<a+n;}
static bool RosterRead(EpRosterMigrationStage* s,uint64_t a,void* p,uint32_t n)
{
    if (ep_roster_owner_native_status(s->mod,s->owner)!=EP_OWNER_OK) return false;
    if (!RosterRange(a,n) || !ep_commit_read_reserve(s->budget,n)) {s->result.status=EP_ROSTER_MIGRATION_READ;return false;}
    s->result.read_bytes+=n;
    if (s->api.read((uintptr_t)a,p,n)!=0) {s->result.status=EP_ROSTER_MIGRATION_READ;return false;}
    return ep_roster_owner_native_status(s->mod,s->owner)==EP_OWNER_OK;
}
static int RosterCurrent(void* p,const EpNativeRosterView* view)
{((EpRosterMigrationStage*)p)->view=*view;return 1;}
static bool RosterCollect(EpRosterMigrationStage* s,EpRosterMigrationSnapshot* out)
{
    *out={};auto* v=&s->view;s->result.status=EP_ROSTER_MIGRATION_LAYOUT;
    if (!RosterRead(s,v->game+0x3326468,&out->global,8) || !RosterRead(s,v->game+0x3483c34,&out->invalid,4)) return false;
    if (out->global!=v->roster) return false;
    if (!RosterRead(s,v->roster,out->source,sizeof(out->source))) return false;
    const auto* p=out->source;uint32_t t=RosterD(p+0x80),d=RosterD(p+0x84),prefix=RosterD(p+0x88);
    uint64_t map=RosterQ(p+0xd0);
    if (t>4 || t!=d || prefix>d || RosterD(p+0xd8)!=8 || !RosterRange(map,64,8) ||
        (RosterOverlap(map,64,v->roster,sizeof(out->source)) && map!=v->roster+0x90) ||
        RosterOverlap(map,64,v->storage,EP_NATIVE_ROSTER_BYTES)) return false;
    if (map==v->roster+0x90) memcpy(out->map,p+0x90,64);
    else if (!RosterRead(s,map,out->map,64)) return false;
    for (unsigned i=0;i<t;i++) {
        auto* e=&out->entities[i];e->address=RosterQ(p+0xe8+i*8);
        if (!RosterRange(e->address,24) || RosterOverlap(e->address,24,v->roster,sizeof(out->source)) ||
            RosterOverlap(e->address,24,v->storage,EP_NATIVE_ROSTER_BYTES) || RosterOverlap(e->address,24,map,64)) return false;
        if (!RosterRead(s,e->address+8,&e->id,4) || !RosterRead(s,e->address+20,&e->flags,4)) return false;
    }
    return true;
}
static bool RosterBuild(EpRosterMigrationStage* s)
{
    auto* v=&s->view;auto* snap=&s->source;const auto* p=snap->source;
    unsigned t=RosterD(p+0x80),prefix=RosterD(p+0x88),empty=RosterD(p+0xdc),seed=RosterD(p+0xe0),seen=0;
    s->result.status=EP_ROSTER_MIGRATION_LAYOUT;
    for (unsigned i=0;i<8;i++) {
        uint32_t key=RosterD(snap->map+8*i),ordinal=RosterD(snap->map+8*i+4);
        if (key==empty) continue;
        if (!key || key==snap->invalid || ordinal>=t || (seen&(1u<<ordinal))) return false;
        seen|=1u<<ordinal;
    }
    if (seen!=((1u<<t)-1)) return false;
    s->result.status=EP_ROSTER_MIGRATION_IDENTITY;
    if (v->build!=25480438 || !v->epoch || v->ticket_count!=t) return false;
    unsigned tickets=0;
    for (unsigned i=0;i<t;i++) {
        const auto* e=&snap->entities[i];uint64_t peer=RosterQ(p+0x2c8+i*0x38);uint32_t index=RosterD(p+0x3a8+i*0x20+12);
        if (!e->id || e->id==empty || e->id==snap->invalid || (e->flags&1)!=unsigned(i<prefix) || !peer || index>=4) return false;
        for (unsigned j=0;j<i;j++) if (snap->entities[j].address==e->address || snap->entities[j].id==e->id) return false;
        bool found=false;unsigned bucket=(e->id*seed)&7;
        for (unsigned j=0;j<8;j++,bucket=(bucket+1)&7) {
            uint32_t key=RosterD(snap->map+8*bucket);if (key==empty) break;
            if (key==e->id) {found=RosterD(snap->map+8*bucket+4)==i;break;}
        }
        if (!found) return false;
        found=false;
        for (unsigned j=0;j<t;j++) {
            const auto* ticket=&v->tickets[j];
            if (ticket->peer==peer && ticket->player==e->id && ticket->network_index==index && ticket->epoch==v->epoch && ticket->generation && !ticket->reserved) {
                if (tickets&(1u<<j)) return false;tickets|=1u<<j;found=true;break;
            }
        }
        if (!found) return false;
    }
    // Preserve opaque bytes and inactive old slots; new slots start clear.
    memset(s->after,0,sizeof(s->after));memcpy(s->after,p+0xe8,32);
    memcpy(s->after+0x40,p+0x108,4*0x70);memcpy(s->after+0x3c0,p+0x2c8,4*0x38);memcpy(s->after+0x580,p+0x3a8,4*0x20);
    s->result.status=EP_ROSTER_MIGRATION_OK;return true;
}
bool ep_roster_migration_stage(EpRosterMigrationStage* s)
{
    if (ep_roster_owner_call(s->mod,s->owner,0,RosterCurrent,s)!=EP_OWNER_OK) return false;
    auto* v=&s->view;auto* c=&s->component;s->result.status=EP_ROSTER_MIGRATION_LAYOUT;
    if (!RosterRange(v->roster,sizeof(s->source.source),8) || !RosterRange(v->storage,sizeof(s->after),16) || v->game!=c->game ||
        RosterOverlap(v->roster,sizeof(s->source.source),v->storage,sizeof(s->after)) ||
        RosterOverlap(v->storage,sizeof(s->after),c->component,EP_C33_SOURCE_BYTES) ||
        RosterOverlap(v->storage,sizeof(s->after),c->storage,EP_COMPONENT33_STORAGE_BYTES) ||
        RosterOverlap(v->storage,sizeof(s->after),c->resources.address,ep_c33_resource_bytes(c->resources.capacity))) return false;
    EpRosterMigrationSnapshot again={};
    if (!RosterCollect(s,&s->source) || !RosterCollect(s,&again)) return false;
    if (memcmp(&s->source,&again,sizeof(again))) {s->result.status=EP_ROSTER_MIGRATION_CHANGED;return false;}
    if (!RosterBuild(s)) return false;
    memcpy(s->before,(void*)v->storage,sizeof(s->before));s->dirty=true;
    memcpy((void*)v->storage,s->after,sizeof(s->after));return true;
}
bool ep_roster_migration_intact(EpRosterMigrationStage* s)
{
    if (!s->dirty || !memcmp((void*)s->view.storage,s->after,sizeof(s->after))) return true;
    s->result.status=EP_ROSTER_MIGRATION_CHANGED;return false;
}
bool ep_roster_migration_check(EpRosterMigrationStage* s)
{
    EpRosterMigrationSnapshot again={};if (!RosterCollect(s,&again)) return false;
    if (memcmp(&s->source,&again,sizeof(again))) {s->result.status=EP_ROSTER_MIGRATION_CHANGED;return false;}
    s->result.status=EP_ROSTER_MIGRATION_OK;return true;
}
int ep_roster_migration_restore(void* p)
{
    auto* s=(EpRosterMigrationStage*)p;if (!s->dirty) return 1;
    uint32_t previous=s->result.status;s->result.status=EP_ROSTER_MIGRATION_RESTORE;
    memcpy((void*)s->view.storage,s->before,sizeof(s->before));
    if (memcmp((void*)s->view.storage,s->before,sizeof(s->before))) return 0;
    s->result.restored=1;s->result.status=previous;return 1;
}
