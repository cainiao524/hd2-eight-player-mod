"""Offline tests for the peer/confirmed-peer lifecycle contract."""
import pytest

from peer_lifecycle_sidecar_contract_20261003 import (
    BUILD,
    CAPACITY,
    CallbackLease,
    MigrationToken,
    PeerLifecycleSidecar,
    PeerToken,
    synthetic_report,
)


def confirmed_sidecar() -> tuple[PeerLifecycleSidecar, list[PeerToken]]:
    sidecar = PeerLifecycleSidecar(0x1000, "epoch-1")
    tokens = []
    for index in range(4, 8):
        token = sidecar.reserve(f"member-{index}", f"peer-{index}", index)
        assert sidecar.confirm(token, f"handle-{index}")["accepted"]
        tokens.append(token)
    return sidecar, tokens


def test_partial_confirmation_rolls_back_every_owned_resource():
    sidecar = PeerLifecycleSidecar(0x1000, "epoch-1")
    token = sidecar.reserve("member-4", "peer-4", 4)
    result = sidecar.confirm(token, "handle-4", fail_stage="confirmed_dispatch")
    assert result == {
        "operation": "confirm", "accepted": False, "reason": "callback_failed",
        "stage": "confirmed_dispatch", "rolled_back": True,
    }
    assert sidecar.snapshot()["records"][4]["state"] == "pending"
    assert sidecar.snapshot()["records"][4]["resource_handle"] is None
    assert sidecar.confirm(token, "handle-4")["accepted"]


def test_pending_cancel_is_idempotent_and_does_not_consume_the_slot():
    sidecar = PeerLifecycleSidecar(0x1000, "epoch-1")
    token = sidecar.reserve("member-4", "peer-4", 4)
    assert sidecar.cancel_pending(token)["accepted"]
    assert sidecar.cancel_pending(token)["reason"] == "already_cancelled"
    replacement = sidecar.reserve("member-4", "peer-4-retry", 4)
    assert replacement.generation > token.generation
    assert sidecar.confirm(replacement, "handle-4")["accepted"]


def test_peer_tokens_reject_bool_aliases_for_index_and_generation():
    sidecar = PeerLifecycleSidecar(0x1000, "epoch-1")
    token = sidecar.reserve("member-4", "peer-4", 4)
    assert sidecar.confirm(token, "handle-4")["accepted"]
    forged_index = PeerToken(True, token.generation)
    forged_generation = PeerToken(token.network_index, True)
    assert sidecar.begin_release(forged_index)["reason"] == "stale_or_missing"
    assert sidecar.begin_release(forged_generation)["reason"] == "stale_or_missing"


def test_departure_is_idempotent_and_reconnect_fences_old_callbacks():
    sidecar, _ = confirmed_sidecar()
    old = sidecar._records[4]
    assert old is not None
    token = PeerToken(4, old.generation)
    assert sidecar.depart(token)["accepted"]
    assert sidecar.depart(token)["reason"] == "already_removed"
    replacement = sidecar.reserve("member-4", "peer-4-reconnect", 4)
    assert replacement.generation > token.generation
    assert sidecar.confirm(replacement, "handle-4-reconnect")["accepted"]
    assert sidecar.finish_release(token)["reason"] == "already_removed"
    with pytest.raises(ValueError, match="stale_or_missing"):
        sidecar.acquire_callback(token)


def test_callback_lease_blocks_departure_and_migration_until_released():
    sidecar, _ = confirmed_sidecar()
    token = PeerToken(4, sidecar._records[4].generation)
    lease = sidecar.acquire_callback(token)
    assert sidecar.begin_release(token)["reason"] == "callback_in_flight"
    with pytest.raises(ValueError, match="callback_in_flight"):
        sidecar.begin_migration(0x2000, "epoch-2")
    assert sidecar.release_callback(lease)["accepted"]
    assert sidecar.release_callback(lease)["reason"] == "already_released"
    assert sidecar.depart(token)["accepted"]


def test_callback_lease_token_mismatch_does_not_drop_live_lease():
    sidecar, _ = confirmed_sidecar()
    token = PeerToken(4, sidecar._records[4].generation)
    other = PeerToken(5, sidecar._records[5].generation)
    lease = sidecar.acquire_callback(token)
    forged = CallbackLease(lease.lease_id, other)
    assert sidecar.release_callback(forged)["reason"] == "lease_token_mismatch"
    assert sidecar.begin_release(token)["reason"] == "callback_in_flight"
    assert sidecar.release_callback(lease)["accepted"]


def test_migration_abort_restores_owner_and_commit_rebuilds_maps():
    sidecar, _ = confirmed_sidecar()
    before = sidecar.snapshot()
    staged = sidecar.begin_migration(0x2000, "epoch-2")
    assert sidecar.abort_migration(staged)["reason"] == "rolled_back"
    assert sidecar.abort_migration(staged)["reason"] == "already_aborted"
    assert sidecar.abort_migration(MigrationToken(True, 0x2000, "epoch-2"))["reason"] == "invalid_token"
    assert sidecar.snapshot()["owner_key"] == before["owner_key"]
    assert sidecar.snapshot()["owner_epoch"] == before["owner_epoch"]
    migration = sidecar.begin_migration(0x2000, "epoch-2", [
        {"member_id": "member-4", "peer_id": "peer-4-new", "network_index": 4},
        {"member_id": "member-5", "peer_id": "peer-5", "network_index": 5},
        {"member_id": "member-6", "peer_id": "peer-6", "network_index": 6},
        {"member_id": "member-7", "peer_id": "peer-7", "network_index": 7},
    ])
    assert sidecar.commit_migration(migration)["accepted"]
    assert sidecar.snapshot()["peer_to_index"]["peer-4-new"] == 4
    with pytest.raises(ValueError, match="stale_or_missing"):
        sidecar.acquire_callback(PeerToken(4, 1))


def test_invalid_migration_rejected_without_mutation_and_report_is_fail_closed():
    sidecar, _ = confirmed_sidecar()
    before = sidecar.snapshot()
    with pytest.raises(ValueError, match="migration_duplicate_index"):
        sidecar.begin_migration(0x2000, "epoch-2", [
            {"member_id": "member-4", "peer_id": "peer-a", "network_index": 4},
            {"member_id": "member-5", "peer_id": "peer-b", "network_index": 4},
            {"member_id": "member-6", "peer_id": "peer-6", "network_index": 6},
            {"member_id": "member-7", "peer_id": "peer-7", "network_index": 7},
        ])
    assert sidecar.snapshot()["owner_key"] == before["owner_key"]
    report = synthetic_report()
    assert report["schema"] == "hd2_peer_lifecycle_sidecar_contract_v1"
    assert report["build"] == BUILD
    assert report["capacity"] == CAPACITY
    assert all(report["checks"].values())
    assert report["native_owner_quiescence_proven"] is False
    assert report["runtime_verified"] is False
    assert report["installable"] is False
    assert report["multiplayer_verified"] is False
