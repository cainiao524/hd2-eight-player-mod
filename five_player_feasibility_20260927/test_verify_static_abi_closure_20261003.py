import json

import verify_static_abi_closure_20261003 as closure


def test_fixed_build_static_closure_is_consistent_and_fail_closed():
    report = closure.verify()
    assert report["schema"] == "hd2_static_abi_closure_receipt_v1"
    assert report["build"] == closure.BUILD
    assert all(report["checks"].values())
    assert report["installable"] is False
    assert report["runtime_verified"] is False
    assert report["multiplayer_verified"] is False
    assert all(path["build"] == closure.BUILD for path in report["source_reports"].values())


def test_closure_rejects_a_tampered_source(monkeypatch, tmp_path):
    source = closure.REPORTS["native_admission_plan"]
    tampered = json.loads(source.read_text(encoding="utf-8"))
    tampered["sidecar"]["host_peer_slots"] = 4
    copy = tmp_path / source.name
    copy.write_text(json.dumps(tampered), encoding="utf-8")
    reports = dict(closure.REPORTS)
    reports["native_admission_plan"] = copy
    monkeypatch.setattr(closure, "REPORTS", reports)
    report = closure.verify()
    assert report["checks"]["native_plan_has_eight_slots_and_ten_sites"] is False


def test_closure_keeps_runtime_and_install_claims_false():
    report = closure.verify()
    for flags in report["production_flags"].values():
        assert all(value is False for value in flags.values())


def test_closure_requires_public_runtime_audit_to_remain_observation_only(monkeypatch):
    reports = dict(closure.REPORTS)
    path = reports["public_runtime_entry_audit"]
    data = json.loads(path.read_text(encoding="utf-8"))
    data["conclusion"]["public_peer_admission_abi_found"] = True
    copy = path.parent / "_tmp_public_runtime_entry_audit.json"
    copy.write_text(json.dumps(data), encoding="utf-8")
    try:
        reports["public_runtime_entry_audit"] = copy
        monkeypatch.setattr(closure, "REPORTS", reports)
        assert closure.verify()["checks"]["public_runtime_bridge_remains_unavailable"] is False
    finally:
        copy.unlink()


def test_closure_requires_join_handler_four_literal_inventory(monkeypatch, tmp_path):
    reports = dict(closure.REPORTS)
    path = reports["join_handler_fixed_four_inventory"]
    data = json.loads(path.read_text(encoding="utf-8"))
    data["fixed_four_sites"] = data["fixed_four_sites"][:-1]
    copy = tmp_path / path.name
    copy.write_text(json.dumps(data), encoding="utf-8")
    reports["join_handler_fixed_four_inventory"] = copy
    monkeypatch.setattr(closure, "REPORTS", reports)
    assert closure.verify()["checks"]["join_handler_four_literals_classified"] is False


def test_closure_rejects_a_claimed_external_game_bridge(monkeypatch, tmp_path):
    reports = dict(closure.REPORTS)
    path = reports["external_party_playfab_capacity"]
    data = json.loads(path.read_text(encoding="utf-8"))
    data["game_native_peer_admission_resolved"] = True
    copy = tmp_path / path.name
    copy.write_text(json.dumps(data), encoding="utf-8")
    reports["external_party_playfab_capacity"] = copy
    monkeypatch.setattr(closure, "REPORTS", reports)
    assert closure.verify()["checks"]["external_party_playfab_boundary_is_not_game_bridge"] is False
