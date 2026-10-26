#ifndef EP_ROSTER_CALL_H
#define EP_ROSTER_CALL_H
#include "ep_roster_owner.h"
#include "ep_roster_gate.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Exact Windows x64 bridge layout. RFLAGS and incoming R10/R11 are scratch;
 * preserve register arguments, XMM0..5, producer stack arguments and volatile
 * return registers. Nonvolatile registers are preserved by the Windows ABI. */
typedef struct EpRosterCallFrame {
    uint64_t rax,rcx,rdx,r8,r9,r10,r11,reserved;
    uint8_t xmm[6][16];
    uintptr_t entry_stack;
    uint32_t status,padding;
} EpRosterCallFrame;
/* Required explicit failure policy; no invented success/sentinel return.
 * Set frame return values as required by the original caller ABI. No throw or
 * owner reentry. Context/code must survive every published hook. Not rollback. */
typedef void (*EpRosterCallFailure)(void*,uint32_t kind,EpRosterOwnerResult,EpRosterCallFrame*);
typedef struct EpRosterCallPolicy {EpRosterCallFailure failure;void* context;} EpRosterCallPolicy;
typedef struct EpRosterCallContext {
    HfMod* mod;
    uint64_t owner,game,roster,storage;
    volatile int32_t* active;
    uintptr_t next_pointer,body;
    uint32_t kind;
    EpRosterCallPolicy policy;
    /* Optional group staging barrier; checked AFTER acquiring the owner.
     * Same-thread callbacks cannot enter either layout during a joint commit. */
    volatile int32_t* switching;
} EpRosterCallContext;
/* Replaces only the existing 32-byte leaf prefix. Context remains immutable
 * after exposure except the separately atomic active/next variables. */
int ep_roster_call_prefix(EpRosterCallContext*,uint8_t prefix[32]);
#ifdef __cplusplus
}
#endif
#endif
