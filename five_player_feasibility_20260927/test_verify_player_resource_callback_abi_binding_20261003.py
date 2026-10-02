import json
import verify_player_resource_callback_abi_binding_20261003 as binding
from verify_player_resource_callback_abi_binding_20261003 import BUILD, CALLBACK_ORDER, CALLBACK_TABLES, verify


def test_fixed_build_callback_and_cleanup_binding_is_complete():
    report = verify()
    assert report["schema"] == "hd2_player_resource_callback_abi_binding_v1"
    assert report["build"] == BUILD
    assert report["callback_order"] == ["first_callback", "second_callback", "third_callback"]
    assert report["roster_insert_phase"] == "first_callback"
    assert report["callback_tables"] == CALLBACK_TABLES
    checks = report["checks"]
    assert all(checks[key] is True for key in (
        "fixed_build_matches",
        "callback_tables_match",
        "callback_stage_order_complete",
        "model_tables_match",
        "roster_in_first_table",
        "registration_capture_matches",
        "roster_component_matches",
        "roster_leaf_guard_and_writes_present",
        "resource_dispatch_abi_present",
        "resource_record_rollback_requirement_present",
        "reverse_cleanup_anchors_complete",
        "reverse_cleanup_edges_complete",
    ))
    assert checks["production_patch_ready"] is False
    assert checks["runtime_verified"] is False
    assert checks["installable"] is False
    assert checks["multiplayer_verified"] is False


def test_obsolete_fourth_stage_is_rejected(monkeypatch):
    monkeypatch.setattr(binding.transaction, "CALLBACK_ORDER", (*CALLBACK_ORDER, "roster_insert"))
    assert verify()["checks"]["callback_stage_order_complete"] is False


def test_wrong_roster_table_is_rejected(tmp_path, monkeypatch):
    data = json.loads(binding.REGISTRATION_REPORT.read_text(encoding="utf-8"))
    for row in data["component_239"]:
        if row["target_rva"] == "0x540920":
            row["table_base_offset"] = "0xf0d550"
    path = tmp_path / "registration.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(binding, "REGISTRATION_REPORT", path)
    assert verify()["checks"]["roster_in_first_table"] is False
