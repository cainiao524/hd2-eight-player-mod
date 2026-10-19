"""Verify the fixed-build PlayerCreationGate adapters and synthetic binaries."""
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
    integration_exe = HERE / receipt["integration_test"]["binary"]
    assert sha(integration_exe) == receipt["binary_sha256"][receipt["integration_test"]["binary"]]
    integration_run = subprocess.run([str(integration_exe)], cwd=HERE,
                                     capture_output=True, text=True, check=True)
    assert receipt["integration_test"]["output"] in integration_run.stdout
    resource_integration_exe = HERE / receipt["resource_integration_test"]["binary"]
    assert sha(resource_integration_exe) == receipt["binary_sha256"][receipt["resource_integration_test"]["binary"]]
    resource_run = subprocess.run([str(resource_integration_exe)], cwd=HERE,
                                  capture_output=True, text=True, check=True)
    assert receipt["resource_integration_test"]["output"] in resource_run.stdout
    print(json.dumps({"schema": receipt["schema"], "status": "passed",
                      "output": [run.stdout.strip(), integration_run.stdout.strip(),
                                 resource_run.stdout.strip()]},
                      ensure_ascii=False))

if __name__ == "__main__":
    main()
