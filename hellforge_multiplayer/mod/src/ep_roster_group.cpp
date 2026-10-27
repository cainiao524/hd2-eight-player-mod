/* C-compatible for tests against the actual HellForge loader. */
#include "ep_roster_group.h"
#include "ep_player_join_call.h"
#include "ep_roster_group_transition.h"
#include "ep_roster_gate.h"
#include <windows.h>
#include <string.h>
typedef struct EpRosterGroup {
    HfMod* owner;
    uint64_t handle;
    volatile LONG active;
    uint32_t state,attempts;
    uintptr_t targets[EP_ROSTER_ENTRIES];
    uint64_t code[EP_ROSTER_ENTRIES];
    uint64_t storage_owner;
    EpRosterCallContext calls[EP_ROSTER_ENTRIES];
    volatile LONG switching;
    uint64_t transition;
    EpPlayerJoinPeers peers;
    uint32_t peer_count,peer_retained;
    EpClientPeerFamily peer_bodies;
    EpSessionCodeInfo peer_gates[EP_CLIENT_PEER_FAMILY_COUNT];
    EpRosterCallContext peer_calls[EP_CLIENT_PEER_FAMILY_COUNT];
} EpRosterGroup;
static EpRosterGroup epGroups[EP_ROSTER_GROUP_SLOTS];
static SRWLOCK epGroupLock=SRWLOCK_INIT;
static uint64_t epGroupSequence;
static uint64_t epTransitionSequence;
static EpRosterGroup* EpGroupFind(HfMod* owner,uint64_t id)
{
    if (owner && id) for (unsigned i=0;i<EP_ROSTER_GROUP_SLOTS;i++)
        if (epGroups[i].owner==owner && epGroups[i].handle==id) return &epGroups[i];
    return NULL;
}
static void EpGroupInfo(EpRosterGroup* g,EpRosterGroupInfo* out)
{
    memset(out,0,sizeof(*out)); out->handle=g->handle; out->state=g->state;
    out->active=(uint32_t)InterlockedCompareExchange(&g->active,0,0); out->published_attempts=g->attempts;
    out->storage_owner=g->storage_owner;
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) ep_session_code_info(g->owner,g->code[i],&out->code[i]);
}
int ep_roster_group_info(HfMod* owner,uint64_t id,EpRosterGroupInfo* out)
{
    int ok=0; if (!out) return 0; memset(out,0,sizeof(*out));
    AcquireSRWLockShared(&epGroupLock); EpRosterGroup* g=EpGroupFind(owner,id);
    if (g) { EpGroupInfo(g,out); ok=1; }
    ReleaseSRWLockShared(&epGroupLock); return ok;
}
/* Called with the group lock. Exposed gates can still read their latch/next. */
static int EpGroupCancel(EpRosterGroup* g)
{
    int ok=1;
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) if (g->code[i]) {
        EpSessionCodeInfo info;
        if (!ep_session_code_info(g->owner,g->code[i],&info)) { ok=0; continue; }
        if (!info.pinned) {
            if (ep_session_code_discard(g->owner,g->code[i])) g->code[i]=0;
            else ok=0;
        }
    }
    for (unsigned i=0;i<EP_CLIENT_PEER_FAMILY_COUNT;i++) {
        EpSessionCodeInfo* pair[]={&g->peer_gates[i],&g->peer_bodies.code[i]};
        for (auto* code:pair) if (code->handle) {
            EpSessionCodeInfo current={};
            if (!ep_session_code_info(g->owner,code->handle,&current)) {ok=0;continue;}
            if (!current.pinned) {
                if (ep_session_code_discard(g->owner,code->handle)) *code={};else ok=0;
            }
        }
    }
    if (ok && !g->attempts && !g->peer_retained) memset(g,0,sizeof(*g));
    else g->state=ok ? EP_GROUP_CANCELLED : EP_GROUP_FAILED;
    return ok;
}
static const uint32_t EpPeerRvas[EP_CLIENT_PEER_FAMILY_COUNT]={
    0x10872c0,0xb90b20,0x1087540,0x1087010,0x10845b0,0x1084fd0,0x1085010,0x1085090};
static int EpGroupPreparePeers(const HfApi* api,EpRosterGroup* g,const EpRosterGroupBindings* b,
    const EpRosterCallPolicy* policy,const EpClientPeerFamilyAddresses* family,const EpSessionCodeInfo* roster)
{
    if (ep_client_peer_family_prepare(api,g->owner,family,&g->peer_bodies)!=EP_PROPERTY_OK) return 0;
    for (unsigned i=0;i<EP_CLIENT_PEER_FAMILY_COUNT;i++)
        if (!ep_session_code_reserve(api,g->owner,0,48,&g->peer_gates[i])) return 0;
    // Exclude complete reservation windows and mutable next slots before gates
    // become executable. Numeric ranges only; neither bank is dereferenced.
    const uint64_t ranges[][2]={{g->peers.client-0x162c8,0x162c8+0x528},{g->peers.bank,g->peers.capacity*32ull},
        {b->roster_address,0x428},{b->storage_address,0x680},{family->reject,1},
        {(uintptr_t)epGroups,sizeof(epGroups)},{b->game_base,74727424}};
    for (unsigned i=0;i<sizeof(ranges)/sizeof(*ranges);i++) {
        const auto& r=ranges[i];
        for (unsigned j=0;j<i;j++) if (r[0]<ranges[j][0]+ranges[j][1] && ranges[j][0]<r[0]+r[1]) return 0;
        for (unsigned j=0;j<EP_ROSTER_ENTRIES+2*EP_CLIENT_PEER_FAMILY_COUNT;j++) {
            const auto& code=j<EP_ROSTER_ENTRIES ? roster[j] : j<EP_ROSTER_ENTRIES+EP_CLIENT_PEER_FAMILY_COUNT ?
                g->peer_bodies.code[j-EP_ROSTER_ENTRIES] : g->peer_gates[j-EP_ROSTER_ENTRIES-EP_CLIENT_PEER_FAMILY_COUNT];
            if ((r[0]<code.base+65536 && code.base<r[0]+r[1]) ||
                (r[0]<code.next_pointer+8 && code.next_pointer<r[0]+r[1])) return 0;
            for (unsigned k=0;k<EP_ROSTER_ENTRIES;k++)
                if ((b->reject[k]>=code.base && b->reject[k]<code.base+65536) ||
                    (b->reject[k]>=code.next_pointer && b->reject[k]<code.next_pointer+8)) return 0;
        }
    }
    for (unsigned i=0;i<EP_CLIENT_PEER_FAMILY_COUNT;i++) {
        auto& c=g->peer_calls[i];const auto& gate=g->peer_gates[i];
        c.mod=g->owner;c.owner=g->storage_owner;c.game=b->game_base;c.roster=b->roster_address;c.storage=b->storage_address;
        c.active=(volatile int32_t*)&g->active;c.switching=(volatile int32_t*)&g->switching;
        c.next_pointer=gate.next_pointer;c.body=g->peer_bodies.code[i].base;
        c.kind=EP_ROSTER_CALL_PEER_INSERT+i;c.policy=*policy;c.join_client=g->peers.client;
        uint8_t image[48]={};if (!ep_roster_call_prefix(&c,image)) return 0;
        image[32]=1;const uint32_t row[]={0,32,32};memcpy(image+36,row,sizeof(row));
        if (!ep_session_code_seal_table(g->owner,gate.handle,image,sizeof(image),36,1)) return 0;
    }
    g->peer_count=EP_CLIENT_PEER_FAMILY_COUNT;return 1;
}
int ep_roster_group_peer_routes_info(HfMod* mod,uint64_t id,EpRosterPeerRoutesInfo* out)
{
    if (!out) return 0;*out={};AcquireSRWLockShared(&epGroupLock);auto* g=EpGroupFind(mod,id);
    const int ok=g && g->state!=EP_GROUP_PREPARING && g->peer_count==EP_CLIENT_PEER_FAMILY_COUNT;
    if (ok) {
        out->group=id;out->count=g->peer_count;out->retained=g->peer_retained;
        for (unsigned i=0;i<g->peer_count;i++) {
            ep_session_code_info(mod,g->peer_bodies.code[i].handle,&out->body[i]);
            ep_session_code_info(mod,g->peer_gates[i].handle,&out->gate[i]);
        }
    }
    ReleaseSRWLockShared(&epGroupLock);return ok;
}
static int EpGroupPrepare(const HfApi* api,HfMod* owner,const EpRosterGroupBindings* input,uint64_t storage_owner,
    const EpRosterCallPolicy* policy,const EpPlayerJoinPeers* peer_input,const EpClientPeerFamilyAddresses* family,EpRosterGroupInfo* out)
{
    EpRosterGroupBindings bindings; EpRosterGroup* g=NULL; int ok=1;
    EpPlayerJoinPeers peers={};if (peer_input) peers=*peer_input;
    if (!out) return 0;
    if (input) bindings=*input;
    memset(out,0,sizeof(*out)); if (!input || !owner) return 0;
    if (peer_input && (!storage_owner || peers.reserved || peers.capacity<4 || peers.capacity>8 ||
        peers.client<0x10000+0x162c8 || peers.client>(UINT64_C(1)<<47)-0x528 || peers.client%8 ||
        peers.bank<0x10000 || peers.bank>(UINT64_C(1)<<47)-peers.capacity*32ull || peers.bank%16)) return 0;
    if (storage_owner && (!policy || !policy->failure || ep_roster_owner_check_binding(owner,storage_owner,
        bindings.game_base,bindings.roster_address,bindings.storage_address)!=EP_OWNER_OK)) return 0;
    if (!bindings.storage_address || (bindings.storage_address&15) || bindings.storage_address>(UINT64_C(1)<<47)-0x680) return 0;
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++)
        if (bindings.reject[i]>=bindings.storage_address && bindings.reject[i]<bindings.storage_address+0x680) return 0;
    uintptr_t groups=(uintptr_t)epGroups,groups_end=groups+sizeof(epGroups);
    if ((bindings.roster_address<groups_end && groups<bindings.roster_address+0x428) ||
        (bindings.storage_address<groups_end && groups<bindings.storage_address+0x680)) return 0;
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) if (bindings.reject[i]>=groups && bindings.reject[i]<groups_end) return 0;
    AcquireSRWLockExclusive(&epGroupLock);
    if (epGroupSequence!=UINT64_MAX) for (unsigned i=0;i<EP_ROSTER_GROUP_SLOTS;i++) if (!epGroups[i].handle) {
        g=&epGroups[i]; g->owner=owner; g->handle=++epGroupSequence; g->state=EP_GROUP_PREPARING;
        g->storage_owner=storage_owner;g->peers=peers;break;
    }
    ReleaseSRWLockExclusive(&epGroupLock); if (!g) return 0;
    EpSessionCodeInfo allocations[EP_ROSTER_ENTRIES]={{0}};
    /* Allocate every entry before binding its internal mover, association or getter body. */
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {
        EpRosterGateLayout layout; ep_roster_gate_layout(i+1,&layout);
        if (peer_input && i+1==EP_ROSTER_PLAYER_JOIN) layout.image_bytes=EP_PLAYER_JOIN_PEER_GATE_BYTES;
        if (!ep_session_code_reserve(api,owner,bindings.desired_code[i],layout.image_bytes,&allocations[i])) { ok=0; break; }
        AcquireSRWLockExclusive(&epGroupLock); g->code[i]=allocations[i].handle; ReleaseSRWLockExclusive(&epGroupLock);
    }
    /* Sealing protects complete committed pages, including image padding.
     * No storage, rejection path or next slot may occupy that padding. */
    SYSTEM_INFO system;GetSystemInfo(&system);
    for (unsigned i=0;ok && i<EP_ROSTER_ENTRIES;i++) {
        for (unsigned j=0;j<EP_ROSTER_ENTRIES;j++) {
            uintptr_t base=allocations[j].base;
            uint32_t bytes=(allocations[j].bytes+system.dwPageSize-1)/system.dwPageSize*system.dwPageSize;
            uintptr_t next=allocations[j].next_pointer;
            if ((bindings.reject[i]>=base && bindings.reject[i]<base+bytes) ||
                (bindings.reject[i]>=next && bindings.reject[i]<next+8) ||
                (bindings.roster_address<base+bytes && base<bindings.roster_address+0x428) ||
                (bindings.storage_address<base+bytes && base<bindings.storage_address+0x680) ||
                (allocations[i].base<next+8 && next<allocations[i].base+allocations[i].bytes)) ok=0;
            if (peer_input) {
                const uint64_t ranges[][2]={{peers.client-0x162c8,0x162c8+0x528},{peers.bank,peers.capacity*32ull}};
                for (const auto& range:ranges) {
                    auto p=range[0],n=range[1];
                    if ((p<base+bytes && base<p+n) || (p<next+8 && next<p+n) ||
                        (p<groups_end && groups<p+n) || (bindings.reject[i]>=p && bindings.reject[i]<p+n) ||
                        (p<bindings.roster_address+0x428 && bindings.roster_address<p+n) ||
                        (p<bindings.storage_address+0x680 && bindings.storage_address<p+n)) ok=0;
                }
            }
        }
        if (bindings.reject[i]>=(uintptr_t)&g->active && bindings.reject[i]<(uintptr_t)&g->active+4) ok=0;
    }
    for (unsigned i=0;ok && i<EP_ROSTER_ENTRIES;i++) {
        EpRosterGateImage image;
        EpInsertAddresses a={bindings.game_base,allocations[i].base,bindings.roster_address,bindings.storage_address,
            allocations[EP_ROSTER_MOVER-1].base+32,bindings.reject[i]};
        if (i+1==EP_ROSTER_REGISTRY_UPDATE) a.move_code_address=allocations[EP_ROSTER_ASSOCIATION-1].base+32;
        if (i+1==EP_ROSTER_DEPARTURE) a.move_code_address=allocations[EP_ROSTER_GETTER-1].base+32;
        if (peer_input && i+1==EP_ROSTER_PLAYER_JOIN) {
            EpPlayerJoinImage joined={};
            if (ep_player_join_peer_gate_build(bindings.game_base,allocations[i].base,(uintptr_t)&g->active,
                allocations[i].next_pointer,bindings.reject[i],&peers,&joined)!=EP_PROPERTY_OK) {ok=0;break;}
            image={};image.bytes=joined.bytes;image.table_offset=joined.table_offset;image.function_count=joined.function_count;
            memcpy(image.data,joined.data,joined.bytes);
        } else if (ep_roster_gate_build(i+1,&a,(uintptr_t)&g->active,allocations[i].next_pointer,&image)!=EP_PROPERTY_OK) {ok=0;break;}
        if (i+1==EP_ROSTER_PLAYER_JOIN) {
            uint32_t thunk;memcpy(&thunk,image.data+image.table_offset+8*12,4);
            uintptr_t checked=ep_player_join_creation_entry();memcpy(image.data+thunk+2,&checked,8);
        }
        if (storage_owner) {
            EpRosterCallContext* c=&g->calls[i];
            c->mod=owner;c->owner=storage_owner;c->game=bindings.game_base;c->roster=bindings.roster_address;c->storage=bindings.storage_address;
            c->active=(volatile int32_t*)&g->active;c->next_pointer=allocations[i].next_pointer;c->body=allocations[i].base+32;
            c->kind=i+1;c->policy=*policy;
            if (i+1==EP_ROSTER_PLAYER_JOIN) c->join_client=peers.client;
            c->switching=(volatile int32_t*)&g->switching;
            if (!ep_roster_call_prefix(c,image.data)) {ok=0;break;}
        }
        if (i+1==EP_ROSTER_PLAYER_JOIN) {
            uint32_t handler;memcpy(&handler,image.data+image.table_offset+9*12,4);
            const EpSessionGsCheck gs={1,handler,(uintptr_t)bindings.game_base+0x21044a0};
            if (!(peer_input ? ep_session_code_seal_player_join_peers(owner,g->code[i],image.data,image.bytes,image.table_offset,&gs) :
                  ep_session_code_seal_player_join(owner,g->code[i],image.data,image.bytes,image.table_offset,&gs))) ok=0;
        } else if (i+1==EP_ROSTER_STATE_UPDATE) {
            const EpSessionGsCheck gs={2,1952,(uintptr_t)bindings.game_base+0x21044a0};
            if (!ep_session_code_seal_gs_table(owner,g->code[i],image.data,image.bytes,image.table_offset,image.function_count,&gs)) ok=0;
        } else if (!ep_session_code_seal_table(owner,g->code[i],image.data,image.bytes,image.table_offset,image.function_count)) ok=0;
    }
    if (ok && family) ok=EpGroupPreparePeers(api,g,&bindings,policy,family,allocations);
    AcquireSRWLockExclusive(&epGroupLock);
    if (ok) {
        for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {
            EpRosterGateLayout layout;ep_roster_gate_layout(i+1,&layout);
            g->targets[i]=(uintptr_t)bindings.game_base+layout.original_rva;
        }
        g->state=EP_GROUP_PREPARED;
    } else EpGroupCancel(g);
    if (g->handle) EpGroupInfo(g,out);
    ReleaseSRWLockExclusive(&epGroupLock); return ok;
}
int ep_roster_group_prepare(const HfApi* api,HfMod* mod,const EpRosterGroupBindings* b,EpRosterGroupInfo* out)
{return EpGroupPrepare(api,mod,b,0,NULL,NULL,NULL,out);}
int ep_roster_group_prepare_owned(const HfApi* api,HfMod* mod,const EpRosterGroupBindings* b,uint64_t storage_owner,
    const EpRosterCallPolicy* policy,EpRosterGroupInfo* out)
{
    if (!storage_owner) {if(out) memset(out,0,sizeof(*out));return 0;}
    return EpGroupPrepare(api,mod,b,storage_owner,policy,NULL,NULL,out);
}
int ep_roster_group_prepare_owned_peers(const HfApi* api,HfMod* mod,const EpRosterGroupBindings* b,uint64_t storage_owner,
    const EpRosterCallPolicy* policy,const EpPlayerJoinPeers* peers,EpRosterGroupInfo* out)
{
    if (!storage_owner || !peers) {if(out) memset(out,0,sizeof(*out));return 0;}
    return EpGroupPrepare(api,mod,b,storage_owner,policy,peers,NULL,out);
}
int ep_roster_group_prepare_owned_peer_family(const HfApi* api,HfMod* mod,const EpRosterGroupBindings* b,uint64_t owner,
    const EpRosterCallPolicy* policy,const EpClientPeerFamilyAddresses* input,EpRosterGroupInfo* out)
{
    if (!out) return 0;*out={};if (!b || !owner || !input || input->game!=b->game_base) return 0;
    const auto family=*input;const EpPlayerJoinPeers peers={family.client,family.peers,family.capacity,family.reserved};
    return EpGroupPrepare(api,mod,b,owner,policy,&peers,&family,out);
}
int ep_roster_group_peer_binding(HfMod* mod,uint64_t id,EpPlayerJoinPeers* out)
{
    if (!out) return 0;*out={};AcquireSRWLockShared(&epGroupLock);auto* g=EpGroupFind(mod,id);
    int ok=g && g->peers.client && g->state!=EP_GROUP_PREPARING && g->state!=EP_GROUP_FAILED && g->state!=EP_GROUP_CANCELLED;
    if (ok) *out=g->peers;ReleaseSRWLockShared(&epGroupLock);return ok;
}
int ep_roster_group_publish(HfMod* owner,uint64_t id,int32_t priority)
{
    int ok=1;
    AcquireSRWLockExclusive(&epGroupLock); EpRosterGroup* g=EpGroupFind(owner,id);
    if (!g || g->state!=EP_GROUP_PREPARED) { ReleaseSRWLockExclusive(&epGroupLock); return 0; }
    g->state=EP_GROUP_PUBLISHING; ReleaseSRWLockExclusive(&epGroupLock);
    if (g->peer_count) {
        uint64_t ids[2*EP_CLIENT_PEER_FAMILY_COUNT];
        for (unsigned i=0;i<g->peer_count;i++) {ids[i]=g->peer_bodies.code[i].handle;ids[g->peer_count+i]=g->peer_gates[i].handle;}
        ok=ep_session_code_retain_set(owner,ids,2*g->peer_count);
        AcquireSRWLockExclusive(&epGroupLock);g->peer_retained=ok;ReleaseSRWLockExclusive(&epGroupLock);
    }
    for (unsigned i=0;ok && i<EP_ROSTER_ENTRIES;i++) {
        int published=ep_session_code_publish(owner,g->code[i],g->targets[i],priority);
        EpSessionCodeInfo info;
        AcquireSRWLockExclusive(&epGroupLock);
        if (ep_session_code_info(owner,g->code[i],&info) && info.pinned) g->attempts++;
        ReleaseSRWLockExclusive(&epGroupLock);
        if (!published) { ok=0; break; }
    }
    for (unsigned i=0;ok && i<g->peer_count;i++) {
        const int published=ep_session_code_publish(owner,g->peer_gates[i].handle,g->calls[0].game+EpPeerRvas[i],priority);
        EpSessionCodeInfo info={};AcquireSRWLockExclusive(&epGroupLock);
        if (ep_session_code_info(owner,g->peer_gates[i].handle,&info) && info.pinned) g->attempts++;
        ReleaseSRWLockExclusive(&epGroupLock);
        if (!published || !InterlockedCompareExchangePointer((void* volatile*)g->peer_calls[i].next_pointer,NULL,NULL)) ok=0;
    }
    AcquireSRWLockExclusive(&epGroupLock); g->state=ok ? EP_GROUP_READY : EP_GROUP_FAILED;
    ReleaseSRWLockExclusive(&epGroupLock); return ok;
}
static int TransitionNextReady(EpRosterGroup*);
typedef struct EpOwnedCommit {EpRosterGroup* group;EpPropertyCommitGuard guard;void* lease;int committed,ended;} EpOwnedCommit;
static int EpValidateUnderOwner(void* context,const EpNativeRosterView* view)
{
    (void)view;EpOwnedCommit* c=(EpOwnedCommit*)context;
    c->committed=c->guard.validate(c->guard.context,c->lease)!=0;return 1;
}
static int EpCommitUnderOwner(void* context,const EpNativeRosterView* view)
{
    EpOwnedCommit* c=(EpOwnedCommit*)context;EpRosterGroup* g=c->group;
    if (view->game!=g->calls[0].game || view->roster!=g->calls[0].roster || view->storage!=g->calls[0].storage) return 0;
    /* Validation faults unwind to an inherited scope, so the outer lease is
     * still held when end receives committed=0. */
    if (ep_roster_owner_call(g->owner,g->storage_owner,1,EpValidateUnderOwner,c)!=EP_OWNER_OK) c->committed=0;
    if (c->committed) InterlockedExchange(&g->active,1);
    c->ended=1;c->guard.end(c->guard.context,c->lease,c->committed);return 1;
}
int ep_roster_group_commit(HfMod* owner,uint64_t id,const EpPropertyCommitGuard* guard)
{
    EpPropertyCommitGuard copy; void* lease=NULL; int entered,ok=0;
    if (!guard || !guard->begin || !guard->validate || !guard->end) return 0;
    copy=*guard;
    AcquireSRWLockExclusive(&epGroupLock); EpRosterGroup* g=EpGroupFind(owner,id);
    if (!g || g->state!=EP_GROUP_READY || (g->storage_owner && (ep_roster_owner_in_scope() || !TransitionNextReady(g)))) { ReleaseSRWLockExclusive(&epGroupLock); return 0; }
    g->state=EP_GROUP_COMMITTING; ReleaseSRWLockExclusive(&epGroupLock);
    entered=copy.begin(copy.context,&lease);
    if (g->storage_owner) {
        EpOwnedCommit c={g,copy,lease,0,0};
        if (entered && lease) ok=ep_roster_owner_call(owner,g->storage_owner,1,EpCommitUnderOwner,&c)==EP_OWNER_OK && c.committed;
        if (entered && !c.ended) copy.end(copy.context,lease,0);
        AcquireSRWLockExclusive(&epGroupLock);
        /* If end unexpectedly faults after activation, never permit cancel or
         * retry as an inactive group. The quarantined owner blocks body calls. */
        g->state=InterlockedCompareExchange(&g->active,0,0) ? EP_GROUP_ACTIVE : EP_GROUP_READY;
        ReleaseSRWLockExclusive(&epGroupLock);return ok;
    }
    if (entered && lease) ok=copy.validate(copy.context,lease)!=0;
    AcquireSRWLockExclusive(&epGroupLock);
    if (ok) InterlockedExchange(&g->active,1);
    ReleaseSRWLockExclusive(&epGroupLock);
    if (entered) copy.end(copy.context,lease,ok);
    AcquireSRWLockExclusive(&epGroupLock); g->state=ok ? EP_GROUP_ACTIVE : EP_GROUP_READY;
    ReleaseSRWLockExclusive(&epGroupLock);
    return ok;
}
int ep_roster_group_cancel(HfMod* owner,uint64_t id)
{
    int ok=0; AcquireSRWLockExclusive(&epGroupLock); EpRosterGroup* g=EpGroupFind(owner,id);
    if (g && (g->state==EP_GROUP_PREPARED || g->state==EP_GROUP_READY || g->state==EP_GROUP_FAILED || g->state==EP_GROUP_CANCELLED)) ok=EpGroupCancel(g);
    ReleaseSRWLockExclusive(&epGroupLock); return ok;
}
static EpRosterGroup* TransitionFind(HfMod* mod,const EpRosterGroupTransition* token)
{
    EpRosterGroup* g=token ? EpGroupFind(mod,token->group) : NULL;
    return g && token->sequence && g->transition==token->sequence && g->storage_owner==token->storage_owner && g->state==EP_GROUP_COMMITTING ? g : NULL;
}
static int TransitionNextReady(EpRosterGroup* g)
{
    for (unsigned i=0;i<EP_ROSTER_ENTRIES;i++) {
        EpSessionCodeInfo code;
        if (!ep_session_code_info(g->owner,g->code[i],&code) || !code.pinned || !g->calls[i].next_pointer ||
            !InterlockedCompareExchangePointer((void* volatile*)g->calls[i].next_pointer,NULL,NULL)) return 0;
    }
    if (g->peers.client) {
        if (g->peer_count!=EP_CLIENT_PEER_FAMILY_COUNT || !g->peer_retained) return 0;
        for (unsigned i=0;i<g->peer_count;i++) {
            EpSessionCodeInfo gate={},body={};
            if (!ep_session_code_info(g->owner,g->peer_gates[i].handle,&gate) || !gate.pinned || gate.state!=EP_CODE_PUBLISHED ||
                !ep_session_code_info(g->owner,g->peer_bodies.code[i].handle,&body) || !body.pinned ||
                !g->peer_calls[i].next_pointer || !InterlockedCompareExchangePointer((void* volatile*)g->peer_calls[i].next_pointer,NULL,NULL)) return 0;
        }
    }
    return 1;
}
int ep_roster_group_transition_claim(HfMod* mod,uint64_t id,uint64_t owner,uint64_t game,EpRosterGroupTransition* out)
{
    if (!out) return 0;memset(out,0,sizeof(*out));if (!owner || ep_roster_owner_in_scope()) return 0;
    AcquireSRWLockExclusive(&epGroupLock);EpRosterGroup* g=EpGroupFind(mod,id);
    int ok=g && g->state==EP_GROUP_READY && g->storage_owner==owner && g->calls[0].game==game &&
        !g->active && !g->switching && !g->transition && epTransitionSequence!=UINT64_MAX && TransitionNextReady(g);
    if (ok) {
        g->transition=++epTransitionSequence;g->state=EP_GROUP_COMMITTING;
        out->group=id;out->sequence=g->transition;out->storage_owner=owner;
    }
    ReleaseSRWLockExclusive(&epGroupLock);return ok;
}
int ep_roster_group_transition_enter(HfMod* mod,const EpRosterGroupTransition* token)
{
    if (!token || ep_roster_owner_native_status(mod,token->storage_owner)!=EP_OWNER_OK) return 0;
    AcquireSRWLockExclusive(&epGroupLock);EpRosterGroup* g=TransitionFind(mod,token);
    int ok=g && !g->active && !g->switching && TransitionNextReady(g);
    if (ok) InterlockedExchange(&g->switching,1);
    ReleaseSRWLockExclusive(&epGroupLock);return ok;
}
int ep_roster_group_transition_activate(HfMod* mod,const EpRosterGroupTransition* token)
{
    if (!token || ep_roster_owner_native_status(mod,token->storage_owner)!=EP_OWNER_OK) return 0;
    AcquireSRWLockExclusive(&epGroupLock);EpRosterGroup* g=TransitionFind(mod,token);
    int ok=g && g->switching && !g->active;
    if (ok) InterlockedExchange(&g->active,1);
    ReleaseSRWLockExclusive(&epGroupLock);return ok;
}
int ep_roster_group_transition_finish(HfMod* mod,const EpRosterGroupTransition* token,uint32_t outcome)
{
    if (!token || outcome>EP_ROSTER_TRANSITION_UNSAFE) return 0;
    AcquireSRWLockExclusive(&epGroupLock);EpRosterGroup* g=TransitionFind(mod,token);int ok=g!=NULL;
    if (ok && outcome!=EP_ROSTER_TRANSITION_UNSAFE) {
        if (g->switching && ep_roster_owner_native_status(mod,g->storage_owner)!=EP_OWNER_OK) ok=0;
        if ((outcome==EP_ROSTER_TRANSITION_NEW)!=(g->active!=0)) ok=0;
    }
    if (ok) {
        g->state=g->active ? EP_GROUP_ACTIVE : outcome==EP_ROSTER_TRANSITION_UNSAFE ? EP_GROUP_FAILED : EP_GROUP_READY;
        InterlockedExchange(&g->switching,outcome==EP_ROSTER_TRANSITION_UNSAFE ? 1 : 0);g->transition=0;
    }
    ReleaseSRWLockExclusive(&epGroupLock);return ok;
}
