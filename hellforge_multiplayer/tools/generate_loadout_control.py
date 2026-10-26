"""Relocate saved screen input/leave and local selection reset; no game access.

All three remaining calls to the mode switch use the shared mode entry.
Roster descriptors/properties/peer scans and leave cleanup use owned storage.
The native input queue, state enums and non-player services retain their ABI.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

GROUPS=((0x146b190,0x146b350),(0x146d370,0x146d8be),(0x1470700,0x1470732))
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_control_template.h'


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
        need(len(fragments)=={0x146b190:3,0x146d370:6,0x1470700:1}[start] and
             fragments[-1][1]==end and all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),
             'Changed control fragments')
        blob.extend(b'\xcc'*(-len(blob)%16));entry=len(blob);entries.append(entry)
        absolute(11,2);blob.extend(b'\x4c\x39\xd9');reject(b'\x0f\x85')
        absolute(11,9);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326468);reject(b'\x0f\x85')
        blob.extend(bytes.fromhex('458b9384000000'));capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
        blob.extend(bytes.fromhex('45399388000000'));reject(b'\x0f\x87')
        body=len(blob);rows.append((entry,body,b'\x01\0\0\0',None));first_row=len(rows)
        source=capture.read(start,end-start);sources.append(dict(start=start,end=end,data=source))
        insns=list(capture.md.disasm(source,start));need(insns[-1].address+insns[-1].size==end,'Incomplete control decode')
        for ins in insns:
            a=ins.address;at=len(blob);mapping[a]=at;text=ins.mnemonic+' '+ins.op_str
            mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
            if a==0x146b1f4:
                need(text=='lea rbx, [rdi + 0x55a20]','Changed leave widget cleanup');absolute(3,4,0x1fa8)
            elif a==0x146b1fb:
                need(text=='mov esi, 4','Changed leave player bound');capacity(b'\xbe')
            elif a in (0x146b2f7,0x146d3ea,0x146d7b5,0x146d824):
                need(ins.mnemonic=='mov' and ins.reg_name(ins.operands[0].reg)=='rax' and mem.disp==0xe8,'Changed local descriptor')
                absolute(0,10);blob.extend(b'\x48\x8b\x00')
            elif a in (0x146b304,0x146b319,0x146b32d,0x146d3f7,0x146d7c2,0x146d831):
                expected,raw={0x146b304:('or dword ptr [rdx + 0x3ac], 2',b'\x41\x83\x0b\x02'),
                    0x146b319:('mov ecx, dword ptr [rdx + 0x3ac]',b'\x41\x8b\x0b'),
                    0x146b32d:('mov dword ptr [rdx + 0x3ac], ecx',b'\x41\x89\x0b'),
                    0x146d3f7:('or dword ptr [rsi + 0x3ac], 8',b'\x41\x83\x0b\x08'),
                    0x146d7c2:('and dword ptr [rsi + 0x3ac], 0xfffffff7',b'\x41\x83\x23\xf7'),
                    0x146d831:('and dword ptr [rsi + 0x3ac], 0xfffffff7',b'\x41\x83\x23\xf7')}[a]
                need(text==expected,'Changed local flags');absolute(11,10,0x584);blob.extend(raw)
            elif a==0x146d48b:
                need(text=='mov edx, dword ptr [rsi + 0x3a8]','Changed local component ID')
                absolute(11,10,0x580);blob.extend(b'\x41\x8b\x13')
            elif a==0x146d654:
                need(text=='lea rcx, [rsi + 0x2c8]','Changed roster peer scan');absolute(1,10,0x3c0)
            elif a==0x146d671:
                need(text=='mov rcx, qword ptr [rsi + rax*8 + 0xe8]','Changed dense descriptor lookup')
                capacity(b'\x3d');reject();absolute(11,10);blob.extend(b'\x49\x8b\x0c\xc3')
            elif a==0x1470704:
                need(text=='mov edx, dword ptr [rcx + 0x72874]','Changed local selection ID')
                absolute(11,4,0x1edfc);blob.extend(b'\x41\x8b\x13')
            elif a==0x147070a:
                need(text=='mov dword ptr [rcx + 0x7288c], 0xbf800000','Changed local selection timer')
                absolute(11,4,0x1ee14);blob.extend(b'\x41\xc7\x03\x00\x00\x80\xbf')
            elif ins.mnemonic=='call' and ins.operands[0].type==X86_OP_IMM and ins.operands[0].imm in (0x1470d90,0x146d9b0,0x146e0a0,0x1470740):
                fix(b'\xe8'+bytes(4),1,{0x1470d90:11,0x146d9b0:12,0x146e0a0:13,0x1470740:14}[ins.operands[0].imm],0)
            elif (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                raw=bytes(ins.bytes);target=ins.operands[0].imm
                op=raw[:1] if raw[0] in (0xe8,0xe9) else b'\xe9' if raw[0]==0xeb else bytes((0x0f,raw[0]+0x10)) if 0x70<=raw[0]<=0x7f else raw[:2]
                if any(b<=target<e for b,e in GROUPS):branch(op,('entry',target) if ins.mnemonic=='call' else target)
                else:fix(op+bytes(4),len(op),0,0,target)
            else:
                blob.extend(ins.bytes)
                if mem and mem.base==X86_REG_RIP:fixes.append((at+ins.disp_offset,len(blob),0,0,a+ins.size+ins.disp))
            ends[a+ins.size]=len(blob)
        for b,e,u in fragments:
            head=capture.read(u,4);n=4+((head[2]+1)&~1)*2;uw=bytearray(capture.read(u,n));parent=None
            need(head[0] in (1,33) and head[3]==0,'Unexpected control unwind')
            def offset(old):return ends[b+old]-mapping[b] if old else 0
            uw[1]=offset(head[1]);i=0
            while i<head[2]:
                uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                need(op in (0,1,2,4,8),'Unexpected control unwind operation');i+=2 if op in (1,4,8) else 1
            if head[0]==33:
                old=struct.unpack('<III',capture.read(u+n,12));need(old in fragments[:fragments.index((b,e,u))],'Foreign control chain')
                parent=first_row+fragments.index(old)
            rows.append((mapping[b],ends[e],bytes(uw),parent))
    for at,nxt,target in branches:
        if isinstance(target,tuple):target=entries[[b for b,e in GROUPS].index(target[1])]
        else:need(target in mapping,'Missing control branch');target=mapping[target]
        fixes.append((at,nxt,1,0,target))
    code_bytes=len(blob);blob.extend(bytes(-len(blob)%4));unwind_offset=len(blob);functions=[]
    for b,e,uw,parent in rows:
        functions.append((b,e,len(blob)));blob.extend(uw)
        if parent is not None:blob.extend(struct.pack('<III',*functions[parent]))
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE and len(functions)==13,'Control image bounds')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,functions=functions,entries=entries,sources=sources,mapping=mapping)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_control.py.',
           'static const uint8_t ep_loadout_control_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutControlFixup ep_loadout_control_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset'):
        lines.append(f'static const uint32_t ep_loadout_control_{key} = {a[key]};')
    lines.append(f'static const uint32_t ep_loadout_control_functions = {len(a["functions"])};')
    lines.append('static const uint32_t ep_loadout_control_entries[] = {'+','.join(map(str,a['entries']))+'};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
