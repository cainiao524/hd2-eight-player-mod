"""Relocate saved 146FC40 record synchronization and all five unwind fragments.

Network index, UI slot and equipment-source ordinal stay distinct. Eight
activity bytes occupy unused stack +38..3F, without enlarging the GS frame.
Only saved workspace evidence is read; no game discovery or access.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need,GS_HANDLER
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

START,END=0x146fc40,0x1470648
UNWIND=bytes.fromhex('192103000f01920202d00000')
COOKIE=0x1460
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_records_template.h'


def build():
    capture=Capture();blob=bytearray();fixes=[];branches=[];mapping={};ends={};rows=[]
    fragments=[f for f in capture.functions if START<=f[0]<END]
    need(len(fragments)==5 and fragments[0][0]==START and fragments[-1][1]==END and
         all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),'Changed record-sync fragments')
    need(capture.read(fragments[0][2],20)==UNWIND+struct.pack('<II',GS_HANDLER,COOKIE),'Changed record-sync GS frame')
    def fix(raw,offset,key,kind=1,add=0):
        at=len(blob);blob.extend(raw);fixes.append((at+offset,len(blob),key,kind,add))
    def absolute(reg,key,add=0,kind=1):fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,kind,add)
    def branch(op,target):
        at=len(blob);blob.extend(op+bytes(4));branches.append((at+len(op),len(blob),target))
    def capacity(raw):fix(raw+bytes(4),len(raw),5,2)
    def reject(op=b'\x0f\x83'):fix(op+bytes(4),len(op),6,0)

    absolute(11,2);blob.extend(b'\x4c\x39\xd9');reject(b'\x0f\x85')
    for key,global_rva in ((9,0x3326468),(11,0x33264f8)):
        absolute(11,key);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,global_rva);reject(b'\x0f\x85')
    absolute(11,9);blob.extend(b'\x45\x8b\x93\x84\0\0\0');capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
    body=len(blob);rows.append((0,body,b'\x01\0\0\0',None));source=capture.read(START,END-START)
    insns=list(capture.md.disasm(source,START));need(insns[-1].address+insns[-1].size==END,'Incomplete record-sync decode')
    # No native stack operand occupies our eight-byte activity scratch.
    for ins in insns:
        for op in ins.operands:
            if op.type==X86_OP_MEM and ins.reg_name(op.mem.base)=='rsp':
                need(not 0x38<=op.mem.disp<0x40,'Activity scratch is no longer unused')
    for ins in insns:
        a=ins.address;at=len(blob);mapping[a]=at;text=ins.mnemonic+' '+ins.op_str
        mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
        if a==0x146fc7e:
            need(text=='mov dword ptr [rsp + 0x4c], eax','Changed activity initialization');blob.extend(b'\x48\x89\x44\x24\x38')
        elif a==0x146fc9a:
            need(text=='add rsi, 0x3ac','Changed roster flags');absolute(6,10,0x584)
        elif a==0x146fd47:
            need(text=='mov rax, qword ptr [rsi + r14*8 + 0xe8]','Changed roster descriptors')
            absolute(11,10);blob.extend(b'\x4b\x8b\x04\xf3')
        elif a in (0x146fd65,0x146fda6):
            need(mem.disp==(0x3a8 if a==0x146fd65 else 0x2c8),'Changed roster bank')
            absolute(11,10,0x580 if a==0x146fd65 else 0x3c0)
            blob.extend(b'\x41\x8b\x14\x03' if a==0x146fd65 else b'\x4d\x8b\x3c\x03')
        elif a==0x146fde6:
            need(text=='cmp ebx, 4','Changed network bound');capacity(b'\x81\xfb')
        elif a==0x146fdf9:
            need(text=='mov esi, dword ptr [r13 + rbx*4 + 0x27d8]','Changed forward map')
            absolute(10,7);blob.extend(b'\x41\x8b\x34\x9a\x83\xfe\xff');branch(b'\x0f\x84','map_done')
            capacity(b'\x81\xfe');reject();absolute(10,8);blob.extend(b'\x41\x39\x1c\xb2');reject(b'\x0f\x85')
            mapping['map_done']=len(blob)
        elif a==0x146fe05:
            need(text=='mov byte ptr [rsp + rbx + 0x4c], 1','Changed activity write');blob.extend(b'\xc6\x44\x1c\x38\x01')
        elif a in (0x146fe43,0x1470010):
            need(text==('add rsi, r13' if a==0x146fe43 else 'add r14, r13'),'Changed record address')
            absolute(11,3,-0x10);blob.extend(b'\x4c\x01\xde' if a==0x146fe43 else b'\x4d\x01\xde')
        elif a==0x146ff6c:
            need(text=='cmp qword ptr [rbx + r13 + 0x9f8], r15','Changed record peer')
            absolute(11,3,-0x10);blob.extend(bytes.fromhex('4d39bc1bf8090000'))
        elif a==0x146ff8a:
            need(text=='lea rcx, [r13 + 0x10]','Changed record copy');absolute(1,3)
        elif a in (0x146ffb6,0x14703b6):
            need(text=='add rbx, r13','Changed widget address');absolute(11,4,-0x53a78);blob.extend(b'\x4c\x01\xdb')
        elif a in (0x1470451,0x14704d8,0x1470550):
            need(ins.mnemonic=='lea' and mem.base and ins.reg_name(mem.base)=='r13','Changed fixed widget')
            absolute(3 if a==0x1470451 else 1,4,mem.disp-0x53a78)
        elif a==0x1470530:
            need(text=='add rcx, 0x53a78','Changed indexed widget');absolute(11,4,0,3);blob.extend(b'\x4c\x01\xd9')
        elif a in (0x14704ab,0x147056d):
            need(text=='cmp esi, 4','Changed player loop');capacity(b'\x81\xfe')
        elif a==0x146ff0a:
            capacity(b'\x41\x81\xf9');reject();blob.extend(ins.bytes)
        elif a==0x146ff1b:
            need(text=='lea r8, [r9 + 0xa8c]','Changed equipment write');absolute(8,13,0x10)
        elif a==0x146ff2d:
            need(text=='mov rax, qword ptr [r9 + rcx*8 + 0x948]','Changed source actors')
            absolute(11,12);blob.extend(b'\x49\x8b\x04\xcb')
        elif a in (0x147007d,0x1470305):
            need(text=='mov ecx, eax','Changed source ordinal');capacity(b'\x3d');reject();blob.extend(ins.bytes)
        elif a==0x147007f:
            need(text=='lea r12, [rsi + 0xa7c]','Changed equipment source');absolute(12,13)
        elif a==0x147030b:
            need(text=='movzx ecx, byte ptr [rax + rbp + 0x994]','Changed status source')
            absolute(11,14);blob.extend(b'\x41\x0f\xb6\x0c\x03')
        elif a==0x147059e:
            need(text=='mov eax, dword ptr [rsp + 0x4c]','Changed activity result');blob.extend(b'\x48\x8b\x44\x24\x38')
        elif a in (0x14705da,0x14705dc):blob.extend(b'\x90'*ins.size)
        elif a==0x14705de:
            absolute(8,3,0x9e8);capacity(b'\x41\xb9');mapping['clear_loop']=len(blob)
            blob.extend(b'\x84\xc0');branch(b'\x0f\x85','clear_next');blob.extend(b'\x49\xc7\x00'+bytes(4))
            mapping['clear_next']=len(blob);blob.extend(b'\x49\x81\xc0'+struct.pack('<I',0x9f0)+b'\x48\xc1\xe8\x08\x41\xff\xc9')
            branch(b'\x0f\x85','clear_loop')
        elif 0x14705de<a<0x147061f:pass
        elif (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
            raw=bytes(ins.bytes);target=ins.operands[0].imm
            op=raw[:1] if raw[0] in (0xe8,0xe9) else b'\xe9' if raw[0]==0xeb else bytes((0x0f,raw[0]+0x10)) if 0x70<=raw[0]<=0x7f else raw[:2]
            if START<=target<END:branch(op,target)
            else:fix(op+bytes(4),len(op),0,0,target)
        else:
            blob.extend(ins.bytes)
            if mem and mem.base==X86_REG_RIP:fixes.append((at+ins.disp_offset,len(blob),0,0,a+ins.size+ins.disp))
        if a==0x1470582:
            capacity(b'\x81\xb8\x84\0\0\0');reject(b'\x0f\x87')
        ends[a+ins.size]=len(blob)
        if a<START+UNWIND[1]:
            need(len(blob)-at==ins.size and at-body==a-START,'Record-sync root prologue moved')
            need(blob[at:]==ins.bytes or text=='call 0x21045c0','Unexpected root prologue change')
    for at,nxt,target in branches:
        need(target in mapping,'Record-sync branch leaves owned code');fixes.append((at,nxt,1,0,mapping[target]))
    for b,e,u in fragments:
        head=capture.read(u,4);n=4+((head[2]+1)&~1)*2;uw=bytearray(capture.read(u,n))
        if b==START:uw+=bytes(8);parent='gs'
        else:
            need(head[0]==33 and head[3]==0,'Unexpected record-sync chain')
            def offset(old):return ends[b+old]-mapping[b] if old else 0
            uw[1]=offset(head[1]);i=0
            while i<head[2]:
                uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                need(op in (0,1,2,4,8),'Unexpected record-sync unwind operation');i+=2 if op in (1,4,8) else 1
            parent=struct.unpack('<III',capture.read(u+n,12));need(parent in fragments[:fragments.index((b,e,u))],'Foreign record-sync chain')
            parent=fragments.index(parent)+1
        rows.append((mapping[b],ends[e],bytes(uw),parent))
    blob.extend(b'\xcc'*(-len(blob)%16));handler_offset=len(blob);fix(b'\xe9'+bytes(4),1,0,0,GS_HANDLER)
    code_bytes=len(blob);rows.append((handler_offset,code_bytes,b'\x01\0\0\0',None));blob.extend(bytes(-len(blob)%4))
    unwind_offset=len(blob);functions=[]
    for b,e,uw,parent in rows:
        functions.append((b,e,len(blob)))
        if parent=='gs':blob.extend(uw[:-8]+struct.pack('<II',handler_offset,COOKIE))
        else:
            blob.extend(uw)
            if parent:blob.extend(struct.pack('<III',*functions[parent]))
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE and len(functions)==7,'Record-sync image bounds')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,handler_offset=handler_offset,functions=functions,source=source,mapping=mapping)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_records.py.',
           'static const uint8_t ep_loadout_records_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutRecordsFixup ep_loadout_records_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset','handler_offset'):
        lines.append(f'static const uint32_t ep_loadout_records_{key} = {a[key]};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
