"""Bounded, offline ID-zero template/caller replay from the pinned code capture.

No game process is opened. This checks direct initializer helper calls and the
already captured same-D builder/update roots. It deliberately does not
infer that a writable template remains unchanged at runtime.
"""
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

PRIOR = {
    'indexed_float_template_budget_evidence.json':
        '575501706ca9dd257f4cd155325b6a809ed303037736359fb4da6918ee5117bc',
    'indexed_float_pool_triple_members_evidence_v3.json':
        '7a5b7ef002c671d698edd6c663b791a7306eda2b09a238b5d8f187393c04bd60',
    'indexed_float_pool_counter_bounds_evidence.json':
        'aae3906ab3672a3b0f8ed631fdfddeec11bb7b636e3b5bfbb7083d3554f048d4',
    'indexed_float_subobjects_evidence.json':
        '5468aca4b6b456c8714e0cf922fe3e473fe2de2b4dbebc2531118eb8c737bf54',
    'indexed_float_template_helpers_full_discovery.json':
        '6b39645fd682d117c7f59c31226b4b71fb87965317090998b0184ffcd9de98fa',
}
INIT_START, INIT_END = 0x1258050, 0x12616B6
SELECT = 0x1257720
BASE, STRIDE, TABLE_SIZE = 0x3492F20, 0xA0E8, 73 * 0xA0E8
SELECTOR_GLOBAL = 0x346D248
DYNAMIC = {
    0x125A300: (0x3D,),
    0x125A79A: (0x3E,),
    0x125B5E6: (0x41, 0x42, 0x43),
    0x125B7F7: (0x44,),
    0x1260691: (0x29, 0x2A, 0x2B, 0x2C),
}
REG_NAMES = {
    'rax': {'rax', 'eax', 'ax', 'ah', 'al'},
    'rbx': {'rbx', 'ebx', 'bx', 'bh', 'bl'},
    'rcx': {'rcx', 'ecx', 'cx', 'ch', 'cl'},
    'rsi': {'rsi', 'esi', 'si', 'sil'},
    'r12': {'r12', 'r12d', 'r12w', 'r12b'},
    'r15': {'r15', 'r15d', 'r15w', 'r15b'},
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_prior(name):
    raw = (HERE / name).read_bytes()
    require(sha(raw) == PRIOR[name], 'prior evidence changed: ' + name)
    return json.loads(raw)


def pins(by, expected):
    out = []
    for address, asm in expected.items():
        require(address in by, 'missing instruction ' + hex(address))
        r = row(by[address])
        require(r['asm'].strip() == asm, 'changed instruction ' + hex(address))
        out.append(r)
    return out


def flow(instructions):
    by = {i.address: i for i in instructions}
    require(len(by) == len(instructions), 'duplicate instruction address')
    preds = defaultdict(set)
    for i in instructions:
        next_at = i.address + i.size
        if i.mnemonic == 'ret':
            successors = []
        elif i.mnemonic.startswith('j'):
            require(i.operands[0].type == X86_OP_IMM, 'indirect initializer branch')
            successors = [i.operands[0].imm]
            if i.mnemonic != 'jmp':
                successors.append(next_at)
        else:
            successors = [next_at]
        require(all(p in by for p in successors), 'initializer edge outside root')
        for p in successors:
            preds[p].add(i.address)
    reached, todo = set(), [instructions[0].address]
    while todo:
        address = todo.pop()
        if address not in reached:
            reached.add(address)
            i = by[address]
            if i.mnemonic != 'ret':
                n = i.address + i.size
                if i.mnemonic.startswith('j'):
                    todo.append(i.operands[0].imm)
                    if i.mnemonic != 'jmp':
                        todo.append(n)
                else:
                    todo.append(n)
    require(reached == set(by), 'unreachable initializer instructions')
    return by, preds


def reaching(instructions, preds, reg):
    """Last register writes on every normal CFG path; call kills volatile RCX/RAX."""
    state = {i.address: set() for i in instructions}
    outs = {i.address: set() for i in instructions}
    changed = True
    while changed:
        changed = False
        for i in instructions:
            before = set().union(*(outs[p] for p in preds[i.address])) if preds[i.address] else set()
            _, writes = i.regs_access()
            wrote = any(i.reg_name(w) in REG_NAMES[reg] for w in writes)
            if i.mnemonic == 'call' and reg in ('rax', 'rcx'):
                wrote = True
            after = {i.address} if wrote else before
            if state[i.address] != before or outs[i.address] != after:
                state[i.address], outs[i.address] = before, after
                changed = True
    return state


def checked_span(im, evidence_span):
    start = int(evidence_span['start'], 16)
    end = int(evidence_span['end_exclusive'], 16)
    raw = im.read(start, end - start)
    require(sha(raw) == evidence_span['sha256'], 'code-span hash changed ' + hex(start))
    ins = list(im.md.disasm(raw, start))
    require(sum(i.size for i in ins) == len(raw), 'truncated decode ' + hex(start))
    require([row(i) for i in ins] == evidence_span['instructions'], 'code-span rows changed ' + hex(start))
    return ins


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    output = Path(args.output)
    require(not output.exists(), 'refusing overwrite')
    prior = {name: load_prior(name) for name in PRIOR}
    im = Image(args.evidence)
    budget = prior['indexed_float_template_budget_evidence.json']
    require(budget['source_sha256'] == EXPECTED, 'budget capture mismatch')
    require(prior['indexed_float_pool_triple_members_evidence_v3.json']['source_sha256'] == EXPECTED,
            'triple capture mismatch')

    initial = budget['initializer']
    require((int(initial['start'], 16), int(initial['end_exclusive'], 16)) == (INIT_START, INIT_END),
            'initializer bounds changed')
    root_ins = checked_span(im, initial)
    require(len(root_ins) == 6440, 'initializer instruction count changed')
    by, preds = flow(root_ins)
    startup = pins(by, {
        0x12580E7: 'xor edx, edx',
        0x12580E9: 'lea rcx, [rip + 0x223ae30]',
        0x12580F0: 'mov r8d, 0x2de228',
        0x12580F6: 'call 0x208aaa0',
    })
    op = by[0x12580E9].operands[1]
    require(op.type == X86_OP_MEM and 0x12580E9 + by[0x12580E9].size + op.mem.disp == BASE,
            'bulk-zero table base changed')
    require(TABLE_SIZE == 0x2DE228 and BASE + TABLE_SIZE == 0x3771148,
            'bulk-zero table length changed')

    helper_rows = prior['indexed_float_template_helpers_full_discovery.json']
    helper_decoded = {}
    for r in helper_rows:
        at = int(r['rva'], 16)
        raw = bytes.fromhex(r['bytes'])
        require(im.read(at, len(raw)) == raw, 'helper byte mismatch ' + hex(at))
        decoded = list(im.md.disasm(raw, at))
        require(len(decoded) == 1 and row(decoded[0]) == r,
                'helper instruction mismatch ' + hex(at))
        helper_decoded[at] = decoded[0]
    helper_by = {int(r['rva'], 16): r for r in helper_rows}
    helper_pins = {at: helper_by[at] for at in (
        0x1257722, 0x1257729, 0x1257730, 0x1257736, 0x125773F,
        0x1257830, 0x125783D, 0x1257847, 0x1257855, 0x1257857,
        0x12578E0, 0x12578ED, 0x12578F7, 0x1257905, 0x1257907,
        0x1257C90, 0x1257C9D, 0x1257CA7, 0x1257CB8, 0x1257CBA,
        0x1257D50, 0x1257D5D, 0x1257D67, 0x1257D75, 0x1257D77,
        0x1257E00, 0x1257E10, 0x1257EF0, 0x1257F00)}
    helper_refs = []
    for r in helper_rows:
        i = helper_decoded[int(r['rva'], 16)]
        for operand in i.operands:
            if operand.type == X86_OP_MEM and i.reg_name(operand.mem.base) == 'rip':
                target = i.address + i.size + operand.mem.disp
                if target in (BASE, SELECTOR_GLOBAL):
                    helper_refs.append(dict(instruction=row(i), target=hex(target)))
    require(len(helper_refs) == 14, 'template helper global reference count changed')

    ecx = reaching(root_ins, preds, 'rcx')
    selector_calls = [i for i in root_ins if i.mnemonic == 'call' and
                      i.operands[0].type == X86_OP_IMM and i.operands[0].imm == SELECT]
    require(len(selector_calls) == 66, 'selector call count changed')
    all_ids, call_evidence = set(), []
    for i in selector_calls:
        defs = ecx[i.address]
        require(len(defs) == 1, 'ambiguous selector ID reaching definition ' + hex(i.address))
        source = by[next(iter(defs))]
        require(source.address < i.address, 'unexpected selector source ordering')
        if i.address in DYNAMIC:
            ids = DYNAMIC[i.address]
        else:
            require(source.mnemonic == 'mov' and source.op_str.startswith('ecx, '),
                    'unclassified selector source ' + hex(i.address))
            operand = source.operands[1]
            require(operand.type == X86_OP_IMM, 'nonconstant selector source ' + hex(i.address))
            ids = (operand.imm,)
        require(all(1 <= n <= 72 for n in ids), 'selector zero/out of range')
        all_ids.update(ids)
        call_evidence.append(dict(call=row(i), reaching_definition=row(source), ids=list(ids)))
    require(set(DYNAMIC).issubset({int(r['call']['rva'], 16) for r in call_evidence}),
            'dynamic selector site changed')
    require(all_ids == set(range(1, 73)) - {0x30}, 'selector ID domain changed')
    first_template_helper = next(i for i in root_ins if i.mnemonic == 'call' and
                                 i.operands[0].type == X86_OP_IMM and
                                 0x1257720 <= i.operands[0].imm < 0x125803D)
    require(first_template_helper.address == 0x1258C17 and
            first_template_helper.operands[0].imm == SELECT, 'appender before selector')
    id_one_calls = [(i.address, i.operands[0].imm) for i in root_ins
                    if 0x125C158 <= i.address < 0x125C2C6 and i.mnemonic == 'call' and
                    i.operands[0].type == X86_OP_IMM and
                    i.operands[0].imm in (SELECT, 0x1257830, 0x12578E0,
                                           0x1257C90, 0x1257D50, 0x1257E00, 0x1257EF0)]
    require(id_one_calls == [(0x125C158, SELECT), (0x125C164, 0x1257D50),
                             (0x125C170, 0x1257EF0), (0x125C17C, 0x1257E00),
                             (0x125C188, 0x1257E00), (0x125C194, 0x1257E00)],
            'ID1 helper ordering changed')

    dynamic_pins = pins(by, {
        0x125A263: 'mov ebx, 2', 0x125A2DC: 'sub rbx, 1',
        0x125A2E0: 'jne 0x125a270', 0x125A2EA: 'lea ecx, [rbx + 0x3d]',
        0x125A341: 'mov ebx, 4', 0x125A3B9: 'sub rbx, 1',
        0x125A3BD: 'jne 0x125a350', 0x125A797: 'lea ecx, [rbx + 0x3e]',
        0x125B462: 'mov qword ptr [rbp + 0x1fc0], 0x41',
        0x125B474: 'mov qword ptr [rbp + 0x2030], 0x42',
        0x125B4EC: 'mov qword ptr [rbp + 0x20a0], 0x43',
        0x125B5A7: 'lea rsi, [rbp + 0x1fc0]',
        0x125B5B5: 'mov r15d, 3', 0x125B5E0: 'mov ecx, dword ptr [rsi]',
        0x125B6A7: 'add rsi, 0x70', 0x125B6AB: 'sub r15, 1',
        0x125B6AF: 'jne 0x125b5e0',
        0x125B76D: 'xor eax, eax', 0x125B78D: 'lea ecx, [rax + 0x44]',
        0x1258570: 'xor r12d, r12d', 0x1260642: 'mov ebx, r12d',
        0x1260655: 'lea ecx, [rbx + 0x29]', 0x12606BA: 'inc ebx',
        0x12606BC: 'cmp ebx, 4', 0x12606BF: 'jb 0x1260650',
    })
    expected_defs = {
        ('rbx', 0x125A2EA): {0x125A2DC},
        ('rbx', 0x125A797): {0x125A3B9},
        ('rax', 0x125B78D): {0x125B76D},
        ('r12', 0x1260642): {0x1258570},
        ('rbx', 0x1260655): {0x1260642, 0x12606BA},
        ('rsi', 0x125B5E0): {0x125B5A7, 0x125B6A7},
        ('r15', 0x125B5E0): {0x125B5B5, 0x125B6AB},
    }
    dynamic_defs = []
    for (reg, at), wanted in expected_defs.items():
        got = reaching(root_ins, preds, reg)[at]
        require(got == wanted, 'dynamic source changed ' + hex(at))
        dynamic_defs.append(dict(register=reg, at=hex(at), definitions=[hex(x) for x in sorted(got)]))

    # The prior counter-bounds artifact contains finite, complete same-D roots.
    bounds = prior['indexed_float_pool_counter_bounds_evidence.json']
    builder = []
    update = []
    for span in bounds['code_spans'].values():
        if int(span['root'], 16) in (0x142CB90, 0x142D870):
            dest = builder if int(span['root'], 16) == 0x142CB90 else update
            dest.extend(checked_span(im, span))
    require((len(builder), len(update)) == (673, 1186), 'same-D root coverage changed')
    direct = {}
    for label, instructions in [('builder', builder), ('update', update)]:
        direct[label] = [row(i) for i in instructions if i.mnemonic == 'call' and
                         i.operands[0].type == X86_OP_IMM and i.operands[0].imm == 0x140C2E0]
    require([int(r['rva'], 16) for r in direct['builder']] ==
            [0x142D0BD, 0x142D144, 0x142D171], 'builder C2E0 sites changed')
    require([int(r['rva'], 16) for r in direct['update']] ==
            [0x142DACA, 0x142DE6F, 0x142DF09, 0x142DFAC,
             0x142E00F, 0x142E0B1, 0x142E391], 'update C2E0 sites changed')
    b_by = {i.address: i for i in builder}
    caller_pins = pins(b_by, {
        0x142CFE9: 'mov dword ptr [rdi + r8*4 + 0x8b6b0], 0x27',
        0x142CFF7: 'mov dword ptr [rdi + r8*4 + 0x8b6b0], 0x28',
        0x142D005: 'mov dword ptr [rdi + r8*4 + 0x8b6b0], 0x26',
        0x142D013: 'mov dword ptr [rdi + r8*4 + 0x8b6b0], r14d',
        0x142D02A: 'mov dword ptr [rdi + rcx*4 + 0x8b6b0], eax',
        0x142D069: 'cmp byte ptr [r15 + rsi + 0x24c], r12b',
        0x142D082: 'jne 0x142d165', 0x142D090: 'jne 0x142d165',
        0x142D09F: 'je 0x142d165',
        0x142D0AF: 'lea rcx, [rbx + 0x886c0]',
        0x142D0B6: 'mov edx, dword ptr [rdi + rax*4 + 0x8b6b0]',
        0x142D13E: 'setbe dl', 0x142D141: 'add edx, 0x2d',
        0x142D165: 'lea rcx, [rdi + 0x886c0]',
        0x142D16C: 'xor edx, edx',
        0x142D16E: 'add rcx, r14',
        0x142D171: 'call 0x140c2e0',
    })
    u_by = {i.address: i for i in update}
    update_id_pins = pins(u_by, {
        0x142DABE: 'mov edx, 0x1b',
        0x142DE63: 'mov edx, 0x19',
        0x142DF00: 'mov edx, 0x1b',
        0x142DF9D: 'mov edx, 0x1a',
        0x142E007: 'mov edx, 0x1b',
        0x142E096: 'mov edx, 0x1b',
        0x142E376: 'mov edx, 0x1b',
    })
    native = prior['indexed_float_subobjects_evidence.json']
    native_ins = []
    for span in native['code_spans'].values():
        if 0x140C2E0 <= int(span['start'], 16) < 0x140C529:
            native_ins.extend(checked_span(im, span))
    n_by = {i.address: i for i in native_ins}
    native_pins = pins(n_by, {
        0x140C2E8: 'mov eax, dword ptr [rcx + 0x1c]',
        0x140C2F0: 'cmp eax, edx',
        0x140C2F2: 'je 0x140c4b3',
        0x140C302: 'test eax, eax',
        0x140C304: 'je 0x140c30b',
        0x140C306: 'call 0x140c200',
        0x140C319: 'mov dword ptr [r14 + 0x1c], ebx',
        0x140C323: 'cmp dword ptr [r12 + 0xa0e0], r15d',
        0x140C32B: 'jbe 0x140c4a9',
    })

    result = {
        'schema_version': 1,
        'source_sha256': EXPECTED,
        'prior_sha256': PRIOR,
        'runtime_verified': False,
        'native_execution': False,
        'initializer': {
            'start': hex(INIT_START), 'end_exclusive': hex(INIT_END),
            'sha256': initial['sha256'], 'instruction_count': len(root_ins),
            'normal_cfg_reachable': True, 'bulk_zero': startup,
            'table_base': hex(BASE), 'table_stride': hex(STRIDE),
            'table_bytes': TABLE_SIZE, 'template_zero_node_count_offset': hex(0xA0E0),
            'first_template_helper_call': row(first_template_helper),
            'id_one_helper_sequence': [{'site': hex(a), 'helper': hex(b)} for a, b in id_one_calls],
            'selector_call_count': len(selector_calls),
            'selector_calls': call_evidence,
            'selected_ids': sorted(all_ids),
            'unselected_ids_within_0_to_72': [0, 0x30],
            'dynamic_source_pins': dynamic_pins,
            'dynamic_reaching_definitions': dynamic_defs,
            'helper_semantic_pins': list(helper_pins.values()),
            'helper_global_references': helper_refs,
            'conditional_id_zero_result': {'node_count': 0, 'emitted_nodes': 0,
                'emitted_events': 0, 'condition': 'normal captured initializer flow and byte-fill/helper semantics; opaque callees do not mutate template 0, selector, dynamic ID source locals, loop registers or target pointers; all emit/payload writes remain within their selected template bounds; no later writer changes template 0'},
        },
        'same_D_caller_roots': {
            'builder': {'root': '0x142cb90', 'instructions': len(builder), 'direct_C2E0_calls': direct['builder']},
            'update': {'root': '0x142d870', 'instructions': len(update), 'direct_C2E0_calls': direct['update']},
            'builder_pins': caller_pins,
            'update_id_pins': update_id_pins,
            'explicit_id_zero': '0x142d171',
            'dynamic_primary': '0x142d0bd',
            'third_S_ids': [0x2D, 0x2E],
        },
        'native_C2E0_pins': native_pins,
        'limits': [
            'No writable template snapshot, live invocation or later-writer closure.',
            'Initializer proof is finite to direct calls in root 1258050 and pinned helper semantics; opaque callees must not mutate template 0 or selector, and every emission must stay inside its selected template.',
            'Only ID1 direct helper order was checked for immediate last-node use; no all-template overflow proof was attempted.',
            'Same-D caller scan is finite to complete captured roots 142CB90 and 142D870; other callers are not excluded.',
            'Builder dynamic table IDs require its previously stated valid-count, intact table and callee noninterference preconditions.',
            'Zero-node ID0 is not a full-record cleanup, and C2E0 same-ID early return does not repair partial/inconsistent state.',
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
