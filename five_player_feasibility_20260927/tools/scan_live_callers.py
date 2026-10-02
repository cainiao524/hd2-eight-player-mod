"""Bounded, read-only live call-edge scan for fixed-build native sites.

The scanner opens one explicitly supplied Helldivers 2 PID with query/read
rights, verifies the pinned build files, and scans executable image pages for
near calls (E8 rel32) targeting the saved native RVAs.  It never invokes game
code, writes memory, loads a DLL, installs a hook, or follows a discovered
pointer.  Results describe one process state only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys

import interface_probe as base


TARGETS = {
    # game.dll RVAs recovered from the fixed-build captures/disassembly.
    "host_join_root": 0x108BC70,
    "host_capacity_gate": 0x108C18F,
    "host_index_allocator": 0x108C3D8,
    "host_confirmed_peer_sender": 0x108C760,
    "host_migration_rebuild": 0x1089720,
    "host_peer_remove": 0x108D190,
    "platform_member_enumerator": 0x1092E60,
    "platform_member_consumer": 0x1093590,
    "platform_member_leaf_reader": 0x10936E0,
    "platform_member_state_update": 0x10937A0,
    "client_confirmed_peer_insert": 0x0B90B20,
    "client_confirmed_peer_receive": 0x0BABA80,
    "client_player_creation_gate": 0x1086460,
}

PAGE = 0x1000
MAX_READ = 0x10000000  # hard budget: 256 MiB


def _target_map(selected: dict, module_name: str = "game.dll") -> dict[int, dict]:
    module = next((m for name, m in selected.items() if name.lower() == module_name), None)
    base.require(module is not None, "pinned game.dll missing")
    return {
        int(module["base"]) + rva: {"name": name, "module": module_name,
                                    "rva": hex(rva)}
        for name, rva in TARGETS.items()
    }


def scan(pid: int, output: Path) -> dict:
    # interface_probe's regular captures intentionally use a 64 KiB budget.
    # This scanner has its own explicit 256 MiB ceiling for page-by-page
    # executable-image reads; raising the module-local guard does not widen
    # the process rights (the reader still requests query/read only).
    base.READ_BUDGET = MAX_READ
    reader = base.WindowsReader(pid)
    try:
        executable = reader.executable()
        modules = reader.modules()
        selected = base.check_files(modules, executable)
        base.verify_loaded(reader, selected)
        targets = _target_map(selected)
        target_addresses = set(targets)
        page_count = 0
        bytes_read = 0
        calls: list[dict] = []
        hash_hits: list[dict] = []
        # The confirmed-peer event ID is documented as a little-endian dword.
        hash_pattern = struct.pack("<I", 0x4804FCF4)
        previous_tail = b""
        for module_name, module in selected.items():
            start = int(module["base"])
            end = start + int(module["size"])
            cursor = start
            while cursor < end:
                amount = min(PAGE, end - cursor)
                try:
                    data = reader.read(cursor, amount, executable=True)
                except (ValueError, OSError):
                    cursor += amount
                    previous_tail = b""
                    continue
                page_count += 1
                bytes_read += len(data)
                combined = previous_tail + data
                combined_base = cursor - len(previous_tail)
                # Restrict call targets to the pinned game image. A call in a
                # page from another module is still useful, so retain caller
                # module identity below.
                for offset in range(max(0, len(previous_tail) - 4), len(combined) - 4):
                    if combined[offset] != 0xE8:
                        continue
                    call_address = combined_base + offset
                    displacement = struct.unpack_from("<i", combined, offset + 1)[0]
                    target = call_address + 5 + displacement
                    if target not in target_addresses:
                        continue
                    caller_rva = call_address - int(module["base"])
                    calls.append({
                        "target": targets[target],
                        "caller_module": module_name,
                        "caller_address": hex(call_address),
                        "caller_rva": hex(caller_rva),
                        "instruction": combined[offset:offset + 5].hex(),
                    })
                start_hash = 0
                while True:
                    hit = combined.find(hash_pattern, start_hash)
                    if hit < 0:
                        break
                    address = combined_base + hit
                    if start <= address < end:
                        hash_hits.append({"module": module_name, "address": hex(address),
                                          "rva": hex(address - int(module["base"]))})
                    start_hash = hit + 1
                previous_tail = data[-4:] if len(data) >= 4 else data
                cursor += amount
            previous_tail = b""
        base.require(bytes_read <= MAX_READ, "read budget exceeded")
        base.verify_loaded(reader, selected)
        result = {
            "schema": "hd2_live_native_call_edges_v1",
            "build": base.BUILD,
            "pid": pid,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "authorized read-only live executable-image scan; E8 rel32 calls and confirmed-peer hash only",
            "pinned_images": selected,
            "targets": {name: {"module": "game.dll", "rva": hex(rva)}
                        for name, rva in TARGETS.items()},
            "calls": calls,
            "confirmed_peer_event_hash_hits": hash_hits,
            "scan_stats": {"executable_pages_read": page_count, "memory_bytes_read": bytes_read,
                            "target_call_count": len(calls)},
            "read_only": True,
            "calls_made": False,
            "writes_made": False,
            "hooks_installed": False,
            "eight_player_verified": False,
            "limitations": [
                "Only direct E8 rel32 calls are reported; indirect calls, tail calls and dispatcher table entries require separate evidence.",
                "A call edge does not establish callback registration, argument ABI, owner lifetime or successful player creation.",
                "No function was invoked and no memory was changed; absence of a hit is process-state evidence only.",
            ],
        }
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result
    finally:
        reader.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite output")
    result = scan(args.pid, args.output)
    print(json.dumps({"output": str(args.output),
                      "calls": len(result["calls"]),
                      "hash_hits": len(result["confirmed_peer_event_hash_hits"])}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print("Stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
