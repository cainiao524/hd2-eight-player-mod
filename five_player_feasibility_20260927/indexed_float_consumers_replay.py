"""Bounded offline consumer audit for the already identified destination D.

Only saved capture/workspace files are read. No process, launch, network or patch API.
This is a finite set of source-proven D paths, not an exhaustive consumer inventory.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row
from capstone import CS_GRP_JUMP
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

PRIOR_SHA = '11e984e270540eded0e141f821ddfbb22118c0b99645237eca15e14149d42378'
CALLER_REVIEW_SHA = 'b1ac8e336b754ee5ec7cc55128ddb3b5670eaf11f9419c38843a5b472cd5ef90'
ROOTS = {
    0x142B990: 0x142BEB3, 0x142BED0: 0x142C89E,
    0x142C9B0: 0x142CB57, 0x142CB90: 0x142D864,
    0x142D870: 0x142EE66, 0x142EE70: 0x142F528,
    0x142FED0: 0x142FF8B, 0x142FF90: 0x1430444,
    0x1430450: 0x1431FE4, 0x14329B0: 0x1432F09,
    0x1433020: 0x14332D9, 0x14335F0: 0x143372C,
}
WINDOWS = {
    'manager_instance_and_writer': (0x727500, 0x727610),
    'same_instance_lifecycle_and_update_calls': (0x72AC49, 0x72AD3D),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    out = Path(args.output)
    require(not out.exists(), 'refusing overwrite')
    prior_raw = (HERE / 'indexed_float_storage_evidence.json').read_bytes()
    require(sha(prior_raw) == PRIOR_SHA, 'prior destination evidence changed')
    prior = json.loads(prior_raw)
    caller_review_raw = (HERE / 'indexed_float_consumers_review_caller_cfg.json').read_bytes()
    require(sha(caller_review_raw)==CALLER_REVIEW_SHA,'independent full caller CFG evidence changed')
    im = Image(args.evidence)
    require(prior['capture_identity_sha256'] == im.report['capture_sha256'], 'capture identity differs')
    spans, roots, decoded, raw_tails = {}, {}, {}, []

    def span(label, a, b, proof):
        raw = im.read(a, b-a)
        ins = list(im.md.disasm(raw, a))
        require(ins and sum(i.size for i in ins) == len(raw), 'incomplete decode '+label)
        for i in ins:
            bounded = im.instruction(i.address)
            require(bounded is not None and bounded.bytes == i.bytes, 'instruction boundary '+hex(i.address))
        decoded.update({i.address: i for i in ins})
        spans[label] = dict(start=hex(a), end_exclusive=hex(b), sha256=sha(raw),
                            proof=proof, instructions=[row(i) for i in ins])
        return ins

    for entry, end in ROOTS.items():
        fs = [f for f in im.functions if entry <= f[0] < end and im.root(f[0])[0] == entry]
        require(fs and fs[0][0] == entry and fs[-1][1] == end, 'root bounds '+hex(entry))
        require(all(a[1] == b[0] for a, b in zip(fs, fs[1:])), 'root gaps '+hex(entry))
        roots[entry] = []
        for f in fs:
            end_code = 0x142D831 if f[0] == 0x142D818 else f[1]
            roots[entry] += span(hex(f[0]), f[0], end_code, dict(kind='code_prefix_before_nop_and_referenced_table' if end_code != f[1] else 'complete_unwind_fragment',
                root=hex(entry), fragment=[hex(v) for v in f]))
            if end_code != f[1]:
                raw = im.read(end_code, f[1]-end_code)
                require(raw[:3] == bytes.fromhex('0f1f00'), 'post-ret padding changed')
                table = [int.from_bytes(raw[n:n+4],'little') for n in range(3,len(raw),4)]
                require(len(table)==12 and table==[0x142CEA5,0x142CEB6,0x142CEAA,0x142CEB1]*3,'switch table changed')
                raw_tails.append(dict(start=hex(end_code),end_exclusive=hex(f[1]),bytes=raw.hex(),sha256=sha(raw),
                    interpretation='Post-ret3-byte NOP then12 DWORD RVAs referenced by142CE98..142CEA3; stored as data, not instructions.',
                    dword_rva_values=[hex(x) for x in table],dispatch='142CE98/142CEA0/142CEA3'))
    for label, (a,b) in WINDOWS.items():
        require(im.instruction(a) is not None and im.instruction(b) is not None, 'window boundary')
        span(label, a, b, dict(kind='unwind_bounded_window', root=hex(im.root(a)[0])))
    caller_restore_pins=[]
    for at in [0x7251A7,0x72B230]:
        i=im.instruction(at)
        require(i is not None,'caller save/restore instruction boundary')
        decoded[at]=i
        caller_restore_pins.append(row(i))

    semantic = [
        (0x7251A7,'mov','qword ptr [rbp + 0x130], rcx'),
        (0x72B230,'mov','r14, qword ptr [rbp + 0x130]'),
        (0x727516,'lea','rsi, [r14 + 0x4f90]'),
        (0x72752C,'imul','rax, rax, 0x55a698'), (0x727537,'add','rsi, rax'),
        (0x72755D,'lea','rcx, [rsi + 0x4c8260]'), (0x727579,'call','0x14329b0'),
        (0x7275F3,'lea','rcx, [rsi + 0x4c8260]'), (0x7275FA,'call','0x14335f0'),
        (0x72AC69,'lea','rcx, [rsi + 0x4c8260]'), (0x72AC70,'call','0x142c9b0'),
        (0x72ACA3,'lea','rcx, [rsi + 0x4c8260]'), (0x72ACC6,'call','0x142bed0'),
        (0x72ACFC,'lea','rcx, [rsi + 0x4c8260]'), (0x72AD11,'call','0x142d870'),
        (0x72AD1A,'lea','rcx, [rsi + 0x4c8260]'), (0x72AD38,'call','0x1430450'),
        (0x142BB8D,'lea','r14, [rbx + 0x80eb8]'), (0x142BB94,'mov','r12d, 4'),
        (0x142BBA0,'lea','rcx, [r14 - 0xa0]'), (0x142BBA9,'mov','r8d, 0x298'),
        (0x142BC2C,'add','r14, 0x298'), (0x142BC33,'sub','r12, 1'),
        (0x142BC37,'jne','0x142bba0'),
        (0x142BEF6,'mov','rbx, rcx'), (0x142BFAC,'xor','ecx, ecx'),
        (0x142C867,'mov','qword ptr [rbx + 0x8d6c4], 0xffffffffffffffff'),
        (0x142C872,'mov','qword ptr [rbx + 0x8d6d4], rcx'),
        (0x142C879,'mov','qword ptr [rbx + 0x8d6cc], 0xffffffffffffffff'),
        (0x142C884,'mov','qword ptr [rbx + 0x8d6dc], rcx'),
        (0x142CC37,'xor','r12d, r12d'), (0x142D7D2,'lea','rbx, [rdi + 0x80e18]'),
        (0x142CE90,'add','eax, -0xc'), (0x142CE93,'cmp','eax, 0xb'),
        (0x142CE96,'ja','0x142ceb6'),
        (0x142CE98,'mov','ecx, dword ptr [r13 + rax*4 + 0x142d834]'),
        (0x142CEA0,'add','rcx, r13'), (0x142CEA3,'jmp','rcx'),
        (0x142D7E0,'cmp','byte ptr [rbx], 0'), (0x142D7EB,'call','0x142ff90'),
        (0x142D7F0,'inc','r12d'), (0x142D7F3,'add','rbx, 0x298'),
        (0x142D7FA,'cmp','r12d, 4'), (0x142D7FE,'jb','0x142d7e0'),
        (0x142D8A7,'mov','qword ptr [rsp + 0x68], rcx'),
        (0x142D8B6,'mov','rsi, rcx'), (0x142D8B9,'call','0x142ee70'),
        (0x142D972,'mov','rcx, rsi'), (0x142D975,'call','0x142cb90'),
        (0x142DA78,'lea','r14, [rsi + 0x810a5]'), (0x142DA87,'xor','r12d, r12d'),
        (0x142DA9B,'mov','dword ptr [rsp + 0x60], r12d'),
        (0x142DAB0,'cmp','byte ptr [r14 - 0x28d], 0'),
        (0x142DF7F,'inc','r13d'), (0x142DF82,'add','r14, 0x298'),
        (0x142DF8E,'cmp','r13d, 4'), (0x142DF92,'jb','0x142dab0'),
        (0x142EA44,'call','0x606820'), (0x142EA49,'mov','r15d, eax'),
        (0x142EA69,'imul','rbx, rax, 0x298'),
        (0x142EA70,'cmp','byte ptr [rbx + r14 + 0x80e18], 0'),
        (0x142EA85,'call','0x1433020'), (0x142EA90,'call','0x142ff90'),
        (0x142EA9C,'mov','rax, qword ptr [rbx + r14 + 0x80e24]'),
        (0x142EB05,'mov','eax, dword ptr [rdi + 0x84]'), (0x142EB0B,'mov','r8d, r12d'),
        (0x142EB0E,'mov','qword ptr [rbp - 0x60], 0xffffffffffffffff'),
        (0x142EB16,'mov','qword ptr [rbp - 0x58], 0xffffffffffffffff'),
        (0x142EB33,'mov','dword ptr [rbp - 0x50], 0x56d7e815'),
        (0x142EB61,'lea','rdx, [rdi + 0x3b4]'), (0x142EB70,'mov','eax, dword ptr [rdx]'),
        (0x142EB72,'cmp','eax, r15d'), (0x142EB75,'je','0x142eb81'),
        (0x142EB77,'mov','ecx, r8d'), (0x142EB7A,'inc','r8d'),
        (0x142EB7D,'mov','dword ptr [rbp + rax*4 - 0x60], ecx'),
        (0x142EB81,'add','rdx, 0x20'), (0x142EB85,'sub','r9, 1'),
        (0x142EB89,'jne','0x142eb70'), (0x142EB94,'lea','r12, [rbp - 0x60]'),
        (0x142EBA1,'add','r14, 0x80e30'),
        (0x142EC6D,'mov','qword ptr [r14 - 4], rax'),
        (0x142EC9D,'mov','qword ptr [r14 - 0x14], rax'),
        (0x142ED2E,'mov','eax, dword ptr [r12]'), (0x142ED32,'cmp','eax, -1'),
        (0x142ED37,'mov','edx, dword ptr [rbp + rax*4 - 0x70]'),
        (0x142ED3B,'mov','edi, dword ptr [rbp + rax*4 - 0x50]'),
        (0x142ED3F,'mov','ebx, dword ptr [rbp + rax*4 - 0x80]'),
        (0x142EDB5,'add','r14, 0x298'), (0x142EDBE,'add','r12, 4'),
        (0x142EDC6,'cmp','eax, 4'), (0x142EDC9,'jb','0x142ebc3'),
        (0x142EF48,'mov','ecx, dword ptr [rax + r9 + 0x163ac]'),
        (0x142EF50,'cmp','ecx, -1'), (0x142EF78,'imul','rcx, rcx, 0x298'),
        (0x142EF8E,'movss','xmm7, dword ptr [rcx + rdi + 0x80e24]'),
        (0x142EF9E,'movss','xmm8, dword ptr [rcx + rdi + 0x80e28]'),
        (0x142FEF3,'lea','rdx, [rcx + 0x8d6d4]'), (0x142FEFA,'add','rcx, 0x80e18'),
        (0x142FF20,'add','rdx, 4'), (0x142FF24,'add','rcx, 0x298'),
        (0x142FF2B,'cmp','r8d, 4'), (0x142FF2F,'jb','0x142ff01'),
        (0x142FFDF,'cmp','ebx, eax'), (0x142FFE1,'jne','0x143043b'),
        (0x1430004,'imul','rcx, rbx, 0x298'),
        (0x14303AB,'call','0x142fed0'), (0x14303DD,'call','0x142fed0'),
        (0x14303F3,'lea','rcx, [rdi + 0x80e40]'),
        (0x1430402,'lea','rcx, [rdi + 0x80eb8]'),
        (0x1430509,'xor','edi, edi'), (0x1430635,'lea','rbx, [rsi + 0x80eb5]'),
        (0x1430644,'mov','r12d, edi'), (0x143064F,'lea','r15, [rsi + 0x8d6d4]'),
        (0x1430690,'cmp','byte ptr [rbx - 0x9d], dil'),
        (0x14306B3,'movss','dword ptr [rbx - 0x79], xmm0'),
        (0x1430DD0,'add','r15, 4'), (0x1430DD4,'inc','r12d'),
        (0x1430DD7,'add','rbx, 0x298'), (0x1430DE3,'cmp','r12d, 4'),
        (0x1430DE7,'jb','0x1430690'),
        (0x1431523,'mov','r15d, dword ptr [rax + 0x3b4]'),
        (0x1431646,'imul','rcx, rax, 0x298'), (0x1431A6B,'imul','rcx, rax, 0x298'),
        (0x14329F1,'lea','rbx, [rcx + 0x810bc]'), (0x1432A00,'mov','esi, 2'),
        (0x1432BCE,'mov','qword ptr [rbx - 0x298], rax'),
        (0x1432C8F,'mov','qword ptr [rbx - 0x298], rax'),
        (0x1432DCA,'mov','qword ptr [rbx], rax'), (0x1432E8B,'add','rbx, 0x530'),
        (0x1432E80,'mov','qword ptr [rbx], rax'),
        (0x1432E9A,'sub','rsi, 1'), (0x1432E9E,'jne','0x1432aa0'),
        (0x143306F,'imul','rdi, rax, 0x298'),
        (0x14331B8,'mov','qword ptr [rdi + rbx + 0x80e24], rax'),
        (0x143328C,'mov','qword ptr [rdi + rbx + 0x80e24], rax'),
        (0x143362F,'mov','qword ptr [r12 + rcx + 0x80e24], rax'),
        (0x14336FC,'call','0x142ff90'), (0x1433706,'call','0x1433020'),
        (0x1433710,'call','0x142ff90'),
    ]
    for at, mn, op in semantic:
        require(at in decoded and (decoded[at].mnemonic,decoded[at].op_str)==(mn,op),
                'semantic pin '+hex(at)+' actual '+str(row(decoded[at]) if at in decoded else None))

    audits = []
    for a,b,aliases,expected in [
        (0x725160,0x72AD3D,('rsi','esi','si','sil'),[0x725352,0x725361,0x7273A4,0x727516,0x727537]),
        (0x142D870,0x142DA78,('rsi','esi','si','sil'),[0x142D8B6]),
        (0x1430450,0x1431B00,('rsi','esi','si','sil'),[0x14304C8]),
        (0x142CB90,0x142D800,('rdi','edi','di','dil'),[0x142CBBA]),
        (0x142CB90,0x142D7D2,('r12','r12d','r12w','r12b'),[0x142CC37]),
        (0x142EE70,0x142F4B0,('rdi','edi','di','dil'),[0x142EEE8]),
        (0x142FF90,0x1430422,('rsi','esi','si','sil'),[0x142FF9C]),
        (0x1433020,0x14332A0,('rbx','ebx','bx','bl','bh'),[0x1433037]),
        (0x142BED0,0x142C88B,('rbx','ebx','bx','bl','bh'),[0x142BEF6]),
    ]:
        # The audit end need not be an instruction boundary: decode a full root prefix
        # through the last complete instruction before it, then use that exact end.
        f = im.containing(b-1)
        root_ins = list(im.md.disasm(im.read(a,f[1]-a),a))
        ins = [i for i in root_ins if i.address < b]
        end = ins[-1].address+ins[-1].size
        raw = im.read(a,end-a)
        require(sum(i.size for i in ins)==len(raw),'prefix decode incomplete')
        writes = [i for i in ins if any(im.md.reg_name(r) in aliases for r in i.regs_access()[1])]
        require([i.address for i in writes]==expected,'base prefix changed '+hex(a))
        audits.append(dict(start=hex(a),end_exclusive=hex(end),sha256=sha(raw),aliases=aliases,
            explicit_writes=[row(i) for i in writes]))

    # Actual control flow reaching definitions, rather than assuming R14/R12 stay fixed.
    cfg_proofs = []
    body = {i.address:i for i in roots[0x142D870]}
    for aliases, checks in [
        (('r14','r14d','r14w','r14b'), {
            0x142EA70:[0x142DF98,0x142E2D4,0x142E5B4,0x142E7D7],
            0x142EBA1:[0x142DF98,0x142E2D4,0x142E5B4,0x142E7D7]}),
        (('r12','r12d','r12w','r12b'), {
            0x142EB0B:[0x142DA87,0x142DE97,0x142E2AA,0x142E58A,0x142E7A5],
            0x142DA9B:[0x142DA87]}),
    ]:
        incoming = {0x142D870:{-1}}
        pending = [0x142D870]
        while pending:
            at = pending.pop(); i = body[at]
            outgoing = {at} if any(im.md.reg_name(r) in aliases for r in i.regs_access()[1]) else incoming[at]
            targets = []
            if i.group(CS_GRP_JUMP):
                require(i.operands[0].type == X86_OP_IMM,'unhandled indirect jump in CFG')
                targets.append(i.operands[0].imm)
                if i.mnemonic != 'jmp': targets.append(at+i.size)
            elif i.mnemonic not in ('ret','int3','ud2'):
                targets.append(at+i.size)
            for t in targets:
                require(t in body,'unexpected CFG exit '+hex(t))
                merged = incoming.get(t,set()) | outgoing
                if merged != incoming.get(t,set()): incoming[t]=merged;pending.append(t)
        for at, expected in checks.items():
            require(incoming[at] == set(expected),'reaching definitions changed '+hex(at))
            for d in expected:
                if aliases[0]=='r14':
                    require((body[d].mnemonic,body[d].op_str)==('mov','r14, qword ptr [rsp + 0x68]'),'D restore changed')
                else:
                    require((body[d].mnemonic,body[d].op_str)==('xor','r12d, r12d'),'zero definition changed')
            cfg_proofs.append(dict(at=hex(at),aliases=aliases,definitions=[row(body[d]) for d in expected]))
    saved_D_writes = [i for i in body.values() if i.op_str.startswith('qword ptr [rsp + 0x68]')]
    require([i.address for i in saved_D_writes]==[0x142D8A7],'saved D slot overwritten')

    # Close the one indirect dispatch in142CB90 using its saved, range-guarded table.
    # R13 is reused elsewhere; prove its image-base definitions at this dispatch.
    cb = {i.address:i for i in roots[0x142CB90]}
    aliases = ('r13','r13d','r13w','r13b')
    incoming, pending = {0x142CB90:{-1}}, [0x142CB90]
    while pending:
        at = pending.pop(); i = cb[at]
        outgoing = {at} if any(im.md.reg_name(r) in aliases for r in i.regs_access()[1]) else incoming[at]
        targets = []
        if i.group(CS_GRP_JUMP):
            if i.operands[0].type == X86_OP_IMM:
                targets.append(i.operands[0].imm)
            else:
                require(at==0x142CEA3 and i.op_str=='rcx','unhandled CB90 indirect jump')
                targets.extend(sorted(set(table)))
            if i.mnemonic != 'jmp': targets.append(at+i.size)
        elif i.mnemonic not in ('ret','int3','ud2'):
            targets.append(at+i.size)
        for t in targets:
            require(t in cb,'CB90 unexpected normal CFG exit '+hex(t))
            merged = incoming.get(t,set()) | outgoing
            if merged != incoming.get(t,set()): incoming[t]=merged;pending.append(t)
    require(len(incoming)==len(cb)==673,'CB90 normal CFG coverage changed')
    for at in [0x142CE98,0x142CEA0,0x142CEA3]:
        require(incoming[at]=={0x142CC4D,0x142D1B8},'dispatch base definitions changed')
    for at in [0x142CC4D,0x142D1B8]:
        i=cb[at]
        refs=[i.address+i.size+o.mem.disp for o in i.operands if o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP]
        require(i.mnemonic=='lea' and i.op_str.startswith('r13, ') and refs==[0], 'dispatch image base changed')
    table_proof=dict(table_span=['0x142d834','0x142d864'],padding_span=['0x142d831','0x142d834'],
        index_guard='142CE90 subtractC;142CE93 compareB;142CE96 unsigned-above fallback142CEB6',
        dispatch=[row(cb[x]) for x in [0x142CE98,0x142CEA0,0x142CEA3]],
        image_base_reaching_definitions=[row(cb[x]) for x in [0x142CC4D,0x142D1B8]],
        table_targets=[hex(x) for x in table],normal_cfg_reached_instructions=len(incoming),
        note='All12 saved table RVAs are normal instruction boundaries; four unique targets. Tail data are not instructions.')

    globals_ = []
    for at, target in [(0x72757E,0x3326468),(0x7275B1,0x3326468),
                       (0x142EA95,0x3326468),(0x142EAFE,0x3326468),(0x1431506,0x3326468)]:
        i=decoded[at]
        refs=[i.address+i.size+o.mem.disp for o in i.operands if o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP]
        require(refs==[target],'roster source changed')
        globals_.append(dict(instruction=row(i),target=hex(target)))

    base,stride=0x80E18,0x298
    require(base+4*stride==0x81878 and 2*stride==0x530,'record arithmetic')
    require(0x810BC-0x298==0x80E24 and 0x810A5-0x28D==base and 0x80EB5-0x9D==base,'relative bases')
    require(-0x60+4*4==-0x50 and 0x8D6C4+4*4==0x8D6D4 and 0x8D6D4+4*4==0x8D6E4,'companion overlap arithmetic')
    result = dict(schema_version=2, source_sha256=EXPECTED,
        capture_identity_sha256=im.report['capture_sha256'],prior_evidence_sha256=PRIOR_SHA,
        runtime_verified=False,scope='Finite source-proven D consumers reached from the identified manager update/writer paths; not exhaustive',
        code_spans=spans,raw_unwind_tails=raw_tails,semantic_pins=[row(decoded[x[0]]) for x in semantic],
        selected_instruction_count=sum(len(x['instructions']) for x in spans.values())+len(caller_restore_pins),
        caller_manager_save_restore_pins=caller_restore_pins,
        full_caller_cfg_independent_evidence=dict(file='indexed_float_consumers_review_caller_cfg.json',sha256=CALLER_REVIEW_SHA,
            note='Independent complete5507-instruction caller CFG: six RSI=D-source sites reach727537; R14 at727516 comes from entry7251A4 or loop restore72B230. Saved manager slot[RBP+130]=[RSP+230] has only7251A7 write. This replay pins that evidence plus the two additional captured instructions; it does not claim to recompute that separate full caller CFG.'),
        selected_root_instruction_counts={hex(k):len(v) for k,v in roots.items()},
        base_prefix_audits=audits,normal_cfg_reaching_definitions=cfg_proofs,
        referenced_jump_table=table_proof,
        saved_D_slot_writes=[row(i) for i in saved_D_writes],roster_global_proofs=globals_,
        base_identity=prior['base_identity'],record_layout=prior['initialized_record_layout'],
        record_subobjects=dict(relative_offsets=['0x28','0xa0','0x118','0x1a0','0x218'],size='0x78',
            constructor='140C160',cleanup='140C200',owner_backpointer='+8 = D',pool_pointer='+20 = D+36F8',
            note='These pointers are initialized by the pinned prior evidence; generic helpers receive interior subobject pointers.'),
        same_D_edges=[
            ['727579','14329B0','RCX=U+4C8260'],['7275FA','14335F0','RCX=U+4C8260'],
            ['72AC70','142C9B0','RCX=U+4C8260'],['72ACC6','142BED0','RCX=U+4C8260'],
            ['72AD11','142D870','RCX=U+4C8260'],['72AD38','1430450','RCX=U+4C8260'],
            ['142D8B9','142EE70','RCX retained entry D'],['142D975','142CB90','RCX=RSI=D'],
            ['14336FC/1433710','142FF90','RCX=R14=D, EDX=input n'],
            ['1433706','1433020','RCX=R14=D, EDX=input n'],
            ['142EA85/142EA90','1433020/142FF90','RCX=restored R14=D, EDX=selected roster index'],
            ['142D7EB','142FF90','RCX=RDI=D, EDX=loop slot'],
            ['14303AB/14303DD','142FED0','RCX=RSI=D, EDX=input n']],
        bounded_consumers=[
            dict(root='142B990',kind='initialize',count=4,stride='298',proof='142BB94/142BBA0/142BC2C/142BC37',subobjects=5),
            dict(root='142C9B0',kind='cleanup',count=4,stride='298',proof='complete body and prior evidence',subobjects=5),
            dict(root='14329B0',kind='float read/modify/write',count=4,proof='1432A00 count2; two records per iteration;1432E8B step530',
                 condition='parameter differs from saved D+8D700'),
            dict(root='142CB90',kind='enabled-record scan calls142FF90',count=4,proof='142D7D2..142D7FE'),
            dict(root='142D870',kind='two record loops plus indexed path',count=4,
                 proof=['142DA78..142DF92','142EBA1..142EDC9','142EA69/142EA70/142EA9C'],
                 fields=['flag +0','float pairs +4/+c/+14','five embedded subobjects'],
                 dynamic_index='606820 selected roster index; sentinel tests, no numeric <4 gate at the access'),
            dict(root='1430450',kind='record/subobject processing and indexed float reads',count=4,
                 proof=['1430635..1430DE7','1431523/1431646','1431A6B'],
                 dynamic_index='first roster record network index when roster+88 !=0; -1 sentinel gates',
                 fields=['flag +0','float pair +14','float +24','embedded subobject fields']),
            dict(root='14335F0',kind='indexed qword write/flag and downstream calls',index='roster n',bound='no numeric <4 before first write'),
            dict(root='1433020',kind='indexed float read/modify/write',index='caller n',bound='coordinate clamp is not an index bound'),
            dict(root='142FF90',kind='indexed float/metadata read and subobject calls',index='caller n',
                 condition='input n must equal selected local/current index from606820, otherwise return before record access'),
            dict(root='142FED0',kind='four enabled-record scan plus per-n metadata writes',count=4,proof='142FEF3..142FF2F'),
            dict(root='142EE70',kind='indexed float reader',index='q from external table+163AC matching pointer+B3A8',
                 bound='-1 rejected; q semantics and upstream range not closed')],
        companion_capacity=[
            dict(kind='two D-relative metadata arrays',bases=['0x8d6c4','0x8d6d4'],stride=4,count=4,
                 initialize='142C867/142C879 all-ones first array;142C872/142C884 zero second array',
                 used_by=['142FED0','142FF90','1430450'],
                 collisions=['first array index4 begins second array','second array index4 begins state at8D6E4'],
                 adjacent_live_fields=['142BEF9 qword D+8D6E4','142BF0B dword D+8D6EC','142BF11 float D+8D6F0']),
            dict(kind='142D870 stack network-index to nonlocal-rank map',base='RBP-60',stride=4,count=4,
                 initialized_span=['RBP-60','RBP-50'],write='142EB7D [RBP+n*4-60]=rank',
                 guard='only n==selected local/current index is skipped; roster+84 controls enumeration count',
                 index4_collision='RBP-50, initialized to56D7E815 at142EB33 and consumed at142ED3B',
                 note='This conditional overwrite can occur before the later fixed-four record loop is expanded.'),
            dict(kind='three stack ID tables indexed by nonlocal rank',bases=['RBP-70','RBP-50','RBP-80'],stride=4,count=3,
                 initialization='142EB1E..142EB56',consumers=['142ED37','142ED3B','142ED3F'],
                 use='opaque IDs subsequently passed to lookups/calls; resource names and intended style are not proved',
                 extension='With one valid selected local index present among eight rows, need seven valid entries per table or a bounded fallback. If local index is missing/invalid, eight non-skipped ranks are possible: validate/reject that state or provide a bounded fallback; seven is not unconditionally safe.')],
        finite_eight_slot_worklist=[
            'Provide relocated eight-record storage (8*298=14C0 bytes) with five subobjects per record, preserving owner/pool relationships; existing extra four records would overlap proven initialized neighbors.',
            'Redirect the listed D-relative field and interior-subobject address formations consistently, including input-index readers/writers and paired14329B0 traversal.',
            'Change the listed initialization/cleanup/scans from4 to8, and14329B0 from2 paired iterations to4; this alone is insufficient.',
            'Relocate/resize both four-dword metadata arrays and update their initialization and the listed readers/writers; expanding in place collides with used fields.',
            'Resize/rehome the four-dword stack map in142D870, preserving stack frame/unwind/call alignment requirements; validate every network index before indexing.',
            'With a valid selected local index present among eight rows, provide seven valid rank-ID choices or a bounded fallback; missing/invalid local selection must be validated/rejected or safely bounded because eight non-skipped ranks are possible.',
            'Close the unexamined helper/callsite boundaries before claiming complete relocation or implementing a game patch.'],
        not_closed=[
            'This bounded set is not an exhaustive global consumer inventory or a complete alias audit.',
            '142EE70 has proven D but the semantic identity/range of external-table index q is unclosed.',
            'Generic interior-object helpers (including140C2E0,140C630,140C6A0,140D710,142F6E0), plus142FA60/1432F10, are call boundaries here, not fully audited relocation implementations.',
            'No same-offset match was promoted to same-object proof; candidates such as1433380/142F860 were not admitted without a proven D call path.',
            'Other manager callsites, runtime aliases, ID resource definitions and teardown timing are not exhaustively covered.',
            'The exact class/UI label of D remains unproved; parent Galaxy_map strings are context only.',
            'Normal CFG assumes standard Windows x64 nonvolatile-register preservation; exception/unwind execution is not modeled.',
            '142CB90 post-ret bytes142D831..142D864 are NOP padding plus a referenced RVA table; only its saved targets, not data bytes, participate in the normal CFG.',
            'No live reads, game execution, writes, patch, network session or eight-player success is established.'])
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),instructions=result['selected_instruction_count'],sha256=sha(out.read_bytes()))))


if __name__ == '__main__':
    main()
