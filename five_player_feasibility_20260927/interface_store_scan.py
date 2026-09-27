"""Scan the pinned code capture for direct RIP-relative stores to interface globals."""
import json
import re
import struct
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str((SCRIPT_DIR / '../research_handoff_20260927/indirect').resolve()))
from inspect_capture import Image, row  # noqa: E402

EVIDENCE = Path(
    r'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438'
)
TARGETS = set(range(0x3326300, 0x3326349, 8))


PATTERN = re.compile(
    rb'[\x40-\x4f]?[\x89\x8d\x87\xc7\xc6][\x05\x0d\x15\x1d\x25\x2d\x35\x3d]'
)


def main():
    im = Image(EVIDENCE)
    area = next(x for x in im.report['ranges'] if x['label'] == 'code')
    start = area['rva']
    data = im.read(start, area['size'])
    hits = []
    for match in PATTERN.finditer(data):
        pos = match.start()
        prefix = 1 if 0x40 <= data[pos] <= 0x4F else 0
        op = pos + prefix
        if op + 6 > len(data):
            continue
        opcode = data[op]
        length = prefix + (10 if opcode == 0xC7 else 7 if opcode == 0xC6 else 6)
        if pos + length > len(data):
            continue
        target = start + pos + length + struct.unpack_from('<i', data, op + 2)[0]
        if target not in TARGETS:
            continue
        rva = start + pos
        ins = im.instruction(rva)
        if ins is None or ins.size != length:
            continue
        hit = row(ins)
        kind = {0x89: 'store', 0x8D: 'address', 0x87: 'exchange', 0xC7: 'immediate_store', 0xC6: 'byte_store'}[opcode]
        hit.update(kind=kind, target=hex(target), fragment=[hex(x) for x in im.containing(rva)], root=[hex(x) for x in im.root(rva)])
        hits.append(hit)
    out = {
        'source_sha256': {name: __import__('hashlib').sha256(content).hexdigest() for name, content in im.files.items()},
        'targets': [hex(x) for x in sorted(TARGETS)],
        'scope': 'Only REX/non-REX MOV register stores, LEA address-taking, XCHG, and C6/C7 immediate stores with RIP-relative disp32 are searched; decoded instruction boundaries are verified against captured unwind fragments.',
        'hits': hits,
        'limits': [
            'Computed-address stores, arbitrary instruction forms, uncaptured code, import callbacks, and EXE writes are not excluded by no hit.',
            'The writable global data section is absent from this capture.',
        ],
    }
    dest = SCRIPT_DIR / 'interface_store_refs.json'
    dest.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
    print(dest)
    print(len(hits))


if __name__ == '__main__':
    main()
