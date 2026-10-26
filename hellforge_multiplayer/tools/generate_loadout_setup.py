"""Relocate the saved 1466170 native screen setup; never access a game.

The original controls/parent attachment stay native. Player widget positions
come from an immutable per-slot table, not a read past the four-float table.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture, PROJECT, need, GS_HANDLER
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

START,END=0x1466170,0x1467325
UNWIND=bytes.fromhex('19350f002768140023743300236432002334310023012a0018f016e014d012c010500000')
COOKIE=0x130
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_setup_template.h'


def build():
    capture=Capture();b,e,at=next(f for f in capture.functions if f[0]==START)
    need(e==END and capture.read(at,len(UNWIND)+8)==UNWIND+struct.pack('<II',GS_HANDLER,COOKIE),'Changed setup unwind/GS contract')
    blob=bytearray();fixes=[];branches=[];mapping={}
    def fix(raw,operand,key,kind=1,add=0):
        base=len(blob);blob.extend(raw);fixes.append((base+operand,len(blob),key,kind,add))
    def absolute(reg,key,add=0):fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,1,add)
    def branch(op,target):
        base=len(blob);blob.extend(op+bytes(4));branches.append((base+len(op),len(blob),target))
    absolute(11,2);blob.extend(b'\x4c\x39\xd9');fix(b'\x0f\x85'+bytes(4),2,6,0)
    body=len(blob);source=capture.read(b,e-b);insns=list(capture.md.disasm(source,b))
    need(insns[-1].address+insns[-1].size==END,'Incomplete setup decode')
    layout_fix=None
    expected={
        0x1466ad4:'lea r12, [rip + 0xd724dd]',0x1466adb:'lea rbx, [rdi + 0x562f9]',
        0x1466ae2:'lea rsi, [rdi + 0x53a78]',0x1466afd:'mov dword ptr [rbp + 0x20], 0',
        0x1466b07:'mov dword ptr [rbp + 0x24], 0x42de0000',0x1466b0e:'mov rdx, qword ptr [rbp + 0x20]',
        0x1466b17:'movss xmm1, dword ptr [r12]',0x1466b20:'movss dword ptr [rsp + 0x48], xmm1',
        0x1466b26:'mov dword ptr [rsp + 0x4c], 0',0x1466b2e:'mov rdx, qword ptr [rsp + 0x48]',
        0x1466b38:'mov qword ptr [rsp + 0x40], 0x3f000000',0x1466b44:'mov rdx, qword ptr [rsp + 0x40]',
        0x1466c42:'add r12, 4',0x14670c1:'mov dword ptr [rdi + 0x27d4], ecx',
        0x14670c7:'mov dword ptr [rdi + rcx*4 + 0x27d8], r14d',0x14670cf:'mov dword ptr [rdi + 0x27e8], ecx',
    }
    seen=set()
    for ins in insns:
        a=ins.address;mapping[a]=len(blob);start=len(blob)
        if a in expected:
            need(ins.mnemonic+' '+ins.op_str==expected[a],'Changed setup operand');seen.add(a)
        if a==0x1466ad4:
            absolute(12,1);layout_fix=len(fixes)-1
        elif a==0x1466adb:absolute(3,4,0x2881)
        elif a==0x1466ae2:
            absolute(6,4)
            # R13=4 was an equipment enum AND a byte stride earlier. Replace
            # it only here, once it becomes the outer player-loop counter.
            fix(b'\x41\xbd'+bytes(4),2,5,2)
        elif a in (0x1466afd,0x1466b07,0x1466b17,0x1466b20,0x1466b26,0x1466b38):blob.extend(b'\x90')
        elif a==0x1466b0e:blob.extend(b'\x49\x8b\x14\x24')
        elif a==0x1466b2e:blob.extend(b'\x49\x8b\x54\x24\x08')
        elif a==0x1466b44:blob.extend(b'\x49\x8b\x54\x24\x10')
        elif a==0x1466c42:blob.extend(b'\x49\x83\xc4\x18')
        elif a in (0x1466f26,0x1466f31,0x1466f3c,0x1466f47):
            need(ins.mnemonic=='mov' and ins.op_str.endswith(', 0xffffffffffffffff'),'Changed map reset')
            if a in (0x1466f26,0x1466f31):
                absolute(11,7 if a==0x1466f26 else 8)
                for offset in (0,8,16,24):blob.extend(b'\x49\xc7\x43'+bytes((offset,))+b'\xff'*4)
            else:blob.extend(b'\x90')
        elif a==0x14670c1:
            fix(b'\x81\xf9'+bytes(4),2,5,2);branch(b'\x0f\x83',0x1466f9d)
            blob.extend(ins.bytes)
        elif a==0x14670c7:absolute(11,7);blob.extend(b'\x45\x89\x34\x8b')
        elif a==0x14670cf:absolute(11,8);blob.extend(b'\x41\x89\x0b')
        elif (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
            raw=bytes(ins.bytes);target=ins.operands[0].imm
            if raw[0] in (0xe8,0xe9):op=raw[:1]
            elif raw[0]==0xeb:op=b'\xe9'
            elif 0x70<=raw[0]<=0x7f:op=bytes((0x0f,raw[0]+0x10))
            else:
                need(raw[0]==0x0f and 0x80<=raw[1]<=0x8f,'Unsupported setup branch');op=raw[:2]
            if START<=target<END:branch(op,target)
            else:fix(op+bytes(4),len(op),0,0,target)
        else:
            blob.extend(ins.bytes)
            if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in ins.operands):
                need(struct.unpack_from('<i',ins.bytes,ins.disp_offset)[0]==ins.disp,'Invalid RIP operand')
                fixes.append((start+ins.disp_offset,len(blob),0,0,a+ins.size+ins.disp))
        if a<START+UNWIND[1]:need(blob[start:]==ins.bytes and start-body==a-START,'Setup prologue moved')
    need(seen==set(expected) and layout_fix is not None,'Missing setup replacement')
    for offset,nxt,target in branches:
        need(target in mapping,'Invalid branch boundary');fixes.append((offset,nxt,1,0,mapping[target]))
    body_end=len(blob);blob.extend(b'\xcc'*(-len(blob)%16));handler=len(blob)
    fix(b'\xe9'+bytes(4),1,0,0,GS_HANDLER);code_bytes=len(blob)
    blob.extend(bytes(-len(blob)%8));placements=len(blob);blob.extend(bytes(8*24))
    f=fixes[layout_fix];fixes[layout_fix]=f[:-1]+(placements,)
    unwind_offset=len(blob);functions=[]
    for begin,end,uw in ((0,body,b'\x01\0\0\0'),(body,body_end,UNWIND+struct.pack('<II',handler,COOKIE)),(handler,code_bytes,b'\x01\0\0\0')):
        functions.append((begin,end,len(blob)));blob.extend(uw)
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE,'Setup image exceeds storage')
    return dict(blob=bytes(blob),fixes=fixes,mapping=mapping,source=source,functions=functions,
                code_bytes=code_bytes,unwind_offset=unwind_offset,table_offset=table_offset,
                handler_offset=handler,placements_offset=placements)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_loadout_setup.py.',
           'static const uint8_t ep_loadout_setup_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutSetupFixup ep_loadout_setup_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset','handler_offset','placements_offset'):
        lines.append(f'static const uint32_t ep_loadout_setup_{key} = {a[key]};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
