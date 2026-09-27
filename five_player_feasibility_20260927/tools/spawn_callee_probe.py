"""Offline plan for a fixed, previously observed direct callee prefix.

Only a separately authorized --capture --pid N --output NEW.json can open a
process. No process discovery, launch, writes, function calls, retries, or
following newly observed pointers, branches, jump thunks, or callees.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import interface_probe as base

PRIOR_CAPTURE_SHA = "44773c271226df2df3a93991421287cee71ea7971cbad877ed5a70275dff798a"
CALLER_RVA, CALLER_SIZE = 0x30FF50, 34
CALLER_SHA = "387a2d5d4cd5499df56722eb328d0fe917218678c625847078962f83c6e4ffa9"
CALL_SITE_RVA, TARGET_RVA, CODE_BYTES = 0x30FF66, 0x1AE380, 4096
USER_END = 0x800000000000
READ_COMPONENTS = {
    "pe_header_pages": 2 * 2 * 4096,
    "previous_game_code_pins": 2 * sum(size for _, size, _ in base.PINS),
    "wrapper_caller_pin": 2 * CALLER_SIZE,
    "target_code_prefix": 2 * CODE_BYTES,
}
EXPECTED_MEMORY_BYTES = sum(READ_COMPONENTS.values())


def bounded_address(address, size):
    base.pointer(address)
    base.require(0 < size <= 4096 and address + size <= USER_END,
                 "Read range overflows user address space")
    return address


class BudgetReader:
    """Enforce this observation's exact budget around the unchanged adapter."""

    def __init__(self, adapter):
        self.adapter, self.used = adapter, 0

    def read(self, address, size, executable=False):
        bounded_address(address, size)
        base.require(self.used + size <= EXPECTED_MEMORY_BYTES,
                     "Spawn callee read budget exceeded")
        self.used += size
        raw = self.adapter.read(address, size, executable=executable)
        base.require(len(raw) == size, "Short bounded read")
        return raw


def checked_modules(selected):
    base.require(set(selected) == set(base.HASHES), "Only two pinned images allowed")
    for name, module in selected.items():
        base.require(module.get("sha256") == base.HASHES[name], "Unverified image fingerprint")
        base.require(Path(module["path"]).name.lower() == name, "Image name mismatch")
        base.pointer(module["base"])
        base.require(4096 <= module["size"] and module["base"] + module["size"] <= USER_END,
                     "Image range overflows user address space")
        base.require(module["pe_identity"]["image_size"] == module["size"],
                     "PE identity image size mismatch")
    exe, game = selected["helldivers2.exe"], selected["game.dll"]
    base.require(CALLER_RVA + CALLER_SIZE <= exe["size"] and
                 TARGET_RVA + CODE_BYTES <= exe["size"], "Fixed code exceeds EXE image")
    base.require(all(rva + size <= game["size"] for rva, size, _ in base.PINS),
                 "Fixed pins exceed game.dll image")
    # Ambiguous/overlapping module ownership is rejected before the code reads.
    base.owner(list(selected.values()), exe["base"] + CALLER_RVA, CALLER_SIZE)
    base.owner(list(selected.values()), exe["base"] + TARGET_RVA, CODE_BYTES)


def verify_caller(reader, exe):
    raw = reader.read(bounded_address(exe["base"] + CALLER_RVA, CALLER_SIZE),
                      CALLER_SIZE, executable=True)
    base.require(len(raw) == CALLER_SIZE and base.digest(raw) == CALLER_SHA,
                 "Previously saved wrapper caller changed")


def observe_callee(reader, selected):
    checked_modules(selected)
    exe = selected["helldivers2.exe"]
    address = bounded_address(exe["base"] + TARGET_RVA, CODE_BYTES)
    raw = reader.read(address, CODE_BYTES, executable=True)
    base.require(len(raw) == CODE_BYTES, "Short callee read")
    again = reader.read(address, CODE_BYTES, executable=True)
    base.require(len(again) == CODE_BYTES, "Short callee reread")
    base.require(again == raw, "Callee code changed on reread")
    return {
        "function": {"address": hex(address), "module": exe["path"],
                     "module_rva": hex(TARGET_RVA), "size": CODE_BYTES,
                     "bytes": raw.hex(), "sha256": base.digest(raw),
                     "reread_sha256": base.digest(again), "unchanged_on_reread": True},
        "entry_basis": {"saved_direct_call_site_rva": hex(CALL_SITE_RVA),
                        "prior_capture_sha256": PRIOR_CAPTURE_SHA},
        "atomic_snapshot": False, "eight_player_verified": False,
        "limitations": [
            "The prefix may be incomplete, a stub, or include following functions/data.",
            "No newly discovered pointer, branch, jump thunk, or called function is followed.",
            "Equal rereads do not exclude intervening changes, image reload, or address reuse.",
            "No game function invocation, returned handle, successful entity creation, or multiplayer validation.",
            "This is a roster-related handle wrapper's callee, not an established player-only allocator.",
        ],
    }


def plan():
    return {
        "mode": "offline_plan", "build": base.BUILD, "file_sha256": base.HASHES,
        "purpose": "one fixed direct callee of the roster-related handle wrapper",
        "prior_capture_sha256": PRIOR_CAPTURE_SHA,
        "target": {"exe_rva": hex(TARGET_RVA), "size": CODE_BYTES,
                   "direct_call_site_rva": hex(CALL_SITE_RVA)},
        "caller_pin": {"exe_rva": hex(CALLER_RVA), "size": CALLER_SIZE,
                       "end_exclusive_rva": hex(CALLER_RVA + CALLER_SIZE),
                       "sha256": CALLER_SHA, "instruction_count": 9},
        "each_code_range_read_twice": True,
        "read_components": READ_COMPONENTS,
        "expected_memory_bytes": EXPECTED_MEMORY_BYTES,
        "hard_read_budget": EXPECTED_MEMORY_BYTES,
        "target_requires_executable_mem_image": True,
        "opens_process": False, "requires_separate_capture_authorization": True,
        "runtime_tested": False, "eight_player_mod": False,
    }


def capture_once(adapter, pid):
    """Single bounded transaction; injectable adapter permits offline tests."""
    reader = BudgetReader(adapter)
    executable = adapter.executable()
    modules = adapter.modules()
    selected = base.check_files(modules, executable)
    checked_modules(selected)
    base.verify_loaded(reader, selected)
    verify_caller(reader, selected["helldivers2.exe"])
    report = observe_callee(reader, selected)
    verify_caller(reader, selected["helldivers2.exe"])
    base.verify_loaded(reader, selected)
    base.require(adapter.executable() == executable and adapter.modules() == modules,
                 "Process image/module list changed")
    base.require(base.check_files(modules, executable) == selected, "Disk identity changed")
    base.require(reader.used == adapter.used == EXPECTED_MEMORY_BYTES,
                 "Read count differs from fixed capture plan")
    report.update({
        "schema_version": 1, "purpose": plan()["purpose"],
        "build": base.BUILD, "pid": pid, "utc": datetime.now(timezone.utc).isoformat(),
        "pinned_images": selected, "caller_pin": plan()["caller_pin"],
        "read_components": READ_COMPONENTS, "memory_bytes_read": reader.used,
        "runtime_capture": True,
        "utility_file_sha256_at_output": base.digest(Path(__file__).read_bytes()),
        "reader_file_sha256_at_output": base.digest(Path(base.__file__).read_bytes()),
    })
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--capture", action="store_true")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.capture:
        base.require(args.pid is None and args.output is None, "PID/output require --capture")
        print(json.dumps(plan(), indent=2))
        return
    base.require(args.pid is not None and args.output is not None,
                 "Capture requires explicit --pid and new --output")
    base.require(0 < args.pid <= 0xFFFFFFFF, "Invalid explicit PID")
    base.require(not args.output.exists(), "Refusing to overwrite output")
    adapter = base.WindowsReader(args.pid)
    try:
        report = capture_once(adapter, args.pid)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        print(str(args.output.resolve()))
    finally:
        adapter.close()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print("Stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
