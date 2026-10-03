"""Verify the fixed-build PlayerCreationGate adapter receipt and synthetic binary."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECEIPT = HERE / "player_creation_gate_receipt_20261003.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["schema"] == "hd2_player_creation_gate_adapter_v1"
    assert receipt["build"] == 25480438
    assert receipt["capacity_contract"]["valid_network_indexes"] == list(range(8))
    assert receipt["gates"] == {"production_executable": False,
                                "runtime_verified": False,
                                "installable": False,
                                "multiplayer_verified": False}
    for name, expected in receipt["source_sha256"].items():
        assert sha(HERE / name) == expected, name
    exe = HERE / receipt["test"]["binary"]
    assert sha(exe) == receipt["binary_sha256"][receipt["test"]["binary"]]
    run = subprocess.run([str(exe)], cwd=HERE, capture_output=True, text=True, check=True)
    assert receipt["test"]["output"] in run.stdout
    print(json.dumps({"schema": receipt["schema"], "status": "passed",
                      "output": run.stdout.strip()}, ensure_ascii=False))

if __name__ == "__main__":
    main()
