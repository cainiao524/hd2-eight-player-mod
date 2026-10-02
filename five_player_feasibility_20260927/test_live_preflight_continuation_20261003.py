import json
from pathlib import Path


def test_live_preflight_continuation_report():
    report = json.loads((Path(__file__).parent / "live_preflight_continuation_verification_20261003.json").read_text(encoding="utf-8"))
    assert report["schema"] == "hd2_live_preflight_continuation_verification_v1"
    assert report["build"] == 25480438
    assert report["pid"] == 36900
    assert report["verification_passed"] is True
    assert report["runtime_calls_made"] is False
    assert report["game_memory_written"] is False
    assert report["hooks_installed"] is False
    assert report["resolver_closed"] is False
    assert report["installable"] is False
    assert report["multiplayer_verified"] is False
    assert report["checks_passed"] == report["checks_total"]
