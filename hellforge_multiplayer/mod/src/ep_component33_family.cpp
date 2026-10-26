#include "ep_component33_family.h"
#include <windows.h>
#include <string.h>
struct C33Family {
    HfMod* owner;
    EpComponent33FamilyInfo info;
    EpC33FamilyResources resources;
};
static C33Family c33Families[EP_C33_FAMILY_SLOTS];
static SRWLOCK c33Lock=SRWLOCK_INIT;
static uint64_t c33Sequence;
static C33Family* C33Find(HfMod* owner,uint64_t id)
{
    if (owner && id) for (auto& g:c33Families) if (g.owner==owner && g.info.handle==id) return &g;
    return nullptr;
}
static void C33Info(C33Family* g,EpComponent33FamilyInfo* out)
{
    *out=g->info;out->reserved_images=0;
    for (auto& c:out->code) if (c.handle) {
        EpSessionCodeInfo actual;
        if (ep_session_code_info(g->owner,c.handle,&actual)) c=actual;
        out->reserved_images++;
    }
}
int ep_component33_family_info(HfMod* owner,uint64_t id,EpComponent33FamilyInfo* out)
{
    if (!out) return 0;memset(out,0,sizeof(*out));
    AcquireSRWLockShared(&c33Lock);auto* g=C33Find(owner,id);
    if (g) C33Info(g,out);
    ReleaseSRWLockShared(&c33Lock);return g!=nullptr;
}
int ep_component33_family_resources(HfMod* owner,uint64_t id,EpC33FamilyResources* out)
{
    if (!out) return 0;memset(out,0,sizeof(*out));
    AcquireSRWLockShared(&c33Lock);auto* g=C33Find(owner,id);int ok=g && g->resources.binding.address;
    if (ok) *out=g->resources;ReleaseSRWLockShared(&c33Lock);return ok;
}
static int C33Cancel(C33Family* g)
{
    int ok=1;
    for (unsigned i=EP_C33_FAMILY_IMAGES;i--;) if (g->info.code[i].handle) {
        if (ep_session_code_discard(g->owner,g->info.code[i].handle)) memset(&g->info.code[i],0,sizeof(g->info.code[i]));
        else ok=0;
    }
    if (ok) memset(g,0,sizeof(*g));
    else {
        g->info.state=EP_C33_CLEANUP_REQUIRED;
        memset(&g->info.owner_window,0,sizeof(g->info.owner_window));
        memset(g->info.reader_windows,0,sizeof(g->info.reader_windows));
        memset(g->info.outer_windows,0,sizeof(g->info.outer_windows));
        memset(&g->resources.windows,0,sizeof(g->resources.windows));
    }
    return ok;
}
int ep_component33_family_cancel(HfMod* owner,uint64_t id)
{
    int ok=0;AcquireSRWLockExclusive(&c33Lock);auto* g=C33Find(owner,id);
    if (g && (g->info.state==EP_C33_PREPARED || g->info.state==EP_C33_CLEANUP_REQUIRED)) ok=C33Cancel(g);
    ReleaseSRWLockExclusive(&c33Lock);return ok;
}
int ep_component33_family_retain(HfMod* owner,uint64_t id)
{
    int ok=0;AcquireSRWLockExclusive(&c33Lock);auto* g=C33Find(owner,id);
    if (g && g->info.state==EP_C33_PREPARED) {
        uint64_t handles[EP_C33_FAMILY_IMAGES];
        for (unsigned i=0;i<EP_C33_FAMILY_IMAGES;i++) handles[i]=g->info.code[i].handle;
        if (ep_session_code_retain_set(owner,handles,EP_C33_FAMILY_IMAGES)) { g->info.state=EP_C33_RETAINED;ok=1; }
    }
    ReleaseSRWLockExclusive(&c33Lock);return ok;
}
static bool C33Overlap(uint64_t a,uint64_t n,uint64_t b,uint64_t m)
{ return a<b+m && b<a+n; }
static EpPropertyResult C33Prepare(const HfApi* api,HfMod* owner,const EpComponent33FamilyBindings* input,const EpC33ResourceBinding* resources,EpComponent33FamilyInfo* out)
{
    if (!out) return EP_PROPERTY_ARGUMENT;
    EpComponent33FamilyBindings a={};if (input) a=*input;
    memset(out,0,sizeof(*out));if (!input || !owner) return EP_PROPERTY_ARGUMENT;
    /* Validate the external addresses before reserving any family state. */
    const uint64_t external[][3]={{a.game_base,0x3483c38,4096},{a.component_address,0x2b8,8},
        {a.storage_address,0x490,16},{a.reject_address,1,1}};
    for (const auto& r:external) if (!r[0] || r[0]>=(UINT64_C(1)<<47) || r[1]>(UINT64_C(1)<<47)-r[0] || r[0]%r[2]) return EP_PROPERTY_POINTER;
    for (unsigned i=1;i<4;i++) if (C33Overlap(external[i][0],external[i][1],(uintptr_t)c33Families,sizeof(c33Families))) return EP_PROPERTY_OVERLAP;
    uint32_t resource_bytes=resources ? ep_c33_resource_bytes(resources->capacity) : 0;
    if (resources) {
        uint64_t p=resources->address;
        if (!resource_bytes || resources->reserved || !p || p>=(UINT64_C(1)<<47) || resource_bytes>(UINT64_C(1)<<47)-p || p%16) return EP_PROPERTY_POINTER;
        if (C33Overlap(p,resource_bytes,a.game_base,0x4000000) || C33Overlap(p,resource_bytes,(uintptr_t)c33Families,sizeof(c33Families))) return EP_PROPERTY_OVERLAP;
        for (unsigned i=1;i<4;i++) if (C33Overlap(p,resource_bytes,external[i][0],external[i][1])) return EP_PROPERTY_OVERLAP;
    }
    C33Family* g=nullptr;AcquireSRWLockExclusive(&c33Lock);
    if (c33Sequence!=UINT64_MAX) for (auto& slot:c33Families) if (!slot.info.handle) {
        g=&slot;g->owner=owner;g->info.handle=++c33Sequence;g->info.state=EP_C33_PREPARING;
        if (resources) g->resources.binding=*resources;break;
    }
    ReleaseSRWLockExclusive(&c33Lock);if (!g) return EP_PROPERTY_RESERVE;
    EpPropertyResult result=EP_PROPERTY_OK;EpSessionCodeInfo code[EP_C33_FAMILY_IMAGES]={};
    for (unsigned i=0;i<EP_C33_FAMILY_IMAGES;i++) {
        uint32_t bytes=i<14 ? ep_component33_image_bytes(i+1) : i==14 ? ep_component33_readers_image_bytes() : i<19 ? ep_component33_consumer_bytes(i-14) : ep_component33_outer_image_bytes();
        if (!ep_session_code_reserve(api,owner,a.desired_code[i],bytes,&code[i])) { result=EP_PROPERTY_RESERVE;break; }
        AcquireSRWLockExclusive(&c33Lock);g->info.code[i]=code[i];ReleaseSRWLockExclusive(&c33Lock);
    }
    /* Check the complete dependency set and the mutable next slots before any
     * pages are sealed. Individual emitters check their own protected sources. */
    SYSTEM_INFO system;GetSystemInfo(&system);
    for (unsigned i=0;result==EP_PROPERTY_OK && i<EP_C33_FAMILY_IMAGES;i++) {
        uint64_t n=(code[i].bytes+system.dwPageSize-1)/system.dwPageSize*system.dwPageSize;
        for (unsigned j=1;j<4;j++) if (C33Overlap(code[i].base,n,external[j][0],external[j][1]) ||
            C33Overlap(code[i].next_pointer,8,external[j][0],external[j][1])) result=EP_PROPERTY_OVERLAP;
        if (resources && (C33Overlap(code[i].base,n,resources->address,resource_bytes) ||
            C33Overlap(code[i].next_pointer,8,resources->address,resource_bytes))) result=EP_PROPERTY_OVERLAP;
    }
    EpComponent33OwnerPatch owner_window={};EpComponent33ReaderPlan readers={};EpComponent33OuterPlan outer={};
    EpC33ResourcePlan resource_windows={};
    if (result==EP_PROPERTY_OK && resources) {
        int r=ep_c33_resource_windows(a.game_base,resources,code[7].base,&resource_windows);
        if (r!=EP_RESOURCE_OK) result=r==EP_RESOURCE_REL32 ? EP_PROPERTY_REL32 : EP_PROPERTY_OVERLAP;
    }
    if (result==EP_PROPERTY_OK) result=ep_component33_owner_patch_build(a.game_base,code[13].base,&owner_window);
    if (result==EP_PROPERTY_OK) {
        EpComponent33ReaderAddresses r={a.game_base,code[14].base,a.component_address,a.storage_address,code[7].base,a.reject_address};
        result=ep_component33_readers_build(&r,&readers);
    }
    if (result==EP_PROPERTY_OK) {
        EpC33ConsumerAddresses r={a.game_base,code[19].base,a.component_address,a.storage_address,code[18].base,a.reject_address};
        result=ep_component33_outer_build(&r,&outer);
    }
    for (unsigned i=0;result==EP_PROPERTY_OK && i<EP_C33_FAMILY_IMAGES;i++) {
        EpComponent33Image image={};
        if (i<14) {
            EpComponent33Addresses b={a.game_base,code[i].base,a.component_address,a.storage_address,code[0].base,a.reject_address};
            result=ep_component33_image_build(i+1,&b,&image);
        } else if (i==14) image=readers.bridge;
        else if (i<19) {
            EpC33ConsumerAddresses b={a.game_base,code[i].base,a.component_address,a.storage_address,code[18].base,a.reject_address};
            if (resources) {
                int r=ep_c33_resource_consumer(i-14,&b,resources,&image);
                if (r!=EP_RESOURCE_OK) result=r==EP_RESOURCE_REL32 ? EP_PROPERTY_REL32 : EP_PROPERTY_OVERLAP;
            } else result=ep_component33_consumer_build(i-14,&b,&image);
        } else image=outer.bridge;
        if (result!=EP_PROPERTY_OK) break;
        int sealed;
        if (i+1==EP_COMPONENT33_PROPERTY) {
            EpSessionGsCheck gs={1,image.code_bytes-5,(uintptr_t)a.game_base+0x21044a0};
            sealed=ep_session_code_seal_component33_property(owner,code[i].handle,image.data,image.bytes,image.table_offset,&gs);
        } else sealed=ep_session_code_seal_table(owner,code[i].handle,image.data,image.bytes,image.table_offset,image.function_count);
        if (!sealed) result=EP_PROPERTY_SEAL;
    }
    AcquireSRWLockExclusive(&c33Lock);
    if (result==EP_PROPERTY_OK) {
        g->info.owner_window=owner_window;memcpy(g->info.reader_windows,readers.windows,sizeof(readers.windows));
        memcpy(g->info.outer_windows,outer.windows,sizeof(outer.windows));
        g->resources.windows=resource_windows;
        g->info.state=EP_C33_PREPARED;
    } else if (!C33Cancel(g)) result=EP_PROPERTY_CLEANUP;
    if (g->info.handle) C33Info(g,out);
    ReleaseSRWLockExclusive(&c33Lock);return result;
}
EpPropertyResult ep_component33_family_prepare(const HfApi* api,HfMod* owner,const EpComponent33FamilyBindings* input,EpComponent33FamilyInfo* out)
{ return C33Prepare(api,owner,input,nullptr,out); }
EpPropertyResult ep_component33_family_prepare_resources(const HfApi* api,HfMod* owner,const EpComponent33FamilyBindings* input,const EpC33ResourceBinding* resource,EpComponent33FamilyInfo* out)
{
    if (!resource) { if (out) memset(out,0,sizeof(*out));return EP_PROPERTY_ARGUMENT; }
    EpC33ResourceBinding copy=*resource;return C33Prepare(api,owner,input,&copy,out);
}
