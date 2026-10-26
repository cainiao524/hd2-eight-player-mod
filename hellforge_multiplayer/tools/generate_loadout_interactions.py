"""Relocate saved loadout input, editing and edit-close operations.

Player navigation uses the configured capacity, including non-powers of two.
Inner equipment choices and event enums remain native. No game access.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need
from generate_loadout_consumers import REG
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_REG_RIP

GROUPS=((0x146d9b0,0x146e07c),(0x146e0a0,0x146e9cb),(0x146f3b0,0x146f504))
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_interactions_template.h'


def build():
    capture=Capture();blob=bytearray();fixes=[];branches=[];mapping={};ends={};rows=[];entries=[];sources=[]
    table_refs=[]
    def fix(raw,offset,key,kind=1,add=0):
        at=len(blob);blob.extend(raw);fixes.append((at+offset,len(blob),key,kind,add))
    def absolute(reg,key,add=0,kind=1):fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,kind,add)
    def branch(op,target):
        at=len(blob);blob.extend(op+bytes(4));branches.append((at+len(op),len(blob),target))
    def reject(op=b'\x0f\x83'):fix(op+bytes(4),len(op),6,0)
    def capacity(raw,add=0):fix(raw+bytes(4),len(raw),5,2,add)
    def memory(ins):
        # Input and close have no live R11. Edit does: its catalog index and
        # four-choice iterator must survive every local-widget reference.
        mem=next(o.mem for o in ins.operands if o.type==X86_OP_MEM)
        base=REG[ins.reg_name(mem.base)];absolute(11,4,-0x53a78,3)
        blob.extend(bytes((0x4d+(2 if base>=8 else 0),0x8d,0x1c,((base&7)<<3)|3)))
        raw=bytearray(ins.bytes);m=ins.modrm_offset
        if raw[m]&7==4:raw[m+1]=(raw[m+1]&0xf8)|3
        else:raw[m]=(raw[m]&0xf8)|3
        p=0
        while raw[p] in (0x66,0xf2,0xf3,0x2e,0x3e,0x64,0x65):p+=1
        if 0x40<=raw[p]<=0x4f:raw[p]|=1
        else:raw[p:p]=b'\x41'
        blob.extend(raw)
    def navigation(right):
        tag=('nav',right);done=0x146e044 if right else 0x146dfba
        blob.extend(bytes.fromhex('448b8bc8392700'));capacity(b'\x41\x81\xf9');reject()
        blob.extend(b'\x45\x89\xc8');capacity(b'\x41\xba') # candidate, attempts
        mapping[(tag,'loop')]=len(blob)
        if right:
            blob.extend(b'\x41\xff\xc0');capacity(b'\x41\x81\xf8');branch(b'\x0f\x82',(tag,'index'))
            blob.extend(b'\x45\x31\xc0')
        else:
            blob.extend(b'\x45\x85\xc0');branch(b'\x0f\x85',(tag,'decrement'))
            capacity(b'\x41\xb8');mapping[(tag,'decrement')]=len(blob);blob.extend(b'\x41\xff\xc8')
        mapping[(tag,'index')]=len(blob)
        blob.extend(b'\x49\x69\xc8'+struct.pack('<I',0x1ee18));absolute(11,4)
        blob.extend(bytes.fromhex('4180bc0b12ee010000'));branch(b'\x0f\x84',(tag,'found'))
        blob.extend(b'\x41\xff\xca');branch(b'\x0f\x85',(tag,'loop'));branch(b'\xe9',done)
        mapping[(tag,'found')]=len(blob);blob.extend(bytes.fromhex('448983c83927004589c1'));branch(b'\xe9',done)

    for start,end in GROUPS:
        b,e,uw_at=next(f for f in capture.functions if f[0]==start)
        need(e==(0x146e0a0 if start==0x146d9b0 else end),'Changed interaction extent')
        blob.extend(b'\xcc'*(-len(blob)%16));entry=len(blob);entries.append(entry)
        absolute(11,2);blob.extend(b'\x4c\x39\xd9');reject(b'\x0f\x85')
        if start!=0x146f3b0:
            absolute(11,9);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326468);reject(b'\x0f\x85')
            blob.extend(b'\x41\x8b\x83\x84\0\0\0');capacity(b'\x3d');reject(b'\x0f\x87')
            blob.extend(b'\x41\x39\x83\x88\0\0\0');reject(b'\x0f\x87')
        rows.append((entry,len(blob),b'\x01\0\0\0'))
        source=capture.read(start,end-start);sources.append(dict(start=start,end=end,data=source))
        insns=list(capture.md.disasm(source,start));need(insns[-1].address+insns[-1].size==end,'Incomplete interaction decode')
        for ins in insns:
            a=ins.address;mapping[a]=len(blob);text=ins.mnemonic+' '+ins.op_str
            mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
            if 0x146df6c<=a<0x146dfba or 0x146e002<=a<0x146e044:
                if a in (0x146df6c,0x146e002):navigation(a==0x146e002)
                ends[a+ins.size]=len(blob);continue
            if a==0x146dd56:
                need(text=='mov eax, dword ptr [rsi + rax*4 + 0x146e07c]','Changed input dispatch')
                absolute(11,1);table_refs.append(len(fixes)-1);blob.extend(b'\x41\x8b\x04\x83')
            elif a==0x146dd5d:
                absolute(11,1);blob.extend(b'\x4c\x01\xd8')
            elif a in (0x146ddba,0x146df40):
                need(text==('lea rsi, [rbx + 0x781e8]' if a==0x146ddba else 'add rbx, 0x781e8'),'Changed remote-widget loop')
                absolute(6 if a==0x146ddba else 3,4,0x781e8-0x53a78)
            elif a in (0x146ddc1,0x146df47):
                need(text=='mov edi, 3','Changed remote-widget count');capacity(b'\xbf',-1)
                blob.extend(b'\x85\xff');branch(b'\x0f\x84',0x146dddd if a==0x146ddc1 else 0x146e05f)
            elif a in (0x146dcc9,0x146dce3,0x146dfd7,0x146dfee,0x146e050):
                need(ins.mnemonic=='add' and ins.op_str.startswith('rcx, '),'Changed derived widget')
                absolute(11,4,ins.operands[1].imm-0x53a78,3);blob.extend(b'\x4c\x01\xd9')
            elif a in (0x146dad2,0x146de40,0x146e12a,0x146e89e):
                need(mem.disp==0xe8,'Changed roster pointer array');reg=REG[ins.reg_name(ins.operands[0].reg)]
                absolute(reg,10);blob.extend(b'\x4d\x8b\x36' if reg==14 else b'\x48\x8b\x00')
            elif a in (0x146de19,0x146de79):
                need(mem.disp==0x3ac,'Changed roster properties');absolute(11,10,0x584)
                blob.extend(b'\x41\x8b\x3b' if a==0x146de19 else b'\x41\x8b\x0b')
            elif a in (0x146e1b3,0x146e867):
                need(text in ('cmp r10d, 4','cmp eax, 4'),'Changed record bound')
                capacity(b'\x41\x81\xfa' if a==0x146e1b3 else b'\x3d')
            elif a in (0x146e1c0,0x146e877):
                need(mem.disp==0x10,'Changed record base');absolute(10 if a==0x146e1c0 else 6,3)
            elif a in (0x146e68b,0x146e6b0,0x146e9a3):
                need(ins.op_str.endswith(', 0x10'),'Changed derived record')
                absolute(11,3,0,3);blob.extend(b'\x4c\x01\xda' if a==0x146e68b else b'\x4c\x01\xd9')
            elif a==0x146dd04:
                need(text=='call 0x146e9d0','Changed input refresh edge');fix(b'\xe8'+bytes(4),1,11,0)
            elif mem and 0x53a78<=mem.disp<0x72890 and ins.reg_name(mem.base) in ('rbx','rdi','rsi'):
                if a==0x146f47d:capacity(b'\xbd') # after the four-choice cleanup
                if start==0x146e0a0:
                    need(not mem.index,'Unexpected indexed edit widget')
                    if ins.mnemonic=='lea':absolute(REG[ins.reg_name(ins.operands[0].reg)],4,mem.disp-0x53a78)
                    elif ins.mnemonic=='mov' and ins.reg_name(ins.operands[0].reg)=='eax':
                        absolute(0,4,mem.disp-0x53a78);blob.extend(b'\x8b\x00')
                    else:
                        need(a==0x146e609 and text=='cmp dword ptr [rdi + 0x6f290], 1','Unknown edit widget operand')
                        absolute(0,4,mem.disp-0x53a78);blob.extend(b'\x83\x38\x01')
                else:memory(ins)
            elif (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                raw=bytes(ins.bytes);target=ins.operands[0].imm
                op=raw[:1] if raw[0] in (0xe8,0xe9) else b'\xe9' if raw[0]==0xeb else bytes((0x0f,raw[0]+0x10)) if 0x70<=raw[0]<=0x7f else raw[:2]
                if any(b<=target<e for b,e in GROUPS):branch(op,('entry',target) if ins.mnemonic=='call' else target)
                else:fix(op+bytes(4),len(op),0,0,target)
            else:
                blob.extend(ins.bytes)
                if mem and mem.base==X86_REG_RIP:fixes.append((len(blob)-ins.size+ins.disp_offset,len(blob),0,0,a+ins.size+ins.disp))
            ends[a+ins.size]=len(blob)
            # Callback results can change focus/record selection. Bound each
            # freshly loaded index before deriving a relocated pointer.
            if start==0x146d9b0 and text in ('mov eax, dword ptr [rcx + 0x2739c8]','mov eax, dword ptr [rbx + 0x2739c8]'):
                capacity(b'\x3d');reject()
            if a in (0x146e677,0x146e6a3,0x146e996):
                capacity(b'\x3d');branch(b'\x0f\x83',0x146e1a1)
        head=capture.read(uw_at,4);need(head[0]==1 and head[3]==0,'Unexpected interaction unwind')
        uw=bytearray(capture.read(uw_at,4+((head[2]+1)&~1)*2))
        def offset(old):return ends[start+old]-mapping[start] if old else 0
        uw[1]=offset(head[1]);i=0
        while i<head[2]:
            uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
            need(op in (0,1,2,4,8),'Unexpected unwind operation');i+=2 if op in (1,4,8) else 1
        rows.append((mapping[start],ends[end],bytes(uw)))
    for at,nxt,target in branches:
        if isinstance(target,tuple) and target[0]=='entry':dest=entries[[b for b,e in GROUPS].index(target[1])]
        else:need(target in mapping,'Missing interaction branch');dest=mapping[target]
        fixes.append((at,nxt,1,0,dest))
    code_bytes=len(blob);blob.extend(bytes(-len(blob)%4));jump_table=len(blob)
    for target in struct.unpack('<9I',capture.read(0x146e07c,36)):
        need(target in mapping,'Unknown native dispatch target');blob.extend(struct.pack('<I',mapping[target]))
    for i in table_refs:fixes[i]=fixes[i][:-1]+(jump_table,)
    unwind_offset=len(blob);functions=[]
    for b,e,uw in rows:functions.append((b,e,len(blob)));blob.extend(uw)
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE,'Interaction storage exceeded')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,entries=entries,functions=functions,sources=sources,mapping=mapping)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_interactions.py.',
           'static const uint8_t ep_loadout_interactions_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutInteractionFixup ep_loadout_interaction_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset'):
        lines.append(f'static const uint32_t ep_loadout_interaction_{key} = {a[key]};')
    lines.append('static const uint32_t ep_loadout_interaction_entries[] = {'+','.join(map(str,a['entries']))+'};')
    lines.append(f'static const uint32_t ep_loadout_interaction_functions = {len(a["functions"])};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
