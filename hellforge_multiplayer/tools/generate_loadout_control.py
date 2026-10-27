"""Relocate saved screen input/leave/reset and selection commit/exit.

All three remaining calls to the mode switch use the shared mode entry.
Roster descriptors/properties/peer scans and leave cleanup use owned storage.
The native input queue, state enums and non-player services retain their ABI.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

GROUPS=((0x146b190,0x146b350),(0x146d370,0x146d8be),(0x1470700,0x1470732),
        (0x1467790,0x1467b8b),(0x1467b90,0x1467f8a))
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
        need(len(fragments)=={0x146b190:3,0x146d370:6,0x1470700:1,0x1467790:3,0x1467b90:7}[start] and
             fragments[-1][1]==end and all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),
             'Changed control fragments')
        blob.extend(b'\xcc'*(-len(blob)%16));entry=len(blob);entries.append(entry)
        absolute(11,2);blob.extend(b'\x4c\x39\xd9');reject(b'\x0f\x85')
        absolute(11,9);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326468);reject(b'\x0f\x85')
        blob.extend(bytes.fromhex('458b9384000000'));capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
        blob.extend(bytes.fromhex('45399388000000'));reject(b'\x0f\x87')
        if start in (0x1467790,0x1467b90):
            absolute(11,17);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x33264f8);reject(b'\x0f\x85')
        body=len(blob);rows.append((entry,body,b'\x01\0\0\0',None));native_rows={}
        source=capture.read(start,end-start);sources.append(dict(start=start,end=end,data=source))
        insns=list(capture.md.disasm(source,start));need(insns[-1].address+insns[-1].size==end,'Incomplete control decode')
        for ins in insns:
            a=ins.address;at=len(blob);mapping[a]=at;text=ins.mnemonic+' '+ins.op_str
            mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
            if a in (0x14677ab,0x1467c02,0x1467ede):
                expected={0x14677ab:'mov rax, qword ptr [rcx + 0xe8]',
                          0x1467c02:'mov rax, qword ptr [rsi + 0xe8]',
                          0x1467ede:'mov rdx, qword ptr [rax + 0xe8]'}[a]
                need(text==expected,'Changed exit local descriptor');absolute(11,10)
                blob.extend(b'\x49\x8b\x13' if a==0x1467ede else b'\x49\x8b\x03')
            elif a in (0x14677ca,0x1467c21):
                need(text==('mov edx, dword ptr [rcx + 0x3a8]' if a==0x14677ca else
                            'mov edx, dword ptr [rsi + 0x3a8]'),'Changed exit local component')
                absolute(11,10,0x580);blob.extend(b'\x41\x8b\x13')
            elif a in (0x14677fa,0x146783c,0x1467a3e,0x1467a8b,0x1467ac8,0x1467ccb):
                need(text=='imul rcx, rax, 0x9f0','Changed exit selected record')
                capacity(b'\x3d');reject();blob.extend(ins.bytes)
            elif a in (0x1467805,0x1467847,0x1467cd6):
                need(text==('add rcx, rdi' if a==0x1467cd6 else 'add rcx, rsi'),'Changed exit record base')
                absolute(11,3,-0x10);blob.extend(b'\x4c\x01\xd9')
            elif a in (0x146797b,0x1467a02,0x1467a1c):
                need(text==('mov rax, qword ptr [rsi + 0x72868]' if a==0x1467a02 else
                            'mov rdx, qword ptr [rsi + 0x72868]'),'Changed exit local widget')
                absolute(11,4,0x1edf0);blob.extend(b'\x49\x8b\x03' if a==0x1467a02 else b'\x49\x8b\x13')
            elif a==0x14679d3:
                need(text=='mov r11d, ebx','Changed exit equipment ordinal')
                capacity(b'\x81\xfb');reject();blob.extend(ins.bytes)
            elif a==0x14679f1:
                need(text=='cmp dword ptr [r11 + r15 + 0xa8c], r9d','Changed exit equipment compare')
                absolute(0,19,0x10);blob.extend(bytes.fromhex('46390c18'))
            elif a in (0x1467a37,0x1467a87,0x1467aba):
                add=0x188 if a==0x1467a37 else 0
                need(text==f'lea r8, [rsi + {add+0x10:#x}]','Changed exit submitted record')
                absolute(8,3,add)
            elif a==0x1467a4a:
                need(text=='mov r9d, dword ptr [rcx + rsi + 0x798]','Changed exit record field')
                absolute(11,3,0x788);blob.extend(bytes.fromhex('458b0c0b'))
            elif a==0x1467cde:
                need(text=='lea rcx, [rdi + 0x53a78]','Changed exit local widget reset');absolute(1,4)
            elif a==0x1467d9e:
                need(text=='mov ecx, eax','Changed exit dense ordinal');capacity(b'\x3d');reject();blob.extend(ins.bytes)
            elif a==0x1467da0:
                need(text=='mov rax, qword ptr [rsi + rax*8 + 0xe8]','Changed exit dense descriptor')
                absolute(11,10);blob.extend(bytes.fromhex('498b04c3'))
            elif a==0x1467db2:
                need(text=='and dword ptr [rcx + rsi + 0x3ac], 0xffffffbf','Changed exit dense property')
                absolute(11,10,0x584);blob.extend(bytes.fromhex('4183240bbf'))
            elif a in (0x1467eed,0x1467efc):
                mask=0xfd if a==0x1467eed else 0xf7
                need(text==f'and dword ptr [rax + 0x3ac], {0xffffff00|mask:#x}','Changed exit local flag')
                absolute(11,10,0x584);blob.extend(bytes((0x41,0x83,0x23,mask)))
            elif a==0x146b1f4:
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
            elif ins.mnemonic=='call' and ins.operands[0].type==X86_OP_IMM and ins.operands[0].imm in (0x60b3b0, 0x60b460):
                fix(b'\xe8'+bytes(4),1,{0x60b3b0: 15, 0x60b460: 16}[ins.operands[0].imm],0)
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
            if head[0]==33:
                old=struct.unpack('<III',capture.read(u+n,12));need(old in native_rows,'Foreign control chain')
                parent=native_rows[old]
            if b==0x1467825:
                # Widened branches move the delayed R14 save beyond UNWIND_INFO's
                # byte-sized prologue offset. Split at that actual save, chaining
                # its new five-byte fragment to the three already executed saves.
                # Both sides retain the original stack locations and root frame.
                need(bytes(uw)==bytes.fromhex('21df0800dfe407000ff406000ac40f0005540e00'),
                     'Changed delayed selection-commit saves')
                split=0x14678ff;early=bytearray(bytes.fromhex('210f0600')+uw[8:])
                early[1]=ends[b+15]-mapping[b]
                for i in (0,2,4):early[4+2*i]=ends[b+early[4+2*i]]-mapping[b]
                early_row=len(rows);rows.append((mapping[b],mapping[split],bytes(early),parent))
                need(ends[split+5]-mapping[split]==5,'Delayed R14 save changed')
                native_rows[(b,e,u)]=len(rows)
                rows.append((mapping[split],ends[e],bytes.fromhex('2105020005e40700'),early_row))
                continue
            def offset(old):return ends[b+old]-mapping[b] if old else 0
            uw[1]=offset(head[1]);i=0
            while i<head[2]:
                uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                need(op in (0,1,2,4,8),'Unexpected control unwind operation');i+=2 if op in (1,4,8) else 1
            native_rows[(b,e,u)]=len(rows)
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
    need(len(blob)<=MAX_IMAGE and len(functions)==26,'Control image bounds')
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
