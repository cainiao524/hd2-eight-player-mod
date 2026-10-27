"""Relocate the saved client update; no game discovery, reads or calls.

The two native pointer-returning lookups stay native calls, so publication must
wrap this entire caller in the same owner scope. The inline third lookup uses
the shared bank. The separate host's four-byte flag map is NOT expanded: a
larger local network index rejects before storing it into host state.
"""
import argparse
import struct
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP
from generate_loadout_lifecycle import Capture, PROJECT, need

START, END = 0x1083150, 0x1084341
GS = bytes.fromhex('1926090018341d00180114000cf00ae00870076006500000')
HEADER = PROJECT/'mod/src/ep_client_update_template.h'


def build():
    c = Capture(); source = c.read(START, END-START)
    ins = list(c.md.disasm(source, START))
    need(sum(i.size for i in ins) == len(source), 'Incomplete update source')
    blob = bytearray(b'\x49\xbb'+bytes(8)+b'\x4c\x39\xd9\x0f\x85'+bytes(4))
    blob += b'\x81\xb9\xc8\0\0\0'+bytes(4)+b'\x0f\x86'+bytes(4)
    reject = len(blob); blob += b'\x49\xbb'+bytes(8)+b'\x41\xff\xe3'
    blob += b'\x90'*(64-len(blob)); body = len(blob)
    fixes = [(2,0,1,1,1,0),(25,0,3,2,1,0),(reject+2,0,4,1,1,0)]
    struct.pack_into('<i',blob,15,reject-19); struct.pack_into('<i',blob,31,body-35)
    mapping = {}; edges = []; literal_refs = []

    def fail_unless(jcc):
        # Full original frame is established at all late checks. The policy
        # must not return; UD2 prevents continuation if it violates the contract.
        blob.extend(bytes((jcc,15)))
        at = len(blob); blob.extend(b'\x49\xbb'+bytes(8)+b'\x41\xff\xd3\x0f\x0b')
        fixes.append((at+2,0,4,1,1,0))

    for i in ins:
        mapping[i.address] = len(blob)
        if i.address == 0x1083c3a:
            need(i.op_str == 'r9d, dword ptr [r8 + 0x16390]', 'Changed inline count')
            at = len(blob); blob += b'\x49\xb9'+bytes(8)+b'\x4d\x39\xc8'
            fixes.append((at+2,0,1,1,1,-0x162c8)); fail_unless(0x74)
            blob += i.bytes
            at = len(blob); blob += b'\x41\x81\xf9'+bytes(4)
            fixes.append((at+3,0,3,2,1,0)); fail_unless(0x76)
            continue
        if i.address == 0x1083c58:
            need(i.op_str == 'qword ptr [rax + r8 + 0x16398], r10', 'Changed inline peer')
            # R8 owner, R9 count, R10 peer, R11 zero, RCX/RDX ordinals are live.
            # Add a RIP-relative bank literal into the otherwise dead RAX offset.
            at = len(blob); blob += b'\x48\x03\x05'+bytes(4)+b'\x4c\x39\x10'
            literal_refs.append((at+3,at+7)); continue
        if i.address == 0x1083d34:
            need(i.op_str == 'ecx, dword ptr [rdx + r8 + 0x163ac]', 'Changed inline index')
            at = len(blob); blob += b'\x48\xb9'+bytes(8)+b'\x8b\x4c\x11\x14'
            fixes.append((at+2,0,2,1,1,0)); continue
        if i.address == 0x1083c7b:
            need(i.op_str == 'dword ptr [rbx + 0x34], eax', 'Changed host local-index store')
            blob += b'\x83\xf8\x04'; fail_unless(0x72)
        at = len(blob)
        if (i.mnemonic == 'call' or i.mnemonic.startswith('j')) and i.operands[0].type == X86_OP_IMM:
            target = i.operands[0].imm
            if i.mnemonic in ('call','jmp'):
                blob += (b'\xe8' if i.mnemonic == 'call' else b'\xe9')+bytes(4); off = at+1
            else:
                condition = i.bytes[0]-0x70 if i.bytes[0] in range(0x70,0x80) else i.bytes[1]-0x80
                need(0 <= condition < 16, 'Unsupported conditional edge')
                blob += bytes((0x0f,0x80+condition))+bytes(4); off = at+2
            if START <= target < END: edges.append((off,len(blob),target))
            else: fixes.append((off,len(blob),0,0,1,target))
        else:
            blob += i.bytes
            if any(o.type == X86_OP_MEM and o.mem.base == X86_REG_RIP for o in i.operands):
                fixes.append((at+i.disp_offset,at+i.size,0,0,1,i.address+i.size+i.disp))
    mapping[END] = len(blob)
    for off,nxt,target in edges:
        need(target in mapping, 'Branch into instruction'); struct.pack_into('<i',blob,off,mapping[target]-nxt)
    blob += b'\xcc'*(-len(blob)%16); handler = len(blob); blob += b'\xe9'+bytes(4)
    fixes.append((handler+1,handler+5,0,0,1,0x21044a0))
    blob += bytes(-len(blob)%8); literal = len(blob); blob += bytes(8)
    fixes.append((literal,0,2,1,1,0))
    for off,nxt in literal_refs: struct.pack_into('<i',blob,off,literal-nxt)
    rows = [(0,body,len(blob))]; blob += bytes((1,0,0,0))
    fs = [f for f in c.functions if START <= f[0] < END]
    need(len(fs) == 3 and fs[-1][1] == END, 'Changed update fragments')
    original = {}
    for b,e,u in fs:
        h = c.read(u,4); n = 4+((h[2]+1)&~1)*2; uw = c.read(u,n)
        row = (mapping[b],mapping[e],len(blob)); original[(b,e,u)] = row; rows.append(row); blob += uw
        if b == START:
            need(uw == GS and c.read(u+n,8) == struct.pack('<II',0x21044a0,0x98), 'Changed update GS')
            blob += struct.pack('<II',handler,0x98)
        else:
            need(h[0] == 33 and struct.unpack('<III',c.read(u+n,12)) == fs[0], 'Changed update chain')
            blob += struct.pack('<III',*original[fs[0]])
    rows.append((handler,handler+5,len(blob))); blob += bytes((1,0,0,0))
    table = len(blob)
    for row in rows: blob += struct.pack('<III',*row)
    need(len(blob) <= 8192, 'Update image too large')
    return dict(blob=bytes(blob),fixes=fixes,body=body,handler=handler,table=table,rows=rows,mapping=mapping)


def render(a):
    lines = ['// Generated from saved build 25480438 by generate_client_update.py.',
             'static const uint8_t ep_client_update_template[] = {']
    lines += ['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines += ['};','static const EpClientUpdateFixup ep_client_update_fixups[] = {']
    lines += ['    {'+','.join(map(str,f))+'},' for f in a['fixes']]; lines += ['};']
    for k in ('body','handler','table'): lines.append(f'static const uint32_t ep_client_update_{k} = {a[k]};')
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--write',action='store_true'); args = p.parse_args(); a = build()
    if args.write: HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print('Client update candidate bytes:',len(a['blob']))
