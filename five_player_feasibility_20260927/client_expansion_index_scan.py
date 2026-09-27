"""Bounded offline scan for possible client peer index field readers."""
import argparse
import json
import sys
from pathlib import Path

from capstone.x86 import X86_OP_MEM

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, row

DISPS = {0x14, 0xE4, 0x104, 0x124, 0x144}
RANGES = [(0x1080000, 0x1092000), (0xB90000, 0xB93000)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    im = Image(a.evidence)
    hits = []
    for start, end, _ in im.functions:
        if not any(lo <= start < hi for lo, hi in RANGES):
            continue
        for ins in im.md.disasm(im.read(start, end-start), start):
            for op in ins.operands:
                if op.type == X86_OP_MEM and op.mem.disp in DISPS:
                    item = row(ins)
                    item.update(root=hex(im.root(start)[0]), fragment=[hex(start), hex(end)],
                                displacement=hex(op.mem.disp),
                                base=ins.reg_name(op.mem.base),
                                index=ins.reg_name(op.mem.index), scale=op.mem.scale,
                                operand_size=op.size, operand_access=op.access)
                    hits.append(item)
    result = {'capture_sha256': im.report['capture_sha256'], 'source_sha256': EXPECTED,
              'ranges': [[hex(a), hex(b)] for a,b in RANGES],
              'displacements': [hex(x) for x in sorted(DISPS)],
              'method': 'unwind-bounded nearby client code; operand displacement only, not base provenance',
              'hits': hits}
    path = Path(a.output)
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(path)


if __name__ == '__main__':
    main()
