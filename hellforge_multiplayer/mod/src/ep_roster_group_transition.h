#ifndef EP_ROSTER_GROUP_TRANSITION_H
#define EP_ROSTER_GROUP_TRANSITION_H
#include "ep_roster_group.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {EP_ROSTER_TRANSITION_OLD,EP_ROSTER_TRANSITION_NEW,EP_ROSTER_TRANSITION_UNSAFE};
typedef struct EpRosterGroupTransition {uint64_t group,sequence,storage_owner;} EpRosterGroupTransition;
/* Internal coordinator protocol, not an independent activation API. claim
 * reserves a fully published OWNED group outside any owner scope. enter runs
 * inside the exact healthy owner after external drain; activate/finish stay
 * under that owner through both latches, data, windows and guard.end. finish
 * OLD is also allowed before enter to abandon a claim without side effects.
 * UNSAFE keeps the staging barrier and forbids retry; coordinator must also
 * quarantine the common owner and never resume external execution. Serial
 * tokens prevent stale cleanup from finishing a later attempt. No callbacks,
 * game reads or automatic publication. Never share tokens with external guards. */
int ep_roster_group_transition_claim(HfMod*,uint64_t group,uint64_t owner,uint64_t game,EpRosterGroupTransition*);
int ep_roster_group_transition_enter(HfMod*,const EpRosterGroupTransition*);
int ep_roster_group_transition_activate(HfMod*,const EpRosterGroupTransition*);
int ep_roster_group_transition_finish(HfMod*,const EpRosterGroupTransition*,uint32_t outcome);
#ifdef __cplusplus
}
#endif
#endif
