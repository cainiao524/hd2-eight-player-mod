"""Pin both roster remove bodies and their direct map-delete helper offline.

The program reads a fixed saved capture only. It does not attach to a game,
generate native code, install a hook, or infer runtime reachability.
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

ROSTER_GLOBAL_RVA = 0x3326468
MOVER_RVA = 0x60C410
DELETE_RVA = 0x172F8A0
MOVER_EVIDENCE_SHA256 = '115802c09eb15f840932667717731150aa347e7ae8a72245dd92e05a5e86a242'
MOVER_BODY_SHA256 = 'b977816b8863034f0c247d0ee58779ab0f7d87cdb54eaa49ebfcdd5cab95434b'
BODIES = {
    0x60CEA0: dict(end=0x60CF4C, unwind=0x24257C0,
                   sha256='0c6e7607bf93a1e9fba1b8eeba998053b316670295e7d8db432352b3ce49cc7d',
                   instructions=43,
                   abi='RDX=removal entity record; read ID at +8; return saved record+10h in EAX',
                   external=[('rip_memory',0x60CEAA,ROSTER_GLOBAL_RVA),
                             ('call_rel32',0x60CEBE,DELETE_RVA),
                             ('call_rel32',0x60CF0E,MOVER_RVA),
                             ('call_rel32',0x60CF3A,MOVER_RVA)]),
    0x540A40: dict(end=0x540AE0, unwind=0x2410A84,
                   sha256='35e4c996bb1466c41df455f8e5f9df1174c8c2bb958ee127a3b7ecc59f6abcf8',
                   instructions=40,
                   abi='RCX=removal entity record; read ID at +8; output depends on map/mover path',
                   external=[('rip_memory',0x540A49,ROSTER_GLOBAL_RVA),
                             ('call_rel32',0x540A57,DELETE_RVA),
                             ('call_rel32',0x540AA4,MOVER_RVA),
                             ('tail_jump_rel32',0x540AD5,MOVER_RVA)]),
    DELETE_RVA: dict(end=0x172F9A3, unwind=0x2567A5C,
                     sha256='d58cc9dbb3c79864b4ca0692be1fcf3a31ec267c059f7c904063aed53d05ec4f',
                     instructions=78,
                     abi='RCX=&S+D0 map header; EDX=entity ID; EAX=old ordinal if found, zero on miss',
                     external=[]),
}


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def detail(x):
    result = row(x)
    result['encoding'] = dict(rex=x.rex, modrm=x.modrm, sib=x.sib,
                              displacement_offset=x.disp_offset,
                              displacement_size=x.disp_size,
                              immediate_offset=x.imm_offset,
                              immediate_size=x.imm_size)
    return result


def complete_body(im, start, spec):
    end = spec['end']
    fs = [f for f in im.functions if im.root(f[0])[0] == start]
    require(fs == [(start, end, spec['unwind'])],
            'unwind extent changed at ' + hex(start))
    raw = im.read(start, end-start)
    require(sha(raw) == spec['sha256'], 'body fingerprint changed at ' + hex(start))
    ins = list(im.md.disasm(raw, start))
    require(len(ins) == spec['instructions'] and
            sum(x.size for x in ins) == len(raw),
            'incomplete body decode at ' + hex(start))
    by_addr = {x.address: x for x in ins}
    require(len(by_addr) == len(ins), 'duplicate instruction boundary')
    edges, branches, externals = {}, [], []
    for x in ins:
        for op in x.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                externals.append(dict(kind='rip_memory', rva=hex(x.address),
                                      target_rva=hex(x.address+x.size+op.mem.disp),
                                      displacement_offset=x.disp_offset,
                                      displacement_size=x.disp_size,
                                      instruction=detail(x)))
        if x.group(cs.CS_GRP_CALL):
            require(len(x.operands) == 1 and x.operands[0].type == X86_OP_IMM,
                    'unmodeled indirect call')
            externals.append(dict(kind='call_rel32', rva=hex(x.address),
                                  target_rva=hex(x.operands[0].imm),
                                  displacement_offset=x.imm_offset,
                                  displacement_size=x.imm_size,
                                  instruction=detail(x)))
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
                                      instruction=detail(x)))
            if x.mnemonic != 'jmp':
                successors.append(x.address+x.size)
            branches.append(detail(x))
        else:
            successors = [x.address+x.size]
        require(all(t in by_addr for t in successors),
                'edge outside body at ' + hex(x.address))
        edges[x.address] = successors
    require({(r['kind'],int(r['rva'],16),int(r['target_rva'],16))
             for r in externals} == set(spec['external']),
            'external relocation set changed at ' + hex(start))
    require(all(r['displacement_size'] == 4 for r in externals),
            'unexpected external relocation width')
    seen, pending = set(), [start]
    while pending:
        at = pending.pop()
        if at in seen:
            continue
        seen.add(at)
        pending.extend(edges[at])
    require(seen == set(by_addr), 'unreachable instruction in body')
    return (dict(entry=hex(start), end_exclusive=hex(end),
                 size_bytes=len(raw), sha256=sha(raw), bytes_hex=raw.hex(),
                 fragment=dict(start=hex(start),end_exclusive=hex(end),
                               unwind=hex(spec['unwind']), sha256=sha(raw)),
                 abi=spec['abi'], instructions=[detail(x) for x in ins],
                 cfg={hex(k):list(map(hex,v)) for k,v in edges.items()},
                 branches=branches,external_relocations=externals),by_addr,edges)


def pin_delete(by_addr):
    exact = {0x172F8EB:'33c0',0x172F8F9:'8b410c',
             0x172F8FC:'418901',0x172F90C:'418b6904',
             0x172F969:'4a8b041b',0x172F972:'498904d3',
             0x172F97C:'42891403',0x172F990:'8bc5'}
    require(all(by_addr[a].bytes.hex()==blob for a,blob in exact.items()),
            'map-delete miss/delete/backshift contract changed')
    return dict(miss_returns_zero=detail(by_addr[0x172F8EB]),
                empty_sentinel_store=detail(by_addr[0x172F8FC]),
                saved_ordinal=detail(by_addr[0x172F90C]),
                shift_copy=[detail(by_addr[a]) for a in (0x172F969,0x172F972,0x172F97C)],
                found_return=detail(by_addr[0x172F990]),
                meaning='Zero on absent/capacity-zero is ambiguous with a present key mapped to ordinal zero; deletion precedes caller count mutation.')


def pin_remove(start, by_addr, edges):
    if start==0x60CEA0:
        a=dict(delete=0x60CEBE, compare=0x60CECF, branch=0x60CED2,
               pending_decrement=0x60CED4, pointer=0x60CEEB,
               bit=0x60CEF3, prefix_decrement=0x60CEF9,
               first_move=0x60CF0E, dense_total_decrement=0x60CF22,
               dense_decrement=0x60CF28, dense_store=0x60CF2B,
               last_move=0x60CF3A, missing_minus_one=0x60CEE6,
               return_field=0x60CF3F)
    else:
        a=dict(delete=0x540A57, compare=0x540A65, branch=0x540A68,
               pending_decrement=0x540A6A, pointer=0x540A81,
               bit=0x540A89, prefix_decrement=0x540A8F,
               first_move=0x540AA4, dense_total_decrement=0x540AB8,
               dense_decrement=0x540ABE, dense_store=0x540AC1,
               last_move=0x540AD5, missing_minus_one=0x540A7C)
    require(by_addr[a['delete']].operands[0].imm==DELETE_RVA and
            by_addr[a['last_move']].operands[0].imm==MOVER_RVA and
            by_addr[a['first_move']].operands[0].imm==MOVER_RVA and
            by_addr[a['bit']].bytes.hex()=='f6411401' and
            by_addr[a['dense_decrement']].bytes.hex()=='41ffc8',
            'removal branch/mover/flag behavior changed')
    require(edges[a['branch']][0] == a['missing_minus_one'] and
            by_addr[a['missing_minus_one']].mnemonic=='cmp' and
            by_addr[a['missing_minus_one']].operands[1].imm==-1,
            'dense unsigned branch or minus-one check changed')
    pointer=by_addr[a['pointer']]
    require(pointer.operands[1].type==X86_OP_MEM and
            pointer.operands[1].mem.disp==0xE8,
            'pointer array read changed')
    return dict(critical_sites={k:detail(by_addr[v]) for k,v in a.items()},
                pointer_site=dict(rva=hex(pointer.address), access='read',
                                  width_bytes=pointer.operands[1].size,
                                  displacement_offset=pointer.disp_offset,
                                  displacement_size=pointer.disp_size,
                                  base_register=pointer.reg_name(pointer.operands[1].mem.base),
                                  index_register=pointer.reg_name(pointer.operands[1].mem.index),
                                  index_scale=pointer.operands[1].mem.scale,
                                  original_displacement=0xE8),
                flow='Map delete first. If r>=D, T-- and move old last tracked slot to r unless equal. '
                     'If r<D, inspect slot r entity bit0; if set P-- and move old prefix tail to r; '
                     'then T--, D-- and move old dense tail to the resulting r. '
                     'The -1 check is behind unsigned r<D and is unreachable for r=FFFFFFFF.')


def counterexamples():
    return [
        dict(name='dense_delete_with_pending_tail',
             before=dict(P=0,D=1,T=2,slots=['A_dense','B_pending'],map={'A_dense':0,'B_pending':1}),
             operation='Remove A_dense, valid map hit r=0, record bit0 clear. Original sets T=1,D=0 and skips final mover.',
             after=dict(P=0,D=0,T=1,slots=['A_dense','B_pending'],map={'B_pending':1}),
             conclusion='B_pending is outside tracked [0,T), with stale map ordinal 1.'),
        dict(name='absent_key_aliases_ordinal_zero',
             before=dict(P=0,D=1,T=1,slots=['A_dense'],map={'A_dense':0}),
             operation='Remove absent X: delete helper returns 0 and changes no map bucket; caller treats 0 as A_dense ordinal.',
             after=dict(P=0,D=0,T=0,slots=['A_dense'],map={'A_dense':0}),
             conclusion='A_dense is dropped from tracked range though its map entry remains.'),
        dict(name='prefix_flag_mismatch_underflow',
             before=dict(P=0,D=1,T=1,slot0_bit0=1),
             operation='Remove present ordinal 0; code tests record bit0 and decrements P before T/D.',
             after=dict(P=0xFFFFFFFF),
             conclusion='P wraps and first mover can use invalid source ordinal; partition/flag consistency is a necessary precondition.'),
    ]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    require(not args.output.exists(),'refusing to overwrite output')
    mover_bytes=(HERE/'roster_move_native_evidence.json').read_bytes()
    require(sha(mover_bytes)==MOVER_EVIDENCE_SHA256 and
            json.loads(mover_bytes)['move']['sha256']==MOVER_BODY_SHA256,
            'prior full mover evidence changed')
    im=Image(args.evidence)
    out={}; decoded={}
    for start,spec in BODIES.items():
        body,by_addr,edges=complete_body(im,start,spec)
        out[hex(start)]=body
        decoded[start]=(by_addr,edges)
    out[hex(DELETE_RVA)]['delete_semantics']=pin_delete(decoded[DELETE_RVA][0])
    for start in (0x60CEA0,0x540A40):
        out[hex(start)]['remove_semantics']=pin_remove(start,*decoded[start])
    result=dict(source_sha256=EXPECTED,
                capture_identity_sha256=im.report['capture_sha256'],
                mover_evidence_sha256=MOVER_EVIDENCE_SHA256,
                bodies=out,
                counterexamples=counterexamples(),
                finite_scope='Two complete remove bodies, one direct full map-delete helper, and prior pinned full mover ABI only.',
                limits=[
                    'The static counterexamples do not prove runtime reachability.',
                    'Map presence, unique keys, valid ordinals, P/D/T ordering and record bit0 partition consistency are not established by these bodies.',
                    'Dense removal with D<T does not preserve every distinct tracked pending entity without another contract or repair.',
                    'No emitter, live hook, caller inventory expansion, or multiplayer verification.'])
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),
                          body_instruction_counts={k:len(v['instructions']) for k,v in out.items()},
                          direct_helper=hex(DELETE_RVA))))


if __name__=='__main__':
    main()
