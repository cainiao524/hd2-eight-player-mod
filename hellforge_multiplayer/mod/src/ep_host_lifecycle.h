#ifndef EP_HOST_LIFECYCLE_H
#define EP_HOST_LIFECYCLE_H
#include "ep_client_disconnect.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {EP_HOST_START=1,EP_HOST_RESUME=2,EP_HOST_LOOKUP=3};
typedef struct EpHostLifecycleAddresses {
    uint64_t game,code,client,confirmed,reject,peers,flags,large,pending;
    uint32_t capacity,reserved;
} EpHostLifecycleAddresses;
typedef struct EpHostLifecycleImage {
    uint32_t bytes,table_offset,function_count,handler_offset,body_offset,source_rva;
    uint8_t data[4096];
} EpHostLifecycleImage;
/* Saved 1088A30 start, 1088D80 resume, 108B520 slot lookup. The original host
 * remains embedded at client-918h, with its owner backpointer unchanged.
 * Separate banks hold capacity x 38h host records, capacity byte flags,
 * capacity x 1C0h large records, capacity x 40h pending records. Confirmed
 * client peers use their existing capacity x 20h shared bank and client+C8
 * count. Host records and confirmed records are different layouts/identities.
 *
 * Start clears full host records/flags/large records, preserving the native
 * one-self-peer confirmed reset. Resume clears only host record ID/state,
 * preserves opaque bytes, and maps self through the confirmed bank's NETWORK
 * INDEX (not ordinal); only native -1/no-match falls back to zero. Pending is
 * not reset by these bodies. Lookup returns the actual 38h record or NULL,
 * including native empty-slot lookup with peer=0; it never invents a slot.
 *
 * Numeric emission/preparation ONLY: no allocation/import of data, publication,
 * activation or game access. Caller must supply immutable same-owner bindings,
 * migrate all host consumers/constructors and retain all banks before exposure.
 * Entire native calls and returned-pointer use need the shared owner lease.
 * Other host migration/removal/pending methods and client-update's four-slot
 * guard still require conversion before these candidates can switch together.
 * Rejection is nonreturning; late failures require quarantine, never replay.
 */
EpPropertyResult ep_host_lifecycle_build(uint32_t,const EpHostLifecycleAddresses*,EpHostLifecycleImage*);
EpPropertyResult ep_host_lifecycle_prepare(const HfApi*,HfMod*,uint32_t,const EpHostLifecycleAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
