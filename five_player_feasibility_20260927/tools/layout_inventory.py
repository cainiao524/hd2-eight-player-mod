"""Inventory native HostSynchronizer candidates in a pinned, offline capture.

This records observations, not a patch recipe. String references identify candidate
functions; identical displacement/immediate values do not establish object identity.
No process, game installation, or capture file is opened for writing.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research_handoff_20260927" / "indirect"))
from inspect_capture import EXPECTED, Image, row, scan, sha
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

HOST_STRING = 0x2263478
DISPLACEMENTS = {0x20, 0x58, 0x90, 0xC8, 0x100, 0x101, 0x102, 0x103,
                 0x808, 0x848, 0x888, 0x8C8, 0x908}


def printable_string(im, rva):
    try:
        data = im.read(rva, 256).split(b"\0", 1)[0]
    except ValueError:
        return None
    if len(data) >= 4 and all(32 <= x < 127 or x in (9, 10, 13) for x in data):
        return data.decode("ascii")
    return None


def build_inventory(im):
    assert im.read(HOST_STRING, 17) == b"HostSynchronizer\0"
    xrefs = scan(im, {HOST_STRING})
    references = xrefs["targets"][hex(HOST_STRING)]["rip_references"]
    roots = {int(ref["root"][0], 16) for ref in references}
    grouped = defaultdict(list)
    for fragment in im.functions:
        root = im.root(fragment[0])[0]
        if root in roots:
            grouped[root].append(fragment)
    methods = []
    for root in sorted(roots):
        method = {
            "root": hex(root),
            "category": "candidate from HostSynchronizer string reference; ownership unproven",
            "host_string_refs": [ref["rva"] for ref in references if int(ref["root"][0], 16) == root],
            "fragments": [], "strings": [], "layout_candidates": [],
            "count_candidates": [], "direct_calls": [],
        }
        for start, end, unwind in grouped[root]:
            raw = im.read(start, end-start)
            instructions = list(im.md.disasm(raw, start))
            decoded = sum(ins.size for ins in instructions)
            method["fragments"].append({"start":hex(start), "end":hex(end),
                "unwind":hex(unwind), "sha256":sha(raw), "decoded_bytes":decoded,
                "undecoded_bytes":len(raw)-decoded})
            for ins in instructions:
                for op in ins.operands:
                    if op.type == X86_OP_MEM:
                        mem = op.mem
                        if mem.base == X86_REG_RIP:
                            target = ins.address + ins.size + mem.disp
                            text = printable_string(im, target)
                            if text:
                                method["strings"].append({"rva":hex(ins.address), "target":hex(target), "text":text})
                        elif mem.disp in DISPLACEMENTS:
                            item = row(ins)
                            item.update(displacement=hex(mem.disp), base=ins.reg_name(mem.base),
                                        index=ins.reg_name(mem.index), scale=mem.scale, access=op.access,
                                        operand_size=op.size)
                            method["layout_candidates"].append(item)
                    elif op.type == X86_OP_IMM:
                        if op.imm in (4, 8, 0x38, 0x40):
                            method["count_candidates"].append(row(ins))
                        if ins.mnemonic == "call":
                            method["direct_calls"].append({"rva":hex(ins.address), "target":hex(op.imm)})
        methods.append(method)
    return {
        "schema_version":1, "source_sha256":EXPECTED,
        "capture_identity_sha256":im.report["capture_sha256"],
        "host_string_rva":hex(HOST_STRING), "validated_string_xref_count":len(references),
        "candidate_method_count":len(methods), "methods":methods,
        "limits":[
            "Only candidate methods with a recognized direct RIP MOV/LEA reference to the logger name are included.",
            "Methods without that logger name, indirect calls, and code outside captured unwind ranges can be omitted.",
            "Unwind roots group code fragments; they do not identify C++ class ownership.",
            "Same immediate or displacement values may describe unrelated objects; validate dataflow before any transformation.",
            "No heap, writable global values, networking outcomes, or gameplay execution are observed.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise SystemExit("refusing to overwrite output: " + str(output))
    result = build_inventory(Image(args.evidence))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output":str(output), "candidate_methods":result["candidate_method_count"],
                      "string_xrefs":result["validated_string_xref_count"]}))


if __name__ == "__main__":
    main()
