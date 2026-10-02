"""Verify the saved exact-build peer-admission bridge boundary review.

This verifier consumes only repository files supplied by the caller.  It does
not inspect a process, load a module, resolve a writable callback table, patch
bytes, install a hook, or contact a service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PLAN = HERE / "native_peer_admission_plan_20261002.json"
BOUNDARY = HERE / "native_peer_admission_bridge_boundary_20261002.json"
CAPTURE = HERE / "live_native_session_capture_20261002.json"
MIDGATE = HERE / "midgate_bridge_plan_20261002.json"

REQUIRED_GAME_RVAS = {
    "0x108bc70",
    "0x108c18f",
    "0x108c3d8",
    "0x108c760",
    "0x1089720",
    "0x108d190",
    "0xb90b20",
    "0x1087540",
    "0x10845b0",
    "0x1086460",
}


class BoundaryError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BoundaryError(f"cannot_read:{path.name}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(base: Path = HERE) -> dict[str, Any]:
    boundary = _load(base / BOUNDARY.name)
    capture = _load(base / CAPTURE.name)
    plan = _load(base / PLAN.name)
    midgate = _load(base / MIDGATE.name)

    if boundary.get("steam_build") != 25480438:
        raise BoundaryError("boundary_build_mismatch")
    if boundary.get("capture_identity_sha256") != "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8":
        raise BoundaryError("boundary_capture_identity_mismatch")
    status = boundary.get("status", {})
    if status.get("executable") is not False or status.get("live_ready") is not False:
        raise BoundaryError("boundary_must_remain_blocked")
    if status.get("multiplayer_verified") is not False:
        raise BoundaryError("boundary_multiplayer_claim")

    rows = {
        str(row.get("rva", "")).lower()
        for row in capture.get("rows", [])
        if isinstance(row, dict) and row.get("module") == "game" and row.get("rva")
    }
    missing = sorted(REQUIRED_GAME_RVAS - rows)
    if missing:
        raise BoundaryError("capture_sites_missing:" + ",".join(missing))
    if capture.get("build") != 25480438:
        raise BoundaryError("capture_build_mismatch")

    if plan.get("executable") is not False or plan.get("multiplayer_verified") is not False:
        raise BoundaryError("native_plan_not_blocked")
    plan_sites = {
        (hex(item["rva"]) if type(item.get("rva")) is int else str(item.get("rva", ""))).lower()
        for item in plan.get("sites", [])
        if isinstance(item, dict)
    }
    if not REQUIRED_GAME_RVAS.issubset(plan_sites):
        raise BoundaryError("native_plan_sites_missing")

    if midgate.get("steam_build") != 25480438:
        raise BoundaryError("midgate_build_mismatch")
    capacity = midgate.get("capacity_gate", {})
    if capacity.get("rva") != "0x108c18f":
        raise BoundaryError("midgate_root_mismatch")
    if capacity.get("count_prefix_continuation") != "0x108c1b5":
        raise BoundaryError("midgate_continuation_mismatch")
    if capacity.get("four_constant", {}).get("bytes") != "b904000000":
        raise BoundaryError("midgate_four_constant_mismatch")
    allocator = midgate.get("allocator_gate", {})
    if allocator.get("rva") != "0x108c3d8":
        raise BoundaryError("allocator_root_mismatch")
    if allocator.get("loop_bound_instruction", {}).get("bytes") != "83f904":
        raise BoundaryError("allocator_four_bound_mismatch")

    result = {
        "schema": "hd2_native_peer_admission_bridge_boundary_verification_v1",
        "status": "passed_static_boundary_checks",
        "steam_build": 25480438,
        "boundary_sha256": _sha256(base / BOUNDARY.name),
        "capture_sha256": _sha256(base / CAPTURE.name),
        "native_plan_sha256": _sha256(base / PLAN.name),
        "midgate_plan_sha256": _sha256(base / MIDGATE.name),
        "checks": {
            "capture_required_game_sites": len(REQUIRED_GAME_RVAS),
            "native_plan_blocked": True,
            "midfunction_capacity_boundary": True,
            "allocator_four_bound_boundary": True,
            "confirmed_peer_dispatch_binding_closed": False,
            "production_patch_emitted": False,
            "process_accessed": False,
            "multiplayer_verified": False,
        },
        "unresolved": boundary.get("production_blockers", []),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=HERE,
                        help="directory containing the saved JSON evidence")
    parser.add_argument("--output", type=Path,
                        help="optional output JSON path")
    args = parser.parse_args()
    result = verify(args.base.resolve())
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
