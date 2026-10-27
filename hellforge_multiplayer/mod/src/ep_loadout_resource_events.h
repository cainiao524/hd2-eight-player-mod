#ifndef EP_LOADOUT_RESOURCE_EVENTS_H
#define EP_LOADOUT_RESOURCE_EVENTS_H
#include "ep_loadout_resource_owner.h"
#ifdef __cplusplus
extern "C" {
#endif
#define EP_LOADOUT_RESOURCE_EVENTS_BYTES 8192u
typedef EpLoadoutResourceOwnerAddresses EpLoadoutResourceEventsAddresses;
typedef struct EpLoadoutResourceEventsImage {
    uint32_t bytes,code_bytes,unwind_offset,table_offset,function_count;
    uint32_t initialize,publish;
    uint8_t data[EP_LOADOUT_RESOURCE_EVENTS_BYTES];
} EpLoadoutResourceEventsImage;
/* Saved 66ACF0 initialization and 66AF10 transform publication callbacks.
 * Native object hash, phase reset, property variant and transform services
 * retain their ABI. Resource names match case-sensitive hellpod1..capacity
 * without leading zeroes or suffixes. This replaces the four-name dispatch;
 * it does not create physical pods or supply new engine property values.
 * Initializing a row first clears its previous ordinal/known flag. Missing,
 * wrong-type and unrecognized properties remain unbound. Publication skips
 * unbound/out-of-range rows, bounds hash ordinals and scans the shared bank.
 * Caller retains the owner/hash, registered objects, property-service string
 * and transform lifetimes, and excludes mutation throughout each callback.
 * Replicated state initialization, queued publication, ownership callbacks,
 * physical resource creation and remaining consumers still need routing.
 * No game access, original writes, hooks, activation or runtime verification. */
EpPropertyResult ep_loadout_resource_events_build(const EpLoadoutResourceEventsAddresses*,EpLoadoutResourceEventsImage*);
EpPropertyResult ep_loadout_resource_events_prepare(const HfApi*,HfMod*,const EpLoadoutResourceEventsAddresses*,EpSessionCodeInfo*);
#ifdef __cplusplus
}
#endif
#endif
