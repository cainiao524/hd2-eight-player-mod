/* Test-only export adapter; production owner entry points remain internal. */
#include "../mod/src/ep_session_code.h"
typedef struct SessionCodeTestApi {
    int (*reserve)(const HfApi*,HfMod*,uintptr_t,uint32_t,EpSessionCodeInfo*);
    int (*seal)(HfMod*,uint64_t,const void*,uint32_t,uint32_t);
    int (*info)(HfMod*,uint64_t,EpSessionCodeInfo*);
    int (*publish)(HfMod*,uint64_t,uintptr_t,int32_t);
    int (*discard)(HfMod*,uint64_t);
} SessionCodeTestApi;
