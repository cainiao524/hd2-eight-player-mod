"""Locate one RPC identifier in all pinned captured ranges without executing the game."""
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
    p.add_argument('--value', type=lambda s: int(s, 0), default=0x4804FCF4)
    a = p.parse_args()
    im = Image(a.evidence)
    needle = struct.pack('<I', a.value)
    hits = []
    for area in im.report['ranges']:
        data = im.read(area['rva'], area['size'])
        start = 0
        while (pos := data.find(needle, start)) >= 0:
            rva = area['rva'] + pos
            item = {'rva': hex(rva), 'range': area['label']}
            if area['label'] == 'code':
                fragment = im.containing(rva)
                if fragment:
                    for ins in im.md.disasm(im.read(fragment[0], fragment[1]-fragment[0]), fragment[0]):
                        if ins.address <= rva < ins.address + ins.size:
                            item['containing_instruction'] = row(ins)
                            break
            hits.append(item)
            start = pos + 1
    out = Path(a.output)
    if out.exists():
        raise FileExistsError(out)
    out.write_text(json.dumps({'capture_sha256': im.report['capture_sha256'],
                               'source_sha256': EXPECTED,
                               'value': hex(a.value), 'little_endian_bytes': needle.hex(),
                               'ranges_scanned': [x['label'] for x in im.report['ranges']],
                               'hits': hits}, indent=2) + '\n', encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
