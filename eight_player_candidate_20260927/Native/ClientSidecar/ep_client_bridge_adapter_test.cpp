#include <windows.h>
#include <cstdio>
#include "ep_client_bridge_adapter.h"

static int g_confirm = 0;
static int g_create = 0;
static int g_remove = 0;
static int g_retain = 0;
static int g_release = 0;
static int g_allocate = 0;
static int g_release_index = 0;
static bool g_reserved[EP_SIDECAR_CAPACITY]{};
static UINT8 g_forced_index = 0xFF;
static bool g_overflow_reserved = false;

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

static EP_BRIDGE_STATUS __cdecl native_allocate(void*, UINT64, UINT64, UINT8* out) {
    ++g_allocate;
    if (g_forced_index != 0xFF) {
        *out = g_forced_index;
        if (g_forced_index < EP_SIDECAR_CAPACITY) {
            if (g_reserved[g_forced_index]) return EP_BRIDGE_INDEX_REJECTED;
            g_reserved[g_forced_index] = true;
        } else {
            g_overflow_reserved = true;
        }
        return EP_BRIDGE_OK;
    }
    for (UINT8 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        if (g_reserved[i]) continue;
        g_reserved[i] = true;
        *out = i;
        return EP_BRIDGE_OK;
    }
    return EP_BRIDGE_INDEX_REJECTED;
}

static EP_BRIDGE_STATUS __cdecl native_release_index(void*, UINT64, UINT64, UINT8 index, UINT32) {
    ++g_release_index;
    if (index >= EP_SIDECAR_CAPACITY) {
        if (!g_overflow_reserved || index != g_forced_index)
            return EP_BRIDGE_INDEX_REJECTED;
        g_overflow_reserved = false;
        return EP_BRIDGE_OK;
    }
    if (!g_reserved[index]) return EP_BRIDGE_INDEX_REJECTED;
    g_reserved[index] = false;
    return EP_BRIDGE_OK;
}

static EP_BRIDGE_STATUS __cdecl native_retain(void*) { ++g_retain; return EP_BRIDGE_OK; }
static void __cdecl native_release(void*) { ++g_release; }

int main() {
    EP_CLIENT_ADAPTER a{};
    if (ep_client_adapter_init(&a, &a, nullptr, nullptr, nullptr, nullptr, nullptr,
                               nullptr, nullptr) !=
        EP_BRIDGE_INVALID_ARGUMENT) return 10;

    EP_CLIENT_ADAPTER b{};
    if (ep_client_adapter_init(&b, &b, native_confirm, native_create, native_remove,
                               native_allocate, native_release_index,
                               native_retain, native_release) != EP_BRIDGE_OK) return 11;
    if (ep_client_adapter_retain(&b) != EP_BRIDGE_OK) return 12;
    UINT8 index = 0xFF;
    if (ep_client_adapter_allocate_index(&b, 100, 900, &index) != EP_BRIDGE_OK || index != 0) return 13;
    if (ep_client_adapter_init(&b, &b, native_confirm, native_create, native_remove,
                               native_allocate, native_release_index,
                               native_retain, native_release) != EP_BRIDGE_ALREADY_READY ||
        b.index_reserved[0] == 0) return 131;
    if (ep_client_adapter_confirm(&b, 100, 900, index) != EP_BRIDGE_OK) return 14;
    if (ep_client_adapter_create(&b, 100, 900, index) != EP_BRIDGE_OK) return 15;
    ep_client_adapter_release(&b);
    if (ep_client_adapter_remove(&b, 100, 900, index) != EP_BRIDGE_OK) return 16;
    if (ep_client_adapter_release_index(&b, 100, 900, index, 1) != EP_BRIDGE_OK) return 17;
    g_forced_index = 8;
    if (ep_client_adapter_allocate_index(&b, 101, 901, &index) != EP_BRIDGE_INDEX_REJECTED ||
        index != 8 || !b.overflow[0].valid) return 171;
    if (ep_client_adapter_release_index(&b, 101, 901, index, 1) != EP_BRIDGE_INDEX_REJECTED ||
        !b.overflow[0].valid) return 172;
    if (ep_client_adapter_release_index(&b, 101, 901, index, 0) != EP_BRIDGE_OK ||
        b.overflow[0].valid) return 173;
    g_forced_index = 0xFF;
    if (ep_client_adapter_allocate_index(&b, 999, 9999, &index) != EP_BRIDGE_OK) return 18;
    if (ep_client_adapter_confirm(&b, 999, 9999, index) != EP_BRIDGE_CALLBACK_REJECTED) return 19;
    if (ep_client_adapter_create(&b, 999, 9999, index) != EP_BRIDGE_CALLBACK_REJECTED) return 20;
    if (ep_client_adapter_destroy(&b) != EP_BRIDGE_CLEANUP_REQUIRED) return 20;
    if (ep_client_adapter_remove(&b, 999, 9999, index) != EP_BRIDGE_OK) return 21;
    if (ep_client_adapter_release_index(&b, 999, 9999, index, 2) != EP_BRIDGE_OK) return 22;
    if (ep_client_adapter_destroy(&b) != EP_BRIDGE_OK) return 23;
    if (g_confirm != 2 || g_create != 1 || g_remove != 2 ||
        g_allocate != 3 || g_release_index != 3 ||
        g_retain != 1 || g_release != 1) return 24;
    std::puts("ep_client_bridge_adapter_synthetic_passed");
    return 0;
}
