#ifndef EP_CLIENT_METADATA_H
#define EP_CLIENT_METADATA_H
#include "ep_client_disconnect.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {EP_METADATA_CONSTRUCT=0,EP_METADATA_SEND=1,EP_METADATA_READY_LOOKUP=2,
      EP_METADATA_READY_FINISH=3,EP_METADATA_READY_ACK=4,EP_METADATA_ENTRY_COUNT=5};
typedef struct EpClientMetadataAddresses {
    uint64_t game,code,client,metadata,ready,reject;
    uint32_t capacity,reserved;
} EpClientMetadataAddresses;
typedef struct EpClientMetadataImage {
    uint32_t bytes,table_offset,function_count,entry[EP_METADATA_ENTRY_COUNT];
    uint8_t data[4096];
} EpClientMetadataImage;
/* Saved 1082F30 constructor, 1086AA0 metadata send, 1086920 readiness
 * lookup/append, 1086B70 completion and 1086B30 acknowledgment. Internal calls
 * use this image's guarded entries, not original inline-table implementations.
 * metadata is the SAME capacity*16 bank used by ep_host_accept; ready replaces
 * client+40's records (member ID, two bytes at +8/+9, six opaque bytes).
 * Readiness count remains client+38. All searches/appends use bounded counts.
 * At capacity an existing member remains findable; a new member rejects before
 * any write. Completion preserves full-record swap removal and both predicates.
 * Native field limits 90/60, state values, wire field widths/counts and service
 * calls are unchanged. This does not establish gameplay meaning for the fields.
 *
 * Constructor RCX=client, RDX=owner; it checks these identities before calling
 * original base registration, then preserves all original non-bank resets.
 * It initializes every metadata ID, sets row 0 to self, and preserves each
 * row's two DWORDs just like the original constructor. Supply initialized
 * backing storage on first construction. This is NOT an import/rejoin shortcut:
 * do not call it on a live client merely to migrate metadata, as it resets
 * native ID/confirmed/readiness counts and other object state.
 * Other entries take RCX=client and retain their original remaining arguments.
 * The lookup returns a leased pointer: compaction may move the record.
 *
 * Numeric generation/preparation only, no game discovery or activation. Bind
 * all producers/consumers to retained same-owner images and banks before any
 * publication. Player-join, removal, reset/update and other readiness readers
 * still need common-bank routing. Hold the owner lease throughout whole calls,
 * service callbacks and returned-pointer use. Reject never returns; failures
 * after native effects require quarantine, not replay or partial rollback.
 */
EpPropertyResult ep_client_metadata_build(const EpClientMetadataAddresses*,EpClientMetadataImage*);
EpPropertyResult ep_client_metadata_prepare(const HfApi*,HfMod*,const EpClientMetadataAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
