#ifndef EP_PROPERTY_CODE_H
#define EP_PROPERTY_CODE_H
#include "ep_property_image.h"
#include "ep_session_code.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Reserve -> generate at the actual returned base -> seal/register. Never
 * publish. addresses.code_address=0 chooses an address; otherwise exact.
 * This does not search for nearby memory or inspect any game address.
 * On failure, cancel the unpublished allocation. If cancellation itself
 * fails, return EP_PROPERTY_CLEANUP and preserve its handle in out: the
 * owner must retry discard. Success leaves an owned, cancellable READY image.
 * API callbacks must not throw; caller must not expose code before publication.
 */
EpPropertyResult ep_property_code_prepare(const HfApi*, HfMod*, uint32_t kind,
                                         const EpPropertyAddresses*, EpSessionCodeInfo* out);
#ifdef __cplusplus
}
#endif
#endif
