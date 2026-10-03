#pragma once

#include <windows.h>

// The fixed-build callback-vector leaf is known, but the event-hash to
// selector producer is not.  This adapter decodes only the observed wrapper
// shape and refuses every selector except the pinned confirmed-peer slot.
#define EP_RECEIVER_MAGIC 0x45505256u /* "EPRV" */
#define EP_RECEIVER_VERSION 1u
#define EP_RECEIVER_SELECTOR_CONFIRMED_PEER 168u
#define EP_RECEIVER_DESCRIPTOR_SIZE 0x50u

extern "C" {

typedef enum EP_RECEIVER_STATUS : UINT32 {
    EP_RV_OK = 0,
    EP_RV_INVALID_ARGUMENT = 1,
    EP_RV_INVALID_CONTEXT = 2,
    EP_RV_UNSUPPORTED_SELECTOR = 3,
    EP_RV_MISSING_FIELD = 4,
} EP_RECEIVER_STATUS;

typedef struct EP_RECEIVER_DESCRIPTOR {
    BYTE opaque[EP_RECEIVER_DESCRIPTOR_SIZE];
} EP_RECEIVER_DESCRIPTOR;

typedef struct EP_RECEIVER_VALUES {
    UINT64 field0;
    UINT64 field1;
    UINT64 field2;
    UINT32 field3;
    BYTE field4;
    BYTE reserved[3];
} EP_RECEIVER_VALUES;

typedef struct EP_RECEIVER_ADAPTER {
    UINT32 magic;
    UINT32 version;
    UINT32 initialized;
    UINT32 selector;
    void* owner;
} EP_RECEIVER_ADAPTER;

__declspec(dllexport) EP_RECEIVER_STATUS __cdecl ep_receiver_init(
    EP_RECEIVER_ADAPTER* adapter, void* owner);
__declspec(dllexport) EP_RECEIVER_STATUS __cdecl ep_receiver_destroy(
    EP_RECEIVER_ADAPTER* adapter);
__declspec(dllexport) EP_RECEIVER_STATUS __cdecl ep_receiver_decode(
    EP_RECEIVER_ADAPTER* adapter, UINT32 selector,
    const EP_RECEIVER_DESCRIPTOR* descriptor, EP_RECEIVER_VALUES* out_values);
__declspec(dllexport) UINT32 __cdecl ep_receiver_selector();

}
