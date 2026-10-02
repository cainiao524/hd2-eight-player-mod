from pathlib import Path

from player_resource_reverse_cleanup_audit_20261003 import build_audit


EVIDENCE = Path(__file__).resolve().parents[1] / "evidence" / "existing-code-evidence-25480438"


def test_reverse_cleanup_chain_is_pinned_and_fail_closed():
    result = build_audit(EVIDENCE)
    assert result["schema"] == "hd2_player_resource_reverse_cleanup_audit_v1"
    assert result["checks"]["create_record_fields_are_pinned"]
    assert result["checks"]["resource_handle_release_is_pinned"]
    assert result["checks"]["owner8_reverse_map_delete_is_pinned"]
    assert result["checks"]["owner8_ordinal_flag_compaction_is_pinned"]
    assert result["checks"]["missing_key_does_not_decrement_owner8_count"]
    assert not result["checks"]["partial_callback_rollback_is_complete"]
    assert not result["checks"]["resource_release_idempotence_under_reentry"]
    assert not result["checks"]["installable"]
