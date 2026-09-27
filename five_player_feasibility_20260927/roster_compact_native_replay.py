"""Pin 60CC70 compaction and its direct owner call from the saved capture.

This reads saved bytes only. It neither attaches to the game nor emits a patch.
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

ENTRY, END = 0x60CC70, 0x60CE76
BODY_SHA256 = '37b79524a6ed1b43d8ce3244c66288a0b921e1ea5766ba64fd7e0b186c41e452'
FRAGMENTS = [
    (0x60CC70, 0x60CC97, 0x2425788,
     '89c51f53a1a693eaf3048842da571fcfa57aac1d8e4f7724e0e5b21aad42fd6e'),
    (0x60CC97, 0x60CE65, 0x2425794,
     '777d66667eb4e467d075f468781c021d636db7a7dd9a3f766a3d9d9634b68779'),
    (0x60CE65, 0x60CE76, 0x24257B0,
     '08273783d17791c318b35b10a17fddaeb90ecbca1f49ac1aa538d033ce980143'),
]
CALLER_START, CALLER_END = 0x57E00F, 0x57E024
CALLER_SHA256 = '303568302bce36265a4fc66df105def1da1ed2b73b764c6ed1c7826801491057'
CALLER_OWNER_ROOT = (0x576CF0, 0x58131E, 0x24139C0)
PRIOR_INVENTORY_SHA256 = '0b664e0f65601221399bfd01ad92f248d373b30376c5e2fdac6b7a702dc93dc2'
MOVER_EVIDENCE_SHA256 = '115802c09eb15f840932667717731150aa347e7ae8a72245dd92e05a5e86a242'
MOVER_BODY_SHA256 = 'b977816b8863034f0c247d0ee58779ab0f7d87cdb54eaa49ebfcdd5cab95434b'


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def detail(x):
    r = row(x)
    r['encoding'] = dict(rex=x.rex, modrm=x.modrm, sib=x.sib,
                         displacement_offset=x.disp_offset,
                         displacement_size=x.disp_size,
                         immediate_offset=x.imm_offset,
                         immediate_size=x.imm_size)
    return r


def pin_body(im):
    actual = [f for f in im.functions if im.root(f[0])[0] == ENTRY]
    require([tuple(f) for f in actual] == [f[:3] for f in FRAGMENTS],
            'compactor unwind fragments changed')
    raw = im.read(ENTRY, END - ENTRY)
    require(sha(raw) == BODY_SHA256, 'compactor body SHA changed')
    ins, fragment_rows = [], []
    for start, end, unwind, expected_sha in FRAGMENTS:
        piece = im.read(start, end - start)
        require(sha(piece) == expected_sha, 'fragment SHA changed at ' + hex(start))
        part = list(im.md.disasm(piece, start))
        require(sum(x.size for x in part) == len(piece),
                'incomplete fragment decode at ' + hex(start))
        ins.extend(part)
        fragment_rows.append(dict(start=hex(start), end_exclusive=hex(end),
                                  unwind=hex(unwind), sha256=sha(piece),
                                  bytes_hex=piece.hex()))
    require(len(ins) == 100 and sum(x.size for x in ins) == len(raw),
            'instruction coverage changed')
    by_addr = {x.address: x for x in ins}
    require(len(by_addr) == len(ins), 'duplicate instruction boundary')
    cfg, branches, external = {}, [], []
    for x in ins:
        require(not any(op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP
                        for op in x.operands), 'unexpected RIP operand')
        if x.group(cs.CS_GRP_CALL):
            require(x.address == 0x60CE24 and len(x.operands) == 1 and
                    x.operands[0].type == X86_OP_IMM and
                    x.operands[0].imm == 0x60C410 and x.imm_size == 4,
                    'external call set changed')
            external.append(dict(kind='call_rel32', rva=hex(x.address),
                                 target_rva=hex(x.operands[0].imm),
                                 immediate_offset=x.imm_offset,
                                 immediate_size=x.imm_size,
                                 instruction=detail(x)))
        if x.group(cs.CS_GRP_RET):
            successors = []
        elif x.group(cs.CS_GRP_JUMP):
            require(len(x.operands) == 1 and x.operands[0].type == X86_OP_IMM,
                    'unmodeled indirect jump')
            target = x.operands[0].imm
            require(target in by_addr, 'branch escaped complete body')
            successors = [target]
            if x.mnemonic != 'jmp':
                successors.append(x.address + x.size)
            branches.append(detail(x))
        else:
            successors = [x.address + x.size]
        require(all(y in by_addr for y in successors),
                'edge not on captured instruction boundary')
        cfg[x.address] = successors
    require(len(branches) == 7 and len(external) == 1,
            'control-flow counts changed')
    seen, pending = set(), [ENTRY]
    while pending:
        at = pending.pop()
        if at in seen:
            continue
        seen.add(at)
        pending.extend(cfg[at])
    require(seen == set(by_addr), 'unreachable instruction in body')
    return (dict(entry=hex(ENTRY), end_exclusive=hex(END),
                 size_bytes=len(raw), sha256=sha(raw), bytes_hex=raw.hex(),
                 fragments=fragment_rows,
                 instructions=[detail(x) for x in ins],
                 cfg={hex(k): list(map(hex, v)) for k, v in cfg.items()},
                 branches=branches, external_relocations=external),
            by_addr, cfg)


def array_sites(by_addr):
    groups = {k: [] for k in ('pointer', 'primary', 'aux', 'property')}
    for x in by_addr.values():
        for i, op in enumerate(x.operands):
            if op.type != X86_OP_MEM:
                continue
            disp = op.mem.disp
            group = ('pointer' if disp == 0xE8 else
                     'primary' if 0x108 <= disp < 0x178 else
                     'aux' if 0x2C8 <= disp < 0x300 else
                     'property' if 0x3A8 <= disp < 0x3C8 else None)
            if group is None:
                continue
            require(x.disp_size == 4 and x.disp_offset + 4 <= x.size,
                    'array site lost disp32')
            groups[group].append(dict(rva=hex(x.address),
                                      access='write' if i == 0 else 'read',
                                      width_bytes=op.size,
                                      base_register=x.reg_name(op.mem.base),
                                      index_register=x.reg_name(op.mem.index),
                                      index_scale=op.mem.scale,
                                      original_displacement=disp,
                                      displacement_offset=x.disp_offset,
                                      displacement_size=x.disp_size,
                                      instruction=detail(x)))
    require([len(groups[k]) for k in groups] == [3, 14, 8, 4],
            'four-array site count changed')
    require([(sum(z['access'] == 'read' for z in groups[k]),
              sum(z['access'] == 'write' for z in groups[k]))
             for k in groups] == [(2, 1), (7, 7), (4, 4), (2, 2)],
            'four-array access direction changed')
    return groups


def pin_caller(im):
    require(im.root(0x57E01C) == CALLER_OWNER_ROOT,
            'caller owning function changed')
    raw = im.read(CALLER_START, CALLER_END - CALLER_START)
    require(sha(raw) == CALLER_SHA256, 'caller slice changed')
    ins = list(im.md.disasm(raw, CALLER_START))
    require([x.address for x in ins] ==
            [0x57E00F, 0x57E016, 0x57E01C, 0x57E021],
            'caller slice instruction boundaries changed')
    require(ins[0].bytes == bytes.fromhex('488d8b1808ea00') and
            ins[2].bytes == bytes.fromhex('e84fec0800') and
            ins[2].operands[0].imm == ENTRY,
            'owner roster address or direct call changed')
    return dict(start=hex(CALLER_START), end_exclusive=hex(CALLER_END),
                size_bytes=len(raw), bytes_hex=raw.hex(), sha256=sha(raw),
                owning_function=dict(start=hex(CALLER_OWNER_ROOT[0]),
                                     end_exclusive=hex(CALLER_OWNER_ROOT[1]),
                                     unwind=hex(CALLER_OWNER_ROOT[2])),
                instructions=[detail(x) for x in ins],
                meaning='RCX=owner+EA0818 at 57E00F; direct call 60CC70 at 57E01C. '
                        'This local slice does not check S+80/+84/+88.')


def pin_flow(by_addr, cfg, mover):
    expected = {
        0x60CC7A: '8bb984000000', 0x60CC83: '8b8180000000',
        0x60CC8B: '0f83d4010000', 0x60CC91: '8b9188000000',
        0x60CCA6: '3bd7', 0x60CCA8: '0f8370010000',
        0x60CCB5: '4a8b84c3e8000000', 0x60CCC3: '498981e8000000',
        0x60CDB2: '498b81e8000000', 0x60CE11: '4533c0',
        0x60CE14: '41897804', 0x60CE18: '8b9388000000',
        0x60CE1E: '448bc7', 0x60CE21: '488bcb',
        0x60CE24: 'e8e7f5ffff', 0x60CE29: 'ff8388000000',
        0x60CE2F: 'ffc7', 0x60CE3F: '0f8261feffff',
        0x60CE54: '898384000000', 0x60CE6A: '898184000000',
    }
    require(all(by_addr[a].bytes.hex() == blob for a, blob in expected.items()),
            'critical count/copy/map instructions changed')
    require(cfg[0x60CC8B] == [0x60CE65, 0x60CC91] and
            cfg[0x60CCA8] == [0x60CE1E, 0x60CCAE] and
            cfg[0x60CE3F] == [0x60CCA6, 0x60CE45],
            'major branch targets changed')
    move_ins = {int(x['rva'], 16): x for x in mover['instructions']}
    require(mover['sha256'] == MOVER_BODY_SHA256 and
            move_ins[0x60C423]['bytes'] == '448bf2' and
            move_ins[0x60C426]['bytes'] == '458bd0' and
            move_ins[0x60C438]['bytes'] == '4a8b84d1e8000000' and
            move_ins[0x60C440]['bytes'] == '498983e8000000',
            'previously pinned mover ABI/pointer direction changed')
    slots = ['A', 'B', 'C']
    mapping = {'A': 0, 'B': 1, 'C': 2}
    P, D, T = 1, 2, 3
    before = dict(P=P, D=D, T=T, slots=slots.copy(), map=mapping.copy())
    slots[D] = slots[P]  # Verified inline pointer P→D at CCB5/CCC3.
    mapping[slots[D]] = D  # Verified inline map write at CE14.
    slots[P] = slots[D]  # Verified 60C410 call with destination P/source D.
    mapping[slots[P]] = P  # Verified mover map rewrite in prior evidence.
    P += 1
    D += 1
    require(slots == ['A', 'B', 'B'] and mapping['C'] == 2 and D == T,
            'pointer identity counterexample changed')
    return dict(
        count_fields=dict(T='S+80h tracked', D='S+84h dense', P='S+88h prefix'),
        branch_order=[
            dict(rva='0x60cc8b', condition='D>=T', target='0x60ce65; D:=T then return'),
            dict(rva='0x60cca8', condition='P>=D', target='0x60ce1e; skip inline P→D'),
            dict(rva='0x60ce3f', condition='next D<T', target='0x60cca6; loop')],
        p_lt_d_path=dict(
            inline_pointer=['0x60ccb5 P load', '0x60ccc3 D store'],
            inline_primary='0x60ccca..0x60cd3a P→D',
            inline_aux='0x60cd46..0x60cd87 P→D',
            inline_property='0x60cd90..0x60cdaa P→D',
            inline_map='0x60cdb2..0x60ce14 copied entity ID mapped to D',
            shared_move='0x60ce18 EDX=P; 0x60ce1e R8D=D; 0x60ce24 call 60C410, therefore D→P',
            after='0x60ce29 P++; 0x60ce2f D++; 0x60ce54 D:=T at exit'),
        counterexample=dict(
            model_scope='One verified pointer/map path; static dataflow, not native execution.',
            before=before,
            after=dict(P=P, D=D, T=T, slots=slots, map=mapping),
            lost_entity='C was unique at old D=2, overwritten before being read; its map still points to slot 2'),
        conclusion='P<D does not preserve all distinct valid entities in [0,T). '
                   'The caller slice does not prove P<D unreachable. '
                   'P==D is the directly provable D<T no-copy case; P>D needs another contract.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    require(not args.output.exists(), 'refusing to overwrite output')
    prior = (HERE / 'roster_property_consumers_native_inventory.json').read_bytes()
    require(sha(prior) == PRIOR_INVENTORY_SHA256, 'consumer inventory changed')
    mover_bytes = (HERE / 'roster_move_native_evidence.json').read_bytes()
    require(sha(mover_bytes) == MOVER_EVIDENCE_SHA256, 'mover evidence changed')
    mover = json.loads(mover_bytes)['move']
    im = Image(args.evidence)
    body, by_addr, cfg = pin_body(im)
    body['array_sites'] = array_sites(by_addr)
    body['dataflow'] = pin_flow(by_addr, cfg, mover)
    result = dict(source_sha256=EXPECTED,
                  capture_identity_sha256=im.report['capture_sha256'],
                  prior_inventory_sha256=PRIOR_INVENTORY_SHA256,
                  mover_evidence_sha256=MOVER_EVIDENCE_SHA256,
                  compact=body, caller_slice=pin_caller(im),
                  finite_scope='Complete 60CC70 body/three unwind fragments; '
                               'only 57E00F..57E024 caller slice; prior complete 60C410 ABI evidence.',
                  limits=[
                      'Static identity counterexample is not proof that P<D occurs at runtime.',
                      'Only the local owner caller slice is pinned, not the whole caller or all callers.',
                      'No native emitter, live process, hook, map validity, sidecar lifetime, or multiplayer proof.'])
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(args.output), body_bytes=body['size_bytes'],
                          instructions=len(body['instructions']),
                          array_sites={k: len(v) for k, v in body['array_sites'].items()},
                          counterexample_after=body['dataflow']['counterexample']['after'])))


if __name__ == '__main__':
    main()
