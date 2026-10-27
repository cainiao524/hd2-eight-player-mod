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
    uint32_t transition,handler_offset,construct_banks;
    uint8_t data[4096];
} EpLoadoutImage;
/* Saved build 25480438: 14A17E0 constructor, 1467330/1467720 releases,
 * and 1470A40 transition. The transition keeps the original virtual services,
 * 189E080/1451100 per-widget callbacks (including stack/float parameters),
 * screen state changes, user-state cleanup and security-cookie checks.
 * Explicit per-screen records/widgets, configurable 1..8 native player slots.
 * Constructor initializes the original record fields and calls real 14AA5C0
 * once per widget. Releases preserve distinct +4548/+1FA8 nested members and
 * original callback ordering/conditions. All other screen members stay inline.
 * Saved 1465820 calls 1467330 then tail-calls 1466170 setup on the SAME screen:
 * resource cleanup is also part of normal screen reset, not proof of terminal
 * destruction. 1467720 performs conditional nested-resource cleanup separately.
 * The owned call catalog routes both and owns the complete 1465820 wrapper;
 * it never frees/reconstructs banks merely because a cleanup body returned.
 * 189D050's four entries are INSIDE each widget (stride 12A8), not the outer
 * player widget array (stride 1EE18); those limits are deliberately preserved.
 * Pure numeric generation. Caller supplies correctly sized/aligned, retained
 * distinct allocations, current source/build validation, exclusion, and a
 * nonreturning rejection target. A fault midway through native construction
 * or release is not rollback and must not be retried/freed blindly.
 * NOT complete UI relocation: maps, runtime consumers, callback target
 * validation, lifetime/exclusion and package ownership still need integration.
 * No game discovery, allocation of screen/data, activation or Mod-init binding.
 * The limit is this adapter's implemented capacity, not verified player count.
 */
/* construct_banks is a separate entry for FRESH unexposed record/widget banks.
 * RCX must be the bound screen; RAX returns it. It runs the original record
 * initializer and 14AA5C0 once per configured widget, preserving the native
 * frame/inner widget resource loops. It omits every unrelated inline screen
 * write/call from the full constructor. It does NOT copy old widget ownership,
 * run setup, migrate records/maps, redirect external references, or publish UI.
 * Caller owes module/code/data retention, source validation and whole-call
 * exclusion before invocation. Never call twice or on live/constructed banks.
 * A partial native constructor fault is not rollback: keep all backing pinned
 * and quarantine the generation; do not call release or retry blindly.
 * Native helper side effects/lifetime remain part of the caller's engine gate.
 * Exposing this entry does not invoke it or authorize live game access. */
/* The transition must use the same group's guarded state-change entry.
 * This extra link is numeric only and must remain alive with this image. */
EpPropertyResult ep_loadout_lifecycle_build(const EpLoadoutAddresses*,uint64_t state_change,EpLoadoutImage*);
/* One cancellable READY image holds five entries and eleven unwind rows. The
 * transition keeps EH/UH __GSHandlerCheck at game+21044A0, with cookie +80
 * and an owned handler thunk. Caller must validate both native GS targets.
 * CLEANUP returns a retained handle; caller must retry discard. Does not
 * publish hooks or own/construct/release any supplied screen/data allocation. */
EpPropertyResult ep_loadout_lifecycle_prepare(const HfApi*,HfMod*,const EpLoadoutAddresses*,uint64_t state_change,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
