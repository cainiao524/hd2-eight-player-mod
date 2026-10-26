#ifndef EP_LOADOUT_RESOURCES_H
#define EP_LOADOUT_RESOURCES_H
#include "ep_loadout_countdown.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_RESOURCES_BYTES 8192u
typedef struct EpLoadoutResourcesAddresses {
    EpLoadoutRecordsAddresses records;
    EpLoadoutCountdownSource source;
    uint64_t resource_lookup;
} EpLoadoutResourcesAddresses;
typedef struct EpLoadoutResourcesImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t write,ordinal,transform,player_value,assign;
    uint8_t data[EP_LOADOUT_RESOURCES_BYTES];
} EpLoadoutResourcesImage;
/* Full 65DE10 write callback, 661E70 ordinal lookup, 6619C0 transform,
 * 606820 player value and 662E90 assignment. All resource rows share the
 * countdown bank; ID + 64 transform bytes are written, last eight bytes kept.
 * Callback R9D and returned resource ordinal are bounded before indexing.
 * The local descriptor/value use roster B; player value retains EDX for the
 * following ordinal lookup. The owned fifteen-case transform switch keeps
 * native categories/default transforms (not player counts). Assignment calls
 * the group's countdown lookup. Engine callbacks, lifecycle/registration,
 * 66B090's inline writer and remaining readers/writers still need routing.
 * Native catalogs, transforms outside the resource bank and actor services
 * retain their ABI/retention/exclusion prerequisites. No game access, hooks,
 * publication or implicit initialization; READY is not runtime verification. */
EpPropertyResult ep_loadout_resources_build(const EpLoadoutResourcesAddresses*,EpLoadoutResourcesImage*);
EpPropertyResult ep_loadout_resources_prepare(const HfApi*,HfMod*,const EpLoadoutResourcesAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
