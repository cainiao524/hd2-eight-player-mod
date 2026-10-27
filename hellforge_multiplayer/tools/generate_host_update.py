"""Relocate saved host update and its pending-consumer/serializer paths.

All member banks share the same owner. Expand per-call stack scratch before
allowing larger counted arrays; packet decoding and helper activation are separate.
"""
import argparse
import struct
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP
from generate_loadout_lifecycle import Capture,PROJECT,need
from host_task_layout import TASK_STRIDE,SECONDARY_COUNT,SECONDARY_START,PENDING_STRIDE,PENDING_KEY

START,END=0x108a440,0x108b512
HEADER=PROJECT/'mod/src/ep_host_update_template.h'
UNWIND={
    START:'1926060015016b0006c0047003300250',
    0x108a5a7:'212b08002bf46a001ce4730010d4720008647100',
    0x108a5d2:'2108020008683400',
    0x108ab57:'21000000',
    0x108b4f6:'21000000',
}
# RBP remains RSP+100h. Keep all existing locals/saves fixed relative to RSP,
# add scratch above them, and move the cookie above the new buffers.
FRAME=0x558
COOKIE=0x538
IDS=0x2a0   # RSP+3A0: count/reserved, eight QWORD IDs (80 bytes reserved).
TIMERS=0x2f0  # RSP+3F0: count, eight DWORD timers (48 bytes reserved).


def build():
    c=Capture();blob=bytearray();fixes=[];mapping={};edges=[]
    def absolute(op,key,add=0):
        at=len(blob);blob.extend(bytes.fromhex(op)+bytes(8));fixes.append((at+2,0,key,1,1,add))
    def number(op,key=8,add=0):
        op=bytes.fromhex(op);at=len(blob);blob.extend(op+bytes(4));fixes.append((at+len(op),0,key,2,1,add))
    def check(jcc,leaf=False):
        blob.extend(bytes((jcc,13 if leaf else 15)));absolute('49bb',9)
        blob.extend(b'\x41\xff\xe3' if leaf else b'\x41\xff\xd3\x0f\x0b')
    def edge(op,target):
        op=bytes.fromhex(op);at=len(blob);blob.extend(op+bytes(4));edges.append((at+len(op),len(blob),target))
    def displacement(i,old,new):
        need(i.disp==old and i.disp_size in (1,4),'Changed host update field '+hex(i.address))
        out=bytearray(i.bytes)
        if i.disp_size==1:out[i.modrm_offset]=(out[i.modrm_offset]&0x3f)|0x80
        out[i.disp_offset:i.disp_offset+i.disp_size]=struct.pack('<i',new)
        return out
    absolute('49bb',1);blob+=bytes.fromhex('4c39d9');check(0x74,True)
    absolute('49bb',2);blob+=bytes.fromhex('4c3919');check(0x74,True)
    for offset in (0x162d8,0x16390):number('4181bb'+struct.pack('<I',offset).hex());check(0x76,True)
    need(len(blob)<=128,'Update entry guard');blob+=b'\x90'*(128-len(blob));body=len(blob)
    bases={
        0x108a609:('rdi, [r12 + 0x40]','48bf',4,32),
        0x108a731:('rdi, [r12 + 0x140]','48bf',6,SECONDARY_COUNT),
        0x108a7e9:('rsi, [r12 + 0x78]','48be',4,88),
        0x108aa41:('rax, [r12 + 0x20]','48b8',4,0),
        0x108abcd:('rcx, [r12 + 0x20]','48b9',4,0),
        0x108abe8:('rdx, [r12 + 0x20]','48ba',4,0),
        0x108ae3a:('rbx, [r12 + 0x28]','48bb',4,8),
        0x108aec8:('rcx, [r12 + 0x40]','48b9',4,32),
        0x108af53:('r14, [r12 + 0x808]','49be',7,0),
        0x108b245:('rcx, [r12 + 0x108]','48b9',6,0),
    }
    bounds={0x108a60e:'be',0x108a72b:'41bf',0x108aa56:'81f9',0x108abdd:'3d',
            0x108ae3f:'bf',0x108aee7:'3d',0x108af5b:'41bd',0x108b25f:'3d'}
    scratch={
        0x108aba4:(0x1a8,IDS),0x108abaa:(0x190,TIMERS),0x108abf6:(0x1b0,IDS+8),
        0x108abfe:(0x1a8,IDS),0x108ac09:(0x194,TIMERS+4),0x108ac10:(0x190,TIMERS),
        0x108ac18:(0x1a8,IDS),0x108ac1e:(0x190,TIMERS),
        0x108ac91:(0,IDS),0x108acb7:(0,IDS),0x108acd3:(8,IDS+8),0x108acf4:(0,IDS),
        0x108acfa:(-0x50,TIMERS),0x108ad1f:(-0x50,TIMERS),0x108ad43:(-0x4c,TIMERS+4),0x108ad64:(-0x50,TIMERS),
        0x108b316:(0x30,IDS),0x108b326:(0x30,IDS),0x108b343:(0x38,IDS+8),0x108b364:(0x30,IDS),
    }
    pair_fields={0x108a756:8,0x108a760:0x18,0x108a767:0x20,0x108a76b:0x1c,0x108a770:0x10,0x108a77e:0x18}
    ins=list(c.md.disasm(c.read(START,END-START),START));need(sum(i.size for i in ins)==END-START,'Incomplete host update')
    for i in ins:
        if (0x108ab6c<i.address<0x108ab98 or 0x108ac38<=i.address<0x108ac54 or
            0x108ac54<i.address<0x108ac75 or 0x108b266<i.address<0x108b2a2 or 0x108b2a2<i.address<0x108b2cd):continue
        mapping[i.address]=len(blob)
        if i.address==0x108a446:blob+=displacement(i,-0x258,-0x458);continue
        if i.address in (0x108a44e,0x108b505):
            need(i.operands[-1].imm==0x358,'Changed update frame');out=bytearray(i.bytes);struct.pack_into('<I',out,i.imm_offset,FRAME);blob+=out;continue
        if i.address in (0x108a45f,0x108b4f6):blob+=displacement(i,0x238,COOKIE-0x100);continue
        if i.address in bases:
            expected,op,key,add=bases[i.address];need(i.op_str==expected,'Changed update bank');absolute(op,key,add);continue
        if i.address in bounds:
            need(i.operands[-1].imm==4,'Changed update bound');number(bounds[i.address]);continue
        if i.address==0x108a7ee:number('41be',add=-1);continue
        if i.address in pair_fields:
            old=pair_fields[i.address];blob+=displacement(i,old,old+SECONDARY_START-SECONDARY_COUNT-8);continue
        if i.address==0x108a740:number('813f',17);check(0x76)
        if i.address in (0x108a78c,0x108b258):
            need(i.operands[-1].imm==0x1c0,'Changed task stride');out=bytearray(i.bytes);struct.pack_into('<I',out,i.imm_offset,TASK_STRIDE);blob+=out;continue
        if i.address==0x108ab6c:
            blob+=bytes.fromhex('0f57c0')
            for offset in range(IDS,TIMERS+48,16):blob+=bytes.fromhex('0f1185')+struct.pack('<I',offset)
            continue
        if i.address==0x108abb0:
            need(i.op_str=='rbx, qword ptr [rcx + r14*8 + 0x162e0]','Changed client IDs')
            absolute('49bb',10);blob+=bytes.fromhex('4b8b1cf3');continue
        if i.address==0x108abf2:
            number('81ff');check(0x72);number('81fe');check(0x72)
        if i.address in scratch:blob+=displacement(i,*scratch[i.address]);continue
        if i.address==0x108ac54:blob+=bytes.fromhex('488d4dd0');continue
        if i.address==0x108af7a:number('41817e08');check(0x76)
        if i.address in (0x108af88,0x108afca,0x108b111,0x108b16b,0x108b42b,0x108b43e):
            blob+=displacement(i,0x38,PENDING_KEY);continue
        if i.address in (0x108b060,0x108b205,0x108b4a2):
            blob+=i.bytes
            for offset in range(0x40,PENDING_STRIDE,16):blob+=bytes.fromhex('410f1146')+bytes((offset,))
            continue
        if i.address==0x108b264:
            # No free task: preserve the request and retry on a later update.
            # Never send success and erase a request that was not installed.
            edge('e9',0x108b4c3);continue
        if i.address==0x108b266:
            # RCX is the selected empty task. Clear the entire expanded row,
            # then transfer the bounded count/reserved/IDs, without a temporary.
            blob+=bytes.fromhex('0f57c04989cb41ba')+struct.pack('<I',TASK_STRIDE//16)
            loop=len(blob);blob+=bytes.fromhex('410f11034983c31041ffca');blob+=b'\x75'+struct.pack('b',loop-len(blob)-2)
            blob+=bytes.fromhex('498b06488901498b460848894108458b460831c0')
            loop=len(blob);blob+=bytes.fromhex('4439c0');edge('0f83',0x108b2a2)
            blob+=bytes.fromhex('498b54c610488954c110ffc0');blob+=b'\xeb'+struct.pack('b',loop-len(blob)-2);continue
        if i.address==0x108b2a2:
            # The native allocator/descriptor builder now reads a complete
            # count-plus-eight-IDs buffer; nested RPC field count remains TWO.
            blob+=bytes.fromhex('498b064889442438498b9e')+struct.pack('<I',PENDING_KEY)
            blob+=bytes.fromhex('4c8d95')+struct.pack('<I',IDS)+bytes.fromhex('4d8d5e0841b809000000')
            loop=len(blob);blob+=bytes.fromhex('498b034989024983c3084983c20841ffc8');blob+=b'\x75'+struct.pack('b',loop-len(blob)-2)
            blob+=bytes.fromhex('488d4de8');continue
        if i.address==0x108b4c8:
            need(i.operands[-1].imm==0x40,'Changed pending stride');blob+=bytes.fromhex('4983c6')+bytes((PENDING_STRIDE,));continue
        at=len(blob)
        if (i.mnemonic=='call' or i.mnemonic.startswith('j')) and i.operands[0].type==X86_OP_IMM:
            if i.mnemonic in ('call','jmp'):op='e8' if i.mnemonic=='call' else 'e9'
            else:
                cond=i.bytes[0]-0x70 if i.bytes[0] in range(0x70,0x80) else i.bytes[1]-0x80
                need(0<=cond<16,'Unsupported update branch');op=bytes((0x0f,0x80+cond)).hex()
            edge(op,i.operands[0].imm)
        else:
            blob+=i.bytes
            if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
                fixes.append((at+i.disp_offset,at+i.size,0,0,1,i.address+i.size+i.disp))
    mapping[END]=len(blob)
    helpers={0x108b6b0:11,0x108d190:12,0x1089400:13,0x108c760:14,0x108d9f0:15,0x108d840:16}
    for off,nxt,target in edges:
        if target in mapping:struct.pack_into('<i',blob,off,mapping[target]-nxt)
        else:
            need(not START<=target<END,'Edge into replaced update block')
            fixes.append((off,nxt,helpers.get(target,0),0,1,0 if target in helpers else target))
    handler=len(blob);blob+=b'\xe9'+bytes(4);fixes.append((handler+1,handler+5,0,0,1,0x21044a0))
    blob+=bytes(-len(blob)%4);rows=[(0,body,len(blob))];blob+=bytes((1,0,0,0));original={}
    fs=[f for f in c.functions if START<=f[0]<END];need(len(fs)==5 and fs[-1][1]==END,'Update unwind extent')
    for sb,se,u in fs:
        h=c.read(u,4);n=4+((h[2]+1)&~1)*2;uw=c.read(u,n);need(uw==bytes.fromhex(UNWIND[sb]),'Changed update unwind')
        row=(mapping[sb],mapping[se],len(blob));rows.append(row);original[(sb,se,u)]=row
        if sb==START:
            need(c.read(u+n,8)==struct.pack('<II',0x21044a0,0x338),'Changed update cookie')
            uw=bytearray(uw);struct.pack_into('<H',uw,6,FRAME//8);blob+=uw+struct.pack('<II',handler,COOKIE)
        else:
            blob+=uw;parent=struct.unpack('<III',c.read(u+n,12));need(parent in original,'Unowned update unwind chain')
            blob+=struct.pack('<III',*original[parent])
    rows.append((handler,handler+5,len(blob)));blob+=bytes((1,0,0,0));table=len(blob)
    for row in rows:blob+=struct.pack('<III',*row)
    need(len(blob)<=8192 and len(rows)==7,'Update image layout')
    return dict(blob=bytes(blob),fixes=fixes,mapping=mapping,rows=rows,table=table,body=body,handler=handler)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_host_update.py.','static const uint8_t ep_host_update_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpHostUpdateFixup ep_host_update_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for field in ('table','body','handler'):lines.append(f'static const uint32_t ep_host_update_{field} = {a[field]};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print('Host update candidate bytes:',len(a['blob']))
