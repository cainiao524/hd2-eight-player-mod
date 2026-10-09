import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT = HERE / "player_resource_report_20261003.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_report_contract_and_hashes():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["build"] == 25480438
    assert report["capacity"] == 16
    assert report["callback_order"] == ["first_callback", "second_callback", "third_callback"]
    assert report["roster_component"] == 239
    assert report["test"]["status"] == "passed"
    assert report["test"]["output"] == "ep_player_resource_synthetic_passed"
    assert all(value is False for value in report["checks"].values())
    for name, digest in report["source_sha256"].items():
        assert sha(HERE / name) == digest
    for name, digest in report["binary_sha256"].items():
        assert sha(HERE / name) == digest


def test_expected_artifacts_exist():
    for name in ("ep_player_resource.h", "ep_player_resource.cpp", "ep_player_resource_test.cpp", "README.zh-TW.md"):
        assert (HERE / name).exists()
