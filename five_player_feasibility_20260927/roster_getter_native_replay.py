"""Pin the complete 606AD0 roster ID-to-network-index getter offline.

Reads one fixed saved capture. No process attach, native emitter, hook install,
global code scan, or inference about runtime caller reachability.
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

ENTRY = 0x606AD0
END = 0x606B75
UNWIND = 0x2424C2C
BODY_SHA = '96ce6884140adb9ae93688e042a2b5db7ffc1e59ffb45eb03188e6bab79abcfb'
INSTRUCTIONS = 43
ROSTER_GLOBAL_RVA = 0x3326468
INVALID_ID_GLOBAL_RVA = 0x3483C20
EXTERNAL = {('rip_memory', 0x606AE4, INVALID_ID_GLOBAL_RVA),
            ('rip_memory', 0x606AEA, ROSTER_GLOBAL_RVA)}
CRITICAL = {
    'input_invalid_compare': (0x606AE4, '3b1536d1e702'),
    'roster_global_load': (0x606AEA, '4c8b1577f9d102'),
    'invalid_branch': (0x606AF1, '744d'),
    'capacity_zero_branch': (0x606B0D, '7431'),
    'bucket_key_read': (0x606B29, '428b0cc7'),
    'bucket_address': (0x606B2D, '4e8d1cc7'),
    'empty_key_branch': (0x606B33, '7425'),
    'key_found_branch': (0x606B37, '7425'),
    'full_probe_branch': (0x606B3E, '72e0'),
    'miss_return_value': (0x606B40, 'b8ffffffff'),
    'shared_return': (0x606B59, 'c3'),
    'empty_key_confirm': (0x606B5A, '3bca'),
    'ordinal_load': (0x606B5E, '418b4304'),
    'invalid_ordinal_branch': (0x606B65, '74d9'),
    'ordinal_scale': (0x606B67, '48c1e005'),
    'network_index_read': (0x606B6B, '428b8410b4030000'),
    'success_join': (0x606B73, 'ebd0'),
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


def pin(im):
    fragments = [f for f in im.functions if im.root(f[0])[0] == ENTRY]
    require(fragments == [(ENTRY, END, UNWIND)], 'getter unwind root/extent changed')
    raw = im.read(ENTRY, END-ENTRY)
    require(sha(raw) == BODY_SHA, 'getter body bytes changed')
    instructions = list(im.md.disasm(raw, ENTRY))
    require(len(instructions) == INSTRUCTIONS and sum(x.size for x in instructions) == len(raw),
            'getter decode incomplete')
    by_addr = {x.address: x for x in instructions}
    require(len(by_addr) == len(instructions), 'duplicate getter instruction boundary')
    cfg, branches, relocations, calls = {}, [], [], []
    for x in instructions:
        for op in x.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                relocations.append(dict(kind='rip_memory', rva=hex(x.address),
                                        target_rva=hex(x.address+x.size+op.mem.disp),
                                        displacement_offset=x.disp_offset,
                                        displacement_size=x.disp_size,
                                        instruction=detail(x)))
        if x.group(cs.CS_GRP_CALL):
            calls.append(detail(x))
        if x.group(cs.CS_GRP_RET):
            successors = []
        elif x.group(cs.CS_GRP_JUMP):
            require(len(x.operands) == 1 and x.operands[0].type == X86_OP_IMM,
                    'unmodeled getter indirect branch')
            target = x.operands[0].imm
            require(target in by_addr, 'getter branch escapes body')
            successors = [target]
            if x.mnemonic != 'jmp':
                successors.append(x.address+x.size)
            branches.append(detail(x))
        else:
            successors = [x.address+x.size]
        require(all(t in by_addr for t in successors),
                'getter CFG successor outside body at ' + hex(x.address))
        cfg[hex(x.address)] = [hex(t) for t in successors]
    require(not calls, 'getter unexpectedly calls another function')
    require({(r['kind'], int(r['rva'], 16), int(r['target_rva'], 16))
             for r in relocations} == EXTERNAL, 'getter RIP relocation set changed')
    require(all(r['displacement_size'] == 4 for r in relocations),
            'getter RIP relocation width changed')
    seen, todo = set(), [ENTRY]
    while todo:
        at = todo.pop()
        if at in seen:
            continue
        seen.add(at)
        todo.extend(int(x, 16) for x in cfg[hex(at)])
    require(seen == set(by_addr), 'unreachable getter instruction')
    require(all(by_addr[at].bytes.hex() == blob for at, blob in CRITICAL.values()),
            'getter critical instruction changed')
    returns = [x.address for x in instructions if x.group(cs.CS_GRP_RET)]
    require(returns == [0x606B59], 'getter return sites changed')
    prop = by_addr[0x606B6B]
    require(prop.operands[1].type == X86_OP_MEM and prop.operands[1].mem.disp == 0x3B4
            and prop.operands[1].size == 4 and prop.disp_size == 4,
            'property network-index operand changed')
    require(by_addr[0x606B67].mnemonic == 'shl' and
            by_addr[0x606B67].operands[1].imm == 5,
            'property ordinal stride changed')
    require(by_addr[0x606B5E].operands[1].type == X86_OP_MEM and
            by_addr[0x606B5E].operands[1].mem.disp == 4,
            'map ordinal source changed')
    return dict(entry=hex(ENTRY), end_exclusive=hex(END), size_bytes=len(raw),
                sha256=sha(raw), bytes_hex=raw.hex(),
                fragments=[dict(start=hex(ENTRY), end_exclusive=hex(END),
                                unwind=hex(UNWIND), size_bytes=len(raw), sha256=sha(raw))],
                abi='Windows x64; EDX=entity ID; RCX entry unused by this body; EAX=-1 for invalid/missing ID, zero capacity, exhausted probe or map ordinal -1, otherwise EAX=property[ordinal].network_index DWORD. RBX/RBP/RSI/RDI preserved; one shared RET.',
                instructions=[detail(x) for x in instructions], cfg=cfg,
                branches=branches, external_relocations=relocations,
                direct_calls=calls,
                critical_sites={name: detail(by_addr[at]) for name, (at, _) in CRITICAL.items()},
                property_site=dict(rva=hex(prop.address), operand_index=1,
                                   width_bytes=prop.operands[1].size,
                                   base_register=prop.reg_name(prop.operands[1].mem.base),
                                   index_register=prop.reg_name(prop.operands[1].mem.index),
                                   index_scale=prop.operands[1].mem.scale,
                                   original_displacement=prop.operands[1].mem.disp,
                                   displacement_offset=prop.disp_offset,
                                   displacement_size=prop.disp_size,
                                   ordinal_scale_instruction=detail(by_addr[0x606B67]),
                                   meaning='S+3A8h+ordinal*20h+0Ch; network index, not map ordinal'),
                map_contract=dict(header='S+D0h pointer, +D8h capacity, +DCh empty-key sentinel, +E0h multiplier',
                                  bucket_key_read=detail(by_addr[0x606B29]),
                                  bucket_value_read=detail(by_addr[0x606B5E]),
                                  no_map_mutations=True),
                return_routes=dict(invalid_id=hex(0x606AF1), capacity_zero=hex(0x606B0D),
                                   empty_nonmatching_key=hex(0x606B5C),
                                   full_probe_exhausted=hex(0x606B3E),
                                   invalid_map_ordinal=hex(0x606B65),
                                   miss_value_site=hex(0x606B40),
                                   success_network_read=hex(0x606B6B),
                                   shared_return=hex(0x606B59)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    require(not args.output.exists(), 'refusing to overwrite output')
    im = Image(args.evidence)
    body = pin(im)
    result = dict(source_sha256=EXPECTED,
                  capture_identity_sha256=im.report['capture_sha256'],
                  replay_sha256=sha(Path(__file__).read_bytes()),
                  bodies={hex(ENTRY): body},
                  finite_scope='One complete unwind getter root only, with exact direct RIP reads and no callee/global xref expansion.',
                  limits=['Static byte/CFG evidence does not prove any caller or eight-player runtime reachability.',
                          'Original getter rejects map ordinal FFFFFFFFh but does not bound a different ordinal before the property read.',
                          'Map memory validity, unique keys and stable roster lifetime are external preconditions.',
                          'No native emitter, hook, process access, or multiplayer execution in this replay.'])
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(args.output), entry=body['entry'],
                          size_bytes=body['size_bytes'], instructions=len(body['instructions']),
                          body_sha256=body['sha256'], relocations=len(body['external_relocations']))))


if __name__ == '__main__':
    main()
