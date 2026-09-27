"""Bounded, read-only layout observations for ClientSynchronizer string roots."""
import argparse
import json
import sys
from pathlib import Path

from capstone.x86 import X86_OP_MEM

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, row

DISPS = {0xC8, 0xD0, 0x14, 0x150, 0x160, 0x170, 0x180,
         0x51A, 0x4D0, 0x510, 0x518}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--xrefs', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    image = Image(args.evidence)
    xrefs = json.loads(Path(args.xrefs).read_text(encoding='utf-8'))
    roots = {int(x['root'][0], 16) for x in xrefs['targets']['0x2262b00']['rip_references']}
    hits = []
    for fragment in image.functions:
        start, end, _ = fragment
        if not (0xB60000 <= start < 0xBC0000 or 0x1080000 <= start < 0x1092000):
            continue
        root = image.root(start)[0]
        if root not in roots:
            continue
        for ins in image.md.disasm(image.read(start, end-start), start):
            for op in ins.operands:
                if op.type == X86_OP_MEM and op.mem.disp in DISPS:
                    hit = row(ins)
                    hit.update(root=hex(root), fragment=[hex(start), hex(end)],
                               displacement=hex(op.mem.disp), base=ins.reg_name(op.mem.base),
                               index=ins.reg_name(op.mem.index), scale=op.mem.scale,
                               operand_size=op.size)
                    hits.append(hit)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps({'capture_sha256': image.report['capture_sha256'],
                                  'source_sha256': EXPECTED,
                                  'client_string_rva': '0x2262b00',
                                  'candidate_roots': [hex(x) for x in sorted(roots)],
                                  'method': 'ClientSynchronizer string candidate roots; operand displacement only, no pointer provenance',
                                  'hits': hits}, indent=2) + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
