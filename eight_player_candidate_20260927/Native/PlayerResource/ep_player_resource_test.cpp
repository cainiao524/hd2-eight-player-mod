#include "ep_player_resource.h"
#include <cstdio>

static bool check(bool ok, const char* label) { if (!ok) std::fprintf(stderr, "failed: %s\n", label); return ok; }

int main() {
    EP_PLAYER_RESOURCE r{}; bool ok = check(ep_resource_init(&r, 0x3000) == EP_RS_OK, "init");
    EP_RESOURCE_TOKEN token{}; ok &= check(ep_resource_begin(&r, 4, 0x44, 0xA004, 0xB004, 0, 239, &token) == EP_RS_OK, "begin index4");
    EP_RESOURCE_RECORD before_reinit{};
    ok &= check(ep_resource_get(&r, 4, &before_reinit) == EP_RS_OK, "capture before reinit");
    ok &= check(ep_resource_init(&r, 0xDEAD) == EP_RS_BUSY, "live reinit rejected");
    EP_RESOURCE_RECORD after_reinit{};
    ok &= check(ep_resource_get(&r, 4, &after_reinit) == EP_RS_OK &&
                    after_reinit.state == before_reinit.state &&
                    after_reinit.generation == before_reinit.generation &&
                    after_reinit.peer_id == before_reinit.peer_id &&
                    after_reinit.resource_handle == before_reinit.resource_handle,
                "live reinit preserves record");
    for (UINT8 stage = 0; stage < 3; ++stage) {
        EP_RESOURCE_LEASE lease{};
        ok &= check(ep_resource_begin_callback(&r, token, &lease) == EP_RS_OK, "begin callback");
        ok &= check(ep_resource_complete_callback(&r, lease, static_cast<EP_RESOURCE_STAGE>(stage), TRUE) == EP_RS_OK, "complete callback");
    }
    ok &= check(ep_resource_publish(&r, token) == EP_RS_OK, "publish");
    ok &= check(ep_resource_release(&r, token) == EP_RS_OK, "release");
    ok &= check(ep_resource_release(&r, token) == EP_RS_ALREADY_RELEASED, "idempotent release");
    ok &= check(ep_resource_quiesce(&r) == EP_RS_OK, "quiesce");
    ok &= check(ep_resource_migrate_owner(&r, 0x4000) == EP_RS_OK, "migrate owner");

    EP_RESOURCE_TOKEN all[EP_RESOURCE_CAPACITY]{};
    for (UINT8 index = 0; index < EP_RESOURCE_CAPACITY; ++index) {
        ok &= check(ep_resource_begin(&r, index, 0x100 + index, 0xA100 + index,
                                      0xB100 + index, index, 239, &all[index]) == EP_RS_OK,
                    "all eight begin");
    }
    EP_RESOURCE_TOKEN rejected_ninth{};
    ok &= check(ep_resource_begin(&r, 0, 0x999, 0xA999, 0xB999, 9, 239, &rejected_ninth) == EP_RS_DUPLICATE,
                "occupied slot rejected");
    for (UINT8 index = 0; index < EP_RESOURCE_CAPACITY; ++index) {
        for (UINT8 stage = 0; stage < 3; ++stage) {
            EP_RESOURCE_LEASE lease{};
            ok &= check(ep_resource_begin_callback(&r, all[index], &lease) == EP_RS_OK, "all eight lease");
            ok &= check(ep_resource_complete_callback(&r, lease, static_cast<EP_RESOURCE_STAGE>(stage), TRUE) == EP_RS_OK,
                        "all eight callback");
        }
        ok &= check(ep_resource_publish(&r, all[index]) == EP_RS_OK, "all eight publish");
        ok &= check(ep_resource_release(&r, all[index]) == EP_RS_OK, "all eight release");
    }
    ok &= check(ep_resource_quiesce(&r) == EP_RS_OK, "all eight quiesce");
    ok &= check(ep_resource_migrate_owner(&r, 0x5000) == EP_RS_OK, "second owner migration");

    EP_RESOURCE_TOKEN order_failed{}; ok &= check(ep_resource_begin(&r, 6, 0x66, 0xA006, 0xB006, 2, 239, &order_failed) == EP_RS_OK, "begin order case");
    EP_RESOURCE_LEASE order_lease{}; ok &= check(ep_resource_begin_callback(&r, order_failed, &order_lease) == EP_RS_OK, "order lease");
    ok &= check(ep_resource_complete_callback(&r, order_lease, EP_RS_STAGE_SECOND, TRUE) == EP_RS_CALLBACK_ORDER, "order rejection");
    ok &= check(ep_resource_release(&r, order_failed) == EP_RS_ALREADY_RELEASED, "order rollback");

    EP_RESOURCE_TOKEN failed{}; ok &= check(ep_resource_begin(&r, 7, 0x77, 0xA007, 0xB007, 1, 239, &failed) == EP_RS_OK, "begin failure case");
    EP_RESOURCE_LEASE l1{}; ok &= check(ep_resource_begin_callback(&r, failed, &l1) == EP_RS_OK, "first lease");
    ok &= check(ep_resource_complete_callback(&r, l1, EP_RS_STAGE_FIRST, TRUE) == EP_RS_OK, "first complete");
    EP_RESOURCE_LEASE l2{}; ok &= check(ep_resource_begin_callback(&r, failed, &l2) == EP_RS_OK, "second lease");
    ok &= check(ep_resource_complete_callback(&r, l2, EP_RS_STAGE_SECOND, TRUE) == EP_RS_OK, "second complete");
    EP_RESOURCE_LEASE l3{}; ok &= check(ep_resource_begin_callback(&r, failed, &l3) == EP_RS_OK, "third lease");
    ok &= check(ep_resource_complete_callback(&r, l3, EP_RS_STAGE_THIRD, FALSE) == EP_RS_OK, "third rollback");
    ok &= check(ep_resource_release(&r, failed) == EP_RS_ALREADY_RELEASED, "failed release idempotence");
    ok &= check(ep_resource_validate(&r) == EP_RS_OK, "validate after rollback");
    ok &= check(ep_resource_quiesce(&r) == EP_RS_OK, "final quiesce");
    ok &= check(ep_resource_destroy(&r) == EP_RS_OK, "destroy");
    ok &= check(ep_resource_init(&r, 0x6000) == EP_RS_OK, "reinit after destroy");
    ok &= check(ep_resource_destroy(&r) == EP_RS_OK, "destroy reinitialized table");
    if (!ok) return 1;
    std::puts("ep_player_resource_synthetic_passed"); return 0;
}
