import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def test_registration_state_verification():
    d=json.loads((ROOT/"live_registration_state_verification_20261003.json").read_text(encoding="utf-8"))
    assert d["verification_passed"] is True
    assert d["checks_passed"] == d["checks_total"]
    assert d["installable"] is False
    assert d["multiplayer_verified"] is False
