#ifndef EP_LOADOUT_GROUP_H
#define EP_LOADOUT_GROUP_H
#include "ep_loadout_setup.h"
#include "ep_loadout_interactions.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpLoadoutGroupAddresses {
    EpLoadoutSetupAddresses setup;
    uint64_t lifecycle_code,consumers_code,interactions_code;
} EpLoadoutGroupAddresses;
enum {EP_LOADOUT_GROUP_EMPTY,EP_LOADOUT_GROUP_READY,EP_LOADOUT_GROUP_CLEANUP};
typedef struct EpLoadoutGroup {
    EpSessionCodeInfo code[4]; /* lifecycle, consumers, setup, interactions */
    uint64_t constructor,release,alternate_release,transition,setup,update,lookup,action;
    uint64_t input,edit,close;
    uint32_t capacity,state;
} EpLoadoutGroup;
/* Prepare all eleven native entries from ONE screen/storage/map/capacity
 * binding. The four desired code bases must be explicit and nonoverlapping.
 * Only owned code allocations are made; data still belongs to the caller.
 * All images must reach READY before callable addresses are returned. Partial
 * preparation discards in reverse order; failed cleanup retains only handles
 * and exposes no callable entries. Retry group_discard for CLEANUP.
 * No initialization, original writes, retention/pinning, hooks or activation.
 * Complete writer routing, layout/navigation and source/owner validation are
 * prerequisites to a future common publication; READY is not that gate. */
EpPropertyResult ep_loadout_group_prepare(const HfApi*,HfMod*,const EpLoadoutGroupAddresses*,EpLoadoutGroup*);
EpPropertyResult ep_loadout_group_discard(HfMod*,EpLoadoutGroup*);
#ifdef __cplusplus
}
#endif
#endif
