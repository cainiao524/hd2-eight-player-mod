"""Validated RIP references into a bounded readonly callback-table neighborhood."""
import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, row


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--start', type=lambda s: int(s, 0), default=0x214C000)
    p.add_argument('--end', type=lambda s: int(s, 0), default=0x214CA00)
    a = p.parse_args()
    im = Image(a.evidence)
    code = next(x for x in im.report['ranges'] if x['label'] == 'code')
    b = im.read(code['rva'], code['size'])
    hits = []
    for pos in range(len(b) - 7):
        rva = code['rva'] + pos
        prefix = 1 if 0x40 <= b[pos] <= 0x4f else 0
        if b[pos + prefix] not in (0x8d, 0x8b, 0x89):
            continue
        if b[pos + prefix + 1] & 0xc7 != 0x05:
            continue
        size = 6 + prefix
        target = rva + size + struct.unpack_from('<i', b, pos + prefix + 2)[0]
        if a.start <= target < a.end:
            ins = im.instruction(rva)
            if ins is None or ins.size != size:
                continue
            item = row(ins)
            item.update(target=hex(target), fragment=[hex(x) for x in im.containing(rva)],
                        root=[hex(x) for x in im.root(rva)])
            hits.append(item)
    output = Path(a.output)
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps({'capture_sha256': im.report['capture_sha256'],
                                  'source_sha256': EXPECTED,
                                  'target_range': [hex(a.start), hex(a.end)],
                                  'method': 'RIP LEA/MOV code references, unwind instruction-boundary validated',
                                  'hits': hits}, indent=2) + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
