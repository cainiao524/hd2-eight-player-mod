#ifndef EP_REMOVE_IMAGE_H
#define EP_REMOVE_IMAGE_H
#include "ep_insert_image.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef enum EpRemoveKind { EP_REMOVE_LEGACY=1, EP_REMOVE_REGISTERED=2 } EpRemoveKind;
typedef EpInsertAddresses EpRemoveAddresses;
typedef struct EpRemoveImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset;
    uint8_t data[776];
} EpRemoveImage;
/* Explicit numeric bindings; no memory access, admission or publication. */
EpPropertyResult ep_remove_image_build(uint32_t,const EpRemoveAddresses*,EpRemoveImage*);
/* Prepared images stop at cancellable READY; CLEANUP retains a retry handle. */
EpPropertyResult ep_remove_code_prepare(const HfApi*,HfMod*,uint32_t,const EpRemoveAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
