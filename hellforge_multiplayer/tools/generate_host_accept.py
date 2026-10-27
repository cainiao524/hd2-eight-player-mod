"""Saved acceptance plus client member-metadata receive/local update bodies.

The shared metadata bank replaces client+150's four 16-byte records. Numeric
limits 90/60, peer states, and protocol kinds/field counts are not capacities.
"""
import argparse
import struct
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP
from generate_loadout_lifecycle import Capture,PROJECT,need

SOURCES=((0x108c760,0x108cd7c),(0x1084f50,0x1084fc2),(0x1084e10,0x1084ec1))
HEADER=PROJECT/'mod/src/ep_host_accept_template.h'
UNWIND={
    0x108c760:'192406001601310007e005d003300250',
    0x108c7d2:'2108020008f42e00',0x108c888:'211504001574300008643900',
    0x108c8a7:'2108020008c42f00',0x108c9c0:'21000000',0x108cd5a:'21000000',0x108cd62:'21000000',
    0x1084f50:'0106020006320230',0x1084e10:'0106020006720230',
}


def build():
    c=Capture();blob=bytearray();fixes=[];mapping={};entries={};edges=[];groups=[]
    def absolute(op,key,add=0):
        at=len(blob);blob.extend(bytes.fromhex(op)+bytes(8));fixes.append((at+2,0,key,1,1,add))
    def number(op,key=8):
        op=bytes.fromhex(op);at=len(blob);blob.extend(op+bytes(4));fixes.append((at+len(op),0,key,2,1,0))
    def check(jcc):
        blob.extend(bytes((jcc,13)));absolute('49bb',9);blob.extend(bytes.fromhex('41ffe3'))
    for kind,(start,end) in enumerate(SOURCES):
        blob+=b'\xcc'*(-len(blob)%16);entry=len(blob);entries[start]=entry
        absolute('49bb',1 if kind==0 else 13);blob+=bytes.fromhex('4c39d9');check(0x74)
        absolute('49bb',2);blob+=bytes.fromhex('4c3919');check(0x74)
        number('4181bb90630100');check(0x76)
        need(len(blob)-entry<=96,'Acceptance guard size');blob+=b'\x90'*(96-(len(blob)-entry));body=len(blob)
        ins=list(c.md.disasm(c.read(start,end-start),start));need(sum(i.size for i in ins)==end-start,'Incomplete acceptance source')
        for i in ins:
            mapping[i.address]=len(blob)
            bases={0x108c7da:('rcx, 0x20','48b9',4,0),0x108c7f6:('rcx, [r14 + 0x20]','48b9',4,0),
                   0x108c8e3:('rdi, [r14 + 0x40]','48bf',4,32),0x108c9c0:('rcx, qword ptr [r14]','48b9',10,0),
                   0x1084f59:('rax, [rcx + 0x150]','48b8',10,0)}
            if i.address in bases:
                expected,op,key,add=bases[i.address];need(i.op_str==expected,'Changed acceptance bank');absolute(op,key,add);continue
            if i.address in (0x108c7eb,0x108c8e7,0x1084f83):
                need(i.operands[-1].imm==4,'Changed acceptance bound');number({0x108c7eb:'3d',0x108c8e7:'41bc',0x1084f83:'81fa'}[i.address]);continue
            if i.address==0x108c9bc:
                need(i.op_str=='esi, [rdi + 4]','Changed metadata loop');number('be');continue
            if i.address in (0x108c7a9,0x108c928):
                need(i.address+i.size+i.disp==0x347cef0,'Changed selected owner global');absolute('48b8',2);continue
            if i.address==0x108c815:
                # R15 previously held only an inline offset. Save the actual
                # selected bank record for all subsequent reciprocal messages.
                blob+=bytes.fromhex('4989cf')
            fields={0x108c92f:('ecx, dword ptr [r15 + r14 + 0x40]','418b4f20'),
                    0x108c934:('edx, dword ptr [r15 + r14 + 0x34]','418b5714'),
                    0x108c939:('r9d, dword ptr [r15 + r14 + 0x30]','458b4f10'),
                    0x108c93e:('r8, qword ptr [r15 + r14 + 0x28]','4d8b4708'),
                    0x108c9c3:('rdx, qword ptr [rdi + rcx + 0x16418]','488b140f'),
                    0x108c9d0:('eax, dword ptr [rdi + rcx + 0x16424]','8b440f0c'),
                    0x108c9e5:('eax, dword ptr [rdi + rcx + 0x16420]','8b440f08')}
            if i.address in fields:
                expected,op=fields[i.address];need(i.op_str==expected,'Changed acceptance field');blob+=bytes.fromhex(op);continue
            local={0x1084e26:(0x158,'41895308'),0x1084e34:(0x15c,'41894b0c'),
                   0x1084e3f:(0x158,'41894308'),0x1084e4c:(0x15c,'4189430c')}
            if i.address in local:
                old,op=local[i.address];need(i.disp==old,'Changed local metadata field');absolute('49bb',10);blob+=bytes.fromhex(op);continue
            if (i.mnemonic=='call' or i.mnemonic.startswith('j')) and i.operands[0].type==X86_OP_IMM:
                if i.mnemonic in ('call','jmp'):op='e8' if i.mnemonic=='call' else 'e9'
                else:
                    cond=i.bytes[0]-0x70 if i.bytes[0] in range(0x70,0x80) else i.bytes[1]-0x80
                    need(0<=cond<16,'Unsupported acceptance branch');op=bytes((0x0f,0x80+cond)).hex()
                op=bytes.fromhex(op);at=len(blob);blob+=op+bytes(4);edges.append((at+len(op),len(blob),i.operands[0].imm))
            else:
                at=len(blob);blob+=i.bytes
                if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
                    fixes.append((at+i.disp_offset,at+i.size,0,0,1,i.address+i.size+i.disp))
        mapping[end]=len(blob);groups.append((start,end,entry,body))
    for off,nxt,target in edges:
        if target in mapping:struct.pack_into('<i',blob,off,mapping[target]-nxt)
        else:
            need(not any(s<=target<e for s,e in SOURCES),'Acceptance edge into replaced block')
            key={0x108b6b0:11,0xb90b20:12}.get(target,0);fixes.append((off,nxt,key,0,1,0 if key else target))
    handler=len(blob);blob+=b'\xe9'+bytes(4);fixes.append((handler+1,handler+5,0,0,1,0x21044a0))
    blob+=bytes(-len(blob)%4);rows=[];original={}
    for start,end,entry,body in groups:
        rows.append((entry,body,len(blob)));blob+=bytes((1,0,0,0))
        fs=[f for f in c.functions if start<=f[0]<end];need(fs[-1][1]==end,'Acceptance unwind extent')
        for sb,se,u in fs:
            h=c.read(u,4);n=4+((h[2]+1)&~1)*2;uw=c.read(u,n);need(uw==bytes.fromhex(UNWIND[sb]),'Changed acceptance unwind')
            row=(mapping[sb],mapping[se],len(blob));rows.append(row);original[(sb,se,u)]=row;blob+=uw
            if h[0]==25:
                need(c.read(u+n,8)==struct.pack('<II',0x21044a0,0x160),'Changed acceptance cookie');blob+=struct.pack('<II',handler,0x160)
            elif h[0]==33:
                parent=struct.unpack('<III',c.read(u+n,12));need(parent in original,'Unowned acceptance unwind chain');blob+=struct.pack('<III',*original[parent])
    rows.append((handler,handler+5,len(blob)));blob+=bytes((1,0,0,0));table=len(blob)
    for row in rows:blob+=struct.pack('<III',*row)
    need(len(blob)<=4096 and len(rows)==13,'Acceptance image size')
    return dict(blob=bytes(blob),fixes=fixes,mapping=mapping,entries=list(entries.values()),rows=rows,table=table,handler=handler)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_host_accept.py.','static const uint8_t ep_host_accept_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpHostAcceptFixup ep_host_accept_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    lines+=['static const uint32_t ep_host_accept_entries[] = {'+','.join(map(str,a['entries']))+'};']
    for field in ('table','handler'):lines.append(f'static const uint32_t ep_host_accept_{field} = {a[field]};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print('Host acceptance candidate bytes:',len(a['blob']))
