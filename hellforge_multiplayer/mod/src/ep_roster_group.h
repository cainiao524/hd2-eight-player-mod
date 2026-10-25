#ifndef EP_ROSTER_GROUP_H
#define EP_ROSTER_GROUP_H
#include "ep_property_group.h"
#include "ep_roster_gate.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_ROSTER_GROUP_SLOTS 4u
typedef struct EpRosterGroupBindings {
    uint64_t game_base,roster_address,storage_address;
    uintptr_t desired_code[EP_ROSTER_ENTRIES],reject[EP_ROSTER_ENTRIES];
} EpRosterGroupBindings;
typedef struct EpRosterGroupInfo {
    uint64_t handle;
    uint32_t state,active,published_attempts;
    EpSessionCodeInfo code[EP_ROSTER_ENTRIES];
} EpRosterGroupInfo;
/* Twelve entries share one latch and storage binding. All reservations precede
 * emission; internal insert/remove calls use this group's mover body. Uses
 * EP_GROUP_* states and the same full-capacity guard contract. No production
 * guard, automatic binding, active cancellation or game access is provided.
 * Exclusive ownership of ALL code handles is transferred to the group. */
int ep_roster_group_prepare(const HfApi*,HfMod*,const EpRosterGroupBindings*,EpRosterGroupInfo*);
int ep_roster_group_info(HfMod*,uint64_t,EpRosterGroupInfo*);
int ep_roster_group_publish(HfMod*,uint64_t,int32_t);
int ep_roster_group_commit(HfMod*,uint64_t,const EpPropertyCommitGuard*);
int ep_roster_group_cancel(HfMod*,uint64_t);
#ifdef __cplusplus
}
#endif
#endif
