"""Offline plan for one bounded roster-related handle interface observation.

Live access requires explicit --capture --pid N --output NEW.json and a separate
authorization. No automatic process discovery, launch, writes, game calls,
privilege adjustment, retries, or following discovered branches/callees.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import interface_probe as base

API_RVA = 0x3326308
OBJECT_OFFSET, VTABLE_OFFSET, FUNCTION_OFFSET = 0xC0, 0, 0x18
CODE_BYTES = 4096
CALLER_RVA, CALLER_SIZE = 0xAC9BE9, 51
CALLER_SHA = "6c78736c1f150bd2f9e600a811d71464658f0dd8093768f8f4cfb60a073d8536"
CALL_SITE_RVA = 0xAC9C19
SOURCE_SHA256 = {
    "capture-report.json": "132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5",
    "captured-data.bin": "31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d",
}
# Each item is read exactly twice on a successful capture. File hashing and
# module metadata queries are separate from this ReadProcessMemory byte count.
READ_COMPONENTS = {
    "pe_header_pages": 2 * 2 * 4096,
    "previous_game_code_pins": 2 * sum(size for _, size, _ in base.PINS),
    "spawn_caller_pin": 2 * CALLER_SIZE,
    "four_pointer_fields": 2 * 4 * 8,
    "target_code_prefix": 2 * CODE_BYTES,
}
EXPECTED_MEMORY_BYTES = sum(READ_COMPONENTS.values())
USER_END = 0x800000000000


def bounded_address(address, size):
    base.pointer(address)
    base.require(0 < size <= 4096 and address + size <= USER_END,
                 "Read range overflows user address space")
    return address


class BudgetReader:
    """Narrow the reviewed adapter's read budget without changing its source."""

    def __init__(self, adapter):
        self.adapter = adapter
        self.used = 0

    def read(self, address, size, executable=False):
        bounded_address(address, size)
        base.require(self.used + size <= EXPECTED_MEMORY_BYTES,
                     "Spawn probe read budget exceeded")
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
        base.require(0 < module["size"] and module["base"] + module["size"] <= USER_END,
                     "Image range overflows user address space")
    game = selected["game.dll"]
    base.require(API_RVA + 8 <= game["size"] and CALLER_RVA + CALLER_SIZE <= game["size"],
                 "Fixed game.dll locations exceed image")


def verify_caller(reader, game):
    raw = reader.read(bounded_address(game["base"] + CALLER_RVA, CALLER_SIZE),
                      CALLER_SIZE, executable=True)
    base.require(len(raw) == CALLER_SIZE and base.digest(raw) == CALLER_SHA,
                 "Roster handle caller fingerprint changed")


def observe_spawn_interface(reader, selected):
    """Read precisely four pointer fields and one code prefix, each twice.

    selected must come from base.check_files in the live path. Re-reading uses
    the original four field addresses; it never follows a changed pointer.
    """
    checked_modules(selected)
    watched = []

    def field(address, label):
        raw = reader.read(bounded_address(address, 8), 8)
        base.require(len(raw) == 8, "Short pointer read")
        value = base.pointer(int.from_bytes(raw, "little"))
        watched.append((address, raw, label, value))
        return value

    api = field(selected["game.dll"]["base"] + API_RVA, "api_root")
    obj = field(api + OBJECT_OFFSET, "api_plus_c0_object")
    vtable = field(obj + VTABLE_OFFSET, "object_vtable")
    target = field(vtable + FUNCTION_OFFSET, "vtable_plus_18_target")
    bounded_address(target, CODE_BYTES)
    # The entire prefix must belong to one of the two file-hash-verified images.
    module = base.owner(list(selected.values()), target, CODE_BYTES)
    raw = reader.read(target, CODE_BYTES, executable=True)
    base.require(len(raw) == CODE_BYTES, "Short code read")
    for address, original, label, _ in watched:
        again = reader.read(address, 8)
        base.require(len(again) == 8, "Short pointer reread")
        base.require(again == original, "Pointer changed on reread: " + label)
    again = reader.read(target, CODE_BYTES, executable=True)
    base.require(len(again) == CODE_BYTES, "Short code reread")
    base.require(again == raw, "Code prefix changed on reread")
    return {
        "api_global_rva": hex(API_RVA),
        "pointer_path": "game.dll+0x3326308 -> api+0xc0 -> object+0 -> vtable+0x18",
        "field_samples": [{"label": label, "address": hex(address), "bytes": value.hex(),
                           "value": hex(pointer_value)}
                          for address, value, label, pointer_value in watched],
        "function": {"address": hex(target), "module": module["path"],
                     "module_rva": hex(target - module["base"]), "size": CODE_BYTES,
                     "bytes": raw.hex(), "sha256": base.digest(raw),
                     "reread_sha256": base.digest(again), "unchanged_on_reread": True},
        "observed_fields_unchanged_on_reread": True,
        "atomic_snapshot": False,
        "eight_player_verified": False,
        "limitations": [
            "The prefix may be a stub, incomplete function, or include following functions/data.",
            "No discovered pointer, branch, jump thunk, or called function is followed.",
            "Equal rereads do not exclude intervening changes, unload/reload, or address reuse.",
            "No invocation, returned handle, successful entity creation, service result, or multiplayer test is observed.",
            "The caller is roster-related; neither player-specific allocation nor eight-player capacity is established.",
        ],
    }


def plan():
    return {
        "mode": "offline_plan", "build": base.BUILD, "file_sha256": base.HASHES,
        "purpose": "resolve one roster-related handle-producing interface target",
        "pointer_path": "game.dll+0x3326308 -> api+0xc0 -> object+0 -> vtable+0x18",
        "pointer_fields": 4, "bytes_per_pointer_field": 8,
        "code_prefix_bytes": CODE_BYTES, "each_field_and_prefix_read_twice": True,
        "caller_pin": {"game_rva": hex(CALLER_RVA), "size": CALLER_SIZE,
                       "sha256": CALLER_SHA, "call_rva": hex(CALL_SITE_RVA),
                       "end_exclusive_rva": hex(CALLER_RVA + CALLER_SIZE)},
        "caller_source_sha256": SOURCE_SHA256,
        "read_components": READ_COMPONENTS,
        "expected_memory_bytes": EXPECTED_MEMORY_BYTES,
        "hard_read_budget": EXPECTED_MEMORY_BYTES,
        "target_allowed_images": list(base.HASHES),
        "target_requires_executable_mem_image": True,
        "opens_process": False, "requires_separate_capture_authorization": True,
        "runtime_tested": False, "eight_player_mod": False,
    }


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
    base.require(not args.output.exists(), "Refusing to overwrite output")
    adapter = base.WindowsReader(args.pid)
    reader = BudgetReader(adapter)
    try:
        executable = adapter.executable()
        modules = adapter.modules()
        selected = base.check_files(modules, executable)
        checked_modules(selected)
        base.verify_loaded(reader, selected)
        verify_caller(reader, selected["game.dll"])
        report = observe_spawn_interface(reader, selected)
        verify_caller(reader, selected["game.dll"])
        base.verify_loaded(reader, selected)
        base.require(adapter.executable() == executable and adapter.modules() == modules,
                     "Process image/module list changed")
        base.require(base.check_files(modules, executable) == selected, "Disk identity changed")
        base.require(reader.used == adapter.used == EXPECTED_MEMORY_BYTES,
                     "Read count differs from fixed capture plan")
        report.update({
            "schema_version": 1, "purpose": plan()["purpose"],
            "build": base.BUILD, "pid": args.pid, "utc": datetime.now(timezone.utc).isoformat(),
            "pinned_images": selected, "caller_pin": plan()["caller_pin"],
            "caller_source_sha256": SOURCE_SHA256,
            "read_components": READ_COMPONENTS, "memory_bytes_read": reader.used,
            "runtime_capture": True,
            "utility_file_sha256_at_output": base.digest(Path(__file__).read_bytes()),
            "reader_file_sha256_at_output": base.digest(Path(base.__file__).read_bytes()),
        })
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
