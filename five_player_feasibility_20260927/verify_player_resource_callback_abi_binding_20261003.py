"""Verify that the offline resource transaction stages bind to fixed-build ABI evidence.

This is a static consistency check.  It reads the saved player-creation and
reverse-cleanup reports only; it never opens a process, follows a pointer,
calls native code, writes memory, installs a payload, or claims multiplayer
support.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BUILD = 25480438
HERE = Path(__file__).resolve().parent
ABI_REPORT = HERE / "player_creation_abi_gap_audit_20261003.json"
REVERSE_REPORT = HERE / "player_resource_reverse_cleanup_audit_20261003.json"

CALLBACK_TABLES = {
    "first_callback": "owner+0x40 + component_index*8 + 0xf0c110",
    "second_callback": "owner+0x40 + component_index*8 + 0xf0cb30",
    "third_callback": "owner+0x40 + component_index*8 + 0xf0d550",
}
CALLBACK_ORDER = ["first_callback", "second_callback", "third_callback", "roster_insert"]
REQUIRED_CLEANUP_ANCHORS = {
    "release_entry",
    "resource_release",
    "owner8_key_delete",
    "generic_map_delete",
    "roster_remove",
}
REQUIRED_CLEANUP_EDGES = {"0xfdc820", "0xfddc80", "0x172f8a0"}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def verify() -> dict[str, Any]:
    abi = _read(ABI_REPORT)
    reverse = _read(REVERSE_REPORT)
    abi_section = abi.get("abi", {})
    tables = abi_section.get("callback_tables")
    roster = abi_section.get("roster_leaf_540920")
    fdc = abi_section.get("fdc140_contract")
    anchors = reverse.get("body_anchors")
    edges = reverse.get("release_edges")
    sidecar = abi.get("required_sidecar_contract")

    observed_tables = {
        "first_callback": tables.get("first") if isinstance(tables, dict) else None,
        "second_callback": tables.get("second") if isinstance(tables, dict) else None,
        "third_callback": tables.get("third") if isinstance(tables, dict) else None,
    }
    dispatch = fdc.get("dispatch") if isinstance(fdc, dict) else None
    sidecar_text = " ".join(sidecar) if isinstance(sidecar, list) else ""

    checks = {
        "fixed_build_matches": abi.get("build") == BUILD and reverse.get("build") == BUILD,
        "callback_tables_match": observed_tables == CALLBACK_TABLES,
        "callback_stage_order_complete": CALLBACK_ORDER == [*CALLBACK_TABLES, "roster_insert"],
        "roster_component_matches": isinstance(tables, dict) and tables.get("roster_component") == 239,
        "roster_leaf_guard_and_writes_present": isinstance(roster, dict)
        and roster.get("guard") == "global roster field +0x80 cmp 4"
        and "+0xe8 + ordinal*8" in roster.get("writes", ""),
        "resource_dispatch_abi_present": isinstance(fdc, dict)
        and dispatch == [
            "0x581320(rcx=owner+0x40, rdx=record, r8=metadata, r9=owner+8)",
            "0x581780(rcx=owner+0x40, rdx=record, r8=metadata)",
        ],
        "resource_record_rollback_requirement_present": "idempotent failure unwind" in sidecar_text
        and "Reverse owner+8 ordinal/flags/count" in sidecar_text,
        "reverse_cleanup_anchors_complete": isinstance(anchors, dict)
        and REQUIRED_CLEANUP_ANCHORS.issubset(anchors),
        "reverse_cleanup_edges_complete": isinstance(edges, dict)
        and REQUIRED_CLEANUP_EDGES.issubset(edges),
        "production_patch_ready": False,
        "runtime_verified": False,
        "installable": False,
        "multiplayer_verified": False,
    }
    return {
        "schema": "hd2_player_resource_callback_abi_binding_v1",
        "build": BUILD,
        "callback_order": CALLBACK_ORDER,
        "callback_tables": CALLBACK_TABLES,
        "roster_component": 239,
        "source_reports": {
            "player_creation_abi": {
                "path": str(ABI_REPORT),
                "schema": abi.get("schema"),
                "capture_sha256": abi.get("capture_sha256"),
            },
            "player_resource_reverse_cleanup": {
                "path": str(REVERSE_REPORT),
                "schema": reverse.get("schema"),
                "capture_sha256": reverse.get("capture_sha256"),
            },
        },
        "checks": checks,
        "limits": [
            "Static report binding only; no process query, pointer traversal, native call, memory write, hook, install or multiplayer test.",
            "A matching callback table and cleanup chain does not prove that index 4..7 reaches the runtime creation path.",
            "All production, runtime, install and multiplayer flags remain false.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = verify()
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"schema": report["schema"], "passed": sum(v is True for v in report["checks"].values()), "installable": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
