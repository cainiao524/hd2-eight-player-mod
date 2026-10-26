"""Relocate saved resource writer, ordinal/transform queries and assignment.

Resource rows and player roster scans expand together. Transform categories
1..15 and event argument type 4 retain their native meanings. No game access.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

GROUPS=((0x65de10,0x65dec2),(0x661e70,0x661f97),(0x6619c0,0x661c24),(0x606820,0x6068e5),(0x662e90,0x662ffa))
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_resources_template.h'


def build():
    capture=Capture();blob=bytearray();fixes=[];branches=[];mapping={};ends={};rows=[];entries=[];sources=[];tables=[]
    def fix(raw,offset,key,kind=1,add=0):
        at=len(blob);blob.extend(raw);fixes.append((at+offset,len(blob),key,kind,add))
    def absolute(reg,key,add=0):fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,1,add)
    def capacity(raw):fix(raw+bytes(4),len(raw),5,2)
    def reject(op=b'\x0f\x83'):fix(op+bytes(4),len(op),6,0)
    def branch(op,target):
        at=len(blob);blob.extend(op+bytes(4));branches.append((at+len(op),len(blob),target))
    for start,end in GROUPS:
        fragments=[f for f in capture.functions if start<=f[0]<end]
        need(len(fragments)=={0x65de10:1,0x661e70:1,0x6619c0:1,0x606820:3,0x662e90:3}[start] and
             fragments[-1][1]==end and all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),
             'Changed resources fragments')
        blob.extend(b'\xcc'*(-len(blob)%16));entry=len(blob);entries.append(entry)
        if start==0x65de10:
            blob.extend(b'\x4d\x85\xc0');branch(b'\x0f\x84',0x65dec1) # retain null callback no-op
            capacity(b'\x41\x81\xf9');reject() # callback slot before services/writes
        if start in (0x661e70,0x606820):
            absolute(11,11 if start==0x661e70 else 9);blob.extend(b'\x4c\x39\xd9');reject(b'\x0f\x85')
        absolute(11,9);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326468);reject(b'\x0f\x85')
        blob.extend(bytes.fromhex('458b9384000000'));capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
        blob.extend(bytes.fromhex('45399388000000'));reject(b'\x0f\x87')
        absolute(11,11);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x33265f0);reject(b'\x0f\x85')
        rows.append((entry,len(blob),b'\x01\0\0\0',None));first_row=len(rows)
        code_end=0x661be8 if start==0x6619c0 else end
        source=capture.read(start,code_end-start);sources.append(dict(start=start,end=code_end,data=source))
        insns=list(capture.md.disasm(source,start));need(insns[-1].address+insns[-1].size==code_end,'Incomplete resources decode')
        for ins in insns:
            a=ins.address;at=len(blob);mapping[a]=at;text=ins.mnemonic+' '+ins.op_str
            mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
            if a in (0x65de8b,0x65de93,0x65de9f,0x65dea7,0x65deaf):
                need(mem.disp in (0x11d18,0x11d1c,0x11d2c,0x11d3c,0x11d4c) and ins.reg_name(mem.base)=='rcx' and ins.reg_name(mem.index)=='rdi','Changed resource callback row')
                absolute(11,12,mem.disp-0x11d18)
                if a==0x65de93:blob.extend(b'\x41\x89\x1c\x0b')
                else:
                    register={0x65de8b:0,0x65de9f:1,0x65dea7:2,0x65deaf:3}[a]
                    blob.extend(bytes((0x41,0x0f,0x11,0x04+(register<<3),0x0b)))
            elif a==0x661f62:
                need(text=='lea rcx, [r14 + 0x11d18]','Changed ordinal resource base');absolute(1,12)
            elif a==0x661f7b:
                need(text=='cmp r8d, 4','Changed ordinal bound');capacity(b'\x41\x81\xf8')
            elif a==0x6619ec:
                need(text=='mov rax, qword ptr [rcx + 0xe8]','Changed local descriptor');absolute(0,10);blob.extend(b'\x48\x8b\x00')
            elif a==0x661ac1:
                need(text=='imul rcx, rax, 0x4c','Changed transform resource index')
                capacity(b'\x3d');reject();blob.extend(ins.bytes)
            elif a==0x661ac5:
                need(text=='lea rax, [rdi + 0x11d1c]','Changed transform row');absolute(0,12,4)
            elif a==0x661a13:
                need(text=='lea r9, [rip - 0x661a1a]','Changed transform switch base');absolute(9,1)
            elif a==0x661a1d:
                need(text=='mov r8d, dword ptr [r9 + rcx*4 + 0x661be8]','Changed transform switch operand')
                raw=bytearray(ins.bytes);raw[ins.disp_offset:ins.disp_offset+4]=bytes(4)
                tables.append(len(blob)+ins.disp_offset);blob.extend(raw)
            elif a in (0x606836,0x6068ca):
                need(text=='shl rcx, 5','Changed player-value stride');capacity(b'\x81\xf9');reject()
                blob.extend(b'\x41\x3b\x8a\x84\0\0\0');reject();blob.extend(ins.bytes)
            elif a in (0x60683a,0x6068ce):
                need(text=='mov eax, dword ptr [rcx + r10 + 0x3b4]','Changed player value')
                absolute(11,10,0x58c);blob.extend(b'\x41\x8b\x04\x0b')
            elif a==0x662eb3:
                need(text=='lea rdi, [r15 + 0x11d18]','Changed assignment resource base');absolute(7,12)
            elif a==0x662eba:
                need(text=='lea ebp, [rsi + 4]','Changed assignment scan count');capacity(b'\xbd')
            elif a==0x662f3d:
                need(text=='cmp ecx, 4','Changed assignment resource mask');capacity(b'\x81\xf9')
            elif a==0x662f58:
                need(text=='mov ebx, dword ptr [rcx + r15 + 0x11d18]','Changed assignment handle read')
                absolute(11,12);blob.extend(b'\x41\x8b\x1c\x0b')
            elif a==0x662f00:
                need(text=='lea rdi, [rbp*8 + 0xe8]','Changed assignment descriptor offset')
                capacity(b'\x81\xfd');reject();blob.extend(b'\x48\x8d\x3c\xed\0\0\0\0')
            elif a in (0x662f08,0x662f60):
                need(text==('mov rax, qword ptr [rdi + rcx]' if a==0x662f08 else 'mov rcx, qword ptr [rdi + rax]'),'Changed assignment descriptor')
                absolute(11,10);blob.extend(b'\x49\x8b\x04\x3b' if a==0x662f08 else b'\x49\x8b\x0c\x3b')
            elif a==0x662f18:
                need(text=='call 0x661fa0','Changed shared resource lookup');fix(b'\xe8'+bytes(4),1,13,0)
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
        for b,e,u in fragments:
            head=capture.read(u,4);need(head[0] in (1,33) and head[3]==0,'Unexpected resources unwind')
            n=4+((head[2]+1)&~1)*2;uw=bytearray(capture.read(u,n));parent=None
            def offset(old):return ends[b+old]-mapping[b] if old else 0
            uw[1]=offset(head[1]);i=0
            while i<head[2]:
                uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                need(op in (0,1,2,4,8),'Unexpected resources unwind operation');i+=2 if op in (1,4,8) else 1
            if head[0]==33:
                old=struct.unpack('<III',capture.read(u+n,12));need(old in fragments[:fragments.index((b,e,u))],'Foreign resources chain')
                parent=first_row+fragments.index(old)
            rows.append((mapping[b],ends[min(e,code_end)],bytes(uw),parent))
    for at,nxt,target in branches:
        if isinstance(target,tuple):target=entries[[b for b,e in GROUPS].index(target[1])]
        else:need(target in mapping,'Missing resources branch');target=mapping[target]
        fixes.append((at,nxt,1,0,target))
    code_bytes=len(blob);blob.extend(bytes(-len(blob)%4));switch_offset=len(blob)
    for target in struct.unpack('<15I',capture.read(0x661be8,60)):
        need(target in mapping,'Changed transform switch target');blob.extend(struct.pack('<I',mapping[target]))
    for at in tables:struct.pack_into('<I',blob,at,switch_offset)
    unwind_offset=len(blob);functions=[]
    for b,e,uw,parent in rows:
        functions.append((b,e,len(blob)));blob.extend(uw)
        if parent is not None:blob.extend(struct.pack('<III',*functions[parent]))
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE and len(functions)==14,'Resources image bounds')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,functions=functions,entries=entries,sources=sources,mapping=mapping)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_resources.py.',
           'static const uint8_t ep_loadout_resources_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutResourcesFixup ep_loadout_resources_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset'):
        lines.append(f'static const uint32_t ep_loadout_resources_{key} = {a[key]};')
    lines.append(f'static const uint32_t ep_loadout_resources_functions = {len(a["functions"])};')
    lines.append('static const uint32_t ep_loadout_resources_entries[] = {'+','.join(map(str,a['entries']))+'};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
