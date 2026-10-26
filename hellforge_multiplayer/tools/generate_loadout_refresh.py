"""Relocate complete saved 146E9D0 refresh, including chained GS metadata.

All player loops use the bound capacity. EBP's four equipment choices, enum,
level-table stride and flag value remain four. No game access.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need,GS_HANDLER
from generate_loadout_consumers import REG
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_REG_RIP

START,END,CAPTURE_END=0x146e9d0,0x146f38c,0x146f3a4
UNWIND=bytes.fromhex('191803000901140002700000')
COOKIE=0x70
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_refresh_template.h'


def build():
    capture=Capture();blob=bytearray();fixes=[];branches=[];mapping={};ends={};rows=[]
    fragments=[f for f in capture.functions if START<=f[0]<CAPTURE_END]
    need(len(fragments)==3 and fragments[0][0]==START and fragments[-1][1]==CAPTURE_END and
         all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),'Changed refresh fragments')
    need(capture.read(fragments[0][2],20)==UNWIND+struct.pack('<II',GS_HANDLER,COOKIE),'Changed refresh GS frame')
    def fix(raw,offset,key,kind=1,add=0):
        at=len(blob);blob.extend(raw);fixes.append((at+offset,len(blob),key,kind,add))
    def absolute(reg,key,add=0,kind=1):fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,kind,add)
    def branch(op,target):
        at=len(blob);blob.extend(op+bytes(4));branches.append((at+len(op),len(blob),target))
    def capacity(raw):fix(raw+bytes(4),len(raw),5,2)
    def memory(ins):
        mem=next(o.mem for o in ins.operands if o.type==X86_OP_MEM)
        need(ins.reg_name(mem.base) in ('rcx','rdi'),'Unexpected refresh widget base')
        # No original refresh instruction retains a value in volatile R11.
        absolute(11,4,-0x53a78,3);base=REG[ins.reg_name(mem.base)]
        blob.extend(bytes((0x4d,0x8d,0x1c,(base<<3)|3)))
        raw=bytearray(ins.bytes);m=ins.modrm_offset
        if raw[m]&7==4:raw[m+1]=(raw[m+1]&0xf8)|3
        else:raw[m]=(raw[m]&0xf8)|3
        p=0
        while raw[p] in (0x66,0xf2,0xf3,0x2e,0x3e,0x64,0x65):p+=1
        if 0x40<=raw[p]<=0x4f:raw[p]|=1
        else:raw[p:p]=b'\x41'
        blob.extend(raw)

    absolute(11,2);blob.extend(b'\x4c\x39\xd9');fix(b'\x0f\x85'+bytes(4),2,6,0)
    body=len(blob);rows.append((0,body,b'\x01\0\0\0',None));source=capture.read(START,END-START)
    insns=list(capture.md.disasm(source,START));need(insns[-1].address+insns[-1].size==END,'Incomplete refresh decode')
    table_ref=None
    for ins in insns:
        a=ins.address;at=len(blob);mapping[a]=at;text=ins.mnemonic+' '+ins.op_str
        mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
        if a==0x146ea28:
            need(text=='lea rbx, [rcx + 0x53a78]','Changed first widget');absolute(3,4)
        elif a==0x146ea44:
            need(text=='mov esi, ebp','Changed first player counter');capacity(b'\xbe')
        elif a in (0x146ed06,0x146edd0):
            need(text=='cmp esi, 4','Changed refresh player bound');capacity(b'\x81\xfe')
        elif a in (0x146ef7f,0x146f0bb):
            need(text=='lea rsi, [rdi + 0x562f9]','Changed player animation loop')
            capacity(b'\xbd');absolute(6,4,0x2881)
        elif a in (0x146ecd6,0x146eda0):
            need(text=='add rcx, 0x53a78','Changed derived widget')
            absolute(11,4,0,3);blob.extend(b'\x4c\x01\xd9')
        elif a==0x146ed48:
            blob.extend(ins.bytes);capacity(b'\x3d');fix(b'\x0f\x83'+bytes(4),2,6,0)
        elif a==0x146ed5e:
            need(text=='add r8, 0x10','Changed refresh record')
            absolute(11,3,0,3);blob.extend(b'\x4d\x01\xd8')
        elif a==0x146eb25:
            need(text=='mov ecx, dword ptr [r8 + rax*4 + 0x146f38c]','Changed refresh switch')
            absolute(11,1);table_ref=len(fixes)-1;blob.extend(b'\x41\x8b\x0c\x83')
        elif a==0x146eb2d:absolute(11,1);blob.extend(b'\x4c\x01\xd9')
        elif a==0x146ed7a:
            need(text=='call 0x146f3b0','Changed refresh close edge');fix(b'\xe8'+bytes(4),1,11,0)
        elif mem and 0x53a78<=mem.disp<0x72890 and ins.reg_name(mem.base) in ('rcx','rdi'):memory(ins)
        elif (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
            raw=bytes(ins.bytes);target=ins.operands[0].imm
            op=raw[:1] if raw[0] in (0xe8,0xe9) else b'\xe9' if raw[0]==0xeb else bytes((0x0f,raw[0]+0x10)) if 0x70<=raw[0]<=0x7f else raw[:2]
            if START<=target<END:branch(op,target)
            else:fix(op+bytes(4),len(op),0,0,target)
        else:
            blob.extend(ins.bytes)
            if mem and mem.base==X86_REG_RIP:fixes.append((at+ins.disp_offset,len(blob),0,0,a+ins.size+ins.disp))
        ends[a+ins.size]=len(blob)
        if a<START+UNWIND[1]:need(blob[at:]==ins.bytes and at-body==a-START,'Refresh root prologue moved')
    for at,nxt,target in branches:
        need(target in mapping,'Refresh branch leaves owned code');fixes.append((at,nxt,1,0,mapping[target]))
    for b,e,u in fragments:
        head=capture.read(u,4);n=4+((head[2]+1)&~1)*2
        uw=bytearray(capture.read(u,n))
        if b==START:uw+=bytes(8);parent='gs'
        else:
            need(head[0]==33 and head[3]==0,'Unexpected refresh chain')
            def offset(old):return ends[b+old]-mapping[b] if old else 0
            uw[1]=offset(head[1]);i=0
            while i<head[2]:
                uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                need(op in (0,1,2,4,8),'Unexpected refresh unwind operation');i+=2 if op in (1,4,8) else 1
            parent=struct.unpack('<III',capture.read(u+n,12));need(parent==fragments[0],'Changed refresh chain parent')
        rows.append((mapping[b],ends[min(e,END)],bytes(uw),parent))
    blob.extend(b'\xcc'*(-len(blob)%16));handler_offset=len(blob);fix(b'\xe9'+bytes(4),1,0,0,GS_HANDLER)
    code_bytes=len(blob);rows.append((handler_offset,code_bytes,b'\x01\0\0\0',None))
    blob.extend(bytes(-len(blob)%4));jump_table=len(blob)
    for target in struct.unpack('<6I',capture.read(0x146f38c,24)):
        need(target in mapping,'Changed refresh dispatch target');blob.extend(struct.pack('<I',mapping[target]))
    need(table_ref is not None,'Missing refresh switch');fixes[table_ref]=fixes[table_ref][:-1]+(jump_table,)
    unwind_offset=len(blob);functions=[]
    for b,e,uw,parent in rows:
        functions.append((b,e,len(blob)))
        if parent=='gs':blob.extend(uw[:-8]+struct.pack('<II',handler_offset,COOKIE))
        else:
            blob.extend(uw)
            if parent:blob.extend(struct.pack('<III',*functions[1]))
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE and len(functions)==5,'Refresh image bounds')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,handler_offset=handler_offset,functions=functions,source=source,mapping=mapping)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_refresh.py.',
           'static const uint8_t ep_loadout_refresh_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutRefreshFixup ep_loadout_refresh_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset','handler_offset'):
        lines.append(f'static const uint32_t ep_loadout_refresh_{key} = {a[key]};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
