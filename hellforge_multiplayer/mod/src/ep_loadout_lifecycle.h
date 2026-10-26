#ifndef EP_LOADOUT_LIFECYCLE_H
#define EP_LOADOUT_LIFECYCLE_H
#include "ep_property_image.h"
#include "ep_session_code.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_RECORD_BYTES 0x9f0u
#define EP_LOADOUT_WIDGET_BYTES 0x1ee18u
#define EP_LOADOUT_SCREEN_BYTES 0x2739d0u
#define EP_LOADOUT_LIFECYCLE_LIMIT 8u
typedef struct EpLoadoutAddresses {
    uint64_t game,code,screen,records,widgets,reject;
    uint32_t capacity,reserved;
} EpLoadoutAddresses;
typedef struct EpLoadoutImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset;
    uint32_t constructor,release,alternate_release,function_count;
    uint8_t data[4096];
} EpLoadoutImage;
/* Saved build 25480438: 14A17E0 constructor and 1467330/1467720 releases.
 * Explicit per-screen records/widgets, configurable 1..8 native player slots.
 * Constructor initializes the original record fields and calls real 14AA5C0
 * once per widget. Releases preserve distinct +4548/+1FA8 nested members and
 * original callback ordering/conditions. All other screen members stay inline.
 * 189D050's four entries are INSIDE each widget (stride 12A8), not the outer
 * player widget array (stride 1EE18); those limits are deliberately preserved.
 * Pure numeric generation. Caller supplies correctly sized/aligned, retained
 * distinct allocations, current source/build validation, exclusion, and a
 * nonreturning rejection target. A fault midway through native construction
 * or release is not rollback and must not be retried/freed blindly.
 * NOT complete UI relocation: maps, runtime consumers, transition (including
 * its GS handler), callbacks and package lifetime still need integration.
 * No game discovery, allocation of screen/data, activation or Mod-init binding.
 * The limit is this adapter's implemented capacity, not verified player count.
 */
EpPropertyResult ep_loadout_lifecycle_build(const EpLoadoutAddresses*,EpLoadoutImage*);
/* One cancellable READY image holds all three entries and six unwind rows.
 * CLEANUP returns a retained handle; caller must retry discard. Does not
 * publish hooks or own/construct/release any supplied screen/data allocation. */
EpPropertyResult ep_loadout_lifecycle_prepare(const HfApi*,HfMod*,const EpLoadoutAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
