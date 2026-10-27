"""Relocate the saved local-player join body; no game access or receipts.

Keep every instruction's original length and every internal edge. Only the
unsigned network-index ceiling and external rel32/RIP operands change.
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
    # No prefix is inserted into the native body; original prologue offsets,
    # delayed saves and short branch displacements remain exact.
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
    rows.append((handler,handler+5,len(blob)));blob.extend(bytes((1,0,0,0)))
    table=len(blob)
    for row in rows:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=4096,'Join image too large')
    return dict(blob=bytes(blob),fixes=fixes,capacity=capacity,handler=handler,table=table,rows=rows,code_bytes=code_bytes)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_player_join.py.',
           'static const uint8_t ep_player_join_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpPlayerJoinFixup ep_player_join_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for k in ('capacity','handler','table','code_bytes'):
        lines.append(f'static const uint32_t ep_player_join_{k} = {a[k]};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),handler=a['handler'],game_access=False)))
