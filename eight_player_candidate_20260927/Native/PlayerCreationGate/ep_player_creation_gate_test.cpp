#include "ep_player_creation_gate.h"

#include <cstdio>
#include <cstring>
#include <vector>

struct Context {
    std::vector<BYTE>* image{};
    bool ready{false};
    bool fail_retain{false};
    bool fail_components{false};
    bool fail_roster{false};
    bool fail_rollback{false};
    bool fail_cleanup_roster_once{false};
    unsigned retain{0};
    unsigned release{0};
    unsigned resolve{0};
    unsigned components{0};
    unsigned roster{0};
    unsigned cleanup_roster{0};
    unsigned cleanup_components{0};
    unsigned rollback{0};
    unsigned quiesce{0};
    unsigned resume{0};
    unsigned writes{0};
};

static bool check(bool value, const char* label) {
    if (!value) std::fprintf(stderr, "failed: %s\n", label);
    return value;
}

static EP_PC_STATUS __cdecl retain(void* owner) {
    auto* c = static_cast<Context*>(owner); ++c->retain;
    return c->fail_retain ? EP_PC_CALLBACK_REJECTED : EP_PC_OK;
}
static void __cdecl release_owner(void* owner) { ++static_cast<Context*>(owner)->release; }
static EP_PC_STATUS __cdecl resolve(void* owner, UINT64 peer, UINT64 handle,
                                    UINT64 hash, UINT8 index, UINT32 generation,
                                    EP_PC_RESOURCE* out) {
    auto* c = static_cast<Context*>(owner); ++c->resolve;
    if (!out) return EP_PC_INVALID_ARGUMENT;
    out->network_index = index; out->generation = generation;
    out->peer_id = peer; out->resource_handle = handle; out->resource_hash = hash;
    out->opaque = reinterpret_cast<UINT64>(c);
    return EP_PC_OK;
}
static EP_PC_STATUS __cdecl components(void* owner, const EP_PC_RESOURCE*) {
    auto* c = static_cast<Context*>(owner); ++c->components;
    return c->fail_components ? EP_PC_CALLBACK_REJECTED : EP_PC_OK;
}
static EP_PC_STATUS __cdecl roster(void* owner, const EP_PC_RESOURCE*) {
    auto* c = static_cast<Context*>(owner); ++c->roster;
    return c->fail_roster ? EP_PC_CALLBACK_REJECTED : EP_PC_OK;
}
static EP_PC_STATUS __cdecl cleanup_roster(void* owner, const EP_PC_RESOURCE*) {
    auto* c = static_cast<Context*>(owner); ++c->cleanup_roster;
    if (c->fail_cleanup_roster_once) { c->fail_cleanup_roster_once = false; return EP_PC_CALLBACK_REJECTED; }
    return EP_PC_OK;
}
static EP_PC_STATUS __cdecl cleanup_components(void* owner, const EP_PC_RESOURCE*) {
    ++static_cast<Context*>(owner)->cleanup_components; return EP_PC_OK;
}
static EP_PC_STATUS __cdecl rollback(void* owner, const EP_PC_RESOURCE*, UINT32) {
    auto* c = static_cast<Context*>(owner); ++c->rollback;
    return c->fail_rollback ? EP_PC_CALLBACK_REJECTED : EP_PC_OK;
}
static EP_PC_STATUS __cdecl quiesce(void* owner) { ++static_cast<Context*>(owner)->quiesce; return EP_PC_OK; }
static void __cdecl resume(void* owner) { ++static_cast<Context*>(owner)->resume; }
static EP_PC_STATUS __cdecl write_bytes(void* owner, uintptr_t address, const BYTE* bytes, SIZE_T size) {
    auto* c = static_cast<Context*>(owner); ++c->writes;
    if (!c->image || !bytes || size == 0) return EP_PC_INVALID_ARGUMENT;
    auto begin = reinterpret_cast<uintptr_t>(c->image->data());
    auto end = begin + c->image->size();
    if (address < begin || size > end - address) return EP_PC_WRITE_FAILED;
    std::memcpy(reinterpret_cast<void*>(address), bytes, size);
    return EP_PC_OK;
}
static EP_PC_STATUS __cdecl downstream_ready(void* owner) {
    return static_cast<Context*>(owner)->ready ? EP_PC_OK : EP_PC_DOWNSTREAM_UNREADY;
}

int main() {
    bool ok = true;
    constexpr SIZE_T image_size = 0x1200000;
    std::vector<BYTE> image(image_size, 0);
    const BYTE gate_expected[] = {0x42,0x83,0xbc,0x02,0xac,0x63,0x01,0x00,0x04};
    const BYTE resource_expected[] = {0xde,0xad,0xbe,0xef};
    const BYTE roster_expected[] = {0x11,0x22,0x33,0x44};
    std::memcpy(image.data() + EP_PC_GATE_RVA, gate_expected, sizeof(gate_expected));
    std::memcpy(image.data() + EP_PC_RESOURCE_RVA, resource_expected, sizeof(resource_expected));
    std::memcpy(image.data() + EP_PC_ROSTER_RVA, roster_expected, sizeof(roster_expected));
    const EP_PC_SITE gate{EP_PC_GATE_RVA, gate_expected, sizeof(gate_expected)};
    const EP_PC_SITE downstream[] = {
        {EP_PC_RESOURCE_RVA, resource_expected, sizeof(resource_expected)},
        {EP_PC_ROSTER_RVA, roster_expected, sizeof(roster_expected)},
    };
    Context context{&image};
    EP_PC_CALLBACKS callbacks{&context, retain, release_owner, resolve, components,
                              roster, cleanup_roster, cleanup_components, rollback};
    EP_PC_PATCH_BACKEND backend{&context, quiesce, resume, write_bytes, downstream_ready};
    EP_PLAYER_CREATION_ADAPTER adapter{};

    EP_PC_PREFLIGHT report{};
    ok &= check(ep_pc_preflight(EP_PC_BUILD, image.data(), image.size(), &gate,
                                downstream, 2, &callbacks, &backend, &report) == EP_PC_OK,
                "preflight fixed build");
    ok &= check(report.ready && report.gate_ok && report.downstream_sites_ok, "preflight flags");
    ok &= check(ep_pc_init(&adapter, EP_PC_BUILD, &callbacks) == EP_PC_OK, "init");
    ok &= check(ep_pc_prepare_patch(&adapter, EP_PC_BUILD, image.data(), image.size(),
                                    &gate, downstream, 2, &backend, &report) == EP_PC_OK,
                "prepare patch");
    ok &= check(ep_pc_install_gate_patch(&adapter) == EP_PC_DOWNSTREAM_UNREADY,
                "route readiness required");
    context.ready = true;
    ok &= check(ep_pc_install_gate_patch(&adapter) == EP_PC_OK, "install gate");
    ok &= check(image[EP_PC_GATE_RVA + 8] == 8, "gate changed only after ready");
    ok &= check(ep_pc_remove_gate_patch(&adapter) == EP_PC_OK, "remove gate");
    ok &= check(std::memcmp(image.data() + EP_PC_GATE_RVA, gate_expected, sizeof(gate_expected)) == 0,
                "gate restored");

    EP_PC_TOKEN tokens[EP_PC_CAPACITY]{};
    for (UINT8 index = 0; index < EP_PC_CAPACITY; ++index) {
        ok &= check(ep_pc_admit(&adapter, index, 0x100 + index, 0x200 + index,
                                0x300 + index, &tokens[index]) == EP_PC_OK, "eight admit");
    }
    EP_PC_TOKEN rejected{};
    ok &= check(ep_pc_admit(&adapter, 8, 0x999, 0x999, 0x999, &rejected) == EP_PC_INDEX_REJECTED,
                "index eight rejected");
    ok &= check(ep_pc_admit(&adapter, 0, 0x100, 0x900, 0x901, &rejected) == EP_PC_DUPLICATE,
                "duplicate peer rejected");
    ok &= check(ep_pc_validate(&adapter) == EP_PC_OK, "active validate");

    context.fail_cleanup_roster_once = true;
    ok &= check(ep_pc_depart(&adapter, tokens[0]) == EP_PC_CALLBACK_REJECTED, "cleanup retry required");
    ok &= check(ep_pc_depart(&adapter, tokens[0]) == EP_PC_OK, "cleanup retry");
    for (UINT8 index = 1; index < EP_PC_CAPACITY; ++index)
        ok &= check(ep_pc_depart(&adapter, tokens[index]) == EP_PC_OK, "eight depart");
    ok &= check(context.release == EP_PC_CAPACITY, "owner lease balanced");

    context.fail_roster = true;
    EP_PC_TOKEN failed{};
    ok &= check(ep_pc_admit(&adapter, 4, 0x444, 0x544, 0x644, &failed) == EP_PC_CALLBACK_REJECTED,
                "roster failure rollback");
    EP_PC_SLOT free_slot{};
    ok &= check(ep_pc_get(&adapter, 4, &free_slot) == EP_PC_OK && free_slot.state == EP_PC_FREE,
                "rollback freed slot");
    context.fail_roster = false;
    ok &= check(ep_pc_validate(&adapter) == EP_PC_OK, "final validate");
    ok &= check(ep_pc_destroy(&adapter) == EP_PC_OK, "destroy");
    if (!ok) return 1;
    std::puts("ep_player_creation_gate_synthetic_passed");
    return 0;
}
