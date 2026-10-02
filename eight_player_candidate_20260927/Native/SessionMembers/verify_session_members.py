"""Run the bounded native session-member execution comparison and save receipt."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "session_members_verification_20261002.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    sys.path.insert(0, str(ROOT / ".native-test-deps"))
    sys.path.insert(0, str(HERE))
    import session_members  # noqa: PLC0415
    import test_session_members  # noqa: PLC0415

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_session_members)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    evidence = ROOT / "five_player_feasibility_20260927" / "creation_enumeration_helper_full_disasm_20261002.json"
    artifact = session_members.build(
        game_base=0x7FF600000000,
        code_address=0x7FF610000000,
        resolver_address=0x7FF610020000,
        consumer_address=0x7FF610021000,
        sidecar_address=0x7FF610022000,
    )
    report = {
        "status": "passed" if result.wasSuccessful() else "failed",
        "test_methods_run": result.testsRun,
        "failure_count": len(result.failures),
        "error_count": len(result.errors),
        "candidate": {
            "source": "Native/SessionMembers/session_members.py",
            "source_sha256": sha(HERE / "session_members.py"),
            "body_evidence": str(evidence.relative_to(ROOT.parent)).replace("\\", "/"),
            "body_evidence_sha256": sha(evidence),
            "code_sha256": artifact["code_sha256"],
            "size_bytes": artifact["size_bytes"],
            "capacity": artifact["capacity"],
        },
        "comparison": {
            "executed_original_capture_body": True,
            "executed_candidate_bytes": True,
            "original_counts": "0..4 on both platform branches",
            "candidate_counts": "0..8 plus capped 9 on both platform branches",
            "platform_callbacks": "synthetic Unicorn stubs with captured argument shape",
            "consumer_callback": "synthetic sidecar-aware callback contract",
        },
        "production": {
            "installable": False,
            "game_process_accessed": False,
            "game_files_modified": False,
            "multiplayer_verified": False,
            "blockers": [
                "resolver/consumer callback identities and ABI are not found in the game",
                "0x1093590 and all other four-slot readers/writers still need sidecar-aware production patches",
                "hook/unwind/owner lifetime and Party service acceptance remain unclosed",
            ],
        },
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "status": report["status"],
                      "tests": result.testsRun, "code_sha256": artifact["code_sha256"]}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
