#ifndef EP_INSERT_IMAGE_H
#define EP_INSERT_IMAGE_H
#include "ep_property_image.h"
#include "ep_session_code.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef enum EpInsertKind {
    EP_INSERT_DENSE_LEGACY=1, EP_INSERT_APPEND_LEGACY=2,
    EP_INSERT_APPEND_REGISTERED=3, EP_INSERT_DENSE_REGISTERED=4
} EpInsertKind;
typedef struct EpInsertAddresses {
    uint64_t game_base,code_address,roster_address,storage_address,move_code_address,reject_address;
} EpInsertAddresses;
/* Numeric-only generation. The mover must use this build's complete image.
 * No ownership, membership admission, publication or automatic initialization. */
EpPropertyResult ep_insert_image_build(uint32_t,const EpInsertAddresses*,EpPropertyImage*);
/* Successful preparation stops at cancellable READY; CLEANUP retains a handle. */
EpPropertyResult ep_insert_code_prepare(const HfApi*,HfMod*,uint32_t,const EpInsertAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
