"""Pin both full roster classification bodies from one saved code capture.

This is bounded, offline static evidence. It neither opens a game process nor
emits/installs native code. Direct temporary arena helpers are inspected only
to the depth required to state their calling boundary; their indirect global
callbacks are deliberately not expanded.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import capstone as cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RBP, X86_REG_RIP

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row

ROSTER_GLOBAL_RVA = 0x3326468
SENTINEL_GLOBAL_RVA = 0x3483C20
TEMP_INIT_RVA = 0x173B6F0
TEMP_ALLOC_RVA = 0x173B8D0
TEMP_RELEASE_RVA = 0x173BC20

ROOTS = {
    0x60CF50: dict(end=0x60D2F6, sha256='09e5e20c35955b4f563f1e971646a8c32c67ff6afdc76e4c1aa796270a6ff33c',
                   instructions=197, kind='promote',
                   fragments=[(0x60CF50, 0x60D044, 0x24257CC, '94ab331c1d9b101362471cf0eff1bbb7e2257fafb189cad977b56d5044b62781'),
                              (0x60D044, 0x60D296, 0x24257E4, 'b4115b099060fd6471e0bc94a53b31929af01da6b7f4433351cdcd056d2062d9'),
                              (0x60D296, 0x60D2F6, 0x24257F8, '7c6a580aa0dc2593613a29487c1c85f3ed22811432cb40dc92d5c2ec1a20001b')],
                   external=[('rip_memory', 0x60CF6B, SENTINEL_GLOBAL_RVA),
                             ('rip_memory', 0x60CF71, ROSTER_GLOBAL_RVA),
                             ('call_rel32', 0x60D0B5, TEMP_INIT_RVA),
                             ('call_rel32', 0x60D0C8, TEMP_ALLOC_RVA),
                             ('call_rel32', 0x60D166, TEMP_RELEASE_RVA),
                             ('call_rel32', 0x60D170, TEMP_RELEASE_RVA),
                             ('call_rel32', 0x60D17A, TEMP_INIT_RVA),
                             ('call_rel32', 0x60D18D, TEMP_ALLOC_RVA),
                             ('call_rel32', 0x60D1F1, TEMP_RELEASE_RVA),
                             ('call_rel32', 0x60D1FB, TEMP_RELEASE_RVA)],
                   array_counts=dict(pointer=6, primary=14, aux=9, property=8),
                   key_sites=dict(initial_lookup=0x60CFB0, miss_ordinal=0x60CFD0,
                                  boundary_compare=0x60CFE2, equal_count_write=0x60CFEB,
                                  pointer_swap=(0x60D049, 0x60D06C), primary_zero=(0x60D07D, 0x60D0AD),
                                  aux_base_alias=0x60D0D1, property_swap=(0x60D19F, 0x60D1E8),
                                  map_first_store=0x60D264, map_second_store=0x60D2D3,
                                  moved_count_write=0x60D2D7, return_site=0x60D2F5)),
    0x60D300: dict(end=0x60D760, sha256='973e04a016a90f53ba131da1590d9e647b7c9ad8ebec35018ae173d72a22cf6a',
                   instructions=232, kind='demote',
                   fragments=[(0x60D300, 0x60D39A, 0x2425808, '18f0da1cf885b083b8547d8d3c7de419016d71e2a2fad5697868609bdd1eb0c0'),
                              (0x60D39A, 0x60D70B, 0x242581C, '89012add7bde527111adc6489fe2496a3e77024e76ff2f71a1d0eaecea6731fd'),
                              (0x60D70B, 0x60D760, 0x2425834, '5ac0091797b889b3cf9f76712ba3d104e37b513ab05395af2d3dcfc923781c76')],
                   external=[('rip_memory', 0x60D315, SENTINEL_GLOBAL_RVA),
                             ('rip_memory', 0x60D31B, ROSTER_GLOBAL_RVA),
                             ('call_rel32', 0x60D3DE, TEMP_INIT_RVA),
                             ('call_rel32', 0x60D3F1, TEMP_ALLOC_RVA),
                             ('call_rel32', 0x60D51C, TEMP_RELEASE_RVA),
                             ('call_rel32', 0x60D526, TEMP_RELEASE_RVA),
                             ('call_rel32', 0x60D530, TEMP_INIT_RVA),
                             ('call_rel32', 0x60D543, TEMP_ALLOC_RVA),
                             ('call_rel32', 0x60D5E1, TEMP_RELEASE_RVA),
                             ('call_rel32', 0x60D5EB, TEMP_RELEASE_RVA),
                             ('call_rel32', 0x60D5F5, TEMP_INIT_RVA),
                             ('call_rel32', 0x60D608, TEMP_ALLOC_RVA),
                             ('call_rel32', 0x60D668, TEMP_RELEASE_RVA),
                             ('call_rel32', 0x60D672, TEMP_RELEASE_RVA)],
                   array_counts=dict(pointer=6, primary=28, aux=9, property=8),
                   key_sites=dict(initial_lookup=0x60D350, miss_ordinal=0x60D370,
                                  boundary_compare=0x60D37F, equal_count_write=0x60D384,
                                  pointer_swap=(0x60D3A7, 0x60D3D1),
                                  primary_swap=(0x60D3FD, 0x60D514),
                                  aux_base_alias=0x60D54C, property_swap=(0x60D61A, 0x60D660),
                                  map_first_store=0x60D6DB, map_second_store=0x60D743,
                                  moved_count_write=0x60D747, return_site=0x60D75F)),
}

HELPERS = {
    TEMP_INIT_RVA: dict(end=0x173B7F4, sha256='16fa4b7d418012fa547368f3d69d580037d162bdebf2a09c3d0550fca0e8440c',
                        abi='RCX=&24-byte temporary context C (at caller [RSP+20h]); C[0]=arena entry A, C[8]=current block, C[10h]=block used offset; RAX returns RCX.',
                        critical=[0x173B712, 0x173B715, 0x173B719, 0x173B7CF, 0x173B7D5, 0x173B7DA, 0x173B7E5]),
    TEMP_ALLOC_RVA: dict(end=0x173BA52, sha256='18eaaac8e2b019af7f29146be600edb4976a1ad1662546632cc319cbcd7943d9',
                         abi='RCX=A=C[0], not &C; RDX=byte count (70h/38h/20h here); R8=alignment 4; RAX=allocated pointer on ordinary path, zero for size zero.',
                         critical=[0x173B8D8, 0x173B8DB, 0x173B8DE, 0x173B907, 0x173BA3D, 0x173BA48]),
    TEMP_RELEASE_RVA: dict(end=0x173BC97, sha256='9d66bb642a3255538db168c4cef89b8c3138e4b5036c264be0caee571a3e3150',
                           abi='RCX=&C; rolls back arena A to saved C[8]/C[10h], releasing intervening growth blocks via indirect callbacks; return value unused by callers.',
                           critical=[0x173BC26, 0x173BC30, 0x173BC40, 0x173BC5F, 0x173BC73, 0x173BC87, 0x173BC8E]),
}

GROUPS = {
    'pointer': dict(displacements={0xE8}, old_base=0xE8, sidecar_base=0),
    'primary': dict(displacements=set(range(0x108, 0x169, 0x10)), old_base=0x108, sidecar_base=0x40),
    'aux': dict(displacements=set(range(0x2C8, 0x2F9, 0x10)), old_base=0x2C8, sidecar_base=0x3C0),
    'property': dict(displacements={0x3A8, 0x3B8}, old_base=0x3A8, sidecar_base=0x580),
}


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def detail(ins):
    out = row(ins)
    out['encoding'] = dict(rex=ins.rex, modrm=ins.modrm, sib=ins.sib,
                           displacement_offset=ins.disp_offset,
                           displacement_size=ins.disp_size,
                           immediate_offset=ins.imm_offset,
                           immediate_size=ins.imm_size)
    return out


def fragments(im, start, end, expected=None):
    found = [f for f in im.functions if im.root(f[0])[0] == start]
    require(found and found[0][0] == start and found[-1][1] == end,
            'root/extent changed at ' + hex(start))
    require(all(left[1] == right[0] for left, right in zip(found, found[1:])),
            'noncontiguous fragments at ' + hex(start))
    if expected is not None:
        require([(a, b, u) for a, b, u in found] == [(a, b, u) for a, b, u, _ in expected],
                'fragment/unwind boundary changed at ' + hex(start))
    out = []
    for i, (a, b, unwind) in enumerate(found):
        digest = sha(im.read(a, b-a))
        if expected is not None:
            require(digest == expected[i][3], 'fragment bytes changed at ' + hex(a))
        out.append(dict(start=hex(a), end_exclusive=hex(b), unwind=hex(unwind),
                        size_bytes=b-a, sha256=digest))
    return out


def decode(im, start, end, expected_sha=None, expected_count=None):
    raw = im.read(start, end-start)
    if expected_sha is not None:
        require(sha(raw) == expected_sha, 'full body changed at ' + hex(start))
    ins = list(im.md.disasm(raw, start))
    require(sum(x.size for x in ins) == len(raw), 'incomplete body decode at ' + hex(start))
    if expected_count is not None:
        require(len(ins) == expected_count, 'instruction count changed at ' + hex(start))
    require(len({x.address for x in ins}) == len(ins), 'duplicate boundary at ' + hex(start))
    return raw, ins


def control_flow(ins, *, allow_indirect_calls=False, require_reachable=True):
    by_addr = {x.address: x for x in ins}
    cfg, branches, relocations, indirect_calls = {}, [], [], []
    for x in ins:
        for op in x.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                relocations.append(dict(kind='rip_memory', rva=hex(x.address),
                                        target_rva=hex(x.address+x.size+op.mem.disp),
                                        displacement_offset=x.disp_offset,
                                        displacement_size=x.disp_size, instruction=detail(x)))
        if x.group(cs.CS_GRP_CALL):
            require(len(x.operands) == 1, 'unmodeled call operands')
            if x.operands[0].type == X86_OP_IMM:
                relocations.append(dict(kind='call_rel32', rva=hex(x.address),
                                        target_rva=hex(x.operands[0].imm),
                                        displacement_offset=x.imm_offset,
                                        displacement_size=x.imm_size, instruction=detail(x)))
            else:
                require(allow_indirect_calls, 'unexpected indirect call in classify body')
                indirect_calls.append(detail(x))
        if x.group(cs.CS_GRP_RET):
            successors = []
        elif x.group(cs.CS_GRP_JUMP):
            require(len(x.operands) == 1 and x.operands[0].type == X86_OP_IMM,
                    'unmodeled indirect jump')
            target = x.operands[0].imm
            require(target in by_addr, 'branch escapes body at ' + hex(x.address))
            successors = [target]
            if x.mnemonic != 'jmp':
                successors.append(x.address+x.size)
            branches.append(detail(x))
        else:
            successors = [x.address+x.size]
        require(all(t in by_addr for t in successors), 'edge outside body at ' + hex(x.address))
        cfg[hex(x.address)] = [hex(t) for t in successors]
    seen, pending = set(), [ins[0].address]
    while pending:
        at = pending.pop()
        if at in seen:
            continue
        seen.add(at)
        pending.extend(int(x, 16) for x in cfg[hex(at)])
    if require_reachable:
        require(seen == set(by_addr), 'unreachable instruction in body')
    return cfg, branches, relocations, indirect_calls, sorted(set(by_addr) - seen)


def array_sites(ins):
    found = []
    for x in ins:
        for index, op in enumerate(x.operands):
            if op.type != X86_OP_MEM or X86_REG_RBP not in (op.mem.base, op.mem.index):
                continue
            group = next((name for name, spec in GROUPS.items()
                          if op.mem.disp in spec['displacements']), None)
            if group is None:
                continue
            found.append(dict(rva=hex(x.address), group=group, operand_index=index,
                              access='address_only' if x.mnemonic == 'lea' else
                                     'write' if index == 0 else 'read',
                              operand_width_bytes=op.size,
                              base_register=x.reg_name(op.mem.base),
                              index_register=x.reg_name(op.mem.index),
                              index_scale=op.mem.scale, original_displacement=op.mem.disp,
                              displacement_offset=x.disp_offset,
                              displacement_size=x.disp_size,
                              instruction=detail(x)))
    return found


def classify_body(im, start, spec):
    fs = fragments(im, start, spec['end'], spec['fragments'])
    raw, ins = decode(im, start, spec['end'], spec['sha256'], spec['instructions'])
    cfg, branches, relocations, indirect, unreachable = control_flow(ins)
    require(not unreachable, 'unreachable classify instruction')
    require(not indirect, 'classify body unexpectedly acquired an indirect call')
    actual = {(r['kind'], int(r['rva'], 16), int(r['target_rva'], 16)) for r in relocations}
    require(actual == set(spec['external']), 'external relocation set changed at ' + hex(start))
    require(all(r['displacement_size'] == 4 for r in relocations), 'non-disp32 relocation')
    sites = array_sites(ins)
    counts = {group: sum(s['group'] == group for s in sites) for group in GROUPS}
    require(counts == spec['array_counts'], 'four-array operand count changed')
    by_addr = {x.address: x for x in ins}
    require(all(at in by_addr for value in spec['key_sites'].values()
                for at in (value if isinstance(value, tuple) else (value,))),
            'critical site no longer instruction boundary')
    require(all(by_addr[spec['key_sites'][name]].operands[0].type == X86_OP_MEM
                for name in ('map_first_store', 'map_second_store', 'equal_count_write', 'moved_count_write')),
            'critical mutation site changed')
    return dict(kind=spec['kind'], entry=hex(start), end_exclusive=hex(spec['end']),
                size_bytes=len(raw), sha256=sha(raw), bytes_hex=raw.hex(), fragments=fs,
                abi='Windows x64; RDX=entity record (ID at +8); RCX entry is not used as roster base; RBP=[global 3326468]; result RAX not asserted by this static replay.',
                instructions=[detail(x) for x in ins], cfg=cfg, branches=branches,
                external_relocations=relocations, array_sites=sites,
                array_site_counts=counts,
                critical_sites={name: [detail(by_addr[a]) for a in value] if isinstance(value, tuple)
                                else detail(by_addr[value]) for name, value in spec['key_sites'].items()})


def helper_body(im, start, spec):
    fs = fragments(im, start, spec['end'])
    raw, ins = decode(im, start, spec['end'], spec['sha256'])
    cfg, branches, relocations, indirect, unreachable = control_flow(
        ins, allow_indirect_calls=True, require_reachable=False)
    by_addr = {x.address: x for x in ins}
    require(all(a in by_addr for a in spec['critical']), 'temporary helper contract site changed')
    return dict(entry=hex(start), end_exclusive=hex(spec['end']),
                size_bytes=len(raw), sha256=sha(raw), bytes_hex=raw.hex(), fragments=fs,
                abi=spec['abi'], instructions=[detail(x) for x in ins], cfg=cfg,
                branches=branches, external_relocations=relocations,
                statically_unreachable_instruction_rvas=[hex(a) for a in unreachable],
                indirect_calls=indirect,
                critical_sites={hex(a): detail(by_addr[a]) for a in spec['critical']})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    require(not args.output.exists(), 'refusing to overwrite output')
    im = Image(args.evidence)
    out = {hex(start): classify_body(im, start, spec) for start, spec in ROOTS.items()}
    helpers = {hex(start): helper_body(im, start, spec) for start, spec in HELPERS.items()}
    result = dict(source_sha256=EXPECTED, capture_identity_sha256=im.report['capture_sha256'],
                  replay_sha256=sha(Path(__file__).read_bytes()),
                  bodies=out, temporary_helpers=helpers,
                  storage_geometry={name: dict(old_base=hex(spec['old_base']),
                                              sidecar_base=hex(spec['sidecar_base']))
                                    for name, spec in GROUPS.items()},
                  direct_map_helper_calls=0,
                  map_contract='Both roots inline-probe S+D0 with capacity S+D8, empty sentinel S+DC and multiplier S+E0. On a moved path each probes both swapped entity IDs and writes their new ordinal at bucket+4. A failed post-swap probe can write through a zero bucket pointer; this replay does not prove preconditions or runtime reachability.',
                  temporary_contract='Only direct callees 173B6F0, 173B8D0, 173BC20 are expanded. Init and release receive &24-byte C at caller [RSP+20h]; alloc receives A=C[0], sizes 70h/38h/20h and alignment 4. Every allocation sequence has two release calls. Indirect allocator callbacks, concurrency and lifetime are not expanded.',
                  finite_scope='Two complete chained classification roots and their three direct temporary arena helpers from fixed saved capture; no global xref or callee closure.',
                  limits=['Original map miss or zero capacity yields ordinal FFFFFFFF, not a safe return.',
                          'Array operands and aliases are pinned statically; no emitter or sidecar binding is asserted.',
                          'No game process, hook installation, caller reachability or multiplayer verification.'])
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),
                          body_instruction_counts={k: len(v['instructions']) for k, v in out.items()},
                          array_site_counts={k: v['array_site_counts'] for k, v in out.items()},
                          direct_helpers=list(helpers))))


if __name__ == '__main__':
    main()
