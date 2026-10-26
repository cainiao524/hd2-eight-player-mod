"""Relocate saved loadout mode switch and its open wrapper; no game access.

Network/UI slots and widget loops use shared storage/capacity. Event argument
type 4 at 1471820 remains four; EDI becomes capacity only at the widget loop.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need,GS_HANDLER
from generate_loadout_consumers import REG
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

GROUPS=((0x1470d90,0x1471918),(0x146f510,0x146f568))
UNWIND=bytes.fromhex('19230700150126000af008c00660053004500000')
COOKIE=0xd0
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_mode_template.h'


def build():
    capture=Capture();blob=bytearray();fixes=[];branches=[];mapping={};ends={};rows=[];entries=[];sources=[]
    def fix(raw,offset,key,kind=1,add=0):
        at=len(blob);blob.extend(raw);fixes.append((at+offset,len(blob),key,kind,add))
    def absolute(reg,key,add=0,kind=1):fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,kind,add)
    def capacity(raw):fix(raw+bytes(4),len(raw),5,2)
    def reject(op=b'\x0f\x83'):fix(op+bytes(4),len(op),6,0)
    def branch(op,target):
        at=len(blob);blob.extend(op+bytes(4));branches.append((at+len(op),len(blob),target))
    def widget(ins):
        mem=next(o.mem for o in ins.operands if o.type==X86_OP_MEM);base=REG[ins.reg_name(mem.base)]
        need(base in (1,3,6,7),'Unexpected mode widget base')
        # R11's prologue and hash-table uses end before every relocated field.
        # Preserve flags and original scaled/base registers with MOV/LEA.
        absolute(11,4,-0x53a78,3);blob.extend(bytes((0x4d,0x8d,0x1c,(base<<3)|3)))
        raw=bytearray(ins.bytes);m=ins.modrm_offset
        if raw[m]&7==4:raw[m+1]=(raw[m+1]&0xf8)|3
        else:raw[m]=(raw[m]&0xf8)|3
        p=0
        while raw[p] in (0x66,0xf2,0xf3,0x2e,0x3e,0x64,0x65):p+=1
        if 0x40<=raw[p]<=0x4f:raw[p]|=1
        else:raw[p:p]=b'\x41'
        blob.extend(raw)
    for start,end in GROUPS:
        fragments=[f for f in capture.functions if start<=f[0]<end]
        need(len(fragments)==(4 if start==GROUPS[0][0] else 1) and fragments[-1][1]==end and
             all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),'Changed mode fragments')
        blob.extend(b'\xcc'*(-len(blob)%16));entry=len(blob);entries.append(entry)
        absolute(11,2);blob.extend(b'\x4c\x39\xd9');reject(b'\x0f\x85')
        absolute(11,9);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326468);reject(b'\x0f\x85')
        blob.extend(bytes.fromhex('458b9384000000'));capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
        blob.extend(bytes.fromhex('45399388000000'));reject(b'\x0f\x87')
        body=len(blob);rows.append((entry,body,b'\x01\0\0\0',None));first_row=len(rows)
        source=capture.read(start,end-start);sources.append(dict(start=start,end=end,data=source))
        insns=list(capture.md.disasm(source,start));need(insns[-1].address+insns[-1].size==end,'Incomplete mode decode')
        for ins in insns:
            a=ins.address;at=len(blob);mapping[a]=at;text=ins.mnemonic+' '+ins.op_str
            mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
            if a in (0x1471134,0x14711f1,0x14714bc):
                expected,prefix={0x1471134:('cmp r15d, 4',b'\x41\x81\xff'),0x14711f1:('cmp r12d, 4',b'\x41\x81\xfc'),0x14714bc:('cmp r14d, 4',b'\x41\x81\xfe')}[a]
                need(text==expected,'Changed mode player bound');capacity(prefix)
            elif a==0x14716b6:
                need(text=='mov ecx, dword ptr [rsi + rax*4 + 0x27d8]','Changed mode forward map')
                capacity(b'\x3d');reject();absolute(11,7);blob.extend(b'\x41\x8b\x0c\x83')
            elif a==0x14716c6:
                need(text=='imul rbx, rcx, 0x1ee18','Changed mapped local widget')
                capacity(b'\x81\xf9');reject();absolute(11,8);blob.extend(b'\x41\x39\x04\x8b');reject(b'\x0f\x85');blob.extend(ins.bytes)
            elif a==0x1471798:
                need(text=='mov rax, qword ptr [rcx + 0xe8]','Changed mode local descriptor');absolute(0,10);blob.extend(b'\x48\x8b\x00')
            elif mem and 0x53a78<=mem.disp<0x72890 and ins.reg_name(mem.base) in ('rsi','rdi','rbx','rcx'):
                if a==0x1471848:capacity(b'\xbf') # Do not widen event type EDI at 1471820.
                widget(ins)
            elif (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                raw=bytes(ins.bytes);target=ins.operands[0].imm
                op=raw[:1] if raw[0] in (0xe8,0xe9) else b'\xe9' if raw[0]==0xeb else bytes((0x0f,raw[0]+0x10)) if 0x70<=raw[0]<=0x7f else raw[:2]
                if any(b<=target<e for b,e in GROUPS):branch(op,('entry',target) if ins.mnemonic=='call' else target)
                else:fix(op+bytes(4),len(op),0,0,target)
            else:
                blob.extend(ins.bytes)
                if mem and mem.base==X86_REG_RIP:fixes.append((at+ins.disp_offset,len(blob),0,0,a+ins.size+ins.disp))
            ends[a+ins.size]=len(blob)
            if start==GROUPS[0][0] and a<start+UNWIND[1]:need(blob[at:]==ins.bytes and at-body==a-start,'Mode GS prologue moved')
        for b,e,u in fragments:
            head=capture.read(u,4);n=4+((head[2]+1)&~1)*2;uw=bytearray(capture.read(u,n));parent=None
            if b==GROUPS[0][0]:
                need(capture.read(u,n+8)==UNWIND+struct.pack('<II',GS_HANDLER,COOKIE),'Changed mode GS contract');uw+=bytes(8);parent='gs'
            else:
                need(head[0] in (1,33) and head[3]==0,'Unexpected mode unwind')
                def offset(old):return ends[b+old]-mapping[b] if old else 0
                uw[1]=offset(head[1]);i=0
                while i<head[2]:
                    uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                    need(op in (0,1,2,4,8),'Unexpected mode unwind operation');i+=2 if op in (1,4,8) else 1
                if head[0]==33:
                    old=struct.unpack('<III',capture.read(u+n,12));need(old in fragments[:fragments.index((b,e,u))],'Foreign mode chain')
                    parent=first_row+fragments.index(old)
            rows.append((mapping[b],ends[e],bytes(uw),parent))
    for at,nxt,target in branches:
        if isinstance(target,tuple):target=entries[[b for b,e in GROUPS].index(target[1])]
        else:need(target in mapping,'Missing mode branch');target=mapping[target]
        fixes.append((at,nxt,1,0,target))
    blob.extend(b'\xcc'*(-len(blob)%16));handler_offset=len(blob);fix(b'\xe9'+bytes(4),1,0,0,GS_HANDLER)
    code_bytes=len(blob);rows.append((handler_offset,code_bytes,b'\x01\0\0\0',None));blob.extend(bytes(-len(blob)%4))
    unwind_offset=len(blob);functions=[]
    for b,e,uw,parent in rows:
        functions.append((b,e,len(blob)))
        if parent=='gs':blob.extend(uw[:-8]+struct.pack('<II',handler_offset,COOKIE))
        else:
            blob.extend(uw)
            if parent is not None:blob.extend(struct.pack('<III',*functions[parent]))
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE and len(functions)==8,'Mode image bounds')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,handler_offset=handler_offset,functions=functions,entries=entries,sources=sources,mapping=mapping)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_mode.py.',
           'static const uint8_t ep_loadout_mode_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutModeFixup ep_loadout_mode_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset','handler_offset'):
        lines.append(f'static const uint32_t ep_loadout_mode_{key} = {a[key]};')
    lines.append('static const uint32_t ep_loadout_mode_entries[] = {'+','.join(map(str,a['entries']))+'};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
