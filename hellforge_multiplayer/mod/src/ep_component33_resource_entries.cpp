#include "ep_component33_resource_entries.h"
#include <windows.h>
#include <string.h>
struct EntryGroup;
struct EntryContext { EntryGroup* group;uint32_t kind; };
struct EntryGroup {
    HfMod* mod;HfApi api;EpC33ResourceEntryBindings bindings;
    EpC33ResourceScopeView view;EpC33ResourceEntriesInfo info;
    EntryContext contexts[EP_C33_RESOURCE_ENTRY_COUNT],update;volatile LONG ready;
};
static EntryGroup entryGroups[EP_C33_RESOURCE_ENTRY_GROUPS];
static SRWLOCK entriesLock=SRWLOCK_INIT;static uint64_t entrySequence;
static EntryGroup* Find(HfMod* mod,uint64_t id)
{
    if (mod && id) for (auto& g:entryGroups) if (g.mod==mod && g.info.handle==id) return &g;
    return nullptr;
}
struct Invocation { EntryContext* entry;uint64_t component,value,flag;EpC33ResourceProviderResult result; };
static thread_local EntryGroup* updating;
static void Reject(EntryGroup* g,uint32_t kind,EpC33ResourceProviderResult* result,EpRosterOwnerResult owner)
{
    if (!result->call.status) result->call.status=EP_C33_CALL_OWNER;
    if (!result->call.owner_result) result->call.owner_result=owner;
    g->bindings.reject(g->bindings.reject_context,kind,result);
    RaiseException(EP_C33_RESOURCE_ENTRY_ABORT,EXCEPTION_NONCONTINUABLE,0,nullptr);
    __builtin_unreachable();
}
static int Invoke(void* context,const EpNativeRosterView* owner)
{
    auto* call=(Invocation*)context;auto* c=call->entry;auto* g=c->group;
    if (owner->game!=g->view.game || call->component!=g->view.component) {
        call->result.call.status=EP_C33_CALL_STORAGE;return 0;
    }
    int rc;
    if (c->kind==EP_C33_ACQUIRE) rc=ep_component33_resource_acquire_native_call(&g->api,g->mod,g->bindings.storage,g->bindings.roster_owner,call->value,&call->result);
    else if (c->kind==EP_C33_DEFER) rc=ep_component33_resource_defer_native_call(&g->api,g->mod,g->bindings.storage,g->bindings.roster_owner,call->value,&call->result);
    else if (c->kind==EP_C33_RESOURCE_DRAIN) rc=ep_component33_resource_drain_native_call(&g->api,g->mod,g->bindings.storage,g->bindings.roster_owner,&call->result);
    else rc=ep_component33_resource_release_native_call(&g->api,g->mod,g->bindings.storage,g->bindings.roster_owner,
        (uint32_t)call->value,(uint8_t)call->flag!=0,&call->result);
    return rc==EP_C33_CALL_OK;
}
static void Dispatch(EntryContext* entry,uint64_t component,uint64_t value,uint64_t flag)
{
    auto* g=entry->group;Invocation call={entry,component,value,flag,{}};
    bool scoped=entry->kind!=EP_C33_RESOURCE_DRAIN || ep_roster_owner_native_status(g->mod,g->bindings.roster_owner)==EP_OWNER_OK;
    auto result=InterlockedCompareExchange(&g->ready,0,0)==1 && scoped ?
        ep_roster_owner_call(g->mod,g->bindings.roster_owner,0,Invoke,&call) : EP_OWNER_UNAVAILABLE;
    if (result==EP_OWNER_OK) return;
    Reject(g,entry->kind,&call.result,result);
}
struct UpdateInvocation { EntryGroup* group;uint64_t component;uint32_t delta;bool reentry;EpC33ResourceProviderResult result; };
static int UpdateBody(void* context,const EpNativeRosterView*)
{
    auto* c=(UpdateInvocation*)context;float delta;memcpy(&delta,&c->delta,sizeof(delta));
    c->result.call.executed=1;
    ((void(*)(uint64_t,float))(uintptr_t)c->group->info.update_body.base)(c->component,delta);
    return 1;
}
static int UpdateInvoke(void* context,const EpNativeRosterView* owner)
{
    auto* c=(UpdateInvocation*)context;auto* g=c->group;
    if (c->reentry) { c->result.call.status=EP_C33_CALL_REENTRANT;return 0; }
    if (owner->game!=g->view.game || c->component!=g->view.component) { c->result.call.status=EP_C33_CALL_STORAGE;return 0; }
    // A nested writing call records exhaustion/fault on this same owner even
    // when no write was possible. Only the outer call commits its revision.
    c->result.call.owner_result=ep_roster_owner_call(g->mod,g->bindings.roster_owner,1,UpdateBody,c);
    return c->result.call.owner_result==EP_OWNER_OK;
}
static void UpdateDispatch(EntryContext* entry,uint64_t component,uint32_t delta)
{
    auto* g=entry->group;auto* prior=updating;
    UpdateInvocation c={g,component,delta,prior!=nullptr || ep_component33_resource_scope_ready(g->mod,g->bindings.roster_owner),{}};
    // ep_roster_owner_call contains SEH before returning, including any fault
    // of the routed body or a nested resource entry. Clear TLS on that return,
    // before a rejection policy can unwind out of this dispatcher itself.
    updating=g;
    auto result=InterlockedCompareExchange(&g->ready,0,0)==1 ?
        ep_roster_owner_call(g->mod,g->bindings.roster_owner,0,UpdateInvoke,&c) : EP_OWNER_UNAVAILABLE;
    updating=prior;
    if (result!=EP_OWNER_OK) Reject(g,EP_C33_UPDATE,&c.result,result);
}
static void UpdateGuardReject()
{
    RaiseException(EP_C33_RESOURCE_ENTRY_ABORT,EXCEPTION_NONCONTINUABLE,0,nullptr);
    __builtin_unreachable();
}
static void UpdateImage(EntryContext* c,uint8_t out[80])
{
    // MOVD R8D,XMM1; MOV RDX,RCX; MOV RCX,context; MOV RAX,dispatch; JMP RAX.
    // Transfer bits without arithmetic, including signed zero/NaN payloads.
    const uint8_t prefix[]={0x66,0x41,0x0f,0x7e,0xc8,0x48,0x89,0xca,0x48,0xb9};
    memset(out,0x90,48);memset(out+48,0,32);memcpy(out,prefix,sizeof(prefix));
    uintptr_t value=(uintptr_t)c;memcpy(out+10,&value,8);out[18]=0x48;out[19]=0xb8;
    value=(uintptr_t)UpdateDispatch;memcpy(out+20,&value,8);out[28]=0xff;out[29]=0xe0;
    out[32]=0x48;out[33]=0xb8;value=(uintptr_t)UpdateGuardReject;memcpy(out+34,&value,8);out[42]=0xff;out[43]=0xe0;
    out[48]=out[52]=1;const uint32_t table[]={0,32,48,32,44,52};memcpy(out+56,table,sizeof(table));
}
static void Image(EntryContext* c,uint8_t out[48])
{
    // Preserve RDX and R8 before shifting them into the dispatch arguments.
    // No stack change, shadow-space write or nonvolatile register use.
    const uint8_t prefix[]={0x4d,0x89,0xc1,0x49,0x89,0xd0,0x48,0x89,0xca,0x48,0xb9};
    memset(out,0,48);memcpy(out,prefix,sizeof(prefix));uintptr_t context=(uintptr_t)c,target=(uintptr_t)Dispatch;
    memcpy(out+11,&context,8);out[19]=0x48;out[20]=0xb8;memcpy(out+21,&target,8);
    out[29]=0xff;out[30]=0xe0;out[31]=0x90;out[32]=1;
    const uint32_t row[]={0,32,32};memcpy(out+36,row,sizeof(row));
}
static int Cancel(EntryGroup* g)
{
    int ok=1;
    EpSessionCodeInfo* updates[]={&g->info.update_body,&g->info.update_entry};
    for (auto* c:updates) if (c->handle) {
        if (ep_session_code_discard(g->mod,c->handle)) memset(c,0,sizeof(*c));else ok=0;
    }
    for (unsigned i=EP_C33_RESOURCE_ENTRY_COUNT;i--;) if (g->info.code[i].handle) {
        if (ep_session_code_discard(g->mod,g->info.code[i].handle)) memset(&g->info.code[i],0,sizeof(g->info.code[i]));else ok=0;
    }
    if (ok) memset(g,0,sizeof(*g));else g->info.state=EP_C33_ENTRIES_CLEANUP_REQUIRED;
    return ok;
}
struct BindingCapture { HfMod* mod;uint64_t storage,owner;EpC33ResourceScopeView view;int ready; };
static int Capture(void* context,const EpNativeRosterView* view)
{
    auto* c=(BindingCapture*)context;
    c->ready=ep_component33_storage_resource_scope(c->mod,c->storage,c->owner,view->game,&c->view);return 1;
}
static int Prepare(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* input,const EpC33UpdateEntryConfig* config,EpC33ResourceEntriesInfo* out)
{
    if (!out) return 0;EpC33ResourceEntryBindings b={};if (input) b=*input;
    EpC33UpdateEntryConfig update={};if (config) update=*config;memset(out,0,sizeof(*out));
    if (!mod || !input || !b.storage || !b.roster_owner || !b.reject || ep_roster_owner_in_scope() || !api || api->version<13 ||
        api->size<offsetof(HfApi,read_code)+sizeof(api->read_code) || !api->read || !api->read_code || !api->hook_ex || !api->build_id) return 0;
    const char* build=api->build_id();if (!build || strcmp(build,"25480438")) return 0;
    BindingCapture captured={mod,b.storage,b.roster_owner,{},0};
    if (ep_roster_owner_call(mod,b.roster_owner,0,Capture,&captured)!=EP_OWNER_OK || !captured.ready) return 0;
    const uint32_t kinds[]={EP_C33_ACQUIRE,EP_C33_DEFER,EP_C33_RELEASE,EP_C33_RESOURCE_DRAIN};
    const uint32_t rvas[]={0x6656c0,0x665940,0x6659e0,0};
    AcquireSRWLockExclusive(&entriesLock);EntryGroup* group=nullptr;bool duplicate=false;
    for (auto& g:entryGroups) if (g.info.handle && g.mod==mod && g.bindings.storage==b.storage) duplicate=true;
    if (!duplicate && entrySequence!=UINT64_MAX) for (auto& g:entryGroups) if (!g.info.handle) {
        group=&g;g.mod=mod;g.bindings=b;g.view=captured.view;g.info.handle=++entrySequence;g.info.state=EP_C33_ENTRIES_PREPARING;
        g.api.version=api->version;g.api.size=sizeof(g.api);g.api.build_id=api->build_id;g.api.read=api->read;g.api.read_code=api->read_code;g.api.hook_ex=api->hook_ex;
        for (unsigned i=0;i<EP_C33_RESOURCE_ENTRY_COUNT;i++) { g.contexts[i]={&g,kinds[i]};g.info.targets[i]=rvas[i] ? g.view.game+rvas[i] : 0; }
        g.update={&g,EP_C33_UPDATE};if (config) g.info.update_target=g.view.game+0x664520;
        break;
    }
    ReleaseSRWLockExclusive(&entriesLock);if (!group) return 0;
    int ok=1;
    for (unsigned i=0;i<EP_C33_RESOURCE_ENTRY_COUNT;i++) {
        EpSessionCodeInfo code={};
        if (!ep_session_code_reserve(&group->api,mod,b.desired_code[i],48,&code)) { ok=0;break; }
        AcquireSRWLockExclusive(&entriesLock);group->info.code[i]=code;ReleaseSRWLockExclusive(&entriesLock);
        uint8_t image[48];Image(&group->contexts[i],image);
        if (!ep_session_code_seal(mod,code.handle,image,sizeof(image),36)) { ok=0;break; }
        ep_session_code_info(mod,code.handle,&code);
        AcquireSRWLockExclusive(&entriesLock);group->info.code[i]=code;ReleaseSRWLockExclusive(&entriesLock);
    }
    if (ok && config) {
        EpSessionCodeInfo entry={},body={};
        ok=ep_session_code_reserve(&group->api,mod,update.desired_entry,80,&entry);
        if (ok) ok=ep_session_code_reserve(&group->api,mod,update.desired_body,ep_component33_consumer_bytes(EP_C33_UPDATE),&body);
        AcquireSRWLockExclusive(&entriesLock);group->info.update_entry=entry;group->info.update_body=body;ReleaseSRWLockExclusive(&entriesLock);
        if (ok) {
            EpC33ConsumerAddresses a={group->view.game,body.base,group->view.component,group->view.storage,group->info.code[2].base,entry.base+32};
            EpComponent33Image image={};
            ok=ep_component33_update_drain_build(&a,group->info.code[3].base,&image)==EP_PROPERTY_OK;
            if (ok) ok=ep_session_code_seal_table(mod,body.handle,image.data,image.bytes,image.table_offset,image.function_count);
            uint8_t bridge[80];UpdateImage(&group->update,bridge);
            if (ok) ok=ep_session_code_seal_table(mod,entry.handle,bridge,sizeof(bridge),56,2);
            ep_session_code_info(mod,entry.handle,&entry);ep_session_code_info(mod,body.handle,&body);
            AcquireSRWLockExclusive(&entriesLock);group->info.update_entry=entry;group->info.update_body=body;ReleaseSRWLockExclusive(&entriesLock);
        }
    }
    AcquireSRWLockExclusive(&entriesLock);
    if (ok) group->info.state=EP_C33_ENTRIES_PREPARED;else Cancel(group);
    if (group->info.handle) *out=group->info;ReleaseSRWLockExclusive(&entriesLock);return ok;
}
int ep_component33_resource_entries_prepare(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* b,EpC33ResourceEntriesInfo* out)
{ return Prepare(api,mod,b,nullptr,out); }
int ep_component33_resource_entries_prepare_update(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* b,const EpC33UpdateEntryConfig* config,EpC33ResourceEntriesInfo* out)
{
    if (!config) { if (out) memset(out,0,sizeof(*out));return 0; }
    return Prepare(api,mod,b,config,out);
}
int ep_component33_resource_entries_info(HfMod* mod,uint64_t id,EpC33ResourceEntriesInfo* out)
{
    if (!out) return 0;memset(out,0,sizeof(*out));if (ep_roster_owner_in_scope()) return 0;
    AcquireSRWLockShared(&entriesLock);auto* g=Find(mod,id);if (g) *out=g->info;ReleaseSRWLockShared(&entriesLock);return g!=nullptr;
}
int ep_component33_resource_entries_retain(HfMod* mod,uint64_t id)
{
    if (ep_roster_owner_in_scope()) return 0;int ok=0;AcquireSRWLockExclusive(&entriesLock);auto* g=Find(mod,id);
    if (g && g->info.state==EP_C33_ENTRIES_PREPARED) {
        uint64_t handles[EP_C33_RESOURCE_ENTRY_COUNT+2];unsigned count=EP_C33_RESOURCE_ENTRY_COUNT;
        for (unsigned i=0;i<EP_C33_RESOURCE_ENTRY_COUNT;i++) handles[i]=g->info.code[i].handle;
        if (g->info.update_target) { handles[count++]=g->info.update_entry.handle;handles[count++]=g->info.update_body.handle; }
        if (ep_session_code_retain_set(mod,handles,count)) {
            g->info.state=EP_C33_ENTRIES_RETAINED;
            for (auto& c:g->info.code) ep_session_code_info(mod,c.handle,&c);
            if (g->info.update_target) {
                ep_session_code_info(mod,g->info.update_entry.handle,&g->info.update_entry);
                ep_session_code_info(mod,g->info.update_body.handle,&g->info.update_body);
            }
            InterlockedExchange(&g->ready,1);ok=1;
        }
    }
    ReleaseSRWLockExclusive(&entriesLock);return ok;
}
int ep_component33_resource_entries_cancel(HfMod* mod,uint64_t id)
{
    if (ep_roster_owner_in_scope()) return 0;int ok=0;AcquireSRWLockExclusive(&entriesLock);auto* g=Find(mod,id);
    if (g && (g->info.state==EP_C33_ENTRIES_PREPARED || g->info.state==EP_C33_ENTRIES_CLEANUP_REQUIRED)) ok=Cancel(g);
    ReleaseSRWLockExclusive(&entriesLock);return ok;
}
