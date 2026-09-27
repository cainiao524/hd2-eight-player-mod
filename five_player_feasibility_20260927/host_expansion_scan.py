"""Reproduce bounded static host lifecycle disassembly from the pinned capture.

No process access, game execution, or binary modifications.
"""

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "research_handoff_20260927" / "indirect"))
from inspect_capture import Image, row

CAPTURE = Path(
    r"C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an"
    r"\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438"
)
ROOTS = (
    0x1088A30, 0x1088F00, 0x1088F30, 0x1088F80, 0x1089720,
    0x108D020, 0x108D130, 0x108D190, 0x108D3B0, 0x108D5E0,
    0x108D9F0,
)
EXTRA_ROOTS = (0x1089400, 0x108B560, 0x108B6B0)


def main():
    image = Image(CAPTURE)
    inventory = json.loads((HERE / "host_layout_inventory.json").read_text(encoding="utf-8"))
    methods = {int(item["root"], 16): item for item in inventory["methods"]}
    for root in ROOTS + EXTRA_ROOTS:
        source = methods.get(root)
        fragments = []
        if source:
            ranges = [(int(f["start"], 16), int(f["end"], 16), f["sha256"]) for f in source["fragments"]]
        else:
            i = image.fn_starts.index(root)
            ranges = []
            while i < len(image.functions) and image.root(image.functions[i][0])[0] == root:
                begin, end, _ = image.functions[i]
                ranges.append((begin, end, hashlib.sha256(image.read(begin, end - begin)).hexdigest()))
                i += 1
        for begin, end, expected_hash in ranges:
            raw = image.read(begin, end - begin)
            if hashlib.sha256(raw).hexdigest() != expected_hash:
                raise ValueError(f"Fragment digest mismatch {begin:#x}")
            decoded = list(image.md.disasm(raw, begin))
            if sum(ins.size for ins in decoded) != len(raw):
                raise ValueError(f"Incomplete disassembly {begin:#x}")
            if any(image.root(ins.address)[0] != root for ins in decoded):
                raise ValueError(f"Unwind root mismatch {begin:#x}")
            fragments.append({
                "range": [hex(begin), hex(end)], "sha256": expected_hash,
                "instructions": [row(ins) for ins in decoded],
            })
        result = {
            "capture_identity_sha256": image.report["capture_sha256"],
            "root": hex(root), "fragments": fragments,
            "limits": "Unwind-derived fragment bounds only; semantics require register/base provenance review.",
        }
        out = HERE / f"host_expansion_disasm_{root:x}.json"
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(out.name, sum(len(f["instructions"]) for f in fragments), "instructions")
    # 0x108b520 is a direct-call target with no captured unwind entry. Its two
    # return sites and following INT3 padding bound this small leaf candidate.
    # Do not call this an unwind-verified function boundary.
    begin, end = 0x108B520, 0x108B560
    raw = image.read(begin, end - begin)
    decoded = list(image.md.disasm(raw, begin))
    if sum(ins.size for ins in decoded) != len(raw):
        raise ValueError("Incomplete direct-target leaf disassembly")
    result = {
        "capture_identity_sha256": image.report["capture_sha256"],
        "root": hex(begin), "boundary_basis": "Direct call at 0x1089d58; two RETs and following INT3 padding; no unwind entry",
        "fragments": [{
            "range": [hex(begin), hex(end)],
            "sha256": hashlib.sha256(raw).hexdigest(),
            "instructions": [row(ins) for ins in decoded],
        }],
    }
    out = HERE / "host_expansion_disasm_108b520.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(out.name, len(decoded), "instructions")


if __name__ == "__main__":
    main()
