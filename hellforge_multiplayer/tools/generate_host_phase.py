"""Relocate saved host phase notifications and completion into one image.

Member scans and ordered task pairs expand; descriptor widths, two resource
streams, 64-resource batches and flow-control resumptions retain native ABI.
"""
import argparse
import struct
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP
from generate_loadout_lifecycle import Capture,PROJECT,need
from host_task_layout import SECONDARY_COUNT,SECONDARY_START

SOURCES=((0x108d840,0x108d9f0),(0x108d9f0,0x108deaa))
HEADER=PROJECT/'mod/src/ep_host_phase_template.h'
UNWIND={
    0x108d840:'010e06000e7207e00570046003300250',
    0x108d888:'2105020005f40e00',0x108d93a:'21000000',
    0x108d9f0:'192807001701140108f006c00460033002500000',
    0x108dae7:'211f06001f68890017e41d0108741c01',
    0x108de78:'21000000',0x108de96:'210006000068890000e41d0100741c01',
}


def build():
    c=Capture();blob=bytearray();fixes=[];mapping={};entries={};edges=[];groups=[]
    def absolute(op,key,add=0):
        at=len(blob);blob.extend(bytes.fromhex(op)+bytes(8));fixes.append((at+2,0,key,1,1,add))
    def number(op,key=8):
        op=bytes.fromhex(op);at=len(blob);blob.extend(op+bytes(4));fixes.append((at+len(op),0,key,2,1,0))
    def reject(leaf=False):
        absolute('49bb',9);blob.extend(b'\x41\xff\xe3' if leaf else b'\x41\xff\xd3\x0f\x0b')
    def check(jcc,leaf=False):
        blob.extend(bytes((jcc,13 if leaf else 15)));reject(leaf)
    def edge(op,target,call=False):
        op=bytes.fromhex(op);at=len(blob);blob.extend(op+bytes(4));edges.append((at+len(op),len(blob),target,call))
    for start,end in SOURCES:
        blob+=b'\xcc'*(-len(blob)%16);entry=len(blob);entries[start]=entry
        absolute('49bb',1);blob+=bytes.fromhex('4c39d9');check(0x74,True)
        absolute('49bb',2);blob+=bytes.fromhex('4c3919');check(0x74,True)
        number('4181bb90630100');check(0x76,True)
        if start==0x108d9f0:blob+=bytes.fromhex('4885d2');check(0x75,True)
        need(len(blob)-entry<=128,'Phase guard size');blob+=b'\x90'*(128-(len(blob)-entry));body=len(blob)
        groups.append((start,end,entry,body))
        ins=list(c.md.disasm(c.read(start,end-start),start));need(sum(i.size for i in ins)==end-start,'Incomplete phase source')
        for i in ins:
            mapping[i.address]=len(blob)
            bases={0x108d8af:('rbx, [rsi + 0x20]','48bb',0),0x108d998:('rbx, [rcx + 0x40]','48bb',32),
                   0x108da1d:('rcx, 0x20','48b9',0),0x108da3d:('r12, [r15 + 0x20]','49bc',0),
                   0x108daa5:('rcx, [r15 + 0x20]','48b9',0),0x108dacb:('rax, [r15 + 0x40]','48b8',32)}
            if i.address in bases:
                expected,op,add=bases[i.address];need(i.op_str==expected,'Changed phase bank');absolute(op,4,add);continue
            if i.address in (0x108d8aa,0x108da2f,0x108dabb):
                need(i.operands[-1].imm==4,'Changed phase bound');number('bf' if i.address==0x108d8aa else '3d');continue
            if i.address==0x108d8b3:
                # Native EDI=4 also supplied TWO fields. Do not grow the RPC.
                need(i.op_str=='r14d, [rdi - 2]','Changed phase field count');blob+=bytes.fromhex('41be02000000');continue
            if i.address==0x108d99c:
                need(i.op_str=='rsi, rdi','Changed second phase loop');number('be');continue
            if i.address in (0x108da34,0x108dac0):
                # The original paths dereference a null peer. A stale ID must
                # quarantine instead; effects before rejection cannot replay.
                reject();continue
            if i.address==0x108da82:blob+=bytes.fromhex('4885c0');check(0x75)
            if i.address==0x108da85:
                need(i.disp==0x38,'Changed ordered-pair count');out=bytearray(i.bytes);out[i.disp_offset]=SECONDARY_COUNT;blob+=out
                number('4181fa',11);check(0x76);continue
            if i.address==0x108da8e:
                need(i.disp==0x50,'Changed pair state cursor');out=bytearray(i.bytes);out[i.disp_offset]=SECONDARY_START+16;blob+=out;continue
            if (i.mnemonic=='call' or i.mnemonic.startswith('j')) and i.operands[0].type==X86_OP_IMM:
                if i.mnemonic in ('call','jmp'):op='e8' if i.mnemonic=='call' else 'e9'
                else:
                    cond=i.bytes[0]-0x70 if i.bytes[0] in range(0x70,0x80) else i.bytes[1]-0x80
                    need(0<=cond<16,'Unsupported phase branch');op=bytes((0x0f,0x80+cond)).hex()
                edge(op,i.operands[0].imm,i.mnemonic=='call')
            else:
                at=len(blob);blob+=i.bytes
                if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
                    fixes.append((at+i.disp_offset,at+i.size,0,0,1,i.address+i.size+i.disp))
        # Adjacent source ranges have a distinct guarded entry. Keep the first
        # body's end separate from the next body's mapping for unwind bounds.
        groups[-1]+= (len(blob),)
        mapping[end]=len(blob)
    for off,nxt,target,call in edges:
        if call and target in entries:struct.pack_into('<i',blob,off,entries[target]-nxt)
        elif target in mapping:struct.pack_into('<i',blob,off,mapping[target]-nxt)
        else:
            need(not any(s<=target<e for s,e in SOURCES),'Phase edge into replaced block')
            fixes.append((off,nxt,10 if target==0x108b560 else 0,0,1,0 if target==0x108b560 else target))
    handler=len(blob);blob+=b'\xe9'+bytes(4);fixes.append((handler+1,handler+5,0,0,1,0x21044a0))
    blob+=bytes(-len(blob)%4);rows=[];original={}
    for start,end,entry,body,body_end in groups:
        rows.append((entry,body,len(blob)));blob+=bytes((1,0,0,0))
        fs=[f for f in c.functions if start<=f[0]<end];need(fs[-1][1]==end,'Phase unwind extent')
        for sb,se,u in fs:
            h=c.read(u,4);n=4+((h[2]+1)&~1)*2;uw=c.read(u,n);need(uw==bytes.fromhex(UNWIND[sb]),'Changed phase unwind')
            row=(mapping[sb],body_end if se==end else mapping[se],len(blob));rows.append(row);original[(sb,se,u)]=row;blob+=uw
            if h[0]==25:
                need(c.read(u+n,8)==struct.pack('<II',0x21044a0,0x880),'Changed completion cookie');blob+=struct.pack('<II',handler,0x880)
            elif h[0]==33:
                parent=struct.unpack('<III',c.read(u+n,12));need(parent in original,'Unowned phase unwind chain');blob+=struct.pack('<III',*original[parent])
    rows.append((handler,handler+5,len(blob)));blob+=bytes((1,0,0,0));table=len(blob)
    for row in rows:blob+=struct.pack('<III',*row)
    need(len(blob)<=4096 and len(rows)==10,'Phase image size')
    return dict(blob=bytes(blob),fixes=fixes,mapping=mapping,entries=list(entries.values()),rows=rows,table=table,handler=handler)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_host_phase.py.','static const uint8_t ep_host_phase_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpHostPhaseFixup ep_host_phase_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    lines+=['static const uint32_t ep_host_phase_entries[] = {'+','.join(map(str,a['entries']))+'};']
    for field in ('table','handler'):lines.append(f'static const uint32_t ep_host_phase_{field} = {a[field]};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print('Host phase candidate bytes:',len(a['blob']))
