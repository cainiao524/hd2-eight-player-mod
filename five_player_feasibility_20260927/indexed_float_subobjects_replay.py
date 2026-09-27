"""Replay the bounded five-subobject lifecycle from the fixed offline capture.

No process, network, registry, game launch, or mutation APIs. Three cleanup
switch tables are classified by their actual indexed reads/indirect jumps.
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

PRIOR = {
    'indexed_float_storage_evidence.json': '11e984e270540eded0e141f821ddfbb22118c0b99645237eca15e14149d42378',
    'indexed_float_consumers_evidence.json': '503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578',
}
# entry: (last code byte exclusive, entire unwind family end exclusive)
ROOTS = {
    0x140C160: (0x140C1FC, 0x140C1FC),
    0x140C200: (0x140C28D, 0x140C28D),
    0x140C2E0: (0x140C529, 0x140C529),
    0x140D710: (0x140D8B1, 0x140D8B1),
    0x142F6E0: (0x142F77A, 0x142F77A),
    0x1408F00: (0x1408F8F, 0x1408F8F),
    0x1408FE0: (0x14090C6, 0x14090C6),
    0x1405580: (0x140560B, 0x140560B),
    0x14066A0: (0x14067DB, 0x14067F4),
    0x1407960: (0x1407AF4, 0x1407B0C),
    0x1403070: (0x140319D, 0x14031B8),
    0x142B990: (0x142BEB3, 0x142BEB3),
    0x142C9B0: (0x142CB57, 0x142CB57),
}
LEAVES = {0x140C630: (0x140C69E, 0x142DE4F), 0x140C6A0: (0x140C70E, 0x142DE5E)}
TABLES = {
    0x1403070: dict(start=0x14031A0, end=0x14031B8, base=0x1403093,
                    read=0x140309C, add=0x14030A4, jump=0x14030A7,
                    targets=[0x14030AA, 0x14030D3, 0x14030FC, 0x1403125, 0x140314B, 0x1403174]),
    0x14066A0: dict(start=0x14067DC, end=0x14067F4, base=0x14066D8,
                    read=0x14066FA, add=0x1406701, jump=0x1406704,
                    targets=[0x1406706, 0x1406725, 0x1406741, 0x140675D, 0x1406776, 0x1406792]),
    0x1407960: dict(start=0x1407AF4, end=0x1407B0C, base=0x1407994,
                    read=0x14079BA, add=0x14079C2, jump=0x14079C5,
                    targets=[0x14079C7, 0x14079E6, 0x1407A02, 0x1407A1E, 0x1407A37, 0x1407A53]),
}
CALLER_PINS = [0x142DE4F, 0x142DE5E, 0x142DE22, 0x142DE3B, 0x142DB4E]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    output = Path(args.output)
    require(not output.exists(), 'refusing overwrite')
    prior_rows = {}
    for name, expected in PRIOR.items():
        raw = (HERE / name).read_bytes()
        require(sha(raw) == expected, 'prior artifact changed: ' + name)
        obj = json.loads(raw)
        def collect(x):
            if isinstance(x, dict):
                if 'rva' in x and 'bytes' in x and 'asm' in x:
                    prior_rows[int(x['rva'], 16)] = x
                for v in x.values():
                    collect(v)
            elif isinstance(x, list):
                for v in x:
                    collect(v)
        collect(obj)
    im = Image(args.evidence)
    spans, decoded, functions = {}, {}, {}

    def decode(label, a, b, proof, leaf=False):
        raw = im.read(a, b-a)
        ins = list(im.md.disasm(raw, a))
        require(ins and sum(i.size for i in ins) == len(raw), 'incomplete code span ' + label)
        if not leaf:
            for i in ins:
                bounded = im.instruction(i.address)
                require(bounded is not None and bounded.bytes == i.bytes, 'not unwind boundary ' + hex(i.address))
        decoded.update({i.address: i for i in ins})
        spans[label] = dict(start=hex(a), end_exclusive=hex(b), bytes=raw.hex(), sha256=sha(raw),
                            proof=proof, instructions=[row(i) for i in ins])
        return ins

    for entry, (code_end, family_end) in ROOTS.items():
        fragments = [f for f in im.functions if entry <= f[0] < family_end and im.root(f[0])[0] == entry]
        require(fragments and fragments[0][0] == entry and fragments[-1][1] == family_end, 'family bounds')
        require(all(a[1] == b[0] for a, b in zip(fragments, fragments[1:])), 'noncontiguous family')
        ins = []
        for f in fragments:
            if f[0] < code_end:
                ins += decode(hex(f[0]), f[0], min(f[1], code_end),
                              dict(kind='complete_unwind_fragment_or_proven_code_prefix', root=hex(entry),
                                   fragment=[hex(x) for x in f], excluded_tail=entry in TABLES))
        functions[entry] = ins

    caller_pins = []
    for at in CALLER_PINS:
        i = im.instruction(at)
        require(i is not None and at in prior_rows and i.bytes.hex() == prior_rows[at]['bytes'], 'prior caller proof')
        caller_pins.append(dict(**row(i), root=hex(im.root(at)[0])))
    for entry, (end, callsite) in LEAVES.items():
        i = im.instruction(callsite)
        require(i.mnemonic == 'call' and i.operands[0].type == X86_OP_IMM and i.operands[0].imm == entry,
                'leaf entry not direct-call proven')
        require(im.containing(entry) is None, 'leaf unexpectedly has unwind')
        ins = decode(hex(entry), entry, end, dict(kind='proven_direct_call_leaf', caller=row(i)), leaf=True)
        require(ins[-1].mnemonic == 'ret' and ins[-1].address + ins[-1].size == end, 'leaf return boundary')
        require(not any(i.mnemonic == 'call' for i in ins), 'leaf unexpectedly calls')
        functions[entry] = ins

    tables, table_edges = [], {}
    for entry, spec in TABLES.items():
        raw = im.read(spec['start'], spec['end']-spec['start'])
        require(list(struct.unpack('<6I', raw)) == spec['targets'], 'switch targets changed')
        base_i = decoded[spec['base']]
        require(base_i.mnemonic == 'lea' and base_i.operands[1].mem.base == X86_REG_RIP and
                base_i.address + base_i.size + base_i.operands[1].mem.disp == 0, 'switch base not image base')
        read_i = decoded[spec['read']]
        require(read_i.mnemonic == 'mov' and read_i.operands[1].type == X86_OP_MEM and
                read_i.operands[1].mem.disp == spec['start'] and read_i.operands[1].mem.scale == 4,
                'switch table not actually indexed')
        require(decoded[spec['jump']].mnemonic == 'jmp' and decoded[spec['jump']].operands[0].type != X86_OP_IMM,
                'switch indirect jump missing')
        require(all(t in {i.address for i in functions[entry]} for t in spec['targets']), 'table target not code')
        padding = im.read(ROOTS[entry][0], spec['start']-ROOTS[entry][0])
        if padding:
            padding_ins = list(im.md.disasm(padding, ROOTS[entry][0]))
            require(sum(i.size for i in padding_ins) == len(padding) and all(i.mnemonic == 'nop' for i in padding_ins),
                    'table padding not NOP')
        table_edges[spec['jump']] = spec['targets']
        tables.append(dict(root=hex(entry), start=hex(spec['start']), end_exclusive=hex(spec['end']),
                           bytes=raw.hex(), sha256=sha(raw), targets=[hex(t) for t in spec['targets']],
                           padding_bytes=padding.hex(), source=[row(decoded[spec[k]]) for k in ('base', 'read', 'add', 'jump')]))

    # Close the finite instruction CFG. External calls/tail calls remain explicit
    # boundaries; the table jumps are followed only after the proofs above.
    cfgs, transfers, all_successors = [], [], {}
    for entry, ins in functions.items():
        by_address = {i.address: i for i in ins}
        successors = {}
        for i in ins:
            following = i.address + i.size
            nxt = []
            if i.mnemonic == 'ret':
                pass
            elif i.mnemonic == 'jmp':
                if i.operands[0].type == X86_OP_IMM:
                    target = i.operands[0].imm
                    if target in by_address:
                        nxt = [target]
                    else:
                        transfers.append(dict(root=hex(entry), kind='tail_call_boundary', **row(i), target=hex(target)))
                else:
                    require(i.address in table_edges, 'unclassified indirect jump')
                    nxt = table_edges[i.address]
            elif i.mnemonic.startswith('j'):
                require(i.operands[0].type == X86_OP_IMM, 'unexpected conditional indirect jump')
                nxt = [i.operands[0].imm, following]
            else:
                nxt = [following]
                if i.mnemonic == 'call':
                    target = hex(i.operands[0].imm) if i.operands[0].type == X86_OP_IMM else None
                    transfers.append(dict(root=hex(entry), kind='direct_call' if target else 'indirect_call_boundary',
                                          **row(i), target=target))
            require(all(a in by_address for a in nxt), 'CFG exits unclassified code ' + hex(i.address))
            successors[i.address] = nxt
        reachable, todo = set(), [entry]
        while todo:
            a = todo.pop()
            if a not in reachable:
                reachable.add(a)
                todo += successors[a]
        unreachable = [i for i in ins if i.address not in reachable]
        require(all(i.mnemonic == 'nop' for i in unreachable), 'unreachable non-NOP code')
        cfgs.append(dict(root=hex(entry), decoded_instructions=len(ins), reachable_instructions=len(reachable),
                         unreachable_alignment_nops=[row(i) for i in unreachable],
                         edges=[dict(at=hex(a), successors=[hex(t) for t in targets]) for a, targets in successors.items()]))
        all_successors[entry] = successors

    table_base_flow = []
    for entry, spec in TABLES.items():
        aliases = {0x1403070: ('rcx','ecx','cx','cl','ch'),
                   0x14066A0: ('rbp','ebp','bp','bpl'),
                   0x1407960: ('r14','r14d','r14w','r14b')}[entry]
        ins = functions[entry]
        by_address = {i.address:i for i in ins}
        before = {i.address:set() for i in ins}
        before[entry] = {'entry'}
        changed = True
        while changed:
            changed = False
            for i in ins:
                if not before[i.address]:
                    continue
                written = any(im.md.reg_name(reg) in aliases for reg in i.regs_access()[1])
                # ABI clobbers are relevant for RCX, not the two nonvolatile bases.
                volatile_call = entry == 0x1403070 and i.mnemonic == 'call'
                after = {hex(i.address)} if written or volatile_call else before[i.address]
                for target in all_successors[entry][i.address]:
                    union = before[target] | after
                    if union != before[target]:
                        before[target] = union
                        changed = True
        for key in ('read','add','jump'):
            require(before[spec[key]] == {hex(spec['base'])}, 'table base has other reaching definition')
        table_base_flow.append(dict(root=hex(entry), aliases=aliases,
                                    proven_sites={hex(spec[k]):sorted(before[spec[k]]) for k in ('read','add','jump')},
                                    register_writes=[row(i) for i in ins if any(im.md.reg_name(r) in aliases for r in i.regs_access()[1])],
                                    assumption='Windows x64 nonvolatile RBP/R14 are preserved by callees; volatile RCX calls explicitly clobber.'))

    semantic = {
        'constructor_actual_entry_and_links': {
            0x140C174: 'mov rbx, rcx', 0x140C193: 'mov rax, qword ptr [rsp + 0x50]',
            0x140C198: 'mov qword ptr [rcx + 0x10], rax', 0x140C19C: 'mov qword ptr [rcx], rdx',
            0x140C19F: 'mov qword ptr [rcx + 0x20], r8', 0x140C1A3: 'mov qword ptr [rcx + 8], r9',
            0x140C1A7: 'mov byte ptr [rcx + 0x5c], 1',
        },
        'pool_initialization': {
            0x142B9BE: 'mov rbx, rcx', 0x142BA4C: 'mov qword ptr [rbx + 8], rax',
            0x142BAC6: 'lea rsi, [rbx + 0x3718]', 0x142BAE3: 'mov r14d, 0x100',
            0x142BAFA: 'lea rax, [rbx + 0x23f18]', 0x142BB1B: 'lea rdi, [rbx + 0x36f8]',
            0x142BB22: 'mov qword ptr [rdi], rsi', 0x142BB25: 'mov qword ptr [rdi + 8], rax',
            0x142BB29: 'mov dword ptr [rdi + 0x14], r14d', 0x142BB42: 'mov r8d, 0x208',
            0x142BB4B: 'call 0x208aaa0', 0x142BB53: 'call 0x1408fe0', 0x142BB58: 'add rsi, 0x208',
            0x142BB5F: 'sub r14, 1', 0x142BB63: 'jne 0x142bb40',
        },
        'five_constructor_calls_and_four_record_loop': {
            0x142BB8D: 'lea r14, [rbx + 0x80eb8]', 0x142BB94: 'mov r12d, 4',
            0x142BBA0: 'lea rcx, [r14 - 0xa0]', 0x142BBA9: 'mov r8d, 0x298',
            0x142BBB4: 'lea rcx, [r14 - 0x78]', 0x142BBC6: 'call 0x140c160',
            0x142BBD9: 'mov rcx, r14', 0x142BBDC: 'call 0x140c160',
            0x142BBE1: 'lea rcx, [r14 + 0x78]', 0x142BBF3: 'call 0x140c160',
            0x142BBF8: 'lea rcx, [r14 + 0x100]', 0x142BC0D: 'call 0x140c160',
            0x142BC12: 'lea rcx, [r14 + 0x178]', 0x142BC27: 'call 0x140c160',
            0x142BC2C: 'add r14, 0x298', 0x142BC33: 'sub r12, 1', 0x142BC37: 'jne 0x142bba0',
        },
        'matching_cleanup_loop': {
            0x142C9BF: 'mov rdi, rcx', 0x142C9CE: 'lea rbx, [rdi + 0x80eb8]',
            0x142C9D5: 'mov esi, 4', 0x142C9E4: 'call 0x140c200', 0x142C9EC: 'call 0x140c200',
            0x142C9F5: 'call 0x140c200', 0x142CA01: 'call 0x140c200', 0x142CA0D: 'call 0x140c200',
            0x142CA12: 'add rbx, 0x298', 0x142CA19: 'sub rsi, 1', 0x142CA1D: 'jne 0x142c9e0',
        },
        'cleanup_ownership': {
            0x140C226: 'mov eax, dword ptr [rbx + rax*4 + 0x28]', 0x140C22A: 'imul rcx, rax, 0x208',
            0x140C231: 'mov rax, qword ptr [rbx + 0x20]', 0x140C235: 'add rcx, qword ptr [rax]',
            0x140C238: 'call 0x1408f00', 0x140C244: 'mov rax, qword ptr [rdx + 8]',
            0x140C24E: 'mov byte ptr [rax + rcx], bpl', 0x140C252: 'dec dword ptr [rdx + 0x10]',
        },
        'template_latch_and_allocation': {
            0x140C2E8: 'mov eax, dword ptr [rcx + 0x1c]', 0x140C2F0: 'cmp eax, edx',
            0x140C2F2: 'je 0x140c4b3', 0x140C306: 'call 0x140c200',
            0x140C30B: 'imul r12, rbx, 0xa0e8', 0x140C319: 'mov dword ptr [r14 + 0x1c], ebx',
            0x140C323: 'cmp dword ptr [r12 + 0xa0e0], r15d',
            0x140C356: 'mov r8d, dword ptr [r9 + 0x14]', 0x140C35D: 'je 0x140c495',
            0x140C363: 'mov edi, dword ptr [r9 + 0x18]', 0x140C367: 'mov rbx, qword ptr [r9 + 8]',
            0x140C375: 'div r8d', 0x140C37E: 'cmp byte ptr [rdx + rbx], 0',
            0x140C386: 'cmp ecx, r8d', 0x140C38B: 'jmp 0x140c495',
            0x140C398: 'mov dword ptr [r9 + 0x18], edx', 0x140C39C: 'mov byte ptr [r10 + rbx], 1',
            0x140C3A1: 'inc dword ptr [r9 + 0x10]', 0x140C3AF: 'inc dword ptr [r14 + 0x58]',
            0x140C3B3: 'mov dword ptr [r14 + r15*4 + 0x28], r10d',
            0x140C3BC: 'mov rdx, qword ptr [r14 + 0x10]', 0x140C3C0: 'mov rcx, qword ptr [r14 + 8]',
            0x140C3C4: 'mov r8d, dword ptr [r14 + 0x18]', 0x140C3C8: 'imul rbx, r11, 0x208',
            0x140C3D5: 'mov rax, qword ptr [r14]', 0x140C3D8: 'imul rdi, r9, 0xd68',
            0x140C3DF: 'mov qword ptr [rbx], rax', 0x140C3E5: 'mov qword ptr [rbx + 8], rcx',
            0x140C3EE: 'mov qword ptr [rbx + 0x10], rdx', 0x140C3F2: 'mov dword ptr [rbx + 0x18], r8d',
            0x140C400: 'mov qword ptr [rbx + 0x20], rdi', 0x140C40C: 'call 0x1408fe0',
            0x140C487: 'cmp r15d, dword ptr [r12 + 0xa0e0]', 0x140C48F: 'jb 0x140c350',
        },
        'leaf_node_fields': {
            0x140C636: 'cmp dword ptr [rcx + 0x58], r10d', 0x140C640: 'mov rax, qword ptr [rcx + 0x20]',
            0x140C644: 'mov r8d, dword ptr [rcx + r10*4 + 0x28]', 0x140C649: 'imul r9, r8, 0x208',
            0x140C650: 'add r9, qword ptr [rax]', 0x140C65C: 'cmp dword ptr [rax], 2',
            0x140C661: 'cmp dword ptr [rax + 8], edx', 0x140C66C: 'mov dword ptr [r9 + 0x40], r11d',
            0x140C6DC: 'mov dword ptr [r9 + 0x44], r11d',
        },
        'event_count_and_dependency': {
            0x140D754: 'mov rax, qword ptr [r14 + 0x20]', 0x140D75A: 'mov ecx, dword ptr [r14 + r15*4 + 0x28]',
            0x140D75F: 'imul rbx, rcx, 0x208', 0x140D769: 'mov rax, qword ptr [rbx + 0x20]',
            0x140D76D: 'cmp dword ptr [rax + 0xd64], ebp', 0x140D782: 'imul rcx, rdi, 0xfc',
            0x140D789: 'cmp dword ptr [rcx + rax + 0x38c], r12d', 0x140D797: 'shl rdi, 5',
            0x140D79B: 'cmp byte ptr [rdi + rbx + 0xb0], sil', 0x140D7C6: 'call 0x72fbe0',
            0x140D80C: 'call 0x72fbe0', 0x140D85F: 'cmp ebp, dword ptr [rax + 0xd64]',
            0x140D883: 'cmp r15d, dword ptr [r14 + 0x58]',
        },
        'wrapper': {
            0x142F6E6: 'mov rbx, rdx', 0x142F6E9: 'mov edx, r8d', 0x142F6EC: 'mov rcx, rbx',
            0x142F6EF: 'call 0x140c2e0', 0x142F740: 'movss xmm0, dword ptr [rsp + 0x50]',
            0x142F754: 'mov edx, 0xa', 0x142F761: 'jmp 0x140d710', 0x142F775: 'jmp 0x140d710',
        },
    }
    semantic_pins = {}
    for label, expected in semantic.items():
        semantic_pins[label] = []
        for at, asm in expected.items():
            i = decoded[at]
            require((i.mnemonic + ' ' + i.op_str).strip() == asm, 'semantic mismatch ' + hex(at))
            semantic_pins[label].append(row(i))

    rip_proofs = []
    for at, expected in [(0x140C312, 0x3492F20), (0x142BB65, 0x347CE90), (0x142F746, 0x23C6D70)]:
        i = decoded[at]
        targets = [i.address + i.size + o.mem.disp for o in i.operands if o.type == X86_OP_MEM and o.mem.base == X86_REG_RIP]
        require(targets == [expected], 'RIP target mismatch')
        rip_proofs.append(dict(instruction=row(i), target=hex(expected)))
    literal = im.read(0x23C6D70, 4)
    require(literal == bytes.fromhex('0000803f'), 'wrapper 1.0 literal changed')

    # Arithmetic constraints are derived from the pinned storage/counter fields,
    # never from guessed live content or treating a same offset as object identity.
    require(0x3718 + 256 * 0x208 == 0x23F18, 'pool next-member boundary')
    require((0x58-0x28)//4 == 12 and 12 * 0xD68 == 0xA0E0, 'template index storage')
    require(0x38C + 10 * 0xFC == 0xD64 and 0xB0 + 10 * 0x20 == 0x1F0, 'event record boundaries')
    require(0x80E18 + 4 * 0x298 == 0x81878, 'four-record storage bound')
    result = dict(
        schema_version=1, source_capture_expected=EXPECTED, source_capture=str(Path(args.evidence)),
        prior_artifacts=PRIOR, scope='Offline complete selected subobject roots and leaf entries; no live state or game changes.',
        code_spans=spans, caller_pins=caller_pins, switch_tables=tables, switch_base_reaching_definitions=table_base_flow, control_flow=cfgs,
        call_and_tail_boundaries=transfers, semantic_pins=semantic_pins, rip_proofs=rip_proofs,
        readonly_literals=[dict(rva='0x23c6d70', bytes=literal.hex(), sha256=sha(literal), float32=1.0)],
        storage=dict(record_base='D+0x80e18', record_stride='0x298', original_records=4,
                     subobject_offsets=['0x28','0xa0','0x118','0x1a0','0x218'], subobject_size='0x78',
                     constructor='0x140c160', cleanup='0x140c200',
                     pool=dict(descriptor='D+0x36f8', nodes='D+0x3718', bitmap='D+0x23f18',
                               initial_capacity=256, node_stride='0x208', used_count_offset='0x10',
                               capacity_offset='0x14', search_cursor_offset='0x18', shared_beyond_four_records=True,
                               used_count_cursor_bitmap_initialization_proved_here=False),
                     subobject_index_storage=12, template_stride='0xa0e8', template_element_stride='0xd68',
                     template_count_offset='0xa0e0', node_event_physical_slots=10,
                     new_subobjects_for_eight_records=20, additional_node_slots_upper_envelope=240,
                     eight_record_subobjects_node_slots_upper_envelope=480,
                     envelope_is_not_observed_template_demand=True),
        conclusions=dict(
            active_clone_safe=False,
            reason='Clones share pool indices and cleanup destroys the same nodes/resources; fresh init first loses live ownership.',
            limited_move_condition='Keeping D/P and external contexts stable preserves these observed referents, but all caller aliases and exclusive ownership must be transferred; universal memcpy safety is not proved.',
            new_record_action='Initialize five fresh subobjects with the same stable D/P/context values; extend matched outer cleanup and ensure pool budget.',
            same_id_retry_after_pool_exhaustion=False,
            exhaustion_behavior='ID is latched before allocation; pool-full/zero capacity returns, retaining any partial node ownership without grow/rollback.',
            generic_player_four_limit_found=False,
            unresolved='Actual template/event counts, bitmap/used-count/cursor initial values, pool occupancy, API targets/runtime calls, other pool consumers and external S aliases are not captured or exhausted.'),
        counts=dict(complete_unwind_roots=len(ROOTS), proven_leaf_entries=len(LEAVES),
                    code_spans=len(spans), decoded_code_instructions=sum(len(v) for v in functions.values()),
                    reachable_instructions=sum(c['reachable_instructions'] for c in cfgs),
                    caller_pins=len(caller_pins), semantic_pins=sum(len(x) for x in semantic_pins.values()),
                    classified_switch_tables=len(tables), external_and_internal_call_tail_sites=len(transfers)))
    raw = (json.dumps(result, indent=2, ensure_ascii=False)+'\n').encode('utf-8')
    output.write_bytes(raw)
    print(json.dumps(dict(output=str(output), sha256=sha(raw), counts=result['counts'])))


if __name__ == '__main__':
    main()
