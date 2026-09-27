"""Bounded scan of HostSynchronizer candidate functions for member +0x14 accesses."""
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
    parser.add_argument('--inventory', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    image = Image(args.evidence)
    inventory = json.loads(Path(args.inventory).read_text(encoding='utf-8'))
    if inventory['capture_identity_sha256'] != image.report['capture_sha256']:
        raise ValueError('inventory capture identity mismatch')
    result = {
        'capture_sha256': image.report['capture_sha256'],
        'source_sha256': EXPECTED,
        'scope': 'unwind-bounded fragments of HostSynchronizer candidate roots from host_layout_inventory.json',
        'roots': [],
    }
    for method in inventory['methods']:
        matches = []
        for fragment in method['fragments']:
            start, end = int(fragment['start'], 16), int(fragment['end'], 16)
            for ins in image.md.disasm(image.read(start, end - start), start):
                for index, op in enumerate(ins.operands):
                    if op.type == X86_OP_MEM and op.mem.disp == 0x14:
                        item = row(ins)
                        item.update({
                            'fragment': [hex(start), hex(end)],
                            'operand_index': index,
                            'operand_access': op.access,
                            'memory_base': ins.reg_name(op.mem.base),
                            'memory_index': ins.reg_name(op.mem.index),
                            'memory_scale': op.mem.scale,
                            'operand_size': op.size,
                        })
                        matches.append(item)
        if matches:
            result['roots'].append({
                'root': method['root'],
                'strings': method.get('strings', []),
                'matches': matches,
            })
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
