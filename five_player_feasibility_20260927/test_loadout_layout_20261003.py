import json
from pathlib import Path


def test_loadout_layout_report():
    report = json.loads((Path(__file__).parent / "loadout_layout_relocation_audit_20261003.json").read_text(encoding="utf-8"))
    assert report["schema"] == "hd2_loadout_layout_relocation_audit_v1"
    assert report["build"] == 25480438
    assert report["verification_passed"] is True
    assert report["checks_passed"] == report["checks_total"]
    assert report["decision"]["production_patch_ready"] is False
    assert report["decision"]["installable"] is False
    assert report["decision"]["multiplayer_verified"] is False
    assert report["runtime_verified"] is False
    assert report["live_process_accessed"] is False

    layout = report["relocation_model"]
    assert layout["eight_entries"] == 8
    assert layout["inline_next_widget_overlap_bytes"] > 0
    assert layout["sidecar_required_if_object_size_stays"] is True
