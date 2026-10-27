#ifndef EP_LOADOUT_RESOURCE_MAIN_H
#define EP_LOADOUT_RESOURCE_MAIN_H
#include "ep_loadout_resource_owner.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_RESOURCE_MAIN_BYTES 16384u
typedef struct EpLoadoutResourceMainAddresses {
    EpLoadoutResourceOwnerAddresses owner;
    uint64_t reset_entry;
} EpLoadoutResourceMainAddresses;
typedef struct EpLoadoutResourceMainImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t update,query,handler_offset;
    uint8_t data[EP_LOADOUT_RESOURCE_MAIN_BYTES];
} EpLoadoutResourceMainImage;
/* Saved 65FA50 main resource update and 6620D0 published-object query.
 * Main takes RCX countdown manager and XMM1 delta, scans capacity resources,
 * updates the shared owned phases, and calls the supplied owned reset entry.
 * The captured native manager has ONE inline controller layout. Main rejects
 * counts +20/+24 above one before entering its body; this is a controller
 * constraint, independent of the expanded player/resource capacity.
 * Query takes RDX output uint32 pointer and R8D native sentinel argument,
 * returning the output pointer. It uses shared published object pointers;
 * missing native catalog keys are skipped without indexing a missing row.
 * Caller retains every native service, controller row, query output, catalog
 * hash/data/flags allocation and the reset image, excludes mutation, and
 * validates catalog ordinals against their independent backing. The native
 * query helper preserves live R9/R10/R11; keep its private ABI when routing.
 * GS metadata and a local handler thunk retain the original cookie contract.
 * No native actor expansion, physical object creation, hooks or activation.
 * These images do not establish game/runtime/multiplayer correctness. */
EpPropertyResult ep_loadout_resource_main_build(const EpLoadoutResourceMainAddresses*,EpLoadoutResourceMainImage*);
EpPropertyResult ep_loadout_resource_main_prepare(const HfApi*,HfMod*,const EpLoadoutResourceMainAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
