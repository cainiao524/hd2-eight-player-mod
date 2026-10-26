#ifndef EP_COMPONENT33_OUTER_H
#define EP_COMPONENT33_OUTER_H
#include "ep_component33_readers.h"
#include "ep_component33_consumers.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpComponent33OuterPlan {
    EpComponent33Image bridge;
    EpComponent33ReaderWindow windows[5];
} EpComponent33OuterPlan;
/* Numeric emission only. Three original pointer MOVs become calls to two
 * getters; two original RELEASE calls bind the exact same-family image.
 * Getters preserve all registers except the original MOV destination.
 * Arithmetic flags are overwritten by pinned following CMP/TEST instructions
 * before use. Six volatile saves have complete Windows unwind metadata.
 * Refusal restores the bridge stack then transfers to the nonreturning
 * rejection continuation; it must never return into the parent interior.
 * All five windows, matching S/B/release and full parent unwind require common
 * publication and exclusion. Prior outer/resource side effects are not rolled
 * back; original resource queue limits and other registry tags are unchanged.
 * No source/target address is dereferenced and no hook is installed here. */
EpPropertyResult ep_component33_outer_build(const EpC33ConsumerAddresses*,EpComponent33OuterPlan*);
uint32_t ep_component33_outer_image_bytes(void);
typedef struct EpC33RefreshAddresses { uint64_t game_base,code_address,acquire_address; } EpC33RefreshAddresses;
/* Saved B5E710 registry traversal, object in RCX. Preserves tag filtering,
 * empty dense-set bypass and all original stack/unwind boundaries. Replaces
 * the inline selected-component release/load loop with ACQUIRE(S,object),
 * so complete demand admission precedes resource effects. The callee must
 * enforce the exact owned component and must not return on refusal. Caller
 * must hold the same roster owner over the COMPLETE traversal. This image
 * itself neither checks source pointers nor installs an entry. Other tags
 * keep the original skip behavior. Whole-entry publication supersedes all
 * old B5E710 interior resource/getter/release windows. */
uint32_t ep_component33_refresh_image_bytes(void);
EpPropertyResult ep_component33_refresh_build(const EpC33RefreshAddresses*,EpComponent33Image*);
#ifdef __cplusplus
}
#endif
#endif
