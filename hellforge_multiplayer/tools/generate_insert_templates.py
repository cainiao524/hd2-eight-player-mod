"""Generate/verify four C++ insertion templates, requiring explicit --write."""
import argparse,json,struct
import native_insert_image as native
from capstone.x86_const import X86_OP_MEM,X86_REG_RIP
REFERENCE=dict(game_base=0x180000000,code_address=0x190000000,roster_address=0x200000000,
               storage_address=0x210000000,move_code_address=0x190040000,reject_address=0x190010000)
HEADER=native.PROJECT/'mod/src/ep_insert_templates.h'

def render():
    lines=['/* Generated from pinned insertion sources; explicit numeric bindings only.']
    for path in ('native-insert.lock.json','tools/native_insert_image.py','tools/native_unwind_source.py','tools/native_mover_image.py'):
        lines.append(' * '+path+' SHA256 '+native.sha((native.PROJECT/path).read_bytes()))
    lines+=[' */',f'#define EP_INSERT_MOVER_BYTES {native.MOVER_BYTES}u'];facts={};infos=[]
    for kind in native.KINDS:
        artifact=native.build(kind=kind,**REFERENCE);candidate=artifact['candidate'];code=bytes.fromhex(candidate['code_hex']);blob=bytearray(artifact['image'])
        md=native.common.capstone.Cs(native.common.capstone.CS_ARCH_X86,native.common.capstone.CS_MODE_64);md.detail=True
        rows=list(md.disasm(code,REFERENCE['code_address']));native.require(sum(i.size for i in rows)==len(code),'Incomplete insert decode')
        base=REFERENCE['code_address'];boundaries={i.address for i in rows};fixups=[]
        def relative(i,off,width,target):
            if base<=target<base+len(code):native.require(target in boundaries,'Invalid internal branch');return
            if target==REFERENCE['reject_address']:param,add=5,0
            elif target==REFERENCE['move_code_address']:param,add=4,0
            else:param,add=0,target-REFERENCE['game_base'];native.require(add in (0x3326468,0x172F790),'Unknown external reference')
            native.require(width==4,'Unsupported relative width');fixups.append((i.address-base+off,i.address-base+i.size,param,width,add))
        for i in rows:
            if i.group(native.common.capstone.CS_GRP_JUMP) or i.group(native.common.capstone.CS_GRP_CALL):relative(i,i.imm_offset,i.imm_size,i.operands[0].imm)
            for op in i.operands:
                if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:relative(i,i.disp_offset,i.disp_size,i.address+i.size+op.mem.disp)
            if i.imm_size==8:
                value=struct.unpack_from('<Q',i.bytes,i.imm_offset)[0]
                if value==REFERENCE['roster_address']:param,add=2,0
                elif value==REFERENCE['storage_address']-0xE8:param,add=3,-0xE8
                else:native.require(value==REFERENCE['game_base']+0x3326468,'Unknown absolute reference');param,add=0,0x3326468
                fixups.append((i.address-base+i.imm_offset,0,param,8,add))
        native.require(len(fixups)==(23 if kind.startswith('dense') else 22),'Changed insertion relocation coverage')
        for off,_,_,width,_ in fixups:blob[off:off+width]=bytes(width)
        label='ep_insert_'+kind
        lines.append('static const uint8_t '+label+'[] = {')
        for off in range(0,len(blob),16):lines.append('    '+','.join(f'0x{x:02x}' for x in blob[off:off+16])+',')
        lines+=['};','static const EpInsertFixup '+label+'_fixups[] = {']
        lines+=['    {'+','.join(str(v) for v in row)+'},' for row in fixups];lines+=['};']
        fn=native.profile()['functions'][kind]
        infos.append('    {'+','.join(map(str,(len(blob),len(code),artifact['unwind_offset'],artifact['table_offset'],int(fn['entry'],16),int(fn['end_exclusive'],16)-int(fn['entry'],16),len(fixups))))+','+label+','+label+'_fixups},')
        facts[kind]=dict(image_bytes=len(blob),code_bytes=len(code),unwind_offset=artifact['unwind_offset'],table_offset=artifact['table_offset'],fixups=len(fixups))
    lines+=['static const EpInsertTemplate ep_insert_templates[] = {',*infos,'};']
    return ('\n'.join(lines)+'\n').encode(),dict(variants=facts,mover_image_bytes=native.MOVER_BYTES)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();blob,facts=render()
    if args.write:HEADER.write_bytes(blob)
    else:native.require(HEADER.read_bytes()==blob,'Insertion template mismatch; review before regenerating')
    print(json.dumps(dict(passed=True,**facts,header_sha256=native.sha(blob),game_access=False)))
