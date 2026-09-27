"""Offline component 43 layout, compaction, owner aliases and record consumers.

Only reads the previously pinned capture. No process or game invocation.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'research_handoff_20260927'/'indirect'))
from inspect_capture import EXPECTED, Image, require, row

ROOTS = [0x51C080, 0x51C110, 0x51C1A0, 0x9BA430, 0x9BA6C0,
         0x9BA8D0, 0x9BA9F0, 0x9BAAD0, 0x9BAB60, 0x9BAC20, 0x172F790]
TABLES = [0xF0B6F0, 0xF0C110, 0xF0CB30, 0xF0D550, 0xF0DF70,
          0xF0E990, 0xF0F3B0, 0xF0FDD0, 0xF107F0, 0xF11210]
REGISTERED = {0xF0B6F0: 0x51C080, 0xF0C110: 0x51C110, 0xF0E990: 0x51C1A0}
SPANS = {
    'constructor_owner_and_global_aliases': [(0xFDA352, 0xFDA37A), (0x551B7A, 0x551B82),
                                            (0x568236, 0x568249), (0x568464, 0x568480)],
    'owner_inline_constructor_and_next_member': [(0x551D3C, 0x551D3F), (0x55285D, 0x5528D9)],
    'owner_direct_update_path': [(0xFDAEED, 0xFDAEF0), (0xFDAF4B, 0xFDAF54),
                                (0x57128D, 0x571290), (0x5715CD, 0x5715DC)],
    'owner_direct_count_sync_path': [(0xFDC78F, 0xFDC792), (0xFDC7A3, 0xFDC7AC),
                                    (0x576D0D, 0x576D10), (0x577E7B, 0x577E8A)],
    'owner_diagnostic': [(0x56A950, 0x56A957), (0x56B3DF, 0x56B405)],
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    target = Path(args.output)
    require(not target.exists(), 'refusing overwrite')
    im = Image(args.evidence)
    cache = {}

    def decode(fragment):
        if fragment not in cache:
            a, b, _ = fragment
            ins = list(im.md.disasm(im.read(a, b-a), a))
            require(sum(i.size for i in ins) == b-a, 'incomplete decode')
            cache[fragment] = {i.address:i for i in ins}
        return cache[fragment]

    def pin(address):
        fragment = im.containing(address)
        require(fragment is not None and address in decode(fragment), 'unproven instruction boundary')
        return dict(**row(decode(fragment)[address]), root=hex(im.root(address)[0]),
                    fragment=[hex(x) for x in fragment])

    fragments_by_root = {entry: [] for entry in ROOTS}
    for fragment in im.functions:
        root = im.root(fragment[0])[0]
        if root in fragments_by_root:
            fragments_by_root[root].append(fragment)
    functions = []
    for entry in ROOTS:
        fragments = []
        for f in fragments_by_root[entry]:
            fragments.append(dict(bounds=[hex(x) for x in f], sha256=sha(im.read(f[0], f[1]-f[0])),
                                  instructions=[row(i) for i in decode(f).values()]))
        require(fragments and int(fragments[0]['bounds'][0], 16) == entry, 'missing function entry')
        functions.append(dict(entry=hex(entry), fragments=fragments))

    # The entry is established by a captured direct call, and the complete
    # initializer is exactly RIP-LEA/RCX-store pairs followed by RET.
    init = im.read(0x556D90, 0x55E1E3-0x556D90)
    require(sha(init) == '22c57829a02419f7e8689a6e2ca501c353fa5362904c6b49e108689d842c91b2', 'initializer changed')
    require(pin(0x568239)['asm'] == 'call 0x556d90', 'initializer entry changed')
    assignments = {}
    for at in range(0, len(init)-1, 14):
        b = init[at:at+14]
        require(b[:3] == b'\x48\x8d\x05' and b[7:10] == b'\x48\x89\x81', 'initializer pattern changed')
        slot = struct.unpack_from('<i', b, 10)[0]
        require(slot not in assignments, 'duplicate slot')
        assignments[slot] = dict(target=hex(0x556D90+at+7+struct.unpack_from('<i', b, 3)[0]),
                                 instructions=[row(i) for i in im.md.disasm(b, 0x556D90+at)])
    require(len(assignments) == 2127 and init[-1] == 0xC3, 'initializer coverage changed')
    registrations = []
    for table in TABLES:
        item = assignments.get(table+43*8)
        require((item is not None) == (table in REGISTERED), 'component assignment set changed')
        if item:
            require(int(item['target'], 16) == REGISTERED[table], 'callback changed')
        registrations.append(dict(table_base=hex(table), slot=hex(table+43*8), assignment=item))

    owner = {}
    for name, spans in SPANS.items():
        owner[name] = []
        for a, b in spans:
            f = im.containing(a)
            require(f is not None and b <= f[1] and a in decode(f), 'owner span start/bounds changed')
            selected = [i for r, i in decode(f).items() if a <= r < b]
            require(sum(i.size for i in selected) == b-a, 'owner span end unaligned')
            owner[name].extend(pin(i.address) for i in selected)
    critical = {
        0x568464:'lea rax, [rbx + 0x2a988]',
        0x568472:'lea rax, [rbx + 0x2ae30]',
        0x552864:'lea rax, [rsi + 0x2a994]',
        0x55287B:'mov dword ptr [rsi + 0x2a9e0], 8',
        0x5715CD:'lea rcx, [rdi + 0x2a988]',
        0x5715D7:'call 0x9ba6c0',
        0x577E7B:'mov eax, dword ptr [rbx + 0x2a98c]',
        0x577E84:'mov dword ptr [rbx + 0x2a990], eax',
        0x9BA8F8:'mov rax, qword ptr [rcx + r8*8 + 0x68]',
        0x9BA8FD:'mov qword ptr [rdx + 0x68], rax',
        0x9BA919:'mov ecx, 2',
        0x9BA97C:'mov rcx, qword ptr [rax]',
        0x9BA97F:'mov qword ptr [r9], rcx',
        0x9BA9E2:'mov dword ptr [r8 + 4], esi',
        0x9BA892:'cmp r15d, dword ptr [rsi + 8]',
        0x9BA526:'cmp ecx, 0x10',
    }
    for rva, asm in critical.items():
        require(pin(rva)['asm'] == asm, 'critical pin changed: '+hex(rva))
    literal = b'"kill_streak" : { "max" : %u, "capacity" : 4 }\0'
    require(im.read(0x224D698, len(literal)) == literal, 'diagnostic changed')
    all_sites = {}
    for f in functions:
        for fragment in f['fragments']:
            for i in fragment['instructions']:
                all_sites[i['rva']] = i
    for group in owner.values():
        for i in group:
            all_sites[i['rva']] = i
    result = dict(
        source_sha256=EXPECTED, capture_identity_sha256=im.report['capture_sha256'],
        component_index=43, global_rva='0x3326af0',
        callback_initializer_sha256=sha(init), registrations=registrations,
        full_functions=functions, owner_pins=owner, critical_asm=critical,
        diagnostic=dict(rva='0x224d698', bytes=literal.hex(), sha256=sha(literal)),
        layout=dict(owner_offset=0x2A988, next_owner_member=0x2AE30, available_span=0x4A8,
                    internal_hash_buckets=dict(base=0xC, count=8, stride=8, header=0x50,
                                               storage_pointer=0x50, capacity=0x58, sentinel=0x5C, multiplier=0x60),
                    pointer_array=dict(base=0x68, count=4, stride=8),
                    record_array=dict(base=0x88, count=4, stride=0x108, end_exclusive=0x4A8),
                    eight_record_payload_growth=0x440,
                    hypothetical_same_header_repack=dict(pointer_base=0x68, record_base=0xA8, end_exclusive=0x8E8),
                    qualification='The hypothetical extent retains the original header/hash layout; it is not a validated new allocation or patch plan.'),
        decisions=[
            'The current record array reaches the next initialized and published owner member; in-place tail extension is invalid.',
            'Replacing only the component global misses the direct owner update and count-copy paths.',
            'Whole-object relocation must rebase its self-relative hash storage pointer or deliberately retain/reconfigure separate bucket storage.',
            'Compaction copies the entity pointer and all 0x108 record bytes and repairs ID-to-ordinal; retain this association.',
            'Registered RCX-entity callbacks and separate RDX-entity helpers use different ABIs.',
            'The 0x10 inner-record limit is per-record storage, not the number of player/component records.'],
        unique_instruction_sites_excluding_registration=len(all_sites),
        limits=[
            'Only three of ten callback slots have assignments for component43 in this initializer; missing assignments do not prove null or unused live slots.',
            'No live callback, current metadata equality, five-player gameplay, or engine helper success was observed.',
            'Hash capacity eight is bucket count, not proof of eight-player safety; full insertion/removal behavior under eight occupied buckets is not established.',
            'Selected owner aliases and consumers are proven; this is not an exhaustive relocation inventory.',
            'No new capture, process query, installation, patch, or anti-cheat operation.'])
    target.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(target), functions=len(functions),
                          unique_instruction_sites=result['unique_instruction_sites_excluding_registration'], sha256=sha(target.read_bytes()))))


if __name__ == '__main__':
    main()
