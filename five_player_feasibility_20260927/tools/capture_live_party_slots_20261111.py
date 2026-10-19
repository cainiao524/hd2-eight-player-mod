"""One explicit-PID, read-only Party capture; --plan never opens a process.

Fixed to build 25480438. Offline tests inject a reader; only main's --pid
branch can construct WindowsReader. No automatic launch, PID search or retry.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys

from interface_probe import WindowsReader, check_files, verify_loaded, pointer, HASHES, BUILD, PINS
from party_manager_binding import verify_party_file, verify_live_layout, observe
from party_manager_binding import (PARTY_SHA256, MANAGER_GLOBAL_RVA, STORED_HANDLE_OFFSET,
                                   HOLDER_RVA, HELPER_RVA, HELPER_SIZE, HELPER_SHA256, CODE_PINS)

# Local hard limit: changing interface_probe.READ_BUDGET cannot enlarge this
# capture. No CLI budget override exists. Failed requests count.
READ_BUDGET = 64 * 1024
PREFIX_BYTES = 512
WRAPPER_BYTES = 1024
SLOT_RVAS = {
    "create_network_candidate": 0x13F6DB8,
    "async_or_state_candidate": 0x13F6EF8,
    "authenticate_or_state_candidate": 0x13F6DF0,
    "create_endpoint_candidate": 0x13F6C30,
    "connect_network_candidate": 0x13F6F70,
    "auth_network_candidate": 0x13F7030,
}
# label -> (missing qword, wrapper RVA, first 1024 bytes SHA-256,
#           position helper RVA, exact 14-byte helper body).
# Sources: recovered r13 windows and saved r5 helper bodies.
ENTRY_PINS = {
    "create_network_candidate": (0x2985447, 0x2FC3336,
        "8c8da15b4aac8db61ff494d411144bcd738552d73958f7281a2209e223b0b468",
        0x29791F8, "e8000000005d4881edfd010000c3"),
    "async_or_state_candidate": (0x2985527, 0x2FCC2D5,
        "722c8831526d02887b3cbcfa74c8b3119edc15dd5a7d9179457ea8088e7316d7",
        0x29790D2, "e8000000005d4881edd7000000c3"),
    "authenticate_or_state_candidate": (0x29848A7, 0x2F4D507,
        "59cf8dc8bbc006ed18bf5da807f418d3bcf30c7ed7917b4b818a8038dc2377b4",
        0x297909A, "e8000000005d4881ed9f000000c3"),
    "create_endpoint_candidate": (0x2984B7F, 0x2F6A2A4,
        "8e8287f94115ef2a976a32bd64a8b260cbef498907d66158f2ce81a96d5d2c9d",
        0x2979206, "e8000000005d4881ed0b020000c3"),
    "connect_network_candidate": (0x2984C3F, 0x2F71DF0,
        "27fe8a7f90af543c0c777a83ae23d58a08960fa432628d0f1d1e541879f2b7b4",
        0x29790EE, "e8000000005d4881edf3000000c3"),
    "auth_network_candidate": (0x298568F, 0x2FDA54E,
        "9589d3e2b53b3946b5e2f1616a7494149aae1141f390f7c5b029b04f116e6038",
        0x2979038, "e8000000005d4881ed3d000000c3"),
}
COMMON_SLOT_RVA = 0x2C75FEC
CALLSITE_RVAS = {"create_network_callsite": 0x8E1370, "follow_on_callsite": 0x8E1970}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixed_reads() -> list[dict]:
    """One source of truth for the plan, range checks and byte accounting."""
    rows = []

    def add(label, module, rva, size, count=1, expected=None):
        rows.append({"label": label, "module": module, "rva": hex(rva),
                     "bytes_per_read": size, "maximum_reads": count, "sha256": expected})

    for name in (*HASHES, "PartyWin.dll"):
        add("loaded_pe_header", name, 0, 4096, 2)
    for rva, size, expected in PINS:
        add("game_code_pin", "game.dll", rva, size, 2, expected)
    add("manager_helper_pin", "helldivers2.exe", HELPER_RVA, HELPER_SIZE, 2, HELPER_SHA256)
    for rva, size, expected in CODE_PINS:
        add("manager_code_pin", "PartyWin.dll", rva, size, 2, expected)
    for label, (data_rva, code_rva, expected, helper_rva, helper_hex) in ENTRY_PINS.items():
        add(label + "_wrapper_pin", "helldivers2.exe", code_rva, WRAPPER_BYTES, 2, expected)
        add(label + "_position_helper", "helldivers2.exe", helper_rva,
            len(bytes.fromhex(helper_hex)), 2, digest(bytes.fromhex(helper_hex)))
        add(label + "_entry_qword", "helldivers2.exe", data_rva, 8, 2)
    for label, rva in SLOT_RVAS.items():
        add(label + "_existing_slot", "helldivers2.exe", rva, 8, 2)
    add("common_call_slot", "helldivers2.exe", COMMON_SLOT_RVA, 8, 2)
    add("opaque_game_handle", "helldivers2.exe", HOLDER_RVA, 8, 2)
    add("party_manager_pointer", "PartyWin.dll", MANAGER_GLOBAL_RVA, 8, 2)
    add("existing_helper_window", "helldivers2.exe", HELPER_RVA, 0x500)
    for label, rva in CALLSITE_RVAS.items():
        add(label, "helldivers2.exe", rva, 0x400)
    return rows


def build_plan() -> dict:
    fixed = fixed_reads()
    fixed_max = sum(r["bytes_per_read"] * r["maximum_reads"] for r in fixed)
    dynamic_max = 16 + (len(SLOT_RVAS) + 1) * PREFIX_BYTES
    return {
        "schema": "hd2_party_slots_capture_plan_v2", "build": BUILD,
        "file_sha256": {**HASHES, "PartyWin.dll": PARTY_SHA256},
        "disk_reads": "Full contents of exactly the three verified loaded image files; PE/Party checks also read those files. No other game files or logs.",
        "metadata_queries": "One explicit PID: executable path, loaded module names/paths/base/size, and memory-region protection for requested ranges. No process search.",
        "fixed_memory_reads": fixed,
        "manager_data_reads": {
            "game_holder": f"helldivers2.exe+{HOLDER_RVA:#x}",
            "party_manager_global": f"PartyWin.dll+{MANAGER_GLOBAL_RVA:#x}",
            "stored_handle": f"[party_manager_global]+{STORED_HANDLE_OFFSET:#x}",
            "bytes_per_read": 8, "maximum_reads_per_field": 2,
            "maximum_bytes_with_rereads": 48, "opaque_handle_dereferenced": False,
        },
        "conditional_memory_reads": [
            {"source": "canonical manager object pointer", "offset": hex(STORED_HANDLE_OFFSET),
             "bytes_per_read": 8, "maximum_reads": 2},
            {"source": "six existing candidate slots", "bytes_per_read": PREFIX_BYTES,
             "maximum_reads": len(SLOT_RVAS), "allowed_images": ["helldivers2.exe"]},
            {"source": "common_call_slot", "bytes_per_read": PREFIX_BYTES,
             "maximum_reads": 1, "allowed_images": [*HASHES, "PartyWin.dll"]},
        ],
        "code_target_rule": "Whole 512-byte range inside one allowed verified image, executable MEM_IMAGE; otherwise no prefix read. No jump or decoded-value following.",
        "new_core_unique_bytes_including_manager": 80,
        "new_core_maximum_bytes_with_rereads": 160,
        "fixed_maximum_bytes_with_rereads": fixed_max,
        "conditional_maximum_bytes": dynamic_max,
        "planned_maximum_memory_bytes": fixed_max + dynamic_max,
        "total_memory_read_budget_bytes": READ_BUDGET,
        "budget_accounting": "All requested process-memory payload bytes, including validation, rereads and failed requests. Excludes OS metadata and whole-file disk hashing.",
        "capture_count": 1, "automatic_retries": 0,
        "required_game_state": "user-reported stable solo ship; one PC/account",
        "starts_game": False, "native_game_calls": False, "memory_writes": False,
        "hooks_installed": False, "changes_game_files": False,
        "provider_binding_proven": False, "runtime_verified": False, "multiplayer_verified": False,
        "stop_conditions": ["unsupported file or loaded-code fingerprint", "unreadable/short read",
                            "budget exhausted", "changed qword reread", "invalid fixed image range"],
        "execution": "Only after explicit user authorization: --pid <current user-supplied PID> --output <new receipt path>. No elevation or fallback on denied access.",
    }


class BudgetedReader:
    """Account before delegation, even when a backend read fails."""
    def __init__(self, backend):
        self.backend = backend
        self.used = 0
        self.reads = []
        self.stage = "identity"

    def read(self, address: int, size: int, executable: bool = False) -> bytes:
        pointer(address)
        if not 0 < size <= 4096 or address + size > 0x800000000000:
            raise ValueError("invalid bounded read range")
        if self.used + size > READ_BUDGET:
            raise ValueError("64 KiB process-memory read budget exhausted")
        self.used += size
        row = {"address": hex(address), "size": size, "executable": executable,
               "stage": self.stage, "status": "requested"}
        self.reads.append(row)
        try:
            raw = self.backend.read(address, size, executable=executable)
            if len(raw) != size:
                raise ValueError("short process-memory read")
        except (OSError, ValueError) as error:
            row.update(status="failed", error=str(error))
            raise
        row.update(status="read", sha256=digest(raw))
        if size == 8:
            row["raw"] = raw.hex()
        return raw


def classify(value: int, modules: list[dict]) -> dict:
    for module in modules:
        if module["base"] <= value < module["base"] + module["size"]:
            return {"module": Path(module["path"]).name, "rva": hex(value - module["base"])}
    return {"module": None, "rva": None}


def verify_entry_code(reader, exe):
    for label, (_, rva, expected, helper_rva, helper_hex) in ENTRY_PINS.items():
        if digest(reader.read(exe + rva, WRAPPER_BYTES, executable=True)) != expected:
            raise ValueError("saved wrapper fingerprint mismatch: " + label)
        code = bytes.fromhex(helper_hex)
        if reader.read(exe + helper_rva, len(code), executable=True) != code:
            raise ValueError("position helper fingerprint mismatch: " + label)


def code_prefix(reader, target, allowed) -> dict:
    matches = [m for m in allowed.values() if m["base"] <= target
               and target + PREFIX_BYTES <= m["base"] + m["size"]]
    if len(matches) != 1:
        return {"status": "skipped_outside_allowed_full_range"}
    code = reader.read(target, PREFIX_BYTES, executable=True)
    return {"status": "read", "size": len(code), "sha256": digest(code), "code": code.hex()}


def capture(reader: BudgetedReader, pid: int) -> dict:
    """Backend-injected core: tests never instantiate or open WindowsReader."""
    exe_path = reader.backend.executable()
    modules = reader.backend.modules()
    selected = check_files(modules, exe_path)
    party_modules = [m for m in modules if Path(m["path"]).name.lower() == "partywin.dll"]
    if len(party_modules) != 1:
        raise ValueError("expected exactly one loaded PartyWin.dll")
    party = party_modules[0]
    identity = verify_party_file(Path(party["path"]))
    if identity["image_size"] != party["size"]:
        raise ValueError("loaded PartyWin image size mismatch")
    selected["PartyWin.dll"] = {
        **party, "sha256": identity["sha256"],
        "pe_identity": {k: identity[k] for k in ("timestamp", "image_size")},
    }
    for row in fixed_reads():
        if int(row["rva"], 16) + row["bytes_per_read"] > selected[row["module"]]["size"]:
            raise ValueError("fixed read outside verified image: " + row["label"])
    exe = selected["helldivers2.exe"]["base"]

    def verify():
        verify_loaded(reader, selected)
        layout = verify_live_layout(reader, exe, party["base"])
        verify_entry_code(reader, exe)
        return layout

    reader.stage = "initial_code_verification"
    layout = verify()
    reader.stage = "data"

    def qword(label, rva):
        raw = reader.read(exe + rva, 8)
        return {"label": label, "rva": hex(rva), "address": hex(exe + rva),
                "raw": raw.hex(), "value": hex(struct.unpack("<Q", raw)[0])}

    slots = [qword(label, rva) for label, rva in SLOT_RVAS.items()]
    entries = [qword(label, pin[0]) for label, pin in ENTRY_PINS.items()]
    common = qword("common_call_slot", COMMON_SLOT_RVA)
    binding = observe(reader, exe, party["base"])
    if not binding["unchanged_on_reread"]:
        raise ValueError("manager data changed during reread")
    for row in [*slots, *entries, common]:
        raw = reader.read(int(row["address"], 16), 8)
        row["reread_raw"] = raw.hex()
        if raw.hex() != row["raw"]:
            raise ValueError("qword changed during reread: " + row["label"])

    reader.stage = "bounded_code_windows"
    for row in slots:
        target = int(row["value"], 16)
        row["target_owner"] = classify(target, modules)
        row["target_prefix"] = code_prefix(reader, target, {"helldivers2.exe": selected["helldivers2.exe"]})
    common_target = int(common["value"], 16)
    common["target_owner"] = classify(common_target, modules)
    common["target_prefix"] = code_prefix(reader, common_target, selected)
    helper = reader.read(exe + HELPER_RVA, 0x500, executable=True)
    callsites = []
    for label, rva in CALLSITE_RVAS.items():
        code = reader.read(exe + rva, 0x400, executable=True)
        callsites.append({"label": label, "rva": hex(rva), "size": len(code),
                          "sha256": digest(code), "code": code.hex()})
    reader.stage = "final_code_verification"
    verify()
    return {
        "schema": "hd2_live_party_slots_external_capture_v2", "status": "captured",
        "build": BUILD, "pid": pid, "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "pinned_images": selected, "exe_base": hex(exe), "read_only": True,
        "calls_made": False, "writes_made": False, "hooks_installed": False,
        "provider_binding_proven": False, "runtime_verified": False, "multiplayer_verified": False,
        "atomic_snapshot": False, "manager_binding_layout": layout,
        "manager_binding_observation": binding, "slots": slots,
        "entry_qwords": entries, "common_call_slot": common,
        "helper": {"rva": hex(HELPER_RVA), "size": len(helper), "sha256": digest(helper), "code": helper.hex()},
        "callsites": callsites, "memory_bytes_read": reader.used,
        "memory_read_budget_bytes": READ_BUDGET, "read_ledger": reader.reads,
        "limits": ["Sampled values and code only; no calls, decoded-value following or jump following.",
                   "The opaque handle is never dereferenced; only the manager pointer's +0x600 field is read.",
                   "Equal rereads are not an atomic snapshot, an owner-lifetime guarantee, ABI proof or admission evidence."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pid", type=int, help="explicit user-supplied HD2 PID; requires separate user authorization")
    mode.add_argument("--plan", action="store_true", help="write scope offline without any game access")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Exclusive creation fails for a bad output path before any process access.
    with args.output.open("x", encoding="utf-8") as output:
        if args.plan:
            json.dump(build_plan(), output, indent=2, ensure_ascii=False)
            output.write("\n")
            print(json.dumps({"output": str(args.output), "mode": "offline_plan", "process_accessed": False}))
            return 0
        reader = None
        try:
            reader = BudgetedReader(WindowsReader(args.pid))
            report = capture(reader, args.pid)
            result = 0
        except (OSError, ValueError) as error:
            report = {
                "schema": "hd2_live_party_slots_external_capture_v2", "status": "stopped",
                "build": BUILD, "pid": args.pid, "error": str(error),
                "stage": reader.stage if reader else "open_process",
                "memory_bytes_read": reader.used if reader else 0,
                "memory_read_budget_bytes": READ_BUDGET,
                "read_ledger": reader.reads if reader else [],
                "calls_made": False, "writes_made": False, "hooks_installed": False,
                "provider_binding_proven": False, "runtime_verified": False, "multiplayer_verified": False,
            }
            result = 1
        finally:
            if reader is not None:
                reader.backend.close()
        json.dump(report, output, indent=2, ensure_ascii=False)
        output.write("\n")
    print(json.dumps({"output": str(args.output), "status": report["status"],
                      "memory_bytes_read": report["memory_bytes_read"]}, ensure_ascii=False))
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print("Stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
