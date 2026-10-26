#include "ep_component33_resources.h"
#include <string.h>
#include <limits.h>
struct ResourceFix { uint32_t kind,offset,next,rva; };
struct ResourceWindow { uint32_t rva,bytes,offset,width,target;uint8_t expected[16]; };
#include "ep_component33_resources_template.h"
static_assert(sizeof(ep_c33_resource_window_templates)/sizeof(ResourceWindow)<=EP_C33_RESOURCE_WINDOWS,"window capacity");
struct Header { uint64_t table;uint32_t capacity,pad;uint64_t empty;uint32_t seed,reserved;uint64_t queued,pad2; };
static_assert(sizeof(Header)==48,"resource layout");
static bool Pointer(uint64_t p,uint64_t bytes,uint64_t align)
{ return p && p<(UINT64_C(1)<<47) && !(p%align) && bytes<=(UINT64_C(1)<<47)-p; }
static bool Overlap(uint64_t a,uint64_t x,uint64_t b,uint64_t y) { return a<b+y && b<a+x; }
uint32_t ep_c33_resource_bytes(uint32_t c)
{ return c>=EP_C33_RESOURCE_MIN && c<=EP_C33_RESOURCE_MAX && !(c&(c-1)) ? 48+24*c : 0; }
static uint32_t Binding(const EpC33ResourceBinding* b)
{ uint32_t z=b ? ep_c33_resource_bytes(b->capacity) : 0;return z && !b->reserved && Pointer(b->address,z,16) ? z : 0; }
static uint64_t* Queue(void* p) { return (uint64_t*)((uint8_t*)p+48); }
static const uint64_t* Queue(const void* p) { return (const uint64_t*)((const uint8_t*)p+48); }
static EpC33ResourceEntry* Table(void* p,uint32_t c) { return (EpC33ResourceEntry*)((uint8_t*)p+48+8*c); }
static const EpC33ResourceEntry* Table(const void* p,uint32_t c) { return (const EpC33ResourceEntry*)((const uint8_t*)p+48+8*c); }
static uint32_t Find(const EpC33ResourceEntry* t,uint32_t c,uint32_t seed,uint64_t key)
{
    uint64_t h=key*seed;
    for (uint32_t i=0;i<c;i++) { uint32_t at=(uint32_t)(h+i)&(c-1);if (!t[at].key || t[at].key==key) return at; }
    return c;
}
static bool InQueue(const uint64_t* q,uint64_t count,uint64_t key)
{ for (uint64_t i=0;i<count;i++) if (q[i]==key) return true;return false; }
static int Check(const EpC33ResourceEntry* t,uint32_t c,uint32_t seed,const uint64_t* q,uint64_t count)
{
    if (count>c) return EP_RESOURCE_STATE;
    for (uint32_t i=0;i<c;i++) {
        if (!t[i].key) { if (t[i].references) return EP_RESOURCE_STATE; }
        else if (Find(t,c,seed,t[i].key)!=i) return EP_RESOURCE_STATE;
    }
    for (uint64_t i=0;i<count;i++) {
        if (!q[i] || InQueue(q,i,q[i])) return EP_RESOURCE_STATE;
        uint32_t at=Find(t,c,seed,q[i]);
        if (at==c || t[at].key!=q[i] || t[at].references) return EP_RESOURCE_STATE;
    }
    return EP_RESOURCE_OK;
}
static void Init(const EpC33ResourceBinding& b,void* p,uint32_t seed)
{
    memset(p,0,ep_c33_resource_bytes(b.capacity));Header* h=(Header*)p;
    h->table=b.address+48+8*b.capacity;h->capacity=b.capacity;h->seed=seed;
}
int ep_c33_resource_validate(const EpC33ResourceBinding* b,const void* p,uint32_t bytes)
{
    uint32_t size=Binding(b);if (!size || !p || (uintptr_t)p%8 || bytes!=size) return EP_RESOURCE_ARGUMENT;
    const Header* h=(const Header*)p;
    if (h->table!=b->address+48+8*b->capacity || h->capacity!=b->capacity || h->empty || h->pad || h->reserved || h->pad2) return EP_RESOURCE_STATE;
    return Check(Table(p,b->capacity),b->capacity,h->seed,Queue(p),h->queued);
}
int ep_c33_resource_migrate(const EpC33ResourceBinding* b,const EpC33ResourceSnapshot* s,void* out,uint32_t bytes)
{
    EpC33ResourceBinding copy={};if (b) copy=*b;b=&copy;
    uint32_t size=Binding(b);if (!size || !s || !out || (uintptr_t)out%8 || bytes!=size || s->reserved) return EP_RESOURCE_ARGUMENT;
    if (Overlap((uintptr_t)out,size,(uintptr_t)s,sizeof(*s))) return EP_RESOURCE_OVERLAP;
    if (Check(s->entries,128,s->seed,s->queue,s->queued)) return EP_RESOURCE_STATE;
    Init(*b,out,s->seed);auto* t=Table(out,b->capacity);
    for (const auto& e:s->entries) if (e.key) t[Find(t,b->capacity,s->seed,e.key)]=e;
    ((Header*)out)->queued=s->queued;memcpy(Queue(out),s->queue,(size_t)s->queued*8);return EP_RESOURCE_OK;
}
int ep_c33_resource_reserve(const EpC33ResourceBinding* b,void* p,uint32_t bytes,const uint64_t* keys,uint32_t count,void* scratch,uint32_t scratch_bytes)
{
    EpC33ResourceBinding copy={};if (b) copy=*b;b=&copy;
    int result=ep_c33_resource_validate(b,p,bytes);if (result) return result;
    if ((!keys && count) || count>EP_C33_RESOURCE_MAX || !scratch || (uintptr_t)scratch%8 || scratch_bytes!=bytes) return EP_RESOURCE_ARGUMENT;
    if (Overlap((uintptr_t)p,bytes,(uintptr_t)scratch,bytes) || (count &&
        (Overlap((uintptr_t)keys,(uint64_t)count*8,(uintptr_t)scratch,bytes) || Overlap((uintptr_t)keys,(uint64_t)count*8,(uintptr_t)p,bytes)))) return EP_RESOURCE_OVERLAP;
    Header h=*(const Header*)p;Init(*b,scratch,h.seed);auto* target=Table(scratch,b->capacity);const auto* source=Table(p,b->capacity);
    for (uint32_t i=0;i<b->capacity;i++) if (source[i].key && (source[i].references || InQueue(Queue(p),h.queued,source[i].key)))
        target[Find(target,b->capacity,h.seed,source[i].key)]=source[i];
    for (uint32_t i=0;i<count;i++) if (keys[i]) {
        uint32_t at=Find(target,b->capacity,h.seed,keys[i]);if (at==b->capacity) return EP_RESOURCE_CAPACITY;
        uint64_t additions=++Queue(scratch)[at];
        if (target[at].references>UINT64_MAX-additions) return EP_RESOURCE_CAPACITY;
        target[at].key=keys[i];
    }
    memset(Queue(scratch),0,(size_t)b->capacity*8);((Header*)scratch)->queued=h.queued;
    memcpy(Queue(scratch),Queue(p),(size_t)h.queued*8);
    memcpy(p,scratch,bytes);return EP_RESOURCE_OK;
}
int ep_c33_resource_execute(const EpC33ResourceBinding* binding,void* p,uint32_t bytes,
    const uint64_t* release_keys,uint32_t releases,const uint64_t* acquire_keys,uint32_t acquisitions,
    void* scratch,uint32_t scratch_bytes,EpC33ResourceService service,void* context)
{
    EpC33ResourceBinding b={};if (binding) b=*binding;
    int result=ep_c33_resource_validate(&b,p,bytes);if (result) return result;
    if (!service || !scratch || (uintptr_t)scratch%8 || bytes!=scratch_bytes ||
        releases>EP_RESOURCE_BATCH_MAX || acquisitions>EP_RESOURCE_BATCH_MAX ||
        (releases && !release_keys) || (acquisitions && !acquire_keys)) return EP_RESOURCE_ARGUMENT;
    if (Overlap((uintptr_t)p,bytes,(uintptr_t)scratch,bytes)) return EP_RESOURCE_OVERLAP;
    for (unsigned which=0;which<2;which++) {
        const uint64_t* keys=which ? acquire_keys : release_keys;uint32_t count=which ? acquisitions : releases;
        if (count && (Overlap((uintptr_t)keys,(uint64_t)count*8,(uintptr_t)p,bytes) ||
            Overlap((uintptr_t)keys,(uint64_t)count*8,(uintptr_t)scratch,bytes))) return EP_RESOURCE_OVERLAP;
    }
    /* Own immutable copies across service calls. No callback can change the
     * next operation by editing the caller's original sequence. */
    uint64_t old_keys[EP_RESOURCE_BATCH_MAX],new_keys[EP_RESOURCE_BATCH_MAX];
    if (releases) memcpy(old_keys,release_keys,(size_t)releases*8);
    if (acquisitions) memcpy(new_keys,acquire_keys,(size_t)acquisitions*8);
    auto* h=(Header*)p;auto* t=Table(p,b.capacity);auto* q=Queue(p);
    for (uint32_t i=0;i<acquisitions;i++) {
        if (!new_keys[i]) return EP_RESOURCE_ARGUMENT;
        uint32_t at=Find(t,b.capacity,h->seed,new_keys[i]);
        if (at==b.capacity || t[at].key!=new_keys[i]) return EP_RESOURCE_CAPACITY;
        uint64_t additions=1;for (uint32_t j=0;j<i;j++) additions+=new_keys[j]==new_keys[i];
        if (t[at].references>UINT64_MAX-additions) return EP_RESOURCE_CAPACITY;
    }
    for (uint32_t i=0;i<releases;i++) if (!old_keys[i]) return EP_RESOURCE_ARGUMENT;
    auto invoke=[&](uint32_t operation,uint64_t key) {
        memcpy(scratch,p,bytes);int completed=service(context,operation,key);
        if (memcmp(scratch,p,bytes)) return EP_RESOURCE_CALLBACK_STATE;
        return completed==1 ? EP_RESOURCE_OK : EP_RESOURCE_SERVICE;
    };
    for (uint32_t i=0;i<releases;i++) {
        uint32_t at=Find(t,b.capacity,h->seed,old_keys[i]);
        if (at==b.capacity || t[at].key!=old_keys[i] || !t[at].references) continue;
        if (!--t[at].references) { result=invoke(EP_RESOURCE_DISPOSE,old_keys[i]);if (result) return result; }
    }
    for (uint32_t i=0;i<acquisitions;i++) {
        uint32_t at=Find(t,b.capacity,h->seed,new_keys[i]);
        if (!t[at].references) {
            uint64_t queued=0;while (queued<h->queued && q[queued]!=new_keys[i]) queued++;
            if (queued<h->queued) { q[queued]=q[h->queued-1];--h->queued; }
            else { result=invoke(EP_RESOURCE_LOAD,new_keys[i]);if (result) return result; }
        }
        ++t[at].references;
    }
    return EP_RESOURCE_OK;
}
int ep_c33_resource_release(const EpC33ResourceBinding* binding,void* p,uint32_t bytes,
    const uint64_t* keys,uint32_t count,uint32_t deferred,void* scratch,uint32_t scratch_bytes,
    EpC33ResourceService service,void* context)
{
    if (deferred>1) return EP_RESOURCE_ARGUMENT;
    if (!deferred) return ep_c33_resource_execute(binding,p,bytes,keys,count,nullptr,0,scratch,scratch_bytes,service,context);
    EpC33ResourceBinding b={};if (binding) b=*binding;
    int result=ep_c33_resource_validate(&b,p,bytes);if (result) return result;
    if (!scratch || (uintptr_t)scratch%8 || scratch_bytes!=bytes || count>EP_RESOURCE_BATCH_MAX || (count && !keys)) return EP_RESOURCE_ARGUMENT;
    if (Overlap((uintptr_t)p,bytes,(uintptr_t)scratch,bytes) || (count &&
        (Overlap((uintptr_t)keys,(uint64_t)count*8,(uintptr_t)p,bytes) || Overlap((uintptr_t)keys,(uint64_t)count*8,(uintptr_t)scratch,bytes)))) return EP_RESOURCE_OVERLAP;
    uint64_t local[EP_RESOURCE_BATCH_MAX];if (count) memcpy(local,keys,(size_t)count*8);
    for (uint32_t i=0;i<count;i++) if (!local[i]) return EP_RESOURCE_ARGUMENT;
    memcpy(scratch,p,bytes);auto* h=(Header*)scratch;auto* t=Table(scratch,b.capacity);auto* q=Queue(scratch);
    for (uint32_t i=0;i<count;i++) {
        uint32_t at=Find(t,b.capacity,h->seed,local[i]);
        if (at==b.capacity || t[at].key!=local[i] || !t[at].references) continue;
        if (!--t[at].references) {
            if (h->queued==b.capacity) return EP_RESOURCE_CAPACITY;
            q[h->queued++]=local[i];
        }
    }
    memcpy(p,scratch,bytes);return EP_RESOURCE_OK;
}
int ep_c33_resource_drain(const EpC33ResourceBinding* binding,void* p,uint32_t bytes,
    void* scratch,uint32_t scratch_bytes,EpC33ResourceService service,void* context)
{
    EpC33ResourceBinding b={};if (binding) b=*binding;
    int result=ep_c33_resource_validate(&b,p,bytes);if (result) return result;
    if (!service || !scratch || (uintptr_t)scratch%8 || scratch_bytes!=bytes) return EP_RESOURCE_ARGUMENT;
    if (Overlap((uintptr_t)p,bytes,(uintptr_t)scratch,bytes)) return EP_RESOURCE_OVERLAP;
    auto* h=(Header*)p;if (!h->queued) return EP_RESOURCE_OK;
    memcpy(scratch,p,bytes);const auto* q=Queue(scratch);const uint64_t count=h->queued;
    for (uint64_t i=0;i<count;i++) {
        int completed=service(context,EP_RESOURCE_DISPOSE,q[i]);
        if (memcmp(scratch,p,bytes)) return EP_RESOURCE_CALLBACK_STATE;
        if (completed!=1) return EP_RESOURCE_SERVICE;
    }
    memset(Queue(p),0,(size_t)b.capacity*8);h->queued=0;return EP_RESOURCE_OK;
}
static uint64_t Target(const EpC33ResourceBinding& b,uint32_t rva)
{
    if (rva>=0x3798180 && rva<0x379819c) return b.address+rva-0x3798180;
    if (rva>=0x348ba88 && rva<0x348ba90) return b.address+32+rva-0x348ba88;
    if (rva>=0x3797550 && rva<0x3797950) return b.address+48+rva-0x3797550;
    if (rva>=0x3797960 && rva<0x3798160) return b.address+48+8*b.capacity+rva-0x3797960;
    return 0;
}
static void Put(uint8_t* p,int64_t v,uint32_t bytes) { for (uint32_t j=0;j<bytes;j++) p[j]=(uint8_t)((uint64_t)v>>(8*j)); }
int ep_c33_resource_consumer(uint32_t kind,const EpC33ConsumerAddresses* a,const EpC33ResourceBinding* b,EpComponent33Image* out)
{
    if (!out) return EP_RESOURCE_ARGUMENT;
    EpComponent33Image result={};EpC33ConsumerAddresses saved={};EpC33ResourceBinding binding={};
    if (a) saved=*a;if (b) binding=*b;memset(out,0,sizeof(*out));a=&saved;b=&binding;
    uint32_t size=Binding(b);if (!size || ep_component33_consumer_build(kind,a,&result)!=EP_PROPERTY_OK) return EP_RESOURCE_ARGUMENT;
    const uint64_t spans[][2]={{a->game_base,0x4000000},{a->code_address,4096},{a->component_address,0x2b8},{a->storage_address,0x490},{a->release_address,4096},{a->reject_address,1}};
    for (const auto& s:spans) if (Overlap(b->address,size,s[0],s[1])) return EP_RESOURCE_OVERLAP;
    for (const auto& f:ep_c33_resource_fixups) if (f.kind==kind) {
        int64_t delta=(int64_t)Target(*b,f.rva)-(int64_t)(a->code_address+f.next);
        if (delta<INT32_MIN || delta>INT32_MAX) return EP_RESOURCE_REL32;
        Put(result.data+f.offset,delta,4);
    }
    *out=result;return EP_RESOURCE_OK;
}
int ep_c33_resource_windows(uint64_t game,const EpC33ResourceBinding* input,uint64_t reset,EpC33ResourcePlan* out)
{
    if (!out) return EP_RESOURCE_ARGUMENT;
    EpC33ResourceBinding b={};if (input) b=*input;memset(out,0,sizeof(*out));uint32_t size=Binding(&b);
    if (!size || !Pointer(game,0x4000000,4096) || !Pointer(reset,4096,16)) return EP_RESOURCE_ARGUMENT;
    if (Overlap(b.address,size,game,0x4000000) || Overlap(b.address,size,reset,4096)) return EP_RESOURCE_OVERLAP;
    EpC33ResourcePlan result={};
    for (const auto& s:ep_c33_resource_window_templates) {
        uint32_t index=0;while (index<result.count && result.windows[index].rva!=s.rva) index++;
        auto& w=result.windows[index];
        if (index==result.count) { result.count++;w.rva=s.rva;w.bytes=s.bytes;memcpy(w.expected,s.expected,s.bytes);memcpy(w.replacement,s.expected,s.bytes); }
        int64_t value=s.target==1 ? b.capacity : s.target==2 ? 8*b.capacity :
            (int64_t)(s.target==3 ? reset : Target(b,s.target))-(int64_t)(game+s.rva+s.bytes);
        if (value<INT32_MIN || value>INT32_MAX) return EP_RESOURCE_REL32;Put(w.replacement+s.offset,value,s.width);
    }
    *out=result;return EP_RESOURCE_OK;
}
