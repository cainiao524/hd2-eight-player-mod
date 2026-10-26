"""Relocate saved resource-object registration, dense move and removal.

Four overlapping inline banks move together into capacity-sized storage.
Native object IDs/hash callbacks and phase counts retain their ABI. No game access.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

GROUPS=((0x66bfc0,0x66c073),(0x66c080,0x66c0f4),(0x66bc20,0x66bd2e),(0x66c270,0x66c2fb))
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_resource_owner_template.h'


def build():
    capture=Capture();blob=bytearray();fixes=[];branches=[];mapping={};ends={};rows=[];entries=[];sources=[]
    def fix(raw,offset,key,kind=1,add=0):
        at=len(blob);blob.extend(raw);fixes.append((at+offset,len(blob),key,kind,add))
    def absolute(reg,key,add=0):fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,1,add)
    def capacity(raw):fix(raw+bytes(4),len(raw),5,2)
    def reject(op=b'\x0f\x83'):fix(op+bytes(4),len(op),6,0)
    def branch(op,target):
        at=len(blob);blob.extend(op+bytes(4));branches.append((at+len(op),len(blob),target))
    def bank(ins,key,add=0):
        # Rewrite only the reviewed owner-bank operand. Keep the original
        # opcode, register width, index/scale and immediate; R11 is dead at
        # each listed site until its next definition in the native hash walk.
        mem=next(o.mem for o in ins.operands if o.type==X86_OP_MEM)
        need(mem.base and ins.reg_name(mem.base) in ('rbx','rcx','rsi','rdi'),'Unexpected owner bank base')
        idx=ins.reg_name(mem.index) if mem.index else None
        names=['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi']+[f'r{i}' for i in range(8,16)]
        index=names.index(idx) if idx else 4
        need(idx is None or idx!='rsp','Unsupported owner bank index')
        raw=bytes(ins.bytes);p=0
        while raw[p] in (0xf0,0xf2,0xf3,0x2e,0x36,0x3e,0x26,0x64,0x65,0x66,0x67):p+=1
        rex=((ins.rex or 0x40)&~3)|1|(2 if idx and index>=8 else 0)
        prefix=raw[:p]+bytes((rex,))+raw[p+bool(ins.rex):ins.modrm_offset]
        absolute(11,key,add)
        blob.extend(prefix+bytes(((ins.modrm&0x38)|4,({1:0,2:1,4:2,8:3}[mem.scale]<<6)|((index&7)<<3)|3)))
        if ins.imm_size:blob.extend(raw[ins.imm_offset:ins.imm_offset+ins.imm_size])
    # 8-byte objects, 12-byte phase rows, 20-byte resource state, 4-byte
    # replicated state. Owner counts/hash remain native; these banks do not.
    banks={
        0x66c019:(15,0,0x88),0x66c021:(15,8,0x90),0x66c039:(16,0,0xb8),0x66c041:(16,16,0xc8),0x66c05c:(14,0,0x68),
        0x66c0b6:(15,0,0x88),0x66c0be:(15,8,0x90),0x66c0ca:(16,0,0xb8),0x66c0d2:(16,16,0xc8),0x66c0da:(14,0,0x68),
        0x66bc46:(14,0,0x68),0x66bc4f:(14,0,0x68),0x66bc5c:(15,0,0x88),0x66bc69:(15,0,0),0x66bc76:(15,8,0x90),
        0x66bc91:(16,0,0xb8),0x66bc9c:(16,0,0),0x66bca7:(16,16,0xc8),0x66bcb4:(17,0,0x108),0x66bcbc:(17,0,0x108),0x66bcc3:(14,0,0x68),
        0x66c2af:(14,0,0x68),
    }
    aliases={0x66bc6d:(0x88,0),0x66bc82:(0x90,8),0x66bca0:(0xb8,0),0x66bcae:(0xc8,16)}
    for start,end in GROUPS:
        fragments=[f for f in capture.functions if start<=f[0]<end]
        need(len(fragments)=={0x66bfc0:1,0x66c080:1,0x66bc20:3,0x66c270:1}[start] and
             fragments[-1][1]==end and all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),
             'Changed resource owner fragments')
        blob.extend(b'\xcc'*(-len(blob)%16));entry=len(blob);entries.append(entry)
        absolute(11,13);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326428);reject(b'\x0f\x85')
        for off in (0,4,8,12):
            blob.extend(b'\x45\x8b\x53'+bytes((off,)));capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
        if start==0x66bfc0:
            # Immediate insertion would overwrite pending registrations. Native
            # publication must precede this callback; fail before mutations.
            blob.extend(b'\x45\x8b\x53\x04\x45\x3b\x53\x08');reject(b'\x0f\x85')
        if start==0x66bc20:
            blob.extend(b'\x4c\x39\xd9');reject(b'\x0f\x85')
            capacity(b'\x81\xfa');reject();capacity(b'\x41\x81\xf8');reject()
        rows.append((entry,len(blob),b'\x01\0\0\0',None));first_row=len(rows)
        code_end=end
        source=capture.read(start,code_end-start);sources.append(dict(start=start,end=code_end,data=source))
        insns=list(capture.md.disasm(source,start));need(insns[-1].address+insns[-1].size==code_end,'Incomplete resource_owner decode')
        for ins in insns:
            a=ins.address;at=len(blob);mapping[a]=at;text=ins.mnemonic+' '+ins.op_str
            mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
            if a in banks:
                key,offset,old=banks[a];need(mem.disp==old,'Changed owner array operand');bank(ins,key,offset)
            elif a in aliases:
                old,offset=aliases[a];need(mem.disp==old,'Changed owner row alias')
                raw=bytearray(ins.bytes);raw[ins.disp_offset:ins.disp_offset+ins.disp_size]=offset.to_bytes(ins.disp_size,'little');blob.extend(raw)
            elif a in (0x66bfd9,0x66c095):
                need(text=='cmp eax, 4','Changed registration limit');capacity(b'\x3d')
            elif a in (0x66bfde,0x66c09a):
                need(text=='mov dword ptr [0], 0','Changed native capacity failure');reject(b'\xe9')
            elif a==0x66c29c:
                # Hash erase must return a valid prior slot before counts move.
                need(text=='jb 0x66c2aa','Changed remove branch')
                branch(b'\x0f\x82',0x66c2aa)
                blob.extend(b'\x3b\x47\x04');reject()
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
            head=capture.read(u,4);need(head[0] in (1,33) and head[3]==0,'Unexpected resource_owner unwind')
            n=4+((head[2]+1)&~1)*2;uw=bytearray(capture.read(u,n));parent=None
            def offset(old):return ends[b+old]-mapping[b] if old else 0
            uw[1]=offset(head[1]);i=0
            while i<head[2]:
                uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                need(op in (0,1,2,4,8),'Unexpected resource_owner unwind operation');i+=2 if op in (1,4,8) else 1
            if head[0]==33:
                old=struct.unpack('<III',capture.read(u+n,12));need(old in fragments[:fragments.index((b,e,u))],'Foreign resource_owner chain')
                parent=first_row+fragments.index(old)
            rows.append((mapping[b],ends[min(e,code_end)],bytes(uw),parent))
    for at,nxt,target in branches:
        if isinstance(target,tuple):target=entries[[b for b,e in GROUPS].index(target[1])]
        else:need(target in mapping,'Missing resource_owner branch');target=mapping[target]
        fixes.append((at,nxt,1,0,target))
    code_bytes=len(blob);blob.extend(bytes(-len(blob)%4));unwind_offset=len(blob);functions=[]
    for b,e,uw,parent in rows:
        functions.append((b,e,len(blob)));blob.extend(uw)
        if parent is not None:blob.extend(struct.pack('<III',*functions[parent]))
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE and len(functions)==10,'Resource owner image bounds')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,functions=functions,entries=entries,sources=sources,mapping=mapping)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_resource_owner.py.',
           'static const uint8_t ep_loadout_resource_owner_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutResourceOwnerFixup ep_loadout_resource_owner_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset'):
        lines.append(f'static const uint32_t ep_loadout_resource_owner_{key} = {a[key]};')
    lines.append(f'static const uint32_t ep_loadout_resource_owner_functions = {len(a["functions"])};')
    lines.append('static const uint32_t ep_loadout_resource_owner_entries[] = {'+','.join(map(str,a['entries']))+'};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
