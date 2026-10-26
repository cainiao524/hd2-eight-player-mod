"""Relocate saved resource update and ready-state queries.

Use the owner sidecar banks and shared resource transforms. State value 4,
45 effect types, 22 effect channels and four hash buckets keep native meaning.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

GROUPS=((0x66b090,0x66b8c5),(0x663240,0x66330f),(0x663310,0x6633c9))
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_resource_tick_template.h'


def build():
    capture=Capture();blob=bytearray();fixes=[];branches=[];mapping={};ends={};rows=[];entries=[];sources=[];tables=[]
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
        # each reviewed site; slot queries instead use R10 to retain owner in R11.
        mem=next(o.mem for o in ins.operands if o.type==X86_OP_MEM)
        need(mem.base and ins.reg_name(mem.base) in ('rbx','rcx','rsi','rdi','r14','r11','rdx'),'Unexpected owner bank base')
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
    banks={
        0x66b121:(14,0,0x68),0x66b147:(14,0,0x68),0x66b3b7:(14,0,0x68),0x66b410:(14,0,0x68),0x66b52e:(14,0,0x68),
        0x66b116:(15,4,0x8c),0x66b138:(15,4,0x8c),0x66b185:(15,8,0x90),0x66b192:(15,8,0x90),0x66b1a4:(15,0,0x88),
        0x66b1b8:(15,0,0x88),0x66b1de:(15,8,0x90),0x66b1f4:(15,4,0x8c),
        0x66b42d:(16,8,0xc0),0x66b477:(16,4,0xbc),0x66b4fc:(16,0,0xb8),0x66b510:(16,0,0xb8),0x66b518:(16,12,0xc4),
        0x66b75f:(16,9,0xc1),0x66b77d:(16,9,0xc1),0x66b798:(16,12,0xc4),0x66b7a9:(16,12,0xc4),0x66b825:(16,9,0xc1),0x66b830:(16,9,0xc1),
        0x66b4f4:(17,0,0x108),0x6632ce:(16,0,0xb8),0x6633ae:(16,0,0xb8),
    }
    for start,end in GROUPS:
        fragments=[f for f in capture.functions if start<=f[0]<end]
        need(len(fragments)=={0x66b090:5,0x663240:1,0x663310:4}[start] and
             fragments[-1][1]==end and all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),
             'Changed resource update fragments')
        blob.extend(b'\xcc'*(-len(blob)%16));entry=len(blob);entries.append(entry)
        absolute(11,13);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326428);reject(b'\x0f\x85')
        for off in (0,4,8,12):
            blob.extend(b'\x45\x8b\x53'+bytes((off,)));capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
        absolute(10,11);fix(b'\x4c\x39\x15'+bytes(4),3,0,0,0x33265f0);reject(b'\x0f\x85')
        if start==0x66b090:blob.extend(b'\x4c\x39\xd9')
        else:blob.extend(b'\x4c\x39\xd1')
        reject(b'\x0f\x85')
        if start==0x663310:capacity(b'\x81\xfa');reject()
        rows.append((entry,len(blob),b'\x01\0\0\0',None));first_row=len(rows)
        code_end=0x66b890 if start==0x66b090 else end
        source=capture.read(start,code_end-start);sources.append(dict(start=start,end=code_end,data=source))
        insns=list(capture.md.disasm(source,start));need(insns[-1].address+insns[-1].size==code_end,'Incomplete resource_tick decode')
        for ins in insns:
            a=ins.address;at=len(blob);mapping[a]=at;text=ins.mnemonic+' '+ins.op_str
            mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
            if a in banks:
                key,offset,old=banks[a];need(mem.disp==old,'Changed resource tick array');bank(ins,key,offset,scratch=10 if a==0x6633ae else 11)
                if a==0x66b477:capacity(b'\x81\xff');reject()
            elif a==0x66b0f0:
                need(text=='lea r15, [r14 + 0x108]','Changed state cell base');absolute(15,17)
            elif a in (0x66b451,0x663261):
                need(mem.disp==0x11d18 and ins.mnemonic=='lea','Changed resource scan base');absolute(0 if a==0x66b451 else 14,12)
            elif a in (0x66b466,0x6632de):
                need(text==('cmp ecx, 4' if a==0x66b466 else 'cmp esi, 4'),'Changed resource scan bound')
                capacity(b'\x81\xf9' if a==0x66b466 else b'\x81\xfe')
            elif a in (0x66b4c0,0x66b4c9,0x66b4d1,0x66b4da,0x66b4e3):
                need(mem.disp in (0x11d18,0x11d1c,0x11d2c,0x11d3c,0x11d4c) and ins.reg_name(mem.index)=='r13','Changed inline resource writer')
                bank(ins,12,mem.disp-0x11d18,forced_index='rcx')
            elif a==0x663321:
                need(text=='mov eax, dword ptr [rdx + rcx + 0x11d18]','Changed slot resource read');bank(ins,12,forced_index='rdx',scratch=10)
            elif a==0x6632c8:
                need(text=='mov edx, eax','Changed any-state hash result')
                blob.extend(b'\x83\xf8\xff');branch(b'\x0f\x84',0x6632d8)
                capacity(b'\x3d');reject();blob.extend(b'\x3b\x47\x04');reject();blob.extend(ins.bytes)
            elif a==0x6633a8:
                need(text=='mov ecx, eax','Changed slot-state hash result')
                blob.extend(b'\x83\xf8\xff');branch(b'\x0f\x85',('slot_valid',a))
                blob.extend(b'\x31\xc0');branch(b'\xe9',0x6633ba)
                slot_valid=len(blob);capacity(b'\x3d');reject();blob.extend(b'\x41\x3b\x43\x04');reject();blob.extend(ins.bytes)
            elif a==0x66b60b:
                need(text=='lea r14, [rip - 0x66b612]','Changed resource effect table base');absolute(14,1)
            elif a in (0x66b623,0x66b62c):
                need(mem.disp in (0x66b898,0x66b890),'Changed resource effect table')
                raw=bytearray(ins.bytes);raw[ins.disp_offset:ins.disp_offset+4]=bytes(4)
                tables.append((len(blob)+ins.disp_offset,a==0x66b623));blob.extend(raw)
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
            head=capture.read(u,4);need(head[0] in (1,33) and head[3]==0,'Unexpected resource_tick unwind')
            n=4+((head[2]+1)&~1)*2;uw=bytearray(capture.read(u,n));parent=None
            def offset(old):return ends[b+old]-mapping[b] if old else 0
            uw[1]=offset(head[1]);i=0
            while i<head[2]:
                uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                need(op in (0,1,2,4,8),'Unexpected resource_tick unwind operation');i+=2 if op in (1,4,8) else 1
            if head[0]==33:
                old=struct.unpack('<III',capture.read(u+n,12));need(old in fragments[:fragments.index((b,e,u))],'Foreign resource_tick chain')
                parent=first_row+fragments.index(old)
            rows.append((mapping[b],ends[min(e,code_end)],bytes(uw),parent))
    for at,nxt,target in branches:
        if isinstance(target,tuple):target=slot_valid if target[0]=='slot_valid' else entries[[b for b,e in GROUPS].index(target[1])]
        else:need(target in mapping,'Missing resource_tick branch');target=mapping[target]
        fixes.append((at,nxt,1,0,target))
    code_bytes=len(blob);blob.extend(bytes(-len(blob)%4));switch_offset=len(blob)
    for target in struct.unpack('<2I',capture.read(0x66b890,8)):
        need(target in mapping,'Changed resource effect arm');blob.extend(struct.pack('<I',mapping[target]))
    map_offset=len(blob);selectors=capture.read(0x66b898,45);need(all(x<2 for x in selectors),'Changed effect selectors');blob.extend(selectors)
    for at,is_map in tables:struct.pack_into('<I',blob,at,map_offset if is_map else switch_offset)
    blob.extend(bytes(-len(blob)%4));unwind_offset=len(blob);functions=[]
    for b,e,uw,parent in rows:
        functions.append((b,e,len(blob)));blob.extend(uw)
        if parent is not None:blob.extend(struct.pack('<III',*functions[parent]))
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE and len(functions)==13,'Resource tick image bounds')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,functions=functions,entries=entries,sources=sources,mapping=mapping)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_resource_tick.py.',
           'static const uint8_t ep_loadout_resource_tick_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutResourceTickFixup ep_loadout_resource_tick_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset'):
        lines.append(f'static const uint32_t ep_loadout_resource_tick_{key} = {a[key]};')
    lines.append(f'static const uint32_t ep_loadout_resource_tick_functions = {len(a["functions"])};')
    lines.append('static const uint32_t ep_loadout_resource_tick_entries[] = {'+','.join(map(str,a['entries']))+'};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
