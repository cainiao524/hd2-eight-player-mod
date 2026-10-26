"""Explicit generation of registry C++ relocation templates from saved evidence."""
import argparse,json,struct
import native_registry_image as native
from capstone import Cs,CS_ARCH_X86,CS_MODE_64,CS_GRP_JUMP,CS_GRP_CALL
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP
REFERENCE=dict(game_base=0x180000000,code_address=0x190000000,helper_code_address=0x190100000,
    roster_address=0x200000000,storage_address=0x210000000,reject_address=0x190010000,helper_reject_address=0x190110000)
HEADER=native.PROJECT/'mod/src/ep_registry_templates.h'

def render():
    artifacts=native.build(**REFERENCE)['artifacts'];lines=['/* Generated from pinned registry sources; no game access.']
    for path in ('native-registry.lock.json','tools/native_registry_image.py','tools/generate_registry_templates.py'):
        lines.append(' * '+path+' SHA256 '+native.sha((native.PROJECT/path).read_bytes()))
    lines+=[' */'];infos=[];facts={}
    for kind in native.KINDS:
        art=artifacts[kind];candidate=art['candidate'];base=candidate['code_address'];code=bytes.fromhex(candidate['code_hex']);blob=bytearray(art['image'])
        md=Cs(CS_ARCH_X86,CS_MODE_64);md.detail=True;rows=list(md.disasm(code,base));boundaries={i.address for i in rows};fixups=[]
        native.require(sum(i.size for i in rows)==len(code),'Registry decode incomplete')
        reject=REFERENCE['reject_address' if kind=='update' else 'helper_reject_address']
        def relative(i,off,width,target):
            if base<=target<base+len(code):native.require(target in boundaries,'Registry branch into instruction');return
            if target==reject:param,add=5,0
            elif kind=='update' and target==REFERENCE['helper_code_address']:param,add=4,0
            else:param,add=0,target-REFERENCE['game_base'];native.require(0<=add<native.legacy().IMAGE_SIZE,'Unknown registry relative')
            native.require(width==4,'Registry relative width changed');fixups.append((i.address-base+off,i.address-base+i.size,param,width,add))
        for i in rows:
            if (i.group(CS_GRP_JUMP) or i.group(CS_GRP_CALL)) and i.operands[0].type==X86_OP_IMM:
                relative(i,i.imm_offset,i.imm_size,i.operands[0].imm)
            for op in i.operands:
                if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:relative(i,i.disp_offset,i.disp_size,i.address+i.size+op.mem.disp)
            if i.imm_size==8:
                value=struct.unpack_from('<Q',i.bytes,i.imm_offset)[0]
                if value==REFERENCE['roster_address']:param,add=2,0
                elif -0xE8<=value-REFERENCE['storage_address']<0x680:param,add=3,value-REFERENCE['storage_address']
                else:param,add=0,value-REFERENCE['game_base'];native.require(add==0x3326468,'Unknown registry absolute')
                fixups.append((i.address-base+i.imm_offset,0,param,8,add))
        for off,_,_,width,_ in fixups:blob[off:off+width]=bytes(width)
        label='ep_registry_'+kind;lines+=['static const uint8_t '+label+'[] = {']
        for off in range(0,len(blob),16):lines.append('    '+','.join(f'0x{x:02x}' for x in blob[off:off+16])+',')
        lines+=['};','static const EpRegistryFixup '+label+'_fixups[] = {']
        lines+=['    {'+','.join(map(str,row))+'},' for row in fixups];lines+=['};']
        info=(len(blob),len(code),art['unwind_offset'],art['table_offset'],art['function_count'],len(fixups))
        infos.append('    {'+','.join(map(str,info))+','+label+','+label+'_fixups},')
        facts[kind]=dict(zip(('bytes','code_bytes','unwind_offset','table_offset','function_count','fixups'),info))
    lines+=['static const EpRegistryTemplate ep_registry_templates[] = {',*infos,'};']
    return ('\n'.join(lines)+'\n').encode(),facts

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();blob,facts=render()
    if args.write:HEADER.write_bytes(blob)
    else:native.require(HEADER.read_bytes()==blob,'Registry template changed; explicit regeneration required')
    print(json.dumps(dict(passed=True,variants=facts,header_sha256=native.sha(blob),game_access=False)))
