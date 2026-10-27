#ifndef EP_ROSTER_CALL_H
#define EP_ROSTER_CALL_H
#include "ep_roster_owner.h"
#include "ep_roster_gate.h"
#include "ep_player_join_result.h"
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
/* Initialize all fields. Optional join_result shares context; it only reports
 * join outcomes, never replaces the mandatory owner failure policy. */
typedef struct EpRosterCallPolicy {
    EpRosterCallFailure failure;void* context;EpPlayerJoinNotice join_result;
} EpRosterCallPolicy;
/* Additional owned routes; do not change the eighteen-entry roster image ABI.
 * Family order: insert, registered insert, remove, reset, disconnect, lookup,
 * contains, set flag. Only insert/registered insert consume stack arguments. */
enum {EP_ROSTER_CALL_PEER_INSERT=EP_ROSTER_ENTRIES+1,
      EP_ROSTER_CALL_PEER_REGISTERED,EP_ROSTER_CALL_PEER_REMOVE,
      EP_ROSTER_CALL_PEER_RESET,EP_ROSTER_CALL_PEER_DISCONNECT,
      EP_ROSTER_CALL_PEER_LOOKUP,EP_ROSTER_CALL_PEER_CONTAINS,
      EP_ROSTER_CALL_PEER_SET_FLAG};
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
    /* Zero-initialize. Only the dispatcher changes this under the owner lock;
     * it orders NEW join notices even when post-call delivery is reordered. */
    uint64_t join_sequence;
    /* Required for NEW PLAYER_JOIN and peer routes. Zero blocks NEW before
     * native effects; OLD still follows the SDK chain. Names the bound client.
     * Registered insert resolves its client inside the guarded native body.
     * NEW pointer-returning peer lookup additionally requires an enclosing
     * same-owner scope lasting through the caller's last use of that pointer. */
    uint64_t join_client;
} EpRosterCallContext;
/* Replaces only the existing 32-byte leaf prefix. Context remains immutable
 * after exposure except join_sequence and the separately atomic active/next variables. */
int ep_roster_call_prefix(EpRosterCallContext*,uint8_t prefix[32]);
#ifdef __cplusplus
}
#endif
#endif
