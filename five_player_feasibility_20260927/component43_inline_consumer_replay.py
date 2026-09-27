"""Rebuild the remaining recognized component43 global consumer, offline only.

Reads the pinned capture and previous layout evidence; never opens a process.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row

ENTRY = 0x129FD00
GLOBAL = 0x3326AF0
KNOWN_REFERENCES = {
    0x51C094: 'registered append', 0x51C124: 'registered append',
    0x51C1A9: 'registered remove', 0x56846B: 'owner publisher',
    0x9BA43F: 'standalone record update', 0x9BA9FC: 'map-only helper',
    0x9BAAE4: 'separate append', 0x9BAB74: 'separate append',
    0x9BAC2A: 'separate remove', 0x12A02BB: 'inline record update',
}
GROUPS = {
    'zero_register': [0x129FD22],
    'roster_to_entity_id': [0x12A020A, 0x12A0213, 0x12A021E,
                           0x12A0225, 0x12A0230, 0x12A03CA, 0x12A03D2],
    'component_base_and_map': [0x12A02BB, 0x12A02CB, 0x12A02D1,
                              0x12A02D5, 0x12A02E2, 0x12A02E6,
                              0x12A02FA, 0x12A0307, 0x12A03F4,
                              0x12A03F9, 0x12A03FC, 0x12A0407],
    'entity_pointer_array': [0x12A0402],
    'record_address': [0x12A043E, 0x12A0445, 0x12A044E],
    'record_item_count': [0x12A0451, 0x12A0492, 0x12A04A4, 0x12A04B3],
    'derived_record_accesses': [0x12A0465, 0x12A048A, 0x12A04A0,
                                0x12A04AF, 0x12A04CB, 0x12A04D2],
    'per_record_item_limit': [0x12A047A, 0x12A047E],
    'other_sixteen_entry_scan': [0x12A040D, 0x12A0412, 0x12A0418,
                               0x12A0438, 0x12A043C],
    'component_base_lifetime_exit': [0x12A031E, 0x12A0325],
    'excluded_other_bases': [0x12A036B, 0x12A03AD, 0x12A064C, 0x12A0659],
}
CRITICAL = {
    0x129FD22: 'xor ebp, ebp',
    0x12A03D2: 'mov eax, dword ptr [rcx + 8]',
    0x12A03F4: 'mov eax, dword ptr [r15 + r8*8 + 4]',
    0x12A03FC: 'je 0x12a0316',
    0x12A0402: 'mov rcx, qword ptr [rdi + rax*8 + 0x68]',
    0x12A0407: 'mov r15d, eax',
    0x12A043E: 'imul r9, r15, 0x108',
    0x12A0445: 'lea rdx, [rdi + 0x88]',
    0x12A044E: 'add rdx, r9',
    0x12A0451: 'mov r8d, dword ptr [r9 + rdi + 0x188]',
    0x12A047A: 'cmp r8d, 0x10',
    0x12A048A: 'mov dword ptr [rdx + rax*8 + 0xc], 1',
    0x12A04A0: 'mov dword ptr [rdx + rcx*8 + 8], eax',
    0x12A04AF: 'mov qword ptr [rdx + rax*8], r11',
    0x12A04B3: 'inc dword ptr [r9 + rdi + 0x188]',
    0x12A04CB: 'inc dword ptr [rdx + rcx*8 + 0xc]',
    0x12A04D2: 'mov dword ptr [rdx + rcx*8 + 8], eax',
    0x12A0325: 'mov edi, ebp',
    0x12A03AD: 'cmp dword ptr [r9 + 0x88], ebp',
    0x12A064C: 'lea rcx, [rsp + 0x88]',
    0x12A0659: 'mov edi, dword ptr [rsp + 0x88]',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    target = Path(args.output)
    require(not target.exists(), 'refusing overwrite')
    prior = HERE / 'component43_lifecycle_evidence.json'
    prior_hash = sha(prior.read_bytes())
    require(prior_hash == 'e0e3f9fcfec8359eb3f777a7537a2c53d8635cc1c754d1318c34938b12e22cb9',
            'previous layout evidence changed')
    im = Image(args.evidence)
    cache = {}

    def decode(f):
        if f not in cache:
            ins = list(im.md.disasm(im.read(f[0], f[1] - f[0]), f[0]))
            require(sum(i.size for i in ins) == f[1] - f[0], 'incomplete decode')
            cache[f] = {i.address: i for i in ins}
        return cache[f]

    def pin(a):
        f = im.containing(a)
        require(f is not None and a in decode(f), 'unproven instruction boundary')
        return dict(**row(decode(f)[a]), root=hex(im.root(a)[0]))

    full = []
    body = {}
    all_bytes = b''
    for f in im.functions:
        if im.root(f[0])[0] == ENTRY:
            data = im.read(f[0], f[1] - f[0])
            all_bytes += data
            body.update(decode(f))
            full.append(dict(bounds=[hex(v) for v in f], sha256=sha(data),
                             instructions=[row(i) for i in decode(f).values()]))
    require(len(full) == 4 and len(body) == 687 and len(all_bytes) == 2821,
            'full-root coverage changed')
    for a, asm in CRITICAL.items():
        require(pin(a)['asm'] == asm, 'critical pin changed: ' + hex(a))
    require(all(a in body for group in GROUPS.values() for a in group), 'pin outside root')

    # Search only the stated RIP-relative MOV/LEA encodings, and validate each
    # match against an instruction decoded from its unwind fragment start.
    code = next(r for r in im.report['ranges'] if r['label'] == 'code')
    raw = im.read(code['rva'], code['size'])
    pattern = re.compile(b'(?=([\x40-\x4f]?[\x8b\x89\x8d][\x05\x0d\x15\x1d\x25\x2d\x35\x3d].{4}))', re.S)
    refs = {}
    for m in pattern.finditer(raw):
        b = m.group(1)
        a = code['rva'] + m.start()
        if a + len(b) + struct.unpack('<i', b[-4:])[0] != GLOBAL:
            continue
        f = im.containing(a)
        if f is None or a not in decode(f) or bytes(decode(f)[a].bytes) != b:
            continue
        refs[a] = pin(a)
    require(set(refs) == set(KNOWN_REFERENCES), 'recognized reference set changed')
    for a, label in KNOWN_REFERENCES.items():
        refs[a]['role'] = label

    # Normal direct control flow, calls assumed to return normally. This is
    # not a symbolic executor or interprocedural proof of input validity.
    edges = []
    external = []
    for a, i in body.items():
        if i.mnemonic.startswith('ret'):
            continue
        fall = a + i.size
        if i.mnemonic.startswith('j'):
            require(i.op_str.startswith('0x'), 'unexpected indirect jump')
            dst = int(i.op_str, 16)
            (edges if dst in body else external).append([hex(a), hex(dst)])
            if i.mnemonic == 'jmp':
                continue
        require(fall in body, 'unexpected fallthrough boundary: ' + hex(a))
        edges.append([hex(a), hex(fall)])
    require(not external, 'external normal branch')
    successors = {}
    for a, b in edges:
        successors.setdefault(int(a, 16), []).append(int(b, 16))
    seen, pending = set(), [0x12A02BB]
    stops = {0x12A0316, 0x12A031E}
    while pending:
        a = pending.pop()
        if a in seen or a in stops:
            continue
        seen.add(a)
        pending.extend(successors.get(a, []))
    writes_rdi = [a for a in seen if body[a].op_str.split(',')[0] in ('rdi', 'edi')]
    require(writes_rdi == [0x12A02BB], 'component base unexpectedly reassigned')

    result = dict(
        source_sha256=EXPECTED, capture_identity_sha256=im.report['capture_sha256'],
        prior_layout_sha256=prior_hash, root=hex(ENTRY), global_rva=hex(GLOBAL),
        full_functions=full, full_function_bytes=len(all_bytes), instruction_count=len(body),
        concatenated_fragment_sha256=sha(all_bytes),
        groups={name: [pin(a) for a in addresses] for name, addresses in GROUPS.items()},
        recognized_rip_references=[refs[a] for a in sorted(refs)],
        control_flow=dict(normal_edges=edges, region_entry='0x12a02bb',
                          region_stop_nodes=[hex(a) for a in sorted(stops)],
                          region_nodes=[hex(a) for a in sorted(seen)],
                          explicit_rdi_destinations=[hex(a) for a in writes_rdi]),
        relocation_obligations=[
            dict(group='entity_pointer_array', formula='S + ordinal*8 + 0x68'),
            dict(group='record_address', formula='S + ordinal*0x108 + 0x88'),
            dict(group='record_item_count', formula='record + 0x100'),
            dict(group='derived_record_accesses', formula='record + item*16 + {0,8,12}')],
        conclusions=[
            'This root performs an inline record update; redirecting only standalone helper 0x9ba430 misses it.',
            'The ID-to-map value selects the component ordinal; it is not a network index.',
            'The 0x10 comparisons concern inner lists, not the player/component record count.',
            'Record base and separately calculated record-count addresses must select the same relocated record.',
            'All ten references recognized by the bounded RIP MOV/LEA scan now have classified consumers or publisher roles.'],
        limits=[
            'The scan omits other encodings, raw pointers, propagated aliases, indirect accesses and uncovered code; it is not a complete relocation inventory.',
            'Full-root decode and normal CFG do not prove that the branch ran or that all callees return and preserve every input.',
            'RDI persistence uses explicit destinations in this path plus the normal x64 callee-preserved register convention.',
            'No new capture, process query, engine call, allocation, patch or multiplayer test.'])
    target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(target), sha256=sha(target.read_bytes()),
                          root_instructions=len(body), recognized_references=len(refs),
                          region_nodes=len(seen))))


if __name__ == '__main__':
    main()
