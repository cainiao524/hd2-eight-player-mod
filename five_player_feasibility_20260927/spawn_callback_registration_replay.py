"""Replay the proven leaf initializer and roster callback index 239 offline."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'research_handoff_20260927'/'indirect'))
from inspect_capture import EXPECTED, Image, require, row
from capstone.x86 import X86_OP_MEM, X86_OP_REG, X86_REG_RAX, X86_REG_RCX, X86_REG_RIP

START, END = 0x556D90, 0x55E1E3
TABLES = {
    0xF0B6F0: 0x540850, 0xF0C110: 0x540920, 0xF0CB30: 0x540AE0,
    0xF0D550: 0x540B10, 0xF0DF70: 0x540B20, 0xF0E990: 0x540A40,
    0xF0F3B0: 0x540B30, 0xF0FDD0: 0x540B50, 0xF107F0: 0x540B40,
    0xF11210: 0x540B60,
}
PINS = {
    'context_plus_40_and_constructor_chain': [
        0xFDA1A4, 0xFDA352, 0xFDA356, 0xFDA375, 0x551B7A, 0x551B7D,
        0x568236, 0x568239, 0x568242, 0x568EC8, 0x568ECF,
        0x5565EF, 0x5565F9, 0xFDC165, 0xFDC250, 0xFDC25A, 0xFDC2A0, 0xFDC2B1],
    'known_three_dispatch_readers': [
        0x581348, 0x58140A, 0x58140E, 0x581416, 0x581421,
        0x581505, 0x581509, 0x58152F,
        0x5817B0, 0x581A37, 0x581A3B, 0x581A43, 0x581A4E],
    'registered_four_slot_insertion': [
        0x540856, 0x540863, 0x54086A, 0x54086E, 0x540871, 0x540873, 0x5408FB, 0x540912,
        0x54092A, 0x540931, 0x540934, 0x54093A, 0x54093C, 0x54093F, 0x540941,
        0x540957, 0x540968, 0x540A01, 0x540A0D, 0x540A24],
    'second_table_wrapper': [0x540AE0, 0x540AE4, 0x540AE9, 0x540AF1, 0x540AF6, 0x540AF9, 0x540AFE, 0x540B02],
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    out = Path(a.output)
    require(not out.exists(), 'refusing overwrite')
    im = Image(a.evidence)
    pins = {}
    for group, rvas in PINS.items():
        pins[group] = []
        for rva in rvas:
            i = im.instruction(rva)
            require(i is not None, 'not an unwind instruction boundary '+hex(rva))
            pins[group].append(dict(**row(i), root=hex(im.root(rva)[0]),
                                   decode_fragment=[hex(v) for v in im.containing(rva)]))
    call = im.instruction(0x568239)
    require(call.mnemonic == 'call' and call.op_str == '0x556d90', 'leaf entry proof changed')
    raw = im.read(START, END-START)
    ins = list(im.md.disasm(raw, START))
    require(len(ins) == 4255 and sum(i.size for i in ins) == len(raw), 'leaf decode coverage mismatch')
    require(ins[-1].address == END-1 and ins[-1].mnemonic == 'ret', 'leaf return mismatch')
    assignments = []
    # Every instruction before RET must match these pairs. This proves RCX is
    # unchanged, no hidden control-flow path exists, and each store's source.
    for k in range(0, len(ins)-1, 2):
        lea, store = ins[k:k+2]
        require(lea.mnemonic == 'lea' and len(lea.operands) == 2 and
                lea.operands[0].type == X86_OP_REG and lea.operands[0].reg == X86_REG_RAX and
                lea.operands[1].type == X86_OP_MEM and lea.operands[1].mem.base == X86_REG_RIP,
                'unexpected initializer producer at '+hex(lea.address))
        require(store.mnemonic == 'mov' and len(store.operands) == 2 and
                store.operands[0].type == X86_OP_MEM and store.operands[0].size == 8 and
                store.operands[0].mem.base == X86_REG_RCX and store.operands[0].mem.index == 0 and
                store.operands[1].type == X86_OP_REG and store.operands[1].reg == X86_REG_RAX,
                'unexpected initializer store at '+hex(store.address))
        target = lea.address+lea.size+lea.operands[1].mem.disp
        assignments.append(dict(destination_offset=hex(store.operands[0].mem.disp), target_rva=hex(target),
                                lea=row(lea), store=row(store)))
    require(len(assignments) == 2127, 'assignment count mismatch')
    require(len({r['destination_offset'] for r in assignments}) == len(assignments), 'duplicate initializer destination')
    selected = []
    for base, expected in TABLES.items():
        off = base+239*8
        matches = [r for r in assignments if int(r['destination_offset'], 16) == off]
        require(len(matches) == 1 and int(matches[0]['target_rva'], 16) == expected, 'index 239 registration mismatch')
        selected.append(dict(table_base_offset=hex(base), component_index=239, **matches[0]))
    # The initialized callback slot itself proves this leaf's entry; the body
    # is decoded from that pointer to its tail transfer, not from arbitrary bytes.
    target = 0x540B10
    leaf = list(im.md.disasm(im.read(target, 11), target))
    require(len(leaf) == 3 and sum(i.size for i in leaf) == 11 and leaf[-1].mnemonic == 'jmp' and
            leaf[-1].op_str == '0x6054f0', 'post-dispatch leaf mismatch')
    result = dict(
        source_sha256=EXPECTED, capture_identity_sha256=im.report['capture_sha256'],
        initializer=dict(entry=hex(START), end_exclusive=hex(END), sha256=hashlib.sha256(raw).hexdigest(),
                         size=len(raw), instructions=len(ins), assignments=len(assignments),
                         entry_proof_call='0x568239', entry_proof_call_unwind_root='0x568230',
                         unwind_present=False, validation='Complete sequential decode: exactly 2127 RIP-LEA/RCX-store pairs and RET.'),
        context_relation='Both FDA190 constructor and FDC140 dispatch pass original context+0x40 to the component owner.',
        pins=pins, component_239=selected,
        post_dispatch_leaf=dict(entry=hex(target), entry_proof_initializer_store='0x55c001',
                                sha256=hashlib.sha256(im.read(target, 11)).hexdigest(),
                                instructions=[row(i) for i in leaf]),
        targets_absent_from_this_initializer=[hex(t) for t in [0x60CA80, 0x60CBA0]
                                            if all(int(r['target_rva'], 16) != t for r in assignments)],
        limits=[
            'Static initialization binds component index 239 to these callbacks; no live table values or invocation were observed.',
            'The resource hash-to-component-list mapping is separate evidence and is not inferred from callback code.',
            'Later callback table rewrites or uncaptured code are not excluded.',
            'Table bases other than F0C110/F0CB30/F0D550 are recorded without claiming their caller phase.',
            'No eight-player allocation, game-file modification, or live process access performed.'])
    out.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(out), initializer_instructions=len(ins), initializer_assignments=len(assignments),
                          unwind_pins=sum(len(v) for v in pins.values()), registered_index=239)))


if __name__ == '__main__':
    main()
