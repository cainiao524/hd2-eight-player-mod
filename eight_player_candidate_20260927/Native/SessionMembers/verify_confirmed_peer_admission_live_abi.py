"""Verify the read-only live confirmed-peer sender ABI inventory."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from confirmed_peer_admission_live_abi import BODY_SHA256, BODY_END, ENTRY, recover


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify(artifact_path: Path) -> dict:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    current = recover()
    fn = artifact["function"]
    require(fn["entry_rva"] == hex(ENTRY), "entry mismatch")
    require(fn["end_exclusive"] == hex(BODY_END), "end mismatch")
    require(fn["body_sha256"] == BODY_SHA256, "body hash mismatch")
    require(fn["instructions"] == current["function"]["instructions"], "instruction evidence changed")
    require(len(artifact["semantic_sites"]) == 8, "semantic site count mismatch")
    require(artifact["sidecar_plan"]["installable"] is False, "artifact must remain non-installable")
    require(artifact["sidecar_plan"]["multiplayer_verified"] is False, "artifact cannot claim multiplayer")
    return {"status": "passed_static_live_abi_verification", "body_bytes": fn["body_bytes"], "semantic_sites": len(artifact["semantic_sites"]), "installable": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.artifact), ensure_ascii=False))


if __name__ == "__main__":
    main()
