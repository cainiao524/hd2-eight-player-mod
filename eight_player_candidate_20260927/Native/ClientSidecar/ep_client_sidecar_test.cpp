#include <windows.h>
#include <cstdio>
#include "ep_client_sidecar.h"

int main() {
    HMODULE dll = LoadLibraryW(L"ep_client_sidecar.dll");
    if (!dll) return 10;
    using Init = EP_CLIENT_STATUS(__cdecl*)(EP_CLIENT_SIDECAR*, UINT32);
    using Destroy = EP_CLIENT_STATUS(__cdecl*)(EP_CLIENT_SIDECAR*);
    using Append = EP_CLIENT_STATUS(__cdecl*)(EP_CLIENT_SIDECAR*, UINT64, UINT64, UINT32, UINT32*);
    using Remove = EP_CLIENT_STATUS(__cdecl*)(EP_CLIENT_SIDECAR*, UINT32, UINT32);
    using Get = EP_CLIENT_STATUS(__cdecl*)(EP_CLIENT_SIDECAR*, UINT32, EP_CLIENT_RECORD*);
    using Reset = EP_CLIENT_STATUS(__cdecl*)(EP_CLIENT_SIDECAR*);
    using Gate = EP_CLIENT_STATUS(__cdecl*)(EP_CLIENT_SIDECAR*, UINT32);
    using Validate = EP_CLIENT_STATUS(__cdecl*)(EP_CLIENT_SIDECAR*);
    auto init = reinterpret_cast<Init>(GetProcAddress(dll, "ep_client_init"));
    auto destroy = reinterpret_cast<Destroy>(GetProcAddress(dll, "ep_client_destroy"));
    auto append = reinterpret_cast<Append>(GetProcAddress(dll, "ep_client_append"));
    auto remove = reinterpret_cast<Remove>(GetProcAddress(dll, "ep_client_remove"));
    auto get = reinterpret_cast<Get>(GetProcAddress(dll, "ep_client_get"));
    auto reset = reinterpret_cast<Reset>(GetProcAddress(dll, "ep_client_reset"));
    auto gate = reinterpret_cast<Gate>(GetProcAddress(dll, "ep_client_creation_gate"));
    auto validate = reinterpret_cast<Validate>(GetProcAddress(dll, "ep_client_validate"));
    if (!init || !destroy || !append || !remove || !get || !reset || !gate || !validate) return 11;

    EP_CLIENT_SIDECAR s{};
    if (init(&s, EP_CLIENT_SIDECAR_BUILD) != EP_CLIENT_OK) return 12;
    UINT32 generation[8]{};
    for (UINT32 i = 0; i < 8; ++i) {
        if (gate(&s, i) != (i >= 4 ? EP_CLIENT_CREATION_REQUIRED : EP_CLIENT_OK)) return 13;
        if (append(&s, 1000 + i, 9000 + i, i, &generation[i]) != EP_CLIENT_OK || generation[i] != 1) return 14;
    }
    if (validate(&s) != EP_CLIENT_OK) return 15;
    UINT32 out = 0;
    if (append(&s, 2000, 10000, 8, &out) != EP_CLIENT_INDEX_REJECTED) return 16;
    if (append(&s, 1000, 10001, 4, &out) != EP_CLIENT_DUPLICATE_PEER) return 17;
    if (remove(&s, 3, generation[3]) != EP_CLIENT_OK) return 18;
    EP_CLIENT_RECORD record{};
    if (get(&s, 3, &record) != EP_CLIENT_NOT_FOUND || get(&s, 4, &record) != EP_CLIENT_OK || record.network_index != 4) return 19;
    if (append(&s, 3000, 12000, 3, &out) != EP_CLIENT_OK || out != 2) return 20;
    if (remove(&s, 3, generation[3]) != EP_CLIENT_STALE_GENERATION) return 21;
    if (validate(&s) != EP_CLIENT_OK) return 22;
    if (reset(&s) != EP_CLIENT_OK || validate(&s) != EP_CLIENT_OK) return 23;
    if (destroy(&s) != EP_CLIENT_OK) return 24;
    FreeLibrary(dll);
    std::puts("ep_client_sidecar_synthetic_passed");
    return 0;
}
