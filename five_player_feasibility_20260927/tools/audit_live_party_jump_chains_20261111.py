"""Follow only bounded direct E9 jumps from the live Party candidate slots."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys

import capstone

from interface_probe import WindowsReader, check_files, verify_loaded, pointer, BUILD


SLOTS = {
    "create_network_candidate": 0x13F6DB8,
    "async_or_state_candidate": 0x13F6EF8,
    "authenticate_or_state_candidate": 0x13F6DF0,
    "create_endpoint_candidate": 0x13F6C30,
    "connect_network_candidate": 0x13F6F70,
    "auth_network_candidate": 0x13F7030,
}
MAX_DEPTH = 4
WINDOW_SIZE = 0x100


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def in_exe(address: int, base: int, size: int) -> bool:
    return base <= address and address + WINDOW_SIZE <= base + size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite output")
    reader = WindowsReader(args.pid)
    try:
        exe_path = reader.executable()
        modules = reader.modules()
        selected = check_files(modules, exe_path)
        verify_loaded(reader, selected)
        base = selected["helldivers2.exe"]["base"]
        size = selected["helldivers2.exe"]["size"]
        chains = []
        disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        disassembler.detail = True
        for label, rva in SLOTS.items():
            slot_address = base + rva
            slot_raw = reader.read(pointer(slot_address), 8)
            address = struct.unpack("<Q", slot_raw)[0]
            hops = []
            seen = set()
            for depth in range(MAX_DEPTH + 1):
                if address in seen or not in_exe(address, base, size):
                    hops.append({"depth": depth, "address": hex(address), "stop": "outside_or_repeat"})
                    break
                seen.add(address)
                try:
                    code = reader.read(pointer(address), WINDOW_SIZE, executable=True)
                except (OSError, ValueError) as error:
                    hops.append({"depth": depth, "address": hex(address),
                                 "rva": hex(address - base),
                                 "stop": "read_failed", "error": str(error)})
                    break
                row = {"depth": depth, "address": hex(address), "rva": hex(address - base),
                       "size": len(code), "sha256": sha(code), "first_bytes": code[:32].hex(),
                       "code": code.hex()}
                if code[:1] != b"\xE9":
                    row["stop"] = "non_e9_entry"
                    direct_calls = []
                    seen_calls = set()
                    for instruction in disassembler.disasm(code, address):
                        if instruction.mnemonic != "call" or not instruction.operands:
                            continue
                        operand = instruction.operands[0]
                        if operand.type != capstone.x86.X86_OP_IMM or instruction.bytes[:1] != b"\xE8":
                            continue
                        target = operand.imm
                        if target in seen_calls:
                            continue
                        seen_calls.add(target)
                        call_row = {"instruction": hex(instruction.address),
                                    "instruction_rva": hex(instruction.address - base),
                                    "target": hex(target),
                                    "target_rva": hex(target - base) if base <= target < base + size else None}
                        if in_exe(target, base, size):
                            try:
                                target_code = reader.read(pointer(target), WINDOW_SIZE, executable=True)
                                call_row.update({"sha256": sha(target_code),
                                                 "first_bytes": target_code[:32].hex(),
                                                 "code": target_code.hex()})
                            except (OSError, ValueError) as error:
                                call_row["read_error"] = str(error)
                        direct_calls.append(call_row)
                        if len(direct_calls) >= 8:
                            break
                    row["direct_relative_calls"] = direct_calls
                    hops.append(row)
                    break
                displacement = struct.unpack_from("<i", code, 1)[0]
                target = address + 5 + displacement
                row["jump_target"] = hex(target)
                row["jump_target_rva"] = hex(target - base) if base <= target < base + size else None
                hops.append(row)
                address = target
            chains.append({"label": label, "slot_rva": hex(rva),
                           "slot_target": hex(address if hops == [] else struct.unpack("<Q", slot_raw)[0]),
                           "hops": hops})
        verify_loaded(reader, selected)
        report = {
            "schema": "hd2_live_party_jump_chains_v1",
            "build": BUILD,
            "pid": args.pid,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "pinned_images": selected,
            "read_only": True,
            "calls_made": False,
            "writes_made": False,
            "hooks_installed": False,
            "max_depth": MAX_DEPTH,
            "window_size": WINDOW_SIZE,
            "chains": chains,
            "findings": {
                "all_chain_reads_inside_exe": all(
                    all(row.get("stop") != "outside_or_repeat" for row in chain["hops"])
                    for chain in chains
                ),
                "all_chains_direct_e9_only": True,
                "partywin_target_observed": False,
                "abi_or_semantics_proven": False,
            },
            "limits": [
                "Only direct E9 targets within the pinned EXE image were followed.",
                "No indirect jump, call, data pointer, or function was followed or invoked.",
                "A chain endpoint is not assigned a Party semantic without a direct binding and return/state proof.",
            ],
        }
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "chain_count": len(chains),
                          "memory_bytes_read": reader.used}, ensure_ascii=False))
    finally:
        reader.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print("Stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1)
