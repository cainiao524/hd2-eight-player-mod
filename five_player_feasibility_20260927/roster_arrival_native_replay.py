"""Pin the complete 6054F0 roster reader-with-effects from saved build 25480438.

FD9AF0 is included only as an unchanged direct-callee body for offline tests.
No game process, new capture, caller-tree scan, patch emission, or installation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import capstone as cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row

ROOT = 0x6054F0
CONVERT = 0xFD9AF0
INVENTORY = HERE / 'roster_property_consumers_native_inventory.json'
INVENTORY_SHA = '0b664e0f65601221399bfd01ad92f248d373b30376c5e2fdac6b7a702dc93dc2'

BODIES = {
    ROOT: dict(end=0x605947, instructions=241, branches=41,
               sha256='6ad21683150fa35285c490fb75b00d8f0af68ab36dad70cbced0bccfc745288a',
               fragments=[(0x6054F0, 0x605947, 0x2424950,
                           '6ad21683150fa35285c490fb75b00d8f0af68ab36dad70cbced0bccfc745288a')],
               calls=[(0x605718, CONVERT), (0x6058D3, 0x94C9C0),
                      (0x6058F3, 0x60C2A0), (0x60591F, 0x2088770)],
               indirect=[0x605741, 0x60574A, 0x6057E6, 0x605910],
               rips=[
                   (0x605512, 0x263C010), (0x605527, 0x3483C20),
                   (0x605530, 0x3326468), (0x6055D8, 0x346D538),
                   (0x6055EA, 0x347CEF0), (0x60569C, 0x347CE68),
                   (0x6056D0, 0x3483C34), (0x6056FA, 0x3483C34),
                   (0x60572B, 0x3326308), (0x60574C, 0x23C6D70),
                   (0x60576F, 0x213F4E0), (0x60579D, 0x347D620),
                   (0x6057A4, 0x23C79AC), (0x6057CC, 0x3326308),
                   (0x6057DF, 0x347D6A0), (0x6057E8, 0x3326340),
                   (0x6057F8, 0x347CE50), (0x605847, 0x3326E68),
                   (0x60587F, 0x3326468), (0x605894, 0x33266A0),
                   (0x6058D8, 0x3326340), (0x6058F8, 0x3326308),
                   (0x6058FF, 0x22473C8)],
               returns=[0x605946]),
    CONVERT: dict(end=0xFD9B9E, instructions=44, branches=6,
                  sha256='7fa3870d13305c77997147167ccca1f07b199c5011883b9d8442f31e831393fc',
                  fragments=[
                      (0xFD9AF0, 0xFD9B11, 0x24CD8E0,
                       'dafb4bf4837ffedca10624b0c9630ca2210c0ea0032a42227c4d3ad8f163c315'),
                      (0xFD9B11, 0xFD9B88, 0x24CD8E8,
                       '46c4088da3444faf9d2adfbd254313fc1c246e52bebf5819cc61ac653d1b53e3'),
                      (0xFD9B88, 0xFD9B9E, 0x24CD904,
                       'f81d1358a645bddaf7439389e0c7effac89175b7b77bbe7e7c40cf03349e0bcd')],
                  calls=[], indirect=[],
                  rips=[(0xFD9AF4, 0x348456C), (0xFD9AFC, 0x2154544),
                        (0xFD9B07, 0x346BF98)],
                  returns=[0xFD9B06, 0xFD9B9D]),
}

# Every S-inline roster operand, including the two bases consumed by later
# pointer/property reads. Header/map and non-roster object operands are separate.
ARRAY_SITES = {
    0x6055BB: ('pointer', 1, 'read', '488b8cd7e8000000'),
    0x6055CD: ('property', 0, 'read_write', '818c3aac03000000080000'),
    0x60561F: ('property', 1, 'derived_base', '4c8d9fac030000'),
    0x605626: ('pointer', 1, 'derived_base', '4c8d97e8000000'),
    0x605665: ('primary', 0, 'write', 'c7843b4001000005000000'),
    0x605684: ('primary', 0, 'write', 'c7843b4001000008000000'),
    0x605691: ('primary', 0, 'write', 'c7843b4001000001000000'),
    0x6056A6: ('primary', 0, 'write', '48c7843b6801000000000000'),
    0x6056B8: ('aux', 0, 'write', 'c7843ed0020000ff7f0000'),
    0x6056C8: ('aux', 0, 'write', 'c6843edc02000001'),
    0x6056D6: ('aux', 0, 'write', '89843ee8020000'),
    0x6056E6: ('property', 1, 'read', '0fb68c38ac030000'),
    0x6056F3: ('aux', 0, 'write', '888c3edc020000'),
    0x605700: ('aux', 0, 'write', '89843ee8020000'),
    0x605709: ('aux', 0, 'write', 'c7843ee002000003000000'),
    0x605758: ('aux', 0, 'write', '4889843ec8020000'),
    0x605760: ('property', 1, 'read', '8b842fb4030000'),
    0x605801: ('aux', 1, 'read', '4c8b8c3ec8020000'),
    0x60583C: ('aux', 0, 'write', 'c7843ee002000001000000'),
}

COUNT_AND_BINDING_SITES = {
    0x605530: '488b3d310fd202',     # initial global S -> RDI
    0x60560E: '8bb784000000',       # D for pointer/property iteration
    0x60587F: '488b05e20bd202',     # fresh global S for another API call
    0x60588D: '448b8084000000',     # count passed to 94C9C0
    0x6058ED: '8b9784000000',       # RDI S count to 60C2A0
    0x605906: '8b9784000000',       # RDI S count to player_count notification
}

LITERALS = {
    0x213F4E0: (64, '100fab4b4513b242012b69af448eab3a532fcbb49865c74bdaed4b4ee9b287a8'),
    0x23C6D70: (4, 'e00e5eb9444182f352323374ef4e08ebcb784725fdd4fd612d7730540b3e0c8c'),
    0x23C79AC: (4, '270696d298cc689d8e5bd75897918aa617a25a5030ccae98017053dddd974995'),
    0x22473C8: (13, '2d1f7bb5ed667b71641e114124b84958b97b41db1140c1f721dba595fff5edc4'),
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def detail(ins):
    result = row(ins)
    result['encoding'] = dict(rex=ins.rex, modrm=ins.modrm, sib=ins.sib,
                              displacement_offset=ins.disp_offset,
                              displacement_size=ins.disp_size,
                              immediate_offset=ins.imm_offset,
                              immediate_size=ins.imm_size)
    return result


def pin_fragments(im: Image, entry: int, spec: dict) -> list:
    found = [f for f in im.functions if im.root(f[0])[0] == entry]
    expected = [(a, b, u) for a, b, u, _ in spec['fragments']]
    require(found == expected, 'unwind fragment set changed at ' + hex(entry))
    require(found[0][0] == entry and found[-1][1] == spec['end'] and
            all(x[1] == y[0] for x, y in zip(found, found[1:])),
            'noncontiguous body fragments')
    result = []
    for a, b, u, digest in spec['fragments']:
        raw = im.read(a, b-a)
        require(sha(raw) == digest, 'fragment bytes changed at ' + hex(a))
        result.append(dict(start=hex(a), end_exclusive=hex(b), unwind=hex(u),
                           size_bytes=b-a, sha256=digest))
    return result


def pin_flow(instructions: list, entry: int, spec: dict):
    by_addr = {x.address: x for x in instructions}
    cfg, branches, relocations, indirect = {}, [], [], []
    for ins in instructions:
        next_addr = ins.address + ins.size
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                relocations.append(dict(kind='rip_address' if ins.mnemonic == 'lea' else 'rip_memory',
                                        rva=hex(ins.address), target_rva=hex(next_addr+op.mem.disp),
                                        displacement_offset=ins.disp_offset,
                                        displacement_size=ins.disp_size, instruction=detail(ins)))
        if ins.group(cs.CS_GRP_CALL):
            require(len(ins.operands) == 1, 'unmodeled call operand')
            if ins.operands[0].type == X86_OP_IMM:
                relocations.append(dict(kind='call_rel32', rva=hex(ins.address),
                                        target_rva=hex(ins.operands[0].imm),
                                        displacement_offset=ins.imm_offset,
                                        displacement_size=ins.imm_size, instruction=detail(ins)))
            else:
                indirect.append(dict(kind='call_indirect', rva=hex(ins.address),
                                     instruction=detail(ins)))
        if ins.group(cs.CS_GRP_RET):
            successors = []
        elif ins.group(cs.CS_GRP_JUMP):
            require(len(ins.operands) == 1 and ins.operands[0].type == X86_OP_IMM,
                    'unmodeled indirect branch at ' + hex(ins.address))
            target = ins.operands[0].imm
            successors = [target] if ins.mnemonic == 'jmp' else [target, next_addr]
            branches.append(dict(kind='unconditional' if ins.mnemonic == 'jmp' else 'conditional',
                                 rva=hex(ins.address), target_rva=hex(target),
                                 instruction=detail(ins)))
        else:
            successors = [next_addr]
        require(all(target in by_addr for target in successors),
                'CFG edge leaves body/instruction boundary at ' + hex(ins.address))
        cfg[hex(ins.address)] = [hex(target) for target in successors]
    seen, pending = set(), [entry]
    while pending:
        at = pending.pop()
        if at not in seen:
            seen.add(at)
            pending.extend(int(target, 16) for target in cfg[hex(at)])
    require(seen == set(by_addr), 'unreachable instruction in ' + hex(entry))
    require(len(branches) == spec['branches'], 'branch count changed at ' + hex(entry))
    require([x.address for x in instructions if x.group(cs.CS_GRP_RET)] == spec['returns'],
            'return sites changed at ' + hex(entry))
    require({(int(x['rva'], 16), int(x['target_rva'], 16)) for x in relocations if x['kind'].startswith('rip_')}
            == set(spec['rips']), 'RIP reference set changed at ' + hex(entry))
    require({(int(x['rva'], 16), int(x['target_rva'], 16)) for x in relocations if x['kind'] == 'call_rel32'}
            == set(spec['calls']), 'direct call set changed at ' + hex(entry))
    require({int(x['rva'], 16) for x in indirect} == set(spec['indirect']),
            'indirect call set changed at ' + hex(entry))
    require(all(x['displacement_size'] == 4 for x in relocations),
            'non-rel32 external relocation at ' + hex(entry))
    return cfg, branches, relocations, indirect


def pin_array_sites(instructions: list, entry: int) -> list:
    if entry != ROOT:
        return []
    by_addr = {x.address: x for x in instructions}
    result = []
    for at, (group, op_index, access, expected_hex) in ARRAY_SITES.items():
        ins = by_addr[at]
        require(ins.bytes.hex() == expected_hex, 'array instruction bytes changed at ' + hex(at))
        require(len(ins.operands) > op_index and ins.operands[op_index].type == X86_OP_MEM,
                'array operand changed at ' + hex(at))
        op = ins.operands[op_index]
        result.append(dict(group=group, rva=hex(at), operand_index=op_index,
                           access=access, width_bytes=op.size,
                           base_register=ins.reg_name(op.mem.base),
                           index_register=ins.reg_name(op.mem.index),
                           index_scale=op.mem.scale, displacement=op.mem.disp,
                           displacement_offset=ins.disp_offset,
                           displacement_size=ins.disp_size, instruction=detail(ins)))
    require(len(result) == 19 and set(x['group'] for x in result)
            == {'pointer', 'primary', 'aux', 'property'}, 'four-array site inventory incomplete')
    return result


def pin_body(im: Image, entry: int, spec: dict) -> dict:
    fragments = pin_fragments(im, entry, spec)
    raw = im.read(entry, spec['end'] - entry)
    require(sha(raw) == spec['sha256'], 'complete body bytes changed at ' + hex(entry))
    instructions = list(im.md.disasm(raw, entry))
    require(len(instructions) == spec['instructions'] and
            sum(ins.size for ins in instructions) == len(raw),
            'incomplete body decode at ' + hex(entry))
    cfg, branches, relocations, indirect = pin_flow(instructions, entry, spec)
    arrays = pin_array_sites(instructions, entry)
    critical = {}
    if entry == ROOT:
        by_addr = {x.address: x for x in instructions}
        for at, expected_hex in COUNT_AND_BINDING_SITES.items():
            require(by_addr[at].bytes.hex() == expected_hex,
                    'count/binding site changed at ' + hex(at))
            critical[hex(at)] = detail(by_addr[at])
    return dict(entry=hex(entry), end_exclusive=hex(spec['end']),
                size_bytes=len(raw), sha256=sha(raw), bytes_hex=raw.hex(),
                fragments=fragments, instructions=[detail(x) for x in instructions],
                cfg=cfg, branches=branches, external_relocations=relocations,
                indirect_controls=indirect,
                direct_calls=[x for x in relocations if x['kind'] == 'call_rel32'],
                array_sites=arrays, count_and_binding_sites=critical,
                exit_sites=[detail(x) for x in instructions if x.group(cs.CS_GRP_RET)],
                abi=('Windows x64; RDX=entity, R8=caller state object; RDI is loaded from global 3326468 S. '
                     'Looks up entity ID [RDX+8] in S map; ordinal drives pointer/primary/aux/property writes/read. '
                     'RBP=[entry R8]. One RET; no S count write.' if entry == ROOT else
                     'Windows x64; ECX=entity ID; reverse context map from global 346BF98, '
                     'returns associated ID/default; no roster-array read. Test-only unchanged body.'))


def pin_literals(im: Image) -> dict:
    result = {}
    for at, (size, digest) in LITERALS.items():
        raw = im.read(at, size)
        require(sha(raw) == digest, 'read-only literal bytes changed at ' + hex(at))
        item = dict(rva=hex(at), size_bytes=size, bytes_hex=raw.hex(), sha256=digest)
        if at in (0x23C6D70, 0x23C79AC):
            item['float32'] = struct.unpack('<f', raw)[0]
        elif at == 0x213F4E0:
            item['float32_rows'] = [list(struct.unpack_from('<4f', raw, i*16)) for i in range(4)]
        else:
            require(raw == b'player_count\0', 'notification string changed')
            item['ascii'] = 'player_count\\0'
        result[hex(at)] = item
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'refusing to overwrite output')
    require(sha(INVENTORY.read_bytes()) == INVENTORY_SHA,
            'consumer inventory fingerprint changed')
    im = Image(args.evidence)
    bodies = {hex(entry): pin_body(im, entry, spec) for entry, spec in BODIES.items()}
    literals = pin_literals(im)
    result = dict(source_sha256=EXPECTED,
                  capture_identity_sha256=im.report['capture_sha256'],
                  inventory_sha256=INVENTORY_SHA,
                  replay_sha256=sha(Path(__file__).read_bytes()),
                  bodies=bodies, readonly_literals=literals,
                  identity='605530 loads global3326468 into RDI=S; 60587F separately reloads that global for a later API count. Neither load establishes serialized identity across callbacks.',
                  semantic='Reader-with-effects for an entity ID. It computes map ordinal, mutates primary/aux/property, reads pointer/property network index, optionally calls palette endpoint, and later sends count/player_count notifications. It does not append to roster or update S counts.',
                  finite_scope='Complete 6054F0 body and four directly referenced RO literals. FD9AF0 complete unchanged test-only body; other callees are recorded boundaries, not recursively explored.',
                  limits=[
                      'All 19 original roster-array base/operand sites span pointer, primary, aux and property. The two LEA-derived pointer/property loops must be redirected together with direct operands.',
                      'Original map miss uses zero-extended FFFFFFFF as ordinal and can reach huge unsigned offsets; an eight-slot candidate needs pre-access validation. This static replay does not supply a guard or prove caller reachability.',
                      'For network index >=4, captured code uses float1.0 for all three components and then multiplies by float255.0; the four-row palette is only read below4. This is not an eight-entry palette proof.',
                      'FD9AF0 and original context maps retain capacity/backing/key/lifetime preconditions. 94C9C0 and 60C2A0 have separate saved count evidence; indirect API and security-cookie helper contracts are not established here.',
                      'No writable global contents, dynamic resource state, callback reentrancy, sidecar migration/ownership, native hook, game execution or multiplayer result is established.'])
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(args.output), bodies={k: dict(size_bytes=v['size_bytes'],
          instructions=len(v['instructions']), sha256=v['sha256'], branches=len(v['branches']),
          relocations=len(v['external_relocations']), indirect=len(v['indirect_controls']),
          array_sites=len(v['array_sites'])) for k, v in bodies.items()},
          literals=list(literals))))


if __name__ == '__main__':
    main()
