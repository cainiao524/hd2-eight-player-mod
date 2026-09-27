"""Build an offline eight-player count/range patch plan for one fixed build.

The context retains player counts through eight. The existing filter extends
only a nonempty range ending at four through eight, retaining its lower bound.
This reuses four-player-eligible configurations for additional players; it does
not invent resources, scale weights, install patches or access a game process.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

TARGET_PROFILE = {
    'build': 25480438,
    'platform': 'Windows x64; offline profile only',
    'exe_sha256': 'f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06',
    'game_dll_sha256': '2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e',
}
# SizeOfImage from the fixed, fingerprinted capture report.
IMAGE_SIZE = 74727424
EVIDENCE_SHA256 = '8f0fad49d9f5bc7e95ffe8735007b59c302034704707602c8d8093ad795676e3'
CONTEXT_EVIDENCE_SHA256 = '04e16b4b9a301ba2fbd796528df6e53f9d3d8a25626cd459cc9f1329edd5d0d0'
SPECS = {
    'context': (0x94C9C0, 0x94D308, '7cc342fdc09d11b0bde285b179adcd4b5356df5df667be89bd7d5c6f76ca4ef2'),
    'filter': (0x94BE10, 0x94C44A, '0316a5430e599017d5a3251dd3b2f63e5bfad65190afb3fc10e19b55ccf81c9e'),
}
CLAMP_RVA, SPLICE_RVA = 0x94CA30, 0x94C07B
PASS_RVA, FAIL_RVA = 0x94C081, 0x94C085
TRAMPOLINE_SIZE = 51
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pointer(value, size, alignment, name):
    require(type(value) is int and value >= 0x10000 and value % alignment == 0,
            name + ' must be an aligned user-space address')
    require(type(size) is int and size > 0 and value + size <= 0x800000000000,
            name + ' range exceeds canonical user space')


def rel32(after, target):
    delta = target - after
    require(-(1 << 31) <= delta < (1 << 31), 'relative branch is outside rel32 reach')
    return struct.pack('<i', delta)


def validate_source(name, blob):
    start, end, digest = SPECS[name]
    require(type(blob) is bytes and len(blob) == end - start and sha(blob) == digest,
            name + ' source fingerprint mismatch')


def load_sources(evidence_path: Path, context_evidence_path: Path) -> dict[str, bytes]:
    result = {}
    for name, path, digest in (
        ('filter', evidence_path, EVIDENCE_SHA256),
        ('context', context_evidence_path, CONTEXT_EVIDENCE_SHA256),
    ):
        raw = Path(path).read_bytes()
        require(sha(raw) == digest, name + ' evidence fingerprint mismatch')
        blob = bytes.fromhex(json.loads(raw)['bodies'][hex(SPECS[name][0])]['bytes_hex'])
        validate_source(name, blob)
        result[name] = blob
    return result


def build(context_source: bytes, filter_source: bytes, *, game_base: int,
          trampoline_address: int) -> dict:
    validate_source('context', context_source)
    validate_source('filter', filter_source)
    pointer(game_base, IMAGE_SIZE, 0x1000, 'game_base')
    pointer(trampoline_address, TRAMPOLINE_SIZE, 16, 'trampoline_address')
    require(trampoline_address + TRAMPOLINE_SIZE <= game_base or
            game_base + IMAGE_SIZE <= trampoline_address,
            'trampoline overlaps the original game image')

    code = bytearray()
    branches = []

    def emit(raw):
        code.extend(raw)

    def branch(opcode, target):
        address = trampoline_address + len(code)
        emit(opcode + rel32(address + len(opcode) + 4, target))
        branches.append({'address': address, 'target_address': target,
                         'opcode_hex': opcode.hex()})

    original_compare = trampoline_address + 36
    # R15 points to record+F0. No scratch GPR, stack access, calls or stores.
    emit(bytes.fromhex('41837f0804'))          # cmp dword [r15+8],4
    branch(b'\x0f\x85', original_compare)    # jne original maximum
    emit(bytes.fromhex('41837f0404'))          # cmp dword [r15+4],4
    branch(b'\x0f\x87', original_compare)    # ja: preserve malformed empty range
    emit(bytes.fromhex('83f808'))              # cmp eax,8
    branch(b'\x0f\x87', game_base + FAIL_RVA)
    branch(b'\xe9', game_base + PASS_RVA)
    require(trampoline_address + len(code) == original_compare, 'internal label mismatch')
    emit(bytes.fromhex('413b4708'))            # original cmp eax,[r15+8]
    branch(b'\x0f\x87', game_base + FAIL_RVA)
    branch(b'\xe9', game_base + PASS_RVA)
    require(len(code) == TRAMPOLINE_SIZE, 'trampoline size mismatch')

    patches = []
    for name, at, before, after in (
        ('context', CLAMP_RVA, bytes.fromhex('b804000000'), bytes.fromhex('b808000000')),
        ('filter', SPLICE_RVA, bytes.fromhex('413b47087704'),
         b'\xe9' + rel32(game_base + SPLICE_RVA + 5, trampoline_address) + b'\x90'),
    ):
        source = context_source if name == 'context' else filter_source
        offset = at - SPECS[name][0]
        require(source[offset:offset + len(before)] == before and len(before) == len(after),
                'fixed patch instruction mismatch')
        patches.append({'source': name, 'rva': at, 'address': game_base + at,
                        'size_bytes': len(before), 'expected_hex': before.hex(),
                        'replacement_hex': after.hex()})

    return {
        'status': 'offline_native_player_count_candidate', 'installable': False,
        'game_execution': False, 'multiplayer_verified': False,
        'target_profile': dict(TARGET_PROFILE), 'game_base': game_base,
        'source_sha256': {'context': sha(context_source), 'filter': sha(filter_source)},
        'evidence_sha256': {'filter': EVIDENCE_SHA256, 'context': CONTEXT_EVIDENCE_SHA256},
        'code_address': trampoline_address, 'entry_address': trampoline_address,
        'size_bytes': len(code), 'code_hex': bytes(code).hex(), 'code_sha256': sha(code),
        'patches': patches, 'branches': branches,
        'known_regions': [
            {'name': 'original game image', 'address': game_base, 'size_bytes': IMAGE_SIZE},
            {'name': 'count range trampoline', 'address': trampoline_address, 'size_bytes': len(code)},
        ],
        'policy': {
            'context_player_count': 'unsigned clamp [1,8]; original raw 0 still becomes 1',
            'record_range': 'retain minimum; effective maximum is 8 iff maximum==4 and minimum<=4, otherwise retain maximum',
            'four_player_equivalence': 'For records with 1<=minimum<=maximum<=4, counts 5..8 select the same records as original count4, with other state/helper results equal',
            'other_ranges': 'Maximum values other than four keep their original meaning; unknown records do not imply coverage for all eight counts',
            'override': 'original tag/flag bypass of range eligibility remains unchanged',
            'tech_level': 'unchanged; separate [1,10] parameter and weight indexes are not player count',
        },
        'continuations': {'accepted': game_base + PASS_RVA, 'rejected': game_base + FAIL_RVA},
        'trampoline_contract': {
            'entry': 'original 94C07B state after the original unsigned lower-bound check',
            'preserved': 'all GPR/XMM registers and RSP; no writes, calls, allocation or stack accesses',
            'flags': 'changed comparisons; original continuations set AL then overwrite flags with COMISS at 94C087',
            'standalone_callable': False,
        },
        'installation_plan': None,
        'limits': [
            'Supplied source fingerprints do not verify a currently loaded game image',
            'The two code patches and trampoline are an offline plan; no executable memory allocation or patch application is provided',
            'Coordinated application/removal, instruction cache handling and valid Windows unwind for the trampoline remain required',
            'Runtime records, resource availability, output buffer capacity, callbacks and synchronized lifetimes remain unverified',
            'Reusing four-player-eligible configurations is a new candidate rule, not verified eight-player balancing',
            'FFFFFFFF from pending D=0 still clamps to 8; this does not resolve the earlier departure count/lifecycle defect',
            'No roster storage, pending/departure semantics, joining, character creation, transport or mission acceptance is completed by this component',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('evidence', 'context-evidence', 'addresses', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'refusing to overwrite output')
    sources = load_sources(args.evidence, args.context_evidence)
    result = build(sources['context'], sources['filter'],
                   **json.loads(args.addresses.read_bytes()))
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'status': result['status'],
                      'trampoline_size_bytes': result['size_bytes'], 'patches': len(result['patches'])}))


if __name__ == '__main__':
    main()
