"""Audit the four-slot MenuScreenLoadout layout from the pinned capture.

This is an offline relocation audit.  It does not read a live process or emit
patch bytes.  The screen owns several independent four-entry structures, so a
capacity change must either relocate all of them together or use an explicitly
versioned sidecar.  The report records the address arithmetic and keeps the
production gates closed until every reader, writer, destructor and callback is
bound.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = 25480438
CAPTURE_SHA = "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8"
REPORT_SHA = "132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5"
DATA_SHA = "31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d"


def check(rows: list[dict], name: str, passed: bool, detail: object) -> None:
    rows.append({"name": name, "passed": bool(passed), "detail": detail})


def group_map(evidence: dict) -> dict[str, dict]:
    return {g.get("name", ""): g for g in evidence.get("groups", [])}


def anchor_map(group: dict) -> dict[str, dict]:
    return {x.get("rva", "").lower(): x for x in group.get("anchors", [])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", type=Path, default=ROOT / "index_slot_mapping_evidence_v2.json")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    checks: list[dict] = []

    source = evidence.get("source_sha256", {})
    check(checks, "fixed_build_source_report", source.get("capture-report.json") == REPORT_SHA, source.get("capture-report.json"))
    check(checks, "fixed_build_source_data", source.get("captured-data.bin") == DATA_SHA, source.get("captured-data.bin"))
    check(checks, "capture_identity", evidence.get("capture_identity_sha256") == CAPTURE_SHA, evidence.get("capture_identity_sha256"))

    groups = group_map(evidence)
    expected_groups = {
        "screen_identity_and_registration",
        "allocation_and_four_element_construction",
        "mapping_reset_and_local_slot_zero",
        "network_index_to_loadout_slot_consumer",
        "mapping_assignment_during_roster_update",
        "mapping_assignment_registered_event",
        "four_slot_release_and_transition",
        "subobject_ui_behavior",
        "separate_network_index_records_in_same_screen",
    }
    check(checks, "all_layout_groups_present", expected_groups.issubset(groups), sorted(set(expected_groups) - set(groups)))
    check(checks, "all_layout_groups_have_anchors", all(groups[n].get("anchors") for n in expected_groups if n in groups),
          {n: len(groups.get(n, {}).get("anchors", [])) for n in sorted(expected_groups)})

    layout = evidence.get("layout", {})
    def integer(name: str) -> int | None:
        value = layout.get(name)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value, 0)
            except ValueError:
                return None
        return None

    forward = integer("forward_map")
    inverse = integer("inverse_map")
    flags = integer("next_flags")
    count = integer("entries_per_map")
    record_base = integer("indexed_record_base")
    record_stride = integer("indexed_record_stride")
    record_count = integer("indexed_record_count")
    record_end = integer("indexed_records_end_exclusive")
    widget_base = integer("slot_widget_base")
    widget_stride = integer("slot_widget_stride")
    widget_count = integer("constructed_slots")
    widget_end = integer("slots_end_exclusive")
    next_widget = integer("next_widget_base")
    allocation = integer("allocation_size_argument")
    values_ok = all(v is not None for v in (forward, inverse, flags, count, record_base, record_stride,
                                             record_count, record_end, widget_base, widget_stride,
                                             widget_count, widget_end, next_widget, allocation))
    check(checks, "layout_integer_fields", values_ok, layout)

    if values_ok:
        check(checks, "original_maps_contiguous", forward + count * 4 == inverse and inverse + count * 4 == flags,
              {"forward_end": hex(forward + count * 4), "inverse": hex(inverse), "inverse_end": hex(inverse + count * 4), "flags": hex(flags)})
        check(checks, "original_records_end_matches", record_base + record_stride * record_count == record_end,
              {"computed": hex(record_base + record_stride * record_count), "captured": hex(record_end)})
        check(checks, "original_widgets_end_matches_next", widget_base + widget_stride * widget_count == widget_end == next_widget,
              {"computed": hex(widget_base + widget_stride * widget_count), "next": hex(next_widget)})
        check(checks, "original_four_slot_layout", count == record_count == widget_count == 4,
              {"map_entries": count, "record_count": record_count, "widget_count": widget_count})
        check(checks, "index_four_forward_overlaps_inverse", forward + 4 * 4 == inverse,
              {"index_4_forward": hex(forward + 4 * 4), "inverse": hex(inverse)})
        check(checks, "index_four_reverse_overlaps_flags", inverse + 4 * 4 == flags,
              {"index_4_reverse": hex(inverse + 4 * 4), "flags": hex(flags)})

        eight_record_end = record_base + record_stride * 8
        relocated_forward = eight_record_end
        relocated_inverse = relocated_forward + 8 * 4
        relocated_flags = relocated_inverse + 8 * 4
        eight_widget_end = widget_base + widget_stride * 8
        inline_delta = eight_widget_end - next_widget
        required_allocation = allocation + inline_delta
        relocation = {
            "eight_entries": 8,
            "records": {"base": hex(record_base), "stride": hex(record_stride), "end_exclusive": hex(eight_record_end)},
            "maps_after_records": {"forward": hex(relocated_forward), "inverse": hex(relocated_inverse), "flags": hex(relocated_flags)},
            "widgets": {"base": hex(widget_base), "stride": hex(widget_stride), "end_exclusive": hex(eight_widget_end)},
            "old_next_widget": hex(next_widget),
            "inline_next_widget_overlap_bytes": inline_delta,
            "minimum_inline_allocation_if_following_object_moves": hex(required_allocation),
            "sidecar_required_if_object_size_stays": True,
        }
        check(checks, "eight_records_do_not_overlap_relocated_maps", eight_record_end <= relocated_forward,
              {"records_end": hex(eight_record_end), "map_base": hex(relocated_forward)})
        check(checks, "eight_widgets_overlap_original_next_object", eight_widget_end > next_widget,
              {"eight_widget_end": hex(eight_widget_end), "original_next": hex(next_widget), "overlap_bytes": inline_delta})
        check(checks, "inline_relocation_requires_size_or_sidecar", required_allocation > allocation and inline_delta > 0,
              {"original_allocation": hex(allocation), "required_allocation": hex(required_allocation), "delta": hex(inline_delta)})
    else:
        relocation = {"error": "layout fields are not all integer-compatible"}

    required_anchors = {
        "0x14a17f4": "mov edi, 4",
        "0xb9014b": "cmp ecx, 4",
        "0xb9014e": "jae 0xb90168",
        "0x146c3d1": "cmp r15, 4",
        "0x146c3d5": "jae 0x146d30b",
        "0xb901e1": "cmp r8d, 4",
        "0xb901e5": "jae 0xb90241",
        "0x146d2c0": "cmp ebp, 4",
        "0x1470b4f": "mov edi, 4",
        "0x146fde6": "cmp ebx, 4",
        "0x146fde9": "jae 0x147057e",
    }
    all_anchors = {a.get("rva", "").lower(): a for g in groups.values() for a in g.get("anchors", [])}
    anchor_checks = {}
    for rva, asm in required_anchors.items():
        row = all_anchors.get(rva)
        passed = row is not None and row.get("asm") == asm
        anchor_checks[rva] = {"expected": asm, "observed": None if row is None else row.get("asm")}
        check(checks, f"anchor_{rva}", passed, anchor_checks[rva])

    report = {
        "schema": "hd2_loadout_layout_relocation_audit_v1",
        "build": BUILD,
        "source_evidence": args.evidence.name,
        "capture_identity_sha256": evidence.get("capture_identity_sha256"),
        "checks": checks,
        "checks_passed": sum(x["passed"] for x in checks),
        "checks_total": len(checks),
        "verification_passed": all(x["passed"] for x in checks),
        "layout": layout,
        "relocation_model": relocation,
        "capacity_anchors": anchor_checks,
        "decision": {
            "production_patch_ready": False,
            "installable": False,
            "multiplayer_verified": False,
            "reason": "Loadout screen owns four independent network-index records, two four-entry maps and four large widgets. An inline 4-to-8 conversion overlaps adjacent fields/objects; a sidecar still needs every reader, writer, callback, destructor, UI and reconnect ABI.",
            "next_required": [
                "Bind all captured loadout readers/writers and indirect callbacks to one eight-slot owner or sidecar layout.",
                "Recover constructor, transition, destructor and package-lifetime ABI before generating patch bytes.",
                "Validate fifth-peer UI state on host and client after confirmed-peer and player creation are real.",
            ],
        },
        "runtime_verified": False,
        "live_process_accessed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.output), "checks_passed": report["checks_passed"], "checks_total": report["checks_total"], "verification_passed": report["verification_passed"], "production_patch_ready": False}, ensure_ascii=False))
    return 0 if report["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
