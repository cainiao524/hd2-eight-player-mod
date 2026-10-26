#include "ep_roster_call.h"
#include <windows.h>
#include <string.h>
static_assert(sizeof(EpRosterCallFrame)==176 && offsetof(EpRosterCallFrame,xmm)==64 &&
    offsetof(EpRosterCallFrame,entry_stack)==160 && offsetof(EpRosterCallFrame,status)==168,"bridge layout");
extern "C" void EpRosterCallEntry(void);
extern "C" void EpRosterCallTarget(EpRosterCallFrame*,uintptr_t,unsigned stack_arguments);
extern "C" void EpRosterCallDispatch(EpRosterCallContext*,EpRosterCallFrame*);
/* Static PE unwind records cover both bridges. No transient unregistered
 * pushes; all SIMD stores are unaligned-safe. The call frame lives beyond the
 * dispatcher's shadow space. Only the producer reads the original +28/+30. */
__asm__(
    ".text\n.p2align 4\n.globl EpRosterCallEntry\n.seh_proc EpRosterCallEntry\n"
    "EpRosterCallEntry:\nsubq $216,%rsp\n.seh_stackalloc 216\n.seh_endprologue\n"
    "movq %rax,32(%rsp)\nmovq %rcx,40(%rsp)\nmovq %rdx,48(%rsp)\nmovq %r8,56(%rsp)\n"
    "movq %r9,64(%rsp)\nmovq %r10,72(%rsp)\nmovq %r11,80(%rsp)\nmovq $0,88(%rsp)\n"
    "movdqu %xmm0,96(%rsp)\nmovdqu %xmm1,112(%rsp)\nmovdqu %xmm2,128(%rsp)\n"
    "movdqu %xmm3,144(%rsp)\nmovdqu %xmm4,160(%rsp)\nmovdqu %xmm5,176(%rsp)\n"
    "leaq 216(%rsp),%rax\nmovq %rax,192(%rsp)\nmovq $0,200(%rsp)\n"
    "movq %r10,%rcx\nleaq 32(%rsp),%rdx\ncall EpRosterCallDispatch\n"
    "movdqu 96(%rsp),%xmm0\nmovdqu 112(%rsp),%xmm1\nmovdqu 128(%rsp),%xmm2\n"
    "movdqu 144(%rsp),%xmm3\nmovdqu 160(%rsp),%xmm4\nmovdqu 176(%rsp),%xmm5\n"
    "movq 32(%rsp),%rax\nmovq 40(%rsp),%rcx\nmovq 48(%rsp),%rdx\nmovq 56(%rsp),%r8\n"
    "movq 64(%rsp),%r9\nmovq 72(%rsp),%r10\nmovq 80(%rsp),%r11\naddq $216,%rsp\nret\n.seh_endproc\n"
    ".p2align 4\n.globl EpRosterCallTarget\n.seh_proc EpRosterCallTarget\n"
    "EpRosterCallTarget:\npushq %rbx\n.seh_pushreg rbx\nsubq $48,%rsp\n.seh_stackalloc 48\n.seh_endprologue\n"
    "movq %rcx,%rbx\nmovq %rdx,%r11\ncmpl $2,%r8d\njne .Lep_roster_register_args\n"
    "movq 160(%rbx),%rax\nmovq 40(%rax),%rcx\nmovq %rcx,32(%rsp)\n"
    "movq 48(%rax),%rcx\nmovq %rcx,40(%rsp)\n.Lep_roster_register_args:\n"
    "movdqu 64(%rbx),%xmm0\nmovdqu 80(%rbx),%xmm1\nmovdqu 96(%rbx),%xmm2\n"
    "movdqu 112(%rbx),%xmm3\nmovdqu 128(%rbx),%xmm4\nmovdqu 144(%rbx),%xmm5\n"
    "movq 0(%rbx),%rax\nmovq 8(%rbx),%rcx\nmovq 16(%rbx),%rdx\nmovq 24(%rbx),%r8\n"
    "movq 32(%rbx),%r9\nmovq 40(%rbx),%r10\ncall *%r11\n"
    "movq %rax,0(%rbx)\nmovq %rcx,8(%rbx)\nmovq %rdx,16(%rbx)\nmovq %r8,24(%rbx)\n"
    "movq %r9,32(%rbx)\nmovq %r10,40(%rbx)\nmovq %r11,48(%rbx)\n"
    "movdqu %xmm0,64(%rbx)\nmovdqu %xmm1,80(%rbx)\nmovdqu %xmm2,96(%rbx)\n"
    "movdqu %xmm3,112(%rbx)\nmovdqu %xmm4,128(%rbx)\nmovdqu %xmm5,144(%rbx)\n"
    "addq $48,%rsp\npopq %rbx\nret\n.seh_endproc\n");
typedef struct EpRosterInvocation {EpRosterCallContext* context;EpRosterCallFrame* frame;} EpRosterInvocation;
static int RunRosterCall(void* opaque,const EpNativeRosterView* view)
{
    EpRosterInvocation* call=(EpRosterInvocation*)opaque;EpRosterCallContext* c=call->context;
    if (view->game!=c->game || view->roster!=c->roster || view->storage!=c->storage) return 0;
    if (c->switching && InterlockedCompareExchange((volatile LONG*)c->switching,0,0)) return 0;
    /* Own the original dispatcher across both callback tables, including the
     * interval after departure returns. Resolve next while ownership is held. */
    uintptr_t target=c->kind!=EP_ROSTER_ENTITY_REMOVE && InterlockedCompareExchange((volatile LONG*)c->active,0,0)==1 ? c->body :
        (uintptr_t)InterlockedCompareExchangePointer((void* volatile*)c->next_pointer,NULL,NULL);
    if (!target) return 0;
    EpRosterCallTarget(call->frame,target,c->kind==EP_ROSTER_SEND ? 2 : 0);return 1;
}
extern "C" void EpRosterCallDispatch(EpRosterCallContext* c,EpRosterCallFrame* frame)
{
    EpRosterInvocation call={c,frame};
    EpRosterOwnerResult result=ep_roster_owner_call(c->mod,c->owner,c->kind!=EP_ROSTER_GETTER && c->kind!=EP_ROSTER_ASSOCIATION,RunRosterCall,&call);
    frame->status=(uint32_t)result;
    if (result!=EP_OWNER_OK) c->policy.failure(c->policy.context,c->kind,result,frame);
}
int ep_roster_call_prefix(EpRosterCallContext* context,uint8_t prefix[32])
{
    if (!context || !prefix || !context->mod || !context->owner || !context->active || !context->next_pointer ||
        !context->body || !context->kind || context->kind>EP_ROSTER_ENTRIES || !context->policy.failure) return 0;
    memset(prefix,0x90,32);uintptr_t c=(uintptr_t)context,entry=(uintptr_t)EpRosterCallEntry;
    prefix[0]=0x49;prefix[1]=0xBA;memcpy(prefix+2,&c,8);
    prefix[10]=0x49;prefix[11]=0xBB;memcpy(prefix+12,&entry,8);
    prefix[20]=0x41;prefix[21]=0xFF;prefix[22]=0xE3;return 1;
}
