#ifndef EP_LOADOUT_FRAME_H
#define EP_LOADOUT_FRAME_H
#include "ep_loadout_records.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_FRAME_BYTES 16384u
typedef struct EpLoadoutFrameAddresses {
    EpLoadoutRecordsAddresses records;
    uint64_t sync_records,update,lookup,open_mode;
} EpLoadoutFrameAddresses;
typedef struct EpLoadoutFrameImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,handler_offset,frame,local_update;
    uint8_t data[EP_LOADOUT_FRAME_BYTES];
} EpLoadoutFrameImage;
/* Complete saved 1468320 main frame and 146C040 local-player refresh.
 * Calls use the same group's record sync, UI update, record lookup and mode open.
 * Player/widget scans use capacity; record-item and equipment limits retain
 * their native meaning. R11 remains the live record iterator on the tail scan.
 * Deferred local-map initialization clears owned forward/inverse maps before
 * assigning UI slot zero. Invalid focus/network/count indices reject before
 * indexing. Both entry points require the bound screen/roster identity.
 * Original GS frame and local/helper chain topology are preserved.
 * Other native callees (including 146BBB0,146B400,146A5B0,146AC60,
 * 146B190,146BE90), all source writers and lifetimes, owner exclusion and
 * common publication still require routing/review. READY does not enable UI.
 * No discovery, game access, hooks, data initialization or automatic calls. */
EpPropertyResult ep_loadout_frame_build(const EpLoadoutFrameAddresses*,EpLoadoutFrameImage*);
EpPropertyResult ep_loadout_frame_prepare(const HfApi*,HfMod*,const EpLoadoutFrameAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
