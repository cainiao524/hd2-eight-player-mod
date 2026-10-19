"""Bounded read-only capture of Steam interface-factory callsites in HD2.

The tool requires an explicit HD2 PID and never invokes a target, suspends a
thread, changes page protections, installs a hook, or writes process memory.
It is intended to identify the interface name/version argument and nearby
return-value stores so that a later ABI audit can bind the real provider.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys

import capstone
import pefile

from interface_probe import WindowsReader, check_files, pointer, require, verify_loaded, BUILD
import interface_probe


IAT_RVA = 0x2961658
FACTORY_NAME = "SteamInternal_FindOrCreateUserInterface"
PAGE = 0x1000
READ_BUDGET = 48 * 1024 * 1024
CONTEXT_BEFORE = 128
CONTEXT_AFTER = 192
STRING_LIMIT = 128


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify(address: int, modules: list[dict]) -> dict:
    for module in modules:
        if module["base"] <= address < module["base"] + module["size"]:
            return {"module": Path(module["path"]).name, "rva": hex(address - module["base"])}
    return {"module": None, "rva": None}


def executable_ranges(exe_path: Path, base: int, image_size: int) -> list[dict]:
    pe = pefile.PE(str(exe_path), fast_load=False)
    ranges = []
    for section in pe.sections:
        if not section.Characteristics & 0x20000000:  # IMAGE_SCN_MEM_EXECUTE
            continue
        start = max(0, section.VirtualAddress)
        size = max(section.Misc_VirtualSize, section.SizeOfRawData)
        if size <= 0 or start >= image_size:
            continue
        size = min(size, image_size - start)
        ranges.append({
            "name": section.Name.rstrip(b"\x00 ").decode("ascii", "replace") or "<unnamed>",
            "rva": hex(start),
            "size": size,
            "start": base + start,
        })
    return ranges


def ascii_candidate(reader: WindowsReader, address: int, modules: list[dict]) -> dict | None:
    owner = classify(address, modules)
    if owner["module"] is None:
        return None
    try:
        data = reader.read(pointer(address), STRING_LIMIT)
    except (OSError, ValueError):
        return None
    text = data.split(b"\x00", 1)[0]
    if len(text) < 3 or any(byte < 0x20 or byte > 0x7E for byte in text):
        return None
    return {"address": hex(address), "owner": owner, "text": text.decode("ascii", "replace")}


def rip_target(instruction: capstone.CsInsn) -> int | None:
    if instruction.mnemonic not in {"lea", "mov"} or len(instruction.operands) < 2:
        return None
    memory = instruction.operands[1]
    if memory.type != capstone.x86.X86_OP_MEM or memory.mem.base != capstone.x86.X86_REG_RIP:
        return None
    return instruction.address + instruction.size + memory.mem.disp


def callsite_details(reader: WindowsReader, address: int, code: bytes,
                     code_start: int, modules: list[dict], exe_base: int) -> dict:
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    instructions = list(md.disasm(code, code_start))
    target = None
    for instruction in instructions:
        if instruction.address == address:
            if len(instruction.bytes) == 6 and instruction.bytes[:2] == b"\xFF\x15":
                target = instruction.address + instruction.size + struct.unpack_from("<i", instruction.bytes, 2)[0]
            break
    rows = []
    for instruction in instructions:
        if instruction.address >= address + 0x180:
            break
        if instruction.address < address - CONTEXT_BEFORE:
            continue
        rows.append({
            "rva": hex(instruction.address - exe_base),
            "address": hex(instruction.address),
            "bytes": instruction.bytes.hex(),
            "mnemonic": instruction.mnemonic,
            "op_str": instruction.op_str,
        })
    strings = []
    string_addresses = set()
    stores = []
    for instruction in instructions:
        candidate = rip_target(instruction)
        if candidate is not None and candidate not in string_addresses:
            string = ascii_candidate(reader, candidate, modules)
            if string is not None:
                string_addresses.add(candidate)
                strings.append(string)
        if instruction.address > address and instruction.address < address + CONTEXT_AFTER:
            if instruction.mnemonic == "mov" and len(instruction.operands) >= 2:
                destination = instruction.operands[0]
                if destination.type == capstone.x86.X86_OP_MEM and destination.mem.base == capstone.x86.X86_REG_RIP:
                    store_address = instruction.address + instruction.size + destination.mem.disp
                    stores.append({
                        "instruction_rva": hex(instruction.address - exe_base),
                        "address": hex(store_address),
                        "owner": classify(store_address, modules),
                        "width": destination.size,
                        "bytes": instruction.bytes.hex(),
                    })
    return {
        "callsite": {"address": hex(address), "rva": hex(address - exe_base)},
        "iat_target": {"address": hex(target) if target else None,
                        "owner": classify(target, modules) if target else None},
        "candidate_interface_strings": strings,
        "candidate_return_stores": stores,
        "instructions": rows,
    }


def capture(pid: int, output: Path) -> dict:
    interface_probe.READ_BUDGET = READ_BUDGET
    reader = WindowsReader(pid)
    try:
        executable = reader.executable()
        modules = reader.modules()
        selected = check_files(modules, executable)
        verify_loaded(reader, selected)
        exe_info = selected["helldivers2.exe"]
        exe_base = exe_info["base"]
        image_size = exe_info["size"]
        iat_address = exe_base + IAT_RVA
        iat_target = struct.unpack("<Q", reader.read(pointer(iat_address), 8))[0]
        ranges = executable_ranges(Path(executable), exe_base, image_size)
        hits = []
        scan_errors = []
        seen = set()
        for region in ranges:
            first = region["start"]
            last = first + region["size"]
            cursor = first
            while cursor < last:
                size = min(PAGE, last - cursor)
                try:
                    page = reader.read(pointer(cursor), size, executable=True)
                except (OSError, ValueError) as error:
                    scan_errors.append({"address": hex(cursor), "rva": hex(cursor - exe_base), "error": str(error)})
                    cursor += size
                    continue
                offset = 0
                while True:
                    offset = page.find(b"\xFF\x15", offset)
                    if offset < 0:
                        break
                    if offset + 6 <= len(page):
                        call = cursor + offset
                        target = call + 6 + struct.unpack_from("<i", page, offset + 2)[0]
                        if target == iat_address and call not in seen:
                            seen.add(call)
                            before = max(first, call - CONTEXT_BEFORE)
                            after = min(last, call + CONTEXT_AFTER)
                            try:
                                context = reader.read(pointer(before), after - before, executable=True)
                                detail = callsite_details(reader, call, context, before, modules, exe_base)
                                detail["context"] = {"start_rva": hex(before - exe_base),
                                                      "size": len(context), "sha256": digest(context),
                                                      "bytes": context.hex()}
                                hits.append(detail)
                            except (OSError, ValueError) as error:
                                hits.append({"callsite": {"address": hex(call), "rva": hex(call - exe_base)},
                                             "error": str(error)})
                    offset += 2
                cursor += size
        verify_loaded(reader, selected)
        report = {
            "schema": "hd2_live_steam_interface_factory_capture_v1",
            "build": BUILD,
            "pid": pid,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "pinned_images": selected,
            "read_only": True,
            "calls_made": False,
            "writes_made": False,
            "hooks_installed": False,
            "factory": {
                "name": FACTORY_NAME,
                "iat_rva": hex(IAT_RVA),
                "iat_address": hex(iat_address),
                "iat_target": hex(iat_target),
                "iat_target_owner": classify(iat_target, modules),
                "expected_module": "steam_api64.dll",
            },
            "executable_ranges": [{k: v for k, v in row.items() if k != "start"} for row in ranges],
            "callsites": hits,
            "scan_errors": scan_errors,
            "findings": {
                "steam_factory_iat_points_into_steam_api": Path(classify(iat_target, modules)["module"] or "").name.lower() == "steam_api64.dll",
                "factory_callsites_observed": bool(hits),
                "interface_name_argument_observed": any(row.get("candidate_interface_strings") for row in hits),
                "returned_interface_object_runtime_bound": False,
                "session_party_abi_proven": False,
                "multiplayer_verified": False,
                "public_release_allowed": False,
            },
            "limits": [
                "The scanner reads executable pages and bounded RIP-relative data only; it never follows or invokes a target.",
                "A candidate return store is an address observation, not proof that the stored object is a particular Steam interface.",
                "The capture cannot prove the GameSession-to-Steam object binding or any 8-player behavior.",
            ],
            "memory_bytes_read": reader.used,
            "tool_path": str(Path(__file__).resolve()),
            "tool_sha256": digest(Path(__file__)),
        }
        if output.exists():
            raise ValueError("refusing to overwrite output")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report
    finally:
        reader.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = capture(args.pid, args.output)
    except (OSError, ValueError) as error:
        print("Stopped: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output.resolve()), "callsites": len(report["callsites"]),
                      "memory_bytes_read": report["memory_bytes_read"],
                      "interface_name_argument_observed": report["findings"]["interface_name_argument_observed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
