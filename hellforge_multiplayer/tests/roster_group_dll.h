#include "../mod/src/ep_roster_group.h"
typedef struct RosterGroupTestApi {
    int (*prepare)(const HfApi*,HfMod*,const EpRosterGroupBindings*,EpRosterGroupInfo*);
    int (*info)(HfMod*,uint64_t,EpRosterGroupInfo*);
    int (*publish)(HfMod*,uint64_t,int32_t);
    int (*commit)(HfMod*,uint64_t,const EpPropertyCommitGuard*);
    int (*cancel)(HfMod*,uint64_t);
    int (*layout)(uint32_t,EpRosterGateLayout*);
    int (*reserve)(const HfApi*,HfMod*,uintptr_t,uint32_t,EpSessionCodeInfo*);
    int (*seal)(HfMod*,uint64_t,const void*,uint32_t,uint32_t,uint32_t);
    int (*discard)(HfMod*,uint64_t);
    void (*failure)(unsigned step,int free_failure);
} RosterGroupTestApi;
