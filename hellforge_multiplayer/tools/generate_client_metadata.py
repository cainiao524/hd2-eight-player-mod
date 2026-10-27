"""Relocate saved client metadata startup/send and its readiness handshake.

Uses only existing workspace capture bytes; no game reads or publication.
All five bodies share metadata/readiness bindings and guarded internal entries.
"""
import argparse
import struct
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP
from generate_loadout_lifecycle import Capture,PROJECT,need

SOURCES=((0x1082f30,0x1082fa7),(0x1086aa0,0x1086b29),(0x1086920,0x10869a3),
         (0x1086b70,0x1086c71),(0x1086b30,0x1086b63))
UNWIND=('0104010004420000','010a04000a3406000a320670','010a04000a3406000a320670',
        '0106020006520230','0106020006320230')
HEADER=PROJECT/'mod/src/ep_client_metadata_template.h'


def build():
    c=Capture();blob=bytearray();fixes=[];mapping={};entries={};edges=[];rows=[];seen=set()
    def absolute(op,key,add=0):
        at=len(blob);blob.extend(bytes.fromhex(op)+bytes(8));fixes.append((at+2,0,key,1,add))
    def number(op,key=6):
        op=bytes.fromhex(op);at=len(blob);blob.extend(op+bytes(4));fixes.append((at+len(op),0,key,2,0))
    def check(jcc):
        blob.extend(bytes((jcc,13)));absolute('49bb',7);blob.extend(bytes.fromhex('41ffe3'))
    replacements={
        0x1086ac0:('mov edx, dword ptr [rbx + 0x158]',4,'418b5308'),
        0x1086acf:('mov dword ptr [rbx + 0x158], ecx',4,'41894b08'),
        0x1086ad9:('mov r8d, dword ptr [rbx + 0x15c]',4,'458b430c'),
        0x1086ae6:('mov dword ptr [rbx + 0x15c], ecx',4,'41894b0c'),
        0x1086942:('add rdx, 4',None,''),
        0x108694a:('add rdx, rbx',5,'4c01da'),
        0x1086974:('lea rax, [rcx + 4]',None,'89c8'),
        0x108697c:('add rax, rbx',5,'4c01d8'),
        0x1086b96:('add r9, 4',None,''),
        0x1086b9d:('cmp byte ptr [rbx + r9*8 + 8], 0',5,'43807ccb0800'),
        0x1086ba5:('cmp byte ptr [rbx + r9*8 + 9], 0',5,'43807ccb0900'),
        0x1086bb6:('add rcx, 4',None,''),
        0x1086bbf:('movups xmm0, xmmword ptr [rbx + rcx*8]',5,'410f1004cb'),
        0x1086bc3:('movups xmmword ptr [rbx + r9*8], xmm0',5,'430f1104cb'),
    }
    for kind,(start,end) in enumerate(SOURCES):
        blob+=b'\xcc'*(-len(blob)%16);entry=len(blob);entries[start]=entry
        absolute('49bb',2);blob+=bytes.fromhex('4c39d9');check(0x74)
        absolute('49bb',3);blob+=bytes.fromhex('4c39da' if kind==0 else '4c3919');check(0x74)
        if kind!=0:number('817938');check(0x76)
        body=len(blob);rows.append((entry,body,bytes.fromhex('01000000')))
        ins=list(c.md.disasm(c.read(start,end-start),start));need(sum(i.size for i in ins)==end-start,'Incomplete metadata source')
        for i in ins:
            mapping[i.address]=len(blob)
            if i.address==0x1082f47:
                need(i.address+i.size+i.disp==0x347cef0,'Changed constructor owner global');absolute('48b8',3);continue
            if i.address==0x1082f86:
                need(i.op_str=='qword ptr [r8 + 0x150], rcx','Changed metadata constructor')
                # Preserve native field bytes; initialize all member IDs only.
                absolute('49bb',4);number('41b9');blob+=bytes.fromhex('4989134983c31041ffc975f4')
                absolute('49bb',4);blob+=bytes.fromhex('49890b');continue
            if i.address in (0x1082f8d,0x1082f94,0x1082f9b):
                need(i.mnemonic=='mov' and i.op_str.endswith(', rdx'),'Changed constructor ID clear');continue
            if i.address==0x1086971:
                # A full bank may still satisfy lookup; only append rejects.
                number('81f9');check(0x72)
            if i.address in replacements:
                expected,key,op=replacements[i.address];need(i.mnemonic+' '+i.op_str==expected,'Changed metadata operand '+hex(i.address))
                seen.add(i.address)
                if key is not None:absolute('49bb',key)
                blob+=bytes.fromhex(op);continue
            if (i.mnemonic=='call' or i.mnemonic.startswith('j')) and i.operands[0].type==X86_OP_IMM:
                if i.mnemonic in ('call','jmp'):op=bytes.fromhex('e8' if i.mnemonic=='call' else 'e9')
                else:
                    cond=i.bytes[0]-0x70 if i.bytes[0] in range(0x70,0x80) else i.bytes[1]-0x80
                    need(0<=cond<16,'Unsupported metadata branch');op=bytes((0x0f,0x80+cond))
                at=len(blob);blob+=op+bytes(4);edges.append((at+len(op),len(blob),i.operands[0].imm))
            else:
                at=len(blob);blob+=i.bytes
                if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
                    fixes.append((at+i.disp_offset,at+i.size,0,0,i.address+i.size+i.disp))
        mapping[end]=len(blob)
        fs=[f for f in c.functions if start<=f[0]<end];need(len(fs)==1 and fs[0][:2]==(start,end),'Changed metadata function extent')
        uw=bytes.fromhex(UNWIND[kind]);need(c.read(fs[0][2],len(uw))==uw,'Changed metadata unwind')
        rows.append((body,len(blob),uw))
    need(seen==set(replacements),'Missing metadata replacement')
    for off,nxt,target in edges:
        if target in entries:struct.pack_into('<i',blob,off,entries[target]-nxt)
        elif target in mapping:struct.pack_into('<i',blob,off,mapping[target]-nxt)
        else:
            need(not any(s<=target<e for s,e in SOURCES),'Metadata branch into replaced instruction')
            fixes.append((off,nxt,0,0,target))
    blob+=bytes(-len(blob)%4);runtime=[]
    for start,end,uw in rows:runtime.append((start,end,len(blob)));blob+=uw
    table=len(blob)
    for row in runtime:blob+=struct.pack('<III',*row)
    need(len(blob)<=4096 and len(runtime)==10,'Metadata image capacity')
    return dict(blob=bytes(blob),fixes=fixes,entries=list(entries.values()),table=table,rows=runtime)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_client_metadata.py.','static const uint8_t ep_client_metadata_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpClientMetadataFixup ep_client_metadata_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    lines+=['static const uint32_t ep_client_metadata_entries[] = {'+','.join(map(str,a['entries']))+'};',
            f'static const uint32_t ep_client_metadata_table = {a["table"]};']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print('Client metadata candidate bytes:',len(a['blob']))
