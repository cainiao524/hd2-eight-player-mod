"""Read-only scan of an address-bounded code neighborhood for +0x14 accesses."""
import argparse
import json
from pathlib import Path
import sys

from capstone.x86_const import X86_OP_MEM

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import Image, EXPECTED, row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--start', required=True, type=lambda x: int(x, 0))
    parser.add_argument('--end', required=True, type=lambda x: int(x, 0))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    image = Image(args.evidence)
    hits = []
    for fragment in image.functions:
        start, end, _ = fragment
        if not args.start <= start < args.end:
            continue
        for ins in image.md.disasm(image.read(start, end - start), start):
            for index, op in enumerate(ins.operands):
                if op.type == X86_OP_MEM and op.mem.disp == 0x14:
                    item = row(ins)
                    item.update({
                        'root': hex(image.root(start)[0]),
                        'fragment': [hex(start), hex(end)],
                        'operand_index': index,
                        'operand_access': op.access,
                        'memory_base': ins.reg_name(op.mem.base),
                        'memory_index': ins.reg_name(op.mem.index),
                        'memory_scale': op.mem.scale,
                        'operand_size': op.size,
                    })
                    hits.append(item)
    result = {
        'capture_sha256': image.report['capture_sha256'],
        'source_sha256': EXPECTED,
        'scan_range': [hex(args.start), hex(args.end)],
        'method': 'all captured unwind fragments whose start lies in scan range; +0x14 memory displacement only, not pointer provenance',
        'hits': hits,
    }
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
