import json
from pathlib import Path


def test_loadout_lifecycle_report():
    report = json.loads((Path(__file__).parent / "loadout_lifecycle_abi_audit_20261003.json").read_text(encoding="utf-8"))
    assert report["schema"] == "hd2_loadout_lifecycle_abi_audit_v1"
    assert report["build"] == 25480438
    assert report["verification_passed"] is True
    assert report["checks_passed"] == report["checks_total"]
    assert report["production_patch_ready"] is False
    assert report["runtime_verified"] is False
    assert report["installable"] is False
    assert report["multiplayer_verified"] is False
    assert report["live_process_accessed"] is False

    lifecycle = report["lifecycle"]
    assert lifecycle["screen_entry_rebuild"]["release_before_reconstruct"] == "0x1467330"
    assert lifecycle["screen_entry_rebuild"]["construct_tail"] == "0x1466170"
    assert lifecycle["screen_constructor"]["widget_constructor"] == "0x14aa5c0"
    assert lifecycle["screen_release"]["shared_release_helper"] == "0x144dd70"
    assert lifecycle["alternate_widget_release"]["nested_release_helper"] == "0x18a0fd0"
    assert lifecycle["transition"]["callbacks"] == ["0x189e080", "0x1451100"]
    assert len(report["implementation_boundary"]["blocked_reasons"]) >= 3
