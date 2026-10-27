#ifndef EP_LOADOUT_COUNTDOWN_H
#define EP_LOADOUT_COUNTDOWN_H
#include "ep_loadout_records.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_COUNTDOWN_BYTES 8192u
typedef struct EpLoadoutCountdownSource {
    uint64_t manager,resources;
} EpLoadoutCountdownSource;
typedef struct EpLoadoutCountdownAddresses {
    EpLoadoutRecordsAddresses records;
    EpLoadoutCountdownSource source;
    uint64_t context_action,transition;
} EpLoadoutCountdownAddresses;
typedef struct EpLoadoutCountdownImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t update,resource_lookup,reset_timers;
    uint8_t data[EP_LOADOUT_COUNTDOWN_BYTES];
} EpLoadoutCountdownImage;
/* Full captured 146A5B0 countdown, 661FA0 resource lookup, 662880 timer reset.
 * The manager at game+33265F0 supplies a separate capacity-row 4Ch resource
 * bank replacing +11D18. Allocation mask and lookup scan share this bank.
 * Roster descriptors/peer scans use shared B storage. Source resource ordinal,
 * roster dense ordinal and actor index are distinct; neither is a UI slot.
 * All other resource-bank writers/consumers must bind this bank before use.
 * Native actor list/count (+50/+24), timer rows (+12EE3/+12EEC, stride54h),
 * hash catalogs, effect lookup and replication queue retain their ABI. Caller
 * must retain their full backing/capacity and exclude writers for each call;
 * the numerical manager span below covers only the directly known prefix.
 * Context/transition target sibling entries, with common ownership/lifetime.
 * No hooks, game access, initialization, publication or runtime claims. */
EpPropertyResult ep_loadout_countdown_validate_span(const EpLoadoutCountdownAddresses*,uint32_t code_bytes);
EpPropertyResult ep_loadout_countdown_build(const EpLoadoutCountdownAddresses*,EpLoadoutCountdownImage*);
/* Shared confirmed-peer variant; use the same retained bank and exclusion as
 * the roster and all sibling UI families. Group preparation binds these calls. */
EpPropertyResult ep_loadout_countdown_build_peers(const EpLoadoutCountdownAddresses*,const EpPlayerJoinPeers*,EpLoadoutCountdownImage*);
EpPropertyResult ep_loadout_countdown_prepare(const HfApi*,HfMod*,const EpLoadoutCountdownAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
