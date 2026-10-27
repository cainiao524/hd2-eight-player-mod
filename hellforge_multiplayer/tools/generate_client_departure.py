"""Whole saved 1087540 departure with all client member arrays relocated.

Preserve native services, authorization, counted swap removal, fixed-table
search semantics and 64-entry event history. Only reads the workspace capture.
"""
import argparse
import struct
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP
from generate_loadout_lifecycle import Capture,PROJECT,need

START,END=0x1087540,0x10877f8
HEADER=PROJECT/'mod/src/ep_client_departure_template.h'
UNWIND={0x1087540:'01100600107409001034080010320ce0',0x108757c:'210a04000a64070005540600',
        0x10875f0:'2100020000640700',0x1087660:'21000000'}


def build():
    c=Capture();blob=bytearray();fixes=[];mapping={};edges=[];seen=set()
    def absolute(op,key,add=0):
        at=len(blob);blob.extend(bytes.fromhex(op)+bytes(8));fixes.append((at+2,0,key,1,add))
    def number(op):
        op=bytes.fromhex(op);at=len(blob);blob.extend(op+bytes(4));fixes.append((at+len(op),0,3,2,0))
    def check(jcc):
        blob.extend(bytes((jcc,13)));absolute('49bb',4);blob.extend(bytes.fromhex('41ffe3'))
    absolute('49bb',1);blob+=bytes.fromhex('4c39d9');check(0x74)
    absolute('49bb',11);blob+=bytes.fromhex('4c3919');check(0x74)
    for offset in (0x10,0x38,0x80,0xc8):number('81b9'+struct.pack('<I',offset).hex());check(0x76)
    body=len(blob)
    patches={
        0x10875f8:('cmp qword ptr [rax + rbx + 0xd0], rdi',2,'49393c03'),
        0x1087626:('movups xmm0, xmmword ptr [rax + rbx + 0xd0]',2,'410f100403'),
        0x108762e:('movups xmmword ptr [rsi + rbx + 0xd0], xmm0',2,'410f110433'),
        0x1087636:('movups xmm1, xmmword ptr [rax + rbx + 0xe0]',2,'410f104c0310'),
        0x108763e:('movups xmmword ptr [rsi + rbx + 0xe0], xmm1',2,'410f114c3310'),
        0x1087660:('lea rax, [rcx + 4]',None,'89c8'),
        0x1087669:('cmp qword ptr [rbx + rax*8], rdi',5,'49393cc3'),
        0x1087681:('lea rax, [rdx + 4]',None,'89d0'),
        0x1087685:('add rcx, 4',None,''),
        0x108768f:('movups xmm0, xmmword ptr [rbx + rcx*8]',5,'410f1004cb'),
        0x1087696:('movups xmmword ptr [rbx + rax*8], xmm0',5,'410f1104c3'),
        0x10876b2:('cmp qword ptr [rbx + rax*8 + 0x18], rdi',6,'49393cc3'),
        0x10876c7:('mov rcx, qword ptr [rbx + rax*8 + 0x18]',6,'498b0cc3'),
        0x10876cc:('mov qword ptr [rbx + rdx*8 + 0x18], rcx',6,'49890cd3'),
        0x10876e7:('cmp qword ptr [rbx + rax*8 + 0x88], rdi',7,'49393cc3'),
        0x108770c:('movups xmm0, xmmword ptr [rbx + rcx*8 + 0x88]',7,'410f1004cb'),
        0x1087714:('movups xmmword ptr [rbx + rdx*8 + 0x88], xmm0',7,'410f1104d3'),
        0x108773e:('add rax, 0x15',None,''),
        0x108774c:('movups xmmword ptr [rbx + rax*8], xmm0',8,'410f1104c3'),
        0x1087750:('mov qword ptr [rbx + rax*8], 0',8,'49c704c300000000'),
    }
    ins=list(c.md.disasm(c.read(START,END-START),START));need(sum(i.size for i in ins)==END-START,'Incomplete departure source')
    for i in ins:
        mapping[i.address]=len(blob)
        if i.address==0x1087612:
            # The release callback occurs before native decrement. Recheck its
            # live count before using count-1 as a source-record ordinal.
            number('81bbc8000000');check(0x76);blob+=bytes.fromhex('83bbc800000000');check(0x77)
        if i.address in patches:
            expected,key,op=patches[i.address];need(i.mnemonic+' '+i.op_str==expected,'Changed departure operand '+hex(i.address));seen.add(i.address)
            if key is not None:absolute('49bb',key)
            blob+=bytes.fromhex(op);continue
        if i.address==0x108771e:
            need(i.op_str=='rcx, [rbx + 0x88]','Changed fixed history search');absolute('48b9',7);continue
        if i.address==0x1087737:
            need(i.address+i.size+i.disp==0x347cd78,'Changed auxiliary slot global');absolute('48ba',9,-8);continue
        if i.address==0x108778c:
            need(i.address+i.size+i.disp==0x347cef0,'Changed departure event owner');absolute('49b8',11);continue
        if i.address in (0x1087730,0x108776b):
            need(i.op_str=='eax, 4','Changed departure fixed search');number('3d');continue
        if (i.mnemonic=='call' or i.mnemonic.startswith('j')) and i.operands[0].type==X86_OP_IMM:
            if i.mnemonic in ('call','jmp'):op=bytes.fromhex('e8' if i.mnemonic=='call' else 'e9')
            else:
                cond=i.bytes[0]-0x70 if i.bytes[0] in range(0x70,0x80) else i.bytes[1]-0x80
                need(0<=cond<16,'Unsupported departure branch');op=bytes((0x0f,0x80+cond))
            at=len(blob);blob+=op+bytes(4);edges.append((at+len(op),len(blob),i.operands[0].imm))
        else:
            at=len(blob);blob+=i.bytes
            if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
                fixes.append((at+i.disp_offset,at+i.size,0,0,i.address+i.size+i.disp))
        bound={0x10875d0:'81fa',0x1087646:'4181f8',0x108769f:'81f9',0x10876d1:'4181f8'}.get(i.address)
        if bound:number(bound);check(0x76)
    mapping[END]=len(blob);need(seen==set(patches),'Missing departure field')
    for off,nxt,target in edges:
        if START<=target<END:need(target in mapping,'Departure interior branch');struct.pack_into('<i',blob,off,mapping[target]-nxt)
        else:fixes.append((off,nxt,10 if target==0x1086b70 else 0,0,0 if target==0x1086b70 else target))
    blob+=bytes(-len(blob)%4);rows=[(0,body,len(blob))];blob+=bytes.fromhex('01000000');original={}
    fs=[f for f in c.functions if START<=f[0]<END];need(len(fs)==4 and fs[-1][1]==END,'Changed departure unwind extent')
    for s,e,u in fs:
        h=c.read(u,4);n=4+((h[2]+1)&~1)*2;uw=c.read(u,n);need(uw==bytes.fromhex(UNWIND[s]),'Changed departure unwind')
        row=(mapping[s],mapping[e],len(blob));rows.append(row);original[(s,e,u)]=row;blob+=uw
        if h[0]==33:
            parent=struct.unpack('<III',c.read(u+n,12));need(parent in original,'Unowned departure unwind parent');blob+=struct.pack('<III',*original[parent])
    table=len(blob)
    for row in rows:blob+=struct.pack('<III',*row)
    need(len(blob)<=4096,'Departure image size')
    return dict(blob=bytes(blob),fixes=fixes,table=table,body=body,rows=rows)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_client_departure.py.','static const uint8_t ep_client_departure_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpClientDepartureFixup ep_client_departure_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('table','body'):lines.append(f'static const uint32_t ep_client_departure_{key} = {a[key]};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print('Client departure candidate bytes:',len(a['blob']))
