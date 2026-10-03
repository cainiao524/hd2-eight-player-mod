#include "ep_receiver_adapter.h"
#include <cstdio>
#include <cstring>

static bool check(bool ok, const char* label) { if (!ok) std::fprintf(stderr, "failed: %s\n", label); return ok; }

int main() {
    EP_RECEIVER_ADAPTER adapter{}; int owner = 1; bool ok = check(ep_receiver_init(&adapter, &owner) == EP_RV_OK, "init");
    EP_RECEIVER_DESCRIPTOR descriptor{}; UINT64 a = 0x1111, b = 0x2222, c = 0x3333; UINT32 d = 7; BYTE e = 1;
    std::memcpy(descriptor.opaque + 0x08, &a, sizeof(a)); std::memcpy(descriptor.opaque + 0x18, &b, sizeof(b));
    std::memcpy(descriptor.opaque + 0x28, &c, sizeof(c)); UINT64 pd = reinterpret_cast<UINT64>(&d), pe = reinterpret_cast<UINT64>(&e);
    std::memcpy(descriptor.opaque + 0x38, &pd, sizeof(pd)); std::memcpy(descriptor.opaque + 0x48, &pe, sizeof(pe));
    // The first three descriptor pointers also point to stable synthetic words.
    UINT64 pa = reinterpret_cast<UINT64>(&a), pb = reinterpret_cast<UINT64>(&b), pc = reinterpret_cast<UINT64>(&c);
    std::memcpy(descriptor.opaque + 0x08, &pa, sizeof(pa)); std::memcpy(descriptor.opaque + 0x18, &pb, sizeof(pb));
    std::memcpy(descriptor.opaque + 0x28, &pc, sizeof(pc));
    EP_RECEIVER_VALUES values{}; ok &= check(ep_receiver_decode(&adapter, 168, &descriptor, &values) == EP_RV_OK, "selector168");
    ok &= check(values.field0 == a && values.field1 == b && values.field2 == c && values.field3 == d && values.field4 == e, "decoded fields");
    ok &= check(ep_receiver_decode(&adapter, 167, &descriptor, &values) == EP_RV_UNSUPPORTED_SELECTOR, "unknown selector");
    EP_RECEIVER_DESCRIPTOR missing{}; ok &= check(ep_receiver_decode(&adapter, 168, &missing, &values) == EP_RV_MISSING_FIELD, "missing field");
    ok &= check(ep_receiver_destroy(&adapter) == EP_RV_OK, "destroy");
    if (!ok) return 1; std::puts("ep_receiver_adapter_synthetic_passed"); return 0;
}
