"""Pin four complete roster insertion bodies and their map helper offline.

This script reads only the existing captured code files. It does not inspect
or modify a game process, install hooks, or execute the saved native code.
"""
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

PRIOR_INVENTORY_SHA256 = '0b664e0f65601221399bfd01ad92f248d373b30376c5e2fdac6b7a702dc93dc2'
ROSTER_GLOBAL_RVA = 0x3326468
MOVER_RVA = 0x60C410
MAP_HELPER_RVA = 0x172F790
ROOTS = {
    0x60CA80: dict(end=0x60CB9F, sha256='974935cec813b3ce3f8d62cff1c7f46b17bb306f5bce020e8dde6fdccfc01e4f',
                   abi='RDX=entity record; R8=creation-flag pointer; roster from global3326468',
                   mode='flag_and_dense', guard_read=0x60CA94, guard_compare=0x60CA9C,
                   null_write=0x60CAA1, first_inline_mutation=0x60CADC,
                   map_edge=0x60CB9A,
                   count_flow=['0x60ca94 tracked+80 read','0x60cab0 dense+84 read',
                               '0x60cab8 prefix+88 read when flag','0x60cadc prefix+88 write when flag',
                               '0x60cb62 dense+84 increment','0x60cb6e tracked+80 increment',
                               '0x60cb74/77/7b high-water+7c update']),
    0x60CBA0: dict(end=0x60CC6B, sha256='57a8d7f5d1dbb83f3a9a80918f740ce2065dfc1ac09b10952189b3693a7132c8',
                   abi='RDX=entity record; roster from global3326468',
                   mode='simple', guard_read=0x60CBB0, guard_compare=0x60CBBB,
                   null_write=0x60CBC0, first_inline_mutation=0x60CBDC,
                   map_edge=0x60CC5A,
                   count_flow=['0x60cbb0 tracked+80 read','0x60cc5a map-helper call',
                               '0x60cc5f tracked+80 increment after helper']),
    0x540850: dict(end=0x54091E, sha256='1264c1c0bf558d390f7dd2bdf075e3f6b3b2465fbfbac5575d6eea8a6ea6d6c0',
                   abi='RCX=entity record (copied to RDX); roster from global3326468',
                   mode='simple', guard_read=0x540863, guard_compare=0x54086E,
                   null_write=0x540873, first_inline_mutation=0x54088F,
                   map_edge=0x54090D,
                   count_flow=['0x540863 tracked+80 read','0x54090d map-helper call',
                               '0x540912 tracked+80 increment after helper']),
    0x540920: dict(end=0x540A3E, sha256='197e6d093ec081d304e0642ffee3e7fc3a71b2eadb36f3a0805d4927af7a5196',
                   abi='RCX=entity record; RDX=creation-flag pointer; roster from global3326468',
                   mode='flag_and_dense', guard_read=0x540934, guard_compare=0x54093C,
                   null_write=0x540941, first_inline_mutation=0x54097B,
                   map_edge=0x540A39,
                   count_flow=['0x540934 tracked+80 read','0x54094f dense+84 read',
                               '0x540957 prefix+88 read when flag','0x54097b prefix+88 write when flag',
                               '0x540a01 dense+84 increment','0x540a0d tracked+80 increment',
                               '0x540a13/16/1a high-water+7c update']),
}
MAP_HELPER_END = 0x172F7FE
MAP_HELPER_SHA256 = '57814b81c7a60e8d4ea989757b9a7d6d3dc3cfd9a81bc315794ca37b8885b375'


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def detailed_row(x):
    result = row(x)
    result['encoding'] = dict(rex=x.rex, modrm=x.modrm, sib=x.sib,
                              displacement_offset=x.disp_offset,
                              displacement_size=x.disp_size,
                              immediate_offset=x.imm_offset,
                              immediate_size=x.imm_size)
    return result


def complete_body(im, start, end, expected_sha, allowed_external):
    fs = [f for f in im.functions if im.root(f[0])[0] == start]
    require(len(fs) == 1 and fs[0][:2] == (start, end),
            'unexpected insertion/helper unwind extent at ' + hex(start))
    raw = im.read(start, end - start)
    require(sha(raw) == expected_sha, 'body fingerprint changed at ' + hex(start))
    ins = list(im.md.disasm(raw, start))
    require(sum(x.size for x in ins) == len(raw), 'incomplete body decode')
    by_addr = {x.address: x for x in ins}
    require(len(ins) == len(by_addr), 'duplicate instruction boundary')
    edges, branches, externals = {}, [], []
    for x in ins:
        for op in x.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                externals.append(dict(kind='rip_memory', rva=hex(x.address),
                                      target_rva=hex(x.address+x.size+op.mem.disp),
                                      displacement_offset=x.disp_offset,
                                      displacement_size=x.disp_size,
                                      instruction=detailed_row(x)))
        if x.group(cs.CS_GRP_CALL):
            require(len(x.operands) == 1 and x.operands[0].type == X86_OP_IMM,
                    'unmodeled indirect call')
            externals.append(dict(kind='call_rel32', rva=hex(x.address),
                                  target_rva=hex(x.operands[0].imm),
                                  displacement_offset=x.imm_offset,
                                  displacement_size=x.imm_size,
                                  instruction=detailed_row(x)))
        if x.group(cs.CS_GRP_RET):
            successors = []
        elif x.group(cs.CS_GRP_JUMP):
            require(len(x.operands) == 1 and x.operands[0].type == X86_OP_IMM,
                    'unmodeled indirect jump')
            target = x.operands[0].imm
            if target in by_addr:
                successors = [target]
            else:
                require(x.mnemonic == 'jmp', 'conditional branch escapes body')
                successors = []
                externals.append(dict(kind='tail_jump_rel32', rva=hex(x.address),
                                      target_rva=hex(target),
                                      displacement_offset=x.imm_offset,
                                      displacement_size=x.imm_size,
                                      instruction=detailed_row(x)))
            if x.mnemonic != 'jmp':
                successors.append(x.address + x.size)
            branches.append(detailed_row(x))
        else:
            successors = [x.address + x.size]
        require(all(target in by_addr for target in successors),
                'body edge outside captured instruction boundary')
        edges[x.address] = successors
    actual_external = {(x['kind'], int(x['rva'],16), int(x['target_rva'],16))
                       for x in externals}
    require(actual_external == set(allowed_external),
            'external relocation set changed at ' + hex(start))
    require(all(x['displacement_size'] == 4 for x in externals),
            'external relocation is not disp32')
    seen, pending = set(), [start]
    while pending:
        at = pending.pop()
        if at in seen:
            continue
        seen.add(at)
        pending.extend(edges[at])
    require(seen == set(by_addr), 'unreachable instruction in body')
    return dict(entry=hex(start), end_exclusive=hex(end), size_bytes=len(raw),
                bytes_hex=raw.hex(),
                sha256=sha(raw), fragment=dict(start=hex(start),end_exclusive=hex(end),
                                              unwind=hex(fs[0][2]),sha256=sha(raw)),
                instructions=[detailed_row(x) for x in ins],
                cfg={hex(k):list(map(hex,v)) for k,v in edges.items()},
                branches=branches, external_relocations=externals), by_addr


def array_sites(by_addr):
    groups = dict(pointer=[], primary=[], aux=[], property=[])
    for x in by_addr.values():
        for op in x.operands:
            if op.type != X86_OP_MEM:
                continue
            disp = op.mem.disp
            if disp == 0xE8:
                group = 'pointer'
            elif 0x108 <= disp < 0x178:
                group = 'primary'
            elif 0x2C8 <= disp < 0x300:
                group = 'aux'
            elif 0x3A8 <= disp < 0x3C8:
                group = 'property'
            else:
                continue
            require(x.operands[0].type == X86_OP_MEM and
                    x.disp_size == 4 and x.disp_offset + 4 <= x.size,
                    'array site is not a disp32 store')
            groups[group].append(dict(rva=hex(x.address), group=group,
                                      instruction=detailed_row(x),
                                      width_bytes=op.size,
                                      base_register=x.reg_name(op.mem.base),
                                      index_register=x.reg_name(op.mem.index),
                                      index_scale=op.mem.scale,
                                      original_displacement=disp,
                                      displacement_offset=x.disp_offset,
                                      displacement_size=x.disp_size))
    require(tuple(len(groups[k]) for k in ('pointer','primary','aux','property')) ==
            (1,7,6,0), 'inline array site counts changed')
    return groups


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    require(not args.output.exists(), 'refusing to overwrite output')
    prior = (HERE/'roster_property_consumers_native_inventory.json').read_bytes()
    require(sha(prior) == PRIOR_INVENTORY_SHA256, 'prior finite inventory changed')
    im = Image(args.evidence)
    inserts = {}
    expected_edges = {
        0x60CA80: [('rip_memory',0x60CA8A,ROSTER_GLOBAL_RVA),
                   ('call_rel32',0x60CAC9,MOVER_RVA),
                   ('tail_jump_rel32',0x60CB9A,MAP_HELPER_RVA)],
        0x60CBA0: [('rip_memory',0x60CBA6,ROSTER_GLOBAL_RVA),
                   ('call_rel32',0x60CC5A,MAP_HELPER_RVA)],
        0x540850: [('rip_memory',0x540856,ROSTER_GLOBAL_RVA),
                   ('call_rel32',0x54090D,MAP_HELPER_RVA)],
        0x540920: [('rip_memory',0x54092A,ROSTER_GLOBAL_RVA),
                   ('call_rel32',0x540968,MOVER_RVA),
                   ('tail_jump_rel32',0x540A39,MAP_HELPER_RVA)],
    }
    for start, info in ROOTS.items():
        body, by_addr = complete_body(im,start,info['end'],info['sha256'],
                                      expected_edges[start])
        sites = array_sites(by_addr)
        guard = by_addr[info['guard_compare']]
        require(guard.mnemonic == 'cmp' and guard.operands[1].imm == 4,
                'four-slot guard changed')
        null = by_addr[info['null_write']]
        require(null.operands[0].type == X86_OP_MEM and
                null.operands[0].mem.base == 0 and
                null.operands[0].mem.disp == 0,
                'over-capacity null write changed')
        first = by_addr[info['first_inline_mutation']]
        require(first.operands[0].type == X86_OP_MEM,
                'first inline mutation changed')
        body.update(dict(abi=info['abi'], mode=info['mode'],
                         guard=dict(tracked_read=detailed_row(by_addr[info['guard_read']]),
                                    compare_four=detailed_row(guard),
                                    over_capacity_null_write=detailed_row(null)),
                         first_inline_mutation=detailed_row(first),
                         array_sites=sites,
                         count_and_init_order=info['count_flow'],
                         map_helper_edge=detailed_row(by_addr[info['map_edge']])))
        inserts[hex(start)] = body
    helper, helper_ins = complete_body(im,MAP_HELPER_RVA,MAP_HELPER_END,
                                       MAP_HELPER_SHA256,[])
    require(helper_ins[0x172F7F2].bytes == bytes.fromhex('897104') and
            helper_ins[0x172F7FA].bytes == bytes.fromhex('448909') and
            helper_ins[0x172F7E3].bytes == bytes.fromhex('33c9'),
            'map helper insertion/null path changed')
    helper['abi'] = 'RCX=&S+D0 map header; EDX=entity ID; R8D=ordinal'
    helper['behavior'] = ('Writes ordinal at selected bucket+4, then entity ID at bucket; '
                          'empty-key or same-key selects bucket; count zero or exhausted '
                          'probe sets bucket pointer zero and then writes [4].')
    result = dict(source_sha256=EXPECTED,
                  capture_identity_sha256=im.report['capture_sha256'],
                  prior_inventory_sha256=PRIOR_INVENTORY_SHA256,
                  inserts=inserts,map_helper=helper,
                  finite_scope=dict(insert_roots=list(map(hex,ROOTS)),
                                    full_instruction_count=sum(len(x['instructions']) for x in inserts.values()),
                                    all_array_site_counts={k:sum(len(x['array_sites'][k]) for x in inserts.values())
                                                           for k in ('pointer','primary','aux','property')}),
                  limits=[
                      'Four complete functions and one direct map helper only; no global alias or caller inventory expansion.',
                      'Every function still contains the original four-slot guard and over-capacity null write; source evidence is not a safe eight-slot patch.',
                      'The original count+1 guard wraps at uint32 FFFFFFFF; a candidate must not treat that state as valid.',
                      'The map helper neither allocates nor grows and can write address 4 on zero-capacity/full miss; valid map state is a precondition.',
                      'No direct property write in these insert bodies; producer and shared mover are separate required code paths.',
                      'No sidecar allocation, live game execution, hook, unwind, or multiplayer verification.'])
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),insert_bodies=len(inserts),
                          insert_instructions=result['finite_scope']['full_instruction_count'],
                          array_sites=result['finite_scope']['all_array_site_counts'],
                          map_helper_bytes=helper['size_bytes'])))


if __name__ == '__main__':
    main()
