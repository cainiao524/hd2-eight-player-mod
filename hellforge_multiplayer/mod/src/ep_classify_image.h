#ifndef EP_CLASSIFY_IMAGE_H
#define EP_CLASSIFY_IMAGE_H
#include "ep_getter_image.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef enum EpClassifyKind { EP_CLASSIFY_ENTER=1, EP_CLASSIFY_LEAVE=2 } EpClassifyKind;
typedef EpGetterAddresses EpClassifyAddresses;
typedef struct EpClassifyImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset;
    uint8_t data[2768];
} EpClassifyImage;
/* Explicit numeric bindings; no memory access, admission or publication. */
EpPropertyResult ep_classify_image_build(uint32_t,const EpClassifyAddresses*,EpClassifyImage*);
/* Prepared images stop at cancellable READY; CLEANUP retains a retry handle. */
EpPropertyResult ep_classify_code_prepare(const HfApi*,HfMod*,uint32_t,const EpClassifyAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
