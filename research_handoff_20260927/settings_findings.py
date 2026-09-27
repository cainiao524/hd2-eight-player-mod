"""Pinned offline evidence: effective mode and constructor settings consumers.

No process access, runtime writer, deployment, or candidate profile is present.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

PINS = {
    0x515113: '8b4108',
    0x515122: '4c8b1daf15e102',
    0x5151aa: '8b4104',
    0x5151b2: '4869c068020000',
    0x5151b9: '490383d0000000',
    0x5151c5: '498b0a',
    0x5151cc: 'e93ffaffff',
    0x615a3e: 'e8bdf6efff',
    0x615a53: '4c8be8',
    0x615afd: 'ba08000000',
    0x615b15: '498b5d28',
    0x615b19: 'e8e2191701',
    0x615b1e: '83f801',
    0x615b21: '751b',
    0x615b23: '418b8540020000',
    0x615b2c: '440f45e0',
    0x615b30: '498b8548020000',
    0x615b3a: '480f45d8',
    0x615bbf: '4885db',
    0x615bc2: '0f843a090000',
    0x6165c2: 'c6453801',
    0x13a99e2: '450f57f6',
    0x13a9c49: '66428994663c200000',
    0x13a9c95: 'f30f107020',
    0x13a9d0b: 'ba07000000',
    0x13a9d10: 'e8ebd73d00',
    0x13a9d15: '83f801',
    0x13a9d18: '7522',
    0x13a9d1e: 'e81d00c3ff',
    0x13a9d26: 'e8d5b316ff',
    0x13a9d2b: 'f30f10803c020000',
    0x13a9d33: '410f2fc6',
    0x13a9d37: '7603',
    0x13a9d39: '0f28f0',
    0x13a9d96: '488b4778',
    0x13a9d9a: '4869d1a8000000',
    0x13a9da1: 'f30f59740250',
    0x13a9db2: 'f3410f59752c',
    0x13a9e55: '498b4608',
    0x13a9e59: 'f30f594008',
    0x13a9e5e: 'f30f5910',
    0x13a9e62: 'f30f594804',
    0x13a9e75: 'f2410f1184374c300000',
    0x13a9e7f: '4189843754300000',
}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    sys.path.insert(0, str(args.repo / 'tools'))
    import generation_research as study
    folder = args.repo / 'build/existing-code-evidence-25480438'
    source = study.load_code_evidence(folder)
    report = json.loads((folder / 'capture-report.json').read_bytes())
    image = study.CapturedImage(report, (folder / 'captured-data.bin').read_bytes())
    dis = Cs(CS_ARCH_X86, CS_MODE_64)
    # Each known instruction above is also checked against a continuous decode
    # starting at its reviewed native function/fragment boundary.
    boundaries = {}
    for start, length in ((0x515100, 0xD1), (0x615A00, 0xBD5 - 0xA00),
                          (0x616502, 0x115), (0x13A9830, 0x1000)):
        boundaries.update({i.address: bytes(i.bytes) for i in dis.disasm(image.read(start, length), start)})
    checked = []
    for rva, expected_hex in PINS.items():
        expected = bytes.fromhex(expected_hex)
        actual = image.read(rva, len(expected))
        if actual != expected or boundaries.get(rva) != expected:
            raise ValueError(f'instruction/boundary mismatch at {rva:#x}')
        insn = next(dis.disasm(actual, rva))
        checked.append({'rva': hex(rva), 'bytes': actual.hex(),
                        'sha256': hashlib.sha256(actual).hexdigest(),
                        'instruction': insn.mnemonic + ' ' + insn.op_str})
    result = {
        'schema_version': 1, 'status': 'UNBOUND', 'field_binding': None,
        'source': source['fingerprints'], 'build_id': source['build_id'],
        'capture_sha256': source['capture_sha256'], 'instructions': checked,
        'findings': [
            {'id': 'effective_mode_nonzero_override', 'structure': 'resolved 0x268-byte weapon settings',
             'fields': {'0x28': 'u64 base entity resource', '0x240': 'u32 alternate projectile type',
                        '0x248': 'u64 alternate entity resource'},
             'dataflow': 'Query 0x1787500(weapon ID, 8); only return 1 enables nonzero alternate fields. Zero alternate values retain earlier selections. Effective entity zero branches to 0x616502.',
             'limit': 'This proves local instruction-level selection only. Player ownership, attachment precedence, query state lifecycle and actual weapon participation remain unproved.'},
            {'id': 'resolved_setting_23c_velocity_consumer', 'field_offset': '0x23c', 'width': 4,
             'instruction_type': 'scalar float32 load',
             'dataflow': 'After initial flags are stored at 0x13a9c49, query 0x1787500(ID, 7). If return is 1 and settings+0x23c > 0, replace XMM6. Multiply by separate manager record+0x50 and options+0x2c, then multiply all three descriptor direction components into an initial velocity term. Later 0x13a9e87..0x13a9edf can add XYZ velocity from non-null options+0x20.',
             'decision': 'This consumer controls launch-speed scaling and cannot establish a self-hit-only change preserving velocity; it does not supply options+0x18. Equal values, zero factors and floating-point rounding can leave the result unchanged.',
             'limit': '0x515100 can return a manager record or fall back to a base resource. No claim of private ownership, exhaustive field consumers or current runtime ownership.'},
            {'id': 'distinct_manager_arrays',
             'dataflow': '0x5151b2/1b9 selects manager+0xd0 with stride 0x268; 0x13a9d96/9d9a selects manager+0x78 with stride 0xa8.',
             'decision': 'Sharing a manager pointer does not make these the same record or establish local ownership.'},
        ],
        'common_solution_found': False, 'runtime_writes': 0,
        'gameplay_verified': False, 'lifecycle_verified': False,
    }
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps({'ok': True, 'pinned_instructions': len(checked), 'status': result['status']}))

if __name__ == '__main__':
    main()
