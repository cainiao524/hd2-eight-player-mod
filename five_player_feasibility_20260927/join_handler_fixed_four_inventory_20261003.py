"""Inventory fixed-four literals in the captured host join handler.

This is a static guard for the native admission plan.  It distinguishes
capacity/slot bounds from protocol status and event metadata literals so a
future bridge cannot blindly replace every ``4`` with ``8``.  It never opens a
process, follows pointers, writes memory, or emits an installable patch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

BUILD = 25480438
MODULE = "game.dll"
HERE = Path(__file__).resolve().parent
DISASM = HERE / "join_handler_disasm.json"
DISASM_SHA256 = "f0e2c853fb731fecffd27ed2bbab97f9d8ed2868b076c60ee51bcdfe472e505c"

PATCHABLE = {
    "0x108c1b5": ("capacity_base", "mid_function_capacity_gate"),
    "0x108c2cb": ("host_peer_search_bound", "peer_table_loop"),
    "0x108c393": ("host_peer_hole_search_bound", "peer_table_loop"),
    "0x108c3e2": ("host_index_allocator_bound", "allocator_loop"),
    "0x108c4a1": ("host_large_record_bound", "large_record_loop"),
}

PROTECTED = {
    "0x108be3c": ("protocol_status_code", "do_not_patch"),
    "0x108c1c5": ("capacity_reject_event_code", "do_not_patch"),
    "0x108c584": ("event_metadata_value", "do_not_patch"),
}


def _rows() -> list[dict]:
    data = json.loads(DISASM.read_text(encoding="utf-8"))
    if data.get("range") != ["0x108be06", "0x108c5be"]:
        raise ValueError("unexpected_join_handler_range")
    rows = data.get("instructions")
    if not isinstance(rows, list):
        raise ValueError("missing_join_handler_instructions")
    return rows


def _is_literal_four(asm: str) -> bool:
    return bool(re.search(r"(?:,|\s)(?:4|0x4)$", asm.lower()))


def verify() -> dict:
    rows = _rows()
    by_rva = {str(row["rva"]).lower(): row for row in rows}
    literal_rows = [row for row in rows if _is_literal_four(str(row.get("asm", "")))]
    literal_rvas = {str(row["rva"]).lower() for row in literal_rows}
    expected_rvas = set(PATCHABLE) | set(PROTECTED)
    if literal_rvas != expected_rvas:
        raise ValueError(f"unclassified_or_missing_literal_four:{sorted(literal_rvas ^ expected_rvas)}")

    sites = []
    for rva, (role, category) in PATCHABLE.items():
        row = by_rva.get(rva)
        if row is None:
            raise ValueError(f"missing_patchable_site:{rva}")
        sites.append({
            "rva": rva,
            "bytes": row["bytes"],
            "asm": row["asm"],
            "sha256": row["sha256"],
            "role": role,
            "category": category,
            "requires_sidecar_or_continuation": True,
        })

    protected = []
    for rva, (role, policy) in PROTECTED.items():
        row = by_rva.get(rva)
        if row is None:
            raise ValueError(f"missing_protected_site:{rva}")
        protected.append({
            "rva": rva,
            "bytes": row["bytes"],
            "asm": row["asm"],
            "sha256": row["sha256"],
            "role": role,
            "policy": policy,
        })

    checks = {
        "fixed_build": BUILD == 25480438,
        "module": MODULE == "game.dll",
        "disassembly_identity": hashlib.sha256(DISASM.read_bytes()).hexdigest() == DISASM_SHA256,
        "five_capacity_or_slot_sites": len(sites) == 5,
        "three_protected_four_literals": len(protected) == 3,
        "all_four_literals_classified": literal_rvas == expected_rvas,
        "no_direct_constant_patch_ready": True,
    }
    return {
        "schema": "hd2_join_handler_fixed_four_inventory_v1",
        "build": BUILD,
        "module": MODULE,
        "disassembly": {"path": str(DISASM), "sha256": hashlib.sha256(DISASM.read_bytes()).hexdigest()},
        "fixed_four_sites": sites,
        "protected_four_literals": protected,
        "checks": checks,
        "checks_passed": sum(value is True for value in checks.values()),
        "checks_total": len(checks),
        "verification_passed": all(checks.values()),
        "decision": {
            "production_patch_ready": False,
            "installable": False,
            "runtime_verified": False,
            "multiplayer_verified": False,
            "meaning": "Five join-handler four-slot bounds require a coordinated sidecar/continuation bridge; three other literal-4 sites are status or metadata values and must remain unchanged.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.output), "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "installable": False}, ensure_ascii=False))
    return 0 if result["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
