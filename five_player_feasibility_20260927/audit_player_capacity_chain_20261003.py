"""Audit the fixed-build player/member capacity chain from saved evidence.

This is an offline boundary audit.  It groups the already captured capacity
source, member metadata, enumeration and recreate consumers so a later hook
cannot mistake one `4` literal for the whole admission/creation contract.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = 25480438
CAPTURE_SHA = "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8"
DATA_SHA = "31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d"


def check(rows: list[dict], name: str, passed: bool, detail: object) -> None:
    rows.append({"name": name, "passed": bool(passed), "detail": detail})


def find(rows: list[dict], rva: str) -> dict | None:
    return next((x for x in rows if x.get("rva") == rva), None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", type=Path, default=ROOT / "creation_path_evidence_v3.json")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    checks: list[dict] = []
    source = evidence.get("source", {})
    check(checks, "fixed_build", source.get("build_id") == BUILD, source.get("build_id"))
    check(checks, "capture_identity", source.get("capture_sha256") == CAPTURE_SHA, source.get("capture_sha256"))
    check(checks, "captured_data_identity", source.get("file_sha256", {}).get("captured-data.bin") == DATA_SHA, source.get("file_sha256", {}).get("captured-data.bin"))

    pins = evidence.get("pins", {})
    capacity = pins.get("capacity_source", [])
    initial = pins.get("initial_member_metadata", [])
    helper = pins.get("enumeration_helper", [])
    update = pins.get("enumeration_update", [])
    recreate = pins.get("recreate", [])
    check(checks, "capacity_source_default_four", find(capacity, "0x10919d1") == {"rva": "0x10919d1", "bytes": "b904000000", "sha256": find(capacity, "0x10919d1")["sha256"], "asm": "mov ecx, 4", "root": "0x1091980"} if find(capacity, "0x10919d1") else False, find(capacity, "0x10919d1"))
    check(checks, "capacity_source_stores_owner_1b90", find(capacity, "0x10919de") is not None and "[rbx + 0x1b90]" in find(capacity, "0x10919de").get("asm", ""), find(capacity, "0x10919de"))
    check(checks, "initial_member_metadata_four", find(initial, "0x10915da") is not None and find(initial, "0x10915da").get("asm") == "mov edx, 4", find(initial, "0x10915da"))
    check(checks, "enumerator_capacity_arguments", all(find(helper, x) is not None for x in ("0x1092e78", "0x1092f31")), [find(helper, x) for x in ("0x1092e78", "0x1092f31")])
    check(checks, "enumerator_four_clamp_and_store", find(helper, "0x1092ecb") is not None and find(helper, "0x1092ed0") is not None, [find(helper, x) for x in ("0x1092ecb", "0x1092ed0")])
    check(checks, "state_update_four_clamp_and_store", find(update, "0x1093c91") is not None and find(update, "0x1093c96") is not None, [find(update, x) for x in ("0x1093c91", "0x1093c96")])
    check(checks, "state_update_capacity_argument", find(update, "0x1093d1e") is not None and find(update, "0x1093d1e").get("asm") == "mov r8d, 4", find(update, "0x1093d1e"))
    check(checks, "recreate_adds_four", find(recreate, "0x1093a96") is not None and find(recreate, "0x1093a96").get("asm") == "add ecx, 4", find(recreate, "0x1093a96"))
    report = {
        "schema": "hd2_player_capacity_chain_audit_v1",
        "build": BUILD,
        "capture_sha256": CAPTURE_SHA,
        "source_evidence": args.evidence.name,
        "checks": checks,
        "checks_passed": sum(x["passed"] for x in checks),
        "checks_total": len(checks),
        "verification_passed": all(x["passed"] for x in checks),
        "capacity_groups": {
            "owner_capacity_source": ["0x10919d1", "0x10919de"],
            "initial_member_metadata": ["0x10915da"],
            "enumerator": ["0x1092e78", "0x1092ecb", "0x1092ed0", "0x1092f31"],
            "state_update": ["0x1093c91", "0x1093c96", "0x1093d1e"],
            "recreate": ["0x1093a96"],
        },
        "decision": {
            "production_patch_ready": False,
            "meaning": "The fixed build contains several separate four-player assumptions across capacity initialization, member metadata, enumeration, state update and recreate. They must be patched as one owner/sidecar contract; no single literal is sufficient.",
            "next_required": [
                "Bind owner+0x1b90/0x1bb0 and callback arguments to the real peer/player creation ABI.",
                "Prove an 8-slot backing and rollback for enumeration, recreate, departure and migration.",
                "Capture a real fifth-peer run before enabling any production patch.",
            ],
        },
        "runtime_verified": False,
        "installable": False,
        "multiplayer_verified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.output), "checks_passed": report["checks_passed"], "checks_total": report["checks_total"], "verification_passed": report["verification_passed"], "production_patch_ready": False}, ensure_ascii=False))
    return 0 if report["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
