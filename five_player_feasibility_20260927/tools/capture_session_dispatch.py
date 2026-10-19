"""Bounded no-call Session dispatch capture; requires an explicit live PID.

Reads only pinned modules, API table pointers, two documented owner paths,
and fixed EXE code windows. Does not install anything, call a game function,
change protections, suspend threads, or traverse arbitrary branch targets.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys

from interface_probe import (WindowsReader, check_files, verify_loaded, pointer,
                             require, digest, BUILD, READ_BUDGET)

ROOT_RVA, CONTEXT_RVA, ENGINE_ROOT_RVA = 0x3326308, 0x347CEF0, 0x1A10278
TABLE_RVAS = {0x38: 0x27CBE30, 0x40: 0x27CBB90}
WRAPPERS = {
    "network_getter": (0x34FDF0, bytes.fromhex("488b0581046c01488b80a8000000c3")),
    "session_08": (0x34B030, bytes.fromhex("4883ec28488b01ff90800000000fb6c04883c428c3")),
    "session_50": (0x34B110, bytes.fromhex("488b0148ff6038")),
    "session_60": (0x34B150, bytes.fromhex("488b0148ff6070")),
}
METHODS = ((0x292C60, 80), (0x291110, 512), (0x28F9C0, 4096), (0x292BE0, 7))
VTABLE_RVA = 0x1675B70


def observe(reader, game_base, exe_base):
    watched = []
    def exact(address, size, label, code=False):
        raw = reader.read(pointer(address), size, executable=code)
        require(len(raw) == size, "short_read:" + label)
        watched.append((address, raw, label, code))
        return raw
    def word(address, label):
        return struct.unpack("<Q", exact(address, 8, label))[0]

    result = {"status": "observed_dispatch", "errors": [], "function_calls": False,
              "memory_writes": False, "atomic_snapshot": False, "dispatch_callable": False,
              "multiplayer_verified": False}
    api = pointer(word(game_base + ROOT_RVA, "game_api_root"))
    tables = {}
    for slot, rva in TABLE_RVAS.items():
        table = word(api + slot, f"api_{slot:x}")
        require(table == exe_base + rva, "api_table_module_or_rva_mismatch")
        tables[slot] = table
    # Verify the actual function pointers as well as the fixed code windows.
    for slot, label in [(8, "session_08"), (0x50, "session_50"), (0x60, "session_60")]:
        require(word(tables[0x40] + slot, label) == exe_base + WRAPPERS[label][0],
                "session_wrapper_pointer_mismatch")
    require(word(tables[0x38] + 8, "network_getter") == exe_base + WRAPPERS["network_getter"][0],
            "network_wrapper_pointer_mismatch")
    for label, (rva, expected) in WRAPPERS.items():
        require(exact(exe_base + rva, len(expected), label + "_code", True) == expected,
                "wrapper_code_mismatch:" + label)
    result["api_root"] = hex(api)
    result["tables"] = {hex(k): hex(v) for k, v in tables.items()}
    result["code_windows"] = []
    for rva, size in METHODS:
        code = exact(exe_base + rva, size, f"method_{rva:x}", True)
        result["code_windows"].append({"module": "helldivers2.exe", "rva": hex(rva),
            "bytes": code.hex(), "size": size, "sha256": digest(code), "complete_function_proven": False})
    engine_root = word(exe_base + ENGINE_ROOT_RVA, "engine_root")
    context = word(game_base + CONTEXT_RVA, "host_context")
    session = word(pointer(engine_root) + 0xA8, "engine_session") if engine_root else 0
    host_owner = word(pointer(context) + 0xB390, "host_owner") if context else 0
    result["owners"] = {"engine_root": hex(engine_root), "host_context": hex(context),
                         "engine_session": hex(session), "host_owner": hex(host_owner)}
    result["owner_pointer_equal"] = bool(session and host_owner == session)
    # A mismatching owner is recorded without assuming it has an engine vtable.
    if session:
        vtable = word(pointer(session), "engine_session_vtable")
        result["engine_vtable"] = hex(vtable)
        if vtable != exe_base + VTABLE_RVA:
            result["errors"].append("engine_vtable_mismatch")
        else:
            result["virtual_targets"] = {}
            for slot, expected in [(0x80, 0x292C60), (0x38, 0x291110), (0x58, 0x28F9C0), (0x70, 0x292BE0)]:
                target = word(vtable + slot, f"virtual_{slot:x}")
                result["virtual_targets"][hex(slot)] = hex(target)
                if target != exe_base + expected:
                    result["errors"].append(f"virtual_target_mismatch:{slot:x}")
    else:
        result["errors"].append("engine_session_missing")
    if not result["owner_pointer_equal"]:
        result["errors"].append("host_owner_not_matched_to_engine_session")
    changed = []
    for address, previous, label, code in watched:
        if reader.read(address, len(previous), executable=code) != previous:
            changed.append(label)
    result["changed_fields"] = changed
    result["unchanged_on_reread"] = not changed
    if changed:
        result["errors"].append("snapshot_changed")
    if result["errors"]:
        result["status"] = "partial_dispatch_evidence"
    result["limitations"] = ["Pointer equality and stable rereads do not prove owner lifetime or thread quiescence.",
        "Code windows are bounded and may omit branches, failure paths or cleanup.",
        "No peer identity, player count, admission, entity creation or multiplayer claim is made."]
    return result


def capture(pid):
    reader = WindowsReader(pid)
    try:
        exe = reader.executable()
        modules = reader.modules()
        selected = check_files(modules, exe)
        verify_loaded(reader, selected)
        result = observe(reader, selected["game.dll"]["base"], selected["helldivers2.exe"]["base"])
        verify_loaded(reader, selected)
        require(reader.executable() == exe and reader.modules() == modules, "module_list_changed")
        require(check_files(modules, exe) == selected, "disk_identity_changed")
        result.update({"schema": "hd2_live_session_dispatch_v1", "pid": pid, "build": BUILD,
                       "utc": datetime.now(timezone.utc).isoformat(), "pinned_images": selected,
                       "read_bytes": reader.used, "read_budget": READ_BUDGET,
                       "tool_sha256": digest(Path(__file__).read_bytes())})
        return result
    finally:
        reader.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing_to_overwrite_capture")
    try:
        report = capture(args.pid)
    except (ValueError, OSError) as error:
        report = {"schema": "hd2_live_session_dispatch_v1", "pid": args.pid, "build": BUILD,
                  "utc": datetime.now(timezone.utc).isoformat(), "status": "capture_failed",
                  "error": str(error), "function_calls": False, "memory_writes": False,
                  "multiplayer_verified": False}
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({k: report[k] for k in ("status", "pid", "multiplayer_verified")}))
    sys.exit(1 if report["status"] == "capture_failed" else 0)
