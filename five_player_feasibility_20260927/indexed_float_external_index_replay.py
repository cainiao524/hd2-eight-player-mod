"""Offline closure of142EE70's external index: owner, confirmed peers and host key.

Reads only the fixed saved capture and pinned prior evidence. No process, probe,
network, launch or game-modification APIs. Bounded producer set, not an inventory.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'research_handoff_20260927'/'indirect'))
from inspect_capture import Image, EXPECTED, require, row
from capstone import CS_GRP_JUMP, CS_AC_WRITE
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_REG_RIP, X86_REG_RSP, X86_REG_RBP

PRIOR='503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578'
ROOTS={0x142EE70:0x142F528,0x134D740:0x134E15C,0xB2ABD0:0xB2AFAE,
       0xB2AFB0:0xB2B180,0xB90B20:0xB90EAB,0x1088A30:0x1088D75,
       0x1089720:0x108A34A,0x13500F0:0x135014B,0xBABA80:0xBABAB9,
       0x108C760:0x108CD7C,0xBE4910:0xBE49D2,0x108BC70:0x108C5D7}
CODE_ENDS={0x134D740:0x134E144,0x1089720:0x108A325}
PINS=[0x142D8B6,0x142D8B9,0xB91581,0xB91596,0xB9159D,
      0x10849ED,0x10849F4,0x10849F7,0x1084A28,0x1087251,0x1087260,0x1087298]

def sha(b):return hashlib.sha256(b).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence',required=True);ap.add_argument('--output',required=True)
    args=ap.parse_args();out=Path(args.output)
    require(not out.exists(),'refusing overwrite')
    prior_raw=(HERE/'indexed_float_consumers_evidence.json').read_bytes()
    require(sha(prior_raw)==PRIOR,'prior D evidence changed')
    im=Image(args.evidence);prior=json.loads(prior_raw)
    require(prior['capture_identity_sha256']==im.report['capture_sha256'],'different capture')
    spans,roots,decoded,tails={},{},{},[]
    for entry,end in ROOTS.items():
        fs=[f for f in im.functions if entry<=f[0]<end and im.root(f[0])[0]==entry]
        require(fs and fs[0][0]==entry and fs[-1][1]==end,'root bounds '+hex(entry))
        require(all(a[1]==b[0] for a,b in zip(fs,fs[1:])),'root gaps')
        code_end=CODE_ENDS.get(entry,end);roots[entry]=[]
        for f in fs:
            b=min(code_end,f[1]);raw=im.read(f[0],b-f[0])
            ins=list(im.md.disasm(raw,f[0]))
            require(sum(i.size for i in ins)==len(raw),'incomplete decode '+hex(f[0]))
            for i in ins:
                v=im.instruction(i.address)
                require(v is not None and v.bytes==i.bytes,'unwind instruction boundary '+hex(i.address))
            decoded.update({i.address:i for i in ins});roots[entry]+=ins
            spans[hex(f[0])]=dict(start=hex(f[0]),end_exclusive=hex(b),sha256=sha(raw),root=hex(entry),
                unwind_fragment=[hex(x) for x in f],instructions=[row(i) for i in ins])
        if code_end<end:
            raw=im.read(code_end,end-code_end)
            tails.append(dict(root=hex(entry),start=hex(code_end),end_exclusive=hex(end),bytes=raw.hex(),sha256=sha(raw)))
    pins=[]
    for at in PINS:
        i=im.instruction(at);require(i is not None,'pin boundary '+hex(at))
        decoded[at]=i;pins.append(dict(**row(i),root=hex(im.root(at)[0])))

    # Both tables have real in-body dispatch references; their bytes are not code.
    ctor_table=[int.from_bytes(im.read(0x134E144+n*4,4),'little') for n in range(6)]
    migrate_table=[int.from_bytes(im.read(0x108A328+n*4,4),'little') for n in range(3)]
    migrate_select=list(im.read(0x108A334,22))
    require(all(v<3 for v in migrate_select),'migration byte selector range')
    require(im.read(0x108A325,3)==bytes.fromhex('0f1f00'),'migration post-ret nop')
    indirect={0x134D98B:set(ctor_table),0x1089B69:set(migrate_table[v] for v in migrate_select)}
    cfg={};cfg_summaries=[]
    for entry,ins in roots.items():
        by={i.address:i for i in ins};edges={};exits=[]
        for at,i in by.items():
            targets=[]
            if i.group(CS_GRP_JUMP):
                if i.operands[0].type==X86_OP_IMM:targets=[i.operands[0].imm]
                else:
                    require(at in indirect,'unhandled indirect jump '+hex(at));targets=sorted(indirect[at])
                if i.mnemonic!='jmp':targets.append(at+i.size)
            elif i.mnemonic not in ('ret','int3','ud2'):targets=[at+i.size]
            edges[at]=[]
            for t in targets:
                if t in by:edges[at].append(t)
                else:
                    require(i.mnemonic=='jmp' and i.operands[0].type==X86_OP_IMM,'unexpected CFG target '+hex(t))
                    exits.append(dict(at=hex(at),target=hex(t),kind='external tail jump'))
        seen=set();pending=[entry]
        while pending:
            at=pending.pop()
            if at in seen:continue
            seen.add(at);pending+=edges[at]
        cfg[entry]=(by,edges)
        cfg_summaries.append(dict(root=hex(entry),instructions=len(ins),normal_reachable=len(seen),
            unreachable_instruction_rvas=[hex(x) for x in sorted(set(by)-seen)],external_tail_jumps=exits,
            indirect_dispatches={hex(a):[hex(t) for t in sorted(indirect[a])] for a in by if a in indirect}))

    semantic=[
        (0x142EF10,'mov','edx, dword ptr [r9 + 0x16390]'),
        (0x142EF17,'mov','r8, qword ptr [r9 + 0xb3a8]'),
        (0x142EF26,'lea','rcx, [r9 + 0x16398]'),(0x142EF30,'cmp','qword ptr [rcx], r8'),
        (0x142EF33,'je','0x142ef44'),(0x142EF37,'add','rcx, 0x20'),
        (0x142EF3B,'cmp','eax, edx'),(0x142EF3D,'jb','0x142ef30'),
        (0x142EF44,'shl','rax, 5'),(0x142EF48,'mov','ecx, dword ptr [rax + r9 + 0x163ac]'),
        (0x142EF50,'cmp','ecx, -1'),(0x142EF53,'je','0x142f0f8'),
        (0x142EF78,'imul','rcx, rcx, 0x298'),
        (0x142EF8E,'movss','xmm7, dword ptr [rcx + rdi + 0x80e24]'),
        (0x142EF9E,'movss','xmm8, dword ptr [rcx + rdi + 0x80e28]'),
        (0x134DC9E,'lea','r9, [rsi + 0x159b0]'),(0x134DCA8,'mov','qword ptr [r9], rsi'),
        (0x134DD07,'lea','r8, [rsi + 0x162c8]'),(0x134DD0E,'mov','rcx, r8'),
        (0x134DD11,'call','0xb2abd0'),(0x134DD28,'mov','qword ptr [r8], rsi'),
        (0x134DD41,'mov','dword ptr [r8 + 0xc8], edi'),
        (0x134DD65,'mov','qword ptr [r8 + 0x150], rcx'),
        (0xB2ABD4,'mov','qword ptr [rsp], rcx'),(0xB2ABDF,'mov','dword ptr [rsp + 8], 0xeb'),
        (0xB2ACEA,'mov','eax, dword ptr [rcx + 0x6438]'),(0xB2ACF6,'add','rax, 0x644'),
        (0xB2ACFC,'add','rax, rax'),(0xB2ACFF,'movups','xmmword ptr [rcx + rax*8], xmm0'),
        (0xB90B6C,'cmp','dword ptr [r14 + rax*8 + 8], 0xeb'),
        (0xB90B7B,'mov','rbx, qword ptr [r14 + rax*8]'),
        (0xB90B82,'cmp','r15, qword ptr [rax + 0xb3a8]'),
        (0xB90BE3,'mov','ecx, dword ptr [rbx + 0xc8]'),(0xB90BF2,'shl','rdx, 5'),
        (0xB90BF6,'add','rdx, 0xd0'),(0xB90BFD,'add','rdx, rbx'),
        (0xB90C03,'mov','dword ptr [rbx + 0xc8], eax'),
        (0xB90C0B,'mov','eax, dword ptr [rsp + 0xd0]'),(0xB90C12,'mov','dword ptr [rdx + 0x14], eax'),
        (0xBABAA5,'mov','eax, dword ptr [r10]'),(0xBABAAB,'mov','dword ptr [rsp + 0x20], eax'),
        (0xBABAAF,'call','0xb90b20'),
        (0x1088B27,'mov','dword ptr [rdi + 0x34], ebx'),
        (0x1088B63,'mov','dword ptr [rax + 0x16390], 1'),
        (0x1088B77,'mov','qword ptr [rcx + 0x16398], rax'),
        (0x1088B7E,'mov','eax, dword ptr [rdi + 0x34]'),
        (0x1088B84,'mov','dword ptr [rcx + 0x163ac], eax'),
        (0x1350100,'mov','qword ptr [rcx + 0xb3a8], rax'),
        (0x1089BF5,'mov','r12, qword ptr [rax + 0xb398]'),
        (0x1089720,'mov','qword ptr [rsp + 8], rcx'),
        (0x1089731,'lea','rbp, [rsp - 0x1f]'),
        (0x1089736,'sub','rsp, 0x98'),
        (0x1089B2C,'mov','r13, qword ptr [rbp + 0x67]'),
        (0x1089C44,'mov','qword ptr [r8 + 0xb3a8], r12'),
        (0x1089E97,'mov','eax, dword ptr [rdx + r8 + 0x163ac]'),
        (0x1089E9F,'mov','dword ptr [rdi + 0x14], eax'),
        (0x1089EAB,'mov','byte ptr [rax + r13 + 0x100], 1'),
        (0xB91596,'add','rcx, 0x159b0'),(0xB9159D,'call','0x1089720'),
        (0x108C3E2,'cmp','ecx, 4'),(0x108C3E5,'jb','0x108c3d8'),
        (0x108C3EB,'mov','r8d, ecx'),(0x108C3FB,'mov','dword ptr [rdx + 0x14], r8d'),
        (0x108C91C,'mov','eax, dword ptr [rdi - 0xc]'),(0x108C91F,'mov','dword ptr [rsp + 0x20], eax'),
        (0x108C923,'call','0xbe4910'),(0x108C934,'mov','edx, dword ptr [r15 + r14 + 0x34]'),
        (0x108C959,'mov','dword ptr [rsp + 0x20], edx'),(0x108C960,'call','0xb90b20'),
        (0x108C974,'mov','dword ptr [rsp + 0x20], edx'),(0x108C97B,'call','0xbe4910'),
        (0x134D980,'mov','ecx, dword ptr [r10 + rax*4 + 0x134e144]'),
        (0x134D988,'add','rcx, r10'),(0x134D98B,'jmp','rcx'),
        (0x1089B57,'movzx','eax, byte ptr [rsi + rax + 0x108a334]'),
        (0x1089B5F,'mov','ecx, dword ptr [rsi + rax*4 + 0x108a328]'),
        (0x1089B66,'add','rcx, rsi'),(0x1089B69,'jmp','rcx'),
    ]
    for at,mn,op in semantic:
        require(at in decoded and (decoded[at].mnemonic,decoded[at].op_str)==(mn,op),'semantic '+hex(at))

    globals_=[]
    for at,target in [(0x142EED8,0x347CEF0),(0x134D754,0x347CEF0),
                      (0xB91581,0x347CEF0),(0x1089D94,0x347CEF0),
                      (0xB2ABD8,0x3326E68),(0xB90B37,0x3326E68)]:
        i=decoded[at];refs=[i.address+i.size+o.mem.disp for o in i.operands if o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP]
        require(refs==[target],'global identity '+hex(at))
        globals_.append(dict(instruction=row(i),target=hex(target)))

    def reaching(root,aliases):
        by,edges=cfg[root];incoming={root:{-1}};pending=[root]
        while pending:
            at=pending.pop();i=by[at]
            outgoing={at} if any(im.md.reg_name(r) in aliases for r in i.regs_access()[1]) else incoming[at]
            for t in edges[at]:
                joined=incoming.get(t,set())|outgoing
                if joined!=incoming.get(t,set()):incoming[t]=joined;pending.append(t)
        return incoming
    rd=[]
    for root,aliases,at,expected in [
        (0x142EE70,('r9','r9d','r9w','r9b'),0x142EF48,[0x142EED8]),
        (0x142EE70,('rdi','edi','di','dil'),0x142EF8E,[0x142EEE8]),
        (0x142EE70,('rcx','ecx','cx','cl','ch'),0x142EF78,[0x142EF48]),
        (0x134D740,('rsi','esi','si','sil'),0x134DD07,[0x134D754]),
        (0x134D740,('rsi','esi','si','sil'),0x134DCA8,[0x134D754]),
        (0x134D740,('rdi','edi','di','dil'),0x134DD41,[0x134D75B]),
        (0x134D740,('r10','r10d','r10w','r10b'),0x134D980,[0x134D979]),
        (0xB90B20,('rax','eax','ax','al','ah'),0xB90C12,[0xB90C0B]),
        (0x1088A30,('rbx','ebx','bx','bl','bh'),0x1088B27,[0x1088A78]),
        (0x1089720,('r12','r12d','r12w','r12b'),0x1089C44,[0x1089BF5]),
        (0x1089720,('r13','r13d','r13w','r13b'),0x1089C30,[0x108973D,0x1089B2C]),
        (0x1089720,('rsi','esi','si','sil'),0x1089B57,[0x1089B40]),
        (0x108BC70,('r14','r14d','r14w','r14b'),0x108C3C0,[0x108BD0B]),
        (0x108C760,('r14','r14d','r14w','r14b'),0x108C934,[0x108C78E]),
    ]:
        incoming=reaching(root,aliases);require(incoming[at]==set(expected),'reaching defs '+hex(at)+' actual '+str([hex(x) for x in sorted(incoming[at])]))
        rd.append(dict(root=hex(root),at=hex(at),aliases=aliases,definitions=[row(decoded[x]) for x in expected]))
    # Explicitly check the actual registration helper preserves the volatile R8
    # used by the constructor after the call; do not assume that from the ABI.
    r8writes=[i for i in roots[0xB2ABD0] if any(im.md.reg_name(r) in ('r8','r8d','r8w','r8b') for r in i.regs_access()[1])]
    require(not r8writes and not any(i.mnemonic=='call' for i in roots[0xB2ABD0]),'registration does not preserve R8')
    for at in [0x134D979,0x1089B40]:
        i=decoded[at];refs=[i.address+i.size+o.mem.disp for o in i.operands if o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP]
        require(i.mnemonic=='lea' and refs==[0],'switch table image base')
    # After8 pushes and SUB98, RBP=currentRSP+79. The entry [RSP+8]
    # save is therefore [RBP+67]=[currentRSP+E0]. Audit explicit fixed writes
    # before the restoring load, accounting for both stack-base spellings.
    saved_host_overwrites=[]
    for i in roots[0x1089720]:
        if not 0x108973D<=i.address<0x1089B2C:continue
        for o in i.operands:
            if o.type!=X86_OP_MEM or not(o.access & CS_AC_WRITE):continue
            if o.mem.base not in (X86_REG_RBP,X86_REG_RSP) or o.mem.index:continue
            off=o.mem.disp+(0x79 if o.mem.base==X86_REG_RBP else 0)
            if off<0xE8 and off+o.size>0xE0:saved_host_overwrites.append(row(i))
    require(not saved_host_overwrites,'saved host argument overwritten before restore')
    q_by,q_edges=cfg[0x142EE70]
    cuts=[]
    for forbidden in [(0x142EF33,0x142EF44),(0x142EF53,0x142EF59)]:
        seen=set();pending=[0x142EE70]
        while pending:
            at=pending.pop()
            if at in seen:continue
            seen.add(at);pending += [t for t in q_edges[at] if (at,t)!=forbidden]
        require(0x142EF8E not in seen and 0x142EF9E not in seen,'q access gate not necessary')
        cuts.append(dict(removed_edge=[hex(x) for x in forbidden],float_reads_unreachable=True))

    strings=[]
    for at,text in [(0x2263468,b'start_hosting\0'),(0x2263478,b'HostSynchronizer\0'),
                    (0x22634A0,b'start_host_migration\0'),(0x22C7E70,b'is_host\0'),
                    (0x2262B00,b'ClientSynchronizer\0'),(0x22631E8,b'Added confirmed peer at %u [%llx]\0')]:
        raw=im.read(at,len(text));require(raw==text,'name bytes changed')
        strings.append(dict(rva=hex(at),bytes=raw.hex(),sha256=sha(raw),text=raw[:-1].decode()))
    require(0x162C8+0xC8==0x16390 and 0x162C8+0xD0==0x16398 and 0x162C8+0xE4==0x163AC,'client identity arithmetic')
    require(0xD0+4*0x20==0x150,'client neighbor overlap')
    result=dict(schema_version=1,source_sha256=EXPECTED,capture_identity_sha256=im.report['capture_sha256'],
        prior_D_consumer_sha256=PRIOR,runtime_verified=False,
        scope='Only142EE70 external index and selected constructor/host/confirmed-peer producers',
        code_spans=spans,pins=pins,semantic_pins=[row(decoded[x[0]]) for x in semantic],
        selected_instruction_count=sum(len(v['instructions']) for v in spans.values())+len(pins),
        code_data_tails=tails,jump_tables=dict(constructor=[hex(x) for x in ctor_table],
            migration_rvas=[hex(x) for x in migrate_table],migration_selector=migrate_select),
        normal_cfg=cfg_summaries,reaching_definitions=rd,necessary_q_access_edges=cuts,
        migration_saved_host_argument=dict(entry_save=row(decoded[0x1089720]),restore=row(decoded[0x1089B2C]),
            normal_frame='RBP=currentRSP+79; entryRSP+8 = RBP+67 = currentRSP+E0',
            fixed_stack_overwrites_before_restore=saved_host_overwrites,
            limitation='Explicit fixed RBP/RSP writes in the selected normal body; no runtime alias observation'),
        global_proofs=globals_,readonly_strings=strings,
        identity=dict(owner='O = qword[global347CEF0]',client='C=O+162C8',host='H=O+159B0',
            owner_backpointers='[C]=[H]=O',confirmed_count='C+C8 = O+16390',
            peer_id='C+D0+p*20 = O+16398+p*20',network_index='C+E4+p*20 = O+163AC+p*20',
            registry='constructor registers C under tagEB in global3326E68 +6440, count+6438; B90B20 selects that same table/tag'),
        q_semantics=dict(key='64-bit O+B3A8',search='confirmed-peer ID match; p is the matching record ordinal',
            value='q = zero-extended32-bit confirmed record+14 network/player index; q is not p',
            local_comparison='O+B398 is the local peer identifier used by the separate local-index getter; +B3A8 is the host-selection key, not automatically local',
            host_context='Global-proven migration callerB91581/96/9D passesO+159B0; its method setsO+B3A8 fromO+B398 and emits is_host. Receiver checks sender againstO+B3A8 or override byteC+51A. Separate13500F0 has the same owner-shaped setter and tail-calls start_hosting, but its own caller identity is not newly closed here.',
            missing='count zero/no key match/q==FFFFFFFF all bypass the two selected D float reads',
            numeric_gate='No q<4, mask3, clamp or narrower store between matched q load and q*298 addressing',
            read_addresses=['D+80E24+q*298','D+80E28+q*298']),
        selected_producers=[
            dict(root='134D740',kind='constructor',effect='C+C8=0; C+150 is independently initialized live storage'),
            dict(root='1088A30',kind='new host initialization',effect='confirmed count1, first peer local O+B398, first index fromH+34=0'),
            dict(root='B90B20',kind='confirmed-peer append',effect='fifth call argument copied as32-bit record+14; count-based append with no capacity/index normalization before store',
                 actual_callers=['108C960 direct local branch','BABAAF decoded-field wrapper'],
                 unclosed='event-hash to receive-wrapper runtime binding and upstream decoder constraints are not established'),
            dict(root='108BC70',kind='existing host allocator',effect='four flag scan allocates0..3 or leavesFFFFFFFF; eight valid indices require coordinated host change'),
            dict(root='108C760',kind='host notification',effect='member index DWORD goes to directB90B20 or BE4910 five-field sender; selected sender wrapper uses4-byte descriptor'),
            dict(root='1089720',kind='host migration',effect='sets host key+B3A8 to local peer, copies existing confirmed network indices into host records, marks index flags without renumbering to0',
                 limit='migration retains other four-slot host storage constraints; not itself proof that current code can migrate eight players')],
        eight_slot_implications=[
            'q source identity is closed: it is a confirmed-peer network/player index keyed by the host-selection peer. It cannot be replaced with record ordinal p or assumed always0.',
            'Relocating client confirmed records requires changing this inline owner-relative count/table/index lookup, not only C-relative methods.',
            'Relocating D records requires redirecting both142EF8E/142EF9E reads; scalar32-bit width and298 multiplication already represent4..7, so there is no extra fixed-four q comparison to increase here.',
            'Preserve no-match/FFFFFFFF behavior and establish a validated0..7 index invariant (or explicit bounds) before dereference; raw32-bit append does not enforce it.',
            'Client four-record allocation/clear ranges and host allocator/migration index flags must be expanded consistently; fifth client record begins at the liveC+150 field.',
            'O+B3A8 is one peer-ID key, not a four-slot array; this evidence requires preserving its meaning, not widening it for eight players.'],
        limits=[
            'Saved code identity only: writable globals, current heap contents, current host/local IDs and executed values are not observed.',
            'The B90B20 tag table is the same registry constructor route; other registered objects or dynamic replacement are not excluded.',
            'Only the selected producer paths are closed. Full protocol decoder, event registry, all identity setters and all relocation aliases are outside this bounded trace.',
            '13500F0 is saved as an owner-shaped entry/call pairing, not independent proof that every caller supplies the global owner. The migration key writer has the explicit global-derived caller proof.',
            'Physical confirmed storage capacity4 is distinct from the received index value. A peer record ordinal below4 can contain q4 or q7 if supplied; no runtime arrival is claimed.',
            'Direct or nested calls may have effects not modeled by normal CFG. Nonvolatile-register preservation follows Windows x64; volatileR8 across the constructor helper was separately checked.',
            'No live process query, probe, capture, game execution, patch or multiplayer validation.'])
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),instructions=result['selected_instruction_count'],sha256=sha(out.read_bytes()))))

if __name__=='__main__':main()
