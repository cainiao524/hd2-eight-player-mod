#ifndef EP_ROSTER_OWNER_H
#define EP_ROSTER_OWNER_H
#include "ep_native_roster.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_ROSTER_OWNER_SLOTS 8u
typedef enum EpRosterOwnerResult {
    EP_OWNER_OK, EP_OWNER_ARGUMENT, EP_OWNER_UNAVAILABLE, EP_OWNER_REENTRANT,
    EP_OWNER_STALE, EP_OWNER_FAULTED, EP_OWNER_CALLBACK_FAILED,
    EP_OWNER_CALLBACK_FAULT, EP_OWNER_IDENTITY, EP_OWNER_EXHAUSTED, EP_OWNER_CONFLICT
} EpRosterOwnerResult;
typedef struct EpRosterIdentitySet {
    uint32_t count;
    EpNativeTicket tickets[EP_NATIVE_ROSTER_CAPACITY];
} EpRosterIdentitySet;
typedef struct EpRosterMemory {
    void* context;
    /* In-process owned memory only. Caller supplies this explicitly, retains
     * its context and all pointees until close returns, and routes EVERY writer
     * through mutate. No implementation/discovery of game reads is supplied. */
    int (*read)(void*, uintptr_t, void*, size_t);
} EpRosterMemory;
typedef struct EpRosterOwnerInfo {
    uint64_t handle, epoch, revision;
    uint32_t fault, ticket_count;
} EpRosterOwnerInfo;
typedef int (*EpRosterMutation)(void*, const EpNativeRosterView* current);
/* Validates numeric bindings/tickets only; does not read memory or bind hooks.
 * Tickets MUST come from the authoritative session source. This module only
 * checks consistency/generation; it cannot authenticate a peer or admit it. */
EpRosterOwnerResult ep_roster_owner_create(HfMod*, const EpNativeRosterView*, const EpRosterMemory*, uint64_t*);
EpRosterOwnerResult ep_roster_owner_info(HfMod*, uint64_t, EpRosterOwnerInfo*);
/* Serialized with all snapshots. Revision and next tickets are checked BEFORE
 * calling mutation. NULL next retains tickets. Success publishes data/tickets
 * together; callback failure/SEH may have partially written and permanently
 * quarantines this owner. This is NOT rollback. No nested owner calls allowed.
 * Callbacks use C ABI and must not throw C++ exceptions or escape with longjmp. */
EpRosterOwnerResult ep_roster_owner_mutate(HfMod*, uint64_t, uint64_t expected_revision,
    const EpRosterIdentitySet* next, EpRosterMutation, void*);
/* Native call scope: acquires the current revision under the lock, so ordinary
 * queued calls are not lost to optimistic-revision conflicts. Same-owner
 * native nesting inherits the scope (max 32); snapshot/identity/close reentry
 * remains forbidden. One outer call advances revision if any nested call wrote.
 * Callback failure/SEH quarantines; nested faults propagate to the outer call. */
EpRosterOwnerResult ep_roster_owner_call(HfMod*,uint64_t,int writes,EpRosterMutation,void*);
EpRosterOwnerResult ep_roster_owner_check_binding(HfMod*,uint64_t,uintptr_t game,uintptr_t roster,uintptr_t storage);
/* Nonblocking thread-local query for control operations that must not start
 * inside an in-flight native/read/write scope. */
int ep_roster_owner_in_scope(void);
EpNativeRosterStatus ep_roster_owner_snapshot(HfMod*, uint64_t, uintptr_t game, EpHfRosterSnapshot*);
/* Stable numerical context, no pointer into reusable owner slots. Closing an
 * owner makes an already exported provider return unavailable, never a later
 * occupant. Unbind the loader before unloading the module's executable code. */
EpRosterOwnerResult ep_roster_owner_provider(HfMod*, uint64_t, EpHfRosterProvider*);
/* Stops new operations, drains acquired and queued operations, then releases
 * references to external memory. Does not free data, uninstall hooks, or turn
 * eight-slot native state back into four-slot state. Never called by Mod init. */
EpRosterOwnerResult ep_roster_owner_close(HfMod*, uint64_t);
#ifdef __cplusplus
}
#endif
#endif
