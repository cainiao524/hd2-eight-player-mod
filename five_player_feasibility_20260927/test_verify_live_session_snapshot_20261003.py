import json
from pathlib import Path

from verify_live_session_snapshot_20261003 import verify


ROOT = Path(__file__).resolve().parent


def test_live_baseline_snapshot_is_stable() -> None:
    report = verify([
        ROOT / "live_session_snapshot_20261003_r2.json",
        ROOT / "live_session_snapshot_20261003_r3.json",
    ])
    assert report["verification_passed"] is True
    assert report["checks_passed"] == report["checks_total"] == 11
    assert report["session_peer_count"] == 4
    assert report["maximum_observed_peer_count"] == 4
    assert report["multiplayer_verified"] is False
