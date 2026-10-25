#ifndef EP_PROPERTY_GATE_H
#define EP_PROPERTY_GATE_H
#include "ep_property_image.h"
#include "ep_getter_image.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { EP_PROPERTY_GATE_BYTES=32, EP_PROPERTY_GATED_MAX=756 };
typedef struct EpPropertyGateImage {
    uint32_t bytes,table_offset;
    uint8_t data[EP_PROPERTY_GATED_MAX];
} EpPropertyGateImage;
/* addresses.code_address is the complete allocation base; candidate begins
 * at +32. control is an aligned LONG, next_pointer the SDK's stable void**.
 * Gate reads control==1, else tail-jumps through the current *next_pointer.
 * Windows x64 ABI: RAX/flags are volatile; argument registers, XMM and stack
 * are untouched. No calls or pushes in the gate. Two independent unwind rows.
 * Numerical inputs only; actual control/next lifetime belongs to the group. */
EpPropertyResult ep_property_gate_build(uint32_t,const EpPropertyAddresses*,
                                        uint64_t control,uint64_t next_pointer,EpPropertyGateImage*);
EpPropertyResult ep_getter_gate_build(const EpGetterAddresses*,
                                      uint64_t control,uint64_t next_pointer,EpPropertyGateImage*);
#ifdef __cplusplus
}
#endif
#endif
