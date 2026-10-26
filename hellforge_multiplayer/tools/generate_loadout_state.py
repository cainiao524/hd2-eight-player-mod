"""Relocate saved loadout state, return, context action and timer dispatch.

The native seven-case switch and eight observed state delays are owned tables.
State 7 keeps the native default arm/zero delay; these are not player limits.
Only the player widgets and selected player's records use configured capacity.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need,GS_HANDLER
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

# Return is entry zero, permitting the control/state dependency to bind both
# images before either is prepared or exposed. Leave is control's entry zero.
GROUPS=((0x1470740,0x14708a8),(0x146ac60,0x146b188),(0x14708d0,0x1470a3c),(0x146abc0,0x146ac53))
UNWIND=bytes.fromhex('192609001764170017541600173415001701120010700000')
COOKIE=0x60
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_state_template.h'


def build():
    capture=Capture();blob=bytearray();fixes=[];branches=[];mapping={};ends={};rows=[];entries=[];sources=[];tables=[]
    def fix(raw,offset,key,kind=1,add=0):
        at=len(blob);blob.extend(raw);fixes.append((at+offset,len(blob),key,kind,add))
    def absolute(reg,key,add=0):fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,1,add)
    def capacity(raw):fix(raw+bytes(4),len(raw),5,2)
    def reject(op=b'\x0f\x83'):fix(op+bytes(4),len(op),6,0)
    def branch(op,target):
        at=len(blob);blob.extend(op+bytes(4));branches.append((at+len(op),len(blob),target))
    for start,end in GROUPS:
        fragments=[f for f in capture.functions if start<=f[0]<end]
        code_end=0x146b16c if start==0x146ac60 else end
        need(len(fragments)=={0x1470740:3,0x146ac60:5,0x14708d0:1,0x146abc0:1}[start] and
             fragments[-1][1]==end and all(a[1]==b[0] for a,b in zip(fragments,fragments[1:])),
             'Changed state fragments')
        blob.extend(b'\xcc'*(-len(blob)%16));entry=len(blob);entries.append(entry)
        absolute(11,2);blob.extend(b'\x4c\x39\xd9');reject(b'\x0f\x85')
        absolute(11,9);fix(b'\x4c\x39\x1d'+bytes(4),3,0,0,0x3326468);reject(b'\x0f\x85')
        blob.extend(bytes.fromhex('458b9384000000'));capacity(b'\x41\x81\xfa');reject(b'\x0f\x87')
        blob.extend(bytes.fromhex('45399388000000'));reject(b'\x0f\x87')
        if start==0x146ac60:blob.extend(b'\x83\xfa\x07');reject(b'\x0f\x87')
        body=len(blob);rows.append((entry,body,b'\x01\0\0\0',None));first_row=len(rows)
        source=capture.read(start,code_end-start);sources.append(dict(start=start,end=code_end,data=source))
        insns=list(capture.md.disasm(source,start));need(insns[-1].address+insns[-1].size==code_end,'Incomplete state decode')
        for ins in insns:
            a=ins.address;at=len(blob);mapping[a]=at;text=ins.mnemonic+' '+ins.op_str
            mem=next((o.mem for o in ins.operands if o.type==X86_OP_MEM),None)
            if a in (0x147078b,0x14707b6,0x146ac9b):
                need(ins.mnemonic=='mov' and mem.disp==0xe8,'Changed state descriptor')
                if a==0x146ac9b:absolute(6,10);blob.extend(b'\x48\x8b\x36')
                else:absolute(0,10);blob.extend(b'\x48\x8b\x00')
            elif a in (0x1470798,0x14707c3):
                expected=0xfffffffd if a==0x1470798 else 0xfffffff7
                need(text==f'and dword ptr [rcx + 0x3ac], {expected:#x}','Changed state flags')
                absolute(11,10,0x584);blob.extend(bytes((0x41,0x83,0x23,expected&255)))
            elif a==0x146acb8:
                need(text=='mov edx, dword ptr [rax + 0x3a8]','Changed state component ID')
                absolute(11,10,0x580);blob.extend(b'\x41\x8b\x13')
            elif a in (0x1470823,0x1470853,0x147087f):
                need(text=='imul rcx, rax, 0x9f0','Changed selected record stride')
                capacity(b'\x3d');reject();blob.extend(ins.bytes)
            elif a in (0x1470837,0x1470863,0x147088e):
                offset={0x1470837:0,0x1470863:0x60,0x147088e:0xc0}[a]
                need(ins.mnemonic=='mov' and ins.reg_name(ins.operands[0].reg)=='r9d' and mem.disp==offset+0x10,'Changed selected equipment field')
                # RCX is the selected record's scaled offset; MOV preserves it
                # and the engine's category/stack arguments through the call.
                absolute(11,3,offset);blob.extend(b'\x45\x8b\x0c\x0b')
            elif a==0x146ae35:
                need(text=='lea rbx, [rdi + 0x53a78]','Changed state widget base');absolute(3,4)
            elif a==0x146ae3c:
                need(text=='mov esi, 4','Changed state widget bound');capacity(b'\xbe')
            elif a==0x146ae18:
                need(text=='lea r14, [rip - 0x146ae1f]','Changed state table base');absolute(14,1)
            elif a in (0x146ae28,0x146b129):
                need(mem.base and ins.reg_name(mem.base)=='r14' and ins.reg_name(mem.index)=='rbp' and mem.scale==4,'Changed state table operand')
                raw=bytearray(ins.bytes);raw[ins.disp_offset:ins.disp_offset+4]=bytes(4)
                tables.append((len(blob)+ins.disp_offset,'switch' if a==0x146ae28 else 'delay'));blob.extend(raw)
            elif a in (0x1470a2c,0x146abee):
                target,key=(0x146f510,11) if a==0x1470a2c else (0x146b190,12)
                need(text==f'call {target:#x}','Changed state sibling call');fix(b'\xe8'+bytes(4),1,key,0)
            elif (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                raw=bytes(ins.bytes);target=ins.operands[0].imm
                op=raw[:1] if raw[0] in (0xe8,0xe9) else b'\xe9' if raw[0]==0xeb else bytes((0x0f,raw[0]+0x10)) if 0x70<=raw[0]<=0x7f else raw[:2]
                if target in [b for b,e in GROUPS]:branch(op,('entry',target)) # includes timer tail calls
                elif any(b<=target<e for b,e in GROUPS):branch(op,target)
                else:fix(op+bytes(4),len(op),0,0,target)
            else:
                blob.extend(ins.bytes)
                if mem and mem.base==X86_REG_RIP:fixes.append((at+ins.disp_offset,len(blob),0,0,a+ins.size+ins.disp))
            ends[a+ins.size]=len(blob)
            if start==0x146ac60 and a<start+UNWIND[1]:need(blob[at:]==ins.bytes and at-body==a-start,'State GS prologue moved')
        for b,e,u in fragments:
            head=capture.read(u,4);n=4+((head[2]+1)&~1)*2;uw=bytearray(capture.read(u,n));parent=None
            if b==0x146ac60:
                need(capture.read(u,n+8)==UNWIND+struct.pack('<II',GS_HANDLER,COOKIE),'Changed state GS contract');uw+=bytes(8);parent='gs'
            else:
                need(head[0] in (1,33) and head[3]==0,'Unexpected state unwind')
                def offset(old):return ends[b+old]-mapping[b] if old else 0
                uw[1]=offset(head[1]);i=0
                while i<head[2]:
                    uw[4+2*i]=offset(uw[4+2*i]);op=uw[5+2*i]&15
                    need(op in (0,1,2,4,8),'Unexpected state unwind operation');i+=2 if op in (1,4,8) else 1
                if head[0]==33:
                    old=struct.unpack('<III',capture.read(u+n,12));need(old in fragments[:fragments.index((b,e,u))],'Foreign state chain')
                    parent=first_row+fragments.index(old)
            rows.append((mapping[b],ends[min(e,code_end)],bytes(uw),parent))
    for at,nxt,target in branches:
        if isinstance(target,tuple):target=entries[[b for b,e in GROUPS].index(target[1])]
        else:need(target in mapping,'Missing state branch');target=mapping[target]
        fixes.append((at,nxt,1,0,target))
    blob.extend(b'\xcc'*(-len(blob)%16));handler_offset=len(blob);fix(b'\xe9'+bytes(4),1,0,0,GS_HANDLER)
    code_bytes=len(blob);rows.append((handler_offset,code_bytes,b'\x01\0\0\0',None));blob.extend(bytes(-len(blob)%4))
    switch_offset=len(blob)
    for target in struct.unpack('<7I',capture.read(0x146b16c,28)):
        need(target in mapping,'Unknown state switch target');blob.extend(struct.pack('<I',mapping[target]))
    delay_offset=len(blob);blob.extend(capture.read(0x21da890,32))
    for at,kind in tables:struct.pack_into('<I',blob,at,switch_offset if kind=='switch' else delay_offset)
    unwind_offset=len(blob);functions=[]
    for b,e,uw,parent in rows:
        functions.append((b,e,len(blob)))
        if parent=='gs':blob.extend(uw[:-8]+struct.pack('<II',handler_offset,COOKIE))
        else:
            blob.extend(uw)
            if parent is not None:blob.extend(struct.pack('<III',*functions[parent]))
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE and len(functions)==15,'State image bounds')
    return dict(blob=bytes(blob),fixes=fixes,code_bytes=code_bytes,unwind_offset=unwind_offset,
                table_offset=table_offset,handler_offset=handler_offset,functions=functions,entries=entries,sources=sources,mapping=mapping)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_state.py.',
           'static const uint8_t ep_loadout_state_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutStateFixup ep_loadout_state_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset','handler_offset'):
        lines.append(f'static const uint32_t ep_loadout_state_{key} = {a[key]};')
    lines.append('static const uint32_t ep_loadout_state_entries[] = {'+','.join(map(str,a['entries']))+'};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
