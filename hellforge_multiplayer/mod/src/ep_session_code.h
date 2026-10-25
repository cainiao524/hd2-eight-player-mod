#ifndef EP_SESSION_CODE_H
#define EP_SESSION_CODE_H
#include "hellforge_mod.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_SESSION_CODE_SLOTS 64u
#define EP_SESSION_CODE_MAX_BYTES 65536u
typedef enum EpSessionCodeState {
    EP_CODE_EMPTY, EP_CODE_RESERVED, EP_CODE_READY, EP_CODE_FAILED,
    EP_CODE_PUBLISHING, EP_CODE_PUBLISHED, EP_CODE_PUBLISH_FAILED
} EpSessionCodeState;
typedef struct EpSessionCodeInfo {
    uint64_t handle;
    uintptr_t base, next_pointer;
    uint32_t bytes, state, registered, pinned;
} EpSessionCodeInfo;
/* Internal Mod API, not an SDK extension or automatic installation path.
 * Reserve returns numerical addresses for address-bound generation. Do not
 * write/call them directly. The original-variable address stays fixed.
 * desired_base=0 lets Windows choose; otherwise exact allocation is required.
 * All functions return 1 on success, unlike HellForge hook_ex (0=success).
 * Caller must preflight the real target/build/code and every external resource.
 * API callbacks must not throw. The generated body must match its unwind data.
 */
int ep_session_code_reserve(const HfApi*, HfMod*, uintptr_t desired_base,
                            uint32_t bytes, EpSessionCodeInfo*);
/* Single function at offset 0; flags=0, no frame register; only PUSH_NONVOL,
 * ALLOC_SMALL and SAVE_NONVOL are accepted. Layout matches the two current
 * property emitters. This checks structure, not instruction equivalence. */
int ep_session_code_seal(HfMod*, uint64_t handle, const void* image,
                         uint32_t bytes, uint32_t table_offset);
/* One to three sorted, nonoverlapping functions, with separate unwind blocks
 * after all code and before the final table. Used by gate + candidate images. */
int ep_session_code_seal_table(HfMod*, uint64_t handle, const void* image,
                              uint32_t bytes, uint32_t table_offset, uint32_t count);
int ep_session_code_info(HfMod*, uint64_t handle, EpSessionCodeInfo*);
/* Before calling hook_ex, permanently pin this module and the image. Even a
 * reported hook failure can have exposed code: keep it for process lifetime.
 * No retry, detach or active-image release is offered. Never unload this Mod
 * or free data referenced by published code while it can be reached. */
int ep_session_code_publish(HfMod*, uint64_t handle, uintptr_t target, int32_t priority);
/* Only never-published images. Caller must not have exposed the base by any
 * other path. Failed unregistration retains backing memory for a retry. */
int ep_session_code_discard(HfMod*, uint64_t handle);
#ifdef __cplusplus
}
#endif
#endif
