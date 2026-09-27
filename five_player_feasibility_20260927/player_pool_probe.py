"""Bounded, read-only xrefs for the captured player component statistic field."""

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research_handoff_20260927" / "indirect"))
from inspect_capture import Image, EXPECTED, row, require  # noqa: E402


FIELDS = (0xEA0894, 0xEA0890, 0xEA0888, 0xEA0898)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    im = Image(args.evidence)
    stat_xref = im.instruction(0x56E7EC)
    require(stat_xref is not None and stat_xref.mnemonic == "lea", "stat xref moved")
    require(stat_xref.address + stat_xref.size + stat_xref.operands[1].mem.disp == 0x2247520,
            "stat string target moved")
    stat_string = im.read(0x2247520, 96).split(b"\x00", 1)[0].decode("ascii")
    code = next(x for x in im.report["ranges"] if x["label"] == "code")
    blob = im.read(code["rva"], code["size"])
    matches = {}
    for field in FIELDS:
        needle = struct.pack("<I", field)
        start = 0
        rows = []
        while True:
            pos = blob.find(needle, start)
            if pos == -1:
                break
            at = code["rva"] + pos
            frag = im.containing(at)
            if frag:
                for ins in im.md.disasm(im.read(frag[0], frag[1] - frag[0]), frag[0]):
                    if ins.address <= at < ins.address + ins.size:
                        if field in [op.mem.disp for op in ins.operands if op.type == 3]:
                            entry = row(ins)
                            entry["root"] = hex(im.root(ins.address)[0])
                            rows.append(entry)
                        break
                    if ins.address > at:
                        break
            start = pos + 1
        matches[hex(field)] = rows
    result = {
        "source_sha256": EXPECTED,
        "game_sha256": im.report["game_sha256"],
        "stat_string": {"rva": "0x2247520", "value": stat_string},
        "stat_xref": {**row(stat_xref), "root": hex(im.root(stat_xref.address)[0])},
        "stat_read_field": "0xea0894",
        "fields": matches,
        "limits": [
            "These are direct disp32 references in unwind-covered code, not full dataflow.",
            "The diagnostic format capacity literal 4 alone does not prove the gameplay allocator limit.",
            "No game execution or writable-data capture.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
