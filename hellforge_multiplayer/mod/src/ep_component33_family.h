#ifndef EP_COMPONENT33_FAMILY_H
#define EP_COMPONENT33_FAMILY_H
#include "ep_component33_readers.h"
#include "ep_session_code.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_C33_FAMILY_IMAGES=15, EP_C33_FAMILY_SLOTS=4,
    EP_C33_PREPARING=1, EP_C33_PREPARED, EP_C33_CLEANUP_REQUIRED, EP_C33_RETAINED };
typedef struct EpComponent33FamilyBindings {
    uint64_t game_base,component_address,storage_address,reject_address;
    uintptr_t desired_code[EP_C33_FAMILY_IMAGES];
} EpComponent33FamilyBindings;
typedef struct EpComponent33FamilyInfo {
    uint64_t handle;
    uint32_t state,reserved_images;
    EpSessionCodeInfo code[EP_C33_FAMILY_IMAGES];
    EpComponent33OwnerPatch owner_window;
    EpComponent33ReaderWindow reader_windows[2];
} EpComponent33FamilyInfo;
/* Reserves all fourteen core images and the shared reader bridge before any
 * emission. Uses this set's mover, reset and promotion addresses. PREPARED
 * means all pages are RX and every unwind table is registered, with all three
 * internal window plans bound to those exact pages. No game addresses are
 * dereferenced. No hook, window, registry, data or active switch is installed.
 * Desired allocations must permit all pinned rel32s; zero requests Windows'
 * choice, which can be rejected and cleaned up if out of range.
 * The family exclusively owns its session-code handles. Do not separately
 * publish, discard, retain or execute them. Failed cleanup returns a live
 * CLEANUP_REQUIRED handle for retry; it cannot be retained or published. */
EpPropertyResult ep_component33_family_prepare(const HfApi*,HfMod*,const EpComponent33FamilyBindings*,EpComponent33FamilyInfo*);
int ep_component33_family_info(HfMod*,uint64_t,EpComponent33FamilyInfo*);
int ep_component33_family_cancel(HfMod*,uint64_t);
/* Irreversibly retain the entire dependency set BEFORE a publisher can expose
 * any window/callback. Atomic lifetime transition only, NOT activation or
 * publication. A later failed publication must still retain the set and all
 * referenced external data/helpers. Caller must close remaining readers,
 * migration, rollback and whole-call exclusion before any target changes. */
int ep_component33_family_retain(HfMod*,uint64_t);
#ifdef __cplusplus
}
#endif
#endif
