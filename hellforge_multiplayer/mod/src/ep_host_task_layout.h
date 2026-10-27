#ifndef EP_HOST_TASK_LAYOUT_H
#define EP_HOST_TASK_LAYOUT_H
/* Private staged layout, never an in-place extension of the native host.
 * Eight primary IDs at +10; up to 8*7 ordered 32-byte pair records at +60.
 * The configured capacity bounds both counts (C and C*(C-1)); unused physical
 * room does not raise negotiated capacity. Reserve full strides even at C<8.
 * Pending rows keep the task ID/count/member fields and move their final key
 * to +50. Import/export and EVERY producer/consumer must use this layout before
 * activation. Native 1C0/40 rows require field-wise conversion, not memcpy.
 */
#define EP_HOST_TASK_STRIDE 0x800u
#define EP_HOST_TASK_SECONDARY_COUNT 0x50u
#define EP_HOST_TASK_SECONDARY_START 0x60u
#define EP_HOST_PENDING_STRIDE 0x60u
#define EP_HOST_PENDING_KEY 0x50u
#endif
