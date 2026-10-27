#include "ep_loadout_call.h"
#include <windows.h>
#include <string.h>
namespace {
struct Entry {uint32_t rva,stack_arguments;size_t member;};
#define EP_LOADOUT_CALL(member,rva,stack) {rva,stack,offsetof(EpLoadoutGroup,member)},
const Entry entries[]={
#include "ep_loadout_call_entries.inc"
};
#undef EP_LOADOUT_CALL
static_assert(sizeof(entries)/sizeof(*entries)==EP_LOADOUT_CALL_COUNT,"complete external loadout catalog");
const Entry* entry(uint32_t rva)
{for (const auto& e:entries) if (e.rva==rva) return &e;return nullptr;}
uintptr_t body(const EpLoadoutStorageInfo& info,const Entry& e)
{uint64_t address;memcpy(&address,(const uint8_t*)&info.group+e.member,sizeof(address));return (uintptr_t)address;}
struct Invocation {EpLoadoutCallContext* context;EpRosterCallFrame* frame;Invocation* prior;bool recursive;uintptr_t target;};
thread_local Invocation* invoking;
}
extern "C" void EpLoadoutCallEntry(void);
extern "C" void EpRosterCallTarget(EpRosterCallFrame*,uintptr_t,unsigned);
extern "C" void EpLoadoutCallDispatch(EpLoadoutCallContext*,EpRosterCallFrame*);
static_assert(sizeof(EpRosterCallFrame)==176 && offsetof(EpRosterCallFrame,xmm)==64 &&
    offsetof(EpRosterCallFrame,entry_stack)==160 && offsetof(EpRosterCallFrame,status)==168,"loadout bridge frame");
// The 32-byte gate tail-jumps here with context in scratch R10. Preserve all
// register arguments before any owner/storage/SDK bookkeeping. Static PE unwind
// records cover this frame; EpRosterCallTarget covers the forwarded native call.
__asm__(
    ".text\n.p2align 4\n.globl EpLoadoutCallEntry\n.seh_proc EpLoadoutCallEntry\n"
    "EpLoadoutCallEntry:\nsubq $216,%rsp\n.seh_stackalloc 216\n.seh_endprologue\n"
    "movq %rax,32(%rsp)\nmovq %rcx,40(%rsp)\nmovq %rdx,48(%rsp)\nmovq %r8,56(%rsp)\n"
    "movq %r9,64(%rsp)\nmovq %r10,72(%rsp)\nmovq %r11,80(%rsp)\nmovq $0,88(%rsp)\n"
    "movdqu %xmm0,96(%rsp)\nmovdqu %xmm1,112(%rsp)\nmovdqu %xmm2,128(%rsp)\n"
    "movdqu %xmm3,144(%rsp)\nmovdqu %xmm4,160(%rsp)\nmovdqu %xmm5,176(%rsp)\n"
    "leaq 216(%rsp),%rax\nmovq %rax,192(%rsp)\nmovq $0,200(%rsp)\n"
    "movq %r10,%rcx\nleaq 32(%rsp),%rdx\ncall EpLoadoutCallDispatch\n"
    "movdqu 96(%rsp),%xmm0\nmovdqu 112(%rsp),%xmm1\nmovdqu 128(%rsp),%xmm2\n"
    "movdqu 144(%rsp),%xmm3\nmovdqu 160(%rsp),%xmm4\nmovdqu 176(%rsp),%xmm5\n"
    "movq 32(%rsp),%rax\nmovq 40(%rsp),%rcx\nmovq 48(%rsp),%rdx\nmovq 56(%rsp),%r8\n"
    "movq 64(%rsp),%r9\nmovq 72(%rsp),%r10\nmovq 80(%rsp),%r11\naddq $216,%rsp\nret\n.seh_endproc\n");
namespace {
int target(void* opaque,const EpNativeRosterView*)
{
    auto& call=*(Invocation*)opaque;
    EpRosterCallTarget(call.frame,call.target,call.context->stack_arguments);return 1;
}
int invoke(void* opaque,const EpNativeRosterView* view)
{
    auto& call=*(Invocation*)opaque;auto& c=*call.context;EpLoadoutStorageInfo info={};
    bool valid=!call.recursive && view->game==c.game && view->roster==c.roster && view->storage==c.storage &&
        !InterlockedCompareExchange((volatile LONG*)&c.control->switching,0,0) &&
        ep_loadout_storage_info(c.mod,c.loadout,&info);
    if (valid) {
        const auto active=InterlockedCompareExchange((volatile LONG*)&c.control->active,0,0);
        if (!active && info.state==EP_LOADOUT_STORAGE_RETAINED)
            call.target=(uintptr_t)InterlockedCompareExchangePointer((void* volatile*)c.next_pointer,nullptr,nullptr);
        else if (active==1 && info.state==EP_LOADOUT_STORAGE_UI_MIGRATED && info.initialization_owner==c.owner &&
                 body(info,*entry(c.rva))==c.body) call.target=c.body;
        valid=call.target!=0;
    }
    if (valid && ep_roster_owner_call(c.mod,c.owner,1,target,&call)==EP_OWNER_OK) return 1;
    // Still inside the outer owner, including after nested SEH. An initialized
    // generation cannot remain apparently callable after its owner has faulted.
    ep_loadout_storage_quarantine_in_scope(c.mod,c.loadout,c.owner);return 0;
}
}
extern "C" void EpLoadoutCallDispatch(EpLoadoutCallContext* context,EpRosterCallFrame* frame)
{
    Invocation call={context,frame,invoking,false,0};
    for (auto* prior=invoking;prior;prior=prior->prior)
        if (prior->context->mod==context->mod && prior->context->loadout==context->loadout &&
            prior->context->rva==context->rva) call.recursive=true;
    invoking=&call;
    const auto result=ep_roster_owner_call(context->mod,context->owner,0,invoke,&call);
    invoking=call.prior;frame->status=result;
    if (result!=EP_OWNER_OK) {
        context->policy.failure(context->policy.context,context->rva,result,frame);
        RaiseException(0xe04c4401,EXCEPTION_NONCONTINUABLE,0,nullptr);
    }
}
int ep_loadout_call_layout(uint32_t index,EpLoadoutCallLayout* out)
{
    if (!out) return 0;*out={};if (index>=EP_LOADOUT_CALL_COUNT) return 0;
    *out={entries[index].rva,entries[index].stack_arguments};return 1;
}
int ep_loadout_call_prepare(const HfApi* api,HfMod* mod,uint64_t loadout,uint64_t owner,uint32_t rva,
    EpLoadoutCallControl* control,const EpRosterCallPolicy* policy,uintptr_t desired,
    EpLoadoutCallContext* context,EpSessionCodeInfo* code)
{
    EpRosterCallPolicy saved={};if (policy) saved=*policy;
    if (code) *code={};if (context) *context={};
    const auto* e=entry(rva);EpLoadoutStorageInfo info={};
    if (!context || !code || !mod || !owner || !control || ((uintptr_t)control&3) || !saved.failure || !e ||
        ep_roster_owner_in_scope() || !ep_loadout_storage_info(mod,loadout,&info) || !info.sources_imported ||
        (info.state!=EP_LOADOUT_STORAGE_RETAINED && info.state!=EP_LOADOUT_STORAGE_UI_MIGRATED) ||
        (info.state==EP_LOADOUT_STORAGE_UI_MIGRATED && info.initialization_owner!=owner) || !body(info,*e)) return 0;
    const auto& b=info.binding.setup.common;
    if (ep_roster_owner_check_binding(mod,owner,b.lifecycle.game,b.roster,b.roster_storage)!=EP_OWNER_OK) return 0;
    if (!ep_session_code_reserve(api,mod,desired,48,code)) return 0;
    *context={mod,owner,loadout,b.lifecycle.game,b.roster,b.roster_storage,body(info,*e),
        (uintptr_t)b.lifecycle.game+rva,code->next_pointer,rva,e->stack_arguments,control,saved};
    uint8_t image[48]={};memset(image,0x90,32);
    image[0]=0x49;image[1]=0xba;uintptr_t address=(uintptr_t)context;memcpy(image+2,&address,8);
    image[10]=0x49;image[11]=0xbb;address=(uintptr_t)&EpLoadoutCallEntry;memcpy(image+12,&address,8);
    image[20]=0x41;image[21]=0xff;image[22]=0xe3;
    image[32]=1;const uint32_t row[]={0,23,32};memcpy(image+36,row,sizeof(row));
    if (ep_session_code_seal(mod,code->handle,image,sizeof(image),36) && ep_session_code_info(mod,code->handle,code)) return 1;
    if (ep_session_code_discard(mod,code->handle)) {*code={};*context={};}
    return 0;
}
