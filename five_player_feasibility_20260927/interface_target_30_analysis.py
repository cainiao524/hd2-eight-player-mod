"""Offline analysis of the saved +0x30/+0x18 target prefix only.

Reads the named JSON and EXE on disk. Does not open a process or access runtime
memory. The EXE code is not assumed to equal the already captured live prefix.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_64


TARGET_RVA = 0x3494B0
DIRECT_CALLEES = (0x4ACDE0, 0x349110)
EXPECTED_EXE_SHA256 = "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def parse_sections(image):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    if image[:2] != b"MZ" or image[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Invalid disk PE")
    number = struct.unpack_from("<H", image, pe + 6)[0]
    optional_size = struct.unpack_from("<H", image, pe + 20)[0]
    optional = pe + 24
    if struct.unpack_from("<H", image, optional)[0] != 0x20B:
        raise ValueError("Expected PE32+")
    table = optional + optional_size
    sections = []
    for i in range(number):
        at = table + i * 40
        name = image[at:at + 8].split(b"\0", 1)[0].decode("ascii", "replace")
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from("<IIII", image, at + 8)
        sections.append({
            "name": name, "rva": virtual_address, "virtual_size": virtual_size,
            "raw_size": raw_size, "raw_pointer": raw_pointer,
        })
    return sections


def disk_slice(image, sections, rva, size):
    candidates = [s for s in sections if s["rva"] <= rva
                  and rva + size <= s["rva"] + s["raw_size"]]
    if len(candidates) != 1:
        raise ValueError(f"RVA {rva:#x} does not map to one raw disk section")
    section = candidates[0]
    offset = section["raw_pointer"] + rva - section["rva"]
    if offset + size > len(image):
        raise ValueError("Disk offset beyond file")
    return image[offset:offset + size], offset, section


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-json", type=Path, required=True)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    capture_bytes = args.capture_json.read_bytes()
    capture = json.loads(capture_bytes)
    matching = [f for table in capture["tables"] if table["root_offset"] == "0x30"
                for f in table["functions"] if f["slot"] == "0x18"]
    if len(matching) != 1:
        raise ValueError("Expected exactly one saved +0x30/+0x18 target")
    target = matching[0]
    if int(target["module_rva"], 16) != TARGET_RVA or target["size"] != 256:
        raise ValueError("Saved target RVA/size mismatch")
    live_prefix = bytes.fromhex(target["bytes"])
    if sha256(live_prefix) != target["sha256"]:
        raise ValueError("Saved prefix digest mismatch")

    image = args.exe.read_bytes()
    disk_sha = sha256(image)
    if disk_sha != EXPECTED_EXE_SHA256:
        raise ValueError("Disk EXE digest mismatch")
    if capture["pinned_images"]["helldivers2.exe"]["sha256"] != disk_sha:
        raise ValueError("Captured EXE disk digest mismatch")
    sections = parse_sections(image)
    disk_prefix, file_offset, section = disk_slice(image, sections, TARGET_RVA, 256)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    instructions = [{
        "rva": hex(ins.address), "bytes": ins.bytes.hex(),
        "asm": ins.mnemonic + " " + ins.op_str,
    } for ins in md.disasm(live_prefix, TARGET_RVA)]
    if instructions[0]["rva"] != hex(TARGET_RVA):
        raise ValueError("Captured prefix did not disassemble at target")
    by_rva = {ins["rva"]: ins for ins in instructions}
    required = {
        0x3494CB: "mov ebp, ecx",
        0x3494CD: "mov esi, edx",
        0x349513: "mov dword ptr [rsp + 0x30], esi",
        0x34951A: "mov dword ptr [rsp + 0x28], ebp",
        0x34952A: "call 0x4acde0",
        0x34953C: "call 0x349110",
        0x349558: "ret ",
    }
    for rva, asm in required.items():
        if by_rva.get(hex(rva), {}).get("asm") != asm:
            raise ValueError(f"Unexpected captured instruction at {rva:#x}")
    rip_global_uses = []
    for rva in (0x3494C4, 0x3494F5, 0x349509, 0x34952F):
        raw = bytes.fromhex(by_rva[hex(rva)]["bytes"])
        disp = struct.unpack_from("<i", raw, len(raw) - 4)[0]
        rip_global_uses.append({"instruction_rva": hex(rva), "target_rva": hex(rva + len(raw) + disp)})
    if {row["target_rva"] for row in rip_global_uses} != {"0x1a10258"}:
        raise ValueError("Unexpected RIP-relative global target")

    callee_rows = []
    for rva in DIRECT_CALLEES:
        raw, offset, sec = disk_slice(image, sections, rva, 256)
        callee_rows.append({
            "rva": hex(rva), "disk_file_offset": hex(offset),
            "disk_section": sec["name"], "disk_256_sha256": sha256(raw),
            "disk_first_32_bytes": raw[:32].hex(),
            "loaded_bytes_available": False,
            "interpretation": "Only a direct call destination is proven by the saved live caller prefix. The callee's loaded code was not captured; disk bytes are opaque and are not disassembled for semantics.",
        })

    result = {
        "source": {
            "capture_json_sha256": sha256(capture_bytes),
            "saved_live_prefix_sha256": target["sha256"],
            "disk_exe_sha256": disk_sha,
            "capture_atomic_snapshot": capture["atomic_snapshot"],
            "observed_fields_unchanged_on_reread": capture["observed_fields_unchanged_on_reread"],
        },
        "target": {
            "path": "+0x30/+0x18", "module": "helldivers2.exe",
            "rva": hex(TARGET_RVA), "saved_live_prefix_size": len(live_prefix),
            "saved_live_prefix_sha256": sha256(live_prefix),
            "disk_file_offset": hex(file_offset),
            "disk_section": section["name"],
            "disk_prefix_sha256": sha256(disk_prefix),
            "disk_prefix_first_32_bytes": disk_prefix[:32].hex(),
            "disk_equals_saved_live_prefix": disk_prefix == live_prefix,
            "first_mismatch_offset": next((i for i, (a, b) in enumerate(zip(disk_prefix, live_prefix)) if a != b), None),
        },
        "saved_live_prefix_disassembly": instructions,
        "rip_global_uses": rip_global_uses,
        "entry_integer_argument_flow": {
            "win_x64_entry": "first integer argument ECX; second integer argument EDX",
            "first": "ECX -> EBP at 0x3494cb; low 32 bits stored at [RSP+0x28] at 0x34951a for direct call 0x4acde0",
            "second": "EDX -> ESI at 0x3494cd; low 32 bits stored at [RSP+0x30] at 0x349513 for direct call 0x4acde0",
            "callee_stack_positions": "At the pre-call RSP, +0x20 is Windows x64 argument 5, +0x28 is argument 6, +0x30 is argument 7. The low 32 bits of both entry integers are forwarded unchanged in arguments 6 and 7; the upper 32 bits of those stack slots are not initialized by these stores, so callee formal types remain unknown.",
            "static_game_dll_caller": "Captured game.dll root 0x1091800 loads EDX from owner+0x1b90 at 0x1091845 and ECX from owner+0x1b94 at 0x1091874 before call at 0x109187a; retry at 0x10918d4/0x10918e2/0x10918e8. The code's default branch sets owner+0x1b90=4 and owner+0x1b94=0x2710; the latter value may be overridden, and no platform meaning is established.",
        },
        "direct_callees_one_layer": [
            {
                "call_site": "0x34952a", "callee_rva": "0x4acde0",
                "arguments": "RCX=RBX from first indirect result, RDX not established after earlier indirect calls (volatile), R8=[global+0x98], R9=RDI from [global+0x90], stack 5=RAX from second indirect result, stack 6=entry ECX low32, stack 7=entry EDX low32",
                "return": "RAX retained in RBX and eventually returned by 0x3494b0",
            },
            {
                "call_site": "0x34953c", "callee_rva": "0x349110",
                "arguments": "RCX=[RIP-relative global RVA 0x1a10258]; RDX=RAX returned by 0x4acde0",
                "return": "ignored by 0x3494b0",
            },
        ],
        "disk_only_callee_bytes": callee_rows,
        "limits": [
            "The exact target disk prefix differs from the saved loaded prefix at byte zero. The disk code for each direct callee has no saved loaded counterpart; treating it as runtime code would be unsupported.",
            "The 256-byte saved live prefix covers a return at 0x349558 and padding through 0x34955f, then starts another entry at 0x349560; this does not provide loaded bytes for any direct callee.",
            "No callee implementation, platform service behavior, multiplayer capacity, or eight-player success follows from this argument forwarding.",
            "The saved capture is not an atomic snapshot, even though watched fields matched on reread.",
        ],
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
