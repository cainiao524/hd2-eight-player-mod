import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def test_capture_rerun_receipt_passes():
    d=json.loads((ROOT / "live_capture_rerun_verification_20261003.json").read_text(encoding="utf-8"))
    assert d["verification_passed"] is True
    assert d["checks_passed"] == d["checks_total"]
    assert d["installable"] is False
    assert d["multiplayer_verified"] is False

def test_private_scan_failure_is_not_negative():
    d=json.loads((ROOT / "live_private_registry_20261003_rerun.failure.json").read_text(encoding="utf-8"))
    assert d["error"] == "result_file_missing_after_process_exit"
    assert d["multiplayer_verified"] is False

def test_rerun_keeps_one_peer_boundary():
    d=json.loads((ROOT / "live_session_snapshot_20261003_rerun.json").read_text(encoding="utf-8"))
    assert d["session"]["peer_count_raw"] == 1
    assert d["roster"]["documented_slot_count"] == 4
    assert d["roster"]["out_of_contract_slots"] == [4,5,6,7]
