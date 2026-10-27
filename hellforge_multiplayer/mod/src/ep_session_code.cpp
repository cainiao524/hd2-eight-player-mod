/* C-compatible so the offline test can include the actual HellForge loader. */
#include "ep_session_code.h"
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <string.h>

typedef struct EpCodeSlot {
    uint64_t handle;
    HfMod* owner;
    uint8_t* base;
    void* next;
    PRUNTIME_FUNCTION table;
    int (*hook)(HfMod*, uintptr_t, void*, void**, int32_t);
    uint32_t bytes, allocation_bytes, state, registered, pinned;
} EpCodeSlot;
static SRWLOCK epCodeLock = SRWLOCK_INIT;
/* Never move slots: HellForge retains &slot.next and may rewrite it later. */
static EpCodeSlot epCodeSlots[EP_SESSION_CODE_SLOTS];
static uint64_t epCodeSequence;

static EpCodeSlot* EpCodeFind(HfMod* owner, uint64_t handle)
{
    if (!owner || !handle) return NULL;
    for (unsigned i=0; i<EP_SESSION_CODE_SLOTS; ++i)
        if (epCodeSlots[i].handle==handle && epCodeSlots[i].owner==owner) return &epCodeSlots[i];
    return NULL;
}
static void EpCodeInfo(const EpCodeSlot* s, EpSessionCodeInfo* out)
{
    out->handle=s->handle; out->base=(uintptr_t)s->base; out->next_pointer=(uintptr_t)&s->next;
    out->bytes=s->bytes; out->state=s->state; out->registered=s->registered; out->pinned=s->pinned;
}
int ep_session_code_info(HfMod* owner, uint64_t handle, EpSessionCodeInfo* out)
{
    int ok=0;
    if (!out) return 0;
    memset(out,0,sizeof *out);
    AcquireSRWLockShared(&epCodeLock);
    EpCodeSlot* s=EpCodeFind(owner,handle);
    if (s) { EpCodeInfo(s,out); ok=1; }
    ReleaseSRWLockShared(&epCodeLock);
    return ok;
}
int ep_session_code_reserve(const HfApi* api, HfMod* owner, uintptr_t desired,
                            uint32_t bytes, EpSessionCodeInfo* out)
{
    int ok=0; SYSTEM_INFO system;
    if (out) memset(out,0,sizeof *out);
    if (!out || !owner || !api || api->version<13 ||
        api->size<offsetof(HfApi,hook_ex)+sizeof(api->hook_ex) || !api->hook_ex || !api->build_id ||
        !bytes || bytes>EP_SESSION_CODE_MAX_BYTES) return 0;
    const char* build=api->build_id();
    if (!build || strcmp(build,"25480438")) return 0;
    GetSystemInfo(&system);
    if (desired && (desired%system.dwAllocationGranularity || desired<0x10000 ||
                    desired>=((uint64_t)1<<47) || bytes>((uint64_t)1<<47)-desired)) return 0;
    AcquireSRWLockExclusive(&epCodeLock);
    if (epCodeSequence!=UINT64_MAX) for (unsigned i=0;i<EP_SESSION_CODE_SLOTS;i++)
    {
        EpCodeSlot* s=&epCodeSlots[i];
        if (s->handle) continue;
        uint8_t* base=(uint8_t*)VirtualAlloc((void*)desired,bytes,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
        if (!base) break;
        if ((desired && (uintptr_t)base!=desired) || (uintptr_t)base>=((uint64_t)1<<47))
        { VirtualFree(base,0,MEM_RELEASE); break; }
        s->handle=++epCodeSequence; s->owner=owner; s->base=base; s->bytes=bytes;
        s->allocation_bytes=(bytes+system.dwPageSize-1)/system.dwPageSize*system.dwPageSize;
        s->hook=api->hook_ex; s->state=EP_CODE_RESERVED;
        EpCodeInfo(s,out); ok=1; break;
    }
    ReleaseSRWLockExclusive(&epCodeLock);
    return ok;
}
static int EpCodeNonvolatile(unsigned reg)
{ return reg==3 || reg==5 || reg==6 || reg==7 || (reg>=12 && reg<=15); }
static int EpCodeMetadata(const uint8_t* p, uint32_t bytes, uint32_t at, uint32_t count, const EpSessionGsCheck* gs, int handler_kind)
{
    RUNTIME_FUNCTION functions[EP_SESSION_CODE_MAX_FUNCTIONS];
    if (!count || count>EP_SESSION_CODE_MAX_FUNCTIONS || (at&3) || at>bytes || bytes-at!=count*sizeof(RUNTIME_FUNCTION)) return 0;
    memcpy(functions,p+at,count*sizeof(RUNTIME_FUNCTION));
    if (functions[0].BeginAddress) return 0;
    if (handler_kind==1 && (!gs || count!=3 || gs->function_index!=1 ||
        functions[0].UnwindData!=functions[2].UnwindData ||
        functions[2].BeginAddress!=gs->handler_offset || functions[2].EndAddress!=gs->handler_offset+5)) return 0;
    if (handler_kind==2 && (!gs || count!=11 || gs->function_index!=7 ||
        functions[10].BeginAddress!=gs->handler_offset || functions[10].EndAddress!=gs->handler_offset+5)) return 0;
    if (handler_kind==3 && (!gs || count!=7 || gs->function_index!=1 ||
        functions[6].BeginAddress!=gs->handler_offset || functions[6].EndAddress!=gs->handler_offset+5)) return 0;
    if (handler_kind==4 && (!gs || count!=5 || gs->function_index!=1 ||
        functions[4].BeginAddress!=gs->handler_offset || functions[4].EndAddress!=gs->handler_offset+5)) return 0;
    if (handler_kind==5 && (!gs || count!=7 || gs->function_index!=1 ||
        functions[6].BeginAddress!=gs->handler_offset || functions[6].EndAddress!=gs->handler_offset+5)) return 0;
    if (handler_kind==6 && (!gs || count!=12 || gs->function_index!=1 ||
        functions[11].BeginAddress!=gs->handler_offset || functions[11].EndAddress!=gs->handler_offset+5)) return 0;
    if (handler_kind==7 && (!gs || count!=8 || gs->function_index!=1 ||
        functions[7].BeginAddress!=gs->handler_offset || functions[7].EndAddress!=gs->handler_offset+5)) return 0;
    if (handler_kind==8 && (!gs || count!=15 || gs->function_index!=5 ||
        functions[14].BeginAddress!=gs->handler_offset || functions[14].EndAddress!=gs->handler_offset+5)) return 0;
    if (handler_kind==9 && (!gs || count!=7 || gs->function_index!=1 ||
        functions[6].BeginAddress!=gs->handler_offset || functions[6].EndAddress!=gs->handler_offset+5)) return 0;
    if (handler_kind==10) {
        if (!gs || count!=10 || gs->function_index!=1 || functions[9].BeginAddress!=gs->handler_offset ||
            functions[9].EndAddress!=gs->handler_offset+5 || functions[8].EndAddress<=functions[8].BeginAddress ||
            functions[8].EndAddress-functions[8].BeginAddress!=12 ||
            functions[8].EndAddress>at) return 0;
        const uint8_t* call=p+functions[8].BeginAddress;uint64_t target;memcpy(&target,call+2,8);
        if (call[0]!=0x48 || call[1]!=0xb8 || call[10]!=0xff || call[11]!=0xe0 ||
            target<0x10000 || target>=(UINT64_C(1)<<47)) return 0;
    }
    if (gs && (gs->function_index>=count || gs->handler_target<0x10000 ||
        gs->handler_target>=((uint64_t)1<<47) || gs->handler_offset>at || at-gs->handler_offset<5 ||
        (gs->handler_target>=(uintptr_t)p && gs->handler_target<(uintptr_t)p+bytes))) return 0;
    for (uint32_t f=0;f<count;f++) {
        RUNTIME_FUNCTION rf=functions[f];
        if (rf.EndAddress<=rf.BeginAddress || (f && rf.BeginAddress<functions[f-1].EndAddress)) return 0;
    }
    for (uint32_t f=0;f<count;f++) {
    RUNTIME_FUNCTION rf=functions[f]; uint32_t end=at;
    if (rf.UnwindData<functions[count-1].EndAddress || (rf.UnwindData&3) || rf.UnwindData>at || at-rf.UnwindData<4) return 0;
    for (uint32_t other=0;other<count;other++) if (other!=f) {
        uint32_t offset=functions[other].UnwindData;
        if (offset==rf.UnwindData && !(handler_kind==1 && f!=1 && other!=1 &&
            !memcmp(p+offset,"\1\0\0\0",4))) return 0;
        if (offset>rf.UnwindData && offset<end) end=offset;
    }
    const uint8_t* u=p+rf.UnwindData;
    const uint32_t body=4u+((u[2]+1u)&~1u)*2u;
    // Isolated attachment and replacement each have a complete prologue/cookie,
    // so they must be validated as separate GS roots, never as handler-free rows
    // or a synthetic chain to a frame established by a different entry.
    const int has_gs=gs && (f==gs->function_index || (handler_kind==3 && (f==3 || f==5)));
    if ((has_gs ? u[0]!=25 : (u[0]!=1 && u[0]!=33)) || u[3] || u[1]>rf.EndAddress-rf.BeginAddress ||
        body+(u[0]==33?12u:has_gs?8u:0u)!=end-rf.UnwindData) return 0;
    if (handler_kind==3 && f!=1 && f!=3 && f!=5 && (u[0]!=1 || u[1] || u[2])) return 0;
    if (handler_kind==4 && ((f==2 || f==3) ? u[0]!=33 : f!=1 && u[0]!=1)) return 0;
    if (handler_kind==5 && ((f>=2 && f<=5) ? u[0]!=33 : f!=1 && u[0]!=1)) return 0;
    if (handler_kind==6 && ((f==2 || (f>=5 && f<=10)) ? u[0]!=33 : f!=1 && u[0]!=1)) return 0;
    if (handler_kind==7 && ((f>=2 && f<=4) ? u[0]!=33 : f!=1 && u[0]!=1)) return 0;
    if (handler_kind==8 && ((f==2 || f==3 || (f>=6 && f<=9)) ? u[0]!=33 : f!=5 && u[0]!=1)) return 0;
    if (handler_kind==9 && ((f==2 || f==3) ? u[0]!=33 : f!=1 && u[0]!=1)) return 0;
    if (handler_kind==10 && ((f>=2 && f<=7) ? u[0]!=33 : f!=1 && u[0]!=1)) return 0;
    if (has_gs) {
        /* Exact original fixed-frame contract. No alignment extensions,
         * chained handler, invented cookie offset or scope-table interpretation. */
        const uint8_t expected[28]={0x19,0x31,0x0c,0,0x22,0x68,7,0,0x1d,0x74,0x15,0,
            0x1d,0x64,0x14,0,0x1d,0x54,0x13,0,0x1d,0x34,0x12,0,0x1d,0xf2,0x16,0xe0};
        const uint8_t property[28]={0x19,0x2b,0x0c,0,0x1c,0x64,0x12,0,0x1c,0x54,0x11,0,
            0x1c,0x34,0x10,0,0x1c,0x92,0x18,0xf0,0x16,0xe0,0x14,0xd0,0x12,0xc0,0x10,0x70};
        const uint8_t loadout[32]={0x19,0x2f,0x0d,0,0x20,0x88,6,0,0x1b,0x78,7,0,
            0x17,0x68,8,0,0x13,0x64,0x15,0,0x13,0x34,0x14,0,0x13,1,0x12,0,0x0c,0x70,0,0};
        const uint8_t setup[36]={0x19,0x35,0x0f,0,0x27,0x68,0x14,0,0x23,0x74,0x33,0,
            0x23,0x64,0x32,0,0x23,0x34,0x31,0,0x23,1,0x2a,0,0x18,0xf0,0x16,0xe0,
            0x14,0xd0,0x12,0xc0,0x10,0x50,0,0};
        uint32_t handler,cookie;int32_t delta;int thunk=0;
        const uint8_t refresh[12]={0x19,0x18,3,0,9,1,0x14,0,2,0x70,0,0};
        const uint8_t records[12]={0x19,0x21,3,0,0xf,1,0x92,2,2,0xd0,0,0};
        const uint8_t frame_update[36]={0x19,0x3b,0x0f,0,0x2a,0x98,0x40,0,0x25,0x88,0x41,0,
            0x20,0x78,0x42,0,0x1c,1,0x88,0,0x0e,0xf0,0x0c,0xe0,0x0a,0xd0,8,0xc0,6,0x70,5,0x60,4,0x50,0,0};
        const uint8_t mode[20]={0x19,0x23,7,0,0x15,1,0x26,0,0x0a,0xf0,8,0xc0,6,0x60,5,0x30,4,0x50,0,0};
        const uint8_t state[24]={0x19,0x26,9,0,0x17,0x64,0x17,0,0x17,0x54,0x16,0,0x17,0x34,0x15,0,0x17,1,0x12,0,0x10,0x70,0,0};
        const uint8_t resource_main[40]={0x19,0x41,0x11,0x0,0x33,0xc8,0x13,0x0,0x2b,0x68,0x19,0x0,0x26,0x74,0x3d,0x0,0x26,0x64,0x3c,0x0,0x26,0x34,0x3b,0x0,0x26,0x1,0x34,0x0,0x18,0xf0,0x16,0xe0,0x14,0xd0,0x12,0xc0,0x10,0x50,0x0,0x0};
        const uint8_t player_join[16]={0x19,0x2b,5,0,0x1a,1,0x60,5,5,0xf0,3,0x30,2,0x50,0,0};
        const uint8_t* expected_unwind=handler_kind==10 ? player_join : handler_kind==9 ? resource_main : handler_kind==8 ? state : handler_kind==7 ? mode : handler_kind==6 ? frame_update : handler_kind==5 ? records : handler_kind==4 ? refresh : handler_kind==3 ? setup : handler_kind==2 ? loadout : handler_kind==1 ? property : expected;
        const uint32_t expected_bytes=handler_kind==10 ? 16u : handler_kind==9 ? 40u : handler_kind==8 ? 24u : handler_kind==7 ? 20u : handler_kind==6 ? 36u : handler_kind>=4 ? 12u : handler_kind==3 ? 36u : handler_kind==2 ? 32u : 28u;
        if (body!=expected_bytes || memcmp(u,expected_unwind,expected_bytes)) return 0;
        memcpy(&handler,u+body,4);memcpy(&cookie,u+body+4,4);
        if (handler!=gs->handler_offset || cookie!=(handler_kind==10 ? 0x2aa0u : handler_kind==9 ? 0x128u : handler_kind==8 ? 0x60u : handler_kind==7 ? 0xd0u : handler_kind==6 ? 0x3f0u : handler_kind==5 ? 0x1460u : handler_kind==4 ? 112u : handler_kind==3 ? 304u : handler_kind==2 ? 80u : handler_kind==1 ? 64u : 96u) || p[handler]!=0xe9) return 0;
        memcpy(&delta,p+handler+1,4);
        if ((int64_t)(uintptr_t)p+handler+5+delta!=(int64_t)gs->handler_target) return 0;
        for (uint32_t j=0;j<count;j++) if (j!=f && functions[j].BeginAddress==handler &&
            functions[j].EndAddress==handler+5 && functions[j].UnwindData<=at-4 &&
            !memcmp(p+functions[j].UnwindData,"\1\0\0\0",4)) thunk=1;
        if (!thunk) return 0;
    }
    if (u[0]==33) {
        /* Only exact earlier rows of this owned table may be chain parents.
         * Refresh's GS parent requires the exact root profile checked above;
         * external, cyclic and forward chains remain forbidden. */
        int parent=0;
        if (handler_kind==4 && memcmp(u+body,&functions[1],sizeof(RUNTIME_FUNCTION))) return 0;
        if (handler_kind==5 && memcmp(u+body,&functions[(f==3 || f==4) ? 2 : 1],sizeof(RUNTIME_FUNCTION))) return 0;
        if (handler_kind==7 && memcmp(u+body,&functions[f==3 ? 2 : 1],sizeof(RUNTIME_FUNCTION))) return 0;
        if (handler_kind==9 && memcmp(u+body,&functions[1],sizeof(RUNTIME_FUNCTION))) return 0;
        if (handler_kind==10 && memcmp(u+body,&functions[f==7 ? 6 : (f==3 || f==4) ? 2 : 1],sizeof(RUNTIME_FUNCTION))) return 0;
        if (handler_kind==8) {
            const unsigned parents[15]={0,0,1,1,0,0,5,6,6,5,0,0,0,0,0};
            if (memcmp(u+body,&functions[parents[f]],sizeof(RUNTIME_FUNCTION))) return 0;
        }
        if (handler_kind==6) {
            const unsigned parents[12]={0,0,1,0,0,4,5,6,6,5,4,0};
            if (memcmp(u+body,&functions[parents[f]],sizeof(RUNTIME_FUNCTION))) return 0;
        }
        for(uint32_t previous=0;previous<f;previous++) if (!memcmp(u+body,&functions[previous],sizeof(RUNTIME_FUNCTION))) parent=1;
        if (!parent) return 0;
    }
    unsigned prior=u[1];
    for (unsigned i=0;i<u[2];i++)
    {
        unsigned offset=u[4+2*i], op=u[5+2*i]&15, info=u[5+2*i]>>4;
        if (offset>prior) return 0;
        prior=offset;
        if (op==0) { if (!EpCodeNonvolatile(info)) return 0; }
        else if (op==1) { /* ALLOC_LARGE: bounded 16-bit scaled form only. */
            if (info || ++i>=u[2] || !(u[4+2*i] || u[5+2*i])) return 0;
        }
        else if (op==8) { /* SAVE_XMM128; volatile XMM0..5 are not unwind saves. */
            if (info<6 || ++i>=u[2]) return 0;
        }
        else if (op==2) { /* ALLOC_SMALL, size encoded in info */ }
        else if (op==4) { if (!EpCodeNonvolatile(info) || ++i>=u[2]) return 0; }
        else return 0;
    }
    }
    return 1;
}
int ep_session_code_seal(HfMod* owner, uint64_t handle, const void* image, uint32_t bytes, uint32_t tableAt)
{ return ep_session_code_seal_table(owner,handle,image,bytes,tableAt,1); }
int ep_session_code_seal_table(HfMod* owner, uint64_t handle, const void* image, uint32_t bytes, uint32_t tableAt, uint32_t count)
{ return ep_session_code_seal_gs_table(owner,handle,image,bytes,tableAt,count,NULL); }
static int EpCodeSeal(HfMod* owner, uint64_t handle, const void* image, uint32_t bytes, uint32_t tableAt, uint32_t count, const EpSessionGsCheck* input,int handler_kind)
{
    int ok=0; DWORD old;
    EpSessionGsCheck profile;const EpSessionGsCheck* gs=NULL;
    if (!image) return 0;
    if (input) {profile=*input;gs=&profile;}
    AcquireSRWLockExclusive(&epCodeLock);
    EpCodeSlot* s=EpCodeFind(owner,handle);
    if (!s || s->state!=EP_CODE_RESERVED || bytes!=s->bytes) goto done;
    /* Owned copy removes any later dependency on the caller's input buffer. */
    memmove(s->base,image,bytes);
    if (!EpCodeMetadata(s->base,bytes,tableAt,count,gs,handler_kind)) goto done;
    s->table=(PRUNTIME_FUNCTION)(s->base+tableAt);
    s->state=EP_CODE_FAILED;
    if (!VirtualProtect(s->base,bytes,PAGE_EXECUTE_READ,&old) ||
        !FlushInstructionCache(GetCurrentProcess(),s->base,bytes) ||
        !RtlAddFunctionTable(s->table,count,(DWORD64)s->base)) goto done;
    s->registered=1; s->state=EP_CODE_READY; ok=1;
done:
    ReleaseSRWLockExclusive(&epCodeLock);
    return ok;
}
int ep_session_code_seal_gs_table(HfMod* owner,uint64_t handle,const void* image,uint32_t bytes,uint32_t at,uint32_t count,const EpSessionGsCheck* gs)
{ return EpCodeSeal(owner,handle,image,bytes,at,count,gs,0); }
int ep_session_code_seal_component33_property(HfMod* owner,uint64_t handle,const void* image,uint32_t bytes,uint32_t at,const EpSessionGsCheck* gs)
{ return EpCodeSeal(owner,handle,image,bytes,at,3,gs,1); }
int ep_session_code_seal_loadout_transition(HfMod* owner,uint64_t handle,const void* image,uint32_t bytes,uint32_t at,const EpSessionGsCheck* gs)
{ return EpCodeSeal(owner,handle,image,bytes,at,11,gs,2); }
int ep_session_code_seal_loadout_setup(HfMod* owner,uint64_t handle,const void* image,uint32_t bytes,uint32_t at,const EpSessionGsCheck* gs)
{ return EpCodeSeal(owner,handle,image,bytes,at,7,gs,3); }
int ep_session_code_seal_loadout_refresh(HfMod* owner,uint64_t handle,const void* image,uint32_t bytes,uint32_t at,const EpSessionGsCheck* gs)
{ return EpCodeSeal(owner,handle,image,bytes,at,5,gs,4); }
int ep_session_code_seal_loadout_records(HfMod* owner,uint64_t handle,const void* image,uint32_t bytes,uint32_t at,const EpSessionGsCheck* gs)
{ return EpCodeSeal(owner,handle,image,bytes,at,7,gs,5); }
int ep_session_code_seal_loadout_frame(HfMod* owner,uint64_t handle,const void* image,uint32_t bytes,uint32_t at,const EpSessionGsCheck* gs)
{ return EpCodeSeal(owner,handle,image,bytes,at,12,gs,6); }
int ep_session_code_seal_loadout_mode(HfMod* owner,uint64_t handle,const void* image,uint32_t bytes,uint32_t at,const EpSessionGsCheck* gs)
{ return EpCodeSeal(owner,handle,image,bytes,at,8,gs,7); }
int ep_session_code_seal_loadout_state(HfMod* owner,uint64_t handle,const void* image,uint32_t bytes,uint32_t at,const EpSessionGsCheck* gs)
{ return EpCodeSeal(owner,handle,image,bytes,at,15,gs,8); }
int ep_session_code_seal_loadout_resource_main(HfMod* owner,uint64_t handle,const void* image,uint32_t bytes,uint32_t at,const EpSessionGsCheck* gs)
{ return EpCodeSeal(owner,handle,image,bytes,at,7,gs,9); }
int ep_session_code_seal_player_join(HfMod* owner,uint64_t handle,const void* image,uint32_t bytes,uint32_t at,const EpSessionGsCheck* gs)
{ return EpCodeSeal(owner,handle,image,bytes,at,10,gs,10); }
int ep_session_code_retain_set(HfMod* owner,const uint64_t* input,uint32_t count)
{
    uint64_t ids[EP_SESSION_CODE_SLOTS];EpCodeSlot* slots[EP_SESSION_CODE_SLOTS];HMODULE module=NULL;int ok=0;
    if (!owner || !input || !count || count>EP_SESSION_CODE_SLOTS) return 0;
    memcpy(ids,input,count*sizeof(*input));
    AcquireSRWLockExclusive(&epCodeLock);
    for (uint32_t i=0;i<count;i++) {
        slots[i]=EpCodeFind(owner,ids[i]);
        if (!slots[i] || slots[i]->state!=EP_CODE_READY || !slots[i]->registered || slots[i]->pinned) goto done;
        for (uint32_t j=0;j<i;j++) if (ids[i]==ids[j]) goto done;
    }
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,
        (LPCSTR)(uintptr_t)&ep_session_code_retain_set,&module)) goto done;
    for (uint32_t i=0;i<count;i++) { slots[i]->pinned=1;slots[i]->state=EP_CODE_RETAINED; }
    ok=1;
done:ReleaseSRWLockExclusive(&epCodeLock);return ok;
}
int ep_session_code_publish(HfMod* owner, uint64_t handle, uintptr_t target, int32_t priority)
{
    EpCodeSlot* s; HMODULE module=NULL; int result;
    if (target<0x10000 || target>=((uint64_t)1<<47)) return 0;
    AcquireSRWLockExclusive(&epCodeLock);
    s=EpCodeFind(owner,handle);
    if (!s || (s->state!=EP_CODE_READY && s->state!=EP_CODE_RETAINED))
    { ReleaseSRWLockExclusive(&epCodeLock); return 0; }
    /* Do not let HellForge rewrite any immutable image managed by this owner,
     * including page padding or a different still-cancellable reservation. */
    for (unsigned i=0;i<EP_SESSION_CODE_SLOTS;i++)
    {
        EpCodeSlot* other=&epCodeSlots[i];
        if (other->handle && target<(uintptr_t)other->base+other->allocation_bytes &&
            target+32>(uintptr_t)other->base)
        { ReleaseSRWLockExclusive(&epCodeLock); return 0; }
    }
    /* Keep the slot, original variable and code implementing this owner alive,
     * including if a mod init declines after its first hook was attempted. */
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,
                           (LPCSTR)(uintptr_t)&ep_session_code_publish,&module))
    { ReleaseSRWLockExclusive(&epCodeLock); return 0; }
    s->pinned=1; s->state=EP_CODE_PUBLISHING;
    ReleaseSRWLockExclusive(&epCodeLock);
    /* No owner lock across the SDK call; in-flight lookups/discard attempts can
     * see the pinned state. The slot cannot be reclaimed or reused now. */
    result=s->hook(owner,target,s->base,&s->next,priority);
    AcquireSRWLockExclusive(&epCodeLock);
    s->state=result==0 ? EP_CODE_PUBLISHED : EP_CODE_PUBLISH_FAILED;
    ReleaseSRWLockExclusive(&epCodeLock);
    return result==0;
}
int ep_session_code_discard(HfMod* owner, uint64_t handle)
{
    int ok=0;
    AcquireSRWLockExclusive(&epCodeLock);
    EpCodeSlot* s=EpCodeFind(owner,handle);
    if (!s || s->pinned) goto done;
    if (s->registered)
    {
        if (!RtlDeleteFunctionTable(s->table)) { s->state=EP_CODE_FAILED; goto done; }
        s->registered=0;
    }
    if (!VirtualFree(s->base,0,MEM_RELEASE)) { s->state=EP_CODE_FAILED; goto done; }
    memset(s,0,sizeof *s); ok=1;
done:
    ReleaseSRWLockExclusive(&epCodeLock);
    return ok;
}
