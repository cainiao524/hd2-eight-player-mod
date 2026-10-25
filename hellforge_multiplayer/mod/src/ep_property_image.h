#ifndef EP_PROPERTY_IMAGE_H
#define EP_PROPERTY_IMAGE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_PROPERTY_PRODUCER=1, EP_PROPERTY_RECEIVER=2, EP_PROPERTY_MAX_IMAGE=708 };
typedef enum EpPropertyResult {
    EP_PROPERTY_OK, EP_PROPERTY_ARGUMENT, EP_PROPERTY_POINTER,
    EP_PROPERTY_OVERLAP, EP_PROPERTY_REL32, EP_PROPERTY_RESERVE,
    EP_PROPERTY_SEAL, EP_PROPERTY_CLEANUP
} EpPropertyResult;
typedef struct EpPropertyAddresses {
    uint64_t game_base, code_address, roster_address, property_address, reject_address;
} EpPropertyAddresses;
typedef struct EpPropertyImage {
    uint32_t bytes, code_bytes, unwind_offset, table_offset;
    uint8_t data[EP_PROPERTY_MAX_IMAGE];
} EpPropertyImage;
/* Fixed saved build 25480438. Only numerical validation and byte emission;
 * never dereference the supplied addresses. Zero output on failure. The
 * caller still owes current source identity, allocations, data lifetime,
 * synchronization and an interior-frame rejection handler. No normal return
 * handler is invented. A successful image is not permission to activate it.
 * Pure C ABI; no Python, disassembler or file access in the production Mod. */
EpPropertyResult ep_property_image_build(uint32_t kind, const EpPropertyAddresses*, EpPropertyImage*);
#ifdef __cplusplus
}
#endif
#endif
