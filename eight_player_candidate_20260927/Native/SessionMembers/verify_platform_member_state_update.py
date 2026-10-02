"""Verify exact captured 0x10937a0 evidence and fail closed on patch claims."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from platform_member_state_update_disasm import BODY_SHA256, END_RVA, ENTRY_RVA, recover, sha256


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify(artifact_path: Path) -> dict:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    current = recover()
    require(artifact["entry"]["rva"] == hex(ENTRY_RVA), "entry RVA mismatch")
    require(artifact["entry"]["end_exclusive"] == hex(END_RVA), "end RVA mismatch")
    require(artifact["entry"]["body_sha256"] == BODY_SHA256, "body hash mismatch")
    require(artifact["entry"]["body_sha256"] == current["entry"]["body_sha256"], "artifact differs from capture")
    require(artifact["control_flow"]["instruction_count"] == current["control_flow"]["instruction_count"], "instruction count mismatch")
    require(artifact["control_flow"]["back_edge_count"] >= 1, "loop inventory missing")
    require(len(artifact["callers"]) == 4, "caller inventory incomplete")
    require(len(artifact["owner_field_sites"]) >= 40, "owner-field inventory unexpectedly small")
    require(len(artifact["four_immediate_sites"]) >= 5, "four-constant inventory unexpectedly small")
    require(artifact["sidecar_patch_assessment"]["installable"] is False, "unsafe artifact marked installable")
    require(artifact["sidecar_patch_assessment"]["safe_leaf_replacement"] is False, "unsafe leaf replacement marked safe")
    return {
        "status": "passed_exact_state_update_evidence",
        "body_sha256": artifact["entry"]["body_sha256"],
        "instruction_count": artifact["control_flow"]["instruction_count"],
        "owner_field_sites": len(artifact["owner_field_sites"]),
        "four_immediate_sites": len(artifact["four_immediate_sites"]),
        "installable": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.artifact), ensure_ascii=False))


if __name__ == "__main__":
    main()
