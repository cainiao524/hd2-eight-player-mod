"""Replay the platform member buffer and adjacent live fields, offline only."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research_handoff_20260927" / "indirect"))
from inspect_capture import EXPECTED, Image, require, row

PINS = {
    "enumeration_and_buffer": [
        0x1092E66, 0x1092E78, 0x1092E8C, 0x1092E93,
        0x1092ECB, 0x1092ED0, 0x1092EDC, 0x1092EEB,
        0x1092F0A, 0x1092F12, 0x1092F14, 0x1092F1A,
        0x1092F2A, 0x1092F31, 0x1092F42, 0x1092F45,
        0x10937CB, 0x1093C91, 0x1093C96, 0x1093CA9,
        0x1093CB0, 0x1093CCB, 0x1093CFE, 0x1093D06,
        0x1093D17, 0x1093D1E, 0x1093D32,
    ],
    "adjacent_fields_are_in_use": [
        0x1091997, 0x1091AC7, 0x1091ACD, 0x1091AED, 0x1091AF7,
        0x1092F4B, 0x1092F4E, 0x1092F53, 0x1092F55, 0x1092F57,
        0x1093E2D, 0x1093E2F, 0x1093E31, 0x1093E34,
        0x1093C49, 0x109411D, 0x1094133,
    ],
    "count_driven_buffer_consumers": [
        0x10935A7, 0x109361F, 0x1093630, 0x1093648,
        0x1093652, 0x109367A, 0x1093694, 0x1093696, 0x109369A,
        0x1093DA8, 0x1093DBA, 0x1093DD1, 0x1093E1C, 0x1093E1F, 0x1093E23,
        0x1094381, 0x10943A4, 0x10943C9, 0x1094428, 0x109442B,
    ],
    "owner_embedding_and_direct_initialization": [
        0x134D754, 0x134D75B, 0x134D75D, 0x134D791,
        0x134D7AE, 0x134D7BC, 0x134D7C2, 0x134D7DD,
        0x134E40F, 0x134E443, 0x134E44A, 0x134E44F, 0x134E459,
        0x108F068, 0x108F06F, 0x108F072, 0x108F078,
        0x108F108, 0x108F188, 0x108F18F,
        0x13F7858, 0x13F7883, 0x13F788A,
    ],
}


def build(im):
    groups = {}
    for name, addresses in PINS.items():
        groups[name] = []
        for address in addresses:
            ins = im.instruction(address)
            require(ins is not None, f"Unproven instruction boundary {address:#x}")
            groups[name].append({**row(ins), "root": hex(im.root(address)[0])})
    base, stride, first_adjacent = 0x1B58, 8, 0x1B78
    require(base + 4 * stride == first_adjacent, "Layout arithmetic mismatch")
    require(0x1D470 + first_adjacent == 0x1EFE8, "Owner alias mismatch")
    return {
        "source_file_sha256": EXPECTED,
        "capture_identity_sha256": im.report["capture_sha256"],
        "build_id": im.report["build_id"],
        "runtime_verified": False,
        "pins": groups,
        "layout": {
            "member_buffer_base": hex(base), "member_stride": stride,
            "existing_capacity_before_adjacent_used_field": 4,
            "count_field": "0x1bb0", "first_adjacent_used_field": hex(first_adjacent),
            "hypothetical_fifth_write": ["0x1b78", "0x1b80"],
            "hypothetical_eight_buffer_end_exclusive": hex(base + 8 * stride),
            "main_owner_platform_offset": "0x1d470",
            "main_owner_fifth_write_start": "0x1efe8",
            "secondary_path": {
                "main_owner_component_offset": "0x171c8",
                "component_platform_offset": "0x1c00",
                "derived_main_owner_platform_offset": hex(0x171C8 + 0x1C00),
            },
        },
        "limits": [
            "The fifth write is a consequence of changing the current limit while preserving the observed layout; it was not executed.",
            "Repeated offsets elsewhere are candidates only; the pinned bases are established by entry arguments and direct caller dataflow.",
            "Count-driven consumers do not prove all other consumers support eight entries.",
            "This does not resolve platform API names, service responses, entity creation, or eight-player gameplay.",
            "No installed game file or live process is modified or read by this script.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Refusing overwrite")
    result = build(Image(args.evidence))
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"output": str(args.output),
        "pinned_sites": len({r["rva"] for group in result["pins"].values() for r in group})}))


if __name__ == "__main__":
    main()
