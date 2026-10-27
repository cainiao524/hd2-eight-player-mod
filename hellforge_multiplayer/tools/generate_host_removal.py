"""Relocate a host removal family from saved code into one bound image.

Four unrolled large-record removals become a capacity loop over the original
first removal body. No game access, discovery, fingerprints or publication.
"""
import argparse
import struct
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP
from generate_loadout_lifecycle import Capture,PROJECT,need

SOURCES=((0x108b560,0x108b5fe),(0x108b6b0,0x108bbb4),(0x108d190,0x108d3b0))
HEADER=PROJECT/'mod/src/ep_host_removal_template.h'
EXPECTED_UW={
    0x108b560:'01140800147404000f6403000a54020005340100',
    0x108b6b0:'011709001764400017543f0017343e0017013c0010700000',
    0x108d190:'010e06000e3415000ed20af008e00660',
    0x108d1dc:'211704001774140008541300',
    0x108d374:'2100020000741400',
    0x108d39e:'21000000',
}


def build():
    c=Capture();blob=bytearray();fixes=[];mapping={};entries={};edges=[];literal_refs=[];metadata=[]
    def absolute(op,key,add=0,multiplier=1):
        at=len(blob);blob.extend(bytes.fromhex(op)+bytes(8));fixes.append((at+2,0,key,1,multiplier,add))
    def number(op,key):
        prefix=bytes.fromhex(op);at=len(blob);blob.extend(prefix+bytes(4));fixes.append((at+len(prefix),0,key,2,1,0))
    def check(jcc,mode='frame'):
        # The large lookup saves registers in caller home space, with no stack
        # allocation. Restore them and tail-reject; never CALL on that frame.
        restore=bytes.fromhex('488b5c2408488b6c2410488b742418488b7c2420') if mode=='home' else b''
        blob.extend(bytes((jcc,len(restore)+(15 if mode=='frame' else 13))))
        blob.extend(restore);absolute('49bb',9)
        blob.extend(b'\x41\xff\xd3\x0f\x0b' if mode=='frame' else b'\x41\xff\xe3')
    def edge(op,target):
        at=len(blob);blob.extend(bytes.fromhex(op)+bytes(4));edges.append((at+len(bytes.fromhex(op)),len(blob),target,False))
    for start,end in SOURCES:
        blob+=b'\xcc'*(-len(blob)%16);entry=len(blob);entries[start]=entry
        absolute('49bb',1);blob+=b'\x4c\x39\xd9';check(0x74,'leaf')
        absolute('49bb',2);blob+=b'\x4c\x39\x19';check(0x74,'leaf')
        number('4181bb90630100',8);check(0x76,'leaf')
        need(len(blob)-entry<=96,'Host preflight');blob+=b'\x90'*(96-(len(blob)-entry));body=len(blob)
        metadata.append((entry,body,None))
        source=c.read(start,end-start);ins=list(c.md.disasm(source,start));need(sum(i.size for i in ins)==len(source),'Incomplete removal body')
        for i in ins:
            if 0x108b7f1<i.address<0x108bb51:continue
            mapping[i.address]=len(blob)
            if i.address==0x108b577:
                need(i.op_str=='rsi, [rcx + 0x110]','Changed large lookup cursor');absolute('48be',6,8);continue
            if i.address==0x108b595:
                blob+=i.bytes;blob+=b'\x83\xfb\x05';check(0x76,'home');continue
            if i.address==0x108b5a9:
                need(i.op_str=='qword ptr [r11 + rax*8 + 0x118], rbp','Changed large member read')
                blob+=b'\x48\xc1\xe0\x03';at=len(blob);blob+=b'\x48\x03\x05'+bytes(4)+b'\x48\x39\x28'
                literal_refs.append((at+3,at+7));continue
            if i.address==0x108b5b6:
                need(i.op_str=='r9, [r11 + 0x108]','Changed large result base');absolute('49b9',6);continue
            if i.address==0x108b5e0:
                need(i.op_str=='r10d, 4','Changed large scan count');number('4181fa',8);continue
            if i.address==0x108b6c7:
                need(i.op_str=='rbx, [rcx + 0x108]','Changed removal base');absolute('48bb',6);continue
            if i.address in (0x108b6ce,0x108b6d1):continue
            if i.address==0x108b6d7:
                need(i.op_str=='rbp, rcx','Changed cursor register');blob+=b'\x48\x89\xdd';continue
            if i.address==0x108b6da:
                # Move initial count acquisition after RDI captures the peer.
                # Back-edges reuse this point without overwriting RDI from RDX.
                blob+=bytes.fromhex('4531c08b430883f805');check(0x76)
            if i.address==0x108b704:
                blob+=i.bytes;blob+=b'\x83\xf9\x0c';check(0x76);continue
            if i.address==0x108b7f1:
                need(i.op_str=='rbx, [rbp + 0x2c8]','Changed unrolled boundary')
                blob+=bytes.fromhex('4881c5c0010000');absolute('49bb',6)
                # End = large + capacity*1C0h, using only volatile scratch.
                number('41ba',8);blob+=bytes.fromhex('4d69d2c00100004d01d34c39dd')
                edge('0f83',0x108bb51);blob+=bytes.fromhex('4889eb');edge('e9',0x108b6da);continue
            if i.address==0x108bb53:
                need(i.op_str=='rcx, [rbp + 0x20]','Changed peer scan base');absolute('48b9',4);continue
            if i.address==0x108bb62:
                need(i.op_str=='eax, 4','Changed peer count');number('3d',8);continue
            if i.address==0x108bb6d:
                need(i.op_str=='rax, [rbp + 0x20]','Changed peer result base');absolute('48b8',4);continue
            if i.address==0x108bb79:
                # -1 retains the native no-flag case. All other indices must
                # fit before even the matched host record is changed.
                blob+=b'\x83\xf9\xff\x74\x17';number('81f9',8);check(0x72)
            if i.address==0x108bb93:
                need(i.op_str=='byte ptr [rcx + rbp + 0x100], 0','Changed flag clear');absolute('49bb',5);blob+=bytes.fromhex('41c6040b00');continue
            if i.address==0x108d2d4:
                need(i.op_str=='edi, 4','Changed dispatch count');number('bf',8);continue
            if i.address==0x108d2d9:
                need(i.op_str=='rbx, [rsi + 0x20]','Changed dispatch bank');absolute('48bb',4);continue
            if i.address==0x108d340:
                need(i.op_str=='dword ptr [rsp + 0x5c], edi','Changed reason byte size')
                blob+=bytes.fromhex('c744245c04000000');continue
            if i.address==0x108d370:
                need(i.op_str=='rbx, [rsi + 0x40]','Changed second dispatch bank');absolute('48bb',4,0x20);continue
            at=len(blob)
            if (i.mnemonic=='call' or i.mnemonic.startswith('j')) and i.operands[0].type==X86_OP_IMM:
                target=i.operands[0].imm
                if i.mnemonic in ('call','jmp'):
                    blob+=(b'\xe8' if i.mnemonic=='call' else b'\xe9')+bytes(4);off=at+1
                else:
                    condition=i.bytes[0]-0x70 if i.bytes[0] in range(0x70,0x80) else i.bytes[1]-0x80
                    need(0<=condition<16,'Unsupported removal branch');blob+=bytes((0x0f,0x80+condition))+bytes(4);off=at+2
                edges.append((off,len(blob),target,i.mnemonic=='call'))
            else:
                blob+=i.bytes
                if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
                    fixes.append((at+i.disp_offset,at+i.size,0,0,1,i.address+i.size+i.disp))
        mapping[end]=len(blob)
        fs=[f for f in c.functions if start<=f[0]<end]
        need(fs and fs[-1][1]==end,'Removal unwind extent')
        for b,e,u in fs:metadata.append((mapping[b],mapping[e],(b,e,u)))
    for off,nxt,target,is_call in edges:
        if is_call and target in entries:struct.pack_into('<i',blob,off,entries[target]-nxt)
        elif target in mapping:struct.pack_into('<i',blob,off,mapping[target]-nxt)
        else:
            need(not any(b<=target<e for b,e in SOURCES),'Edge into removed unrolled block')
            fixes.append((off,nxt,0,0,1,target))
    blob+=bytes(-len(blob)%8);literal=len(blob);blob+=bytes(8);fixes.append((literal,0,6,1,1,16))
    for off,nxt in literal_refs:struct.pack_into('<i',blob,off,literal-nxt)
    rows=[];original={}
    for b,e,f in metadata:
        row=(b,e,len(blob));rows.append(row)
        if not f:blob+=bytes((1,0,0,0));continue
        sb,se,u=f;h=c.read(u,4);n=4+((h[2]+1)&~1)*2;uw=c.read(u,n)
        need(uw==bytes.fromhex(EXPECTED_UW[sb]),'Changed removal unwind');blob+=uw;original[f]=row
        if h[0]==33:
            parent=struct.unpack('<III',c.read(u+n,12));need(parent in original,'Unowned unwind parent')
            blob+=struct.pack('<III',*original[parent])
    table=len(blob)
    for row in rows:blob+=struct.pack('<III',*row)
    need(len(blob)<=4096 and len(rows)==9,'Removal image layout')
    return dict(blob=bytes(blob),fixes=fixes,mapping=mapping,entries=[entries[b] for b,e in SOURCES],rows=rows,table=table)


def render(a):
    lines=['// Generated from saved build 25480438 by generate_host_removal.py.','static const uint8_t ep_host_removal_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpHostRemovalFixup ep_host_removal_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    lines+=[f'static const uint32_t ep_host_removal_table = {a["table"]};',
            'static const uint32_t ep_host_removal_entries[3] = {'+','.join(map(str,a['entries']))+'};']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:HEADER.write_text(render(a),encoding='utf-8',newline='\n')
    print('Host removal candidate bytes:',len(a['blob']))
