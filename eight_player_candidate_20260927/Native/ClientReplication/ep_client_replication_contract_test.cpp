#include <windows.h>
#include <cstdio>

#include "ep_client_replication_contract.h"

struct TestContext {
    EP_CR_EVENT fail_event = static_cast<EP_CR_EVENT>(0);
    bool fail_once = false;
    bool fail_rollback = false;
    UINT32 slot_events = 0;
    UINT32 owner_events = 0;
    UINT32 bad_masks = 0;
};

static EP_CR_STATUS __cdecl slot_callback(void* raw, EP_CR_EVENT event,
                                          const EP_CR_SLOT* slot,
                                          UINT32 mask) {
    auto* ctx = static_cast<TestContext*>(raw);
    ++ctx->slot_events;
    if (mask == 0 || (mask & ~EP_CR_ARRAY_ALL) != 0) ++ctx->bad_masks;
    if (event != EP_CR_EVENT_RESET && (!slot || slot->state == EP_CR_FREE))
        return EP_CR_CALLBACK_REJECTED;
    if (ctx->fail_rollback && event == EP_CR_EVENT_ROLLBACK) return EP_CR_CALLBACK_REJECTED;
    if (ctx->fail_once && event == ctx->fail_event) {
        ctx->fail_once = false;
        return EP_CR_CALLBACK_REJECTED;
    }
    return EP_CR_OK;
}

static EP_CR_STATUS __cdecl owner_callback(void* raw, EP_CR_EVENT, UINT64 owner,
                                           UINT32 epoch) {
    auto* ctx = static_cast<TestContext*>(raw);
    ++ctx->owner_events;
    return owner != 0 && epoch != 0 ? EP_CR_OK : EP_CR_CALLBACK_REJECTED;
}

int main() {
    HMODULE dll = LoadLibraryW(L"ep_client_replication_contract.dll");
    if (!dll) return 10;
    using Init = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*, UINT32,
                                        const EP_CR_CALLBACKS*, UINT64, UINT32);
    using Destroy = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*);
    using Append = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*, UINT8, UINT64, UINT64, UINT32, EP_CR_TOKEN*);
    using Confirm = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*, EP_CR_TOKEN);
    using Remove = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*, EP_CR_TOKEN);
    using Kick = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*, EP_CR_TOKEN);
    using Retry = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*, EP_CR_TOKEN);
    using Reset = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*);
    using Enter = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*, EP_CR_TOKEN, UINT32*);
    using Leave = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*, EP_CR_TOKEN, UINT32);
    using MigBegin = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*, UINT64, UINT32, UINT32);
    using MigCommit = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*, UINT32);
    using MigAbort = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*, UINT32);
    using Get = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*, UINT8, EP_CR_SLOT*);
    using Validate = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*);
    auto init = reinterpret_cast<Init>(GetProcAddress(dll, "ep_cr_init"));
    auto destroy = reinterpret_cast<Destroy>(GetProcAddress(dll, "ep_cr_destroy"));
    auto append = reinterpret_cast<Append>(GetProcAddress(dll, "ep_cr_append"));
    auto confirm = reinterpret_cast<Confirm>(GetProcAddress(dll, "ep_cr_confirm"));
    auto remove = reinterpret_cast<Remove>(GetProcAddress(dll, "ep_cr_remove"));
    auto kick = reinterpret_cast<Kick>(GetProcAddress(dll, "ep_cr_kick"));
    auto retry = reinterpret_cast<Retry>(GetProcAddress(dll, "ep_cr_retry_rollback"));
    auto reset = reinterpret_cast<Reset>(GetProcAddress(dll, "ep_cr_reset"));
    auto enter = reinterpret_cast<Enter>(GetProcAddress(dll, "ep_cr_callback_enter"));
    auto leave = reinterpret_cast<Leave>(GetProcAddress(dll, "ep_cr_callback_leave"));
    auto migration_begin = reinterpret_cast<MigBegin>(GetProcAddress(dll, "ep_cr_migration_begin"));
    auto migration_commit = reinterpret_cast<MigCommit>(GetProcAddress(dll, "ep_cr_migration_commit"));
    auto migration_abort = reinterpret_cast<MigAbort>(GetProcAddress(dll, "ep_cr_migration_abort"));
    auto get = reinterpret_cast<Get>(GetProcAddress(dll, "ep_cr_get"));
    auto validate = reinterpret_cast<Validate>(GetProcAddress(dll, "ep_cr_validate"));
    if (!init || !destroy || !append || !confirm || !remove || !kick || !retry ||
        !reset || !enter || !leave || !migration_begin || !migration_commit ||
        !migration_abort || !get || !validate) return 11;

    TestContext ctx{};
    EP_CR_CALLBACKS callbacks{sizeof(EP_CR_CALLBACKS), EP_CR_VERSION, &ctx,
                              slot_callback, owner_callback};
    EP_CLIENT_REPLICATION_SIDECAR sidecar{};
    if (init(&sidecar, EP_CR_BUILD, &callbacks, 0x100, 1) != EP_CR_OK) return 12;
    if (validate(&sidecar) != EP_CR_OK) return 13;

    // Stable network indices and all five array groups are exercised without
    // compacting a removed slot.
    EP_CR_TOKEN tokens[EP_CR_CAPACITY]{};
    for (UINT8 i = 0; i < EP_CR_CAPACITY; ++i) {
        if (append(&sidecar, i, 1000 + i, 9000 + i, EP_CR_ARRAY_ALL, &tokens[i]) != EP_CR_OK ||
            tokens[i].network_index != i || tokens[i].generation != 1 ||
            confirm(&sidecar, tokens[i]) != EP_CR_OK) return 14;
    }
    if (validate(&sidecar) != EP_CR_OK) return 15;
    UINT32 lease = 0;
    if (enter(&sidecar, tokens[4], &lease) != EP_CR_OK ||
        remove(&sidecar, tokens[4]) != EP_CR_QUIESCENCE_REQUIRED ||
        leave(&sidecar, tokens[4], lease) != EP_CR_OK ||
        remove(&sidecar, tokens[4]) != EP_CR_OK) return 16;

    EP_CR_SLOT slot{};
    if (get(&sidecar, 5, &slot) != EP_CR_OK || slot.peer_id != 1005) return 17;
    EP_CR_TOKEN hole{};
    if (append(&sidecar, 4, 2004, 12004, EP_CR_ARRAY_ALL, &hole) != EP_CR_OK ||
        hole.generation != 2 || confirm(&sidecar, hole) != EP_CR_OK ||
        remove(&sidecar, tokens[4]) != EP_CR_STALE_GENERATION) return 18;

    // A failed confirm is compensated.  A failed compensation remains in a
    // rollback state and can be retried using the same generation token.
    EP_CR_TOKEN failed{};
    if (append(&sidecar, 2, 3002, 13002, EP_CR_ARRAY_ALL, &failed) != EP_CR_INDEX_OCCUPIED) return 19;
    if (remove(&sidecar, tokens[2]) != EP_CR_OK ||
        append(&sidecar, 2, 3002, 13002, EP_CR_ARRAY_ALL, &failed) != EP_CR_OK) return 20;
    ctx.fail_event = EP_CR_EVENT_CONFIRM;
    ctx.fail_once = true;
    if (confirm(&sidecar, failed) != EP_CR_CALLBACK_REJECTED ||
        get(&sidecar, 2, &slot) != EP_CR_NOT_FOUND) return 21;
    if (remove(&sidecar, tokens[3]) != EP_CR_OK) return 22;
    ctx.fail_event = EP_CR_EVENT_APPEND;
    ctx.fail_once = true;
    ctx.fail_rollback = true;
    if (append(&sidecar, 3, 3004, 13004, EP_CR_ARRAY_ALL, &failed) != EP_CR_ROLLBACK_REQUIRED) return 23;
    // The failed append token is returned and can be unwound after callback
    // behavior is repaired.
    ctx.fail_rollback = false;
    if (retry(&sidecar, failed) != EP_CR_OK) return 24;

    // Host migration requires quiescence and preserves every stable index.
    EP_CR_TOKEN invalid{};
    if (append(&sidecar, EP_CR_CAPACITY, 1, 1, EP_CR_ARRAY_ALL, &invalid) != EP_CR_INDEX_REJECTED ||
        append(&sidecar, 2, 1000, 17, EP_CR_ARRAY_ALL, &invalid) != EP_CR_DUPLICATE_PEER) return 28;
    if (migration_begin(&sidecar, 0x200, 2, 7) != EP_CR_OK ||
        append(&sidecar, 2, 51, 52, EP_CR_ARRAY_ALL, &invalid) != EP_CR_MIGRATION_IN_PROGRESS ||
        remove(&sidecar, tokens[0]) != EP_CR_MIGRATION_IN_PROGRESS ||
        migration_commit(&sidecar, 7) != EP_CR_OK ||
        migration_abort(&sidecar, 7) != EP_CR_MIGRATION_NOT_PREPARED) return 25;
    if (append(&sidecar, 2, 51, 52, EP_CR_ARRAY_CONFIRMED_32, &invalid) != EP_CR_OK ||
        confirm(&sidecar, invalid) != EP_CR_OK) return 29;
    UINT8 view[EP_CR_CAPACITY]{};
    UINT32 count = 0;
    using Array = EP_CR_STATUS(__cdecl*)(EP_CLIENT_REPLICATION_SIDECAR*, UINT32, UINT8*, UINT32*);
    auto get_array = reinterpret_cast<Array>(GetProcAddress(dll, "ep_cr_get_array"));
    using Enabled = UINT32(__cdecl*)();
    auto production_enabled = reinterpret_cast<Enabled>(GetProcAddress(dll, "ep_cr_production_enabled"));
    if (!get_array || !production_enabled || get_array(&sidecar, 4, view, &count) != EP_CR_OK || count != EP_CR_CAPACITY - 2 ||
        view[0] != 0 || view[1] != 1 || view[2] != 5 || view[3] != 6 ||
        view[4] != 7 || view[12] != 15 || view[13] != 4 || view[14] != EP_CR_CAPACITY) return 30;
    if (get_array(&sidecar, 3, view, &count) != EP_CR_OK || count != EP_CR_CAPACITY - 1 || view[14] != 2) return 31;
    if (kick(&sidecar, invalid) != EP_CR_OK || production_enabled() != 0) return 32;
    if (reset(&sidecar) != EP_CR_OK || validate(&sidecar) != EP_CR_OK ||
        ctx.bad_masks != 0 || ctx.slot_events == 0 || ctx.owner_events < 2) return 26;
    if (destroy(&sidecar) != EP_CR_OK || validate(&sidecar) != EP_CR_INVALID_CONTEXT) return 27;
    FreeLibrary(dll);
    std::puts("ep_client_replication_contract_synthetic_passed");
    return 0;
}
