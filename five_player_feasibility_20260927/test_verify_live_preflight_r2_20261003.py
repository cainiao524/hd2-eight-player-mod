import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def test_r2_capture_matches_previous_bundle(tmp_path: Path) -> None:
    output = tmp_path / "r2.json"
    spec = spec_from_file_location("verify_live_preflight_r2_20261003", ROOT / "verify_live_preflight_r2_20261003.py")
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    old_argv = sys.argv
    try:
        sys.argv = [str(ROOT / "verify_live_preflight_r2_20261003.py"), "--output", str(output)]
        assert module.main() == 0
    finally:
        sys.argv = old_argv
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["verification_passed"] is True
    assert report["checks_passed"] == report["checks_total"] == 11
    assert report["resolver_closed"] is False
    assert report["multiplayer_verified"] is False
