/* Test-only exports; no production test entry point. */
#include "../mod/src/ep_property_group.h"
#include "../mod/src/ep_property_gate.h"
typedef struct PropertyGroupTestApi {
    int (*prepare)(const HfApi*,HfMod*,const EpPropertyGroupBindings*,EpPropertyGroupInfo*);
    int (*info)(HfMod*,uint64_t,EpPropertyGroupInfo*);
    int (*publish)(HfMod*,uint64_t,int32_t);
    int (*commit)(HfMod*,uint64_t,const EpPropertyCommitGuard*);
    int (*cancel)(HfMod*,uint64_t);
    int (*reserve)(const HfApi*,HfMod*,uintptr_t,uint32_t,EpSessionCodeInfo*);
    int (*seal)(HfMod*,uint64_t,const void*,uint32_t,uint32_t,uint32_t);
    int (*discard)(HfMod*,uint64_t);
    EpPropertyResult (*gate)(uint32_t,const EpPropertyAddresses*,uint64_t,uint64_t,EpPropertyGateImage*);
    void (*failure)(unsigned);
} PropertyGroupTestApi;
