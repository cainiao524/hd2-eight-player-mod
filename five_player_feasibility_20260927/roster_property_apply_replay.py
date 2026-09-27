"""Offline lifecycle interpretation of already-proven component-239 callbacks.

Reuses the pinned registration artifact; does not repeat its initializer scan.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'research_handoff_20260927'/'indirect'))
from inspect_capture import EXPECTED, Image, require, row
from capstone.x86 import X86_OP_MEM, X86_REG_RBP, X86_REG_RIP

REGISTRATION = 'spawn_callback_registration_evidence_v2.json'
REGISTRATION_SHA = '142df92c5411697e03914be224d30e05f85a02011c2c96e00be2e2aa9b9a5109'
LEAVES = {0x540B20: (8, 'jmp 0x605950'), 0x540B30: (8, 'jmp 0x60cf50'),
          0x540B40: (8, 'jmp 0x60d300'), 0x540B50: (3, 'ret 0')}
RANGES = {
    'before_removal_dispatch': [(0xFDC943, 0xFDC955), (0xFDCC53, 0xFDCC65), (0xFDCD77, 0xFDCDC5)],
    'cleanup_uses_roster_and_avatar_reference': [(0x605962, 0x60597B), (0x605A01, 0x605A68),
                                               (0x605B84, 0x605BCE), (0x605DB1, 0x605DCB),
                                               (0x605EF1, 0x605F28)],
    'bit_zero_set_before_promotion': [(0xFDBCE6, 0xFDBCEA), (0xFDBDD0, 0xFDBDEA), (0xFDBE30, 0xFDBE4A)],
    'promotion_ordinal_and_boundary': [(0x60CF68, 0x60CF81), (0x60CFD0, 0x60CFF1), (0x60D036, 0x60D07D)],
    'promotion_initializes_70_byte_state': [(0x60CFF1, 0x60D025), (0x60D079, 0x60D0AD)],
    'promotion_swaps_38_byte_state': [(0x60D0CD, 0x60D158)],
    'promotion_swaps_index_bearing_record': [(0x60D192, 0x60D1E8), (0x60D264, 0x60D268), (0x60D2D3, 0x60D2D7)],
    'before_bit_zero_clear_dispatch': [(0xFDBF58, 0xFDBF85), (0x581F50, 0x581F69), (0x581F80, 0x581F99)],
    'demotion_ordinal_boundary_and_pointer_swap': [(0x60D312, 0x60D32B), (0x60D370, 0x60D384),
                                                 (0x60D394, 0x60D3D1)],
    'demotion_swaps_70_byte_state': [(0x60D3F6, 0x60D514)],
    'demotion_swaps_38_byte_state': [(0x60D548, 0x60D5D3)],
    'demotion_swaps_index_bearing_record': [(0x60D60D, 0x60D660), (0x60D6DB, 0x60D6DF), (0x60D743, 0x60D747)],
    'disconnected_named_notification': [(0x540B64, 0x540B7A), (0x540BE6, 0x540C1A)],
}
ROOTS = [0x605950, 0x60CF50, 0x60D300, 0x540B60, 0xFDC820, 0xFDBB40, 0xFDBEA0, 0x581E10]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    out = Path(a.output)
    require(not out.exists(), 'refusing overwrite')
    im = Image(a.evidence)
    reg_raw = (HERE/REGISTRATION).read_bytes()
    require(sha(reg_raw) == REGISTRATION_SHA, 'registration artifact changed')
    reg = json.loads(reg_raw)
    # Validate existing registration's full leaf bytes by its fingerprint, then
    # reuse its proven instruction boundaries and target mapping.
    init = reg['initializer']
    require(sha(im.read(int(init['entry'], 16), init['size'])) == init['sha256'], 'initializer source changed')
    leaves = []
    for entry, (size, transfer) in LEAVES.items():
        matches = [r for r in reg['component_239'] if int(r['target_rva'], 16) == entry]
        require(len(matches) == 1, 'callback entry not uniquely registered')
        proof = matches[0]
        for key in ['lea', 'store']:
            pin = proof[key]
            require(im.read(int(pin['rva'], 16), len(bytes.fromhex(pin['bytes']))).hex() == pin['bytes'], 'registration pin changed')
        data = im.read(entry, size)
        decoded = list(im.md.disasm(data, entry))
        require(sum(i.size for i in decoded) == size, 'callback decode incomplete')
        require(decoded[-1].mnemonic+' '+decoded[-1].op_str == transfer, 'callback transfer changed')
        leaves.append(dict(entry=hex(entry), sha256=sha(data), entry_proof=proof,
                           instructions=[row(i) for i in decoded]))
    fragments = {r: [] for r in ROOTS}
    instructions = {r: [] for r in ROOTS}
    for f in im.functions:
        rt = im.root(f[0])[0]
        if rt not in fragments:
            continue
        data = im.read(f[0], f[1]-f[0])
        decoded = list(im.md.disasm(data, f[0]))
        require(sum(i.size for i in decoded) == len(data), 'function fragment decode incomplete')
        fragments[rt].append(dict(start=hex(f[0]), end_exclusive=hex(f[1]), sha256=sha(data)))
        instructions[rt].extend(decoded)
    all_ins = {i.address: (rt, i) for rt, items in instructions.items() for i in items}
    groups = {}
    for name, spans in RANGES.items():
        pins = []
        for first, last in spans:
            require(first in all_ins and last in all_ins, 'span not on proven instruction boundary')
            for addr in sorted(all_ins):
                if first <= addr <= last:
                    rt, i = all_ins[addr]
                    pins.append(dict(**row(i), root=hex(rt), decode_fragment=[hex(v) for v in im.containing(addr)]))
        groups[name] = pins
    direct = {}
    for rt in [0x60CF50, 0x60D300]:
        references = []
        for i in instructions[rt]:
            for op in i.operands:
                if (op.type == X86_OP_MEM and
                    (op.mem.base == X86_REG_RBP or op.mem.index == X86_REG_RBP) and
                    0xE8 <= op.mem.disp < 0x428):
                    references.append(dict(**row(i), displacement=hex(op.mem.disp), operand_size=op.size,
                                           access=op.access, roster_register='rbp=roster global3326468',
                                           memory_base=i.reg_name(op.mem.base),
                                           memory_index=i.reg_name(op.mem.index), memory_scale=op.mem.scale))
        direct[hex(rt)] = references
    string = im.read(0x22473B8, 13)
    require(string == b'disconnected\0', 'named notification string changed')
    result = dict(
        source_sha256=EXPECTED, capture_identity_sha256=im.report['capture_sha256'],
        registration_proof_artifact=dict(file=REGISTRATION, sha256=REGISTRATION_SHA),
        callback_leaves=leaves, selected_instruction_groups=groups,
        full_function_fragments={hex(k): v for k, v in fragments.items()},
        direct_roster_array_references=direct,
        named_notification=dict(rva='0x22473b8', bytes=string.hex(), text='disconnected'),
        index_movement=dict(record_base='0x3a8', record_size=32, index_in_record=12,
                            index_roster_offset='0x3b4',
                            behavior='Promotion and demotion copy/swap all 32 bytes, preserving the network-index value while the roster ordinal changes.'),
        classifications={
            '0x540b20': 'Pre-removal cleanup via 605950, before the separate actual-removal callback table.',
            '0x540b30': 'Promotion into the roster prefix counted by +88; increments prefix count; initializes destination 0x70-byte state.',
            '0x540b40': 'Demotion out of that prefix; swaps four parallel arrays and decrements prefix count.',
            '0x540b50': 'Empty callback body: ret 0.',
            '0x540b60': 'Conditional disconnected=true named notification before bit0 is cleared.'},
        limits=[
            'These remaining callbacks are lifecycle operations; no generic index-property deserializer is identified here.',
            'Byte14 bit0 is described by observed set/clear and partition effects, not assigned a universal authority/local name.',
            'Direct roster displacement inventory excludes alias-relative operands and is not a complete relocation inventory.',
            'Shared 32-byte records carry more properties than index; all fields must remain associated with the same entity.',
            'No live game, new capture, modification, installation, or multiplayer verification.'])
    out.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(out), selected_instructions=sum(len(x) for x in groups.values()),
                          leaf_instructions=sum(len(x['instructions']) for x in leaves),
                          direct_array_refs={k:len(v) for k, v in direct.items()})))


if __name__ == '__main__':
    main()
