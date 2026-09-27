"""Offline-only checks of roster entries and missing direct dispatch edges.

No process APIs or game-installation reads. Source bytes are fingerprint-pinned by
inspect_capture.Image. The narrow write walk is an inventory, not full dataflow.
"""
import argparse
import json
import re
import struct
import sys
from pathlib import Path

import capstone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research_handoff_20260927" / "indirect"))
from inspect_capture import EXPECTED, Image, require, row, sha

ENTRIES = (0x540850, 0x540920, 0x540A40, 0x60CA80, 0x60CBA0, 0x60CEA0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--global-xrefs", type=Path, default=Path(__file__).with_name("player_roster_global_xrefs.json"))
    a = p.parse_args()
    require(not a.output.exists(), "refusing overwrite")
    im = Image(a.evidence)
    entries = []
    spans = []
    for address in ENTRIES:
        fn = im.containing(address)
        require(fn[0] == address and im.root(address) == fn, "entry is not independent unwind root")
        spans.append(fn[:2])
        decoded = list(im.md.disasm(im.read(fn[0], fn[1] - fn[0]), fn[0]))
        entries.append({
            "entry": hex(address), "fragment": list(map(hex, fn)),
            "unwind_header": im.read(fn[2], 4).hex(),
            "preceding_32_bytes": im.read(address - 32, 32).hex(),
            "function_sha256": sha(im.read(fn[0], fn[1] - fn[0])),
            "instructions": [row(i) for i in decoded],
        })
    area = next(x for x in im.report["ranges"] if x["label"] == "code")
    code = im.read(area["rva"], area["size"])
    near = []
    for match in re.finditer(rb"[\xe8\xe9]|\x0f[\x80-\x8f]", code):
        pos = match.start()
        n = len(match[0]) + 4
        if pos + n > len(code):
            continue
        target = area["rva"] + pos + n + struct.unpack_from("<i", code, pos + len(match[0]))[0]
        for start, end in spans:
            if start <= target < end:
                near.append({"site": hex(area["rva"] + pos), "target": hex(target), "entry": hex(start)})
    # Even unvalidated byte candidates are kept. Zero does not depend on unwind
    # coverage of the caller or on a disassembler recognizing that caller.
    short = []
    for start, end in spans:
        for site in range(start - 130, end + 128):
            two = im.read(site, 2)
            if two[0] not in (0xEB, 0xE3) and not 0x70 <= two[0] <= 0x7F:
                continue
            target = site + 2 + struct.unpack("b", two[1:])[0]
            if not start <= target < end or start <= site < end:
                continue
            instruction = im.instruction(site)
            destination_instruction = im.instruction(target)
            short.append({"site": hex(site), "target": hex(target), "entry": hex(start),
                          "validated_instruction": row(instruction) if instruction else None,
                          "target_instruction": row(destination_instruction) if destination_instruction else None})
    xraw = a.global_xrefs.read_bytes()
    xrefs = json.loads(xraw)
    require(xrefs["capture_sha256"] == im.report["capture_sha256"], "xref capture mismatch")
    fragments = sorted({im.containing(int(x["rva"], 16)) for x in xrefs["targets"]["0x3326468"]["rip_references"]})
    writes = []
    for fragment in fragments:
        instructions = list(im.md.disasm(im.read(fragment[0], fragment[1] - fragment[0]), fragment[0]))
        for idx, load in enumerate(instructions):
            if load.mnemonic != "mov" or len(load.operands) != 2:
                continue
            dst, src = load.operands
            if dst.type != capstone.x86.X86_OP_REG or src.type != capstone.x86.X86_OP_MEM:
                continue
            if src.mem.base != capstone.x86.X86_REG_RIP or load.address + load.size + src.mem.disp != 0x3326468:
                continue
            for cur in instructions[idx + 1:idx + 180]:
                if cur.operands and cur.operands[0].type == capstone.x86.X86_OP_MEM:
                    mem = cur.operands[0]
                    if (mem.mem.base == dst.reg and mem.mem.disp in (0x80, 0x84, 0x88, 0xE8)
                            and mem.access & capstone.CS_AC_WRITE):
                        writes.append({"load": row(load), "site": row(cur), "root": hex(im.root(cur.address)[0])})
                if dst.reg in cur.regs_access()[1]:
                    break
    result = {
        "source_sha256": EXPECTED, "capture_sha256": im.report["capture_sha256"],
        "runtime_verified": False, "code_range": area, "entries": entries,
        "near_branch_raw_candidates": near,
        "external_short_branch_raw_candidates": short,
        "global_xrefs_file_sha256": sha(xraw), "global_xref_fragment_count": len(fragments),
        "narrow_global_write_inventory": writes,
        "registry_consumer_pins": [
            {**row(im.instruction(address)), "root": hex(im.root(address)[0])}
            for address in (
                0xB27564, 0xB27568, 0xB2756F, 0xB27581,
                0xB275F6, 0xB27609, 0xB27626, 0xB27639,
                0xB27656, 0xB27669, 0xB27699, 0xB276B6,
                0xB83420, 0xB83422, 0xB83429, 0xB8342C,
                0xB8344C, 0xB83452, 0xB83464, 0xB83468, 0xB8346C, 0xB83473,
                0xB83557, 0xB83562, 0xB8356C, 0xB83574, 0xB8357C,
                0xB835BC, 0xB835C0, 0xB835C8,
                0xB8364B, 0xB83657, 0xB8365B, 0xB83665,
                0xB836E1, 0xB836E5, 0xB8370F, 0xB83719,
                0xB83785, 0xB8378F, 0xB83797, 0xB837A0,
                0xB8387D, 0xB8388F, 0xB838FA, 0xB8390A, 0xB8390E,
                0xB83A71, 0xB83A7E,
                0xB83B05, 0xB83B16, 0xB83B7F, 0xB83B82,
                0xB54E58, 0xB54E5B, 0xB55003, 0xB5500D, 0xB5501C,
                0xB5504A, 0xB5504E, 0xB55057, 0xB550F7, 0xB550FB,
            )
        ],
        "limits": [
            "No writable image, heap, process, disk executable, or runtime dispatch data was read.",
            "Near-branch byte patterns cover E8/E9 and 0F80..0F8F rel32 only; register-indirect, memory-indirect, encoded or computed targets remain unresolved.",
            "The write inventory walks at most 179 following linear instructions using only the original loaded base register, ending at an explicit register write; it does not follow aliases, prove control-flow reachability, or model callees. It is not an exhaustive writer list.",
            "An independent unwind root and padding establish a statically separated implementation, not runtime reachability or public API identity.",
        ],
    }
    a.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"entries": len(entries), "near_candidates": len(near), "short_candidates": len(short),
                      "global_xref_fragments": len(fragments), "write_sites": len(writes)}))


if __name__ == "__main__":
    main()
