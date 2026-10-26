#include "ep_component33_resource_entries.h"
#include "ep_roster_call.h"
#include <windows.h>
#include <string.h>
struct EntryGroup;
struct EntryContext { EntryGroup* group;uint32_t kind; };
struct CoreContext { EntryGroup* group;uint32_t kind;uintptr_t body; };
struct EntryGroup {
    HfMod* mod;HfApi api;EpC33ResourceEntryBindings bindings;
    EpC33ResourceScopeView view;EpC33ResourceEntriesInfo info;
    EntryContext contexts[EP_C33_RESOURCE_ENTRY_COUNT],update,resets[2],refresh,leave;volatile LONG ready;
    CoreContext core[EP_C33_CORE_ENTRY_COUNT];
    CoreContext callers[EP_C33_CALLER_ENTRY_COUNT];
    CoreContext routes[EP_C33_PUBLISH_ENTRIES];bool routed;volatile LONG active,switching;
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
static thread_local EntryGroup* coreGroup;
static thread_local uint32_t coreKinds;
static thread_local EntryGroup* callerGroup;
static thread_local uint32_t callerKinds;
static thread_local EntryGroup* routeGroup;
static thread_local uint32_t routeKinds;
enum { RouteKindBase=0x10000 };
static EpSessionCodeInfo* RouteCode(EntryGroup* g,unsigned index)
{
    if (index<3) return &g->info.code[index];if (index==3) return &g->info.update_entry;
    if (index<6) return &g->info.reset_entries[index-4];if (index==6) return &g->info.refresh_entry;
    if (index==7) return &g->info.leave_entry;if (index<22) return &g->info.core_entries[index-8];
    return &g->info.caller_entries[index-22];
}
static uint64_t RouteTarget(EntryGroup* g,unsigned index)
{
    if (index<3) return g->info.targets[index];if (index==3) return g->info.update_target;
    if (index<6) return g->info.reset_targets[index-4];if (index==6) return g->info.refresh_target;
    if (index==7) return g->info.leave_target;if (index<22) return g->info.core_targets[index-8];
    return g->info.caller_targets[index-22];
}
extern "C" void EpRosterCallTarget(EpRosterCallFrame*,uintptr_t,unsigned);
extern "C" void EpC33CoreEntry(void);
extern "C" void EpC33CoreDispatch(CoreContext*,EpRosterCallFrame*);
static void RouteDispatch(CoreContext*,EpRosterCallFrame*);
static_assert(sizeof(EpRosterCallFrame)==176 && offsetof(EpRosterCallFrame,xmm)==64 &&
    offsetof(EpRosterCallFrame,entry_stack)==160 && offsetof(EpRosterCallFrame,status)==168,"core bridge layout");
// Same registered frame ABI as the roster bridge; reuse its target invocation
// to forward PROPERTY's stack arguments without interpreting their pointers.
__asm__(
    ".text\n.p2align 4\n.globl EpC33CoreEntry\n.seh_proc EpC33CoreEntry\n"
    "EpC33CoreEntry:\nsubq $216,%rsp\n.seh_stackalloc 216\n.seh_endprologue\n"
    "movq %rax,32(%rsp)\nmovq %rcx,40(%rsp)\nmovq %rdx,48(%rsp)\nmovq %r8,56(%rsp)\n"
    "movq %r9,64(%rsp)\nmovq %r10,72(%rsp)\nmovq %r11,80(%rsp)\nmovq $0,88(%rsp)\n"
    "movdqu %xmm0,96(%rsp)\nmovdqu %xmm1,112(%rsp)\nmovdqu %xmm2,128(%rsp)\n"
    "movdqu %xmm3,144(%rsp)\nmovdqu %xmm4,160(%rsp)\nmovdqu %xmm5,176(%rsp)\n"
    "leaq 216(%rsp),%rax\nmovq %rax,192(%rsp)\nmovq $0,200(%rsp)\n"
    "movq %r10,%rcx\nleaq 32(%rsp),%rdx\ncall EpC33CoreDispatch\n"
    "movdqu 96(%rsp),%xmm0\nmovdqu 112(%rsp),%xmm1\nmovdqu 128(%rsp),%xmm2\n"
    "movdqu 144(%rsp),%xmm3\nmovdqu 160(%rsp),%xmm4\nmovdqu 176(%rsp),%xmm5\n"
    "movq 32(%rsp),%rax\nmovq 40(%rsp),%rcx\nmovq 48(%rsp),%rdx\nmovq 56(%rsp),%r8\n"
    "movq 64(%rsp),%r9\nmovq 72(%rsp),%r10\nmovq 80(%rsp),%r11\naddq $216,%rsp\nret\n.seh_endproc\n");
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
struct RefreshInvocation { EntryGroup* group;uint64_t object;bool reentry;EpC33ResourceProviderResult result; };
static int RefreshBody(void* context,const EpNativeRosterView* owner)
{
    auto* c=(RefreshInvocation*)context;auto* g=c->group;
    if (c->reentry) { c->result.call.status=EP_C33_CALL_REENTRANT;return 0; }
    if (owner->game!=g->view.game) { c->result.call.status=EP_C33_CALL_STORAGE;return 0; }
    c->result.call.executed=1;
    ((void(*)(uint64_t))(uintptr_t)g->info.refresh_body.base)(c->object);return 1;
}
static void RefreshDispatch(EntryContext* entry,uint64_t object)
{
    auto* g=entry->group;auto* prior=updating;
    RefreshInvocation c={g,object,prior!=nullptr || ep_component33_resource_scope_ready(g->mod,g->bindings.roster_owner),{}};
    updating=g;
    // The traversal writes only its stack. Each admitted ACQUIRE marks the
    // shared outer write, so empty/skipped registries do not consume revision.
    auto result=InterlockedCompareExchange(&g->ready,0,0)==1 ?
        ep_roster_owner_call(g->mod,g->bindings.roster_owner,0,RefreshBody,&c) : EP_OWNER_UNAVAILABLE;
    updating=prior;
    if (result!=EP_OWNER_OK) Reject(g,EP_C33_RESOURCE_REFRESH,&c.result,result);
}
struct LeaveInvocation { EntryGroup* group;uint64_t object;uint32_t flags;bool reentry;EpC33ResourceProviderResult result; };
static int LeaveBody(void* context,const EpNativeRosterView*)
{
    auto* c=(LeaveInvocation*)context;auto* g=c->group;
    c->result.call.executed=1;
    ((void(*)(uint64_t,uint32_t))(uintptr_t)g->info.leave_body.base)(c->object,c->flags);return 1;
}
static int LeaveInvoke(void* context,const EpNativeRosterView* owner)
{
    auto* c=(LeaveInvocation*)context;auto* g=c->group;
    if (c->reentry) { c->result.call.status=EP_C33_CALL_REENTRANT;return 0; }
    if (owner->game!=g->view.game) { c->result.call.status=EP_C33_CALL_STORAGE;return 0; }
    // As for UPDATE, exhausted write admission must fault the shared owner
    // even when no raw native instruction has executed yet.
    c->result.call.owner_result=ep_roster_owner_call(g->mod,g->bindings.roster_owner,1,LeaveBody,c);
    return c->result.call.owner_result==EP_OWNER_OK;
}
static void LeaveDispatch(EntryContext* entry,uint64_t object,uint64_t flags,uint64_t)
{
    auto* g=entry->group;auto* prior=updating;
    LeaveInvocation c={g,object,(uint32_t)flags,prior!=nullptr || ep_component33_resource_scope_ready(g->mod,g->bindings.roster_owner),{}};
    updating=g;
    // Other registry arms retain native writes even without a component33
    // match. Protect/mark the complete frame, not just the nested DEFER call.
    auto result=InterlockedCompareExchange(&g->ready,0,0)==1 ?
        ep_roster_owner_call(g->mod,g->bindings.roster_owner,0,LeaveInvoke,&c) : EP_OWNER_UNAVAILABLE;
    updating=prior;
    if (result!=EP_OWNER_OK) Reject(g,EP_C33_RESOURCE_LEAVE,&c.result,result);
}
static void ObjectImage(EntryContext* c,bool entity_in_rcx,void(*dispatch)(EntryContext*,uint64_t),uint8_t out[48])
{
    memset(out,0x90,32);memset(out+32,0,16);
    // 51ADE0 forwards RCX; 664210 already receives entity in RDX.
    if (entity_in_rcx) { out[0]=0x48;out[1]=0x89;out[2]=0xca; }
    out[3]=0x48;out[4]=0xb9;uintptr_t value=(uintptr_t)c;memcpy(out+5,&value,8);
    out[13]=0x48;out[14]=0xb8;value=(uintptr_t)dispatch;memcpy(out+15,&value,8);
    out[23]=0xff;out[24]=0xe0;out[32]=1;
    const uint32_t row[]={0,32,32};memcpy(out+36,row,sizeof(row));
}
struct CoreInvocation { CoreContext* entry;EpRosterCallFrame* frame;bool reentry;EpC33ResourceProviderResult result; };
static int CoreBody(void* context,const EpNativeRosterView*)
{
    auto* c=(CoreInvocation*)context;c->result.call.executed=1;
    EpRosterCallTarget(c->frame,c->entry->body,c->entry->kind==EP_COMPONENT33_PROPERTY ? 2 : 0);return 1;
}
static int CoreInvoke(void* context,const EpNativeRosterView* owner)
{
    auto* c=(CoreInvocation*)context;auto* g=c->entry->group;
    if (c->reentry) { c->result.call.status=EP_C33_CALL_REENTRANT;return 0; }
    if (owner->game!=g->view.game) { c->result.call.status=EP_C33_CALL_STORAGE;return 0; }
    c->result.call.owner_result=ep_roster_owner_call(g->mod,g->bindings.roster_owner,1,CoreBody,c);
    return c->result.call.owner_result==EP_OWNER_OK;
}
struct CallerInvocation { CoreContext* entry;EpRosterCallFrame* frame;uintptr_t next;bool reentry;EpC33ResourceProviderResult result; };
static int CallerBody(void* context,const EpNativeRosterView*)
{
    auto* c=(CallerInvocation*)context;c->result.call.executed=1;
    EpRosterCallTarget(c->frame,c->next,0);return 1;
}
static int CallerInvoke(void* context,const EpNativeRosterView* owner)
{
    auto* c=(CallerInvocation*)context;auto* g=c->entry->group;
    unsigned index=c->entry->kind-EP_C33_CORE_ENTRY_COUNT-1;
    if (c->reentry) { c->result.call.status=EP_C33_CALL_REENTRANT;return 0; }
    if (owner->game!=g->view.game || (index==0 && c->frame->rcx!=g->view.component-0x3ca0) ||
        *(const uint64_t*)(uintptr_t)(g->view.game+0x33267b8)!=g->view.component) {
        c->result.call.status=EP_C33_CALL_STORAGE;return 0;
    }
    const auto& code=g->info.caller_entries[index];
    c->next=(uintptr_t)InterlockedCompareExchangePointer((void* volatile*)code.next_pointer,nullptr,nullptr);
    if (!c->next || c->next==code.base) { c->result.call.status=EP_C33_CALL_OWNER;return 0; }
    c->result.call.owner_result=ep_roster_owner_call(g->mod,g->bindings.roster_owner,1,CallerBody,c);
    return c->result.call.owner_result==EP_OWNER_OK;
}
static void CallerDispatch(CoreContext* entry,EpRosterCallFrame* frame)
{
    auto* g=entry->group;auto* prior=callerGroup;uint32_t saved=callerKinds;
    unsigned index=entry->kind-EP_C33_CORE_ENTRY_COUNT-1;uint32_t bit=1u<<index;
    bool reentry=updating || coreGroup || (prior && prior!=g) || (saved&bit) ||
        ep_component33_resource_scope_ready(g->mod,g->bindings.roster_owner);
    CallerInvocation c={entry,frame,0,reentry,{}};callerGroup=g;callerKinds|=bit;
    // Deliberately leave updating/coreGroup alone: original callers can invoke
    // this group's inner core/lifecycle entries within the existing owner.
    auto result=InterlockedCompareExchange(&g->ready,0,0)==1 ?
        ep_roster_owner_call(g->mod,g->bindings.roster_owner,0,CallerInvoke,&c) : EP_OWNER_UNAVAILABLE;
    callerGroup=prior;callerKinds=saved;frame->status=result;
    if (result!=EP_OWNER_OK) Reject(g,EP_C33_CALLER_REJECT_BASE+index+1,&c.result,result);
}
extern "C" void EpC33CoreDispatch(CoreContext* entry,EpRosterCallFrame* frame)
{
    if (entry->kind>RouteKindBase) { RouteDispatch(entry,frame);return; }
    if (entry->kind>EP_C33_CORE_ENTRY_COUNT) { CallerDispatch(entry,frame);return; }
    auto* g=entry->group;auto* prior=updating;auto* prior_group=coreGroup;uint32_t prior_kinds=coreKinds,bit=1u<<(entry->kind-1);
    bool reentry=(prior && prior!=g) || (prior_group && prior_group!=g) || (prior_kinds&bit) ||
        ep_component33_resource_scope_ready(g->mod,g->bindings.roster_owner);
    CoreInvocation c={entry,frame,reentry,{}};updating=coreGroup=g;coreKinds|=bit;
    auto result=InterlockedCompareExchange(&g->ready,0,0)==1 ?
        ep_roster_owner_call(g->mod,g->bindings.roster_owner,0,CoreInvoke,&c) : EP_OWNER_UNAVAILABLE;
    updating=prior;coreGroup=prior_group;coreKinds=prior_kinds;frame->status=result;
    if (result!=EP_OWNER_OK) Reject(g,EP_C33_CORE_REJECT_BASE+entry->kind,&c.result,result);
}
static void CoreImage(CoreContext* c,uint8_t out[48])
{
    memset(out,0x90,32);memset(out+32,0,16);uintptr_t context=(uintptr_t)c,target=(uintptr_t)EpC33CoreEntry;
    out[0]=0x49;out[1]=0xba;memcpy(out+2,&context,8);out[10]=0x49;out[11]=0xbb;memcpy(out+12,&target,8);
    out[20]=0x41;out[21]=0xff;out[22]=0xe3;out[32]=1;const uint32_t row[]={0,32,32};memcpy(out+36,row,sizeof(row));
}
struct RouteInvocation { CoreContext* entry;EpRosterCallFrame* frame;uintptr_t target;unsigned index;bool reentry;EpC33ResourceProviderResult result; };
static int RouteBody(void* context,const EpNativeRosterView*)
{
    auto* c=(RouteInvocation*)context;c->result.call.executed=1;
    EpRosterCallTarget(c->frame,c->target,c->index==8+EP_COMPONENT33_PROPERTY-1 ? 2 : 0);return 1;
}
static int RouteInvoke(void* context,const EpNativeRosterView* owner)
{
    auto* c=(RouteInvocation*)context;auto* g=c->entry->group;
    if (c->reentry || InterlockedCompareExchange(&g->switching,0,0)) {c->result.call.status=EP_C33_CALL_REENTRANT;return 0;}
    if (owner->game!=g->view.game) {c->result.call.status=EP_C33_CALL_STORAGE;return 0;}
    auto* code=RouteCode(g,c->index);bool active=InterlockedCompareExchange(&g->active,0,0)!=0;
    c->target=active ? code->base+32 : (uintptr_t)InterlockedCompareExchangePointer((void* volatile*)code->next_pointer,nullptr,nullptr);
    if (!c->target || c->target==code->base) {c->result.call.status=EP_C33_CALL_OWNER;return 0;}
    // OLD native code may write even if an inner component arm is skipped.
    // NEW managed entries supply their own write/no-op accounting.
    if (active) return RouteBody(c,owner);
    c->result.call.owner_result=ep_roster_owner_call(g->mod,g->bindings.roster_owner,1,RouteBody,c);
    return c->result.call.owner_result==EP_OWNER_OK;
}
static void RouteDispatch(CoreContext* entry,EpRosterCallFrame* frame)
{
    auto* g=entry->group;unsigned index=entry->kind-RouteKindBase-1;uint32_t bit=1u<<index,saved=routeKinds;auto* prior=routeGroup;
    RouteInvocation c={entry,frame,0,index,(prior && prior!=g) || bool(saved&bit),{}};routeGroup=g;routeKinds|=bit;
    auto result=InterlockedCompareExchange(&g->ready,0,0)==1 ? ep_roster_owner_call(g->mod,g->bindings.roster_owner,0,RouteInvoke,&c) : EP_OWNER_UNAVAILABLE;
    routeGroup=prior;routeKinds=saved;frame->status=result;
    if (result!=EP_OWNER_OK) Reject(g,EP_C33_ROUTE_REJECT_BASE+index+1,&c.result,result);
}
static int SealEntry(EntryGroup* g,unsigned index,const EpSessionCodeInfo& code,const uint8_t* raw,unsigned bytes,unsigned table,unsigned count=1)
{
    if (!g->routed || index>=EP_C33_PUBLISH_ENTRIES) return ep_session_code_seal_table(g->mod,code.handle,raw,bytes,table,count);
    uint8_t image[112]={},prefix[48];CoreImage(&g->routes[index],prefix);memcpy(image,prefix,32);memcpy(image+32,raw,bytes);
    for (unsigned i=0;i<count;i++) {
        uint32_t row[3];memcpy(row,raw+table+i*12,12);row[0]=i ? row[0]+32 : 0;row[1]+=32;row[2]+=32;
        memcpy(image+32+table+i*12,row,12);
    }
    return ep_session_code_seal_table(g->mod,code.handle,image,bytes+32,table+32,count);
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
static void ArgumentImage(EntryContext* c,void(*dispatch)(EntryContext*,uint64_t,uint64_t,uint64_t),uint8_t out[48])
{
    // Preserve RDX and R8 before shifting them into the dispatch arguments.
    // No stack change, shadow-space write or nonvolatile register use.
    const uint8_t prefix[]={0x4d,0x89,0xc1,0x49,0x89,0xd0,0x48,0x89,0xca,0x48,0xb9};
    memset(out,0,48);memcpy(out,prefix,sizeof(prefix));uintptr_t context=(uintptr_t)c,target=(uintptr_t)dispatch;
    memcpy(out+11,&context,8);out[19]=0x48;out[20]=0xb8;memcpy(out+21,&target,8);
    out[29]=0xff;out[30]=0xe0;out[31]=0x90;out[32]=1;
    const uint32_t row[]={0,32,32};memcpy(out+36,row,sizeof(row));
}
static void Image(EntryContext* c,uint8_t out[48]) { ArgumentImage(c,Dispatch,out); }
static int Cancel(EntryGroup* g)
{
    int ok=1;
    for (unsigned i=EP_C33_CALLER_ENTRY_COUNT;i--;) if (g->info.caller_entries[i].handle) {
        auto& c=g->info.caller_entries[i];if (ep_session_code_discard(g->mod,c.handle)) memset(&c,0,sizeof(c));else ok=0;
    }
    for (unsigned i=EP_C33_CORE_ENTRY_COUNT;i--;) if (g->info.core_entries[i].handle) {
        auto& c=g->info.core_entries[i];if (ep_session_code_discard(g->mod,c.handle)) memset(&c,0,sizeof(c));else ok=0;
    }
    EpSessionCodeInfo* updates[]={&g->info.leave_body,&g->info.leave_entry,&g->info.refresh_body,&g->info.refresh_entry,&g->info.reset_body,&g->info.reset_entries[1],&g->info.reset_entries[0],&g->info.update_body,&g->info.update_entry};
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
    const EpC33LifecycleEntryConfig* lifecycle,const EpC33RefreshEntryConfig* refresh_config,const EpC33LeaveEntryConfig* leave_config,
    const EpC33CoreEntryConfig* core_config,const EpC33CallerEntryConfig* caller_config,bool routed,EpC33ResourceEntriesInfo* out)
{
    if (!out) return 0;EpC33ResourceEntryBindings b={};if (input) b=*input;
    EpC33UpdateEntryConfig update={};if (config) update=*config;
    EpC33LifecycleEntryConfig reset={};if (lifecycle) reset=*lifecycle;
    EpC33RefreshEntryConfig refresh={};if (refresh_config) refresh=*refresh_config;
    EpC33LeaveEntryConfig leave={};if (leave_config) leave=*leave_config;
    EpC33CoreEntryConfig core={};if (core_config) core=*core_config;
    EpC33CallerEntryConfig callers={};if (caller_config) callers=*caller_config;memset(out,0,sizeof(*out));
    if (!mod || !input || !b.storage || !b.roster_owner || !b.reject || ep_roster_owner_in_scope() || !api || api->version<13 ||
        api->size<offsetof(HfApi,read_code)+sizeof(api->read_code) || !api->read || !api->read_code || !api->hook_ex || !api->build_id || (routed && !api->write)) return 0;
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
        g.api.version=api->version;g.api.size=sizeof(g.api);g.api.build_id=api->build_id;g.api.read=api->read;g.api.read_code=api->read_code;g.api.hook_ex=api->hook_ex;g.api.write=api->write;g.routed=routed;
        if (routed) {g.info.publication_state=EP_C33_PUBLISH_PREPARED;for (unsigned i=0;i<EP_C33_PUBLISH_ENTRIES;i++) g.routes[i]={&g,RouteKindBase+i+1,0};}
        for (unsigned i=0;i<EP_C33_RESOURCE_ENTRY_COUNT;i++) { g.contexts[i]={&g,kinds[i]};g.info.targets[i]=rvas[i] ? g.view.game+rvas[i] : 0; }
        g.update={&g,EP_C33_UPDATE};if (config) g.info.update_target=g.view.game+0x664520;
        if (lifecycle) for (unsigned i=0;i<2;i++) {
            g.resets[i]={&g,EP_COMPONENT33_RESET};g.info.reset_targets[i]=g.view.game+(i ? 0x664210 : 0x51ade0);
        }
        if (refresh_config) { g.refresh={&g,EP_C33_RESOURCE_REFRESH};g.info.refresh_target=g.view.game+0xb5e710; }
        if (leave_config) { g.leave={&g,EP_C33_RESOURCE_LEAVE};g.info.leave_target=g.view.game+0xb51de0; }
        if (core_config) {
            const uint32_t rvas[]={0x665fe0,0x51abf0,0x51ac70,0x51ad30,0x666a90,0x666dd0,0x6661a0,
                0x664430,0x666710,0x6667d0,0x666a00,0x6642c0,0x665ec0,0x666850};
            for (unsigned i=0;i<EP_C33_CORE_ENTRY_COUNT;i++) {
                g.core[i]={&g,i+1,storage.family.code[i].base};g.info.core_targets[i]=g.view.game+rvas[i];
            }
        }
        if (caller_config) {
            const uint32_t rvas[]={0x576cf0,0xaddc10,0xb62210};
            for (unsigned i=0;i<EP_C33_CALLER_ENTRY_COUNT;i++) {
                g.callers[i]={&g,EP_C33_CORE_ENTRY_COUNT+i+1,0};g.info.caller_targets[i]=g.view.game+rvas[i];
            }
            g.info.owner_window=storage.family.owner_window;
            memcpy(g.info.reader_windows,storage.family.reader_windows,sizeof(g.info.reader_windows));
        }
        break;
    }
    ReleaseSRWLockExclusive(&entriesLock);if (!group) return 0;
    int ok=1;
    for (unsigned i=0;i<EP_C33_RESOURCE_ENTRY_COUNT;i++) {
        EpSessionCodeInfo code={};
        if (!ep_session_code_reserve(&group->api,mod,b.desired_code[i],48+(routed && i<3 ? 32 : 0),&code)) { ok=0;break; }
        AcquireSRWLockExclusive(&entriesLock);group->info.code[i]=code;ReleaseSRWLockExclusive(&entriesLock);
        uint8_t image[48];Image(&group->contexts[i],image);
        if (!SealEntry(group,i<3 ? i : EP_C33_PUBLISH_ENTRIES,code,image,sizeof(image),36)) { ok=0;break; }
        ep_session_code_info(mod,code.handle,&code);
        AcquireSRWLockExclusive(&entriesLock);group->info.code[i]=code;ReleaseSRWLockExclusive(&entriesLock);
    }
    if (ok && config) {
        EpSessionCodeInfo entry={},body={};
        ok=ep_session_code_reserve(&group->api,mod,update.desired_entry,80+(routed ? 32 : 0),&entry);
        if (ok) ok=ep_session_code_reserve(&group->api,mod,update.desired_body,ep_component33_consumer_bytes(EP_C33_UPDATE),&body);
        AcquireSRWLockExclusive(&entriesLock);group->info.update_entry=entry;group->info.update_body=body;ReleaseSRWLockExclusive(&entriesLock);
        if (ok) {
            EpC33ConsumerAddresses a={group->view.game,body.base,group->view.component,group->view.storage,group->info.code[2].base,entry.base+32+(routed ? 32 : 0)};
            EpComponent33Image image={};
            ok=ep_component33_update_drain_build(&a,group->info.code[3].base,&image)==EP_PROPERTY_OK;
            if (ok) ok=ep_session_code_seal_table(mod,body.handle,image.data,image.bytes,image.table_offset,image.function_count);
            uint8_t bridge[80];UpdateImage(&group->update,bridge);
            if (ok) ok=SealEntry(group,3,entry,bridge,sizeof(bridge),56,2);
            ep_session_code_info(mod,entry.handle,&entry);ep_session_code_info(mod,body.handle,&body);
            AcquireSRWLockExclusive(&entriesLock);group->info.update_entry=entry;group->info.update_body=body;ReleaseSRWLockExclusive(&entriesLock);
        }
    }
    if (ok && lifecycle) {
        for (unsigned i=0;i<2;i++) {
            EpSessionCodeInfo entry={};ok=ep_session_code_reserve(&group->api,mod,reset.reset_entries[i],48+(routed ? 32 : 0),&entry);
            AcquireSRWLockExclusive(&entriesLock);group->info.reset_entries[i]=entry;ReleaseSRWLockExclusive(&entriesLock);
            if (!ok) break;
            uint8_t image[48];ObjectImage(&group->resets[i],i==0,ResetDispatch,image);
            ok=SealEntry(group,4+i,entry,image,sizeof(image),36);
            ep_session_code_info(mod,entry.handle,&entry);
            AcquireSRWLockExclusive(&entriesLock);group->info.reset_entries[i]=entry;ReleaseSRWLockExclusive(&entriesLock);
            if (!ok) break;
        }
        if (ok) {
            EpSessionCodeInfo body={};ok=ep_session_code_reserve(&group->api,mod,reset.reset_body,ep_component33_image_bytes(EP_COMPONENT33_RESET),&body);
            AcquireSRWLockExclusive(&entriesLock);group->info.reset_body=body;ReleaseSRWLockExclusive(&entriesLock);
            if (ok) {
                EpComponent33Addresses a={group->view.game,body.base,group->view.component,group->view.storage,storage.family.code[0].base,group->info.update_entry.base+32+(routed ? 32 : 0)};
                EpComponent33Image image={};ok=ep_component33_image_build(EP_COMPONENT33_RESET,&a,&image)==EP_PROPERTY_OK;
                if (ok) ok=ep_session_code_seal_table(mod,body.handle,image.data,image.bytes,image.table_offset,image.function_count);
                ep_session_code_info(mod,body.handle,&body);
                AcquireSRWLockExclusive(&entriesLock);group->info.reset_body=body;ReleaseSRWLockExclusive(&entriesLock);
            }
        }
    }
    if (ok && refresh_config) {
        EpSessionCodeInfo entry={},body={};
        ok=ep_session_code_reserve(&group->api,mod,refresh.desired_entry,48+(routed ? 32 : 0),&entry);
        if (ok) ok=ep_session_code_reserve(&group->api,mod,refresh.desired_body,ep_component33_refresh_image_bytes(),&body);
        AcquireSRWLockExclusive(&entriesLock);group->info.refresh_entry=entry;group->info.refresh_body=body;ReleaseSRWLockExclusive(&entriesLock);
        if (ok) {
            EpC33RefreshAddresses a={group->view.game,body.base,group->info.code[0].base};EpComponent33Image image={};
            ok=ep_component33_refresh_build(&a,&image)==EP_PROPERTY_OK;
            if (ok) ok=ep_session_code_seal_table(mod,body.handle,image.data,image.bytes,image.table_offset,image.function_count);
            uint8_t bridge[48];ObjectImage(&group->refresh,true,RefreshDispatch,bridge);
            if (ok) ok=SealEntry(group,6,entry,bridge,sizeof(bridge),36);
            ep_session_code_info(mod,entry.handle,&entry);ep_session_code_info(mod,body.handle,&body);
            AcquireSRWLockExclusive(&entriesLock);group->info.refresh_entry=entry;group->info.refresh_body=body;ReleaseSRWLockExclusive(&entriesLock);
        }
    }
    if (ok && leave_config) {
        EpSessionCodeInfo entry={},body={};
        ok=ep_session_code_reserve(&group->api,mod,leave.desired_entry,48+(routed ? 32 : 0),&entry);
        if (ok) ok=ep_session_code_reserve(&group->api,mod,leave.desired_body,ep_component33_leave_image_bytes(),&body);
        AcquireSRWLockExclusive(&entriesLock);group->info.leave_entry=entry;group->info.leave_body=body;ReleaseSRWLockExclusive(&entriesLock);
        if (ok) {
            EpC33LeaveAddresses a={group->view.game,body.base,group->info.code[1].base};EpComponent33Image image={};
            ok=ep_component33_leave_build(&a,&image)==EP_PROPERTY_OK;
            if (ok) ok=ep_session_code_seal_table(mod,body.handle,image.data,image.bytes,image.table_offset,image.function_count);
            uint8_t bridge[48];ArgumentImage(&group->leave,LeaveDispatch,bridge);
            if (ok) ok=SealEntry(group,7,entry,bridge,sizeof(bridge),36);
            ep_session_code_info(mod,entry.handle,&entry);ep_session_code_info(mod,body.handle,&body);
            AcquireSRWLockExclusive(&entriesLock);group->info.leave_entry=entry;group->info.leave_body=body;ReleaseSRWLockExclusive(&entriesLock);
        }
    }
    for (unsigned i=0;ok && core_config && i<EP_C33_CORE_ENTRY_COUNT;i++) {
        EpSessionCodeInfo entry={};ok=ep_session_code_reserve(&group->api,mod,core.desired_entries[i],48+(routed ? 32 : 0),&entry);
        AcquireSRWLockExclusive(&entriesLock);group->info.core_entries[i]=entry;ReleaseSRWLockExclusive(&entriesLock);
        uint8_t bridge[48];CoreImage(&group->core[i],bridge);
        if (ok) ok=SealEntry(group,8+i,entry,bridge,sizeof(bridge),36);
        if (entry.handle) ep_session_code_info(mod,entry.handle,&entry);
        AcquireSRWLockExclusive(&entriesLock);group->info.core_entries[i]=entry;ReleaseSRWLockExclusive(&entriesLock);
    }
    for (unsigned i=0;ok && caller_config && i<EP_C33_CALLER_ENTRY_COUNT;i++) {
        EpSessionCodeInfo entry={};ok=ep_session_code_reserve(&group->api,mod,callers.desired_entries[i],48+(routed ? 32 : 0),&entry);
        AcquireSRWLockExclusive(&entriesLock);group->info.caller_entries[i]=entry;ReleaseSRWLockExclusive(&entriesLock);
        uint8_t bridge[48];CoreImage(&group->callers[i],bridge);
        if (ok) ok=SealEntry(group,22+i,entry,bridge,sizeof(bridge),36);
        if (entry.handle) ep_session_code_info(mod,entry.handle,&entry);
        AcquireSRWLockExclusive(&entriesLock);group->info.caller_entries[i]=entry;ReleaseSRWLockExclusive(&entriesLock);
    }
    AcquireSRWLockExclusive(&entriesLock);
    if (ok) group->info.state=EP_C33_ENTRIES_PREPARED;else Cancel(group);
    if (group->info.handle) *out=group->info;ReleaseSRWLockExclusive(&entriesLock);return ok;
}
int ep_component33_resource_entries_prepare(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* b,EpC33ResourceEntriesInfo* out)
{ return Prepare(api,mod,b,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,false,out); }
int ep_component33_resource_entries_prepare_update(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* b,const EpC33UpdateEntryConfig* config,EpC33ResourceEntriesInfo* out)
{
    if (!config) { if (out) memset(out,0,sizeof(*out));return 0; }
    return Prepare(api,mod,b,config,nullptr,nullptr,nullptr,nullptr,nullptr,false,out);
}
int ep_component33_resource_entries_prepare_lifecycle(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* b,const EpC33LifecycleEntryConfig* config,EpC33ResourceEntriesInfo* out)
{
    if (!config) { if (out) memset(out,0,sizeof(*out));return 0; }
    return Prepare(api,mod,b,&config->update,config,nullptr,nullptr,nullptr,nullptr,false,out);
}
int ep_component33_resource_entries_prepare_refresh(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* b,const EpC33RefreshEntryConfig* config,EpC33ResourceEntriesInfo* out)
{
    if (!config) { if (out) memset(out,0,sizeof(*out));return 0; }
    return Prepare(api,mod,b,&config->lifecycle.update,&config->lifecycle,config,nullptr,nullptr,nullptr,false,out);
}
int ep_component33_resource_entries_prepare_leave(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* b,const EpC33LeaveEntryConfig* config,EpC33ResourceEntriesInfo* out)
{
    if (!config) { if (out) memset(out,0,sizeof(*out));return 0; }
    return Prepare(api,mod,b,&config->refresh.lifecycle.update,&config->refresh.lifecycle,&config->refresh,config,nullptr,nullptr,false,out);
}
int ep_component33_resource_entries_prepare_core(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* b,const EpC33CoreEntryConfig* config,EpC33ResourceEntriesInfo* out)
{
    if (!config) { if (out) memset(out,0,sizeof(*out));return 0; }
    return Prepare(api,mod,b,&config->leave.refresh.lifecycle.update,&config->leave.refresh.lifecycle,&config->leave.refresh,&config->leave,config,nullptr,false,out);
}
int ep_component33_resource_entries_prepare_callers(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* b,const EpC33CallerEntryConfig* config,EpC33ResourceEntriesInfo* out)
{
    if (!config) { if (out) memset(out,0,sizeof(*out));return 0; }
    const auto* core=&config->core;
    return Prepare(api,mod,b,&core->leave.refresh.lifecycle.update,&core->leave.refresh.lifecycle,&core->leave.refresh,&core->leave,core,config,false,out);
}
int ep_component33_resource_entries_prepare_transaction(const HfApi* api,HfMod* mod,const EpC33ResourceEntryBindings* b,const EpC33CallerEntryConfig* config,EpC33ResourceEntriesInfo* out)
{
    if (!config) {if (out) memset(out,0,sizeof(*out));return 0;}
    const auto* core=&config->core;
    return Prepare(api,mod,b,&core->leave.refresh.lifecycle.update,&core->leave.refresh.lifecycle,&core->leave.refresh,&core->leave,core,config,true,out);
}
int ep_component33_resource_entries_info(HfMod* mod,uint64_t id,EpC33ResourceEntriesInfo* out)
{
    if (!out) return 0;memset(out,0,sizeof(*out));if (ep_roster_owner_in_scope()) return 0;
    AcquireSRWLockShared(&entriesLock);auto* g=Find(mod,id);if (g) {*out=g->info;out->active=(uint32_t)InterlockedCompareExchange(&g->active,0,0);}ReleaseSRWLockShared(&entriesLock);return g!=nullptr;
}
int ep_component33_resource_entries_retain(HfMod* mod,uint64_t id)
{
    if (ep_roster_owner_in_scope()) return 0;int ok=0;AcquireSRWLockExclusive(&entriesLock);auto* g=Find(mod,id);
    if (g && g->info.state==EP_C33_ENTRIES_PREPARED) {
        uint64_t handles[EP_C33_RESOURCE_ENTRY_COUNT+9+EP_C33_CORE_ENTRY_COUNT+EP_C33_CALLER_ENTRY_COUNT];unsigned count=EP_C33_RESOURCE_ENTRY_COUNT;
        for (unsigned i=0;i<EP_C33_RESOURCE_ENTRY_COUNT;i++) handles[i]=g->info.code[i].handle;
        if (g->info.update_target) { handles[count++]=g->info.update_entry.handle;handles[count++]=g->info.update_body.handle; }
        if (g->info.reset_targets[0]) {
            handles[count++]=g->info.reset_entries[0].handle;handles[count++]=g->info.reset_entries[1].handle;handles[count++]=g->info.reset_body.handle;
        }
        if (g->info.refresh_target) { handles[count++]=g->info.refresh_entry.handle;handles[count++]=g->info.refresh_body.handle; }
        if (g->info.leave_target) { handles[count++]=g->info.leave_entry.handle;handles[count++]=g->info.leave_body.handle; }
        if (g->info.core_targets[0]) for (const auto& c:g->info.core_entries) handles[count++]=c.handle;
        if (g->info.caller_targets[0]) for (const auto& c:g->info.caller_entries) handles[count++]=c.handle;
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
            if (g->info.refresh_target) {
                ep_session_code_info(mod,g->info.refresh_entry.handle,&g->info.refresh_entry);
                ep_session_code_info(mod,g->info.refresh_body.handle,&g->info.refresh_body);
            }
            if (g->info.leave_target) {
                ep_session_code_info(mod,g->info.leave_entry.handle,&g->info.leave_entry);
                ep_session_code_info(mod,g->info.leave_body.handle,&g->info.leave_body);
            }
            if (g->info.core_targets[0]) for (auto& c:g->info.core_entries) ep_session_code_info(mod,c.handle,&c);
            if (g->info.caller_targets[0]) for (auto& c:g->info.caller_entries) ep_session_code_info(mod,c.handle,&c);
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
int ep_component33_resource_entries_publish(HfMod* mod,uint64_t id,int32_t priority)
{
    if (ep_roster_owner_in_scope()) return 0;
    AcquireSRWLockExclusive(&entriesLock);auto* g=Find(mod,id);
    if (!g || !g->routed || g->info.state!=EP_C33_ENTRIES_RETAINED || g->info.publication_state!=EP_C33_PUBLISH_PREPARED) {
        ReleaseSRWLockExclusive(&entriesLock);return 0;
    }
    g->info.publication_state=EP_C33_PUBLISHING;ReleaseSRWLockExclusive(&entriesLock);int ok=1;
    for (unsigned i=0;i<EP_C33_PUBLISH_ENTRIES;i++) {
        auto* code=RouteCode(g,i);AcquireSRWLockExclusive(&entriesLock);++g->info.published_attempts;ReleaseSRWLockExclusive(&entriesLock);
        ok=ep_session_code_publish(mod,code->handle,(uintptr_t)RouteTarget(g,i),priority);
        EpSessionCodeInfo info={};ep_session_code_info(mod,code->handle,&info);
        AcquireSRWLockExclusive(&entriesLock);code->state=info.state;ReleaseSRWLockExclusive(&entriesLock);
        if (!ok || !InterlockedCompareExchangePointer((void* volatile*)code->next_pointer,nullptr,nullptr)) {ok=0;break;}
    }
    AcquireSRWLockExclusive(&entriesLock);g->info.publication_state=ok ? EP_C33_PUBLISH_READY : EP_C33_PUBLISH_FAILED;ReleaseSRWLockExclusive(&entriesLock);return ok;
}
// Reuse the owner's registered SEH boundary for cleanup even after a nested
// native call quarantines the owner. This does not reacquire or bypass its lock.
extern "C" int EpOwnerInvoke(int (*)(void*),void*,int*);
struct EntryCommit {
    EntryGroup* group;EpC33EntryCommitGuard guard;void* lease;
    unsigned touched;uint32_t outcome;bool unsafe,ended,installed;
};
struct CommitWindow {uint64_t target;unsigned bytes;const uint8_t* expected;const uint8_t* replacement;};
static CommitWindow GetWindow(EntryGroup* g,unsigned index)
{
    if (!index) {const auto& w=g->info.owner_window;return {w.target,w.bytes,w.expected,w.replacement};}
    const auto& w=g->info.reader_windows[index-1];return {w.target,w.bytes,w.expected,w.replacement};
}
static bool WindowMatches(EntryGroup* g,const CommitWindow& w,const uint8_t* expected)
{
    uint8_t bytes[75];return g->api.read_code((uintptr_t)w.target,bytes,w.bytes)==0 && !memcmp(bytes,expected,w.bytes);
}
static int CommitBegin(void* p) {auto* c=(EntryCommit*)p;return c->guard.begin(c->guard.context,&c->lease)!=0;}
static int CommitInstall(void* p)
{
    auto* c=(EntryCommit*)p;auto* g=c->group;
    for (unsigned i=0;i<3;i++) {auto w=GetWindow(g,i);if (!WindowMatches(g,w,w.expected)) return 0;}
    if (!c->guard.validate(c->guard.context,c->lease)) return 0;
    if (ep_roster_owner_native_status(g->mod,g->bindings.roster_owner)!=EP_OWNER_OK) return 0;
    for (unsigned i=0;i<3;i++) {
        auto w=GetWindow(g,i);c->touched=i+1;
        if (g->api.write((uintptr_t)w.target,w.replacement,w.bytes)!=0 || !WindowMatches(g,w,w.replacement)) return 0;
    }
    return 1;
}
struct RestoreWindow {EntryCommit* commit;unsigned index;};
static int CommitRestore(void* p)
{
    auto* r=(RestoreWindow*)p;auto* g=r->commit->group;auto w=GetWindow(g,r->index);
    int written=g->api.write((uintptr_t)w.target,w.expected,w.bytes);bool matches=WindowMatches(g,w,w.expected);
    return written==0 && matches;
}
static int CommitEnd(void* p)
{
    auto* c=(EntryCommit*)p;c->ended=true;c->guard.end(c->guard.context,c->lease,c->outcome);return 1;
}
static int CommitStage(void* p,const EpNativeRosterView*)
{
    auto* c=(EntryCommit*)p;int fault=0;c->installed=EpOwnerInvoke(CommitInstall,c,&fault)!=0;c->unsafe|=fault!=0;return 1;
}
static int CommitUnderOwner(void* p,const EpNativeRosterView* view)
{
    auto* c=(EntryCommit*)p;auto* g=c->group;InterlockedExchange(&g->switching,1);
    if (view->game!=g->view.game) c->unsafe=true;
    if (!c->unsafe && ep_roster_owner_call(g->mod,g->bindings.roster_owner,1,CommitStage,c)!=EP_OWNER_OK) c->unsafe=true;
    c->unsafe|=ep_roster_owner_native_status(g->mod,g->bindings.roster_owner)!=EP_OWNER_OK;
    if (c->installed && !c->unsafe) {InterlockedExchange(&g->active,1);c->outcome=EP_C33_COMMIT_NEW;}
    else {
        for (unsigned i=c->touched;i--;) {
            RestoreWindow restore={c,i};int failed=0;
            if (!EpOwnerInvoke(CommitRestore,&restore,&failed) || failed) c->unsafe=true;
        }
        c->outcome=c->unsafe ? EP_C33_COMMIT_UNSAFE : EP_C33_COMMIT_OLD;
    }
    int end_fault=0;if (!EpOwnerInvoke(CommitEnd,c,&end_fault) || end_fault) c->unsafe=true;
    // Clear before releasing the owner: queued calls must see a finished
    // transition when they acquire it, not a transient reentry refusal.
    InterlockedExchange(&g->switching,0);
    // Return failure only for unknown restoration/SEH. Safe OLD rollback must
    // not poison the owner or prevent a subsequently valid commit attempt.
    return !c->unsafe;
}
int ep_component33_resource_entries_commit(HfMod* mod,uint64_t id,const EpC33EntryCommitGuard* input)
{
    if (!input || !input->begin || !input->validate || !input->end || ep_roster_owner_in_scope()) return 0;
    const auto guard=*input;AcquireSRWLockExclusive(&entriesLock);auto* g=Find(mod,id);
    if (!g || !g->routed || g->info.publication_state!=EP_C33_PUBLISH_READY) {ReleaseSRWLockExclusive(&entriesLock);return 0;}
    g->info.publication_state=EP_C33_COMMITTING;ReleaseSRWLockExclusive(&entriesLock);
    EntryCommit c={g,guard,nullptr,0,EP_C33_COMMIT_OLD,false,false,false};int fault=0,entered=EpOwnerInvoke(CommitBegin,&c,&fault);
    c.unsafe=fault!=0 || (entered && !c.lease) || (!entered && c.lease);
    EpRosterOwnerResult result=EP_OWNER_OK;
    if (entered || c.lease || c.unsafe) {
        result=ep_roster_owner_call(mod,g->bindings.roster_owner,0,CommitUnderOwner,&c);
        if (!c.ended) {c.outcome=EP_C33_COMMIT_UNSAFE;c.unsafe=true;int ignored=0;EpOwnerInvoke(CommitEnd,&c,&ignored);}
    }
    InterlockedExchange(&g->switching,0);
    AcquireSRWLockExclusive(&entriesLock);bool active=InterlockedCompareExchange(&g->active,0,0)!=0;
    bool unsafe=c.unsafe || result!=EP_OWNER_OK;g->info.commit_outcome=unsafe ? EP_C33_COMMIT_UNSAFE : c.outcome;
    g->info.publication_state=active ? EP_C33_PUBLISH_ACTIVE : unsafe ? EP_C33_PUBLISH_FAILED : EP_C33_PUBLISH_READY;
    ReleaseSRWLockExclusive(&entriesLock);return active && !unsafe;
}
