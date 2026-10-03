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
