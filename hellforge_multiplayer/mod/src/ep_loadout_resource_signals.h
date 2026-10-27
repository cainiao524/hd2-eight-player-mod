#ifndef EP_LOADOUT_RESOURCE_SIGNALS_H
#define EP_LOADOUT_RESOURCE_SIGNALS_H
#include "ep_loadout_resource_owner.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_RESOURCE_SIGNALS_BYTES 8192u
typedef EpLoadoutResourceOwnerAddresses EpLoadoutResourceSignalsAddresses;
typedef struct EpLoadoutResourceSignalsImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t finish,reset_effect;
    uint8_t data[EP_LOADOUT_RESOURCE_SIGNALS_BYTES];
} EpLoadoutResourceSignalsImage;
/* Saved 66B9B0 resource completion and 66BAD0 effect reset.
 * Completion searches shared resource ordinals, accepts native states 4/5,
 * dispatches the native effect and replicates state 5 for owned objects.
 * Effect reset resolves the current dense hash ordinal and uses shared
 * phase/resource rows and object pointers. Missing/removed objects return
 * without effects or array access; corrupt in-range hash entries reject.
 * State values, event IDs and effect categories keep their native meaning.
 * Caller retains owner/hash/catalog/service backing, resource ordinal
 * identity and callback arguments, and excludes mutation across services.
 * No network transport, callback routing, hooks or runtime verification. */
EpPropertyResult ep_loadout_resource_signals_build(const EpLoadoutResourceSignalsAddresses*,EpLoadoutResourceSignalsImage*);
EpPropertyResult ep_loadout_resource_signals_prepare(const HfApi*,HfMod*,const EpLoadoutResourceSignalsAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
