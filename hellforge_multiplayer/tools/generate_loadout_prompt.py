"""Relocate the saved native loadout action-prompt dispatch and two panels.

Peer/descriptor lookup and local readiness use the shared roster bank. Button
IDs, text resources and game-mode choices are not player capacities.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

GROUPS=((0x146b400,0x146b596),(0x146b5a0,0x146b704),(0x146b710,0x146b8e2),
        (0x60b3b0,0x60b456),(0x60b460,0x60b507))
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_prompt_template.h'


def build():
    capture=Capture();blob=bytearray();fixes=[];branches=[];mapping={};ends={};rows=[];entries=[];sources=[]
    def fix(raw,offset,key,kind=1,add=0):
        at=len(blob);blob.extend(raw);fixes.append((at+offset,len(blob),key,kind,add))
    def absolute(reg,key,add=0):fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,1,add)
    def capacity(raw):fix(raw+bytes(4),len(raw),5,2)
    def reject(op=b'\x0f\x83'):fix(op+bytes(4),len(op),6,0)
    def branch(op,target):
        at=len(blob);blob.extend(op+bytes(4));branches.append((at+len(op),len(blob),target))
    for start,end in GROUPS:
        fragments=[f for f in capture.functions if start<=f[0]<end]
        query=start in (0x60b3b0,0x60b460)
        need(len(fragments)=={0x146b400:5,0x146b5a0:3,0x146b710:1,0x60b3b0:1,0x60b460:1}[start] and
             fragments[-1][1]==end and all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),
             'Changed prompt fragments')
        blob.extend(b'\xcc'*(-len(blob)%16));entry=len(blob);entries.append(entry)
        if not query or start==0x60b3b0:
            absolute(11,9 if query else 2);blob.extend(b'\x4c\x39\xd9');reject(b'\x0f\x85')
        absolute(11,9);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326468);reject(b'\x0f\x85')
        blob.extend(bytes.fromhex('458b9384000000'));capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
        blob.extend(bytes.fromhex('45399388000000'));reject(b'\x0f\x87')
        # Leaf queries include their guards in one runtime-function prologue.
        # Before any saves, unwind has nothing to undo.
        body=len(blob)
        if not query:rows.append((entry,body,b'\x01\0\0\0',None))
        first_row=len(rows)
        source=capture.read(start,end-start);sources.append(dict(start=start,end=end,data=source))
        insns=list(capture.md.disasm(source,start));need(insns[-1].address+insns[-1].size==end,'Incomplete prompt decode')
        for ins in insns:
            a=ins.address;at=len(blob);mapping[a]=at;text=ins.mnemonic+' '+ins.op_str
            mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
            if a in (0x146b4ff,0x146b66d):
                need(text=='lea rcx, [rsi + 0x2c8]','Changed prompt peer scan');absolute(1,10,0x3c0)
            elif a in (0x146b539,0x146b6a7):
                need(text=='mov rcx, qword ptr [rsi + rax*8 + 0xe8]','Changed prompt descriptor lookup')
                capacity(b'\x3d');reject();absolute(11,10);blob.extend(b'\x49\x8b\x0c\xc3')
            elif a==0x146b862:
                need(text=='mov eax, dword ptr [rax + 0x3ac]','Changed prompt local flags')
                absolute(11,10,0x584);blob.extend(b'\x41\x8b\x03')
            elif a in (0x60b444,0x60b4f4):
                need(text=='shl rax, 5','Changed flag row stride')
                capacity(b'\x3d');reject()
                blob.extend(b'\x41\x3b\x82\x84\0\0\0');reject();blob.extend(ins.bytes)
            elif a in (0x60b448,0x60b4f8):
                need(text=='mov eax, dword ptr [rax + r10 + 0x3ac]','Changed indexed flags')
                absolute(11,10,0x584);blob.extend(b'\x41\x8b\x04\x03')
            elif (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                raw=bytes(ins.bytes);target=ins.operands[0].imm
                op=raw[:1] if raw[0] in (0xe8,0xe9) else b'\xe9' if raw[0]==0xeb else bytes((0x0f,raw[0]+0x10)) if 0x70<=raw[0]<=0x7f else raw[:2]
                if target in [b for b,e in GROUPS]:branch(op,('entry',target))
                elif any(b<=target<e for b,e in GROUPS):branch(op,target)
                else:fix(op+bytes(4),len(op),0,0,target)
            else:
                blob.extend(ins.bytes)
                if mem and mem.base==X86_REG_RIP:fixes.append((at+ins.disp_offset,len(blob),0,0,a+ins.size+ins.disp))
            if a in (0x146b4f5,0x146b663):
                capacity(b'\x81\xfa');reject(b'\x0f\x87') # refreshed count after native panel callbacks
            ends[a+ins.size]=len(blob)
        for b,e,u in fragments:
            head=capture.read(u,4);need(head[0] in (1,33) and head[3]==0,'Unexpected prompt unwind')
            n=4+((head[2]+1)&~1)*2;uw=bytearray(capture.read(u,n));parent=None
            begin=entry if query else mapping[b]
            def offset(old):return ends[b+old]-begin if old else 0
            uw[1]=offset(head[1]);i=0
            while i<head[2]:
                uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                need(op in (0,1,2,4,8),'Unexpected prompt unwind operation');i+=2 if op in (1,4,8) else 1
            if head[0]==33:
                old=struct.unpack('<III',capture.read(u+n,12));need(old in fragments[:fragments.index((b,e,u))],'Foreign prompt chain')
                parent=first_row+fragments.index(old)
            rows.append((begin,ends[e],bytes(uw),parent))
    for at,nxt,target in branches:
        if isinstance(target,tuple):target=entries[[b for b,e in GROUPS].index(target[1])]
        else:need(target in mapping,'Missing prompt branch');target=mapping[target]
        fixes.append((at,nxt,1,0,target))
    code_bytes=len(blob);blob.extend(bytes(-len(blob)%4));unwind_offset=len(blob);functions=[]
    for b,e,uw,parent in rows:
        functions.append((b,e,len(blob)));blob.extend(uw)
        if parent is not None:blob.extend(struct.pack('<III',*functions[parent]))
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE and len(functions)==14,'Prompt image bounds')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,functions=functions,entries=entries,sources=sources,mapping=mapping)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_prompt.py.',
           'static const uint8_t ep_loadout_prompt_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutPromptFixup ep_loadout_prompt_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset'):
        lines.append(f'static const uint32_t ep_loadout_prompt_{key} = {a[key]};')
    lines.append(f'static const uint32_t ep_loadout_prompt_functions = {len(a["functions"])};')
    lines.append('static const uint32_t ep_loadout_prompt_entries[] = {'+','.join(map(str,a['entries']))+'};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
