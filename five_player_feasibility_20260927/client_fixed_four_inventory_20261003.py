"""Replay the fixed-build client confirmed-peer four-slot inventory.

This is an offline, fail-closed audit over the already saved client layout and
index scans.  It turns the previously bounded ``client_expansion_inventory``
into a small contract that names the fixed-four readers/writers and their
append, remove, reset, kicked and host-migration call sites.  It deliberately
does not infer a player index from an offset, emit bytes, open a process or
claim that a sidecar is installable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
BUILD = 25480438
CAPTURE_SHA256 = "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8"
INVENTORY = HERE / "client_expansion_inventory_v2.json"
LAYOUT_SCAN = HERE / "protocol_client_layout_scan_extended.json"
INDEX_SCAN = HERE / "client_expansion_index_scan.json"
EXPECTED_LAYOUT = [
    {"count_offset": "0x10", "base_offset": "0x18", "stride": 8, "next_field_offset": "0x38", "in_object_capacity": 4},
    {"count_offset": "0x38", "base_offset": "0x40", "stride": 16, "next_field_offset": "0x80", "in_object_capacity": 4},
    {"count_offset": "0x80", "base_offset": "0x88", "stride": 16, "next_field_offset": "0xC8", "in_object_capacity": 4},
    {"count_offset": "0xC8", "base_offset": "0xD0", "stride": 32, "next_field_offset": "0x150", "in_object_capacity": 4, "record_player_index_offset": "0x14"},
    {"count_offset": None, "base_offset": "0x150", "stride": 16, "next_field_offset": None, "observed_loop_end_exclusive": "0x190", "in_object_capacity": 4},
]
REQUIRED_GROUPS = {
    "owner_constructor",
    "client_constructor_alternate",
    "confirmed_peer_append_registry",
    "confirmed_peer_append_direct",
    "confirmed_peer_remove_and_neighbor_arrays",
    "client_reset_primary",
    "client_reset_secondary",
    "kicked_path_and_host_migration_handoff",
    "client_adjacent_peer_keyed_array",
}
REQUIRED_ANCHORS = {
    "confirmed_peer_append_registry": {
        "0xb90b98": "[rbx + 0xc8]",
        "0xb90c03": "[rbx + 0xc8], eax",
        "0xb90c12": "[rdx + 0x14], eax",
    },
    "confirmed_peer_append_direct": {
        "0x10872f1": "[rcx + 0xc8]",
        "0x108734c": "[rdi + 0xc8], eax",
        "0x108736a": "[rdx + 0x14], eax",
    },
    "confirmed_peer_remove_and_neighbor_arrays": {
        "0x1087612": "dec dword ptr [rbx + 0xc8]",
        "0x1087626": "+ rbx + 0xd0",
        "0x108763e": "+ rbx + 0xe0",
        "0x1087730": "cmp eax, 4",
    },
    "client_reset_primary": {
        "0x10849ed": "[rdi + 0xc8], r12d",
        "0x10849f7": "[rdi + 0xd0]",
    },
    "client_reset_secondary": {
        "0x1087251": "[r15 + 0xc8], r13d",
        "0x1087260": "[r15 + 0xd0]",
    },
    "client_adjacent_peer_keyed_array": {
        "0x1084f83": "cmp edx, 4",
        "0x1084f8e": "mov qword ptr [rax], rbx",
        "0x1084f95": "mov dword ptr [rax + 0xc], r8d",
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _group_map(doc: dict) -> dict[str, dict[str, dict]]:
    groups = {}
    for group in doc.get("operation_groups", []):
        groups[group["name"]] = {str(row["rva"]).lower(): row for row in group.get("anchors", [])}
    return groups


def _scan_rows(doc: dict) -> dict[str, dict]:
    rows = {}
    for row in doc.get("hits", []):
        if isinstance(row, dict) and isinstance(row.get("rva"), str):
            rows[row["rva"].lower()] = row
    return rows


def build_inventory() -> dict:
    for path in (INVENTORY, LAYOUT_SCAN, INDEX_SCAN):
        if not path.is_file():
            raise FileNotFoundError(path)
    base = _load(INVENTORY)
    layout_scan = _load(LAYOUT_SCAN)
    index_scan = _load(INDEX_SCAN)
    if base.get("capture_sha256") != CAPTURE_SHA256:
        raise ValueError("client_inventory_capture_identity_changed")
    if layout_scan.get("capture_sha256") != CAPTURE_SHA256 or index_scan.get("capture_sha256") != CAPTURE_SHA256:
        raise ValueError("client_scan_capture_identity_changed")

    source_hashes = {}
    for source in base.get("source_scans", []):
        source_path = HERE / Path(str(source["path"])).name
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        observed = _sha256(source_path)
        if observed != source.get("sha256"):
            raise ValueError(f"source_scan_hash_changed:{source_path.name}")
        source_hashes[source_path.name] = observed

    layout = base.get("client_layout")
    if not isinstance(layout, list) or len(layout) != len(EXPECTED_LAYOUT):
        raise ValueError("client_layout_shape_changed")
    for index, expected in enumerate(EXPECTED_LAYOUT):
        actual = layout[index]
        for key, value in expected.items():
            if actual.get(key) != value:
                raise ValueError(f"layout_contract_changed:{index}:{key}")

    groups = _group_map(base)
    missing_groups = sorted(REQUIRED_GROUPS - set(groups))
    if missing_groups:
        raise ValueError(f"missing_operation_groups:{missing_groups}")
    anchor_rows = []
    for group_name, required in REQUIRED_ANCHORS.items():
        rows = groups[group_name]
        for rva, fragment in required.items():
            row = rows.get(rva)
            if row is None:
                raise ValueError(f"missing_client_anchor:{group_name}:{rva}")
            asm = str(row.get("asm", ""))
            if fragment.lower() not in asm.lower():
                raise ValueError(f"client_anchor_asm_changed:{group_name}:{rva}")
            if not isinstance(row.get("sha256"), str) or len(row["sha256"]) != 64:
                raise ValueError(f"client_anchor_hash_missing:{group_name}:{rva}")
            anchor_rows.append({
                "group": group_name,
                "rva": rva,
                "asm": asm,
                "sha256": row["sha256"],
                "role": "reader_or_writer" if "mov" in asm.lower() or "cmp" in asm.lower() or "dec" in asm.lower() else "boundary",
            })

    # The two immediate guards are instruction-boundary rows in the bounded
    # inventory, while the displacement scans intentionally omit immediates.
    # Validate them from the same hashed anchor rows rather than treating a
    # missing displacement hit as evidence that the guard disappeared.
    if groups["confirmed_peer_remove_and_neighbor_arrays"].get("0x1087730", {}).get("asm") != "cmp eax, 4":
        raise ValueError("remove_neighbor_four_guard_missing")
    if groups["client_adjacent_peer_keyed_array"].get("0x1084f83", {}).get("asm") != "cmp edx, 4":
        raise ValueError("peer_keyed_four_guard_missing")

    checks = {
        "fixed_build": BUILD == 25480438,
        "capture_identity": base.get("capture_sha256") == CAPTURE_SHA256,
        "source_scan_hashes": len(source_hashes) == 2,
        "five_four_slot_layouts": len(layout) == 5 and all(row.get("in_object_capacity") == 4 for row in layout),
        "append_readers_and_writers_pinned": all(name in groups for name in ("confirmed_peer_append_registry", "confirmed_peer_append_direct")),
        "remove_and_neighbor_cleanup_pinned": "confirmed_peer_remove_and_neighbor_arrays" in groups,
        "reset_paths_pinned": all(name in groups for name in ("client_reset_primary", "client_reset_secondary")),
        "kicked_and_migration_handoff_pinned": "kicked_path_and_host_migration_handoff" in groups,
        "explicit_four_guards_pinned": True,
        "no_installable_patch_emitted": True,
    }
    return {
        "schema": "hd2_client_fixed_four_inventory_v1",
        "build": BUILD,
        "module": "game.dll",
        "capture_sha256": CAPTURE_SHA256,
        "source_scans": source_hashes,
        "layout_contract": layout,
        "fixed_four_sites": anchor_rows,
        "operation_groups": sorted(REQUIRED_GROUPS),
        "coverage": {
            "confirmed_peer_append": True,
            "confirmed_peer_remove_and_neighbor_arrays": True,
            "client_reset": True,
            "kicked_path": True,
            "host_migration_handoff": True,
            "player_index_semantics": False,
            "client_creation_gate": False,
            "runtime_callbacks": False,
            "cleanup_abi": False,
        },
        "checks": checks,
        "checks_passed": sum(value is True for value in checks.values()),
        "checks_total": len(checks),
        "verification_passed": all(checks.values()),
        "decision": {
            "production_patch_ready": False,
            "installable": False,
            "runtime_verified": False,
            "multiplayer_verified": False,
            "meaning": "Five client-owned four-slot arrays and their append/remove/reset paths are pinned. A sidecar still needs index semantics, callback/cleanup ABI, allocation lifetime and client runtime evidence.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = build_inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"schema": result["schema"], "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "installable": False}, ensure_ascii=False))
    return 0 if result["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
