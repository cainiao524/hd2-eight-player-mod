"""Relocate the saved local-player join body; no game access or receipts.

Keep the original frame and internal edges. A checked creation result takes
an appended success continuation or a register-restoring failure exit.
"""
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

START,END=0x1085d70,0x108691d
GS=bytes.fromhex('192b05001a01600505f0033002500000')
HEADER=PROJECT/'mod/src/ep_player_join_template.h'


def build():
    c=Capture();source=c.read(START,END-START);blob=bytearray(source);fixes=[]
    ins=list(c.md.disasm(source,START));need(sum(i.size for i in ins)==len(source),'Incomplete join body')
    starts={i.address for i in ins}
    for i in ins:
        at=i.address-START
        if i.address in (0x10868d7,0x10868dc,0x10868e3):continue
        if i.address==0x1086460:
            need(i.mnemonic=='cmp' and i.op_str=='dword ptr [rdx + r8 + 0x163ac], 4','Changed network-index gate')
            need(i.imm_size==1 and i.imm_offset==8,'Changed capacity operand')
            capacity=at+i.imm_offset
        if (i.mnemonic=='call' or i.mnemonic.startswith('j')) and i.operands[0].type==X86_OP_IMM:
            target=i.operands[0].imm
            if START<=target<END:need(target in starts,'Branch into instruction')
            else:
                need(i.imm_size==4,'External short branch')
                fixes.append((at+i.imm_offset,at+i.size,target))
        if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
            # Capstone reports operand width for 66-prefixed MOVDQA here;
            # validate the actual encoded RIP displacement instead.
            need(i.disp_offset+4<=i.size and struct.unpack_from('<i',i.bytes,i.disp_offset)[0]==i.disp,'Unexpected RIP displacement')
            fixes.append((at+i.disp_offset,at+i.size,i.address+i.size+i.disp))
    need(source[capacity]==4,'Missing capacity')
    need(c.read(0x1086469,6)==bytes.fromhex('0f83defdffff'),'Changed unsigned fallback')
    need(c.read(0x10868d7,5)==bytes.fromhex('e86458f5ff'),'Changed creation call')
    tail=[i for i in ins if 0x10868dc<=i.address<0x10868e8]
    need(len(tail)==2 and tail[0].mnemonic=='mov' and tail[1].mnemonic=='call' and
         tail[1].operands[0].imm==0x13822e0,'Changed success continuation')
    blob.extend(b'\xcc'*(-len(blob)%16));continuation=len(blob)
    blob.extend(b'\x85\xc0\x0f\x84'+bytes(4)) # test eax,eax; jz failure
    for i in tail:
        at=len(blob);blob.extend(i.bytes)
        if i.mnemonic=='call':fixes.append((at+1,len(blob),i.operands[0].imm))
        else:fixes.append((at+i.disp_offset,len(blob),i.address+i.size+i.disp))
    blob.extend(b'\xe9'+struct.pack('<i',0x10868e8-START-(len(blob)+5)))
    failure=len(blob);struct.pack_into('<i',blob,continuation+4,failure-continuation-8)
    # Only entered after FDC140's full saved-register state. Restore it before
    # jumping directly to the native cookie check/epilogue, bypassing both
    # 608B60 and 1086B70 as well as the other-peer notification loop.
    blob.extend(c.read(0x10868f6,0x22)) # XMM9..6
    blob.extend(c.read(0x10863b3,8)) # RSI
    blob.extend(c.read(0x1086417,0x20)) # R12,R14,R13,RDI
    blob.extend(b'\xe9'+struct.pack('<i',0x1086441-START-(len(blob)+5)))
    continuation_end=len(blob)
    blob.extend(b'\xcc'*(-len(blob)%16));thunk=len(blob)
    blob.extend(b'\x48\xb8'+bytes(8)+b'\xff\xe0');creation_pointer=thunk+2
    at=0x10868d7-START;blob[at:at+5]=b'\xe8'+struct.pack('<i',thunk-at-5)
    at=0x10868dc-START;blob[at:at+12]=b'\xe9'+struct.pack('<i',continuation-at-5)+b'\x90'*7
    blob.extend(b'\xcc'*(-len(blob)%16));handler=len(blob);blob.extend(b'\xe9'+bytes(4))
    fixes.append((handler+1,handler+5,0x21044a0));code_bytes=len(blob)
    blob.extend(bytes(-len(blob)%4));rows=[];original={};parents=[]
    functions=[f for f in c.functions if START<=f[0]<END]
    need(len(functions)==6 and functions[0][0]==START and functions[-1][1]==END,'Changed join fragments')
    for f in functions:
        b,e,u=f;h=c.read(u,4);n=4+((h[2]+1)&~1)*2;uw=c.read(u,n)
        row=(b-START,e-START,len(blob));original[f]=row;rows.append(row);blob.extend(uw)
        if h[0]==25:
            need(b==START and uw==GS and c.read(u+n,8)==struct.pack('<II',0x21044a0,0x2aa0),'Changed join GS contract')
            blob.extend(struct.pack('<II',handler,0x2aa0));parents.append(None)
        else:
            need(h[0]==33,'Unexpected join unwind')
            parent=struct.unpack('<III',c.read(u+n,12));need(parent in original,'Forward or external unwind chain')
            blob.extend(struct.pack('<III',*original[parent]));parents.append(functions.index(parent))
    need(parents==[None,0,1,1,0,0],'Changed join saved-register topology')
    rows.append((continuation,continuation_end,len(blob)))
    blob.extend(bytes((33,0,0,0))+struct.pack('<III',*rows[5]))
    rows.append((thunk,thunk+12,len(blob)));blob.extend(bytes((1,0,0,0)))
    rows.append((handler,handler+5,len(blob)));blob.extend(bytes((1,0,0,0)))
    table=len(blob)
    for row in rows:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=4096,'Join image too large')
    return dict(blob=bytes(blob),fixes=fixes,capacity=capacity,handler=handler,table=table,rows=rows,
                code_bytes=code_bytes,creation_pointer=creation_pointer,continuation=continuation,failure=failure)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_player_join.py.',
           'static const uint8_t ep_player_join_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpPlayerJoinFixup ep_player_join_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for k in ('capacity','handler','table','code_bytes','creation_pointer'):
        lines.append(f'static const uint32_t ep_player_join_{k} = {a[k]};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),handler=a['handler'],game_access=False)))
