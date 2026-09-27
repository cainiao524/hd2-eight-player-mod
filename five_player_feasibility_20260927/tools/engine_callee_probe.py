"""Offline plan by default; a separate authorized capture reads four code ranges.

Imports the previously reviewed Windows reader. No automatic process discovery,
launch, pointer following, escalation, patching, or game function invocation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import interface_probe as base

FIRST_CAPTURE_SHA = "a45e5f5b1647d808b8b7716fd750e4a894ab39a3021b52a0b10c404403a8b85f"
CALLER_PINS = (
    (0x3494B0, 256, "d52d364307cb57a442cc6295a48d840458caf81de9da0ac9e40cb72083d9b144"),
    (0x8C6730, 256, "14e69e3aaea1ffc9bc04ed88cbf0ac1be6887485f65b5330006c0c06e6520720"),
)
RANGE_SIZE = 4096
TARGETS = (
    (0x4ACDE0, 0x34952A, "API +0x30/+0x18; entry integers forwarded as arguments 6 and 7"),
    (0x349110, 0x34953C, "API +0x30/+0x18; receives prior call result as argument 2"),
    (0x8CCFA0, 0x8C67AD, "API +0xf8/+0xa0; obtains object later receiving entry integer"),
    (0x8E1370, 0x8C67C2, "API +0xf8/+0xa0; receives entry integer as argument 2"),
)


def verify_callers(reader, exe_base):
    for rva, size, expected in CALLER_PINS:
        raw = reader.read(exe_base + rva, size, executable=True)
        base.require(len(raw) == size and base.digest(raw) == expected,
                     "Previously captured EXE caller changed at " + hex(rva))


def observe_callees(reader, exe):
    records = []
    # All addresses are fixed, previously decoded direct-call destinations.
    # Read no call destinations discovered during this new observation.
    for rva, call_site, purpose in TARGETS:
        base.require(0 <= rva and rva + RANGE_SIZE <= exe["size"], "Range exceeds EXE image")
        raw = reader.read(exe["base"] + rva, RANGE_SIZE, executable=True)
        base.require(len(raw) == RANGE_SIZE, "Short callee read")
        records.append({"rva": hex(rva), "size": RANGE_SIZE,
            "entry_basis": {"saved_direct_call_site_rva": hex(call_site), "purpose": purpose},
            "bytes": raw.hex(), "sha256": base.digest(raw)})
    for record in records:
        again = reader.read(exe["base"] + int(record["rva"], 16), RANGE_SIZE, executable=True)
        base.require(len(again) == RANGE_SIZE, "Short callee reread")
        record["reread_sha256"] = base.digest(again)
        record["unchanged_on_reread"] = record["reread_sha256"] == record["sha256"]
        if not record["unchanged_on_reread"]:
            record["reread_bytes"] = again.hex()
    return {"ranges": records, "all_ranges_unchanged_on_reread": all(
        record["unchanged_on_reread"] for record in records),
        "atomic_snapshot": False, "eight_player_verified": False,
        "limitations": ["Each range is a bounded prefix, not a verified complete function.",
            "A range can include following functions or data; decode only from established entries.",
            "Unchanged rereads do not exclude changes between observations.",
            "No heap data, service response, callback registry, or multiplayer gameplay is observed."]}


def plan():
    return {"mode": "offline_plan", "build": base.BUILD,
        "prior_capture_sha256": FIRST_CAPTURE_SHA,
        "ranges": [{"exe_rva": hex(r), "size": RANGE_SIZE, "call_site_rva": hex(c)}
                   for r, c, _ in TARGETS],
        "caller_pin_rvas": [hex(r) for r, _, _ in CALLER_PINS],
        "each_range_read_twice": True,
        "expected_memory_bytes": 50400, "hard_read_budget": base.READ_BUDGET,
        "opens_process": False, "requires_separate_capture_authorization": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--capture", action="store_true")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.capture:
        base.require(args.pid is None and args.output is None, "PID/output require --capture")
        print(json.dumps(plan(), indent=2))
        return
    base.require(args.pid is not None and args.output is not None,
                 "Capture requires explicit --pid and new --output")
    base.require(not args.output.exists(), "Refusing to overwrite output")
    reader = base.WindowsReader(args.pid)
    try:
        executable = reader.executable()
        modules = reader.modules()
        selected = base.check_files(modules, executable)
        base.verify_loaded(reader, selected)
        exe = selected["helldivers2.exe"]
        verify_callers(reader, exe["base"])
        report = observe_callees(reader, exe)
        verify_callers(reader, exe["base"])
        base.verify_loaded(reader, selected)
        base.require(reader.executable() == executable and reader.modules() == modules,
                     "Process image/module list changed")
        base.require(base.check_files(modules, executable) == selected, "Disk identity changed")
        report.update({"schema_version": 1, "purpose": "four EXE direct-callee prefixes",
            "build": base.BUILD, "pid": args.pid, "utc": datetime.now(timezone.utc).isoformat(),
            "prior_capture_sha256": FIRST_CAPTURE_SHA, "pinned_images": selected,
            "memory_bytes_read": reader.used, "runtime_capture": True,
            "utility_file_sha256_at_output": base.digest(Path(__file__).read_bytes()),
            "reader_file_sha256_at_output": base.digest(Path(base.__file__).read_bytes())})
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        print(str(args.output.resolve()))
    finally:
        reader.close()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print("Stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
