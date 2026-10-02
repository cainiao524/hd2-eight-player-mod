import pytest

from resource_rollback_quiescence_contract_20261003 import (
    BUILD,
    CallbackStage,
    ResourceRollbackContract,
    ResourceToken,
    TransactionState,
    synthetic_report,
)


def _complete_all(model, token):
    for stage in CallbackStage:
        lease = model.begin_callback(token)
        model.complete_callback(lease, stage)
    model.publish(token)


def test_partial_callback_failure_rolls_back_reverse_and_is_idempotent():
    model = ResourceRollbackContract(0x1000)
    token = model.begin(4, record_ordinal=0, resource_handle=11, resource_hash=22, component_ordinal=239)
    lease = model.begin_callback(token)
    model.complete_callback(lease, CallbackStage.FIRST)
    lease = model.begin_callback(token)
    receipt = model.complete_callback(lease, CallbackStage.SECOND, succeeded=False, reason="reject")
    assert receipt["unwound_callbacks"] == ["first_callback"]
    assert receipt["cleanup_actions"] == [
        "undo:first_callback", "remove_roster_record", "remove_owner8_reverse_map",
        "release_resource_handle", "clear_resource_record",
    ]
    assert model.get(4) is None
    repeat = model.rollback(token)
    assert repeat["idempotent"] is True
    assert repeat["cleanup_actions"] == receipt["cleanup_actions"]


def test_third_callback_failure_unwinds_first_and_second_tables():
    model = ResourceRollbackContract(0x1000)
    token = model.begin(4, record_ordinal=0, resource_handle=11, resource_hash=22, component_ordinal=239)
    for stage in (CallbackStage.FIRST, CallbackStage.SECOND):
        lease = model.begin_callback(token)
        model.complete_callback(lease, stage)
    lease = model.begin_callback(token)
    receipt = model.complete_callback(lease, CallbackStage.THIRD, succeeded=False, reason="reject")
    assert receipt["unwound_callbacks"] == ["second_callback", "first_callback"]
    assert receipt["all_side_effects_cleared"] is True


def test_reentry_stale_generation_cannot_touch_replacement():
    model = ResourceRollbackContract(0x1000)
    old = model.begin(6, record_ordinal=0, resource_handle=61, resource_hash=62)
    model.rollback(old)
    new = model.begin(6, record_ordinal=1, resource_handle=63, resource_hash=64)
    assert new.generation == old.generation + 1
    with pytest.raises(ValueError, match="stale"):
        model.begin_callback(old)
    repeated = model.rollback(old, "late callback")
    assert repeated["idempotent"] is True
    assert model.get(6).generation == new.generation


def test_owner_migration_requires_thread_quiescence_and_empty_registry():
    model = ResourceRollbackContract(0x1000)
    token = model.begin(4, record_ordinal=0, resource_handle=41, resource_hash=42)
    lease = model.begin_callback(token)
    with pytest.raises(RuntimeError, match="callbacks are in flight"):
        model.quiesce()
    with pytest.raises(RuntimeError, match="quiescence"):
        model.migrate_owner(0x2000)
    model.complete_callback(lease, CallbackStage.FIRST, succeeded=False)
    with pytest.raises(RuntimeError, match="quiescence"):
        model.migrate_owner(0x2000)
    model.quiesce()
    migration = model.migrate_owner(0x2000)
    assert migration["new"]["owner_epoch"] == 2
    assert model.owner_key == 0x2000
    assert model.owner_epoch == 2


def test_owner_migration_blocks_active_confirmed_record():
    model = ResourceRollbackContract(0x1000)
    token = model.begin(0, record_ordinal=0, resource_handle=101, resource_hash=102)
    _complete_all(model, token)
    with pytest.raises(RuntimeError, match="resource records are active"):
        model.quiesce()
    with pytest.raises(RuntimeError, match="quiescence"):
        model.migrate_owner(0x2000)
    model.release(token)
    model.quiesce()
    model.migrate_owner(0x2000)


def test_callback_order_violation_is_fail_closed_and_unwinds():
    model = ResourceRollbackContract(0x1000)
    token = model.begin(2, record_ordinal=0, resource_handle=21, resource_hash=22)
    lease = model.begin_callback(token)
    with pytest.raises(ValueError, match="callback order"):
        model.complete_callback(lease, CallbackStage.SECOND)
    assert model.get(2) is None
    assert model.rollback(token)["idempotent"] is True


def test_rollback_waits_for_callback_lease_to_exit():
    model = ResourceRollbackContract(0x1000)
    token = model.begin(3, record_ordinal=0, resource_handle=31, resource_hash=32)
    lease = model.begin_callback(token)
    with pytest.raises(RuntimeError, match="thread quiescence"):
        model.rollback(token)
    model.complete_callback(lease, CallbackStage.FIRST, succeeded=False)
    assert model.get(3) is None


def test_contract_rejects_bool_aliases_and_out_of_range_indices():
    with pytest.raises(ValueError):
        ResourceRollbackContract(True)
    model = ResourceRollbackContract(0x1000)
    with pytest.raises(ValueError, match="network index"):
        model.begin(True, record_ordinal=0, resource_handle=1, resource_hash=1)
    with pytest.raises(ValueError, match="network index"):
        model.begin(8, record_ordinal=0, resource_handle=1, resource_hash=1)
    with pytest.raises(ValueError, match="resource_handle"):
        model.begin(0, record_ordinal=0, resource_handle=True, resource_hash=1)


def test_synthetic_report_is_fail_closed():
    report = synthetic_report()
    assert report["schema"] == "hd2_player_resource_rollback_quiescence_contract_v1"
    assert report["build"] == BUILD
    assert report["capacity"] == 8
    checks = report["checks"]
    assert checks["abi_callback_tables_match"] is True
    assert checks["third_callback_failure_unwinds_reverse_order"] is True
    assert checks["partial_callback_failure_unwinds_reverse_order"] is True
    assert checks["partial_callback_failure_clears_all_side_effects"] is True
    assert checks["rollback_reentry_is_idempotent"] is True
    assert checks["stale_generation_reentry_rejected"] is True
    assert checks["owner_migration_requires_quiescence"] is True
    assert checks["owner_epoch_changes_on_migration"] is True
    assert checks["thread_quiescence_gate_proven"] is True
    assert checks["production_patch_ready"] is False
    assert checks["runtime_verified"] is False
    assert checks["installable"] is False
    assert checks["multiplayer_verified"] is False

