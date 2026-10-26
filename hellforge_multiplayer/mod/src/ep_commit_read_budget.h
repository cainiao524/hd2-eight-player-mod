#ifndef EP_COMMIT_READ_BUDGET_H
#define EP_COMMIT_READ_BUDGET_H
#include <stdint.h>
#define EP_COMMIT_READ_LIMIT 65536u
/* One serialized activation attempt, including failed requests and rollback
 * verification. Never share concurrently. Guards' independent reads are not
 * implied to participate; owned backup buffers are not SDK/source reads. */
typedef struct EpCommitReadBudget {uint32_t used;} EpCommitReadBudget;
static inline int ep_commit_read_reserve(EpCommitReadBudget* b,uint32_t n)
{
    if (!b || b->used>EP_COMMIT_READ_LIMIT || n>EP_COMMIT_READ_LIMIT-b->used) return 0;
    b->used+=n;return 1;
}
#endif
