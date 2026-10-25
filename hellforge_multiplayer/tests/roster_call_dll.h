#include "../mod/src/ep_roster_group.h"
typedef struct RosterCallTestApi {
    int (*prepare)(const HfApi*,HfMod*,const EpRosterGroupBindings*,uint64_t,const EpRosterCallPolicy*,EpRosterGroupInfo*);
    int (*info)(HfMod*,uint64_t,EpRosterGroupInfo*);
    int (*publish)(HfMod*,uint64_t,int32_t);
    int (*commit)(HfMod*,uint64_t,const EpPropertyCommitGuard*);
    int (*cancel)(HfMod*,uint64_t);
    int (*layout)(uint32_t,EpRosterGateLayout*);
    EpRosterOwnerResult (*create)(HfMod*,const EpNativeRosterView*,const EpRosterMemory*,uint64_t*);
    EpRosterOwnerResult (*owner_info)(HfMod*,uint64_t,EpRosterOwnerInfo*);
    EpRosterOwnerResult (*call)(HfMod*,uint64_t,int,EpRosterMutation,void*);
    EpNativeRosterStatus (*snapshot)(HfMod*,uint64_t,uintptr_t,EpHfRosterSnapshot*);
    EpRosterOwnerResult (*close)(HfMod*,uint64_t);
    uint32_t (*pending)(HfMod*,uint64_t,int* closing);
    void (*targets)(const uintptr_t[12]);
    void (*invoke)(EpRosterCallFrame*,uintptr_t,unsigned);
    uintptr_t (*entry)(void);
    void (*revision)(HfMod*,uint64_t,uint64_t);
} RosterCallTestApi;
