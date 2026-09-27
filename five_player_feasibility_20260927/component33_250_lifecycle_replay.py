"""Replay selected component 33/250 lifecycle evidence from the fixed saved capture.

Offline only. No process, network, game-file write, or probe capability.
The resulting storage interpretation is a manual inference, not live validation.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

PRIOR_SHA = '4dedec98d7759d1f629500c42bb9a70ff611d0e0b73175e36f2c0306c37f8147'
TABLES = [0xF0B6F0, 0xF0C110, 0xF0CB30, 0xF0D550, 0xF0DF70,
          0xF0E990, 0xF0F3B0, 0xF0FDD0, 0xF107F0, 0xF11210]
CALLBACKS = {
    33: [0x51ABF0, 0x51AC70, 0x51ADB0, 0x51ADE0, 0x51AE90,
         0x51AD30, 0x51AEA0, None, 0x51AEB0, None],
    250: [0x543230, 0x5432B0, 0x5433E0, None, 0x5434D0,
          0x543360, 0x5434E0, None, 0x5434F0, None],
}
# The root may have multiple chained unwind fragments, all retained here.
ROOT_ENDS = {
    0x51ABF0: 0x51AC6C, 0x51AC70: 0x51AD27, 0x51ADB0: 0x51ADD3,
    0x51ADE0: 0x51AE88, 0x51AD30: 0x51ADAF,
    0x543230: 0x5432A2, 0x5432B0: 0x543360, 0x5433E0: 0x5434C9,
    0x543360: 0x5433DF, 0x665FE0: 0x666128, 0x671610: 0x6716F8,
    0x666A90: 0x666DCD, 0x666DD0: 0x66715D,
    0x671CA0: 0x671EFD, 0x671F00: 0x6721CD,
    0x6661A0: 0x66658D, 0x664430: 0x664518, 0xB28040: 0xB28113,
}
# Leaf boundaries have explicit registration or a boundary-validated direct call.
LEAVES = {
    0x51AE90: (0x51AE93, 'registration', None),
    0x51AEA0: (0x51AEA8, 'registration', None),
    0x51AEB0: (0x51AEB8, 'registration', None),
    0x5434D0: (0x5434D3, 'registration', None),
    0x5434E0: (0x5434E8, 'registration', None),
    0x5434F0: (0x5434F8, 'registration', None),
    0x671910: (0x671968, 'direct_call', 0x5566E3),
    0xB38710: (0xB389A1, 'direct_call', 0x5659BB),
}
WINDOWS = {
    '33_publish_and_next': (0x5683E6, 0x568402),
    '250_publish_and_next': (0x568F62, 0x568F7E),
    '33_initialize_register': (0x55250A, 0x5525CA),
    '33_unregister': (0x55F13C, 0x55F1EC),
    '250_initialize_register_calls': (0x5566DC, 0x5566ED),
    '250_unregister_call': (0x5659B4, 0x5659C0),
    '33_owner_partition_reconcile': (0x577B16, 0x577B6B),
    '250_owner_partition_reconcile': (0x57E6AC, 0x57E6F4),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', required=True, help='Existing fixed code capture directory')
    p.add_argument('--output', required=True, help='New JSON file; existing file is refused')
    args = p.parse_args()
    output = Path(args.output)
    require(not output.exists(), 'refusing overwrite')
    prior_raw = (HERE / 'player_component_capacity_evidence.json').read_bytes()
    require(sha(prior_raw) == PRIOR_SHA, 'capacity evidence fingerprint changed')
    prior = json.loads(prior_raw)
    for index in (33, 250):
        item = next(x for x in prior['entries'] if x['component_index'] == index)
        require(int(item['entry'], 16) == CALLBACKS[index][1], 'prior callback changed')
    im = Image(args.evidence)
    start, end = 0x556D90, 0x55E1E3
    init = im.read(start, end-start)
    require(sha(init) == '22c57829a02419f7e8689a6e2ca501c353fa5362904c6b49e108689d842c91b2',
            'registration initializer changed')
    caller = im.instruction(0x568239)
    require(caller is not None and caller.mnemonic == 'call' and caller.operands[0].imm == start,
            'registration leaf entry proof changed')
    require(len(init) == 2127*14+1 and init[-1] == 0xC3, 'initializer shape changed')
    assigns = {}
    for off in range(0, len(init)-1, 14):
        pair = init[off:off+14]
        require(pair[:3] == b'\x48\x8d\x05' and pair[7:10] == b'\x48\x89\x81', 'initializer pair changed')
        dest = struct.unpack_from('<i', pair, 10)[0]
        require(dest not in assigns, 'duplicate initializer assignment')
        assigns[dest] = dict(target=start+off+7+struct.unpack_from('<i', pair, 3)[0],
                            instructions=[row(i) for i in im.md.disasm(pair, start+off)])
    tables = {}
    registered = set()
    for idx, expected in CALLBACKS.items():
        rows = []
        for table, target in zip(TABLES, expected):
            a = assigns.get(table+8*idx)
            require((a['target'] if a else None) == target, 'callback registration changed')
            rows.append(dict(table=hex(table), slot=hex(table+8*idx), target=hex(target) if target else None,
                             assignment=a, absent_meaning='No assignment in this initializer; runtime null is not proven.' if not a else None))
            if target:
                registered.add(target)
        tables[str(idx)] = rows

    bodies = {}
    decoded = {}

    def save_span(label, a, b, proof):
        raw = im.read(a, b-a)
        ins = list(im.md.disasm(raw, a))
        require(ins and sum(i.size for i in ins) == len(raw), 'incomplete decode '+label)
        require(ins[-1].address+ins[-1].size == b, 'end boundary '+label)
        decoded.update({i.address: i for i in ins})
        bodies[label] = dict(start=hex(a), end_exclusive=hex(b), sha256=sha(raw), proof=proof,
                             instructions=[row(i) for i in ins])
        return ins

    for entry, stop in ROOT_ENDS.items():
        fs = [f for f in im.functions if entry <= f[0] < stop and im.root(f[0])[0] == entry]
        require(fs and fs[0][0] == entry and fs[-1][1] == stop, 'root bounds changed '+hex(entry))
        require(all(a[1] == b[0] for a, b in zip(fs, fs[1:])), 'noncontiguous selected root')
        for f in fs:
            ins = save_span(hex(f[0]), f[0], f[1], dict(kind='captured_unwind_fragment',
                            fragment=[hex(x) for x in f], root=hex(entry)))
            require(im.instruction(ins[-1].address) is not None, 'fragment end not a boundary')
    for entry, (stop, kind, call_rva) in LEAVES.items():
        require(im.containing(entry) is None, 'leaf classification changed')
        proof = dict(kind=kind, registered_entry=hex(entry) if entry in registered else None)
        if kind == 'registration':
            require(entry in registered, 'leaf entry lacks registration')
        else:
            call = im.instruction(call_rva)
            require(call is not None and call.mnemonic == 'call' and call.operands[0].imm == entry,
                    'leaf entry lacks direct call')
            proof['caller'] = row(call)
        ins = save_span(hex(entry), entry, stop, proof)
        require(ins[-1].mnemonic in ('ret', 'jmp'), 'leaf final boundary changed')
        starts = {i.address for i in ins}
        for i in ins:
            if i.mnemonic.startswith('j') and i.operands[0].type == X86_OP_IMM:
                target = i.operands[0].imm
                if entry <= target < stop:
                    require(target in starts, 'leaf jump into instruction')
                elif i.mnemonic != 'jmp':
                    require(False, 'unaccounted conditional leaf exit')
    for label, (a, b) in WINDOWS.items():
        f = im.containing(a)
        require(f is not None and b <= f[1], 'window escaped validated fragment '+label)
        require(im.instruction(a) is not None and (b == f[1] or im.instruction(b) is not None),
                'window boundary changed '+label)
        save_span(label, a, b, dict(kind='slice_from_captured_unwind_fragment',
                                  fragment=[hex(x) for x in f], root=hex(im.root(a)[0])))

    # Validate owner register provenance through whole intervening code. Calls obey
    # the Windows x64 nonvolatile-register ABI; this is not a live ABI assertion.
    owner_provenance = []
    for entry, stop, regs, expected in [
        (0x551B60, 0x5566ED, ('rsi', 'esi', 'si', 'sil'), [0x551B7A]),
        (0x551B60, 0x5525CA, ('r13', 'r13d', 'r13w', 'r13b'), [0x551D3C]),
        (0x568230, 0x568F7E, ('rbx', 'ebx', 'bx', 'bl', 'bh'), [0x568236]),
        (0x55E1F0, 0x5659C0, ('rbx', 'ebx', 'bx', 'bl', 'bh'), [0x55E203]),
        (0x576CF0, 0x57E6F4, ('rbx', 'ebx', 'bx', 'bl', 'bh'), [0x576D0D]),
    ]:
        f = im.containing(entry)
        require(f[0] == entry and stop <= f[1], 'owner range escaped fragment')
        ins = list(im.md.disasm(im.read(entry, stop-entry), entry))
        require(sum(i.size for i in ins) == stop-entry, 'owner range decode incomplete')
        writes = [i for i in ins if any(im.md.reg_name(r) in regs for r in i.regs_access()[1])]
        require([i.address for i in writes] == expected, 'owner register overwritten')
        owner_provenance.append(dict(root=hex(entry), end_exclusive=hex(stop),
                                     raw_sha256=sha(im.read(entry, stop-entry)),
                                     register_aliases=regs, writes=[row(i) for i in writes]))

    def check(rva, mnemonic, operands):
        i = decoded.get(rva) or im.instruction(rva)
        require(i is not None and (i.mnemonic, i.op_str) == (mnemonic, operands), 'semantic pin '+hex(rva))
        return row(i)

    # Pins tie the index arithmetic and accesses to the actual loaded global.
    semantic_specs = [
        (0x666DEB, 'mov', 'rbp, qword ptr [rip + 0x2cbf9c6]'),
        (0x666E50, 'mov', 'ebx, dword ptr [r9 + 4]'),
        (0x666E37, 'mov', 'r14d, dword ptr [rbp + 0x10]'),
        (0x666E3B, 'dec', 'r14d'), (0x666E56, 'mov', 'esi, ebx'),
        (0x666E9E, 'movzx', 'ecx, byte ptr [r14 + rbp + 0x90]'),
        (0x666EA9, 'mov', 'byte ptr [rsi + rbp + 0x90], cl'),
        (0x666076, 'imul', 'rcx, r9, 0x38'),
        (0x66607A, 'imul', 'rax, rbp, 0x38'),
        (0x671686, 'movzx', 'eax, byte ptr [r10 + rcx + 0x164]'),
        (0x67168F, 'mov', 'byte ptr [rsi + rcx + 0x164], al'),
        (0x671DB4, 'movzx', 'ecx, byte ptr [r14 + rsi + 0x160]'),
        (0x671DBF, 'mov', 'byte ptr [rsi + rbp + 0x160], cl'),
        (0x67208E, 'movzx', 'ecx, byte ptr [r14 + rbp + 0x160]'),
        (0x672099, 'mov', 'byte ptr [rsi + rbp + 0x160], cl'),
        (0x671DF7, 'movzx', 'ecx, byte ptr [r14 + rsi + 0x164]'),
        (0x671E02, 'movzx', 'ecx, byte ptr [rsi + rbp + 0x164]'),
        (0x671E0A, 'mov', 'byte ptr [r14 + rsi + 0x164], cl'),
        (0x671E1A, 'mov', 'byte ptr [rsi + rbp + 0x164], al'),
        (0x6720D1, 'movzx', 'ecx, byte ptr [r14 + rbp + 0x164]'),
        (0x6720DC, 'movzx', 'ecx, byte ptr [rsi + rbp + 0x164]'),
        (0x6720E4, 'mov', 'byte ptr [r14 + rbp + 0x164], cl'),
        (0x6720F4, 'mov', 'byte ptr [rsi + rbp + 0x164], al'),
        (0x543486, 'mov', 'byte ptr [rcx + rdi + 0x164], 1'),
        (0x543497, 'mov', 'dword ptr [r15 + rcx*8], 0xa3df1643'),
        (0x55258F, 'mov', 'dword ptr [rbp - 8], 0x7c'),
        (0xB2804F, 'mov', 'dword ptr [rsp + 8], 0x7f'),
        (0x671913, 'lea', 'rax, [rcx + 0x18]'),
        (0x671924, 'mov', 'qword ptr [rcx + 0x58], rax'),
        (0x671928, 'mov', 'dword ptr [rcx + 0x60], 8'),
        (0x552511, 'lea', 'rax, [rsi + 0x3cb4]'),
        (0x552525, 'mov', 'qword ptr [rsi + 0x3cf8], rax'),
        (0x55252F, 'mov', 'dword ptr [rsi + 0x3d00], 8'),
        (0x577B3C, 'call', '0x665fe0'), (0x577B4D, 'call', '0x665fe0'),
        (0x57E6CC, 'call', '0x671610'), (0x57E6DD, 'call', '0x671610'),
    ]
    semantic_pins = [check(*spec) for spec in semantic_specs]
    global_proofs = []
    for rva, target in [(0x5683ED, 0x33267B8), (0x568F69, 0x33266D0),
                        (0x666DEB, 0x33267B8), (0x5433FD, 0x33266D0),
                        (0x55257A, 0x3326E68), (0x55F13C, 0x3326E68),
                        (0xB28048, 0x3326E68), (0xB38710, 0x3326E68)]:
        i = decoded.get(rva) or im.instruction(rva)
        refs = [i.address+i.size+o.mem.disp for o in i.operands
                if o.type == X86_OP_MEM and o.mem.base == X86_REG_RIP]
        require(refs == [target], 'RIP target changed '+hex(rva))
        global_proofs.append(dict(instruction=row(i), target=hex(target)))
    # RCX still points at the embedded object when the constructor immediately
    # calls its registry helper after this leaf returns.
    ctor250 = [i for i in decoded.values() if 0x671910 <= i.address < 0x671968]
    require(not any(im.md.reg_name(r) in ('rcx', 'ecx', 'cx', 'cl', 'ch')
                    for i in ctor250 for r in i.regs_access()[1]), '250 ctor clobbers RCX')
    require(not any(i.mnemonic == 'call' for i in ctor250), '250 ctor now calls elsewhere')

    # Arithmetic statements below use half-open spans and zero-based component
    # storage ordinals. They do not identify the network-player index.
    layouts = {
        '33': dict(global_rva='0x33267b8', owner_offset='0x3ca0', next_owner_offset='0x3f58',
                   embedded_span='0x2b8', pointer_base='0x70', pointer_stride=8,
                   indexed_byte_base='0x90', primary_base='0x98', primary_stride='0x50',
                   secondary_base='0x1d8', secondary_stride='0x38',
                   primary_four_end=hex(0x98+4*0x50), secondary_four_end=hex(0x1D8+4*0x38),
                   pointer_ordinal4_span=['0x90', '0x98'],
                   ordinary_four_index_byte_span=['0x90', '0x94'],
                   unclassified_gap=['0x94', '0x98'],
                   map_inline_base='0x14', map_pointer_field='0x58', map_capacity_field='0x60', map_capacity=8,
                   registry_tag='0x7c', registry_arrays=['0xd18', '0x1f80']),
        '250': dict(global_rva='0x33266d0', owner_offset='0xeb5178', next_owner_offset='0xeb52e0',
                    embedded_span='0x168', pointer_base='0x70', pointer_stride=8,
                    primary_base='0x90', primary_stride='0x34', indexed_byte_bases=['0x160', '0x164'],
                    primary_four_end=hex(0x90+4*0x34), byte_four_end=hex(0x164+4),
                    byte_four_spans=[['0x160', '0x164'], ['0x164', '0x168']],
                    pointer_ordinal4_span=['0x90', '0x98'],
                    byte_movement_rules={
                        '0x160': '671CA0/671F00 perform a one-direction copy; 671610 does not copy it.',
                        '0x164': '671CA0/671F00 perform a two-direction swap; 671610 copies source to destination.'},
                    primary_partition_rules='671CA0 swaps entity pointers but clears the selected primary row; 671F00 swaps primary rows. Do not infer a common full-record swap.',
                    map_inline_base='0x18', map_pointer_field='0x58', map_capacity_field='0x60', map_capacity=8,
                    registry_tag='0x7f', registry_arrays=['0x48', '0x1218', '0x1c78', '0x1d10',
                                                       '0x1d68', '0x1f98', '0x5900', '0x5918']),
    }
    require(0x3F58-0x3CA0 == 0x1D8+4*0x38 == 0x2B8, '33 end adjacency')
    require(0x98+4*0x50 == 0x1D8, '33 parallel array adjacency')
    require(0xEB52E0-0xEB5178 == 0x164+4 == 0x168, '250 end adjacency')
    result = dict(schema_revision=2,
                  supersedes_evidence_sha256='a2ef7535597211ef2a36045161d6517665e3edb44ff72c5fa87272b1b0f64fb9',
                  revision_reason='Previously unclassified 250+160..164 is a second indexed-byte array; distinguish copy, swap, and primary-row reset paths.',
                  source_sha256=EXPECTED, capture_identity_sha256=im.report['capture_sha256'],
                  capacity_evidence_sha256=PRIOR_SHA, runtime_verified=False,
                  initializer_sha256=sha(init), initializer_caller=row(caller), callback_tables=tables,
                  code_bodies=bodies, selected_instruction_count=sum(len(v['instructions']) for v in bodies.values()),
                  owner_register_provenance=owner_provenance, semantic_pins=semantic_pins,
                  global_pointer_proofs=global_proofs, manually_derived_layouts=layouts,
                  limits=[
                      'Only the fixed saved code capture is used. No writable globals, heap, or current process is read.',
                      'Registration and static code do not prove these paths executed or reference resources match installed runtime metadata.',
                      'A missing initializer assignment does not prove the runtime callback slot is null.',
                      'Ordinal refers to a component storage index; no network-index equivalence is assumed.',
                      'Member meanings are inferred only from accesses. The byte at +0x90 is not named or proven to be a boolean.',
                      'Owner-prefix provenance assumes normal Windows x64 nonvolatile-register preservation across calls.',
                      'Recorded aliases are proven examples, not an exhaustive registry/consumer inventory.',
                      'No patch, relocation implementation, mod, or five/eight-player success is established.',
                  ])
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(output), selected_instructions=result['selected_instruction_count'],
                         assigned_callbacks=sum(x is not None for v in CALLBACKS.values() for x in v),
                         output_sha256=sha(output.read_bytes()))))


if __name__ == '__main__':
    main()
