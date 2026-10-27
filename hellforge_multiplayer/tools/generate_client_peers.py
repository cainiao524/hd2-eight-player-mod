"""Relocate saved confirmed-peer lifecycle and lookup functions into one bank.

Preserves native bodies, calls, stack arguments and unwind fragments. The
generated code changes only peer addresses, clear length and bounded guards.
Reads the existing workspace capture only. Does not publish or access a game.
"""
import argparse
import struct
from generate_loadout_lifecycle import Capture, PROJECT, need
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

HEADER=PROJECT/'mod/src/ep_client_peers_template.h'
SOURCES=((0x10872c0,0x1087534),(0xb90b20,0xb90eab),
         (0x1087540,0x10877f8),(0x1087010,0x10872ba))
LEAVES=((0x1084fd0,0x1085006),(0x1085010,0x108505c),(0x1085090,0x10850e5))
RESET_GS=bytes.fromhex('192404001301490104f00250')


def build(kind):
    if kind>=5:return build_leaf(kind)
    c=Capture();start,end=SOURCES[kind-1];source=c.read(start,end-start)
    ins=list(c.md.disasm(source,start));starts={i.address for i in ins}
    need(sum(i.size for i in ins)==len(source),'Incomplete native peer body')
    need(all('r11' not in i.op_str for i in ins),'R11 is not available as scratch')
    # A registered callback receives a host identity in RCX, not the client.
    # Its client check therefore belongs after registry selection and before
    # the first dereference. Other entries can reject in a leaf preflight.
    fixes=[]
    if kind==2:
        blob=bytearray(b'\xe9'+struct.pack('<i',59)+b'\x90'*59)
    else:
        blob=bytearray(b'\x49\xbb'+bytes(8)+b'\x4c\x39\xd9\x0f\x85'+struct.pack('<i',16))
        blob+=b'\x81\xb9\xc8\0\0\0'+bytes(4)+b'\x0f\x86'+struct.pack('<i',29)
        blob+=b'\x49\xbb'+bytes(8)+b'\x41\xff\xe3'
        fixes=[(2,0,1,1,1,0),(25,0,3,2,1,0),(37,0,4,1,1,0)]
        blob+=b'\x90'*(64-len(blob))
    body=len(blob);blob+=source;patches=[];islands=[]

    def bound(code,local,branches,opcode,multiplier,condition=0x83):
        """Compare an unsigned ordinal/offset to capacity, branch to rejection."""
        at=len(code);code+=bytes.fromhex(opcode)+bytes(4)
        local.append((at+len(bytes.fromhex(opcode)),0,3,2,multiplier,0))
        code+=b'\x0f'+bytes((condition,))+bytes(4);branches.append(len(code)-4)

    def bank(code,local,register='r11'):
        at=len(code);code+=b'\x49\xbb' if register=='r11' else b'\x48\xba'
        code+=bytes(8);local.append((at+2,0,2,1,1,0))

    def island(begin,finish,expected,make):
        selected=[i for i in ins if begin<=i.address<finish]
        need(begin in starts and (finish in starts or finish==end) and
             '; '.join(i.mnemonic+' '+i.op_str for i in selected)==expected,'Changed peer window '+hex(begin))
        need(finish-begin>=5,'Short peer window')
        code,local,branches=bytearray(),[],[];make(code,local,branches)
        blob.extend(b'\xcc'*(-len(blob)%16));at=len(blob)
        code+=b'\xe9'+struct.pack('<i',body+finish-start-(at+len(code)+5))
        reject=len(code)
        # Native frames have shadow space and an aligned RSP here. A returning
        # rejection is a contract violation; do not continue after side effects.
        code+=b'\x49\xbb'+bytes(8)+b'\x41\xff\xd3\x0f\x0b'
        local.append((reject+2,0,4,1,1,0))
        for branch in branches:struct.pack_into('<i',code,branch,reject-branch-4)
        for off,n,key,form,mul,add in local:fixes.append((at+off,at+n if n else 0,key,form,mul,add))
        blob.extend(code);islands.append((begin,at,len(blob)))
        site=body+begin-start;blob[site:site+finish-begin]=b'\xe9'+struct.pack('<i',at-site-5)+b'\x90'*(finish-begin-5)
        patches.append((begin,finish))

    def lookup(compare):
        def emit(code,local,branches):
            bound(code,local,branches,'4881f8',32);bank(code,local)
            code.extend(bytes.fromhex(compare))
        return emit

    if kind==1:
        island(0x1087306,0x108730e,'cmp qword ptr [rax + rdi + 0xd0], rbx',lookup('49391c03'))
        def insert(code,local,branches):
            code.extend(bytes.fromhex('8b8fc8000000'))
            bound(code,local,branches,'81f9',1);bank(code,local,'rdx')
        island(0x1087333,0x1087340,'mov ecx, dword ptr [rdi + 0xc8]; lea rdx, [rdi + 0xd0]',insert)
    elif kind==2:
        def selected(code,local,branches):
            code.extend(b'\x49\xbb'+bytes(8)+b'\x4c\x39\xdb\x0f\x85'+bytes(4))
            local.append((2,0,1,1,1,0));branches.append(15)
            bound(code,local,branches,'81bbc8000000',1,0x87)
            code.extend(c.read(0xb90b7f,10))
        island(0xb90b7f,0xb90b89,'mov rax, qword ptr [rbx]; cmp r15, qword ptr [rax + 0xb3a8]',selected)
        island(0xb90bb6,0xb90bbe,'cmp qword ptr [rax + rbx + 0xd0], rdi',lookup('49393c03'))
        def insert(code,local,branches):
            bound(code,local,branches,'81f9',1);bank(code,local);code.extend(bytes.fromhex('4c01da'))
        island(0xb90bf6,0xb90c00,'add rdx, 0xd0; add rdx, rbx',insert)
    elif kind==3:
        island(0x10875f8,0x1087600,'cmp qword ptr [rax + rbx + 0xd0], rdi',lookup('49393c03'))
        def decrement(code,local,branches):
            code.extend(bytes.fromhex('8b83c800000085c00f84')+bytes(4));branches.append(len(code)-4)
            bound(code,local,branches,'3d',1,0x87)
            code.extend(bytes.fromhex('ffc88983c8000000'))
        island(0x1087612,0x108761e,'dec dword ptr [rbx + 0xc8]; mov eax, dword ptr [rbx + 0xc8]',decrement)
        def compact(code,local,branches):
            bound(code,local,branches,'4881f8',32);bound(code,local,branches,'4881fe',32)
            bank(code,local);code.extend(bytes.fromhex('410f100403410f110433410f104c0310410f114c3310'))
        island(0x1087626,0x1087646,'movups xmm0, xmmword ptr [rax + rbx + 0xd0]; movups xmmword ptr [rsi + rbx + 0xd0], xmm0; movups xmm1, xmmword ptr [rax + rbx + 0xe0]; movups xmmword ptr [rsi + rbx + 0xe0], xmm1',compact)
    else:
        island(0x10870a4,0x10870ac,'mov rdi, qword ptr [rax + r15 + 0xd0]',lookup('498b3c03'))
        begin,finish=0x1087260,0x10872a0
        stores=[i for i in ins if begin<=i.address<finish]
        need(len(stores)==8 and all(i.mnemonic=='movups' and i.op_str==f'xmmword ptr [r15 + {hex(0xd0+16*n)}], xmm0'
             for n,i in enumerate(stores)),'Changed reset clear')
        at=body+begin-start
        clear=b'\x49\xbb'+bytes(8)+b'\xb9'+bytes(4)+bytes.fromhex('410f11034983c310ffc975f4')
        blob[at:at+finish-begin]=clear+b'\x90'*(finish-begin-len(clear))
        fixes.extend(((at+2,0,2,1,1,0),(at+11,0,3,2,2,0)));patches.append((begin,finish))

    for i in ins:
        if any(b<=i.address<e for b,e in patches):continue
        at=body+i.address-start
        if (i.mnemonic=='call' or i.mnemonic.startswith('j')) and i.operands[0].type==X86_OP_IMM:
            target=i.operands[0].imm
            if start<=target<end:
                need(target in starts and not any(b<target<e for b,e in patches),'Interior patch edge')
            else:
                need(i.imm_size==4,'External short edge');fixes.append((at+i.imm_offset,at+i.size,0,0,1,target))
        if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
            fixes.append((at+i.disp_offset,at+i.size,0,0,1,i.address+i.size+i.disp))
    handler=0xffffffff
    if kind==4:
        blob+=b'\xcc'*(-len(blob)%16);handler=len(blob);blob+=b'\xe9'+bytes(4)
        fixes.append((handler+1,handler+5,0,0,1,0x21044a0))
    blob+=bytes(-len(blob)%4);rows=[(0,body,len(blob))];blob+=bytes((1,0,0,0))
    fs=[f for f in c.functions if start<=f[0]<end];need(fs[-1][1]==end,'Incomplete native unwind')
    originals={}
    for b,e,u in fs:
        h=c.read(u,4);n=4+((h[2]+1)&~1)*2;uw=c.read(u,n)
        row=(body+b-start,body+e-start,len(blob));rows.append(row);originals[(b,e,u)]=row;blob+=uw
        if h[0]==25:
            need(kind==4 and b==start and uw==RESET_GS and c.read(u+n,8)==struct.pack('<II',0x21044a0,0xa20),'Unknown reset GS')
            blob+=struct.pack('<II',handler,0xa20)
        elif h[0]==33:
            parent=struct.unpack('<III',c.read(u+n,12));need(parent in originals,'Unknown unwind parent')
            blob+=struct.pack('<III',*originals[parent])
        else:need(h[0]==1,'Unknown peer handler')
    for original,b,e in islands:
        parent=next(f for f in fs if f[0]<=original<f[1])
        # Every island starts after this fragment's prologue; no new saves.
        need(original-parent[0]>=c.read(parent[2],2)[1],'Patch within prologue')
        rows.append((b,e,len(blob)));blob+=bytes((33,0,0,0))+struct.pack('<III',*originals[parent])
    if kind==4:rows.append((handler,handler+5,len(blob)));blob+=bytes((1,0,0,0))
    table=len(blob)
    for row in rows:blob+=struct.pack('<III',*row)
    need(len(blob)<=4096,'Peer image too large')
    return dict(blob=bytes(blob),fixes=fixes,rows=rows,table=table,handler=handler,source=start,body=body,islands=islands)


def build_leaf(kind):
    c=Capture();start,end=LEAVES[kind-5];ins=list(c.md.disasm(c.read(start,end-start),start))
    need(sum(i.size for i in ins)==end-start,'Incomplete peer leaf')
    need(not any(b<end and start<e for b,e,_ in c.functions),'Peer leaf acquired unwind frame')
    need(all(i.mnemonic!='call' and not any(r in i.op_str for r in ('rsp','rbp','rbx','rsi','rdi','r11','r12','r13','r14','r15')) for i in ins),
         'Peer leaf now uses a frame or nonvolatile/scratch register')
    blob=bytearray(bytes.fromhex('49bb')+bytes(8)+bytes.fromhex('4c39d90f85')+bytes(4))
    fixes=[(2,0,1,1,1,0)];branches=[(15,19,'reject')];mapping={};seen=set();blob+=b'\x90'*(64-len(blob))
    patches={
        0x1084fde:('lea r8, [rcx + 0xd0]',bytes.fromhex('49b8')+bytes(8),2),
        0x1084ffc:('add rax, 0xd0',b'',None),
        0x1085002:('add rax, rcx',bytes.fromhex('49bb')+bytes(8)+bytes.fromhex('4c01d8'),2),
        0x1085022:('lea r8, [rcx + 0xd0]',bytes.fromhex('49b8')+bytes(8),2),
        0x108504b:('lea r10, [rcx + 0xd0]',bytes.fromhex('49ba')+bytes(8),2),
        0x10850b4:('add rcx, 0xd0',bytes.fromhex('48b9')+bytes(8),2),
        0x10850d4:('lea rcx, [r9 + 0xd0]',bytes.fromhex('48b9')+bytes(8),2),
    }
    count_site=(0x1084fd0,0x1085010,0x10850a8)[kind-5]
    for i in ins:
        at=len(blob);mapping[i.address]=at
        if i.address in patches:
            expected,raw,offset=patches[i.address];need(i.mnemonic+' '+i.op_str==expected,'Changed peer leaf operand')
            blob+=raw;seen.add(i.address)
            if offset is not None:fixes.append((at+offset,0,2,1,1,0))
        elif i.mnemonic.startswith('j'):
            need(i.operands[0].type==X86_OP_IMM and start<=i.operands[0].imm<end,'External peer leaf branch')
            raw=bytes(i.bytes);op=b'\xe9' if i.mnemonic=='jmp' else bytes((0x0f,raw[0]+0x10))
            need(raw[0]==0xeb or 0x70<=raw[0]<=0x7f,'Unexpected peer leaf branch encoding')
            blob+=op+bytes(4);branches.append((at+len(op),len(blob),i.operands[0].imm))
        else:
            need(not any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands),'Unexpected peer leaf global')
            blob+=i.bytes
        if i.address==count_site:
            expected='mov edx, dword ptr [rcx + 0xc8]' if kind==7 else 'mov r9d, dword ptr [rcx + 0xc8]'
            need(i.mnemonic+' '+i.op_str==expected,'Changed peer count')
            # Check the count actually used by this loop, after the native
            # load. No second count load can invalidate the entry guard.
            blob+=bytes.fromhex('81fa' if kind==7 else '4181f9');fixes.append((len(blob),0,3,2,1,0));blob+=bytes(4)
            blob+=b'\x0f\x87'+bytes(4);branches.append((len(blob)-4,len(blob),'reject'))
    need(seen=={a for a in patches if start<=a<end},'Missing peer leaf replacement')
    mapping['reject']=len(blob);blob+=bytes.fromhex('49bb')+bytes(8)+bytes.fromhex('41ffe3')
    fixes.append((mapping['reject']+2,0,4,1,1,0))
    for at,nxt,target in branches:
        need(target in mapping,'Peer leaf branch misses boundary');struct.pack_into('<i',blob,at,mapping[target]-nxt)
    code_bytes=len(blob);blob+=bytes(-len(blob)%4);rows=[(0,code_bytes,len(blob))];blob+=bytes((1,0,0,0))
    table=len(blob);blob+=struct.pack('<III',*rows[0])
    return dict(blob=bytes(blob),fixes=fixes,rows=rows,table=table,handler=0xffffffff,source=start,body=64,islands=[])


def render(images):
    lines=['// Generated from saved build 25480438 by generate_client_peers.py.']
    for k,a in enumerate(images,1):
        lines.append(f'static const uint8_t ep_client_peers_template_{k}[] = {{')
        lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
        lines+=['};',f'static const EpClientPeerFixup ep_client_peers_fixups_{k}[] = {{']
        lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    lines.append('static const EpClientPeerTemplate ep_client_peer_templates[] = {')
    for k,a in enumerate(images,1):
        lines.append('    {'+f'ep_client_peers_template_{k},ep_client_peers_fixups_{k},'+
                     ','.join(map(str,(len(a['blob']),len(a['fixes']),a['table'],len(a['rows']),a['handler'],a['source'])))+'},')
    return '\n'.join(lines+['};',''])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args()
    images=[build(k) for k in range(1,8)]
    if args.write:HEADER.write_text(render(images),encoding='utf-8',newline='\n')
    print('Peer lifecycle/lookup image bytes:',*[len(a['blob']) for a in images])
