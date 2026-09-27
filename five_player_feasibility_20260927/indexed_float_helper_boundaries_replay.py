"""Saved-image audit of two admitted D helpers and two unbound candidates.

No native execution or process access. The prior consumer evidence supplies the
same-D caller identity; this replay pins that artifact and the relevant windows.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row
from capstone import CS_GRP_JUMP
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

PRIOR_SHA = '503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578'
ROOTS = [0x142FA60, 0x1432F10, 0x142F860, 0x1433380]
WINDOWS = [(0x142FED0, 0x142FF47), (0x1430387, 0x14303D3),
           (0x1430690, 0x14306B8), (0x1431570, 0x143159E),
           (0x14319C3, 0x1431A03)]
PINS = {
    0x142FA60:'cmp edx, -1', 0x142FA71:'lea eax, [r8 - 1]',
    0x142FA75:'mov r15d, edx', 0x142FA7C:'mov rbx, rcx',
    0x142FA7F:'cmp eax, 0x16', 0x142FA82:'ja 0x142fe2f',
    0x142FA8D:'lea rdx, [rip - 0x142fa94]',
    0x142FA99:'mov ecx, dword ptr [rdx + rax*4 + 0x142fe6c]',
    0x142FAA0:'add rcx, rdx', 0x142FAA3:'jmp rcx',
    0x142FF31:'mov r8d, dword ptr [rbx + rdi*4 + 0x8d6d4]',
    0x142FF3C:'mov edx, r10d', 0x142FF3F:'mov rcx, rbx',
    0x142FF42:'call 0x142fa60', 0x14303B3:'mov dword ptr [rsi + rdi*4 + 0x8d6c4], r14d',
    0x14303BB:'mov r8d, r13d', 0x14303BE:'mov dword ptr [rsi + rdi*4 + 0x8d6d4], r13d',
    0x14303C6:'mov edx, r14d', 0x14303C9:'mov rcx, rsi',
    0x14303CC:'call 0x142fa60',
    0x1432F10:'mov qword ptr [rsp + 0x10], rdx',
    0x1432F1A:'cmp byte ptr [rcx + 0x8d709], 0',
    0x1432F21:'mov rbx, rcx',
    0x1432F2A:'movss xmm0, dword ptr [rsp + 0x38]',
    0x1432F58:'movss xmm0, dword ptr [rsp + 0x3c]',
    0x1432FC6:'subss xmm0, dword ptr [rbx + 0x24018]',
    0x1432FE6:'addss xmm0, dword ptr [rbx + 0x8d710]',
    0x1433005:'movss xmm0, dword ptr [rcx + 0x8d710]',
    0x143069D:'mov rdx, qword ptr [rbx - 0x89]',
    0x14306A4:'mov rcx, rsi', 0x14306A7:'call 0x1432f10',
    0x1431594:'mov rdx, qword ptr [rsp + 0x50]',
    0x1431599:'call 0x1432f10',
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--output', required=True)
    a=ap.parse_args(); output=Path(a.output)
    require(not output.exists(), 'refusing overwrite')
    prior=(HERE/'indexed_float_consumers_evidence.json').read_bytes()
    require(sha(prior)==PRIOR_SHA, 'prior consumer evidence changed')
    im=Image(a.evidence); cache={}

    def decode(f):
        if f not in cache:
            end=0x142FE6B if f[0]==0x142FE38 else f[1]
            ds=list(im.md.disasm(im.read(f[0],end-f[0]),f[0]))
            require(sum(i.size for i in ds)==end-f[0], 'incomplete decode')
            cache[f]={i.address:i for i in ds}
        return cache[f]

    def instruction(at):
        f=im.containing(at)
        require(f is not None and at in decode(f), 'unproven instruction boundary '+hex(at))
        return decode(f)[at]

    functions=[]; decoded={}
    for root in ROOTS:
        fs=[f for f in im.functions if im.root(f[0])[0]==root]
        require(fs and fs[0][0]==root, 'missing root')
        ds={k:v for f in fs for k,v in decode(f).items()}; decoded[root]=ds
        functions.append(dict(root=hex(root),same_D_admitted=root in [0x142FA60,0x1432F10],
            fragments=[dict(bounds=[hex(v) for v in f],
                sha256=sha(im.read(f[0],f[1]-f[0])),
                code_end_exclusive=hex(0x142FE6B if f[0]==0x142FE38 else f[1]),
                instructions=[row(i) for i in decode(f).values()]) for f in fs]))

    raw=im.read(0x142FE6B,0x142FEC8-0x142FE6B)
    require(raw[0]==0x90 and len(raw)==93, 'padding/table size')
    table=list(struct.unpack('<23I',raw[1:]))
    expected=[0x142FB77]+[0x142FE25]*4+[0x142FAA5,0x142FE25,0x142FAB9,0x142FE25,
              0x142FACD,0x142FAE1,0x142FE49,0x142FE49,0x142FE49,0x142FE38,
              0x142FE49,0x142FE49,0x142FE49,0x142FE38,0x142FE49,0x142FE49,0x142FE49,0x142FE38]
    require(table==expected and all(t in decoded[0x142FA60] for t in table), 'switch targets')
    edges={}; ds=decoded[0x142FA60]
    for at,i in ds.items():
        nxt=at+i.size
        if i.mnemonic=='ret':to=[]
        elif at==0x142FAA3:to=sorted(set(table))
        elif i.group(CS_GRP_JUMP):
            require(i.operands[0].type==X86_OP_IMM,'unexpected indirect jump')
            to=[i.operands[0].imm]+([] if i.mnemonic=='jmp' else [nxt])
        else:to=[nxt]
        require(all(t in ds for t in to),'normal CFG exits decoded body')
        edges[at]=to
    seen=set(); todo=[0x142FA60]
    while todo:
        at=todo.pop()
        if at in seen:continue
        seen.add(at);todo.extend(edges[at])
    require(seen==set(ds),'unreachable normal instructions')
    # Source reaches the one indirect table use with RDX=image base, and no
    # instruction between the LEA and load rewrites RDX.
    require(instruction(0x142FA8D).address+instruction(0x142FA8D).size+instruction(0x142FA8D).operands[1].mem.disp==0,'image base LEA')
    windows=[]
    for start,end in WINDOWS:
        fs=[f for f in im.functions if f[0]<end and start<f[1]]
        ins=[i for f in fs for at,i in decode(f).items() if start<=at<end]
        require(sum(i.size for i in ins)==end-start,'unaligned caller window')
        windows.append(dict(start=hex(start),end_exclusive=hex(end),root=hex(im.root(start)[0]),
                            sha256=sha(im.read(start,end-start)),instructions=[row(i) for i in ins]))
    for at,asm in PINS.items():
        i=instruction(at); require(i.mnemonic+' '+i.op_str==asm,'semantic pin changed '+hex(at))

    reg_audits=[]
    for root in [0x142FA60,0x1432F10]:
        writes=[]
        for i in decoded[root].values():
            _,wr=i.regs_access()
            if set(i.reg_name(r) for r in wr)&{'rbx','ebx','bx','bl','bh'}:writes.append(row(i))
        require([int(x['rva'],0) for x in writes]==([0x142FA7C,0x142FE36] if root==0x142FA60 else [0x1432F21,0x1432FF2,0x1433003,0x1433011]),'D register writes changed')
        reg_audits.append(dict(root=hex(root),register='RBX',writes=writes,assumption='Normal calls preserve Windows x64 nonvolatile RBX.'))

    scalar_refs=[]
    for i in decoded[0x1432F10].values():
        for o in i.operands:
            if o.type==X86_OP_MEM and i.reg_name(o.mem.base) in ('rbx','rcx'):
                scalar_refs.append(dict(instruction=row(i),base=i.reg_name(o.mem.base),index=i.reg_name(o.mem.index),disp=hex(o.mem.disp),size=o.size))
    require({int(v['disp'],0) for v in scalar_refs}=={0x8D709,0x24018,0x8D710},'D scalar reference set changed')
    require(all(v['index'] is None for v in scalar_refs),'unexpected D indexed read')

    calls={hex(r):[row(i) for i in ds.values() if i.mnemonic=='call'] for r,ds in decoded.items()}
    result=dict(schema_version=1,source_sha256=EXPECTED,capture_identity_sha256=im.report['capture_sha256'],
        prior_evidence_sha256=PRIOR_SHA,runtime_verified=False,functions=functions,caller_windows=windows,
        semantic_pins=[row(instruction(at)) for at in PINS],D_register_audits=reg_audits,
        selector_table=dict(start='0x142fe6c',count=23,padding_start='0x142fe6b',bytes=raw.hex(),sha256=sha(raw),
            selector_values=[dict(selector=n+1,target=hex(t)) for n,t in enumerate(table)],
            dispatch=[row(instruction(at)) for at in [0x142FA71,0x142FA7F,0x142FA82,0x142FA8D,0x142FA99,0x142FAA0,0x142FAA3]],
            normal_cfg_instructions=len(seen),edges={hex(k):[hex(t) for t in v] for k,v in edges.items()}),
        scalar_helper_D_references=scalar_refs,call_boundaries=calls,
        conclusions=[
            '142FA60 receives the admitted D and metadata-associated object ordinal/type. Its entry selector range1..23 is not a player capacity.',
            '142FA60 forms subobject pointers in other D ranges with stride180h or fixed addresses; no direct access to the relocated80E18h player-record array is present in its captured normal instructions.',
            '1432F10 receives an8-byte pair interpreted as two floats through its stack copy. Its D-relative reads are8D709h,24018h,8D710h; it has no direct per-player D array indexing.',
            'Keeping D and these non-record fields fixed avoids a record-base rewrite within these two helper bodies; caller record/metadata accesses still require redirection.',
        ],limits=[
            'This is not an audit of the external callees or all D consumers, and no game code is executed.',
            '142F860 and1433380 are stored only as unbound candidates. Unwind entry or matching offsets do not establish that their entry RCX is the admitted D in a live path.',
            'The prior consumer evidence supplies same-D identities and caller register provenance; it is hash-pinned, not recomputed here.',
            'Other caller contexts for1432F10 and external global-object services are not claimed safe for eight players.',
            'Additional0x180-stride families must retain their own object-ordinal bounds; none is presumed to take network index directly.',
        ])
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),sha256=sha(output.read_bytes()),normal_root_instructions=sum(len(v) for v in decoded.values()),admitted_helper_instructions=len(decoded[0x142FA60])+len(decoded[0x1432F10]),selector_cfg_instructions=len(seen))))


if __name__=='__main__':main()
