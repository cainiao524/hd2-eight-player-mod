#include "ep_component33_resource_entries.h"
#include <windows.h>
#include <string.h>
struct EntryGroup;
struct EntryContext { EntryGroup* group;uint32_t kind; };
struct EntryGroup {
    HfMod* mod;HfApi api;EpC33ResourceEntryBindings bindings;
    EpC33ResourceScopeView view;EpC33ResourceEntriesInfo info;
    EntryContext contexts[EP_C33_RESOURCE_ENTRY_COUNT];volatile LONG ready;
};
static EntryGroup entryGroups[EP_C33_RESOURCE_ENTRY_GROUPS];
static SRWLOCK entriesLock=SRWLOCK_INIT;static uint64_t entrySequence;
static EntryGroup* Find(HfMod* mod,uint64_t id)
{
    if (mod && id) for (auto& g:entryGroups) if (g.mod==mod && g.info.handle==id) return &g;
    return nullptr;
}
struct Invocation { EntryContext* entry;uint64_t component,value,flag;EpC33ResourceProviderResult result; };
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
    if (!call.result.call.status) call.result.call.status=EP_C33_CALL_OWNER;
    if (!call.result.call.owner_result) call.result.call.owner_result=result;
    g->bindings.reject(g->bindings.reject_context,entry->kind,&call.result);
    // A return from the supplied policy must not resume an interior game frame.
    RaiseException(EP_C33_RESOURCE_ENTRY_ABORT,EXCEPTION_NONCONTINUABLE,0,nullptr);
    __builtin_unreachable();
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
int ep_component33_resource_entries_prepare(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* input,EpC33ResourceEntriesInfo* out)
{
    if (!out) return 0;EpC33ResourceEntryBindings b={};if (input) b=*input;memset(out,0,sizeof(*out));
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
    AcquireSRWLockExclusive(&entriesLock);
    if (ok) group->info.state=EP_C33_ENTRIES_PREPARED;else Cancel(group);
    if (group->info.handle) *out=group->info;ReleaseSRWLockExclusive(&entriesLock);return ok;
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
        uint64_t handles[EP_C33_RESOURCE_ENTRY_COUNT];for (unsigned i=0;i<EP_C33_RESOURCE_ENTRY_COUNT;i++) handles[i]=g->info.code[i].handle;
        if (ep_session_code_retain_set(mod,handles,EP_C33_RESOURCE_ENTRY_COUNT)) {
            g->info.state=EP_C33_ENTRIES_RETAINED;
            for (auto& c:g->info.code) ep_session_code_info(mod,c.handle,&c);
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
