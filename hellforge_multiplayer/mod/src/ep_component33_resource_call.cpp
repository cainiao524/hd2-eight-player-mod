#include "ep_component33_resource_call.h"
#include <windows.h>
#include <string.h>
static uint32_t U32(const uint8_t* p) { uint32_t x;memcpy(&x,p,4);return x; }
static uint64_t U64(const uint8_t* p) { uint64_t x;memcpy(&x,p,8);return x; }
int ep_component33_acquire_demand(const EpC33AcquireSnapshot* input,EpC33AcquireDemand* out)
{
    if (!out) return 0;
    EpC33AcquireDemand result={};
    if (!input) { memset(out,0,sizeof(*out));return 0; }
    for (unsigned g=0;g<EP_C33_ACQUIRE_GROUPS;g++) {
        const uint8_t* block=input->package+0x808*g;uint32_t value=input->thresholds[g];
        if (!U32(block+0x800)) continue;
        for (unsigned i=0;i<EP_C33_ACQUIRE_ROWS;i++) {
            const uint8_t* row=block+0x20*i;uint64_t key=U64(row);
            if (key && U32(row+0x14)<=value && U32(row+0x10)>=value) result.keys[result.count++]=key;
        }
    }
    *out=result;return 1;
}
struct ResourceCall {
    HfMod* mod;uint64_t storage,owner;
    EpC33ResourceAcquireOps ops;EpC33ResourceCallResult result;
    EpC33ResourceScopeView view;EpC33AcquireSnapshot snapshot;EpC33AcquireDemand demand;
    void* memory;uint32_t bytes;bool reentered,release_only;
};
static thread_local ResourceCall* resourceCall;
static int Execute(void* opaque,const EpNativeRosterView*)
{
    auto* call=(ResourceCall*)opaque;
    memcpy((void*)(uintptr_t)call->view.resources.address,call->memory,call->bytes);
    call->result.executed=1;
    int ok=call->ops.execute(call->ops.context,&call->view,&call->snapshot,&call->demand);
    if (call->reentered) { call->result.status=EP_C33_CALL_REENTRANT;return 0; }
    if (ok==1 && ep_c33_resource_validate(&call->view.resources,(void*)(uintptr_t)call->view.resources.address,call->bytes)!=EP_RESOURCE_OK) {
        call->result.status=EP_C33_CALL_RESOURCE_STATE;return 0;
    }
    return ok==1;
}
static int Acquire(void* opaque,const EpNativeRosterView* roster)
{
    auto* call=(ResourceCall*)opaque;
    if (!ep_component33_storage_resource_scope(call->mod,call->storage,call->owner,roster->game,&call->view)) {
        call->result.status=EP_C33_CALL_STORAGE;return 1;
    }
    uint32_t bytes=ep_c33_resource_bytes(call->view.resources.capacity);
    if (bytes!=call->bytes) { call->result.status=EP_C33_CALL_STORAGE;return 1; }
    void* arena=(void*)(uintptr_t)call->view.resources.address;
    if (ep_c33_resource_validate(&call->view.resources,arena,bytes)!=EP_RESOURCE_OK) {
        call->result.status=EP_C33_CALL_RESOURCE_STATE;return 0;
    }
    memcpy(call->memory,arena,bytes);
    int ready=call->ops.collect(call->ops.context,&call->view,&call->snapshot);
    if (call->reentered) { call->result.status=EP_C33_CALL_REENTRANT;return 0; }
    if (memcmp(call->memory,arena,bytes)) { call->result.status=EP_C33_CALL_SOURCE_CHANGED;return 0; }
    if (ready==2) return 1;
    if (ready!=1) { call->result.status=EP_C33_CALL_SNAPSHOT;return 1; }
    if (!call->release_only) {
        ep_component33_acquire_demand(&call->snapshot,&call->demand);call->result.demand_count=call->demand.count;
        int result=ep_c33_resource_reserve(&call->view.resources,call->memory,bytes,call->demand.keys,call->demand.count,(uint8_t*)call->memory+bytes,bytes);
        if (result!=EP_RESOURCE_OK) {
            call->result.status=result==EP_RESOURCE_CAPACITY ? EP_C33_CALL_CAPACITY : EP_C33_CALL_RESOURCE_STATE;
            return result==EP_RESOURCE_CAPACITY;
        }
    }
    /* Mark a write only after admission; the nested scope also refuses a
     * saturated revision BEFORE copying the admitted arena or service calls. */
    auto owner=ep_roster_owner_call(call->mod,call->owner,1,Execute,call);
    if (owner!=EP_OWNER_OK) { call->result.owner_result=owner;if (!call->result.status) call->result.status=EP_C33_CALL_OWNER; }
    return 1;
}
static int ResourceScopeCall(HfMod* mod,uint64_t storage,uint64_t owner,const EpC33ResourceAcquireOps* input,EpC33ResourceCallResult* out,bool release_only)
{
    EpC33ResourceAcquireOps ops={};if (input) ops=*input;
    if (!out) return EP_C33_CALL_ARGUMENT;memset(out,0,sizeof(*out));
    if (resourceCall) { resourceCall->reentered=true;out->status=EP_C33_CALL_REENTRANT;return out->status; }
    if (!mod || !storage || !owner || !input || !ops.collect || !ops.execute) { out->status=EP_C33_CALL_ARGUMENT;return out->status; }
    EpC33StorageInfo info={};EpC33ResourceStorageInfo resources={};
    if (!ep_component33_storage_info(mod,storage,&info) || info.state!=EP_C33_STORAGE_RETAINED ||
        !ep_component33_storage_resources(mod,storage,&resources) || !resources.binding.address) { out->status=EP_C33_CALL_STORAGE;return out->status; }
    ResourceCall call={};call.mod=mod;call.storage=storage;call.owner=owner;call.ops=ops;call.bytes=resources.arena_bytes;call.release_only=release_only;
    call.memory=HeapAlloc(GetProcessHeap(),0,(SIZE_T)call.bytes*2);
    if (!call.memory) { out->status=EP_C33_CALL_MEMORY;return out->status; }
    resourceCall=&call;auto result=ep_roster_owner_call(mod,owner,0,Acquire,&call);resourceCall=nullptr;
    HeapFree(GetProcessHeap(),0,call.memory);
    if (result!=EP_OWNER_OK) {
        if (!call.result.owner_result) call.result.owner_result=result;
        if (!call.result.status) call.result.status=EP_C33_CALL_OWNER;
    }
    *out=call.result;return out->status;
}
int ep_component33_resource_acquire_call(HfMod* mod,uint64_t storage,uint64_t owner,const EpC33ResourceAcquireOps* input,EpC33ResourceCallResult* out)
{ return ResourceScopeCall(mod,storage,owner,input,out,false); }
struct ServiceCall { EpC33ResourceServiceOps ops;ResourceCall* call;bool release_only;uint32_t deferred; };
static int ServiceCollect(void* p,const EpC33ResourceScopeView* v,EpC33AcquireSnapshot* out)
{ auto* context=(ServiceCall*)p;return context->ops.collect(context->ops.context,v,out); }
static int ServiceInvoke(void* p,uint32_t operation,uint64_t key)
{
    auto* context=(ServiceCall*)p;auto* call=context->call;
    int ok=context->ops.service(context->ops.context,&call->view,operation,key);
    return ok==1 && !call->reentered && ep_roster_owner_native_status(call->mod,call->owner)==EP_OWNER_OK;
}
static int ServiceExecute(void* p,const EpC33ResourceScopeView* v,const EpC33AcquireSnapshot* s,const EpC33AcquireDemand* d)
{
    auto* context=(ServiceCall*)p;auto* call=resourceCall;context->call=call;
    uint64_t releases[EP_C33_ACQUIRE_KEYS];unsigned count=0;
    static_assert(EP_C33_ACQUIRE_KEYS==EP_RESOURCE_BATCH_MAX,"complete resource batch");
    for (unsigned g=0;g<EP_C33_ACQUIRE_GROUPS;g++) {
        const uint8_t* block=s->package+0x808*g;if (!U32(block+0x800)) continue;
        for (unsigned row=0;row<EP_C33_ACQUIRE_ROWS;row++) { uint64_t key=U64(block+row*0x20);if (key) releases[count++]=key; }
    }
    int result=context->release_only ? ep_c33_resource_release(&v->resources,(void*)(uintptr_t)v->resources.address,call->bytes,
        releases,count,context->deferred,call->memory,call->bytes,ServiceInvoke,context) :
        ep_c33_resource_execute(&v->resources,(void*)(uintptr_t)v->resources.address,call->bytes,
        releases,count,d->keys,d->count,call->memory,call->bytes,ServiceInvoke,context);
    if (result!=EP_RESOURCE_OK) call->result.status=result==EP_RESOURCE_SERVICE ? EP_C33_CALL_SERVICE : EP_C33_CALL_RESOURCE_STATE;
    return result==EP_RESOURCE_OK;
}
int ep_component33_resource_acquire_services_call(HfMod* mod,uint64_t storage,uint64_t owner,const EpC33ResourceServiceOps* input,EpC33ResourceCallResult* out)
{
    ServiceCall context={};if (input) context.ops=*input;
    if (!input || !context.ops.collect || !context.ops.service) {
        if (out) { memset(out,0,sizeof(*out));out->status=EP_C33_CALL_ARGUMENT; }return EP_C33_CALL_ARGUMENT;
    }
    EpC33ResourceAcquireOps ops={&context,ServiceCollect,ServiceExecute};
    return ep_component33_resource_acquire_call(mod,storage,owner,&ops,out);
}
int ep_component33_resource_release_services_call(HfMod* mod,uint64_t storage,uint64_t owner,uint32_t deferred,const EpC33ResourceServiceOps* input,EpC33ResourceCallResult* out)
{
    ServiceCall context={};if (input) context.ops=*input;context.release_only=true;context.deferred=deferred;
    if (deferred>1 || !input || !context.ops.collect || (!deferred && !context.ops.service)) {
        if (out) { memset(out,0,sizeof(*out));out->status=EP_C33_CALL_ARGUMENT; }return EP_C33_CALL_ARGUMENT;
    }
    EpC33ResourceAcquireOps ops={&context,ServiceCollect,ServiceExecute};
    return ResourceScopeCall(mod,storage,owner,&ops,out,true);
}
