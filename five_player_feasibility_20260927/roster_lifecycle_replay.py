"""Bounded static replay of the build-25480438 roster lifecycle.

Reads the pinned code capture only; no game process or installed files.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research_handoff_20260927" / "indirect"))
from inspect_capture import EXPECTED, Image, require, row, scan  # noqa: E402


PINS = {
    "owner_layout_and_registry": [
        0x5565EF, 0x5565F9, 0x5565FE, 0x556605,
        0x55660A, 0x556611, 0x568EC8, 0x568ECF,
        0xB27564, 0xB27568, 0xB2756F, 0xB27577,
        0xB27581, 0xB27592,
    ],
    "inline_insert_b": [
        0x540850, 0x540856, 0x540863, 0x54086A, 0x54086E,
        0x540871, 0x540873, 0x54088F, 0x5408CB,
        0x5408FB, 0x540912,
    ],
    "inline_insert_a": [
        0x540920, 0x54092A, 0x540934, 0x54093A, 0x54093C,
        0x54093F, 0x540941, 0x540968, 0x540984,
        0x540988, 0x5409CA, 0x5409D1, 0x540A01,
        0x540A0D, 0x540A24,
    ],
    "shared_relocate": [
        0x60C410, 0x60C438, 0x60C440, 0x60C44B,
        0x60C463, 0x60C4C0, 0x60C4C9, 0x60C4D1,
        0x60C4D9, 0x60C4E5, 0x60C50D, 0x60C516,
        0x60C51F, 0x60C528, 0x60C531, 0x60C53A,
        0x60C5B7,
    ],
    "compact_from_extra_to_dense": [
        0x60CC70, 0x60CC7A, 0x60CC83, 0x60CC8B,
        0x60CC91, 0x60CCB5, 0x60CCC3, 0x60CCCA,
        0x60CCD6, 0x60CD46, 0x60CD56,
        0x60CD90, 0x60CD99, 0x60CDA1, 0x60CDAA,
        0x60CE54,
    ],
    "remove_and_integrate": [
        0x540A40, 0x540A49, 0x540A57, 0x540AA4,
        0x540AC1, 0x540AD5,
        0x60CEA0, 0x60CEAA, 0x60CEBE, 0x60CEC3,
        0x60CED4, 0x60CEEB, 0x60CF0E,
        0x60CF22, 0x60CF2B, 0x60CF3A,
        0x57E00F, 0x57E01C, 0x57E024,
    ],
}

TARGETS = {
    0x60CA80, 0x60CBA0, 0x540850, 0x540920,
    0x540A40, 0x60CEA0, 0x60CC70, 0xB27560,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    image = Image(args.evidence)
    pins = {}
    for name, addresses in PINS.items():
        pins[name] = []
        for address in addresses:
            ins = image.instruction(address)
            require(ins is not None, f"unwind-validated instruction absent: {address:#x}")
            pins[name].append({**row(ins), "root": hex(image.root(address)[0])})

    xrefs = scan(image, TARGETS)
    for target in (0x60CA80, 0x60CBA0, 0x540850, 0x540920,
                   0x540A40, 0x60CEA0):
        hits = xrefs["targets"][hex(target)]
        require(not hits["branches"] and not hits["rip_references"]
                and not hits["absolute_pointers"],
                f"known callback gap changed at {target:#x}")
        require(all(hit["range"] == "unwind" for hit in hits["rva_literals"]),
                f"non-unwind RVA literal appeared at {target:#x}")

    start, next_start = 0xEA0818, 0xEA0C40
    regions = [
        {"name": "pointers", "offset": 0xE8, "count": 4, "stride": 8},
        {"name": "record_70", "offset": 0x108, "count": 4, "stride": 0x70},
        {"name": "record_38", "offset": 0x2C8, "count": 4, "stride": 0x38},
        {"name": "record_20", "offset": 0x3A8, "count": 4, "stride": 0x20},
    ]
    for region in regions:
        region["end_exclusive"] = hex(region["offset"] + region["count"] * region["stride"])
        region["offset"] = hex(region["offset"])
        region["stride"] = hex(region["stride"])
    require(next_start - start == 0x428, "adjacent owner layout changed")
    require([x["end_exclusive"] for x in regions]
            == ["0x108", "0x2c8", "0x3a8", "0x428"],
            "parallel array boundary changed")
    result = {
        "source_sha256": EXPECTED,
        "capture_sha256": image.report["capture_sha256"],
        "game_sha256": image.report["game_sha256"],
        "build_id": image.report["build_id"],
        "runtime_verified": image.report["runtime_verified"],
        "pins": pins,
        "entry_xrefs": xrefs["targets"],
        "layout": {
            "owner_roster_start": hex(start),
            "next_owner_subobject": hex(next_start),
            "gap": "0x428",
            "parallel_arrays": regions,
            "contiguous_eight_slot_layout_if_repacked": {
                "pointer_start": "0xe8", "record_70_start": "0x128",
                "record_38_start": "0x4a8", "record_20_start": "0x668",
                "next_object_start": "0x768",
                "owner_next_subobject_shifted_to": "0xea0f80",
            },
        },
        "limits": [
            "Two insertion implementations at 0x540850/0x540920 are statically analogous to 0x60CBA0/0x60CA80, and all four use the same roster global; this does not prove which execute at runtime.",
            "No identified direct branch, RIP reference, or absolute pointer targets the four insertion entries in the captured image. Their 32-bit RVA literals occur only in captured unwind records. Indirect, computed, and runtime-created dispatch remain possible.",
            "0xB27560 registers the roster object pointer under tag 0x69; it does not expose an insertion callback address in the inspected code.",
            "The 0x60C410 mover and 0x60CC70 compactor operate on four parallel fixed-layout arrays. A contiguous eight-slot repack would move every subsequent owner member; it is an illustrative layout calculation, not a patch recipe.",
            "No writable image data, heap, installed game execution, or live process data were accessed.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
