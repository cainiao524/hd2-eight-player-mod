import json
from pathlib import Path


def test_selector_cleanup_xrefs_report():
    p = Path(__file__).with_name("selector_cleanup_xrefs_20261003.json")
    report = json.loads(p.read_text(encoding="utf-8"))
    assert report["schema"] == "hd2_selector_cleanup_xrefs_v1"
    assert report["build"] == 25480438
    assert report["read_only"] is True
    assert report["process_accessed"] is False
    assert report["game_memory_written"] is False
    assert report["hooks_installed"] is False
    assert report["installable"] is False
    assert report["runtime_verified"] is False
    assert report["multiplayer_verified"] is False
    assert len(report["direct_calls"]["registration"]) == 0
    assert len(report["direct_calls"]["unregistration"]) == 3
    assert len(report["direct_calls"]["status"]) == 3
    assert all(check["passed"] for check in report["checks"])
    assert all(site["owner_source_in_fragment"] == "global+0x1f028" for site in report["cleanup_sites"] if site["helper"] == "unregistration")
