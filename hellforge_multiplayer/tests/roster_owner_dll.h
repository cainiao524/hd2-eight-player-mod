#include "../mod/src/ep_roster_owner.h"
typedef struct RosterOwnerTestApi {
    EpRosterOwnerResult (*create)(HfMod*,const EpNativeRosterView*,const EpRosterMemory*,uint64_t*);
    EpRosterOwnerResult (*info)(HfMod*,uint64_t,EpRosterOwnerInfo*);
    EpRosterOwnerResult (*mutate)(HfMod*,uint64_t,uint64_t,const EpRosterIdentitySet*,EpRosterMutation,void*);
    EpNativeRosterStatus (*snapshot)(HfMod*,uint64_t,uintptr_t,EpHfRosterSnapshot*);
    EpRosterOwnerResult (*provider)(HfMod*,uint64_t,EpHfRosterProvider*);
    EpRosterOwnerResult (*close)(HfMod*,uint64_t);
    /* Observes acquired/queued operations under the real registry lock, used
     * only to arrange deterministic races. No production state is modified. */
    uint32_t (*pending)(HfMod*,uint64_t,int* closing);
} RosterOwnerTestApi;
