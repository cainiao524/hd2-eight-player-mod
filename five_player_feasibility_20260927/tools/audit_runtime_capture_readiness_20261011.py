from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "output" / "native_dispatch_20261010" / "hd2_party_one_shot_reader_ready_20261111_r13.json"
OUTPUT = ROOT / "output" / "native_dispatch_20261010" / "runtime_capture_readiness_audit_20261011.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


ready = json.loads(RECEIPT.read_text(encoding="utf-8"))
package_info = ready["package"]
package_path = Path(package_info["path"])
package_exists = package_path.is_file()
package_hash = sha256(package_path) if package_exists else None

report = {
    "schema": "hd2_runtime_capture_readiness_audit_v1",
    "build": ready["steam_build"],
    "readiness_receipt": {
        "path": RECEIPT.relative_to(ROOT).as_posix(),
        "sha256": sha256(RECEIPT),
    },
    "package": {
        "path": package_info["path"],
        "expected_sha256": package_info["sha256"],
        "actual_sha256": package_hash,
        "exists": package_exists,
        "sha256_matches": package_exists and package_hash == package_info["sha256"],
        "read_only_probe": package_info["read_only_probe"],
        "bundled_hd2_scanner": package_info["bundled_hd2_scanner"],
    },
    "runtime": {
        "fresh_probe_done": ready["runtime_result"]["fresh_probe_done"],
        "user_launch_pending": ready["runtime_result"]["user_launch_pending"],
        "native_calls": ready["runtime_result"]["native_calls"],
        "memory_writes": ready["runtime_result"]["memory_writes"],
        "hooks_installed": ready["runtime_result"]["hooks_installed"],
        "accepted_runtime_evidence": False,
    },
    "decision": {
        "ready_for_explicit_future_capture_window": package_exists and package_hash == package_info["sha256"],
        "runtime_verified": False,
        "multiplayer_verified": False,
        "public_release_allowed": False,
    },
    "limits": [
        "This audit reads the saved readiness receipt and package hash only.",
        "It does not read a game process, call game functions, install a hook or alter game memory.",
        "A future capture must still occur in an explicitly opened test room and must bind the Party/Session ABI before any write path is considered.",
    ],
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"output": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "decision": report["decision"]}, ensure_ascii=False))
