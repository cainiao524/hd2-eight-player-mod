#ifndef EP_LOADOUT_RESOURCE_OWNER_H
#define EP_LOADOUT_RESOURCE_OWNER_H
#include "ep_loadout_countdown.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_RESOURCE_OWNER_BYTES 8192u
typedef struct EpLoadoutResourceOwnerSource {
    uint64_t owner,objects,phases,rows,states;
} EpLoadoutResourceOwnerSource;
typedef struct EpLoadoutResourceOwnerAddresses {
    EpLoadoutRecordsAddresses records;
    EpLoadoutCountdownSource countdown_source;
    EpLoadoutResourceOwnerSource source;
} EpLoadoutResourceOwnerAddresses;
typedef struct EpLoadoutResourceOwnerImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t insert,enqueue,move,remove;
    uint8_t data[EP_LOADOUT_RESOURCE_OWNER_BYTES];
} EpLoadoutResourceOwnerImage;
/* Full native 66BFC0 insertion, 66C080 queued registration, 66BC20 dense move,
 * 66C270 removal. The owner at game+3326428 keeps native counts/hash; its
 * objects (+68,8 bytes), phases (+88,12), resource rows (+B8,20), states
 * (+108,4) move to independent capacity-sized banks. Both registration
 * limits use the binding capacity, with rejection instead of the native
 * null-address assertion. Insert/remove link this same guarded dense move.
 * Immediate insertion requires published count +8 == registered count +4;
 * pending entries must pass the native publication phase before insertion.
 * Removal retains native ownership-flag/prefix ordering. Hash membership,
 * counts, flags and all four row banks must agree on dense object identity.
 * Caller owns initialized storage and retains owner, objects, native hash
 * services/backing, exclusion and publication sequencing. Registration's
 * native initialization fields are retained; state initialization/import,
 * 66C100 publication, ownership callbacks, tick and other consumers still
 * need routing before use. No hooks, game access or runtime verification. */
EpPropertyResult ep_loadout_resource_owner_validate_span(const EpLoadoutResourceOwnerAddresses*,uint32_t);
EpPropertyResult ep_loadout_resource_owner_build(const EpLoadoutResourceOwnerAddresses*,EpLoadoutResourceOwnerImage*);
EpPropertyResult ep_loadout_resource_owner_prepare(const HfApi*,HfMod*,const EpLoadoutResourceOwnerAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
