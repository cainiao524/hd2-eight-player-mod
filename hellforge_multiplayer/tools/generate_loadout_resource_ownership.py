"""Relocate pending settlement and resource ownership promotion/demotion.

Settlement uses complete promotion instead of overwriting pending rows.
Native ownership swaps/reset fields/hash updates use shared sidecar banks.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

GROUPS=((0x66c100,0x66c244),(0x66c300,0x66c583),(0x66c590,0x66c87d))
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_resource_ownership_template.h'


def build():
    capture=Capture();blob=bytearray();fixes=[];branches=[];mapping={};ends={};rows=[];entries=[];sources=[]
    def fix(raw,offset,key,kind=1,add=0):
        at=len(blob);blob.extend(raw);fixes.append((at+offset,len(blob),key,kind,add))
    def absolute(reg,key,add=0):fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,1,add)
    def capacity(raw):fix(raw+bytes(4),len(raw),5,2)
    def reject(op=b'\x0f\x83'):fix(op+bytes(4),len(op),6,0)
    def branch(op,target):
        at=len(blob);blob.extend(op+bytes(4));branches.append((at+len(op),len(blob),target))
    def bank(ins,key,add=0,forced_index=None):
        # Rewrite only the reviewed owner-bank operand. Keep the original
        # opcode, register width, index/scale and immediate; R11 is dead at
        # each listed site until its next definition in the native hash walk.
        mem=next(o.mem for o in ins.operands if o.type==X86_OP_MEM)
        need(mem.base and ins.reg_name(mem.base) in ('rbx','rcx','rsi','rdi','rbp','r12'),'Unexpected owner bank base')
        idx=forced_index or (ins.reg_name(mem.index) if mem.index else None)
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
    banks={
        0x66c13e:(14,0,0x68),0x66c147:(14,0,0x68),0x66c150:(15,0,0x88),0x66c159:(15,0,0),0x66c165:(15,8,0x90),
        0x66c17a:(16,0,0xb8),0x66c182:(16,0,0),0x66c18d:(16,16,0xc8),0x66c19a:(17,0,0x108),0x66c1a2:(17,0,0x108),0x66c1aa:(14,0,0x68),
        0x66c38e:(15,0,0x88),0x66c396:(15,8,0x90),0x66c3ac:(14,0,0x68),0x66c3b1:(14,0,0x68),0x66c3b6:(14,0,0x68),0x66c3bf:(14,0,0x68),
        0x66c3c6:(15,0,0x88),0x66c3ce:(15,8,0x90),0x66c3df:(14,0,0),0x66c402:(16,0,0),0x66c41f:(16,0,0xb8),0x66c42f:(16,16,0xc8),
        0x66c441:(16,0,0xb8),0x66c44d:(16,16,0xc8),0x66c484:(17,0,0x108),0x66c48e:(17,0,0x108),0x66c496:(17,0,0x108),0x66c4a5:(17,0,0x108),0x66c4bc:(14,0,0x68),
        0x66c625:(14,0,0x68),0x66c62f:(14,0,0x68),0x66c634:(14,0,0x68),0x66c639:(14,0,0x68),
        0x66c686:(15,0,0x88),0x66c697:(15,8,0x90),0x66c6a9:(15,0,0x88),0x66c6b6:(15,8,0x90),
        0x66c719:(16,0,0xb8),0x66c729:(16,16,0xc8),0x66c73b:(16,0,0xb8),0x66c747:(16,16,0xc8),
        0x66c77e:(17,0,0x108),0x66c788:(17,0,0x108),0x66c78f:(17,0,0x108),0x66c79e:(17,0,0x108),0x66c7b4:(14,0,0x68),0x66c80f:(14,0,0x68),
    }
    aliases={0x66c15d:(0x88,0),0x66c170:(0x90,8),0x66c186:(0xb8,0),0x66c194:(0xc8,16),
             0x66c406:(0xb8,0),0x66c411:(0xc8,16),0x66c427:(0xb8,0),0x66c436:(0xc8,16),0x66c50d:(0x68,0),
             0x66c66d:(0x88,0),0x66c679:(0x90,8),0x66c68f:(0x88,0),0x66c69e:(0x90,8),
             0x66c700:(0xb8,0),0x66c70b:(0xc8,16),0x66c721:(0xb8,0),0x66c730:(0xc8,16)}
    for start,end in GROUPS:
        fragments=[f for f in capture.functions if start<=f[0]<end]
        need(len(fragments)=={0x66c100:3,0x66c300:3,0x66c590:3}[start] and
             fragments[-1][1]==end and all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),
             'Changed resource owner fragments')
        blob.extend(b'\xcc'*(-len(blob)%16));entry=len(blob);entries.append(entry)
        absolute(11,13);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326428);reject(b'\x0f\x85')
        for off in (0,4,8,12):
            blob.extend(b'\x45\x8b\x53'+bytes((off,)));capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
        # Published and owned counts cannot exceed registered objects.
        blob.extend(b'\x45\x8b\x53\x08\x45\x3b\x53\x04');reject(b'\x0f\x87')
        blob.extend(b'\x45\x8b\x53\x0c\x45\x3b\x53\x04');reject(b'\x0f\x87')
        if start==0x66c100:
            blob.extend(b'\x4c\x39\xd9');reject(b'\x0f\x85')
            blob.extend(b'\x45\x3b\x53\x08');reject(b'\x0f\x87')
        rows.append((entry,len(blob),b'\x01\0\0\0',None));first_row=len(rows)
        code_end=end
        source=capture.read(start,code_end-start);sources.append(dict(start=start,end=code_end,data=source))
        insns=list(capture.md.disasm(source,start));need(insns[-1].address+insns[-1].size==code_end,'Incomplete resource_ownership decode')
        for ins in insns:
            a=ins.address;at=len(blob);mapping[a]=at;text=ins.mnemonic+' '+ins.op_str
            mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
            if a in banks:
                key,offset,old=banks[a];need(mem.disp==old,'Changed owner array operand');bank(ins,key,offset,forced_index='r12' if a in (0x66c625,0x66c634,0x66c80f) else None)
            elif a in aliases:
                old,offset=aliases[a];need(mem.disp==old,'Changed owner row alias')
                raw=bytearray(ins.bytes);raw[ins.disp_offset:ins.disp_offset+ins.disp_size]=offset.to_bytes(ins.disp_size,'little');blob.extend(raw)
            elif a==0x66c130:
                # Native forward-copy order overwrites the pending row when
                # owned < published. Settle by promoting the pending object
                # with the complete swap below, not by copying that row away.
                need(text=='cmp edx, edi','Changed pending settlement loop');branch(b'\xe9',0x66c1fb)
            elif a==0x66c1fb:
                need(text=='mov r8d, edi','Changed pending source');absolute(11,14);blob.extend(b'\x49\x8b\x14\xfb')
            elif a==0x66c201:
                need(text=='call 0x66bc20','Changed pending move');branch(b'\xe8',('entry',0x66c300))
            elif a==0x66c206:
                need(text=='inc dword ptr [rbx + 0xc]','Changed pending ownership count');blob.extend(b'\x90') # promotion owns this increment
            elif a==0x66c375:
                # Promotion accepts a pending registered object. During a
                # settlement loop the owned count can temporarily exceed +8.
                need(text=='mov r14d, dword ptr [rsi + 0xc]','Changed ownership boundary');blob.extend(ins.bytes)
                blob.extend(b'\x3b\x5e\x04');reject()
                blob.extend(b'\x44\x3b\x76\x04');reject()
                blob.extend(b'\x44\x39\xf3');reject(b'\x0f\x82')
            elif a==0x66c5f7:
                need(text=='mov r14d, dword ptr [rbp + 0xc]','Changed demotion boundary');blob.extend(ins.bytes)
                blob.extend(b'\x44\x39\xf3');reject() # also rejects an empty owned prefix
            elif a==0x66c66a:
                need(text=='add rdx, rbp','Changed demotion phase alias');absolute(11,15);blob.extend(b'\x4c\x01\xda')
            elif a==0x66c6fd:
                need(text=='add r8, rbp','Changed demotion row alias');absolute(11,16);blob.extend(b'\x4d\x01\xd8')
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
            head=capture.read(u,4);need(head[0] in (1,33) and head[3]==0,'Unexpected resource_ownership unwind')
            n=4+((head[2]+1)&~1)*2;uw=bytearray(capture.read(u,n));parent=None
            def offset(old):return ends[b+old]-mapping[b] if old else 0
            uw[1]=offset(head[1]);i=0
            while i<head[2]:
                uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                need(op in (0,1,2,4,8),'Unexpected resource_ownership unwind operation');i+=2 if op in (1,4,8) else 1
            if head[0]==33:
                old=struct.unpack('<III',capture.read(u+n,12));need(old in fragments[:fragments.index((b,e,u))],'Foreign resource_ownership chain')
                parent=first_row+fragments.index(old)
            rows.append((mapping[b],ends[min(e,code_end)],bytes(uw),parent))
    for at,nxt,target in branches:
        if isinstance(target,tuple):target=entries[[b for b,e in GROUPS].index(target[1])]
        else:need(target in mapping,'Missing resource_ownership branch');target=mapping[target]
        fixes.append((at,nxt,1,0,target))
    code_bytes=len(blob);blob.extend(bytes(-len(blob)%4));unwind_offset=len(blob);functions=[]
    for b,e,uw,parent in rows:
        functions.append((b,e,len(blob)));blob.extend(uw)
        if parent is not None:blob.extend(struct.pack('<III',*functions[parent]))
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE and len(functions)==12,'Resource ownership image bounds')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,functions=functions,entries=entries,sources=sources,mapping=mapping)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_resource_ownership.py.',
           'static const uint8_t ep_loadout_resource_ownership_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutResourceOwnershipFixup ep_loadout_resource_ownership_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset'):
        lines.append(f'static const uint32_t ep_loadout_resource_ownership_{key} = {a[key]};')
    lines.append(f'static const uint32_t ep_loadout_resource_ownership_functions = {len(a["functions"])};')
    lines.append('static const uint32_t ep_loadout_resource_ownership_entries[] = {'+','.join(map(str,a['entries']))+'};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
