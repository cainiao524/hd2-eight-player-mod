#ifndef EP_LOADOUT_PROMPT_H
#define EP_LOADOUT_PROMPT_H
#include "ep_loadout_consumers.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_PROMPT_BYTES 8192u
typedef struct EpLoadoutPromptImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t update,selection,active,ready_flag,blocked_flag;
    uint8_t data[EP_LOADOUT_PROMPT_BYTES];
} EpLoadoutPromptImage;
/* Saved 146B400 dispatch, 146B5A0 selection and 146B710 active-mode panel.
 * Peer searches use the shared dense roster bank; local ready state uses its
 * first flags row. The saved 60B3B0/60B460 queries retain native hash probing,
 * sentinel handling and EDX preservation, then read the bounded shared flags.
 * Button IDs 0..5 and mission-mode choices stay native.
 * The dispatcher tail-calls the guarded active entry in this same image.
 * The frame binds update. External callers of selection/active/flag queries
 * still require routing, matching owner lifetime and publication exclusion.
 * Builds/prepares owned code only: no game access, hooks or activation. */
EpPropertyResult ep_loadout_prompt_build(const EpLoadoutConsumerAddresses*,EpLoadoutPromptImage*);
EpPropertyResult ep_loadout_prompt_prepare(const HfApi*,HfMod*,const EpLoadoutConsumerAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
