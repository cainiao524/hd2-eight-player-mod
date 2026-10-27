#ifndef EP_LOADOUT_RESOURCE_SYNC_H
#define EP_LOADOUT_RESOURCE_SYNC_H
#include "ep_loadout_resource_owner.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_RESOURCE_SYNC_BYTES 8192u
typedef EpLoadoutResourceOwnerAddresses EpLoadoutResourceSyncAddresses;
typedef struct EpLoadoutResourceSyncImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t emit_initial,receive;
    uint8_t data[EP_LOADOUT_RESOURCE_SYNC_BYTES];
} EpLoadoutResourceSyncImage;
/* Saved 66BDA0 initial-state emission and 66BEA0 state reception.
 * Hash ordinals select the shared replicated-state bank after dense moves.
 * Emission resets the object's state and appends one 16-byte record with
 * native event 82830AED, type 1 and a retained four-byte allocator payload.
 * ABI: RDX object, R9 output records, stack arg5 uint32 count*, arg6 allocator*.
 * Caller must retain count+1 output records, count and allocator backing;
 * the native ABI does not carry an output capacity. Count overflow rejects.
 * Reception ABI: RCX owner, EDX object ID, R8 payload base, R9 uint32 cursor*.
 * Caller validates payload extent and retains four readable bytes at cursor;
 * this entry bounds hash ordinals and cursor overflow, not packet length.
 * Retain owner/hash/objects and exclude mutation through native callbacks.
 * No network transport, callback routing, hooks or runtime verification. */
EpPropertyResult ep_loadout_resource_sync_build(const EpLoadoutResourceSyncAddresses*,EpLoadoutResourceSyncImage*);
EpPropertyResult ep_loadout_resource_sync_prepare(const HfApi*,HfMod*,const EpLoadoutResourceSyncAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
