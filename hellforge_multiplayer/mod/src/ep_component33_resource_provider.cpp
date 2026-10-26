#include "ep_component33_resource_provider.h"
#include <string.h>
#include "ep_component33_resource_provider_template.h"
struct Provider {
    int (*read)(uintptr_t,void*,size_t);
    int (*read_code)(uintptr_t,void*,size_t);
    HfMod* mod;uint64_t owner,target;EpC33ResourceProviderOps ops;
    EpC33ResourceProviderResult result;
    bool release_only,by_object;uint32_t ordinal,deferred;
    bool native,bound;uint64_t engine,service_table,load,dispose,get_context,resolve;
};
static uint32_t D(const void* p) { uint32_t x;memcpy(&x,p,4);return x; }
static uint64_t Q(const void* p) { uint64_t x;memcpy(&x,p,8);return x; }
static bool Pointer(uint64_t p,uint64_t bytes)
{ return p && p<(UINT64_C(1)<<47) && bytes<=(UINT64_C(1)<<47)-p; }
static bool Read(Provider* p,uint64_t address,void* out,uint32_t bytes,bool code=false)
{
    if (!ep_component33_resource_scope_ready(p->mod,p->owner)) { p->result.source_status=EP_C33_PROVIDER_OWNER;return false; }
    if (!Pointer(address,bytes)) { p->result.source_status=EP_C33_PROVIDER_LAYOUT;return false; }
    if (bytes>EP_C33_PROVIDER_READ_LIMIT-p->result.read_bytes) { p->result.source_status=EP_C33_PROVIDER_BUDGET;return false; }
    p->result.read_bytes+=bytes;
    if ((code ? p->read_code : p->read)((uintptr_t)address,out,bytes)!=0) { p->result.source_status=code ? EP_C33_PROVIDER_CODE : EP_C33_PROVIDER_READ;return false; }
    return true;
}
static bool Ready(Provider* p)
{
    if (ep_component33_resource_scope_ready(p->mod,p->owner)) return true;
    p->result.source_status=EP_C33_PROVIDER_OWNER;return false;
}
static bool Link(Provider* p,uint64_t base,uint32_t offset,uint64_t* value)
{
    if (!Pointer(base,uint64_t(offset)+8)) { p->result.source_status=EP_C33_PROVIDER_LAYOUT;return false; }
    if (!Read(p,base+offset,value,8)) return false;
    if (!Pointer(*value,1)) { p->result.source_status=EP_C33_PROVIDER_LAYOUT;return false; }
    return true;
}
static bool BindNative(Provider* p,const EpC33ResourceScopeView* v,unsigned needed)
{
    uint8_t code[sizeof(ep_c33_native_resolve_source)];
    const uint8_t* sources[]={ep_c33_native_dispose_source,ep_c33_native_load_source,p->by_object ? ep_c33_native_defer_source : ep_c33_native_resolve_source};
    const uint32_t sizes[]={sizeof(ep_c33_native_dispose_source),sizeof(ep_c33_native_load_source),sizeof(ep_c33_native_resolve_source)};
    static_assert(sizeof(ep_c33_native_defer_source)==sizeof(ep_c33_native_resolve_source),"resolver windows");
    const uint32_t rvas[]={0x665ada,0x665847,p->by_object ? 0x665985u : 0x665704u};
    for (unsigned i=0;i<3;i++) if (needed&(1u<<i)) {
        if (!Read(p,v->game+rvas[i],code,sizes[i],true)) return false;
        if (memcmp(code,sources[i],sizes[i])) { p->result.source_status=EP_C33_PROVIDER_CODE;return false; }
    }
    if (!Link(p,v->game,0x3326308,&p->engine)) return false;
    if ((needed&3) && !Link(p,p->engine,0x10,&p->service_table)) return false;
    if ((needed&1) && !Link(p,p->service_table,0x300,&p->dispose)) return false;
    if ((needed&2) && !Link(p,p->service_table,0x2f0,&p->load)) return false;
    if (needed&4) {
        uint64_t contexts,objects;
        if (!Link(p,p->engine,0x38,&contexts) ||
            !Link(p,p->engine,0x40,&objects) || !Link(p,contexts,8,&p->get_context) || !Link(p,objects,0x160,&p->resolve)) return false;
    }
    p->bound=true;return true;
}
static bool Resolve(Provider* p,uint32_t handle,uint64_t* out)
{
    *out=0;if (handle==0x7fff) return true;++p->result.resolve_calls;
    if (p->native) {
        if (!p->bound || !Ready(p)) return false;
        /* Win64: getter receives the engine API in RCX; the resolver then
         * receives its RAX in RCX and the zero-extended handle in EDX. */
        uint64_t context=((uint64_t (*)(uint64_t))(uintptr_t)p->get_context)(p->engine);
        if (!Ready(p)) return false;
        *out=((uint64_t (*)(uint64_t,uint32_t))(uintptr_t)p->resolve)(context,handle);
    } else if (p->ops.resolve(p->ops.context,handle,out)!=1) { p->result.source_status=EP_C33_PROVIDER_RESOLVE;return false; }
    return Ready(p);
}
static bool MatchCode(Provider* p,uint64_t game)
{
    uint8_t bytes[sizeof(ep_c33_threshold_source)];
    for (unsigned i=0;i<(p->release_only ? 1u : 2u);i++) {
        const uint8_t* source=i ? ep_c33_threshold_source : ep_c33_package_source;
        uint32_t size=i ? sizeof(ep_c33_threshold_source) : sizeof(ep_c33_package_source);
        if (!Read(p,game+(i ? 0x7af0a0 : 0x4f6430),bytes,size,true)) return false;
        if (memcmp(bytes,source,size)) { p->result.source_status=EP_C33_PROVIDER_CODE;return false; }
    }
    return true;
}
static bool Select(Provider* p,const EpC33ResourceScopeView* v,uint64_t* package_key,bool* found)
{
    uint8_t header[0x70],records[8][24];uint64_t pointers[8],global;uint32_t invalid;
    *found=false;
    if (!Read(p,v->game+0x33267b8,&global,8) || !Read(p,v->game+0x3483c34,&invalid,4) ||
        !Read(p,v->component,header,sizeof(header)) || !Read(p,v->storage,pointers,sizeof(pointers))) return false;
    uint32_t t=D(header+8),d=D(header+12),prefix=D(header+16),seed=D(header+0x68),occupied=0;
    if (global!=v->component || prefix>d || d>t || t>8 || Q(header+0x58)!=v->component+0x14 || D(header+0x60)!=8 || D(header+0x64)) goto bad;
    for (unsigned i=0;i<8;i++) occupied+=D(header+0x14+i*8)!=0;
    if (occupied!=t) goto bad;
    for (unsigned i=0;i<t;i++) {
        if (!Read(p,pointers[i],records[i],24)) return false;
        uint32_t id=D(records[i]+8),flags=D(records[i]+20),at=(id*seed)&7,probe=0;
        if (!id || id==invalid || bool(flags&1)!=(i<prefix)) goto bad;
        while (probe<8 && D(header+0x14+at*8)!=id && D(header+0x14+at*8)) { at=(at+1)&7;++probe; }
        if (probe==8 || D(header+0x14+at*8)!=id || D(header+0x18+at*8)!=i) goto bad;
    }
    if (p->release_only && !p->by_object) {
        if (p->ordinal<d) { *package_key=Q(records[p->ordinal]);*found=true; }
        return true;
    }
    for (unsigned i=0;i<d;i++) {
        uint64_t object;if (!Resolve(p,D(records[i]+16),&object)) return false;
        if (object==p->target) { *package_key=Q(records[i]);*found=true;return true; }
    }
    return true;
bad:p->result.source_status=EP_C33_PROVIDER_LAYOUT;return false;
}
static bool Package(Provider* p,uint64_t game,uint64_t key,uint8_t* out)
{
    uint64_t root,table;uint8_t rows[32];
    if (!key) { p->result.source_status=EP_C33_PROVIDER_NO_PACKAGE;return false; }
    if (!Read(p,game+0x346bf98,&root,8) || !Pointer(root,0xf12588) ||
        !Read(p,root+0xf12580,&table,8) || !Read(p,table,rows,sizeof(rows))) {
        if (!p->result.source_status) p->result.source_status=EP_C33_PROVIDER_LAYOUT;return false;
    }
    for (unsigned probe=0;probe<2;probe++) {
        const uint8_t* row=rows+16*((key+probe)&1);uint64_t current=Q(row);
        if (current==key) {
            uint64_t offset=0x20+UINT64_C(0x3030)*D(row+8);
            if (!Pointer(table,offset+EP_C33_ACQUIRE_PACKAGE_BYTES)) { p->result.source_status=EP_C33_PROVIDER_LAYOUT;return false; }
            return Read(p,table+offset,out,EP_C33_ACQUIRE_PACKAGE_BYTES);
        }
        if (!current) break;
    }
    p->result.source_status=EP_C33_PROVIDER_NO_PACKAGE;return false;
}
static bool Threshold(Provider* p,uint64_t manager,uint32_t tag,uint32_t* value)
{
    *value=0;uint32_t count;
    if (!Pointer(manager,12) || !Read(p,manager+8,&count,4)) { if (!p->result.source_status) p->result.source_status=EP_C33_PROVIDER_LAYOUT;return false; }
    for (uint64_t i=0;i<count;i++) {
        uint64_t pointer,object;uint32_t handle;
        uint64_t offset=0x68+8*i;
        if (!Pointer(manager,offset+8)) { p->result.source_status=EP_C33_PROVIDER_LAYOUT;return false; }
        if (!Read(p,manager+offset,&pointer,8) || !Pointer(pointer,20) || !Read(p,pointer+16,&handle,4)) {
            if (!p->result.source_status) p->result.source_status=EP_C33_PROVIDER_LAYOUT;return false;
        }
        if (!Resolve(p,handle,&object)) return false;
        if (object!=p->target) continue;
        uint64_t row=0x26688+i*0x58;
        if (!Pointer(manager,row+4) || !Read(p,manager+row,&count,4)) { if (!p->result.source_status) p->result.source_status=EP_C33_PROVIDER_LAYOUT;return false; }
        for (uint64_t j=0;j<count;j++) {
            uint32_t key;uint64_t index=row+4+j*4;
            if (!Pointer(manager,index+4) || !Read(p,manager+index,&key,4)) { if (!p->result.source_status) p->result.source_status=EP_C33_PROVIDER_LAYOUT;return false; }
            if (key==tag) {
                index=row+0x30+j*4;
                if (!Pointer(manager,index+4)) { p->result.source_status=EP_C33_PROVIDER_LAYOUT;return false; }
                return Read(p,manager+index,value,4);
            }
        }
        return true;
    }
    return true;
}
static int Collect(void* context,const EpC33ResourceScopeView* v,EpC33AcquireSnapshot* out)
{
    auto* p=(Provider*)context;EpC33AcquireSnapshot result={};uint64_t key=0,manager=0;bool found=false;
    if (!Pointer(v->game,0x3483c38)) { p->result.source_status=EP_C33_PROVIDER_LAYOUT;return 0; }
    if (!MatchCode(p,v->game)) return 0;
    unsigned needed=(p->deferred ? 0u : 1u)|(p->release_only ? 0u : 2u)|(!p->release_only || p->by_object ? 4u : 0u);
    if (p->native && needed && !BindNative(p,v,needed)) return 0;
    if (!Select(p,v,&key,&found)) return 0;
    if (!found) { p->result.source_status=EP_C33_PROVIDER_NO_ENTITY;return 2; }
    if (!Package(p,v->game,key,result.package)) return 0;
    for (unsigned g=0;!p->release_only && g<EP_C33_ACQUIRE_GROUPS;g++) {
        uint32_t tag=D(result.package+0x808*g+0x800);if (!tag) continue;
        if (!Read(p,v->game+0x3326998,&manager,8) || !Threshold(p,manager,tag,&result.thresholds[g])) return 0;
    }
    *out=result;return 1;
}
static int Service(void* context,const EpC33ResourceScopeView* v,uint32_t op,uint64_t key)
{
    auto* p=(Provider*)context;
    if (!p->native) return p->ops.service(p->ops.context,v,op,key);
    if (!p->bound || !Ready(p)) return 0;
    uint64_t target=op==EP_RESOURCE_DISPOSE ? p->dispose : op==EP_RESOURCE_LOAD ? p->load : 0;
    if (!target) return 0;
    /* The saved sites set RCX=key, RDX=service table. They ignore RAX;
     * normal return means the call completed, not that loading is finished. */
    ((void (*)(uint64_t,uint64_t))(uintptr_t)target)(key,p->service_table);
    return Ready(p);
}
static int ProviderCall(const HfApi* api,HfMod* mod,uint64_t storage,
    uint64_t owner,uint64_t target,const EpC33ResourceProviderOps* input,EpC33ResourceProviderResult* out,bool release_only,uint32_t ordinal,uint32_t deferred,bool native=false,bool by_object=false)
{
    EpC33ResourceProviderOps ops={};if (input) ops=*input;
    if (!out) return EP_C33_CALL_ARGUMENT;memset(out,0,sizeof(*out));
    if (!api || api->version<13 || api->size<offsetof(HfApi,read_code)+sizeof(api->read_code) ||
        !api->build_id || !api->read || !api->read_code || (!input && !native) ||
        (release_only ? (by_object ? !Pointer(target,1) || (!native && !ops.resolve) : ordinal>=8) || deferred>1 || (!native && !deferred && !ops.service) : !Pointer(target,1) || (!native && (!ops.resolve || !ops.service)))) {
        out->source_status=EP_C33_PROVIDER_ARGUMENT;out->call.status=EP_C33_CALL_ARGUMENT;return out->call.status;
    }
    const char* build=api->build_id();if (!build || strcmp(build,"25480438")) {
        out->source_status=EP_C33_PROVIDER_CODE;out->call.status=EP_C33_CALL_ARGUMENT;return out->call.status;
    }
    Provider p={};p.read=api->read;p.read_code=api->read_code;p.mod=mod;p.owner=owner;p.target=target;p.ops=ops;
    p.release_only=release_only;p.ordinal=ordinal;p.deferred=deferred;p.native=native;p.by_object=by_object;
    EpC33ResourceServiceOps callbacks={&p,Collect,Service};
    int rc=release_only ? ep_component33_resource_release_services_call(mod,storage,owner,deferred,&callbacks,&p.result.call) :
        ep_component33_resource_acquire_services_call(mod,storage,owner,&callbacks,&p.result.call);
    *out=p.result;return rc;
}
int ep_component33_resource_acquire_provider_call(const HfApi* api,HfMod* mod,uint64_t storage,
    uint64_t owner,uint64_t target,const EpC33ResourceProviderOps* input,EpC33ResourceProviderResult* out)
{ return ProviderCall(api,mod,storage,owner,target,input,out,false,0,0); }
int ep_component33_resource_release_provider_call(const HfApi* api,HfMod* mod,uint64_t storage,
    uint64_t owner,uint32_t ordinal,uint32_t deferred,const EpC33ResourceProviderOps* input,EpC33ResourceProviderResult* out)
{ return ProviderCall(api,mod,storage,owner,0,input,out,true,ordinal,deferred); }
static int DrainEligible(void* context,const EpC33ResourceScopeView* v)
{
    auto* p=(Provider*)context;uint8_t code[sizeof(ep_c33_drain_source)];uint64_t manager;uint32_t blocked;
    if (!Pointer(v->game,0x346d538)) { p->result.source_status=EP_C33_PROVIDER_LAYOUT;return 0; }
    if (!Read(p,v->game+0x664b2f,code,sizeof(code),true)) return 0;
    if (memcmp(code,ep_c33_drain_source,sizeof(code))) { p->result.source_status=EP_C33_PROVIDER_CODE;return 0; }
    if (!Read(p,v->game+0x346d530,&manager,8)) return 0;
    if (!Pointer(manager,0x1910)) { p->result.source_status=EP_C33_PROVIDER_LAYOUT;return 0; }
    if (!Read(p,manager+0x190c,&blocked,4)) return 0;
    if (blocked) return 2;
    return p->native && !BindNative(p,v,1) ? 0 : 1;
}
static int DrainProviderCall(const HfApi* api,HfMod* mod,uint64_t storage,
    uint64_t owner,const EpC33ResourceProviderOps* input,EpC33ResourceProviderResult* out,bool native)
{
    EpC33ResourceProviderOps ops={};if (input) ops=*input;
    if (!out) return EP_C33_CALL_ARGUMENT;memset(out,0,sizeof(*out));
    if (!api || api->version<13 || api->size<offsetof(HfApi,read_code)+sizeof(api->read_code) ||
        !api->build_id || !api->read || !api->read_code || (!native && (!input || !ops.service))) {
        out->source_status=EP_C33_PROVIDER_ARGUMENT;out->call.status=EP_C33_CALL_ARGUMENT;return out->call.status;
    }
    const char* build=api->build_id();if (!build || strcmp(build,"25480438")) {
        out->source_status=EP_C33_PROVIDER_CODE;out->call.status=EP_C33_CALL_ARGUMENT;return out->call.status;
    }
    Provider p={};p.read=api->read;p.read_code=api->read_code;p.mod=mod;p.owner=owner;p.ops=ops;p.native=native;
    EpC33ResourceDrainOps callbacks={&p,DrainEligible,Service};
    int rc=ep_component33_resource_drain_services_call(mod,storage,owner,&callbacks,&p.result.call);
    *out=p.result;return rc;
}
int ep_component33_resource_drain_provider_call(const HfApi* api,HfMod* mod,uint64_t storage,
    uint64_t owner,const EpC33ResourceProviderOps* input,EpC33ResourceProviderResult* out)
{ return DrainProviderCall(api,mod,storage,owner,input,out,false); }
int ep_component33_resource_acquire_native_call(const HfApi* api,HfMod* mod,uint64_t storage,
    uint64_t owner,uint64_t target,EpC33ResourceProviderResult* out)
{ return ProviderCall(api,mod,storage,owner,target,nullptr,out,false,0,0,true); }
int ep_component33_resource_release_native_call(const HfApi* api,HfMod* mod,uint64_t storage,
    uint64_t owner,uint32_t ordinal,uint32_t deferred,EpC33ResourceProviderResult* out)
{ return ProviderCall(api,mod,storage,owner,0,nullptr,out,true,ordinal,deferred,true); }
int ep_component33_resource_drain_native_call(const HfApi* api,HfMod* mod,uint64_t storage,
    uint64_t owner,EpC33ResourceProviderResult* out)
{ return DrainProviderCall(api,mod,storage,owner,nullptr,out,true); }
int ep_component33_resource_defer_native_call(const HfApi* api,HfMod* mod,uint64_t storage,
    uint64_t owner,uint64_t target,EpC33ResourceProviderResult* out)
{ return ProviderCall(api,mod,storage,owner,target,nullptr,out,true,0,1,true,true); }
