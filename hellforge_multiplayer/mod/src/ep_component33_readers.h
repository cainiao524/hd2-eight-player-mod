#ifndef EP_COMPONENT33_READERS_H
#define EP_COMPONENT33_READERS_H
#include "ep_component33_image.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct EpComponent33ReaderAddresses {
    uint64_t game_base,code_address,component_address,storage_address,reset_address,reject_address;
} EpComponent33ReaderAddresses;
typedef struct EpComponent33ReaderWindow {
    uint64_t target;
    uint32_t bytes,call_offset;
    uint8_t expected[16],replacement[16];
} EpComponent33ReaderWindow;
typedef struct EpComponent33ReaderPlan {
    EpComponent33Image bridge;
    EpComponent33ReaderWindow windows[2];
} EpComponent33ReaderPlan;
/* Numeric emission only. Both windows replace the pointer load AND its reset
 * call. The shared leaf takes RCX=S, RDX=ordinal, checks dense bounds, reads B
 * and tail-jumps to the exact prepared per-entity RESET image (664430), not
 * RESET_DENSE. It adds no frame; its own leaf unwind must be registered.
 * Caller must verify complete saved callers, original unwind and window bytes,
 * bind matching S/B/reset images, and publish all affected code/data under
 * whole-call exclusion. Earlier creation, flag writes and prior loop iterations
 * are NOT rolled back on refusal. D==0 retains the original bridge bypass.
 * Refusal must not return into an interior frame. No target is dereferenced
 * by this builder; it does not install either window or register any table. */
EpPropertyResult ep_component33_readers_build(const EpComponent33ReaderAddresses*,EpComponent33ReaderPlan*);
uint32_t ep_component33_readers_image_bytes(void);
#ifdef __cplusplus
}
#endif
#endif
