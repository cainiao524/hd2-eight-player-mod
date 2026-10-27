"""Relocate saved loadout update, record lookup and player action consumers.

Only the workspace capture is read. No game discovery, hashes or receipts.
The four INNER equipment choices and the separate 9F8 peer bank stay intact.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture, PROJECT, need
from capstone.x86_const import X86_OP_MEM, X86_OP_IMM, X86_REG_RIP, X86_REG_RSP

GROUPS = ((0x146c2f0,0x146d311), (0x1470650,0x14706f1), (0x14719f0,0x1471af3))
HEADER = PROJECT/'mod/src/ep_loadout_consumers_template.h'
MAX_IMAGE = 8192
REG = {'rax':0,'rcx':1,'rdx':2,'rbx':3,'rsp':4,'rbp':5,'rsi':6,'rdi':7,
       'r8':8,'r9':9,'r10':10,'r11':11,'r12':12,'r13':13,'r14':14,'r15':15}


def build(peers=False):
    capture=Capture();blob=bytearray();fixes=[];branches=[];mapping={};ends={};entries=[];rows=[];sources=[]
    def fix(code, operand, key, kind=1, add=0):
        at=len(blob);blob.extend(code);fixes.append((at+operand,len(blob),key,kind,add))
    def absolute(reg,key,add=0,kind=1):
        fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,kind,add)
    def branch(op,target):
        at=len(blob);blob.extend(op+bytes(4));branches.append((at+len(op),len(blob),target))
    def reject(op=b'\x0f\x83'):
        fix(op+bytes(4),len(op),6,0)
    def capacity(code):fix(code+bytes(4),len(code),5,2)
    def peer_count(owner, count, instruction, rebase=True):
        # Compare before dereferencing the captured global. The count register
        # is dead here and will immediately receive the original native count.
        absolute(count,12,-0x162c8)
        blob.extend(bytes((0x48+4*(count>=8)+(owner>=8),0x39,
                           0xc0+((count&7)<<3)+(owner&7))))
        reject(b'\x0f\x85');blob.extend(instruction)
        capacity((b'\x41' if count>=8 else b'')+b'\x81'+bytes((0xf8+(count&7),)))
        reject(b'\x0f\x87')
        if rebase:absolute(owner,13,-0x16398)
    def relocate_memory(ins,key,origin):
        mem=next(o.mem for o in ins.operands if o.type==X86_OP_MEM)
        base=REG[ins.reg_name(mem.base)]
        need(base!=11 and (not mem.index or ins.reg_name(mem.index)!='r11'),'Live scratch register')
        # r11 = replacement - screen - original field + original base.
        # LEA/MOV preserve the incoming flags; original index/scale is unchanged.
        absolute(11,key,-origin,3)
        blob.extend(bytes((0x4d+(2 if base>=8 else 0),0x8d,0x1c,((base&7)<<3)|3)))
        raw=bytearray(ins.bytes);m=ins.modrm_offset
        if raw[m]&7==4:raw[m+1]=(raw[m+1]&0xf8)|3
        else:raw[m]=(raw[m]&0xf8)|3
        p=0
        while raw[p] in (0x66,0xf2,0xf3,0x2e,0x3e,0x64,0x65):p+=1
        if 0x40<=raw[p]<=0x4f:raw[p]|=1
        else:raw[p:p]=b'\x41'
        blob.extend(raw)

    for start,end in GROUPS:
        fragments=[f for f in capture.functions if start<=f[0]<end]
        need(fragments and fragments[0][0]==start and fragments[-1][1]==end and
             all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),'Missing function fragment')
        blob.extend(b'\xcc'*(-len(blob)%16));entry=len(blob);entries.append(entry)
        absolute(11,2);blob.extend(b'\x4c\x39\xd9');reject(b'\x0f\x85')
        if start==GROUPS[0][0]:
            absolute(11,9)
            fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326468);reject(b'\x0f\x85')
            blob.extend(b'\x41\x8b\x83\x84\0\0\0');capacity(b'\x3d');reject(b'\x0f\x87')
            blob.extend(b'\x41\x39\x83\x88\0\0\0');reject(b'\x0f\x87')
        rows.append((entry,len(blob),b'\x01\0\0\0',None))
        data=capture.read(start,end-start);insns=list(capture.md.disasm(data,start))
        need(insns[-1].address+insns[-1].size==end,'Incomplete consumer decode')
        sources.append(dict(start=start,end=end,data=data))
        for ins in insns:
            a=ins.address;mapping[a]=len(blob)
            text=ins.mnemonic+' '+ins.op_str
            mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
            if peers and a in (0x146c424,0x146cbd9,0x1471a46):
                owner,count={0x146c424:(9,0),0x146cbd9:(8,2),0x1471a46:(3,10)}[a]
                peer_count(owner,count,ins.bytes)
            elif peers and a in (0x146c6ff,0x146cfc4):
                peer_count(1,2,b'\x8b\x91\x90\x63\x01\0',False)
                blob.extend(b'\x39\xc2' if a==0x146c6ff else b'\x39\xd0')
            elif peers and a==0x146c71d:
                absolute(14,13);blob.extend(b'\x4d\x8b\x34\x06')
            elif a in (0x146c474,0x146cc08,0x146d29b,0x1471ac3):
                # Validate the network index BEFORE indexing either map.
                capacity({0x146c474:b'\x41\x81\xfd',0x146cc08:b'\x81\xf9',
                          0x146d29b:b'\x3d',0x1471ac3:b'\x3d'}[a])
                if a==0x1471ac3:branch(b'\x0f\x83',0x1471ae8)
                else:reject()
            if a==0x146c4eb:
                capacity(b'\x81\xf9');reject()
            if a==0x146cc58:
                blob.extend(b'\x83\xff\xff');branch(b'\x0f\x84',0x146cfb5)
                capacity(b'\x81\xff');reject()
            if a==0x146c319:
                need(text=='mov dword ptr [rsp + 0x40], 0','Changed activity flags')
                # Eight bytes in the existing unused +38..3F stack gap. Native
                # outgoing arguments stop at +30; other locals keep their ABI.
                blob.extend(bytes.fromhex('48c744243800000000'))
            elif mem and mem.base==X86_REG_RSP and mem.disp==0x40 and start==0x146c2f0:
                need(a in (0x146c3de,0x146c5d9,0x146cfd2),'Unknown activity reference')
                raw=bytearray(ins.bytes);raw[ins.disp_offset]=0x38;blob.extend(raw)
            elif a in (0x146c3d1,0x146c4bb,0x146cc2b,0x146d2c0,0x14706c4,0x1471aca):
                need(text.endswith(', 4'),'Changed player limit')
                capacity({0x146c3d1:b'\x49\x81\xff',0x146c4bb:b'\x81\xf9',
                          0x146cc2b:b'\x81\xff',0x146d2c0:b'\x81\xfd',
                          0x14706c4:b'\x81\xfb',0x1471aca:b'\x81\xf9'}[a])
                if a==0x1471aca:
                    branch(b'\x0f\x83',0x1471ae8)
                    absolute(11,8);blob.extend(b'\x41\x39\x04\x8b')
                    branch(b'\x0f\x85',0x1471ae8)
                    capacity(b'\x81\xf9')
            elif a==0x146c3b1:
                need(text=='mov rcx, qword ptr [r10 + rax*8 + 0xe8]','Changed roster array')
                absolute(11,10);blob.extend(b'\x49\x8b\x0c\xc3')
            elif a==0x146c3c0:
                need(text=='add rax, 0x3a8','Changed property array')
                absolute(11,10,0x580);blob.extend(b'\x4a\x8d\x04\x18')
            elif a==0x146c3c9:
                need(text=='add rax, r10','Changed property base');blob.extend(b'\x90')
            elif a==0x146c72b:
                need(text=='lea rax, [r10 + 0x2c8]','Changed roster peer array');absolute(0,10,0x3c0)
            elif a in (0x14706af,0x14706e4):
                need(text==('lea rcx, [rsi + 0x9f8]' if a==0x14706af else 'lea rax, [rsi + 0x10]'),'Changed record pointer')
                absolute(1 if a==0x14706af else 0,3,0x9e8 if a==0x14706af else 0)
            elif a in (0x146c587,0x146cb2c,0x146d190,0x1471ad9):
                base={0x146c587:0x56328,0x146cb2c:0x53a78,0x146d190:0x624b0,0x1471ad9:0x620e8}[a]
                need(text==f'add {"rdi" if a in (0x146c587,0x146cb2c) else "rcx"}, {hex(base)}','Changed derived widget')
                absolute(11,4,base-0x53a78,3)
                blob.extend(b'\x4c\x01\xdf' if a in (0x146c587,0x146cb2c) else b'\x4c\x01\xd9')
            elif mem and 0x53a78<=mem.disp<0x72890 and ins.reg_name(mem.base) in ('rsi','rdi','rbp'):
                relocate_memory(ins,4,0x53a78)
            elif mem and mem.disp in (0x27d8,0x27e8,0x27ec) and ins.reg_name(mem.base) in ('rsi','rdi'):
                relocate_memory(ins,7 if mem.disp==0x27d8 else 8,0x27d8 if mem.disp==0x27d8 else 0x27e8)
            elif ins.mnemonic=='call' and ins.operands[0].type==X86_OP_IMM and ins.operands[0].imm in (0x60b3b0,):
                fix(b'\xe8'+bytes(4),1,{0x60b3b0: 11}[ins.operands[0].imm],0)
            elif (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                raw=bytes(ins.bytes);target=ins.operands[0].imm
                op=raw[:1] if raw[0] in (0xe8,0xe9) else b'\xe9' if raw[0]==0xeb else bytes((0x0f,raw[0]+0x10)) if 0x70<=raw[0]<=0x7f else raw[:2]
                if any(b<=target<e for b,e in GROUPS):branch(op,('entry',target) if ins.mnemonic=='call' else target)
                else:fix(op+bytes(4),len(op),0,0,target)
            else:
                blob.extend(ins.bytes)
                if mem and mem.base==X86_REG_RIP:
                    need(struct.unpack_from('<i',ins.bytes,ins.disp_offset)[0]==ins.disp,'Bad RIP operand')
                    fixes.append((len(blob)-ins.size+ins.disp_offset,len(blob),0,0,a+ins.size+ins.disp))
            ends[a+ins.size]=len(blob)
        for b,e,at in fragments:
            head=capture.read(at,4);need(head[0] in (1,33) and head[3]==0,'Unsupported consumer unwind')
            uw=bytearray(capture.read(at,4+((head[2]+1)&~1)*2))
            def offset(old):return ends[b+old]-mapping[b] if old else 0
            uw[1]=offset(head[1]);i=0
            while i<head[2]:
                uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                need(op in (0,1,2,4,8),'Unknown unwind operation');i+=2 if op in (1,4,8) else 1
            parent=struct.unpack('<III',capture.read(at+len(uw),12)) if head[0]==33 else None
            rows.append((mapping[b],ends[e],bytes(uw),parent))
    for at,nxt,target in branches:
        if isinstance(target,tuple):
            need(target[1] in [x[0] for x in GROUPS],'Call enters a fragment')
            dest=entries[[x[0] for x in GROUPS].index(target[1])]
        else:need(target in mapping,'Branch misses instruction boundary');dest=mapping[target]
        fixes.append((at,nxt,1,0,dest))
    code_bytes=len(blob);blob.extend(bytes(-len(blob)%4));unwind_offset=len(blob);functions=[]
    for b,e,uw,parent in rows:
        row=(b,e,len(blob));functions.append(row);blob.extend(uw)
        if parent:
            old_begin,old_end,_=parent
            found=next((r for r in functions[:-1] if r[:2]==(mapping[old_begin],ends[old_end])),None)
            need(found is not None,'External/forward unwind chain');blob.extend(struct.pack('<III',*found))
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(functions)<=15 and len(blob)<=MAX_IMAGE,'Consumer image exceeds bounds')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,entries=entries,functions=functions,sources=sources,mapping=mapping)


def render(a,peers=False):
    lines=['// Generated from saved build 25480438 by generate_loadout_consumers.py.',
           'static const uint8_t ep_loadout_consumers_template[] = {']
    lines += ['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutConsumerFixup ep_loadout_consumer_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']]
    lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset'):
        lines.append(f'static const uint32_t ep_loadout_consumer_{key} = {a[key]};')
    lines.append('static const uint32_t ep_loadout_consumer_entries[] = {'+','.join(map(str,a['entries']))+'};')
    lines.append(f'static const uint32_t ep_loadout_consumer_functions = {len(a["functions"])};')
    text='\n'.join(lines)+'\n'
    return text.replace('ep_loadout_consumers_','ep_loadout_peer_consumers_').replace('ep_loadout_consumer_','ep_loadout_peer_consumer_') if peers else text


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:
        HEADER.write_text(render(a),encoding='utf-8',newline='\n')
        HEADER.with_name('ep_loadout_peer_consumers_template.h').write_text(render(build(True),True),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),entries=len(a['entries']),game_access=False)))
