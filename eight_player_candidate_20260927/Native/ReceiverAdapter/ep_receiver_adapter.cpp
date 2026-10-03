#include "ep_receiver_adapter.h"
#include <cstring>

namespace {
template <typename T> T read_field(const BYTE* base, SIZE_T offset) {
    T value{}; std::memcpy(&value, base + offset, sizeof(value)); return value;
}
bool valid(const EP_RECEIVER_ADAPTER* a) {
    return a && a->magic == EP_RECEIVER_MAGIC && a->version == EP_RECEIVER_VERSION && a->initialized && a->owner;
}
}

extern "C" {

EP_RECEIVER_STATUS __cdecl ep_receiver_init(EP_RECEIVER_ADAPTER* a, void* owner) {
    if (!a || !owner) return EP_RV_INVALID_ARGUMENT;
    std::memset(a, 0, sizeof(*a)); a->magic = EP_RECEIVER_MAGIC; a->version = EP_RECEIVER_VERSION;
    a->initialized = 1; a->selector = EP_RECEIVER_SELECTOR_CONFIRMED_PEER; a->owner = owner; return EP_RV_OK;
}

EP_RECEIVER_STATUS __cdecl ep_receiver_destroy(EP_RECEIVER_ADAPTER* a) {
    if (!valid(a)) return EP_RV_INVALID_CONTEXT;
    std::memset(a, 0, sizeof(*a)); return EP_RV_OK;
}

EP_RECEIVER_STATUS __cdecl ep_receiver_decode(EP_RECEIVER_ADAPTER* a, UINT32 selector,
                                               const EP_RECEIVER_DESCRIPTOR* descriptor,
                                               EP_RECEIVER_VALUES* out) {
    if (!valid(a) || !out) return EP_RV_INVALID_CONTEXT;
    if (selector != EP_RECEIVER_SELECTOR_CONFIRMED_PEER) return EP_RV_UNSUPPORTED_SELECTOR;
    if (!descriptor) return EP_RV_INVALID_ARGUMENT;
    const BYTE* bytes = descriptor->opaque;
    const UINT64 p0 = read_field<UINT64>(bytes, 0x08);
    const UINT64 p1 = read_field<UINT64>(bytes, 0x18);
    const UINT64 p2 = read_field<UINT64>(bytes, 0x28);
    const UINT64 p3 = read_field<UINT64>(bytes, 0x38);
    const UINT64 p4 = read_field<UINT64>(bytes, 0x48);
    if (!p0 || !p1 || !p2 || !p3 || !p4) return EP_RV_MISSING_FIELD;
    const BYTE* f0 = reinterpret_cast<const BYTE*>(static_cast<ULONG_PTR>(p0));
    const BYTE* f1 = reinterpret_cast<const BYTE*>(static_cast<ULONG_PTR>(p1));
    const BYTE* f2 = reinterpret_cast<const BYTE*>(static_cast<ULONG_PTR>(p2));
    const BYTE* f3 = reinterpret_cast<const BYTE*>(static_cast<ULONG_PTR>(p3));
    const BYTE* f4 = reinterpret_cast<const BYTE*>(static_cast<ULONG_PTR>(p4));
    out->field0 = read_field<UINT64>(f0, 0);
    out->field1 = read_field<UINT64>(f1, 0);
    out->field2 = read_field<UINT64>(f2, 0);
    out->field3 = read_field<UINT32>(f3, 0);
    out->field4 = read_field<BYTE>(f4, 0);
    std::memset(out->reserved, 0, sizeof(out->reserved)); return EP_RV_OK;
}

UINT32 __cdecl ep_receiver_selector() { return EP_RECEIVER_SELECTOR_CONFIRMED_PEER; }

}
