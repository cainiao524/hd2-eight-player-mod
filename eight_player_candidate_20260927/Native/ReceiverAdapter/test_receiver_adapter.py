import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_receiver_contract():
    report = json.loads((HERE / "receiver_adapter_report_20261003.json").read_text(encoding="utf-8"))
    assert report["build"] == 25480438
    assert report["receiver_selector"] == 168
    assert report["descriptor_offsets"] == ["0x08", "0x18", "0x28", "0x38", "0x48"]
    assert report["test"]["status"] == "passed"
    assert report["checks"]["vector_abi_shape_pinned"] is True
    assert report["checks"]["hash_to_selector_proven"] is False
    assert all(report["checks"][key] is False for key in ("production_executable", "runtime_verified", "installable", "multiplayer_verified", "game_process_accessed", "host_native_code_executed"))
    for name, digest in report["source_sha256"].items():
        assert sha(HERE / name) == digest
    for name, digest in report["binary_sha256"].items():
        assert sha(HERE / name) == digest
