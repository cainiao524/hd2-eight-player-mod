"""Generate/verify the fixed C++ getter template; only explicit --write mutates."""
import argparse,json,struct
import native_getter_image as native
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

REFERENCE=dict(game_base=0x180000000,code_address=0x190000000,roster_address=0x200000000,storage_address=0x210000000,reject_address=0x190010000)
HEADER=native.PROJECT/'mod/src/ep_getter_template.h'


def render():
    artifact=native.build(**REFERENCE);code=bytes.fromhex(artifact['candidate']['code_hex']);blob=bytearray(artifact['image'])
    md=native.common.capstone.Cs(native.common.capstone.CS_ARCH_X86,native.common.capstone.CS_MODE_64);md.detail=True
    rows=list(md.disasm(code,REFERENCE['code_address']));native.require(sum(r.size for r in rows)==len(code),'Incomplete decode')
    fixups=[];base=REFERENCE['code_address'];boundaries={r.address for r in rows}
    def rel(ins,off,width,target):
        if base<=target<base+len(code):native.require(target in boundaries,'Branch into instruction');return
        param,add=(4,0) if target==REFERENCE['reject_address'] else (0,target-REFERENCE['game_base'])
        native.require(width==4 and (param==4 or add in (0x3326468,0x3483C20)),'Unknown relative reference')
        fixups.append((ins.address-base+off,ins.address-base+ins.size,param,width,add))
    for ins in rows:
        if ins.group(native.common.capstone.CS_GRP_JUMP):rel(ins,ins.imm_offset,ins.imm_size,ins.operands[0].imm)
        native.require(not ins.group(native.common.capstone.CS_GRP_CALL),'Unexpected call')
        for op in ins.operands:
            if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:rel(ins,ins.disp_offset,ins.disp_size,ins.address+ins.size+op.mem.disp)
        if ins.imm_size==8:
            value=struct.unpack_from('<Q',ins.bytes,ins.imm_offset)[0]
            if value==REFERENCE['roster_address']:param,add=2,0
            else:native.require(value==REFERENCE['storage_address']+0x1D8,'Unknown absolute reference');param,add=3,0x1D8
            fixups.append((ins.address-base+ins.imm_offset,0,param,8,add))
    native.require(len(fixups)==5,'Changed relocation coverage')
    for off,_,_,width,_ in fixups:blob[off:off+width]=bytes(width)
    lines=['/* Generated from the pinned getter; numeric bindings only.']
    for p in ('native-getter.lock.json','tools/native_getter_image.py','tools/native_unwind_source.py'):
        lines.append(' * '+p+' SHA256 '+native.sha((native.PROJECT/p).read_bytes()))
    lines+=[' */',f'#define EP_GETTER_IMAGE_BYTES {len(blob)}u',f'#define EP_GETTER_CODE_BYTES {len(code)}u',
            f'#define EP_GETTER_UNWIND_OFFSET {artifact["unwind_offset"]}u',f'#define EP_GETTER_TABLE_OFFSET {artifact["table_offset"]}u',
            'static const uint8_t ep_getter_template[] = {']
    for i in range(0,len(blob),16):lines.append('    '+','.join(f'0x{x:02x}' for x in blob[i:i+16])+',')
    lines+=['};','static const EpGetterFixup ep_getter_fixups[] = {']
    lines+=['    {'+','.join(str(v) for v in row)+'},' for row in fixups];lines+=['};']
    return ('\n'.join(lines)+'\n').encode(),dict(image_bytes=len(blob),code_bytes=len(code),unwind_offset=artifact['unwind_offset'],table_offset=artifact['table_offset'],fixups=fixups)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');a=p.parse_args();blob,facts=render()
    if a.write:HEADER.write_bytes(blob)
    else:native.require(HEADER.read_bytes()==blob,'Getter template differs; review and regenerate')
    print(json.dumps(dict(passed=True,**facts,header_sha256=native.sha(blob),game_access=False)))
