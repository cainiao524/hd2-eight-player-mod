#ifndef EP_SESSION_CODE_H
#define EP_SESSION_CODE_H
#include "hellforge_mod.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Four complete 17-entry roster groups; unrelated prepared images share this
 * bounded pool and can still cause clean reservation refusal. */
#define EP_SESSION_CODE_SLOTS 68u
#define EP_SESSION_CODE_MAX_BYTES 65536u
typedef enum EpSessionCodeState {
    EP_CODE_EMPTY, EP_CODE_RESERVED, EP_CODE_READY, EP_CODE_FAILED,
    EP_CODE_PUBLISHING, EP_CODE_PUBLISHED, EP_CODE_PUBLISH_FAILED, EP_CODE_RETAINED
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
 * ALLOC_SMALL, scaled ALLOC_LARGE, SAVE_NONVOL and SAVE_XMM128 are accepted.
 * This checks metadata structure, not instruction equivalence. */
int ep_session_code_seal(HfMod*, uint64_t handle, const void* image,
                         uint32_t bytes, uint32_t table_offset);
/* One to fifteen sorted, nonoverlapping functions with distinct metadata after
 * all code and before the final table. Handler-free chains must reference an
 * exact earlier owned row. Used by gate + candidate images. */
int ep_session_code_seal_table(HfMod*, uint64_t handle, const void* image,
                              uint32_t bytes, uint32_t table_offset, uint32_t count);
/* Opt-in for the pinned 6054F0 GS-only handler, not arbitrary EH metadata.
 * Keeps flags EHANDLER|UHANDLER, frame-relative cookie +96 and an owned rel32
 * tail thunk to the explicitly supplied original handler. Caller must verify
 * that target's identity/lifetime. Existing seal_table still rejects handlers.
 * Metadata validation does not prove instruction equivalence or game ABI. */
typedef struct EpSessionGsCheck {
    uint32_t function_index, handler_offset;
    uintptr_t handler_target;
} EpSessionGsCheck;
int ep_session_code_seal_gs_table(HfMod*, uint64_t handle, const void* image,
    uint32_t bytes, uint32_t table_offset, uint32_t count, const EpSessionGsCheck*);
/* Separate opt-in for component33 PROPERTY (6661A0): exact pinned prologue,
 * cookie +64, three rows, and shared leaf metadata for preflight/handler thunk.
 * Does not relax the existing handler-free or 6054F0 contracts. */
int ep_session_code_seal_component33_property(HfMod*, uint64_t handle, const void* image,
    uint32_t bytes, uint32_t table_offset, const EpSessionGsCheck*);
/* Loadout lifecycle opt-in: nine rows, transition at row 7, handler at row 8,
 * exact 1470A40 fixed-frame unwind including XMM6..8, EH/UH cookie +80.
 * Does not admit these handlers through the ordinary or other GS sealers. */
int ep_session_code_seal_loadout_transition(HfMod*, uint64_t handle, const void* image,
    uint32_t bytes, uint32_t table_offset, const EpSessionGsCheck*);
/* Separate 1466170 setup profile: three rows, exact original fixed-frame
 * unwind, EH/UH cookie +0x130 and owned handler thunk. */
int ep_session_code_seal_loadout_setup(HfMod*, uint64_t handle, const void* image,
    uint32_t bytes, uint32_t table_offset, const EpSessionGsCheck*);
/* 146E9D0 refresh only: guard + GS root + two owned chains + handler thunk.
 * Exact root prologue/cookie +0x70; both chains must name that root row. */
int ep_session_code_seal_loadout_refresh(HfMod*, uint64_t handle, const void* image,
    uint32_t bytes, uint32_t table_offset, const EpSessionGsCheck*);
/* 146FC40 record synchronization: seven rows, exact 1490h stack/probe frame,
 * GS cookie +1460h; four chains must retain their captured parent topology. */
int ep_session_code_seal_loadout_records(HfMod*, uint64_t handle, const void* image,
    uint32_t bytes, uint32_t table_offset, const EpSessionGsCheck*);
/* Main/local frame pair: twelve rows, exact prologue, GS cookie +3F0h and
 * captured parent topology for the main and seven local fragments. */
int ep_session_code_seal_loadout_frame(HfMod*, uint64_t handle, const void* image,
    uint32_t bytes, uint32_t table_offset, const EpSessionGsCheck*);
int ep_session_code_info(HfMod*, uint64_t handle, EpSessionCodeInfo*);
/* Before calling hook_ex, permanently pin this module and the image. Even a
 * reported hook failure can have exposed code: keep it for process lifetime.
 * No retry, detach or active-image release is offered. Never unload this Mod
 * or free data referenced by published code while it can be reached. */
int ep_session_code_publish(HfMod*, uint64_t handle, uintptr_t target, int32_t priority);
/* Atomically retain an entire READY dependency set before any non-SDK exposure
 * (internal windows or callback-table publication). No hooks or writes to
 * targets occur. Failure leaves every image unpinned; success is irreversible,
 * including when the later publication fails. A retained image may subsequently
 * enter the ordinary SDK publish path, but can never be discarded. Code/data lifetime and full-call
 * exclusion still belong to the publishing owner. Never use on an exposed set. */
int ep_session_code_retain_set(HfMod*, const uint64_t* handles, uint32_t count);
/* Only never-published images. Caller must not have exposed the base by any
 * other path. Failed unregistration retains backing memory for a retry. */
int ep_session_code_discard(HfMod*, uint64_t handle);
#ifdef __cplusplus
}
#endif
#endif
