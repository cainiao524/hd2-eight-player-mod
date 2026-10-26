"""Route saved B5E710 resource refresh through the admitted ACQUIRE entry.

Pure generation from the saved JSON instruction/unwind bodies. No game reads,
fingerprint workflow, receipt, or publication.
"""
import argparse,json,struct
import native_component33_image as n
LOCK=n.PROJECT/'native-component33-outer.lock.json'
HEADER=n.PROJECT/'mod/src/ep_component33_refresh_template.h'
ROOT=0xb5e710;START=0xb5e785;TAIL=0xb5ea4c


def build():
    f=json.loads(LOCK.read_bytes())['callers']['refresh'];source=bytes.fromhex(f['body_hex']);raw=bytearray(source)
    n.need(f['start']==ROOT and f['end']==0xb5ea87 and len(source)==f['end']-ROOT,'refresh source extent')
    rows=n.decode(source,ROOT);instructions={i.address:i for i in rows}
    n.need(START in instructions and TAIL in instructions,'refresh route boundary')
    n.need(instructions[0xb5e71e].mnemonic=='mov' and instructions[0xb5e77f].operands[0].imm==TAIL,'refresh registry/empty gate')
    # Every source edge into the removed block originates inside that block.
    # Preserve the entire parent frame and fragment offsets, including its
    # conditional saves and final restores. Only the routed call can execute.
    for i in rows:
        if not START<=i.address<TAIL and i.group(n.capstone.CS_GRP_JUMP) and i.operands[0].type==n.X86_OP_IMM:
            n.need(not START<=i.operands[0].imm<TAIL,'external edge into removed refresh body')
    at=START-ROOT;end=TAIL-ROOT;raw[at:end]=b'\x90'*(end-at)
    raw[at:at+16]=bytes.fromhex('4c89fa4889f1e800000000e9')+struct.pack('<i',end-at-16)
    # Registry RIP target and admitted acquisition call are the only remaining
    # external relocations. All other branch offsets stay exactly original.
    registry=instructions[0xb5e71e];registry_off=registry.address-ROOT+registry.disp_offset
    n.need(registry.address+registry.size+registry.disp==0x3326e68,'refresh registry address')
    raw[registry_off:registry_off+4]=bytes(4)
    code_bytes=len(raw)
    while len(raw)%4:raw.append(0)
    unwind_offset=len(raw);unwinds={};offsets=[]
    for row in f['fragments']:
        n.need(not START<row['start']<TAIL and not START<row['end']<TAIL,'refresh fragment crosses new call boundary')
        offsets.append(len(raw));unwinds[row['unwind_rva']]=len(raw);raw.extend(bytes.fromhex(row['unwind_hex']))
    for row,off in zip(f['fragments'],offsets):
        if raw[off]>>3&4:
            at=off+4+((raw[off+2]+1)&~1)*2;start,end,uw=struct.unpack_from('<III',raw,at)
            struct.pack_into('<III',raw,at,start-ROOT,end-ROOT,unwinds[uw])
    table=len(raw)
    for row,off in zip(f['fragments'],offsets):raw.extend(struct.pack('<III',row['start']-ROOT,row['end']-ROOT,off))
    return dict(image=bytes(raw),code_bytes=code_bytes,unwind_offset=unwind_offset,table_offset=table,function_count=len(offsets),
        fixups=[(registry_off,registry.address+registry.size-ROOT,0,0x3326e68),(START-ROOT+7,START-ROOT+11,1,0)])


def render():
    r=build();raw=r['image'];lines=['/* Saved B5E710 registry loop; inline resource effects route to ACQUIRE. */',
        'static const uint8_t ep_c33_refresh_image[]={']
    lines+=['    '+','.join(f'0x{x:02x}' for x in raw[i:i+16])+',' for i in range(0,len(raw),16)];lines+=['};']
    lines+=['static const EpC33OuterFixup ep_c33_refresh_fixups[]={']
    lines+=['    {'+','.join(map(str,(off,nxt,key,4,add)))+'},' for off,nxt,key,add in r['fixups']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset','function_count'):lines.append('static const uint32_t ep_c33_refresh_'+key+'='+str(r[key])+';')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--write',action='store_true');args=ap.parse_args()
    if args.write:HEADER.write_text(render(),encoding='utf-8')
    else:print(render(),end='')
