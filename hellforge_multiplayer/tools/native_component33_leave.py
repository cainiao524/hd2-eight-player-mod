"""Relocate saved B51DE0, routing its component33 arm through owned DEFER.

Only saved source bodies are read. The two image-base LEAs intentionally
keep their original displacement: at the new address they compute code-ROOT,
so the copied RVA and byte-index switch tables still address the local body.
"""
import argparse,json,struct
import native_component33_image as n
LOCK=n.PROJECT/'native-component33-outer.lock.json'
HEADER=n.PROJECT/'mod/src/ep_component33_leave_template.h'
ROOT=0xb51de0;START=0xb51fe6;END=0xb5204b;TAIL=0xb5247d


def build():
    f=json.loads(LOCK.read_bytes())['callers']['release'];source=bytes.fromhex(f['body_hex']);raw=bytearray(source)
    n.need(f['start']==ROOT and f['code_end']==0xb524b8 and f['end']==0xb525ea and len(raw)==f['end']-ROOT,'leave source extent')
    rows=n.decode(source[:f['code_end']-ROOT],ROOT);instructions={i.address:i for i in rows}
    n.need(all(x in instructions for x in (START,END,TAIL)),'leave route boundaries')
    n.need(instructions[0xb51fe0].operands[0].imm==0xb52484 and instructions[0xb52041].operands[0].imm==0x6659e0,'leave empty gate/release')
    targets=[x[0] for x in struct.iter_unpack('<I',source[0xb524b8-ROOT:0xb524ec-ROOT])]
    n.need(len(targets)==13 and targets[5]==0xb51fd0 and all(x in instructions and not START<=x<END for x in targets),'leave switch destinations')
    n.need(len(source[0xb524ec-ROOT:])==254 and max(source[0xb524ec-ROOT:])<len(targets),'leave switch index table')
    fixups=[];bases=[]
    for i in rows:
        if START<=i.address<END:continue
        if i.group(n.capstone.CS_GRP_JUMP) and i.operands[0].type==n.X86_OP_IMM:
            n.need(ROOT<=i.operands[0].imm<f['code_end'] and not START<=i.operands[0].imm<END,'leave external branch/removed target')
        for o in i.operands:
            if o.type==n.X86_OP_MEM and o.mem.base==n.X86_REG_RIP:
                target=i.address+i.size+o.mem.disp
                if target==0:
                    n.need(i.mnemonic=='lea' and i.op_str.startswith('rdx,'),'leave switch base ABI');bases.append(i.address)
                else:fixups.append((i.address-ROOT+i.disp_offset,i.address+i.size-ROOT,0,target))
        if i.group(n.capstone.CS_GRP_CALL) and i.operands[0].type==n.X86_OP_IMM:
            n.need(not ROOT<=i.operands[0].imm<f['end'],'unexpected leave internal call')
            fixups.append((i.address-ROOT+i.imm_offset,i.address+i.size-ROOT,0,i.operands[0].imm))
    n.need(bases==[0xb51e15,TAIL],'leave switch base sites')
    at=START-ROOT;raw[at:END-ROOT]=b'\x90'*(END-START)
    # RCX=R14 (component), RDX=RDI (object); DEFER resolves the selected
    # ordinal under the same owner and retains the original deferred flag=1.
    raw[at:at+16]=bytes.fromhex('4c89f14889fae800000000e9')+struct.pack('<i',TAIL-START-16)
    fixups.append((at+7,at+11,1,0))
    for off,nxt,key,add in fixups:raw[off:off+4]=bytes(4)
    code_bytes=len(raw)
    while len(raw)%4:raw.append(0)
    unwind_offset=len(raw);offsets=[];unwinds={}
    for row in f['fragments']:
        n.need(not START<row['start']<END and not START<row['end']<END,'leave fragment boundary')
        offsets.append(len(raw));unwinds[row['unwind_rva']]=len(raw);raw.extend(bytes.fromhex(row['unwind_hex']))
    for row,off in zip(f['fragments'],offsets):
        if raw[off]>>3&4:
            at=off+4+((raw[off+2]+1)&~1)*2;start,end,uw=struct.unpack_from('<III',raw,at)
            struct.pack_into('<III',raw,at,start-ROOT,end-ROOT,unwinds[uw])
    table=len(raw)
    for row,off in zip(f['fragments'],offsets):raw.extend(struct.pack('<III',row['start']-ROOT,row['end']-ROOT,off))
    return dict(image=bytes(raw),code_bytes=code_bytes,unwind_offset=unwind_offset,table_offset=table,function_count=len(offsets),fixups=fixups)


def render():
    r=build();raw=r['image'];lines=['/* Saved B51DE0 dispatch and tables; component33 routes to DEFER. */','static const uint8_t ep_c33_leave_image[]={']
    lines+=['    '+','.join(f'0x{x:02x}' for x in raw[i:i+16])+',' for i in range(0,len(raw),16)];lines+=['};','static const EpC33OuterFixup ep_c33_leave_fixups[]={']
    lines+=['    {'+','.join(map(str,(off,nxt,key,4,add)))+'},' for off,nxt,key,add in r['fixups']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset','function_count'):lines.append('static const uint32_t ep_c33_leave_'+key+'='+str(r[key])+';')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--write',action='store_true');args=ap.parse_args()
    if args.write:HEADER.write_text(render(),encoding='utf-8')
    else:print(render(),end='')
