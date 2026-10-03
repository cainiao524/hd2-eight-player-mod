import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def test_registration_state_verification_is_superseded():
    d=json.loads((ROOT/"live_registration_state_verification_20261003.json").read_text(encoding="utf-8"))
    assert d["superseded"] is True
    assert d["verification_passed"] is False
    assert d["negative_observation_valid"] is False
    assert d["installable"] is False
    assert d["multiplayer_verified"] is False
