from player_creation_abi_gap_audit_20261003 import build_audit


def test_player_creation_abi_gap_audit_is_replayable_and_fail_closed():
    result = build_audit()
    assert result["schema"] == "hd2_player_creation_abi_gap_audit_v1"
    assert result["build"] == 25480438
    assert len(result["pins"]) >= 35
    assert result["checks"]["gate_rejects_index_4_to_7"]
    assert result["checks"]["first_stage_roster_has_fixed_four_guard"]
    assert not result["checks"]["player_resource_reverse_cleanup_proven"]
    assert not result["checks"]["partial_resource_rollback_proven"]
    assert not result["checks"]["index_4_to_7_player_creation_proven"]
    assert not result["checks"]["installable"]
