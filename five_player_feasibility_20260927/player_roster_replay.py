"""Replay bounded, read-only evidence for the four-entry player roster.

This reads only the fingerprinted build 25480438 capture. It does not execute
the game, access the live process, or modify installed game files.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research_handoff_20260927" / "indirect"))
from inspect_capture import EXPECTED, Image, require, row  # noqa: E402


PINS = {
    "owner_construct_and_publish": [
        0x551B7D, 0x5565EF, 0x5565F9, 0x5565FE, 0x556605,
        0x568EC8, 0x568ECF,
    ],
    "subobject_constructor": [
        0x60C9C0, 0x60C9CA, 0x60C9E8, 0x60C9EF, 0x60CA10,
    ],
    "roster_insert_a_guard_and_fields": [
        0x60CA8A, 0x60CA94, 0x60CA9A, 0x60CA9C, 0x60CA9F,
        0x60CAA1, 0x60CAAC, 0x60CAB0, 0x60CADC, 0x60CAE5,
        0x60CAE9, 0x60CB2B, 0x60CB32, 0x60CB62, 0x60CB68,
        0x60CB6E, 0x60CB74, 0x60CB77, 0x60CB7B, 0x60CB85,
    ],
    "roster_insert_b_guard_and_fields": [
        0x60CBA6, 0x60CBB0, 0x60CBB7, 0x60CBBB, 0x60CBBE,
        0x60CBC0, 0x60CBC8, 0x60CBD5, 0x60CBDC,
        0x60CC14, 0x60CC18, 0x60CC48, 0x60CC5F,
    ],
    "roster_compaction_and_gameplay_consumer": [
        0x60CC7A, 0x60CC83, 0x60CCB5, 0x60CCC3, 0x60CE54,
        0x60CE6A, 0xACC620, 0xACC622, 0xACC638,
    ],
    "capacity_diagnostic_connection": [
        0x56E7DE, 0x56E7EC,
    ],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    image = Image(args.evidence)

    # 0x60C9C0 is a short leaf with no captured unwind entry. Its entry is
    # established by the unwind-validated direct call at 0x5565F9.
    ctor_start, ctor_length = 0x60C9C0, 0xA5
    constructor = {
        ins.address: ins
        for ins in image.md.disasm(image.read(ctor_start, ctor_length), ctor_start)
    }
    require(constructor[0x60CA64].mnemonic == "ret", "leaf end changed")
    pins = {}
    for group, addresses in PINS.items():
        pins[group] = []
        for address in addresses:
            leaf = ctor_start <= address <= 0x60CA64
            instruction = constructor.get(address) if leaf else image.instruction(address)
            require(instruction is not None, f"instruction boundary absent: {address:#x}")
            pin = row(instruction)
            pin["root"] = hex(ctor_start if leaf else image.root(address)[0])
            pin["boundary_validation"] = (
                "known direct-call leaf entry; no captured unwind"
                if leaf else "captured unwind fragment"
            )
            pins[group].append(pin)

    # The four qword slots end immediately before +0x108, which is accessed
    # as the first 0x70-stride auxiliary record in both insertions.
    slots = [0xE8 + 8 * i for i in range(4)]
    require(slots == [0xE8, 0xF0, 0xF8, 0x100], "slot layout changed")
    require(slots[-1] + 8 == 0x108, "adjacent record offset changed")
    require(0xEA0894 - 0xEA0818 == 0x7C, "diagnostic owner offset changed")
    result = {
        "source_sha256": EXPECTED,
        "capture_sha256": image.report["capture_sha256"],
        "game_sha256": image.report["game_sha256"],
        "build_id": image.report["build_id"],
        "runtime_verified": image.report["runtime_verified"],
        "pins": pins,
        "derived_layout": {
            "global_rva": "0x3326468",
            "owner_subobject_offset": "0xea0818",
            "guarded_tracked_count_offset": "0x80",
            "gameplay_consumed_dense_count_offset": "0x84",
            "high_water_count_offset": "0x7c",
            "pointer_slot_offsets": [hex(x) for x in slots],
            "next_auxiliary_record_start": "0x108",
            "diagnostic_owner_field_offset": "0xea0894",
        },
        "limits": [
            "The two insertion functions test tracked_count + 1 <= 4 before indexed stores.",
            "The >4 path contains a write to virtual address zero, followed by linear fallthrough; on ordinary Windows process memory this would fault. Its source-level assertion macro is unknown.",
            "The +0xE8 pointer array has four qword positions before a distinct +0x108 0x70-stride record; merely changing the comparison cannot make a fifth pointer safe.",
            "This proves a four-entry roster insertion layout, not a four-object entity heap allocator or platform/backend lobby capacity.",
            "Direct-call xref scanning found no callers of 0x60CA80/0x60CBA0; indirect and computed references, uncovered leaf callers, and dynamic runtime dispatch remain unexamined.",
            "The installed game and any runtime platform interface were not accessed; runtime_verified is false.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
