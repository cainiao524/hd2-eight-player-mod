"""Relocate saved host migration and bind every member bank it accesses.

Source is the workspace capture only. Preserve native service calls and switch
semantics, not a reimplementation or permission to run a migration in a game.
"""
import argparse
import struct
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP
from generate_loadout_lifecycle import Capture,PROJECT,need
from host_task_layout import TASK_STRIDE

START,CODE_END,END=0x1089720,0x108a325,0x108a34a
HEADER=PROJECT/'mod/src/ep_host_migration_template.h'


def build():
    c=Capture();blob=bytearray();fixes=[];mapping={};edges=[];literal_refs=[];switch_refs=[]
    def absolute(op,key,add=0):
        at=len(blob);blob.extend(bytes.fromhex(op)+bytes(8));fixes.append((at+2,0,key,1,1,add))
    def number(op,key=8,multiplier=1):
        prefix=bytes.fromhex(op);at=len(blob);blob.extend(prefix+bytes(4));fixes.append((at+len(prefix),0,key,2,multiplier,0))
    def check(jcc,leaf=False):
        blob.extend(bytes((jcc,13 if leaf else 15)));absolute('49bb',9)
        blob.extend(b'\x41\xff\xe3' if leaf else b'\x41\xff\xd3\x0f\x0b')
    absolute('49bb',1);blob+=bytes.fromhex('4c39d9');check(0x74,True)
    absolute('49bb',2);blob+=bytes.fromhex('4c3919');check(0x74,True)
    for offset in (0x162d8,0x16300,0x16348,0x16390):
        number('4181bb'+struct.pack('<I',offset).hex());check(0x76,True)
    need(len(blob)<=160,'Migration entry guard');blob+=b'\x90'*(160-len(blob));body=len(blob)
    patches={
        0x108985e:('qword ptr [r13 + 0x20], rdx',4,'498913'),
        0x1089869:('qword ptr [r13 + 0x28], rax',4,'49894308'),
        0x1089877:('dword ptr [r13 + 0x30], ecx',4,'41894b10'),
        0x108987b:('dword ptr [r13 + 0x40], 9',4,'41c7432009000000'),
        0x10898af:('dword ptr [r13 + 0x38], eax',4,'41894318'),
        0x1089e97:('eax, dword ptr [rdx + r8 + 0x163ac]',3,'418b441314'),
        0x1089eab:('byte ptr [rax + r13 + 0x100], 1',5,'41c6040301'),
        0x1089ff4:('byte ptr [rax + r13 + 0x100], 1',5,'41c6040301'),
    }
    bases={
        0x10897a3:('rax, [r13 + 0x58]','48b8',4,0),
        0x1089838:('rcx, [r13 + 0x108]','48b9',6,0),
        0x1089889:('rcx, [r8 + 0x16458]','48b9',13,0),
        0x1089cdb:('rcx, [rax + 0x162e0]','48b9',10,0),
        0x1089ce8:('rdi, [rax + 0x16398]','48bf',3,0),
        0x1089cf3:('rcx, [rax + 0x16308]','48b9',11,0),
        0x1089d2e:('rax, [r13 + 0x20]','48b8',4,0),
        0x1089d46:('rdi, [r13 + 0x20]','48bf',4,0),
        0x1089d67:('rcx, [r8 + 0x16458]','48b9',13,0),
        0x1089fa3:('rcx, [r13 + 0x20]','48b9',4,0),
        0x1089fc8:('rdx, [r13 + 0x20]','48ba',4,0),
        0x1089fd7:('rcx, [r13 + 0x100]','48b9',5,0),
        0x108a029:('r14, [r13 + 0x40]','49be',4,32),
        0x108a05a:('rbx, [r13 + 0x40]','48bb',4,32),
        0x108a1b7:('rsi, [rax + 0x16350]','48be',12,0),
    }
    bounds={0x108989b:('eax, 4','3d'),0x1089d3d:('ecx, 4','81f9'),0x1089d7b:('edx, 4','81fa'),
            0x1089fbb:('eax, 4','3d'),0x1089fea:('eax, 4','3d'),0x108a02d:('r15d, 4','41bf'),0x108a05e:('edi, 4','bf')}
    instructions=list(c.md.disasm(c.read(START,CODE_END-START),START))
    need(sum(i.size for i in instructions)==CODE_END-START,'Incomplete migration body')
    for i in instructions:
        if 0x10897c0<i.address<0x1089838:continue
        mapping[i.address]=len(blob)
        if i.address==0x10897c0:
            # Same 56-byte record zeroing, without the original four-way unroll.
            blob+=bytes.fromhex('0f57d231d24889550ff20f104d0f');number('41b9')
            loop=len(blob);blob+=bytes.fromhex('0f11100f1150100f115020f20f1148304883c03841ffc9')
            blob+=b'\x75'+struct.pack('b',loop-len(blob)-2);continue
        if i.address==0x108983f:number('41b8',8,TASK_STRIDE);continue
        if i.address==0x108984c:
            need(i.op_str=='dword ptr [r13 + 0x100], ecx','Changed flag reset')
            absolute('49ba',5);number('41bb');loop=len(blob);blob+=bytes.fromhex('41880a49ffc241ffcb')
            blob+=b'\x75'+struct.pack('b',loop-len(blob)-2);continue
        if i.address in bases:
            expected,op,key,add=bases[i.address];need(i.op_str==expected,'Changed migration base '+hex(i.address))
            absolute(op,key,add);continue
        if i.address in patches:
            expected,key,replacement=patches[i.address];need(i.op_str==expected,'Changed migration field '+hex(i.address))
            absolute('49bb',key);blob+=bytes.fromhex(replacement);continue
        if i.address in bounds:
            expected,op=bounds[i.address];need(i.op_str==expected,'Changed migration bound');number(op);continue
        if i.address in (0x10898a2,0x1089d84):
            need(i.op_str=='rax, 0x1646','Changed timer offset');blob+=bytes.fromhex('48c1e004');continue
        if i.address in (0x10898a8,0x1089d8a):
            need(i.op_str=='rax, rax','Changed timer scale');absolute('49bb',13);continue
        if i.address in (0x10898ab,0x1089d8d):
            need(i.op_str=='eax, dword ptr [r8 + rax*8]','Changed timer value');blob+=bytes.fromhex('418b440308');continue
        if i.address==0x1089b40:
            # The original compiler switch uses module-base-relative data.
            # Bind both tables and their three targets to this private image.
            absolute('48be',16);continue
        if i.address in (0x1089b57,0x1089b5f):
            prefix=bytes.fromhex('0fb68430' if i.address==0x1089b57 else '8b8c86')
            blob+=prefix;switch_refs.append((len(blob),i.address==0x1089b57));blob+=bytes(4);continue
        if i.address==0x1089d60:blob+=bytes.fromhex('4885c0');check(0x75)
        if i.address==0x1089d9d:
            absolute('49bb',2);blob+=bytes.fromhex('4d39d8');check(0x74)
            blob+=i.bytes;number('4181f9');check(0x76);continue
        if i.address==0x1089db8:
            need(i.op_str=='qword ptr [rax + r8 + 0x16398], r10','Changed inline peer lookup')
            at=len(blob);blob+=b'\x48\x03\x05'+bytes(4)+bytes.fromhex('4c3910');literal_refs.append((at+3,at+7));continue
        if i.address==0x1089e7c:number('81fe');check(0x72)
        if i.address==0x1089e9f:
            # -1 is a native unassigned index, not an unsigned valid flag.
            blob+=bytes.fromhex('83f8ff7416');number('3d');check(0x72)
        if i.address==0x1089fcf:blob+=bytes.fromhex('4885d2');check(0x75)
        if i.address==0x1089fef:
            absolute('49bb',9);blob+=bytes.fromhex('41ffd30f0b');continue
        counts={0x1089cd4:'4181fe',0x1089ce2:'81fe',0x1089cfe:'81f9',0x1089f85:'81f9',0x1089f8e:'81f9',0x108a1b1:'81fb'}
        if i.address in counts:
            blob+=i.bytes;number(counts[i.address]);check(0x76);continue
        at=len(blob)
        if (i.mnemonic=='call' or i.mnemonic.startswith('j')) and i.operands[0].type==X86_OP_IMM:
            target=i.operands[0].imm
            if i.mnemonic in ('call','jmp'):
                blob+=(b'\xe8' if i.mnemonic=='call' else b'\xe9')+bytes(4);off=at+1
            else:
                condition=i.bytes[0]-0x70 if i.bytes[0] in range(0x70,0x80) else i.bytes[1]-0x80
                need(0<=condition<16,'Migration branch');blob+=bytes((0x0f,0x80+condition))+bytes(4);off=at+2
            if START<=target<CODE_END:edges.append((off,len(blob),target))
            elif target in (0x108b520,0x108d190):fixes.append((off,len(blob),14 if target==0x108b520 else 15,0,1,0))
            else:fixes.append((off,len(blob),0,0,1,target))
        else:
            blob+=i.bytes
            if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
                fixes.append((at+i.disp_offset,at+i.size,0,0,1,i.address+i.size+i.disp))
    body_end=len(blob)
    for off,nxt,target in edges:
        need(target in mapping,'Migration edge into replaced block');struct.pack_into('<i',blob,off,mapping[target]-nxt)
    blob+=bytes(-len(blob)%8);literal=len(blob);blob+=bytes(8);fixes.append((literal,0,3,1,1,0))
    for off,nxt in literal_refs:struct.pack_into('<i',blob,off,literal-nxt)
    switch=len(blob)
    for target in struct.unpack('<III',c.read(0x108a328,12)):
        need(target in mapping,'Unowned migration switch target');blob+=struct.pack('<I',mapping[target])
    switch_bytes=len(blob);indices=c.read(0x108a334,22);need(max(indices)<3,'Migration switch index');blob+=indices
    for off,is_byte in switch_refs:struct.pack_into('<I',blob,off,switch_bytes if is_byte else switch)
    blob+=bytes(-len(blob)%4);rows=[(0,body,len(blob))];blob+=bytes((1,0,0,0))
    need((START,END,0x24da344) in c.functions,'Migration unwind extent')
    uw=c.read(0x24da344,24);need(uw==bytes.fromhex('011d0a001d01130011f00fe00dd00bc00970086007300650'),'Migration frame changed')
    rows.append((body,body_end,len(blob)));blob+=uw;table=len(blob)
    for row in rows:blob+=struct.pack('<III',*row)
    need(len(blob)<=8192,'Migration image size')
    return dict(blob=bytes(blob),fixes=fixes,mapping=mapping,body=body,table=table)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_host_migration.py.','static const uint8_t ep_host_migration_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpHostMigrationFixup ep_host_migration_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('body','table'):lines.append(f'static const uint32_t ep_host_migration_{key} = {a[key]};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print('Host migration candidate bytes:',len(a['blob']))
