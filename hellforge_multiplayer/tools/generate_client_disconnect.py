"""Relocate saved disconnect_client for an external confirmed-peer bank.

Only bank lookup/clearing and bounded guards change. No game access, hashes,
receipts, discovery, calls or publication. Native disconnect services remain.
"""
import argparse
import struct
from generate_loadout_lifecycle import Capture,PROJECT,need
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

START,END=0x10845b0,0x1084c0f
HEADER=PROJECT/'mod/src/ep_client_disconnect_template.h'
GS=bytes.fromhex('191f04000d01310006c00470')


def build():
    c=Capture();source=c.read(START,END-START);ins=list(c.md.disasm(source,START))
    need(sum(i.size for i in ins)==len(source),'Incomplete disconnect body')
    # Leaf preflight: verify RCX before reading count, then count <= capacity.
    blob=bytearray(b'\x49\xbb'+bytes(8)+b'\x4c\x39\xd9\x0f\x85'+bytes(4))
    blob+=b'\x81\xb9\xc8\0\0\0'+bytes(4)+b'\x0f\x86'+bytes(4)
    reject=len(blob);blob+=b'\x49\xbb'+bytes(8)+b'\x41\xff\xe3'
    blob+=b'\x90'*(64-len(blob));body=len(blob);blob+=source
    # Fixup: offset, next, key (game/client/peers/capacity/reject), kind
    # (0 rel32, 1 u64, 2 u32), multiplier, addend.
    fixes=[(2,0,1,1,1,0),(25,0,3,2,1,0),(reject+2,0,4,1,1,0)]
    struct.pack_into('<i',blob,15,reject-19);struct.pack_into('<i',blob,31,body-35)
    starts={i.address for i in ins}
    clear_start,clear_end=0x10849f7,0x1084a2f
    for i in ins:
        if i.address==0x10849d6 or clear_start<=i.address<clear_end:continue
        at=body+i.address-START
        if (i.mnemonic=='call' or i.mnemonic.startswith('j')) and i.operands[0].type==X86_OP_IMM:
            target=i.operands[0].imm
            if START<=target<END:
                need(target in starts and not clear_start<target<clear_end,'Unsupported internal edge')
            else:
                need(i.imm_size==4,'External short branch')
                fixes.append((at+i.imm_offset,at+i.size,0,0,1,target))
        if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
            need(i.disp_offset+4<=i.size,'Unexpected RIP displacement')
            fixes.append((at+i.disp_offset,at+i.size,0,0,1,i.address+i.size+i.disp))
    load=next(i for i in ins if i.address==0x10849d6)
    need(load.size==8 and load.mnemonic=='mov' and load.op_str=='rcx, qword ptr [rcx + rdi + 0xd0]','Changed peer lookup')
    stores=[i for i in ins if clear_start<=i.address<clear_end]
    need(len(stores)==8 and all(i.mnemonic=='movups' and i.op_str==f'xmmword ptr [rdi + {hex(0xd0+16*n)}], xmm0'
         for n,i in enumerate(stores)),'Changed peer clear')
    at=body+clear_start-START
    clear=bytearray(b'\x49\xbb'+bytes(8)+b'\xb9'+bytes(4))
    clear+=b'\x41\x0f\x11\x03\x49\x83\xc3\x10\xff\xc9\x75\xf4'
    fixes += [(at+2,0,2,1,1,0),(at+11,0,3,2,2,0)]
    blob[at:at+clear_end-clear_start]=clear+b'\x90'*(clear_end-clear_start-len(clear))
    blob+=b'\xcc'*(-len(blob)%16);lookup=len(blob)
    # A service may have changed count after the entry guard. Bound each lookup
    # too; a late rejection calls the nonreturning policy with an aligned frame.
    blob+=b'\x48\x81\xf9'+bytes(4)+b'\x0f\x83'+bytes(4)
    fixes.append((lookup+3,0,3,2,32,0))
    at=len(blob);blob+=b'\x49\xbb'+bytes(8)+b'\x49\x8b\x0c\x0b'
    fixes.append((at+2,0,2,1,1,0))
    blob+=b'\xe9'+struct.pack('<i',body+0x10849de-START-(len(blob)+5))
    late_reject=len(blob);struct.pack_into('<i',blob,lookup+9,late_reject-lookup-13)
    blob+=b'\x49\xbb'+bytes(8)+b'\x41\xff\xd3\x0f\x0b'
    fixes.append((late_reject+2,0,4,1,1,0));lookup_end=len(blob)
    at=body+load.address-START;blob[at:at+8]=b'\xe9'+struct.pack('<i',lookup-at-5)+b'\x90'*3
    blob+=b'\xcc'*(-len(blob)%16);handler=len(blob);blob+=b'\xe9'+bytes(4)
    fixes.append((handler+1,handler+5,0,0,1,0x21044a0));code_bytes=len(blob)
    blob+=bytes(-len(blob)%4);rows=[(0,body,len(blob))];blob+=bytes((1,0,0,0))
    fs=[f for f in c.functions if START<=f[0]<END];need(len(fs)==8 and fs[-1][1]==END,'Changed disconnect fragments')
    original={};parents=[]
    for b,e,u in fs:
        h=c.read(u,4);n=4+((h[2]+1)&~1)*2;uw=c.read(u,n)
        row=(body+b-START,body+e-START,len(blob));original[(b,e,u)]=row;rows.append(row);blob+=uw
        if h[0]==25:
            need(b==START and uw==GS and c.read(u+n,8)==struct.pack('<II',0x21044a0,0x150),'Changed disconnect GS')
            blob+=struct.pack('<II',handler,0x150);parents.append(None)
        else:
            need(h[0]==33,'Unknown unwind profile');parent=struct.unpack('<III',c.read(u+n,12))
            need(parent in original,'External/forward chain');parents.append(fs.index(parent));blob+=struct.pack('<III',*original[parent])
    need(parents==[None,0,1,2,2,1,0,0],'Changed register lifetimes')
    rows.append((lookup,lookup_end,len(blob)));blob+=bytes((33,0,0,0))+struct.pack('<III',*rows[6])
    rows.append((handler,handler+5,len(blob)));blob+=bytes((1,0,0,0))
    table=len(blob)
    for row in rows:blob+=struct.pack('<III',*row)
    need(len(blob)<=4096,'Disconnect image too large')
    return dict(blob=bytes(blob),fixes=fixes,body=body,lookup=lookup,late_reject=late_reject,
                handler=handler,code_bytes=code_bytes,table=table,rows=rows)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_client_disconnect.py.',
           'static const uint8_t ep_client_disconnect_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpClientDisconnectFixup ep_client_disconnect_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for k in ('body','lookup','handler','code_bytes','table'):
        lines.append(f'static const uint32_t ep_client_disconnect_{k} = {a[k]};')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print('Disconnect candidate bytes:',len(a['blob']))
