import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def test_dynamic_registration_caller_audit_is_fail_closed():
    d=json.loads((ROOT/"dynamic_registration_caller_audit_20261003.json").read_text(encoding="utf-8"))
    assert d["checks"][0]["passed"] is True
    assert d["checks"][1]["passed"] is True
    assert d["hash_to_selector_proven"] is False
    assert d["installable"] is False
    assert d["multiplayer_verified"] is False
