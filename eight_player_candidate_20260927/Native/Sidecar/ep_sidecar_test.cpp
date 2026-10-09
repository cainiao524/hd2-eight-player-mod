#include <windows.h>
#include <cstdio>
#include <cstring>

#include "ep_sidecar.h"

using InitFn = EP_SIDECAR_STATUS(__cdecl*)(EP_SIDECAR*);
using InitCapacityFn = EP_SIDECAR_STATUS(__cdecl*)(EP_SIDECAR*, UINT32);
using DestroyFn = EP_SIDECAR_STATUS(__cdecl*)(EP_SIDECAR*);
using ReserveFn = EP_SIDECAR_STATUS(__cdecl*)(EP_SIDECAR*, UINT64, UINT64, EP_SIDECAR_TOKEN*);
using ReserveAtFn = EP_SIDECAR_STATUS(__cdecl*)(EP_SIDECAR*, UINT8, UINT64, UINT64, EP_SIDECAR_TOKEN*);
using ConfirmFn = EP_SIDECAR_STATUS(__cdecl*)(EP_SIDECAR*, EP_SIDECAR_TOKEN);
using RemoveFn = EP_SIDECAR_STATUS(__cdecl*)(EP_SIDECAR*, EP_SIDECAR_TOKEN);
using ReconnectFn = EP_SIDECAR_STATUS(__cdecl*)(EP_SIDECAR*, UINT64, UINT64, EP_SIDECAR_TOKEN*);
using GetSlotFn = EP_SIDECAR_STATUS(__cdecl*)(EP_SIDECAR*, UINT8, EP_SIDECAR_SLOT*);
using ValidateFn = EP_SIDECAR_STATUS(__cdecl*)(EP_SIDECAR*);
using CapacityFn = UINT32(__cdecl*)();

static bool same_token(const EP_SIDECAR_TOKEN& a, const EP_SIDECAR_TOKEN& b) {
    return a.index == b.index && a.generation == b.generation;
}

int main() {
    HMODULE dll = LoadLibraryW(L"ep_sidecar.dll");
    if (!dll) return 10;
    auto init = reinterpret_cast<InitFn>(GetProcAddress(dll, "ep_sidecar_init"));
    auto init_capacity = reinterpret_cast<InitCapacityFn>(GetProcAddress(dll, "ep_sidecar_init_capacity"));
    auto destroy = reinterpret_cast<DestroyFn>(GetProcAddress(dll, "ep_sidecar_destroy"));
    auto reserve = reinterpret_cast<ReserveFn>(GetProcAddress(dll, "ep_sidecar_reserve"));
    auto reserve_at = reinterpret_cast<ReserveAtFn>(GetProcAddress(dll, "ep_sidecar_reserve_at"));
    auto confirm = reinterpret_cast<ConfirmFn>(GetProcAddress(dll, "ep_sidecar_confirm"));
    auto remove = reinterpret_cast<RemoveFn>(GetProcAddress(dll, "ep_sidecar_remove"));
    auto reconnect = reinterpret_cast<ReconnectFn>(GetProcAddress(dll, "ep_sidecar_reconnect"));
    auto get_slot = reinterpret_cast<GetSlotFn>(GetProcAddress(dll, "ep_sidecar_get_slot"));
    auto validate = reinterpret_cast<ValidateFn>(GetProcAddress(dll, "ep_sidecar_validate"));
    auto capacity = reinterpret_cast<CapacityFn>(GetProcAddress(dll, "ep_sidecar_capacity"));
    if (!init || !init_capacity || !destroy || !reserve || !reserve_at || !confirm || !remove || !reconnect ||
        !get_slot || !validate || !capacity) return 11;

    EP_SIDECAR sidecar{};
    if (capacity() != EP_SIDECAR_CAPACITY || capacity() != 16 ||
        init(&sidecar) != EP_SC_OK || validate(&sidecar) != EP_SC_OK) return 12;

    // The authoritative Session/Party allocator may return a hole or a
    // non-dense ordinal.  The bridge must reserve that exact index and never
    // silently substitute another free slot.
    EP_SIDECAR exact{};
    EP_SIDECAR_TOKEN exact_token{};
    EP_SIDECAR_TOKEN exact_out{};
    if (init(&exact) != EP_SC_OK ||
        reserve_at(&exact, 5, 55, 505, &exact_token) != EP_SC_OK ||
        exact_token.index != 5 || exact_token.generation != 1 ||
        reserve_at(&exact, 5, 56, 506, &exact_out) != EP_SC_INDEX_OCCUPIED ||
        reserve_at(&exact, 4, 55, 507, &exact_out) != EP_SC_DUPLICATE_IDENTITY ||
        remove(&exact, exact_token) != EP_SC_OK ||
        reserve_at(&exact, 5, 56, 506, &exact_out) != EP_SC_OK ||
        exact_out.index != 5 || exact_out.generation != 2 ||
        remove(&exact, exact_token) != EP_SC_STALE_TOKEN ||
        remove(&exact, exact_out) != EP_SC_OK ||
        destroy(&exact) != EP_SC_OK) return 35;

    EP_SIDECAR_TOKEN tokens[EP_SIDECAR_CAPACITY]{};
    for (UINT8 i = 0; i < EP_SIDECAR_CAPACITY; ++i) {
        if (reserve(&sidecar, 1000 + i, 9000 + i, &tokens[i]) != EP_SC_OK ||
            tokens[i].index != i || tokens[i].generation != 1) return 13;
        if (confirm(&sidecar, tokens[i]) != EP_SC_OK) return 14;
    }
    if (validate(&sidecar) != EP_SC_OK) return 15;
    EP_SIDECAR_TOKEN out{};
    if (reserve(&sidecar, 2000, 10000, &out) != EP_SC_FULL) return 16;
    if (reserve(&sidecar, 1000, 11000, &out) != EP_SC_DUPLICATE_IDENTITY) return 17;
    if (reserve(&sidecar, 2000, 9000, &out) != EP_SC_DUPLICATE_RESOURCE) return 18;

    // Remove index 2 without compacting the remaining seven slots.
    EP_SIDECAR_SLOT slot{};
    if (remove(&sidecar, tokens[2]) != EP_SC_OK ||
        get_slot(&sidecar, 2, &slot) != EP_SC_OK || slot.state != EP_SC_SLOT_FREE ||
        slot.generation != 1 || slot.peer_id != 0 || slot.resource_handle != 0) return 19;
    if (get_slot(&sidecar, 3, &slot) != EP_SC_OK || slot.peer_id != 1003) return 20;

    // A new identity fills the hole and advances the generation.  The old
    // token can never remove the replacement.
    EP_SIDECAR_TOKEN replacement{};
    if (reserve(&sidecar, 3000, 12000, &replacement) != EP_SC_OK ||
        replacement.index != 2 || replacement.generation != 2 ||
        remove(&sidecar, tokens[2]) != EP_SC_STALE_TOKEN) return 21;
    if (confirm(&sidecar, replacement) != EP_SC_OK) return 22;
    if (reconnect(&sidecar, 3000, 12000, &out) != EP_SC_OK ||
        !same_token(out, replacement) || confirm(&sidecar, replacement) != EP_SC_ALREADY_CONFIRMED) return 23;

    // Departure and reconnect allocate a fresh generation while retaining the
    // same ordinal if the hole is still available.
    if (remove(&sidecar, replacement) != EP_SC_OK ||
        reconnect(&sidecar, 3000, 12000, &out) != EP_SC_OK ||
        out.index != 2 || out.generation != 3 || remove(&sidecar, replacement) != EP_SC_STALE_TOKEN) return 24;
    if (validate(&sidecar) != EP_SC_OK) return 25;
    if (remove(&sidecar, out) != EP_SC_OK) return 34;

    // Pending entries are visible but not counted as confirmed.  Conflicting
    // peer and resource identities fail independently.
    if (reserve(&sidecar, 4000, 13000, &out) != EP_SC_OK ||
        reserve(&sidecar, 4000, 13001, &replacement) != EP_SC_DUPLICATE_IDENTITY ||
        reserve(&sidecar, 4001, 13000, &replacement) != EP_SC_DUPLICATE_RESOURCE) return 26;
    if (remove(&sidecar, out) != EP_SC_OK) return 27;

    // A stale or out-of-range token cannot mutate a live slot.
    EP_SIDECAR_TOKEN bad{EP_SIDECAR_CAPACITY, {0, 0, 0}, 1};
    if (confirm(&sidecar, bad) != EP_SC_INVALID_TOKEN) return 28;
    bad = tokens[0];
    bad.generation = 2;
    if (remove(&sidecar, bad) != EP_SC_STALE_TOKEN) return 29;

    // A slot whose generation is exhausted is never reused.  With every
    // other slot active, the result is an explicit fail-closed status.
    EP_SIDECAR_TOKEN filler{};
    if (reserve(&sidecar, 5001, 14001, &filler) != EP_SC_OK ||
        filler.index != 2 || confirm(&sidecar, filler) != EP_SC_OK ||
        remove(&sidecar, tokens[0]) != EP_SC_OK) return 30;
    sidecar.slots[0].generation = 0xFFFFFFFFu;
    if (reserve(&sidecar, 5000, 14000, &out) != EP_SC_GENERATION_EXHAUSTED) return 31;
    if (validate(&sidecar) != EP_SC_OK) return 32;

    if (destroy(&sidecar) != EP_SC_OK ||
        validate(&sidecar) != EP_SC_INVALID_CONTEXT ||
        reserve(&sidecar, 6000, 15000, &out) != EP_SC_INVALID_CONTEXT) return 33;

    // The storage ABI is larger than an active contract.  A bounded table
    // rejects the first index outside its active capacity without compacting
    // or consuming a later slot.
    EP_SIDECAR bounded{};
    EP_SIDECAR_TOKEN bounded_token{};
    if (init_capacity(&bounded, 8) != EP_SC_OK ||
        reserve_at(&bounded, 7, 7000, 17000, &bounded_token) != EP_SC_OK ||
        reserve_at(&bounded, 8, 7001, 17001, &out) != EP_SC_INVALID_TOKEN ||
        remove(&bounded, bounded_token) != EP_SC_OK ||
        destroy(&bounded) != EP_SC_OK) return 36;
    FreeLibrary(dll);
    std::puts("ep_sidecar_synthetic_passed");
    return 0;
}
