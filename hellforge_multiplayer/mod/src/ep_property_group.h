#ifndef EP_PROPERTY_GROUP_H
#define EP_PROPERTY_GROUP_H
#include "ep_session_code.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_PROPERTY_GROUP_SLOTS 16
#define EP_PROPERTY_GROUP_ENTRIES 3
typedef enum EpPropertyGroupState {
    EP_GROUP_EMPTY,EP_GROUP_PREPARING,EP_GROUP_PREPARED,EP_GROUP_PUBLISHING,
    EP_GROUP_READY,EP_GROUP_COMMITTING,EP_GROUP_ACTIVE,EP_GROUP_FAILED,EP_GROUP_CANCELLED
} EpPropertyGroupState;
typedef struct EpPropertyGroupBindings {
    uint64_t game_base,roster_address,storage_address; /* complete B, 0x680 bytes */
    uintptr_t desired_code[EP_PROPERTY_GROUP_ENTRIES],reject[EP_PROPERTY_GROUP_ENTRIES]; /* producer, receiver, getter */
} EpPropertyGroupBindings;
typedef struct EpPropertyGroupInfo {
    uint64_t handle;
    uint32_t state,active,published_attempts;
    EpSessionCodeInfo code[EP_PROPERTY_GROUP_ENTRIES];
} EpPropertyGroupInfo;
typedef struct EpPropertyCommitGuard {
    void* context;
    /* Hold all relevant game execution/mutations quiescent, including calls
     * which already chose the old route. Stage and validate ALL related data,
     * capacities and consumers, not just these three entries. Keep external
     * resources alive for the session after success. No production guard yet. */
    int (*begin)(void*,void** lease);
    int (*validate)(void*,void* lease);
    /* On failure undo staged data before resuming. Must not throw/fail. */
    void (*end)(void*,void* lease,int committed);
} EpPropertyCommitGuard;
/* All return 1 on success. No automatic Mod initialization. Prepare/publish
 * never enable the new bodies. If prepare cleanup fails, out retains a handle.
 * After any SDK publication attempt the group/latch and exposed images remain
 * pinned. cancel is only BEFORE activation; no active-data rollback is claimed.
 * Caller transfers exclusive ownership of the three code handles to this group:
 * inspect them, but never seal/publish/discard them independently. */
int ep_property_group_prepare(const HfApi*,HfMod*,const EpPropertyGroupBindings*,EpPropertyGroupInfo*);
int ep_property_group_info(HfMod*,uint64_t,EpPropertyGroupInfo*);
int ep_property_group_publish(HfMod*,uint64_t,int32_t priority);
int ep_property_group_commit(HfMod*,uint64_t,const EpPropertyCommitGuard*);
int ep_property_group_cancel(HfMod*,uint64_t);
#ifdef __cplusplus
}
#endif
#endif
