#ifndef EP_ROSTER_GROUP_H
#define EP_ROSTER_GROUP_H
#include "ep_property_group.h"
#include "ep_roster_gate.h"
#include "ep_roster_call.h"
#include "ep_player_join_image.h"
#include "ep_client_peers.h"
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
    uint64_t storage_owner;
} EpRosterGroupInfo;
/* Eighteen entries share one latch and storage binding. All reservations precede
 * emission; insert/remove and registry calls use this group's mover and
 * association bodies respectively. Uses
 * EP_GROUP_* states and the same full-capacity guard contract. No production
 * guard, automatic binding, active cancellation or game access is provided.
 * Exclusive ownership of ALL code handles is transferred to the group. */
int ep_roster_group_prepare(const HfApi*,HfMod*,const EpRosterGroupBindings*,EpRosterGroupInfo*);
/* Opt-in owned calls; retains original standalone API for existing callers.
 * The supplied owner's binding must exactly match. Every OLD and NEW call is
 * serialized before selecting the latch. Requires an explicit failure policy.
 * For owned commit, begin only excludes/drains external execution; staging is
 * in validate and rollback/resume in end, under the owner call scope.
 * PLAYER_JOIN owns the entire original ClientSynchronizer join body,
 * including native FDC140 creation and callbacks. Use prepare_owned_peers to
 * bind its shared confirmed-peer bank. This legacy owned API leaves NEW join
 * blocked before native effects; OLD still forwards normally.
 * Checked creation supplies bounded preflight and complete-normal-failure
 * cleanup (ep_player_join_call.h). Partial exceptions still quarantine, and
 * the unowned legacy prepare API cannot execute the NEW join body. Full
 * resource/control/UI and runtime acceptance remain integration obligations. */
int ep_roster_group_prepare_owned(const HfApi*,HfMod*,const EpRosterGroupBindings*,uint64_t storage_owner,
    const EpRosterCallPolicy*,EpRosterGroupInfo*);
/* Binds local join to the SAME client/bank/capacity as ep_client_peer_family.
 * Sources must be migrated and retained, all family/inline readers redirected,
 * and writers excluded together before the existing commit guard permits NEW.
 * No bank allocation, migration, reader audit or publication is implied here.
 * This join-only preparation cannot commit NEW: use the peer-family API below
 * to prepare the remaining routes with the same switch.
 * Full lookup windows have original GP-only unwind, independent of the later
 * checked-creation frame. Group data, bank and native owner live for the session.
 */
int ep_roster_group_prepare_owned_peers(const HfApi*,HfMod*,const EpRosterGroupBindings*,uint64_t storage_owner,
    const EpRosterCallPolicy*,const EpPlayerJoinPeers*,EpRosterGroupInfo*);
typedef struct EpRosterPeerRoutesInfo {
    uint64_t group;
    uint32_t count,retained;
    EpSessionCodeInfo body[EP_CLIENT_PEER_FAMILY_COUNT],gate[EP_CLIENT_PEER_FAMILY_COUNT];
} EpRosterPeerRoutesInfo;
/* Prepare all nine confirmed-peer/update routes with the eighteen roster routes.
 * Update owns both native lookup calls through their last pointer access; the
 * independent host four-slot state still needs migration (ep_client_update.h).
 * Family game/client/bank/capacity are the local-join binding too. All gates use
 * the SAME owner, latch, staging barrier and policy. Family code[] supplies
 * native body addresses within rel32 reach; bridge gates use absolute jumps.
 * Preparation is cancellable and does not publish/read any game state.
 *
 * Publication permanently retains all peer bodies/gates before the first hook.
 * Commit requires all twenty-six SDK next pointers and keeps OLD until the
 * existing whole-engine guard has migrated both banks and all other readers.
 * The older join-only prepare_owned_peers cannot commit NEW without this family.
 * A returned lookup pointer is only usable within an enclosing same-owner call;
 * an unowned NEW lookup quarantines rather than letting a movable pointer escape.
 * Other inline consumers, external writers, identities and lifetime remain the
 * caller's integration obligations. This API neither installs automatically nor
 * establishes complete lifecycle coverage or real multiplayer acceptance.
 */
int ep_roster_group_prepare_owned_peer_family(const HfApi*,HfMod*,const EpRosterGroupBindings*,uint64_t storage_owner,
    const EpRosterCallPolicy*,const EpClientPeerFamilyAddresses*,EpRosterGroupInfo*);
int ep_roster_group_peer_routes_info(HfMod*,uint64_t,EpRosterPeerRoutesInfo*);
int ep_roster_group_peer_binding(HfMod*,uint64_t,EpPlayerJoinPeers*);
int ep_roster_group_info(HfMod*,uint64_t,EpRosterGroupInfo*);
int ep_roster_group_publish(HfMod*,uint64_t,int32_t);
int ep_roster_group_commit(HfMod*,uint64_t,const EpPropertyCommitGuard*);
int ep_roster_group_cancel(HfMod*,uint64_t);
#ifdef __cplusplus
}
#endif
#endif
