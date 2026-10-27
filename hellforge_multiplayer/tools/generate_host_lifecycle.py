"""Emit three saved host lifecycle bodies against separate bound banks.

Only workspace capture bytes are read. No hashes, discovery, SDK calls, hooks,
game access or receipts. Unrelated owner fields and service calls stay native.
"""
import argparse
import struct
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP
from generate_loadout_lifecycle import Capture,PROJECT,need
from host_task_layout import TASK_STRIDE

SOURCES=((0x1088a30,0x1088d75),(0x1088d80,0x1088efd),(0x108b520,0x108b551))
GS=bytes.fromhex('192f09001d648f021d548e021d348d021d018a0210700000')
HEADER=PROJECT/'mod/src/ep_host_lifecycle_template.h'
# Fixup keys: game, host, owner, confirmed, host peers, flags, large, pending,
# capacity, reject. Addresses are numeric; the emitter never dereferences them.


def build(kind):
    c=Capture();start,end=SOURCES[kind-1];source=c.read(start,end-start)
    ins=list(c.md.disasm(source,start));need(sum(i.size for i in ins)==len(source),'Incomplete host body')
    blob=bytearray();fixes=[];edges=[];mapping={};literal_refs=[]
    def absolute(op,key,add=0):
        at=len(blob);blob.extend(bytes.fromhex(op)+bytes(8));fixes.append((at+2,0,key,1,1,add))
    def number(op,key,multiplier=1):
        prefix=bytes.fromhex(op);at=len(blob);blob.extend(prefix+bytes(4));fixes.append((at+len(prefix),0,key,2,multiplier,0))
    def check(jcc,leaf=False):
        blob.extend(bytes((jcc,13 if leaf else 15)));absolute('49bb',9)
        blob.extend(b'\x41\xff\xe3' if leaf else b'\x41\xff\xd3\x0f\x0b')
    absolute('49bb',1);blob+=b'\x4c\x39\xd9';check(0x74,True)
    absolute('49bb',2);blob+=b'\x4c\x39\x19';check(0x74,True)
    number('4181bb90630100',8);check(0x76,True)
    need(len(blob)<=96,'Host preflight size');blob+=b'\x90'*(96-len(blob));body=len(blob)

    # Exact source windows establish operand provenance, not a blanket rewrite
    # of every matching displacement or immediate in the function.
    patches={
        0x1088b0b:('qword ptr [rdi + 0x20], rax','49bb',4,'498903'),
        0x1088b16:('qword ptr [rdi + 0x28], rax','49bb',4,'49894308'),
        0x1088b24:('dword ptr [rdi + 0x30], ecx','49bb',4,'41894b10'),
        0x1088b27:('dword ptr [rdi + 0x34], ebx','49bb',4,'41895b14'),
        0x1088b2a:('dword ptr [rdi + 0x40], 9','49bb',4,'41c7432009000000'),
        0x1088b40:('dword ptr [rdi + 0x38], xmm0','49bb',4,'f3410f114318'),
        0x1088b77:('qword ptr [rcx + 0x16398], rax','49bb',3,'498903'),
        0x1088b7e:('eax, dword ptr [rdi + 0x34]','48b9',4,'8b4114'),
        0x1088b84:('dword ptr [rcx + 0x163ac], eax','49bb',3,'41894314'),
        0x1088b92:('eax, dword ptr [rdi + 0x34]','48b9',4,'8b4114'),
        0x1088e2e:('qword ptr [rbx + 0x20], r9','48b8',4,'4c8908'),
        0x1088e39:('qword ptr [rbx + 0x28], rax','48ba',4,'48894208'),
        0x1088e47:('dword ptr [rbx + 0x30], ecx','48b8',4,'894810'),
        0x1088e4d:('dword ptr [rbx + 0x40], 9','48b8',4,'c7402009000000'),
        0x1088e79:('dword ptr [rbx + 0x34], 0xffffffff','48ba',4,'c74214ffffffff'),
        0x1088e83:('dword ptr [rbx + 0x34], eax','48ba',4,'894214'),
        0x1088ea9:('eax, dword ptr [rbx + 0x34]','48ba',4,'8b4214'),
        0x1088eeb:('eax, dword ptr [rdx + r10 + 0x163ac]','48b8',3,'8b441014'),
        0x1088ef3:('dword ptr [rbx + 0x34], eax','48ba',4,'894214'),
    }
    skips=()
    for i in ins:
        if any(b<i.address<e for b,e in skips):continue
        mapping[i.address]=len(blob)
        if i.address==0x1088a87:
            need(i.op_str=='rax, [rdi + 0x90]','Changed full clear anchor')
            skips=((0x1088a87,0x1088b01),)
            absolute('48b8',4);blob+=bytes.fromhex('0f57d231d24889542458f20f104c2458');number('b9',8)
            loop=len(blob);blob+=bytes.fromhex('0f11100f1150100f115020f20f1148304883c038ffc9')
            blob+=b'\x75'+struct.pack('b',loop-len(blob)-2);continue
        if i.address==0x1088dde:
            need(i.op_str=='rax, [rbx + 0x40]','Changed partial clear anchor')
            skips=((0x1088dde,0x1088e24),)
            absolute('48b8',4);number('b9',8);loop=len(blob)
            blob+=bytes.fromhex('4c8918448958204883c038ffc9');blob+=b'\x75'+struct.pack('b',loop-len(blob)-2);continue
        if i.address in (0x1088e83,0x1088ef3):
            # The found path first writes -1 then normalizes it, exactly as
            # native code does. Reject every OTHER out-of-capacity index before
            # its first write. Keep R11=0 and R10=owner live throughout resume.
            if i.address==0x1088ef3:blob+=b'\x83\xf8\xff\x74\x16'
            number('3d',8);check(0x72)
        if i.address in patches:
            expected,op,key,replacement=patches[i.address];need(i.op_str==expected,'Changed host field '+hex(i.address))
            absolute(op,key);blob+=bytes.fromhex(replacement);continue
        if i.address in (0x1088b8c,0x1088ea3):
            need(i.mnemonic=='mov' and '0x100' in i.op_str,'Changed flag clear')
            absolute('48b9',5);number('ba',8);loop=len(blob)
            blob+=bytes.fromhex('c6010048ffc1ffca');blob+=b'\x75'+struct.pack('b',loop-len(blob)-2);continue
        if i.address in (0x1088b95,0x1088eac):
            need(i.mnemonic=='mov' and '0x100' in i.op_str,'Changed indexed flag')
            number('3d',8);check(0x72);absolute('48b9',5);blob+=bytes.fromhex('c6040101');continue
        if i.address==0x1088bc5:
            need(i.op_str=='r8d, 0x700','Changed large clear length');number('41b8',8,TASK_STRIDE);continue
        if i.address==0x1088be6:
            need(i.op_str=='rcx, [rdi + 0x108]','Changed large clear base');absolute('48b9',6);continue
        if i.address==0x1088e54:
            need(i.op_str=='r8d, dword ptr [r10 + 0x16390]','Changed confirmed count')
            blob+=i.bytes;number('4181f8',8)
            # R11 zero is live on success; the failure target never returns.
            check(0x76);continue
        if i.address==0x1088e68:
            need(i.op_str=='qword ptr [rax + r10 + 0x16398], r9','Changed confirmed ID')
            at=len(blob);blob+=b'\x48\x03\x05'+bytes(4)+b'\x4c\x39\x08';literal_refs.append((at+3,at+7));continue
        if i.address==0x108b523:
            need(i.op_str=='r8, [rcx + 0x20]','Changed slot cursor');absolute('49b8',4);continue
        if i.address==0x108b53b:
            need(i.op_str=='eax, 4','Changed slot bound');number('3d',8);continue
        if i.address==0x108b549:
            need(i.op_str=='rax, 0x20','Changed slot header adjustment');continue
        if i.address==0x108b54d:
            # Keep native R9=host intact. Some engine callers can rely on the
            # exact volatile clobber set of this small leaf as well as RAX.
            need(i.op_str=='rax, r9','Changed slot return base')
            at=len(blob);blob+=b'\x48\x03\x05'+bytes(4);literal_refs.append((at+3,at+7));continue
        at=len(blob)
        if (i.mnemonic=='call' or i.mnemonic.startswith('j')) and i.operands[0].type==X86_OP_IMM:
            target=i.operands[0].imm
            if i.mnemonic in ('call','jmp'):
                blob+=(b'\xe8' if i.mnemonic=='call' else b'\xe9')+bytes(4);off=at+1
            else:
                condition=i.bytes[0]-0x70 if i.bytes[0] in range(0x70,0x80) else i.bytes[1]-0x80
                need(0<=condition<16,'Unsupported host branch');blob+=bytes((0x0f,0x80+condition))+bytes(4);off=at+2
            if start<=target<end:edges.append((off,len(blob),target))
            else:fixes.append((off,len(blob),0,0,1,target))
        else:
            blob+=i.bytes
            if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
                fixes.append((at+i.disp_offset,at+i.size,0,0,1,i.address+i.size+i.disp))
    mapping[end]=len(blob)
    for off,nxt,target in edges:
        need(target in mapping,'Edge into replaced clear loop');struct.pack_into('<i',blob,off,mapping[target]-nxt)
    handler=0
    if kind==1:
        blob+=b'\xcc'*(-len(blob)%16);handler=len(blob);blob+=b'\xe9'+bytes(4)
        fixes.append((handler+1,handler+5,0,0,1,0x21044a0))
    if literal_refs:
        blob+=bytes(-len(blob)%8);literal=len(blob);blob+=bytes(8);fixes.append((literal,0,4 if kind==3 else 3,1,1,0))
        for off,nxt in literal_refs:struct.pack_into('<i',blob,off,literal-nxt)
    blob+=bytes(-len(blob)%4);rows=[(0,body,len(blob))];blob+=bytes((1,0,0,0))
    rows.append((body,mapping[end],len(blob)))
    if kind==3:blob+=bytes((1,0,0,0))
    else:
        b,e,u=next(f for f in c.functions if f[0]==start);need(e==end,'Changed host function extent')
        h=c.read(u,4);uw=c.read(u,4+((h[2]+1)&~1)*2)
        if kind==1:
            need(uw==GS and c.read(u+len(uw),8)==struct.pack('<II',0x21044a0,0x1440),'Changed host GS')
            blob+=uw+struct.pack('<II',handler,0x1440)
            rows.append((handler,handler+5,len(blob)));blob+=bytes((1,0,0,0))
        else:
            need(uw==bytes.fromhex('0106020006320230'),'Changed resume frame');blob+=uw
    table=len(blob)
    for row in rows:blob+=struct.pack('<III',*row)
    need(len(blob)<=4096,'Host image size')
    return dict(blob=bytes(blob),fixes=fixes,body=body,handler=handler,table=table,rows=rows,mapping=mapping,source=start)


def render(all_images):
    lines=['// Generated from saved build 25480438 by generate_host_lifecycle.py.']
    for kind,a in enumerate(all_images,1):
        lines.append(f'static const uint8_t ep_host_{kind}_bytes[] = {{')
        lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)];lines+=['};']
        lines.append(f'static const EpHostFixup ep_host_{kind}_fixes[] = {{')
        lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    lines+=['static const EpHostTemplate ep_host_templates[] = {']
    for kind,a in enumerate(all_images,1):
        lines.append('    {'+f'ep_host_{kind}_bytes,ep_host_{kind}_fixes,'+','.join(map(str,(len(a['blob']),len(a['fixes']),a['table'],len(a['rows']),a['handler'],a['body'],a['source'])))+'},')
    return '\n'.join(lines+['};',''])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args()
    images=[build(k) for k in (1,2,3)]
    if args.write:HEADER.write_text(render(images),encoding='utf-8',newline='\n')
    print('Host lifecycle candidate bytes:',*[len(a['blob']) for a in images])
