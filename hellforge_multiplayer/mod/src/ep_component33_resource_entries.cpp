#include "ep_component33_resource_entries.h"
#include <windows.h>
#include <string.h>
struct EntryGroup;
struct EntryContext { EntryGroup* group;uint32_t kind; };
struct EntryGroup {
    HfMod* mod;HfApi api;EpC33ResourceEntryBindings bindings;
    EpC33ResourceScopeView view;EpC33ResourceEntriesInfo info;
    EntryContext contexts[EP_C33_RESOURCE_ENTRY_COUNT],update,resets[2];volatile LONG ready;
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
struct ResetInvocation { EntryGroup* group;uint64_t entity;bool reentry;EpC33ResourceProviderResult result; };
static int ResetBody(void* context,const EpNativeRosterView*)
{
    auto* c=(ResetInvocation*)context;auto* g=c->group;c->result.call.executed=1;
    ((void(*)(uint64_t,uint64_t))(uintptr_t)g->info.reset_body.base)(g->view.component,c->entity);
    int rc=ep_c33_resource_reset_idle(&g->view.resources,(void*)(uintptr_t)g->view.resources.address,ep_c33_resource_bytes(g->view.resources.capacity));
    if (rc!=EP_RESOURCE_OK) c->result.call.status=EP_C33_CALL_RESOURCE_STATE;
    return rc==EP_RESOURCE_OK;
}
static int ResetInvoke(void* context,const EpNativeRosterView* owner)
{
    auto* c=(ResetInvocation*)context;auto* g=c->group;
    if (c->reentry) { c->result.call.status=EP_C33_CALL_REENTRANT;return 0; }
    if (owner->game!=g->view.game) { c->result.call.status=EP_C33_CALL_STORAGE;return 0; }
    if (ep_c33_resource_validate(&g->view.resources,(const void*)(uintptr_t)g->view.resources.address,
        ep_c33_resource_bytes(g->view.resources.capacity))!=EP_RESOURCE_OK) {
        c->result.call.status=EP_C33_CALL_RESOURCE_STATE;return 0;
    }
    c->result.call.owner_result=ep_roster_owner_call(g->mod,g->bindings.roster_owner,1,ResetBody,c);
    return c->result.call.owner_result==EP_OWNER_OK;
}
static void ResetDispatch(EntryContext* entry,uint64_t entity)
{
    auto* g=entry->group;auto* prior=updating;
    ResetInvocation c={g,entity,prior!=nullptr || ep_component33_resource_scope_ready(g->mod,g->bindings.roster_owner),{}};
    updating=g;
    auto result=InterlockedCompareExchange(&g->ready,0,0)==1 ?
        ep_roster_owner_call(g->mod,g->bindings.roster_owner,0,ResetInvoke,&c) : EP_OWNER_UNAVAILABLE;
    updating=prior;
    if (result!=EP_OWNER_OK) Reject(g,EP_COMPONENT33_RESET,&c.result,result);
}
static void ResetImage(EntryContext* c,bool entity_in_rcx,uint8_t out[48])
{
    memset(out,0x90,32);memset(out+32,0,16);
    // 51ADE0 forwards RCX; 664210 already receives entity in RDX.
    if (entity_in_rcx) { out[0]=0x48;out[1]=0x89;out[2]=0xca; }
    out[3]=0x48;out[4]=0xb9;uintptr_t value=(uintptr_t)c;memcpy(out+5,&value,8);
    out[13]=0x48;out[14]=0xb8;value=(uintptr_t)ResetDispatch;memcpy(out+15,&value,8);
    out[23]=0xff;out[24]=0xe0;out[32]=1;
    const uint32_t row[]={0,32,32};memcpy(out+36,row,sizeof(row));
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
    EpSessionCodeInfo* updates[]={&g->info.reset_body,&g->info.reset_entries[1],&g->info.reset_entries[0],&g->info.update_body,&g->info.update_entry};
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
static int Prepare(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* input,const EpC33UpdateEntryConfig* config,
    const EpC33LifecycleEntryConfig* lifecycle,EpC33ResourceEntriesInfo* out)
{
    if (!out) return 0;EpC33ResourceEntryBindings b={};if (input) b=*input;
    EpC33UpdateEntryConfig update={};if (config) update=*config;
    EpC33LifecycleEntryConfig reset={};if (lifecycle) reset=*lifecycle;memset(out,0,sizeof(*out));
    if (!mod || !input || !b.storage || !b.roster_owner || !b.reject || ep_roster_owner_in_scope() || !api || api->version<13 ||
        api->size<offsetof(HfApi,read_code)+sizeof(api->read_code) || !api->read || !api->read_code || !api->hook_ex || !api->build_id) return 0;
    const char* build=api->build_id();if (!build || strcmp(build,"25480438")) return 0;
    BindingCapture captured={mod,b.storage,b.roster_owner,{},0};
    if (ep_roster_owner_call(mod,b.roster_owner,0,Capture,&captured)!=EP_OWNER_OK || !captured.ready) return 0;
    EpC33StorageInfo storage={};
    if (lifecycle && (!ep_component33_storage_info(mod,b.storage,&storage) || storage.state!=EP_C33_STORAGE_RETAINED)) return 0;
    const uint32_t kinds[]={EP_C33_ACQUIRE,EP_C33_DEFER,EP_C33_RELEASE,EP_C33_RESOURCE_DRAIN};
    const uint32_t rvas[]={0x6656c0,0x665940,0x6659e0,0};
    AcquireSRWLockExclusive(&entriesLock);EntryGroup* group=nullptr;bool duplicate=false;
    for (auto& g:entryGroups) if (g.info.handle && g.mod==mod && g.bindings.storage==b.storage) duplicate=true;
    if (!duplicate && entrySequence!=UINT64_MAX) for (auto& g:entryGroups) if (!g.info.handle) {
        group=&g;g.mod=mod;g.bindings=b;g.view=captured.view;g.info.handle=++entrySequence;g.info.state=EP_C33_ENTRIES_PREPARING;
        g.api.version=api->version;g.api.size=sizeof(g.api);g.api.build_id=api->build_id;g.api.read=api->read;g.api.read_code=api->read_code;g.api.hook_ex=api->hook_ex;
        for (unsigned i=0;i<EP_C33_RESOURCE_ENTRY_COUNT;i++) { g.contexts[i]={&g,kinds[i]};g.info.targets[i]=rvas[i] ? g.view.game+rvas[i] : 0; }
        g.update={&g,EP_C33_UPDATE};if (config) g.info.update_target=g.view.game+0x664520;
        if (lifecycle) for (unsigned i=0;i<2;i++) {
            g.resets[i]={&g,EP_COMPONENT33_RESET};g.info.reset_targets[i]=g.view.game+(i ? 0x664210 : 0x51ade0);
        }
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
    if (ok && lifecycle) {
        for (unsigned i=0;i<2;i++) {
            EpSessionCodeInfo entry={};ok=ep_session_code_reserve(&group->api,mod,reset.reset_entries[i],48,&entry);
            AcquireSRWLockExclusive(&entriesLock);group->info.reset_entries[i]=entry;ReleaseSRWLockExclusive(&entriesLock);
            if (!ok) break;
            uint8_t image[48];ResetImage(&group->resets[i],i==0,image);
            ok=ep_session_code_seal(mod,entry.handle,image,sizeof(image),36);
            ep_session_code_info(mod,entry.handle,&entry);
            AcquireSRWLockExclusive(&entriesLock);group->info.reset_entries[i]=entry;ReleaseSRWLockExclusive(&entriesLock);
            if (!ok) break;
        }
        if (ok) {
            EpSessionCodeInfo body={};ok=ep_session_code_reserve(&group->api,mod,reset.reset_body,ep_component33_image_bytes(EP_COMPONENT33_RESET),&body);
            AcquireSRWLockExclusive(&entriesLock);group->info.reset_body=body;ReleaseSRWLockExclusive(&entriesLock);
            if (ok) {
                EpComponent33Addresses a={group->view.game,body.base,group->view.component,group->view.storage,storage.family.code[0].base,group->info.update_entry.base+32};
                EpComponent33Image image={};ok=ep_component33_image_build(EP_COMPONENT33_RESET,&a,&image)==EP_PROPERTY_OK;
                if (ok) ok=ep_session_code_seal_table(mod,body.handle,image.data,image.bytes,image.table_offset,image.function_count);
                ep_session_code_info(mod,body.handle,&body);
                AcquireSRWLockExclusive(&entriesLock);group->info.reset_body=body;ReleaseSRWLockExclusive(&entriesLock);
            }
        }
    }
    AcquireSRWLockExclusive(&entriesLock);
    if (ok) group->info.state=EP_C33_ENTRIES_PREPARED;else Cancel(group);
    if (group->info.handle) *out=group->info;ReleaseSRWLockExclusive(&entriesLock);return ok;
}
int ep_component33_resource_entries_prepare(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* b,EpC33ResourceEntriesInfo* out)
{ return Prepare(api,mod,b,nullptr,nullptr,out); }
int ep_component33_resource_entries_prepare_update(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* b,const EpC33UpdateEntryConfig* config,EpC33ResourceEntriesInfo* out)
{
    if (!config) { if (out) memset(out,0,sizeof(*out));return 0; }
    return Prepare(api,mod,b,config,nullptr,out);
}
int ep_component33_resource_entries_prepare_lifecycle(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* b,const EpC33LifecycleEntryConfig* config,EpC33ResourceEntriesInfo* out)
{
    if (!config) { if (out) memset(out,0,sizeof(*out));return 0; }
    return Prepare(api,mod,b,&config->update,config,out);
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
        uint64_t handles[EP_C33_RESOURCE_ENTRY_COUNT+5];unsigned count=EP_C33_RESOURCE_ENTRY_COUNT;
        for (unsigned i=0;i<EP_C33_RESOURCE_ENTRY_COUNT;i++) handles[i]=g->info.code[i].handle;
        if (g->info.update_target) { handles[count++]=g->info.update_entry.handle;handles[count++]=g->info.update_body.handle; }
        if (g->info.reset_targets[0]) {
            handles[count++]=g->info.reset_entries[0].handle;handles[count++]=g->info.reset_entries[1].handle;handles[count++]=g->info.reset_body.handle;
        }
        if (ep_session_code_retain_set(mod,handles,count)) {
            g->info.state=EP_C33_ENTRIES_RETAINED;
            for (auto& c:g->info.code) ep_session_code_info(mod,c.handle,&c);
            if (g->info.update_target) {
                ep_session_code_info(mod,g->info.update_entry.handle,&g->info.update_entry);
                ep_session_code_info(mod,g->info.update_body.handle,&g->info.update_body);
            }
            if (g->info.reset_targets[0]) {
                for (auto& c:g->info.reset_entries) ep_session_code_info(mod,c.handle,&c);
                ep_session_code_info(mod,g->info.reset_body.handle,&g->info.reset_body);
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
