"""Fingerprint the captured readonly wrapper-pointer run containing 0xBABA80."""
import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, sha

START = 0x214C2E0
TARGET = 0xBABA80


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    im = Image(a.evidence)
    code = next(x for x in im.report['ranges'] if x['label'] == 'code')
    pointers = []
    while True:
        at = START + len(pointers) * 8
        ptr = struct.unpack('<Q', im.read(at, 8))[0]
        rva = ptr - im.base
        if not code['rva'] <= rva < code['rva'] + code['size']:
            break
        pointers.append(rva)
    hits = [i for i, x in enumerate(pointers) if x == TARGET]
    out = {'capture_sha256': im.report['capture_sha256'], 'source_sha256': EXPECTED,
           'range': [hex(START), hex(START + len(pointers)*8)],
           'sha256': sha(im.read(START, len(pointers)*8)),
           'entry_count': len(pointers),
           'all_code_addresses_in_ascending_order': all(x < y for x, y in zip(pointers, pointers[1:])),
           'first_rva': hex(pointers[0]), 'last_rva': hex(pointers[-1]),
           'target': hex(TARGET), 'target_entry_indices': hits,
           'target_pointer_rvas': [hex(START + i*8) for i in hits],
           'target_neighbors': [{"index":i,"pointer_rva":hex(START+i*8),"function_rva":hex(pointers[i])}
                                for i in range(max(0,hits[0]-3), min(len(pointers),hits[0]+4))],
           'next_qword': hex(ptr),
           'limits': ['No hash-to-entry mapping is present in this pointer run.',
                      'Pointer-run membership does not prove a callback is registered at runtime.',
                      'Writable state and engine-side dispatch were not captured.']}
    path = Path(a.output)
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
    print(path)


if __name__ == '__main__':
    main()
