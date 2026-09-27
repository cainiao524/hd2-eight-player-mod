"""Find boundary-validated disp32 memory references in the pinned code capture.

An offset match is a candidate only. Caller/dataflow inspection must establish
whether the base register points to the intended object.
"""
import argparse
import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research_handoff_20260927" / "indirect"))
from inspect_capture import EXPECTED, Image, row
from capstone.x86 import X86_OP_MEM, X86_REG_RIP


def scan_fields(im, offsets, ranges=()):
    code = next(r for r in im.report["ranges"] if r["label"] == "code")
    raw = im.read(code["rva"], code["size"])
    cache = {}
    result = {}
    candidates = defaultdict(set)
    for offset in sorted(set(offsets)):
        pattern = struct.pack("<i", offset)
        position = 0
        while True:
            position = raw.find(pattern, position)
            if position < 0:
                break
            candidates[offset].add(position)
            position += 1
        candidates[offset]  # Keep requested offsets with zero results.
    for lower, upper in ranges:
        if not (0 <= lower < upper <= 0x7fffffff and lower >> 16 == (upper-1) >> 16):
            raise ValueError("range must be nonnegative, end-exclusive, within one 64 KiB displacement band")
        pattern = struct.pack("<I", lower)[2:]
        position = 2
        while True:
            position = raw.find(pattern, position)
            if position < 0:
                break
            offset = struct.unpack_from("<i", raw, position-2)[0]
            if lower <= offset < upper:
                candidates[offset].add(position-2)
            position += 1
    for offset, positions in sorted(candidates.items()):
        matches = []
        uncovered = 0
        for position in sorted(positions):
            rva = code["rva"] + position
            fragment = im.containing(rva)
            if fragment is None:
                uncovered += 1
                continue
            if fragment not in cache:
                a, b, _ = fragment
                cache[fragment] = list(im.md.disasm(im.read(a, b-a), a))
            for ins in cache[fragment]:
                if ins.disp_size != 4 or ins.address + ins.disp_offset != rva:
                    continue
                for op in ins.operands:
                    if op.type == X86_OP_MEM and op.mem.disp == offset and op.mem.base != X86_REG_RIP:
                        item = row(ins)
                        item.update(fragment=[hex(v) for v in fragment], root=hex(im.root(ins.address)[0]),
                                    base=ins.reg_name(op.mem.base), index=ins.reg_name(op.mem.index),
                                    scale=op.mem.scale, operand_size=op.size, access=op.access)
                        matches.append(item)
        result[hex(offset)] = {"references":matches, "raw_matches_outside_unwind":uncovered}
    return {"source_sha256":EXPECTED, "capture_identity_sha256":im.report["capture_sha256"],
            "requested_ranges":[[hex(a),hex(b)] for a,b in ranges],
            "offsets":result, "limits":[
                "Only encoded disp32 memory references in captured unwind-covered code are included.",
                "RIP-relative references are excluded; base-register identity is unproven.",
                "Computed addresses, indexed layout changes, leaf functions without unwind, and uncaptured code can be omitted."]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence", required=True)
    p.add_argument("--offset", type=lambda v:int(v, 0), action="append", default=[])
    p.add_argument("--range", type=lambda v:int(v, 0), nargs=2, action="append", default=[],
                   metavar=("START", "END"), help="end-exclusive displacement range within one 64 KiB band")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    if not (a.offset or a.range):
        p.error("supply --offset or --range")
    path = Path(a.output)
    if path.exists():
        raise SystemExit("refusing to overwrite output: " + str(path))
    result = scan_fields(Image(a.evidence), a.offset, a.range)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    counts = {k:len(v["references"]) for k,v in result["offsets"].items() if v["references"]}
    print(json.dumps({"output":str(path), "displacements_with_references":len(counts),
                      "reference_count":sum(counts.values())}))


if __name__ == "__main__":
    main()
