"""Pin B54E00 registry update and its one roster-reading direct helper offline.

Only the fixed build-25480438 saved capture is read. This does not traverse the
callee tree, access a game process, emit native patches, or establish runtime
ownership of the roster and registry entries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import capstone as cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row

ROOT = 0xB54E00
HELPER = 0x606520
ASSOCIATED = 0xFD9BA0
INVENTORY = HERE / 'roster_property_consumers_native_inventory.json'
INVENTORY_SHA = '0b664e0f65601221399bfd01ad92f248d373b30376c5e2fdac6b7a702dc93dc2'

SPECS = {
    ROOT: dict(end=0xB55169, instructions=203,
               sha256='8f679d31841a3cce6ee1f4d66ec47bc89aa9a347b68939bc4264ec25bf8bd783',
               fragments=[
                   (0xB54E00, 0xB54E28, 0x24AD4C8, '73b5b98498ae49c1ec6cf1270a4a74fe6be011795803c216389e541af67297fb'),
                   (0xB54E28, 0xB5515F, 0x24AD4D4, 'dbcb0cc62ac4fbdfe7d7b49db73630a549fab108f4f2c935dcf975d8bbbb2f2a'),
                   (0xB5515F, 0xB55169, 0x24AD4F8, '217ec2994cd9258a1bc52685bba27b170e55211e4a77469fd209b7fd5a42c126')],
               rips=[(0xB54E0A, 0x3326E68), (0xB54E91, 0x3326308),
                     (0xB54EE2, 0x3326348), (0xB54F19, 0x3326468),
                     (0xB54F30, 0x3483C34), (0xB5505F, 0x3326468),
                     (0xB5506C, 0x3483C20)],
               calls=[(0xB54E7F, 0xFD9AF0), (0xB54F23, HELPER),
                      (0xB54FBF, 0x1731A60), (0xB54FE6, 0x1731A60),
                      (0xB5503A, 0xFD9BA0), (0xB5512C, 0x7B5760)],
               indirect=[0xB54EA7, 0xB54EAF], branches=40, returns=[0xB55168]),
    HELPER: dict(end=0x60662F, instructions=72,
                 sha256='ca355caa6f6c7309202c504fadbfaae2c93fff84f5c846bf8be60d839631c39e',
                 fragments=[(0x606520, 0x60662F, 0x2424B38,
                             'ca355caa6f6c7309202c504fadbfaae2c93fff84f5c846bf8be60d839631c39e')],
                 rips=[(0x606552, 0x346BF98), (0x6065DC, 0x348456C),
                       (0x6065F7, 0x3483C34)], calls=[], indirect=[],
                 branches=11, returns=[0x60661C]),
    ASSOCIATED: dict(end=0xFD9C7C, instructions=59,
                     sha256='d81d3d8b8d73c6301dae0432dbb840658fe113ba8a356c084da5c6d28ab51ad7',
                     fragments=[
                         (0xFD9BA0, 0xFD9BD2, 0x24CD914, '5b7f1c6e30ea0a2bb3a9406220576da6d31a3481d506dac6fffb91ab220d44a9'),
                         (0xFD9BD2, 0xFD9C49, 0x24CD91C, '9a736afc44df63827cf0168b1c699dcb2f8d4211b6696255fb09c692aa7ebc34'),
                         (0xFD9C49, 0xFD9C7C, 0x24CD93C, '300bff071628cfdab13d9da6e5947a9bf49b50d8eced0d1924bf324faa1bcfad')],
                     rips=[(0xFD9BA4, 0x346BF98), (0xFD9BB9, 0x348456C),
                           (0xFD9C68, 0x348456C)], calls=[], indirect=[],
                     branches=6, returns=[0xFD9BC8, 0xFD9C67, 0xFD9C7B]),
}

# Fixed bytes are independent of Capstone's formatting. They pin the operand
# and pointer-derivation points an emitter must consider together.
SITES = {
    ROOT: {
        'registry_global': (0xB54E0A, '4c8b2d57207d02'),
        'registry_count_initial': (0xB54E1B, '4539a5f0100000'),
        'registry_tag_load': (0xB54E47, '418b84cd00110000'),
        'tag73_global_roster': (0xB54F19, '488b0d48157d02'),
        'tag73_roster_helper_call': (0xB54F23, 'e8f815abff'),
        'tag69_registry_roster': (0xB55003, '4d8bb4cdf8100000'),
        'tag69_dense_count': (0xB5500D, '418bae84000000'),
        'property_loop_base': (0xB5501C, '498dbea8030000'),
        'property_first_dword': (0xB55030, '8b17'),
        'property_helper_call': (0xB5503A, 'e8614b4800'),
        'property_loop_advance': (0xB5504A, '4883c720'),
        'first_pointer_read': (0xB55057, '498b84f6e8000000'),
        'map_global_roster': (0xB5505F, '4c8b1d02147d02'),
        'property_loop_ordinal': (0xB55066, '448bce'),
        'map_capacity': (0xB55074, '458b93d8000000'),
        'map_multiplier': (0xB5507D, '418bbbe0000000'),
        'map_buckets': (0xB55090, '4d8bbbd0000000'),
        'map_empty_key': (0xB55097, '418babdc000000'),
        'map_ordinal': (0xB5510A, '438b44c704'),
        'aux_ordinal_scale': (0xB550C9, '486bc138'),
        'aux_state_compare': (0xB550CD, '4283bc18e002000002'),
        'aux_state_write': (0xB550D8, '42c78418e002000001000000'),
        'second_pointer_read': (0xB550E9, '498b84f6e8000000'),
        'property_flag_scale': (0xB550F7, '49c1e105'),
        'property_flag_clear': (0xB550FB, '4383a431ac030000fe'),
    },
    HELPER: {
        'explicit_roster_dense_count': (0x60653D, '448ba984000000'),
        'property_loop_base': (0x606559, '4c8db1a8030000'),
        'property_first_dword': (0x606560, '458b0e'),
        'property_loop_advance': (0x6065EA, '4983c620'),
        'output_dword_store': (0x60660C, '41890424'),
        'restore_explicit_roster': (0x60661D, '488b4c2430'),
        'matched_pointer_read': (0x606622, '488b8cd9e8000000'),
    },
    ASSOCIATED: {
        'associated_context_global': (0xFD9BA4, '4c8b1ded234902'),
        'input_id_sentinel_compare': (0xFD9BB1, '81faff7f0000'),
        'sentinel_output': (0xFD9BBF, '8901'),
        'reverse_map_capacity': (0xFD9BC9, '458b93d02ef200'),
        'reverse_map_buckets': (0xFD9BF9, '498bbbc82ef200'),
        'miss_null_address': (0xFD9C2F, '33c0'),
        'possibly_null_key_compare': (0xFD9C44, '443900'),
        'found_output': (0xFD9C5D, '418901'),
        'missing_output': (0xFD9C71, '418901'),
    },
}

ARRAYS = {
    ROOT: {
        'property_loop_base': (0xB5501C, 1, 'address_only', 'registry S+3A8, then +20h per dense ordinal'),
        'property_first_dword': (0xB55030, 1, 'read', 'RDI-derived property[ordinal] first DWORD'),
        'first_pointer_read': (0xB55057, 1, 'read', 'registry S+E8+property ordinal*8'),
        'aux_state_compare': (0xB550CD, 0, 'read', 'global S+2E0+map ordinal*38h'),
        'aux_state_write': (0xB550D8, 0, 'write', 'global S+2E0+map ordinal*38h'),
        'second_pointer_read': (0xB550E9, 1, 'read', 'registry S+E8+property ordinal*8'),
        'property_flag_clear': (0xB550FB, 0, 'read_write', 'registry S+3AC+property ordinal*20h'),
    },
    HELPER: {
        'property_loop_base': (0x606559, 1, 'address_only', 'explicit RCX=S+3A8, then +20h per dense ordinal'),
        'property_first_dword': (0x606560, 1, 'read', 'R14-derived property[ordinal] first DWORD'),
        'matched_pointer_read': (0x606622, 1, 'read', 'explicit S+E8+property ordinal*8'),
    },
    ASSOCIATED: {},
}


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def detail(ins):
    result = row(ins)
    result['encoding'] = dict(rex=ins.rex, modrm=ins.modrm, sib=ins.sib,
                              displacement_offset=ins.disp_offset,
                              displacement_size=ins.disp_size,
                              immediate_offset=ins.imm_offset,
                              immediate_size=ins.imm_size)
    return result


def pin_fragments(im, entry, spec):
    found = [f for f in im.functions if im.root(f[0])[0] == entry]
    require(found == [(a, b, u) for a, b, u, _ in spec['fragments']],
            'unwind fragments changed at ' + hex(entry))
    result = []
    for a, b, u, expected_sha in spec['fragments']:
        blob = im.read(a, b-a)
        require(sha(blob) == expected_sha, 'fragment bytes changed at ' + hex(a))
        result.append(dict(start=hex(a), end_exclusive=hex(b), unwind=hex(u),
                           size_bytes=len(blob), sha256=sha(blob)))
    return result


def pin_flow(ins, entry, spec):
    by_addr = {x.address: x for x in ins}
    cfg, branches, relocs, indirect = {}, [], [], []
    for x in ins:
        next_addr = x.address+x.size
        for op in x.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                relocs.append(dict(kind='rip_address' if x.mnemonic == 'lea' else 'rip_memory',
                                   rva=hex(x.address), target_rva=hex(next_addr+op.mem.disp),
                                   displacement_offset=x.disp_offset,
                                   displacement_size=x.disp_size, instruction=detail(x)))
        if x.group(cs.CS_GRP_CALL):
            if x.operands[0].type == X86_OP_IMM:
                relocs.append(dict(kind='call_rel32', rva=hex(x.address),
                                   target_rva=hex(x.operands[0].imm),
                                   displacement_offset=x.imm_offset,
                                   displacement_size=x.imm_size, instruction=detail(x)))
            else:
                indirect.append(dict(kind='call_indirect', rva=hex(x.address), instruction=detail(x)))
        if x.group(cs.CS_GRP_RET):
            successors = []
        elif x.group(cs.CS_GRP_JUMP):
            require(len(x.operands) == 1 and x.operands[0].type == X86_OP_IMM,
                    'unmodeled indirect jump at ' + hex(x.address))
            target = x.operands[0].imm
            successors = [target] if x.mnemonic == 'jmp' else [target, next_addr]
            branches.append(dict(kind='unconditional' if x.mnemonic == 'jmp' else 'conditional',
                                 rva=hex(x.address), target_rva=hex(target),
                                 instruction=detail(x)))
        else:
            successors = [next_addr]
        require(all(target in by_addr for target in successors),
                'CFG edge leaves instruction boundaries at ' + hex(x.address))
        cfg[hex(x.address)] = [hex(target) for target in successors]
    seen, pending = set(), [entry]
    while pending:
        at = pending.pop()
        if at not in seen:
            seen.add(at)
            pending.extend(int(target, 16) for target in cfg[hex(at)])
    require(seen == set(by_addr), 'unreachable instruction in ' + hex(entry))
    require(len(branches) == spec['branches'], 'branch count changed at ' + hex(entry))
    require([x.address for x in ins if x.group(cs.CS_GRP_RET)] == spec['returns'],
            'return sites changed at ' + hex(entry))
    require({(int(r['rva'], 16), int(r['target_rva'], 16)) for r in relocs if r['kind'].startswith('rip_')}
            == set(spec['rips']), 'RIP reference set changed at ' + hex(entry))
    require({(int(r['rva'], 16), int(r['target_rva'], 16)) for r in relocs if r['kind'] == 'call_rel32'}
            == set(spec['calls']), 'direct call set changed at ' + hex(entry))
    require({int(r['rva'], 16) for r in indirect} == set(spec['indirect']),
            'indirect call set changed at ' + hex(entry))
    require(all(r['displacement_size'] == 4 for r in relocs if r['kind'].startswith('rip_')),
            'non-rel32 RIP reference')
    require(all(r['displacement_size'] == 4 for r in relocs if r['kind'] == 'call_rel32'),
            'non-rel32 direct call')
    return cfg, branches, relocs, indirect


def pin_sites(ins, entry):
    by_addr = {x.address: x for x in ins}
    required = SITES[entry]
    require(all(at in by_addr and by_addr[at].bytes.hex() == expected
                for at, expected in required.values()),
            'critical source site changed in ' + hex(entry))
    critical = {name: detail(by_addr[at]) for name, (at, _) in required.items()}
    arrays = []
    for name, (at, op_index, access, meaning) in ARRAYS[entry].items():
        x = by_addr[at]
        require(len(x.operands) > op_index and x.operands[op_index].type == X86_OP_MEM,
                'array operand changed at ' + hex(at))
        op = x.operands[op_index]
        arrays.append(dict(group=name, rva=hex(at), operand_index=op_index,
                           access=access, width_bytes=op.size,
                           base_register=x.reg_name(op.mem.base),
                           index_register=x.reg_name(op.mem.index),
                           index_scale=op.mem.scale,
                           displacement=op.mem.disp,
                           displacement_offset=x.disp_offset,
                           displacement_size=x.disp_size,
                           meaning=meaning, instruction=detail(x)))
    return critical, arrays


def pin_body(im, entry, spec):
    fragments = pin_fragments(im, entry, spec)
    raw = im.read(entry, spec['end']-entry)
    require(sha(raw) == spec['sha256'], 'complete body bytes changed at ' + hex(entry))
    ins = list(im.md.disasm(raw, entry))
    require(len(ins) == spec['instructions'] and sum(x.size for x in ins) == len(raw),
            'incomplete body decode at ' + hex(entry))
    require(len({x.address for x in ins}) == len(ins), 'duplicate instruction boundary')
    cfg, branches, relocs, indirect = pin_flow(ins, entry, spec)
    critical, arrays = pin_sites(ins, entry)
    if entry == ROOT:
        abi = ('Windows x64; ECX=input entity ID, R13=[global 3326E68] registry; '
               'tag69 R14=[registry+10F8+index*16] roster S, EBX=input ID. '
               'B5505F independently loads global 3326468 as R11 for map/aux. '
               'Three pushes, 50h local frame, one RET; tag115 and tag73/2E branches retained.')
    elif entry == HELPER:
        abi = ('Windows x64; RCX=explicit roster S, RDX=out-DWORD pointer, R8D=input ID. '
               'R13D=[S+84] dense count, R14 iterates S+3A8 property by 20h; '
               'on matching relationship reads pointer[S+E8+ordinal*8] and writes entity ID, '
               'otherwise writes global sentinel DWORD. One RET.')
    else:
        abi = ('Windows x64; RCX=out-DWORD pointer, EDX=associated ID. '
               'Uses global 346BF98 context reverse map F22EC8/D0/D4/D8 and F32F20+ordinal*18h; '
               'writes out-DWORD and returns its pointer in RAX. ID 7FFF directly writes '
               'global 348456C sentinel. No calls or inline roster-array reads; three RET paths.')
    return dict(entry=hex(entry), end_exclusive=hex(spec['end']), size_bytes=len(raw),
                sha256=sha(raw), bytes_hex=raw.hex(), fragments=fragments, abi=abi,
                instructions=[detail(x) for x in ins], cfg=cfg, branches=branches,
                external_relocations=relocs, indirect_controls=indirect,
                direct_calls=[r for r in relocs if r['kind'] == 'call_rel32'],
                critical_sites=critical, array_sites=arrays,
                exit_sites=[detail(x) for x in ins if x.group(cs.CS_GRP_RET)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'refusing to overwrite output')
    require(sha(INVENTORY.read_bytes()) == INVENTORY_SHA, 'inventory fingerprint changed')
    im = Image(args.evidence)
    bodies = {hex(entry): pin_body(im, entry, spec) for entry, spec in SPECS.items()}
    result = dict(source_sha256=EXPECTED,
                  capture_identity_sha256=im.report['capture_sha256'],
                  inventory_sha256=INVENTORY_SHA,
                  replay_sha256=sha(Path(__file__).read_bytes()), bodies=bodies,
                  dependency='B54F23 directly calls 606520; both bodies use inline roster property/pointer and must share the same sidecar binding. B5503A directly calls FD9BA0, pinned only as an unchanged test helper.',
                  roster_identity='B54E00 tag69 S comes from registry3326E68+10F8; B5505F aux/map S is independently loaded from global3326468. Equality is an external integration precondition.',
                  finite_scope='Complete B54E00 chained body, the one roster-reading 606520 helper, and unchanged direct FD9BA0 for real-instruction tests; other direct/indirect callees are boundaries.',
                  limits=[
                      'Tag69 property iteration and tag73 helper both use S+3A8; tag69 also directly reads S+E8 and compares/writes S+2E0 aux and clears S+3AC property flag.',
                      'Original tag69 map miss or FFFFFFFF ordinal can reach aux indexing; body has no eight-slot map/binding validation.',
                      'FD9BA0 converts property ID via a different context reverse map, not an inline roster read; it is pinned for tests, not emitted as a sidecar modification. Capacity-zero or exhausted-probe null reads remain outside the valid-map contract.',
                      'No runtime registry ownership, S equality, helper side effects, caller reachability, native emission, hook, live process or multiplayer execution is established.'])
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(args.output), bodies={k:dict(size_bytes=v['size_bytes'],
          instructions=len(v['instructions']), sha256=v['sha256'],
          branches=len(v['branches']), relocations=len(v['external_relocations']),
          array_sites=len(v['array_sites'])) for k,v in bodies.items()})))


if __name__ == '__main__':
    main()
