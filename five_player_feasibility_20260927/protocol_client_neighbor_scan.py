"""Read-only scan for potential client peer-record and adjacent field uses."""
import argparse
import json
import sys
from pathlib import Path

from capstone.x86 import X86_OP_MEM

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, row

DISPS = {0xC8, 0xD0, 0x150, 0x160, 0x170, 0x180}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    im = Image(args.evidence)
    hits = []
    for start, end, _ in im.functions:
        if not 0x1080000 <= start < 0x1092000:
            continue
        for ins in im.md.disasm(im.read(start, end-start), start):
            for op in ins.operands:
                if op.type == X86_OP_MEM and op.mem.disp in DISPS:
                    item = row(ins)
                    item.update(root=hex(im.root(start)[0]), fragment=[hex(start), hex(end)],
                                displacement=hex(op.mem.disp), base=ins.reg_name(op.mem.base),
                                index=ins.reg_name(op.mem.index), scale=op.mem.scale,
                                operand_size=op.size)
                    hits.append(item)
    out = Path(args.output)
    if out.exists():
        raise FileExistsError(out)
    out.write_text(json.dumps({'capture_sha256': im.report['capture_sha256'],
                               'source_sha256': EXPECTED,
                               'scan_range': ['0x1080000', '0x1092000'],
                               'method': 'all captured unwind fragments in range; displacement match only, no pointer provenance',
                               'hits': hits}, indent=2) + '\n', encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
