#include <windows.h>
#include <cstdio>
#include "ep_client_bridge_adapter.h"

static int g_confirm = 0;
static int g_create = 0;
static int g_remove = 0;
static int g_retain = 0;
static int g_release = 0;

static EP_BRIDGE_STATUS __cdecl native_confirm(void*, UINT64 peer, UINT64, UINT8) {
    ++g_confirm;
    return peer == 999 ? EP_BRIDGE_CALLBACK_REJECTED : EP_BRIDGE_OK;
}

static EP_BRIDGE_STATUS __cdecl native_create(void*, UINT64, UINT64, UINT8) {
    ++g_create;
    return EP_BRIDGE_OK;
}

static EP_BRIDGE_STATUS __cdecl native_remove(void*, UINT64, UINT64, UINT8) {
    ++g_remove;
    return EP_BRIDGE_OK;
}

static EP_BRIDGE_STATUS __cdecl native_retain(void*) { ++g_retain; return EP_BRIDGE_OK; }
static void __cdecl native_release(void*) { ++g_release; }

int main() {
    EP_CLIENT_ADAPTER a{};
    if (ep_client_adapter_init(&a, &a, nullptr, nullptr, nullptr, nullptr, nullptr) !=
        EP_BRIDGE_INVALID_ARGUMENT) return 10;

    EP_CLIENT_ADAPTER b{};
    if (ep_client_adapter_init(&b, &b, native_confirm, native_create, native_remove,
                               native_retain, native_release) != EP_BRIDGE_OK) return 11;
    if (ep_client_adapter_retain(&b) != EP_BRIDGE_OK) return 12;
    if (ep_client_adapter_confirm(&b, 100, 900, 4) != EP_BRIDGE_OK) return 13;
    if (ep_client_adapter_create(&b, 100, 900, 4) != EP_BRIDGE_OK) return 14;
    ep_client_adapter_release(&b);
    if (ep_client_adapter_remove(&b, 100, 900, 4) != EP_BRIDGE_OK) return 15;
    if (ep_client_adapter_confirm(&b, 999, 9999, 5) != EP_BRIDGE_CALLBACK_REJECTED) return 16;
    if (ep_client_adapter_create(&b, 999, 9999, 5) != EP_BRIDGE_CALLBACK_REJECTED) return 17;
    if (ep_client_adapter_destroy(&b) != EP_BRIDGE_CLEANUP_REQUIRED) return 20;
    if (ep_client_adapter_remove(&b, 999, 9999, 5) != EP_BRIDGE_OK) return 21;
    if (ep_client_adapter_destroy(&b) != EP_BRIDGE_OK) return 18;
    if (g_confirm != 2 || g_create != 1 || g_remove != 2 ||
        g_retain != 1 || g_release != 1) return 19;
    std::puts("ep_client_bridge_adapter_synthetic_passed");
    return 0;
}
