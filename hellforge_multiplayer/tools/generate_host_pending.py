"""Relocate the complete saved 108BC70 request/admission producer.

No game access. The incoming decoded count/member span must already be sized
for the negotiated capacity by its caller; this image is not a packet decoder.
"""
import argparse
import struct
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP
from generate_loadout_lifecycle import Capture,PROJECT,need
from host_task_layout import PENDING_STRIDE,PENDING_KEY

START,END=0x108bc70,0x108c5d7
HEADER=PROJECT/'mod/src/ep_host_pending_template.h'
UNWIND={
    0x108bc70:'192006001201190006c0046003300250',
    0x108bcd2:'211f06001ff4150017e4160008d41700',
    0x108bdd6:'2108020008741800',
    0x108bdf2:'21000000',
    0x108be06:'2100020000741800',
    0x108c5be:'21000000',
}


def build():
    c=Capture();blob=bytearray();fixes=[];mapping={};edges=[];payload_reload=None
    def absolute(op,key,add=0):
        at=len(blob);blob.extend(bytes.fromhex(op)+bytes(8));fixes.append((at+2,0,key,1,1,add))
    def number(op,key=8,add=0):
        op=bytes.fromhex(op);at=len(blob);blob.extend(op+bytes(4));fixes.append((at+len(op),0,key,2,1,add))
    def check(jcc,leaf=False):
        blob.extend(bytes((jcc,13 if leaf else 15)));absolute('49bb',9)
        blob.extend(b'\x41\xff\xe3' if leaf else b'\x41\xff\xd3\x0f\x0b')
    def edge(op,target):
        op=bytes.fromhex(op);at=len(blob);blob.extend(op+bytes(4));edges.append((at+len(op),len(blob),target))
    absolute('49bb',1);blob+=bytes.fromhex('4c39d9');check(0x74,True)
    absolute('49bb',2);blob+=bytes.fromhex('4c3919');check(0x74,True)
    number('4181bb90630100');check(0x76,True)
    blob+=bytes.fromhex('4d85c9');check(0x75,True)
    number('418139');check(0x76,True)
    need(len(blob)<=160,'Pending entry guard');blob+=b'\x90'*(160-len(blob));body=len(blob)
    ins=list(c.md.disasm(c.read(START,END-START),START))
    need(sum(i.size for i in ins)==END-START,'Incomplete request producer')
    bases={
        0x108bf64:('rax, [r8 + 0x16398]','48b8',3,0),
        0x108bf83:('rcx, [r8 + 0x16398]','48b9',3,0),
        0x108c2a3:('rsi, [r9 + 0x20]','48be',4,0),
        0x108c2a7:('r13, [r9 + 0x100]','49bd',5,0),
        0x108c33f:('rax, [r9 + 0x20]','48b8',4,0),
        0x108c3a9:('rdx, [r9 + 0x20]','48ba',4,0),
        0x108c48d:('rax, [rbx + 0x808]','48b8',7,0),
    }
    bounds={0x108c1b5:'b9',0x108c2cb:'3d',0x108c393:'3d',0x108c3e2:'81f9',0x108c4a1:'4181fe'}
    for i in ins:
        if 0x108c18f<i.address<0x108c1b5 or 0x108c4ac<i.address<0x108c4f8:continue
        mapping[i.address]=len(blob)
        if i.address in bases:
            expected,op,key,add=bases[i.address];need(i.op_str==expected,'Changed request bank')
            absolute(op,key,add);continue
        if i.address in bounds:
            need(i.operands[-1].imm==4,'Changed request count');number(bounds[i.address]);continue
        if i.address in (0x108bcc6,0x108bf4f,0x108c409):
            blob+=i.bytes;at=len(blob)-i.size
            fixes.append((at+i.disp_offset,at+i.size,0,0,1,i.address+i.size+i.disp))
            absolute('49bb',2)
            blob+=bytes.fromhex({0x108bcc6:'4c39d9',0x108bf4f:'4d39d8',0x108c409:'4c39db'}[i.address]);check(0x74)
            continue
        if i.address==0x108bf59:
            blob+=i.bytes;number('81fa');check(0x76);continue
        if i.address==0x108c18f:
            # The source reserves slot zero for the current host, then counts
            # occupied peers 1..3. Preserve that rule over 1..capacity-1.
            blob+=bytes.fromhex('b801000000');absolute('49bb',4,56);number('41ba',add=-1)
            loop=len(blob);blob+=bytes.fromhex('49833b007402ffc04983c33841ffca')
            blob+=b'\x75'+struct.pack('b',loop-len(blob)-2);continue
        if i.address==0x108c29f:
            # Reserve existence, before peer changes. Whole calls require the
            # same serialized owner lease; never silently lose a full queue.
            absolute('49bb',7);number('b9');loop=len(blob)
            blob+=bytes.fromhex('49833b00');edge('0f84',0x108c2a3)
            blob+=bytes.fromhex('4983c3')+bytes((PENDING_STRIDE,))+bytes.fromhex('ffc9')
            blob+=b'\x75'+struct.pack('b',loop-len(blob)-2)
            blob+=bytes.fromhex('31c085c0');check(0x75)
            # The branch target must include this original payload load.
            payload_reload=len(blob);blob+=i.bytes;continue
        if i.address==0x108c3b0:
            blob+=bytes.fromhex('4885d2');check(0x75)
        if i.address==0x108c3ee:
            need(i.op_str=='byte ptr [rax + r9 + 0x100], 1','Changed assigned flag')
            absolute('49bb',5);blob+=bytes.fromhex('41c6040301');continue
        if i.address==0x108c49d:
            need(i.operands[-1].imm==0x40,'Changed pending stride');blob+=bytes.fromhex('4883c0')+bytes((PENDING_STRIDE,));continue
        if i.address==0x108c4a7:
            # A full queue after the preflight violates the whole-call lease.
            blob+=bytes.fromhex('31c085c0');check(0x75);continue
        if i.address==0x108c4ac:
            # RAX already points at the selected empty row; RDX is the native
            # opaque key. Copy only count+members, never the old fixed 48 bytes.
            blob+=bytes.fromhex('0f57c0')
            for off in range(0,PENDING_STRIDE,16):blob+=bytes.fromhex('0f1140')+bytes((off,))
            blob+=bytes.fromhex('4c8b458f4c89004c8b45af498b0848894808488950')+bytes((PENDING_KEY,))
            blob+=bytes.fromhex('458b104531db')
            loop=len(blob);blob+=bytes.fromhex('4539d3');edge('0f83',0x108c4f8)
            blob+=bytes.fromhex('4b8b4cd8084a894cd81041ffc3')
            blob+=b'\xeb'+struct.pack('b',loop-len(blob)-2);continue
        at=len(blob)
        if (i.mnemonic=='call' or i.mnemonic.startswith('j')) and i.operands[0].type==X86_OP_IMM:
            target=i.operands[0].imm
            if i.mnemonic in ('call','jmp'):op='e8' if i.mnemonic=='call' else 'e9'
            else:
                cond=i.bytes[0]-0x70 if i.bytes[0] in range(0x70,0x80) else i.bytes[1]-0x80
                need(0<=cond<16,'Unsupported request branch');op=bytes((0x0f,0x80+cond)).hex()
            edge(op,target)
        else:
            blob+=i.bytes
            if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
                fixes.append((at+i.disp_offset,at+i.size,0,0,1,i.address+i.size+i.disp))
    mapping[END]=len(blob)
    # C2A3 must retain the payload reload skipped by the preflight's branch.
    need(blob[payload_reload:mapping[0x108c2a3]]==bytes.fromhex('4c8b55af'),'Pending reload position')
    for off,nxt,target in edges:
        if target==0x108c2a3:struct.pack_into('<i',blob,off,payload_reload-nxt)
        elif target in mapping:struct.pack_into('<i',blob,off,mapping[target]-nxt)
        else:
            need(not START<=target<END,'Branch into replaced request block')
            fixes.append((off,nxt,10 if target==0x108b6b0 else 0,0,1,0 if target==0x108b6b0 else target))
    handler=len(blob);blob+=b'\xe9'+bytes(4);fixes.append((handler+1,handler+5,0,0,1,0x21044a0))
    blob+=bytes(-len(blob)%4);rows=[];original={}
    rows.append((0,body,len(blob)));blob+=bytes((1,0,0,0))
    fs=[f for f in c.functions if START<=f[0]<END];need(len(fs)==6 and fs[-1][1]==END,'Request unwind extent')
    for sb,se,u in fs:
        h=c.read(u,4);n=4+((h[2]+1)&~1)*2;uw=c.read(u,n)
        need(uw==bytes.fromhex(UNWIND[sb]),'Changed request unwind')
        row=(mapping[sb],mapping[se],len(blob));rows.append(row);blob+=uw;original[(sb,se,u)]=row
        if sb==START:
            need(c.read(u+n,8)==struct.pack('<II',0x21044a0,0x98),'Changed request cookie')
            blob+=struct.pack('<II',handler,0x98)
        else:
            parent=struct.unpack('<III',c.read(u+n,12));need(parent in original,'Unowned request chain')
            blob+=struct.pack('<III',*original[parent])
    rows.append((handler,handler+5,len(blob)));blob+=bytes((1,0,0,0))
    table=len(blob)
    for row in rows:blob+=struct.pack('<III',*row)
    need(len(blob)<=8192 and len(rows)==8,'Request image layout')
    return dict(blob=bytes(blob),fixes=fixes,mapping=mapping,rows=rows,table=table,body=body,handler=handler)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_host_pending.py.','static const uint8_t ep_host_pending_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpHostPendingFixup ep_host_pending_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for field in ('table','body','handler'):lines.append(f'static const uint32_t ep_host_pending_{field} = {a[field]};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print('Host pending producer candidate bytes:',len(a['blob']))
