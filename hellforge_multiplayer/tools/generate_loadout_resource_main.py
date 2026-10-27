"""Relocate saved main resource update and published-object query.

The captured countdown layout has one inline controller (+50 pointer,
+58 large state, +11CD8 small state, +12EE0 notification row). Reject
multiple controllers rather than alias their resources. Player resources
use the independent capacity/bank; native catalogs keep their own indices.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need,GS_HANDLER
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

GROUPS=((0x65fa50,0x6614fd),(0x6620d0,0x66222c))
UNWIND=bytes.fromhex("1941110033c813002b68190026743d0026643c0026343b002601340018f016e014d012c010500000")
COOKIE=0x128
MAX_IMAGE=16384
HEADER=PROJECT/'mod/src/ep_loadout_resource_main_template.h'


def build():
    capture=Capture();blob=bytearray();fixes=[];branches=[];mapping={};ends={};rows=[];entries=[];sources=[]
    def fix(raw,offset,key,kind=1,add=0):
        at=len(blob);blob.extend(raw);fixes.append((at+offset,len(blob),key,kind,add))
    def absolute(reg,key,add=0):fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,1,add)
    def capacity(raw):fix(raw+bytes(4),len(raw),5,2)
    def reject(op=b'\x0f\x83'):fix(op+bytes(4),len(op),6,0)
    def branch(op,target):
        at=len(blob);blob.extend(op+bytes(4));branches.append((at+len(op),len(blob),target))
    def bank(ins,key,add=0,forced_index=None,scratch=11):
        # Rewrite only the reviewed owner-bank operand. Keep the original
        # opcode, register width, index/scale and immediate; R11 is dead at
        # each reviewed site; owner registers retain their native lifetimes.
        mem=next(o.mem for o in ins.operands if o.type==X86_OP_MEM)
        need(mem.base and ins.reg_name(mem.base) in ('rax','rbx','rcx','rsi','rdi','r8','r14','r11','rdx'),'Unexpected owner bank base')
        idx=forced_index or (ins.reg_name(mem.index) if mem.index else None)
        names=['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi']+[f'r{i}' for i in range(8,16)]
        index=names.index(idx) if idx else 4
        need(idx is None or idx!='rsp','Unsupported owner bank index')
        raw=bytes(ins.bytes);p=0
        while raw[p] in (0xf0,0xf2,0xf3,0x2e,0x36,0x3e,0x26,0x64,0x65,0x66,0x67):p+=1
        rex=((ins.rex or 0x40)&~3)|1|(2 if idx and index>=8 else 0)
        prefix=raw[:p]+bytes((rex,))+raw[p+bool(ins.rex):ins.modrm_offset]
        absolute(scratch,key,add)
        blob.extend(prefix+bytes(((ins.modrm&0x38)|4,({1:0,2:1,4:2,8:3}[mem.scale]<<6)|((index&7)<<3)|(scratch&7))))
        if ins.imm_size:blob.extend(raw[ins.imm_offset:ins.imm_offset+ins.imm_size])
    banks={0x660ad6:(15,0,0x88),0x660ae1:(15,0,0x88),
           0x660b46:(15,0,0x88),0x660b50:(15,0,0x88)}
    for start,end in GROUPS:
        fragments=[f for f in capture.functions if start<=f[0]<end]
        need(len(fragments)==(3 if start==GROUPS[0][0] else 1) and
             fragments[-1][1]==end and all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),
             'Changed resource callback fragments')
        blob.extend(b'\xcc'*(-len(blob)%16));entry=len(blob);entries.append(entry)
        absolute(11,13);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326428);reject(b'\x0f\x85')
        for off in (0,4,8,12):
            blob.extend(b'\x45\x8b\x53'+bytes((off,)));capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
        for off in (8,12):
            blob.extend(b'\x45\x8b\x53'+bytes((off,))+b'\x45\x3b\x53\x04');reject(b'\x0f\x87')
        absolute(11,11);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x33265f0);reject(b'\x0f\x85')
        if start==GROUPS[0][0]:
            blob.extend(b'\x4c\x39\xd9');reject(b'\x0f\x85')
            for off in (0x20,0x24):
                blob.extend(b'\x41\x83\x7b'+bytes((off,1)));reject(b'\x0f\x87')
        absolute(11,9);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326468);reject(b'\x0f\x85')
        blob.extend(bytes.fromhex('458b9384000000'));capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
        blob.extend(bytes.fromhex('45399388000000'));reject(b'\x0f\x87')
        body=len(blob);rows.append((entry,body,b'\x01\0\0\0',None));first_row=len(rows)
        code_end=end
        source=capture.read(start,code_end-start);sources.append(dict(start=start,end=code_end,data=source))
        insns=list(capture.md.disasm(source,start));need(insns[-1].address+insns[-1].size==code_end,'Incomplete resource_main decode')
        for ins in insns:
            a=ins.address;at=len(blob);mapping[a]=at;text=ins.mnemonic+' '+ins.op_str
            mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
            if a in banks:
                key,offset,old=banks[a];need(mem.disp==old,'Changed phase operand');bank(ins,key,offset)
            elif a==0x660ca5:
                need(text=='mov r13, qword ptr [rbp - 0x60]','Changed resource scan base')
                # Both resource ID loads use this derived pointer +40h.
                # All earlier small-controller fields keep their native base.
                absolute(13,12,-0x40)
            elif a==0x660cdd:
                need(text=='cmp ebx, 4','Changed resource scan bound');capacity(b'\x81\xfb')
            elif a==0x660b1d:
                need(text=='call 0x662400','Changed reset call');fix(b'\xe8'+bytes(4),1,18,0)
            elif a==0x662122:
                need(text=='lea r12, [rax + 0x68]','Changed published object scan');absolute(12,14)
            elif a==0x662192:
                need(text=='mov edx, eax','Changed catalog hash ordinal')
                # A missing native catalog identity must skip this object.
                # A present catalog ordinal is not bounded by player count.
                blob.extend(b'\x83\xf8\xff');branch(b'\x0f\x84',0x6621d1);blob.extend(ins.bytes)
            elif (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                raw=bytes(ins.bytes);target=ins.operands[0].imm
                op=raw[:1] if raw[0] in (0xe8,0xe9) else b'\xe9' if raw[0]==0xeb else bytes((0x0f,raw[0]+0x10)) if 0x70<=raw[0]<=0x7f else raw[:2]
                if target in [b for b,e in GROUPS]:branch(op,('entry',target))
                elif any(b<=target<e for b,e in GROUPS):branch(op,target)
                else:fix(op+bytes(4),len(op),0,0,target)
            else:
                blob.extend(ins.bytes)
                if mem and mem.base==X86_REG_RIP:fixes.append((at+ins.disp_offset,len(blob),0,0,a+ins.size+ins.disp))
            ends[a+ins.size]=len(blob)
            if start==GROUPS[0][0] and a<start+UNWIND[1]:
                need(blob[at:]==ins.bytes and at-body==a-start,'Main GS prologue moved')
        for b,e,u in fragments:
            head=capture.read(u,4);n=4+((head[2]+1)&~1)*2;uw=bytearray(capture.read(u,n));parent=None
            if b==GROUPS[0][0]:
                need(capture.read(u,n+8)==UNWIND+struct.pack('<II',GS_HANDLER,COOKIE),'Changed resource main GS contract');uw+=bytes(8);parent='gs'
            else:
                need(head[0] in (1,33) and head[3]==0,'Unexpected resource main unwind')
                def offset(old):return ends[b+old]-mapping[b] if old else 0
                uw[1]=offset(head[1]);i=0
                while i<head[2]:
                    uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                    need(op in (0,1,2,4,8),'Unexpected unwind operation');i+=2 if op in (1,4,8) else 1
                if head[0]==33:
                    old=struct.unpack('<III',capture.read(u+n,12));need(old in fragments[:fragments.index((b,e,u))],'Foreign resource main chain')
                    parent=first_row+fragments.index(old)
            rows.append((mapping[b],ends[min(e,code_end)],bytes(uw),parent))
    for at,nxt,target in branches:
        if isinstance(target,tuple):target=entries[[b for b,e in GROUPS].index(target[1])]
        else:need(target in mapping,'Missing resource_main branch');target=mapping[target]
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
    need(len(blob)<=MAX_IMAGE and len(functions)==7,'Resource callback image bounds')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,handler_offset=handler_offset,functions=functions,entries=entries,sources=sources,mapping=mapping)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_resource_main.py.',
           'static const uint8_t ep_loadout_resource_main_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutResourceMainFixup ep_loadout_resource_main_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset','handler_offset'):
        lines.append(f'static const uint32_t ep_loadout_resource_main_{key} = {a[key]};')
    lines.append(f'static const uint32_t ep_loadout_resource_main_functions = {len(a["functions"])};')
    lines.append('static const uint32_t ep_loadout_resource_main_entries[] = {'+','.join(map(str,a['entries']))+'};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
