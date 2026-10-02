#include <windows.h>
#include <cstdio>
#include "ep_client_bridge_adapter.h"

static EP_BRIDGE_STATUS __cdecl native_create(void*, UINT64, UINT64, UINT8) {
    return EP_BRIDGE_OK;
}

int main() {
    EP_CLIENT_ADAPTER a{};
    if (ep_client_adapter_init(&a, &a, nullptr) != EP_BRIDGE_OK) return 10;
    if (ep_client_adapter_retain(&a) != EP_BRIDGE_OK) return 11;
    if (ep_client_adapter_confirm(&a, 100, 900, 4) != EP_BRIDGE_OK) return 12;
    if (ep_client_adapter_create(&a, 100, 900, 4) != EP_BRIDGE_CALLBACK_REJECTED) return 13;
    ep_client_adapter_release(&a);
    if (ep_client_adapter_remove(&a, 100, 900, 4) != EP_BRIDGE_OK) return 14;
    if (ep_client_adapter_destroy(&a) != EP_BRIDGE_OK) return 15;

    EP_CLIENT_ADAPTER b{};
    if (ep_client_adapter_init(&b, &b, native_create) != EP_BRIDGE_OK) return 16;
    if (ep_client_adapter_confirm(&b, 101, 901, 5) != EP_BRIDGE_OK ||
        ep_client_adapter_create(&b, 101, 901, 5) != EP_BRIDGE_OK ||
        ep_client_adapter_remove(&b, 101, 901, 5) != EP_BRIDGE_OK ||
        ep_client_adapter_destroy(&b) != EP_BRIDGE_OK) return 17;
    std::puts("ep_client_bridge_adapter_synthetic_passed");
    return 0;
}
