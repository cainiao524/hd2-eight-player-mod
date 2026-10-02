import json
from pathlib import Path


def test_player_capacity_chain_report():
    report = json.loads((Path(__file__).parent / "player_capacity_chain_audit_20261003.json").read_text(encoding="utf-8"))
    assert report["schema"] == "hd2_player_capacity_chain_audit_v1"
    assert report["build"] == 25480438
    assert report["verification_passed"] is True
    assert report["checks_passed"] == report["checks_total"] == 11
    assert report["decision"]["production_patch_ready"] is False
    assert report["runtime_verified"] is False
    assert report["installable"] is False
    assert report["multiplayer_verified"] is False
