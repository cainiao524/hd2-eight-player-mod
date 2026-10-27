#ifndef EP_LOADOUT_RECORDS_H
#define EP_LOADOUT_RECORDS_H
#include "ep_loadout_consumers.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_RECORDS_BYTES 8192u
typedef struct EpLoadoutRecordSource {
    uint64_t manager,actors,equipment,status;
} EpLoadoutRecordSource;
typedef struct EpLoadoutRecordsAddresses {
    EpLoadoutConsumerAddresses common;
    EpLoadoutRecordSource source;
} EpLoadoutRecordsAddresses;
typedef struct EpLoadoutRecordsImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,handler_offset;
    uint8_t data[EP_LOADOUT_RECORDS_BYTES];
} EpLoadoutRecordsImage;
/* Complete saved 146FC40 record synchronization. Native source manager
 * [game+33264F8] retains its hash/catalog ABI. Source arrays replace +948
 * actor pointers (stride 8), +A7C equipment rows (stride 40h), and +994
 * status bytes (stride 44h). Source ordinal is NOT a network or UI index.
 * Missing/out-of-range source identity rejects before indexing those arrays.
 * Caller owns these arrays and must bind ALL their other producers/consumers
 * before publication. actor descriptors and all external catalogs/services
 * retain native ABI/lifetime requirements; this does not migrate them.
 * Shared record storage is network-indexed, widgets use validated forward/
 * inverse maps; unmapped UI slots keep native FF behavior. Eight activity
 * bytes use existing stack slack, leaving the original 1490h GS/probe frame.
 * Four inner equipment choices remain four. Unseen record peers are cleared.
 * No game discovery, reads, initialization, hooks or automatic invocation.
 * The frame group routes caller 1469A9F. Other source writers, exclusion and common
 * activation remain required. READY does not enable a working game UI. */
EpPropertyResult ep_loadout_records_build(const EpLoadoutRecordsAddresses*,EpLoadoutRecordsImage*);
/* Shared confirmed-peer variant; use the same retained bank and exclusion as
 * the roster and all sibling UI families. Group preparation binds these calls. */
EpPropertyResult ep_loadout_records_build_peers(const EpLoadoutRecordsAddresses*,const EpPlayerJoinPeers*,EpLoadoutRecordsImage*);
/* Numerical range validation only; never dereferences supplied addresses. */
EpPropertyResult ep_loadout_records_validate(const EpLoadoutRecordsAddresses*);
EpPropertyResult ep_loadout_records_validate_span(const EpLoadoutRecordsAddresses*,uint32_t code_bytes);
EpPropertyResult ep_loadout_records_prepare(const HfApi*,HfMod*,const EpLoadoutRecordsAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
