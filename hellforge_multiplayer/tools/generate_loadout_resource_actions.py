"""Relocate resource activation, phase reset and conditional activation.

Use the shared resource/owner/roster banks. Native actor notification rows,
completion catalog, mode stack and event formats retain their own meanings.
No game access, automatic callback routing or native catalog expansion.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

GROUPS=((0x661cf0,0x661e42),(0x662400,0x662516),(0x11b61f0,0x11b6477))
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_resource_actions_template.h'


def build():
    capture=Capture();blob=bytearray();fixes=[];branches=[];mapping={};ends={};rows=[];entries=[];sources=[]
    def fix(raw,offset,key,kind=1,add=0):
        at=len(blob);blob.extend(raw);fixes.append((at+offset,len(blob),key,kind,add))
    def absolute(reg,key,add=0):fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,1,add)
    def capacity(raw):fix(raw+bytes(4),len(raw),5,2)
    def reject(op=b'\x0f\x83'):fix(op+bytes(4),len(op),6,0)
    def branch(op,target):
        at=len(blob);blob.extend(op+bytes(4));branches.append((at+len(op),len(blob),target))
    def bank(ins,key,add=0,forced_index=None,scratch=11):
        # Rewrite only the reviewed owner-bank operand. Keep the original
        # opcode, register width, index/scale and immediate; R11 is dead at
        # each reviewed site; owner registers retain their native lifetimes.
        mem=next(o.mem for o in ins.operands if o.type==X86_OP_MEM)
        need(mem.base and ins.reg_name(mem.base) in ('rax','rbx','rcx','rsi','rdi','r8','r14','r11','rdx'),'Unexpected owner bank base')
        idx=forced_index or (ins.reg_name(mem.index) if mem.index else None)
        names=['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi']+[f'r{i}' for i in range(8,16)]
        index=names.index(idx) if idx else 4
        need(idx is None or idx!='rsp','Unsupported owner bank index')
        raw=bytes(ins.bytes);p=0
        while raw[p] in (0xf0,0xf2,0xf3,0x2e,0x36,0x3e,0x26,0x64,0x65,0x66,0x67):p+=1
        rex=((ins.rex or 0x40)&~3)|1|(2 if idx and index>=8 else 0)
        prefix=raw[:p]+bytes((rex,))+raw[p+bool(ins.rex):ins.modrm_offset]
        absolute(scratch,key,add)
        blob.extend(prefix+bytes(((ins.modrm&0x38)|4,({1:0,2:1,4:2,8:3}[mem.scale]<<6)|((index&7)<<3)|(scratch&7))))
        if ins.imm_size:blob.extend(raw[ins.imm_offset:ins.imm_offset+ins.imm_size])
    banks={0x661d92:(12,0,0x11d18,'rcx'),0x11b63c3:(12,0,0x11d18,'rcx'),
           0x662484:(15,0,0x88,None),0x66248f:(15,0,0x88,None),0x11b6294:(16,0,0,None)}
    for start,end in GROUPS:
        fragments=[f for f in capture.functions if start<=f[0]<end]
        need(len(fragments)=={0x661cf0:3,0x662400:3,0x11b61f0:6}[start] and
             fragments[-1][1]==end and all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),
             'Changed resource callback fragments')
        blob.extend(b'\xcc'*(-len(blob)%16));entry=len(blob);entries.append(entry)
        if start==0x11b61f0:
            # Preserve the native null/non-owner no-op before binding reads.
            blob.extend(b'\x48\x85\xc9');branch(b'\x0f\x84',0x11b6468)
            blob.extend(b'\xf6\x41\x14\x01');branch(b'\x0f\x84',0x11b6468)
        absolute(11,13);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326428);reject(b'\x0f\x85')
        for off in (0,4,8,12):
            blob.extend(b'\x45\x8b\x53'+bytes((off,)));capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
        for off in (8,12):
            blob.extend(b'\x45\x8b\x53'+bytes((off,))+b'\x45\x3b\x53\x04');reject(b'\x0f\x87')
        absolute(11,11);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x33265f0);reject(b'\x0f\x85')
        if start==0x662400:blob.extend(b'\x4c\x39\xd9');reject(b'\x0f\x85')
        if start==0x661cf0:capacity(b'\x81\xfa');reject()
        absolute(11,9);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326468);reject(b'\x0f\x85')
        blob.extend(bytes.fromhex('458b9384000000'));capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
        blob.extend(bytes.fromhex('45399388000000'));reject(b'\x0f\x87')
        rows.append((entry,len(blob),b'\x01\0\0\0',None));first_row=len(rows)
        code_end=end
        source=capture.read(start,code_end-start);sources.append(dict(start=start,end=code_end,data=source))
        insns=list(capture.md.disasm(source,start));need(insns[-1].address+insns[-1].size==code_end,'Incomplete resource_actions decode')
        for ins in insns:
            a=ins.address;at=len(blob);mapping[a]=at;text=ins.mnemonic+' '+ins.op_str
            mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
            if a in banks:
                key,offset,old,index=banks[a];need(mem.disp==old,'Changed resource action bank');bank(ins,key,offset,forced_index=index)
            elif a==0x6624b3:
                need(text=='mov rax, qword ptr [rax + 0xe8]','Changed first roster descriptor')
                absolute(0,10);blob.extend(b'\x48\x8b\x00')
            elif a==0x11b6287:
                # Missing object/catalog has no usable resource row. This
                # point is past all native saves; restore before normal exit.
                need(text=='mov eax, 0xffffffff','Changed completion miss path')
                blob.extend(bytes.fromhex('4c8b7c24404c8b742448488bac2480000000488b742458'));branch(b'\xe9',0x11b6459)
            elif a==0x11b628e:
                need(text=='mov edx, ecx','Changed owner hash ordinal')
                blob.extend(b'\x83\xf9\xff');branch(b'\x0f\x84',0x11b6287)
                capacity(b'\x81\xf9');reject();blob.extend(b'\x3b\x4e\x04');reject();blob.extend(ins.bytes)
            elif a==0x11b6318:
                need(text=='mov ecx, eax','Changed native completion catalog ordinal')
                # This catalog is not player-indexed. Keep its native stride
                # and caller-validated backing, without a player-cap clamp.
                blob.extend(b'\x83\xf8\xff');branch(b'\x0f\x84',0x11b6287);blob.extend(ins.bytes)
            elif a==0x11b63b3:
                need(text=='mov eax, dword ptr [r13 + 0xbc]','Changed resource row ordinal')
                blob.extend(b'\x41\x80\x7d\x08\x00');branch(b'\x0f\x84',0x11b6459)
                blob.extend(b'\x41\x8b\x45\x04');capacity(b'\x3d');reject()
            elif (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                raw=bytes(ins.bytes);target=ins.operands[0].imm
                op=raw[:1] if raw[0] in (0xe8,0xe9) else b'\xe9' if raw[0]==0xeb else bytes((0x0f,raw[0]+0x10)) if 0x70<=raw[0]<=0x7f else raw[:2]
                if target in [b for b,e in GROUPS]:branch(op,('entry',target))
                elif any(b<=target<e for b,e in GROUPS):branch(op,target)
                else:fix(op+bytes(4),len(op),0,0,target)
            else:
                blob.extend(ins.bytes)
                if mem and mem.base==X86_REG_RIP:fixes.append((at+ins.disp_offset,len(blob),0,0,a+ins.size+ins.disp))
            ends[a+ins.size]=len(blob)
        for b,e,u in fragments:
            head=capture.read(u,4);need(head[0] in (1,33) and head[3]==0,'Unexpected resource_actions unwind')
            n=4+((head[2]+1)&~1)*2;uw=bytearray(capture.read(u,n));parent=None
            def offset(old):return ends[b+old]-mapping[b] if old else 0
            uw[1]=offset(head[1]);i=0
            while i<head[2]:
                uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                need(op in (0,1,2,4,8),'Unexpected resource_actions unwind operation');i+=2 if op in (1,4,8) else 1
            if head[0]==33:
                old=struct.unpack('<III',capture.read(u+n,12));need(old in fragments[:fragments.index((b,e,u))],'Foreign resource_actions chain')
                parent=first_row+fragments.index(old)
            rows.append((mapping[b],ends[min(e,code_end)],bytes(uw),parent))
    for at,nxt,target in branches:
        if isinstance(target,tuple):target=entries[[b for b,e in GROUPS].index(target[1])]
        else:need(target in mapping,'Missing resource_actions branch');target=mapping[target]
        fixes.append((at,nxt,1,0,target))
    code_bytes=len(blob);blob.extend(bytes(-len(blob)%4));unwind_offset=len(blob);functions=[]
    for b,e,uw,parent in rows:
        functions.append((b,e,len(blob)));blob.extend(uw)
        if parent is not None:blob.extend(struct.pack('<III',*functions[parent]))
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE and len(functions)==15,'Resource callback image bounds')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,functions=functions,entries=entries,sources=sources,mapping=mapping)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_resource_actions.py.',
           'static const uint8_t ep_loadout_resource_actions_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutResourceActionsFixup ep_loadout_resource_actions_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset'):
        lines.append(f'static const uint32_t ep_loadout_resource_actions_{key} = {a[key]};')
    lines.append(f'static const uint32_t ep_loadout_resource_actions_functions = {len(a["functions"])};')
    lines.append('static const uint32_t ep_loadout_resource_actions_entries[] = {'+','.join(map(str,a['entries']))+'};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
