"""Offline plan or one separately authorized fixed-range Party supplement.

The previous v2 capture grant is exhausted. --pid needs new explicit user
authorization and a current user-supplied PID. No launch, PID search or retry.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys

import pefile

from interface_probe import WindowsReader, check_files, verify_loaded, HASHES, BUILD, PINS
from capture_live_party_slots_20261111 import BudgetedReader, READ_BUDGET, digest
from party_manager_binding import PARTY_SHA256

SLOT_RVA = 0x2C75FEC
ENTRY_RVA = 0x2C7A94D
ENTRY_BYTES = bytes.fromhex("e9db052800")
DISPATCHER_RVA = 0x2EFAF2D
DISPATCHER_BYTES = 4096
EXPORT_RVAS = (0x19880, 0x1BE80)


def build_plan():
    rows = [{"label": "loaded_pe_header", "module": name, "rva": "0x0",
             "bytes_per_read": 4096, "maximum_reads": 2}
            for name in (*HASHES, "PartyWin.dll")]
    rows += [{"label": "game_code_pin", "module": "game.dll", "rva": hex(rva),
              "bytes_per_read": size, "maximum_reads": 2, "sha256": expected}
             for rva, size, expected in PINS]
    rows += [
        {"label": "common_call_slot", "module": "helldivers2.exe", "rva": hex(SLOT_RVA),
         "bytes_per_read": 8, "maximum_reads": 2, "required_value": f"EXE+{ENTRY_RVA:#x}"},
        {"label": "known_entry_jump", "module": "helldivers2.exe", "rva": hex(ENTRY_RVA),
         "bytes_per_read": len(ENTRY_BYTES), "maximum_reads": 2, "required_bytes": ENTRY_BYTES.hex()},
        {"label": "fixed_dispatcher_window", "module": "helldivers2.exe", "rva": hex(DISPATCHER_RVA),
         "bytes_per_read": DISPATCHER_BYTES, "maximum_reads": 2,
         "rule": "Executable MEM_IMAGE; whole range inside verified EXE; bytes must agree on reread."},
    ]
    return {
        "schema": "hd2_party_dispatcher_supplement_plan_v1", "build": BUILD,
        "requires_new_explicit_authorization": True, "capture_count": 1, "automatic_retries": 0,
        "file_sha256": {**HASHES, "PartyWin.dll": PARTY_SHA256},
        "fixed_memory_reads": rows,
        "planned_maximum_memory_bytes": sum(r["bytes_per_read"] * r["maximum_reads"] for r in rows),
        "hard_memory_read_budget_bytes": READ_BUDGET,
        "budget_accounting": "Every requested process-memory payload byte, including validation, rereads and failed reads. Disk bytes and OS metadata are separate.",
        "disk_reads": "Full contents of loaded helldivers2.exe, game.dll and PartyWin.dll for fixed hashes. Parse the same PartyWin bytes for exact export names/ordinals at 0x19880 and 0x1be80; no other game files or logs.",
        "disk_export_rvas": [hex(rva) for rva in EXPORT_RVAS],
        "export_lookup_rule": "Exact RVA matches only. Preserve aliases/ordinal-only matches and forwarders; report no_exact_export_match without guessing a name.",
        "metadata_queries": "Executable path and loaded module names/paths/base/size for one explicit PID; memory-region protection checks for fixed requests.",
        "required_user_state": "Current PID supplied by the user in stable solo ship state after new authorization.",
        "stops_on": ["file/header/code identity mismatch", "changed slot or entry jump",
                     "unreadable/short read", "changed dispatcher bytes", "out-of-image range", "budget exhausted"],
        "follows_new_jumps": False, "follows_heap_pointers": False,
        "starts_game": False, "native_game_calls": False, "memory_writes": False,
        "hooks_installed": False, "changes_game_files": False,
        "provider_binding_proven": False, "runtime_verified": False, "multiplayer_verified": False,
        "limit": "A 4096-byte window is not guaranteed to cover the full dispatcher. Any missing continuation is reported, never followed automatically.",
    }


def match_exports(symbols):
    rows = []
    for rva in EXPORT_RVAS:
        matches = [{"name": s.name.decode("ascii") if s.name is not None else None,
                    "ordinal": s.ordinal,
                    "forwarder": s.forwarder.decode("ascii") if s.forwarder is not None else None}
                   for s in symbols if s.address == rva]
        rows.append({"rva": hex(rva), "status": "exact_export_match" if matches else "no_exact_export_match",
                     "matches": matches, "source": "fingerprint_verified_disk_export_table"})
    return rows


def inspect_party_bytes(raw):
    if digest(raw) != PARTY_SHA256:
        raise ValueError("unsupported PartyWin fingerprint")
    pe = pefile.PE(data=raw, fast_load=True)
    try:
        if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20B:
            raise ValueError("expected x64 PartyWin image")
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
        exports = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
        if exports is None or not exports.symbols:
            raise ValueError("PartyWin export directory unavailable")
        return {"sha256": PARTY_SHA256, "image_size": pe.OPTIONAL_HEADER.SizeOfImage,
                "timestamp": pe.FILE_HEADER.TimeDateStamp,
                "exact_export_matches": match_exports(exports.symbols)}
    finally:
        pe.close()


def read_party_image(path):
    return inspect_party_bytes(path.read_bytes())


def capture(reader, pid):
    exe_path = reader.backend.executable()
    modules = reader.backend.modules()
    selected = check_files(modules, exe_path)
    party_modules = [m for m in modules if Path(m["path"]).name.lower() == "partywin.dll"]
    if len(party_modules) != 1:
        raise ValueError("expected exactly one loaded PartyWin.dll")
    party = party_modules[0]
    identity = read_party_image(Path(party["path"]))
    if identity["image_size"] != party["size"]:
        raise ValueError("loaded PartyWin image size mismatch")
    selected["PartyWin.dll"] = {**party, "sha256": identity["sha256"],
                               "pe_identity": {k: identity[k] for k in ("timestamp", "image_size")}}
    for row in build_plan()["fixed_memory_reads"]:
        if int(row["rva"], 16) + row["bytes_per_read"] > selected[row["module"]]["size"]:
            raise ValueError("fixed request outside verified image: " + row["label"])
    exe = selected["helldivers2.exe"]["base"]
    reader.stage = "initial_identity_verification"
    verify_loaded(reader, selected)

    def read_chain():
        slot = reader.read(exe + SLOT_RVA, 8)
        if int.from_bytes(slot, "little") != exe + ENTRY_RVA:
            raise ValueError("common slot no longer points to the pinned entry RVA")
        entry = reader.read(exe + ENTRY_RVA, len(ENTRY_BYTES), executable=True)
        if entry != ENTRY_BYTES:
            raise ValueError("common entry jump fingerprint mismatch")
        destination = ENTRY_RVA + 5 + struct.unpack_from("<i", entry, 1)[0]
        if destination != DISPATCHER_RVA:
            raise ValueError("common jump no longer resolves to the fixed dispatcher RVA")
        return slot, entry

    reader.stage = "fixed_chain_verification"
    slot, entry = read_chain()
    reader.stage = "fixed_dispatcher_window"
    code = reader.read(exe + DISPATCHER_RVA, DISPATCHER_BYTES, executable=True)
    reader.stage = "chain_reread"
    slot_again, entry_again = read_chain()
    if slot_again != slot or entry_again != entry:
        raise ValueError("common chain changed during read")
    reader.stage = "dispatcher_reread"
    again = reader.read(exe + DISPATCHER_RVA, DISPATCHER_BYTES, executable=True)
    if again != code:
        raise ValueError("dispatcher window changed during reread")
    reader.stage = "final_identity_verification"
    verify_loaded(reader, selected)
    return {
        "schema": "hd2_party_dispatcher_supplement_capture_v1", "status": "captured",
        "build": BUILD, "pid": pid, "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "pinned_images": selected, "exe_base": hex(exe),
        "chain": {"slot_rva": hex(SLOT_RVA), "slot_raw": slot.hex(), "target_rva": hex(ENTRY_RVA),
                  "entry_bytes": entry.hex(), "destination_rva": hex(DISPATCHER_RVA),
                  "unchanged_on_reread": True},
        "dispatcher_window": {"rva": hex(DISPATCHER_RVA), "address": hex(exe + DISPATCHER_RVA),
                              "size": len(code), "code": code.hex(), "sha256": digest(code),
                              "reread_sha256": digest(again), "unchanged_on_reread": True},
        "party_disk_exports": identity["exact_export_matches"],
        "memory_bytes_requested": reader.used, "hard_memory_read_budget_bytes": READ_BUDGET,
        "read_ledger": reader.reads, "read_only": True, "atomic_snapshot": False,
        "native_game_calls": False, "memory_writes": False, "hooks_installed": False,
        "follows_new_jumps": False, "provider_binding_proven": False,
        "runtime_verified": False, "multiplayer_verified": False,
        "limit": "Only the fixed dispatcher window and exact on-disk export matches were captured; no target was invoked or new branch followed.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="offline only; no process or game file access")
    mode.add_argument("--pid", type=int, help="current explicit PID after NEW single-capture authorization")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.output.open("x", encoding="utf-8") as output:
        if args.plan:
            json.dump(build_plan(), output, indent=2)
            output.write("\n")
            print(json.dumps({"output": str(args.output), "mode": "offline_plan", "process_accessed": False}))
            return 0
        reader = None
        try:
            reader = BudgetedReader(WindowsReader(args.pid))
            report = capture(reader, args.pid)
            result = 0
        except (OSError, ValueError, pefile.PEFormatError) as error:
            report = {"schema": "hd2_party_dispatcher_supplement_capture_v1", "status": "stopped",
                      "pid": args.pid, "build": BUILD, "error": str(error),
                      "stage": reader.stage if reader else "open_process",
                      "memory_bytes_requested": reader.used if reader else 0,
                      "hard_memory_read_budget_bytes": READ_BUDGET,
                      "read_ledger": reader.reads if reader else [],
                      "native_game_calls": False, "memory_writes": False, "hooks_installed": False,
                      "provider_binding_proven": False, "runtime_verified": False, "multiplayer_verified": False}
            result = 1
        finally:
            if reader is not None:
                reader.backend.close()
        json.dump(report, output, indent=2)
        output.write("\n")
    print(json.dumps({"output": str(args.output), "status": report["status"],
                      "memory_bytes_requested": report["memory_bytes_requested"]}))
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print("Stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
