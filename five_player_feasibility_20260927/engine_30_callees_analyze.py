"""Offline argument-flow inventory for two saved EXE callee windows.

Reads only saved JSON and the pinned EXE's PE import metadata. Never opens a
process. Control-flow coverage comes from tools/exe_capture_cfg.py's bounded
saved-byte CFG, which does not follow calls or exception paths.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct

import pefile

EXPECTED_CAPTURE = "157ddf9f9f9c04265dbc80109441af7090fcf78316e8642781857668348f129a"
EXPECTED_EXE = "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06"
TARGETS = (0x4ACDE0, 0x349110)

GROUPS = [
    {
        "entry": "0x4acde0",
        "name": "first_direct_callee_argument_flow",
        "sites": [
            ("0x4acdf4", "stack", "push RDI adjusts entry RSP by 8"),
            ("0x4acdf5", "stack", "sub RSP,0x30; total body RSP shift is 0x38"),
            ("0x4ace2c", "read", "body [RSP+0x60] is entry argument 5"),
            ("0x4ace3b", "value", "EBX=2; used as first two integer arguments at later indirect call"),
            ("0x4ace47", "argument", "EDX=2 for indirect call at 0x4ace5d"),
            ("0x4ace50", "argument", "ECX=2 for indirect call at 0x4ace5d"),
            ("0x4ace5d", "indirect_call", "unresolved RIP-slot call using ECX=2, EDX=2, R8D=0"),
            ("0x4ace63", "write", "indirect return RAX stored at object+0xa0"),
            ("0x4ace6a", "address", "address of body [RSP+0x70], entry argument 7 slot"),
            ("0x4ace6f", "read", "entry argument 7 low 32 bits"),
            ("0x4ace73", "value", "EDX=0x8004667e for another unresolved indirect call"),
            ("0x4aceaf", "write", "entry argument 7 low 32 bits stored at object+0xa8"),
            ("0x4acf15", "write", "reuse of argument-7 stack slot as scratch value 1 after original copied"),
            ("0x4acf23", "read", "entry argument 6 low 16 bits from body [RSP+0x68]"),
            ("0x4acf28", "write", "word value 2 at start of 16-byte local buffer"),
            ("0x4acf2d", "indirect_call", "arg6 low16 passed in ECX to unresolved RIP-slot call"),
            ("0x4acf33", "value", "ECX=0 for another unresolved indirect conversion call"),
            ("0x4acf35", "write", "returned AX stored at local buffer+2"),
            ("0x4acf3a", "indirect_call", "unresolved call whose return EAX later stored at local buffer+4"),
            ("0x4acf47", "value", "R8D=0x10 (16) for call using local buffer"),
            ("0x4acf4b", "write", "returned EAX stored at local buffer+4"),
            ("0x4acf4f", "address", "RDX points to local buffer"),
            ("0x4acf5b", "indirect_call", "unresolved call with object+0xa0, 16-byte local buffer, size 16"),
            ("0x4acf63", "branch", "both sign-result branches included in saved CFG"),
            ("0x4acf6f", "branch", "error branch jumps to common return path"),
            ("0x4acffe", "direct_call", "call 0x4af960 outside all saved windows"),
            ("0x4ad01a", "return", "common return after normal and error branches"),
        ],
    },
    {
        "entry": "0x349110",
        "name": "second_direct_callee_pointer_append",
        "sites": [
            ("0x34911a", "address", "RBX=entry RCX+0xb8; count/capacity/data fields"),
            ("0x349121", "base", "RDI=entry RDX (first callee's returned pointer)"),
            ("0x349124", "read", "count dword at object+0xb8"),
            ("0x349126", "read", "capacity dword at object+0xbc"),
            ("0x34912a", "value", "count+1"),
            ("0x34912d", "branch", "count+1 <= capacity skips growth"),
            ("0x349132", "value", "growth request 2*capacity+10"),
            ("0x34913a", "value", "cap growth request at 0xffffffff"),
            ("0x34914b", "direct_call", "call 0x172ae0 outside saved windows for capacity growth"),
            ("0x349152", "read", "data pointer at object+0xc0"),
            ("0x349162", "write", "entry RDX pointer stored in data[count]"),
            ("0x349166", "write", "count dword incremented"),
            ("0x349172", "return", "common return for both growth and no-growth paths"),
        ],
    },
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-json", type=Path, required=True)
    parser.add_argument("--cfg-json", type=Path, required=True)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    saved_bytes = args.capture_json.read_bytes()
    if sha(saved_bytes) != EXPECTED_CAPTURE:
        raise ValueError("Saved capture fingerprint mismatch")
    saved = json.loads(saved_bytes)
    cfg_bytes = args.cfg_json.read_bytes()
    cfg = json.loads(cfg_bytes)
    if cfg["capture_file_sha256"] != EXPECTED_CAPTURE:
        raise ValueError("CFG source mismatch")
    ranges = {int(row["rva"], 16): row for row in saved["ranges"]}
    entries = {int(entry["entry_rva"], 16): entry for entry in cfg["entries"]}
    for rva in TARGETS:
        source, entry = ranges[rva], entries[rva]
        raw = bytes.fromhex(source["bytes"])
        if len(raw) != 4096 or sha(raw) != source["sha256"] or source["reread_sha256"] != source["sha256"]:
            raise ValueError(f"Unstable or mismatched saved range {rva:#x}")
        if entry["window_sha256"] != source["sha256"] or entry["unresolved"]:
            raise ValueError(f"CFG mismatch or unresolved normal edge {rva:#x}")

    disk = args.exe.read_bytes()
    if sha(disk) != EXPECTED_EXE or saved["pinned_images"]["helldivers2.exe"]["sha256"] != EXPECTED_EXE:
        raise ValueError("Disk EXE fingerprint mismatch")
    pe = pefile.PE(data=disk, fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
    imports = {
        imp.address - pe.OPTIONAL_HEADER.ImageBase: {
            "dll": entry.dll.decode("ascii", "replace"),
            "symbol": imp.name.decode("ascii", "replace") if imp.name else None,
            "ordinal": imp.ordinal,
        }
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])
        for imp in entry.imports
    }
    groups = []
    for group in GROUPS:
        entry = entries[int(group["entry"], 16)]
        by_rva = {ins["rva"]: ins for ins in entry["instructions"]}
        sites = []
        for rva, kind, effect in group["sites"]:
            if rva not in by_rva:
                raise KeyError(f"Missing CFG-reachable site {rva}")
            ins = by_rva[rva]
            sites.append({**ins, "kind": kind, "effect": effect})
        groups.append({k: v for k, v in group.items() if k != "sites"} | {
            "instruction_count": entry["instruction_count"],
            "normal_edges": entry["edges"],
            "unresolved_normal_edges": entry["unresolved"],
            "sites": sites,
        })

    indirect_sites = [
        "0x4ace5d", "0x4acf1d", "0x4acf2d", "0x4acf3a", "0x4acf5b",
        "0x4acf8d", "0x4acf97", "0x4acfa2", "0x4acfd0", "0x4acfda", "0x4acfe5",
    ]
    indirect_rows = []
    by_rva = {ins["rva"]: ins for ins in entries[0x4ACDE0]["instructions"]}
    for rva_text in indirect_sites:
        ins = by_rva[rva_text]
        raw = bytes.fromhex(ins["bytes"])
        if len(raw) != 6 or raw[:2] != b"\xff\x15":
            raise ValueError(f"Unexpected indirect call form {rva_text}")
        rva = int(rva_text, 16)
        slot = rva + 6 + struct.unpack_from("<i", raw, 2)[0]
        indirect_rows.append({
            "call_site_rva": rva_text, "pointer_slot_rva": hex(slot),
            "declared_pe_import": imports.get(slot),
        })

    result = {
        "source": {
            "capture_json_sha256": EXPECTED_CAPTURE,
            "cfg_json_sha256": sha(cfg_bytes),
            "disk_exe_sha256": EXPECTED_EXE,
            "atomic_snapshot": saved["atomic_snapshot"],
            "all_saved_ranges_unchanged_on_reread": saved["all_ranges_unchanged_on_reread"],
        },
        "stack_argument_mapping": {
            "caller_before_call": {"arg6": "[RSP+0x28] low32 = prior API ECX", "arg7": "[RSP+0x30] low32 = prior API EDX"},
            "callee_entry": {"arg6": "[RSP+0x30]", "arg7": "[RSP+0x38]"},
            "callee_after_push_rdi_sub_0x30": {"arg6": "[RSP+0x68]", "arg7": "[RSP+0x70]"},
        },
        "groups": groups,
        "pe_metadata": {
            "network_related_declared_imports": [
                {"iat_rva": hex(rva), **info}
                for rva, info in sorted(imports.items())
                if info["dll"].lower() in ("ws2_32.dll", "partywin.dll", "playfabmultiplayerwin.dll")
            ],
            "indirect_call_slots": indirect_rows,
            "interpretation": "No indirect call pointer slot above coincides with a declared static PE import IAT RVA; disk import names cannot label the captured indirect calls.",
        },
        "conclusions": [
            "Argument 6 low16 feeds an unresolved indirect conversion call, whose AX return is stored at offset +2 of a 16-byte local buffer with word 2 at offset 0 and another return dword at offset +4. This matches a sockaddr_in-style family/port/address layout and makes a port interpretation plausible, but the call target and actual service use are unverified.",
            "Argument 7 low32 is copied verbatim into the newly initialized object's +0xa8 dword before its stack slot is reused. No fixed-four comparison or bound on this argument appears on the CFG-reachable constructor path; downstream uses of +0xa8 are not covered.",
            "The second callee appends the first callee's returned pointer into a growable object-local array at object+0xb8/+0xbc/+0xc0. Its own growth condition is count+1 > capacity and contains no fixed-four limit; this array is not thereby identified as a player roster.",
        ],
        "limits": [
            "CFG explores all in-window normal direct branches from these two entries, not merely the first RET. It does not follow direct/indirect calls, exception paths, or dynamic dispatch.",
            "Direct callees 0x5c2c40, 0x4af960, and 0x172ae0 lie outside all four saved ranges. Indirect calls use unobserved pointer slots.",
            "No live heap/object values, function-pointer table values, network service responses, or eight-player gameplay were captured.",
            "Only PE import metadata is read from disk; disk code is not substituted for saved loaded code.",
        ],
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
