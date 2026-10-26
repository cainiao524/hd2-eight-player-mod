"""Generate fixed C++ templates from the reviewed component33 relocation."""
import argparse,json,struct
import native_component33_image as n
from capstone.x86_const import X86_OP_MEM,X86_REG_RIP
REFERENCE=dict(game_base=0x180000000,code_address=0x190000000,component_address=0x200000000,
               storage_address=0x210000000,move_code_address=0x190040000,reject_address=0x190010000)
HEADER=n.PROJECT/'mod/src/ep_component33_templates.h'
def render():
    lines=['/* Generated from saved component33 code. No live lookup.']
    for name in ('native-component33.lock.json','tools/native_component33_image.py'):
        lines.append(' * '+name+' SHA256 '+n.sha((n.PROJECT/name).read_bytes()))
    lines+=[' */'];infos=[];facts={}
    for kind in n.ALL_KINDS:
        a=n.build(kind,**REFERENCE);blob=bytearray(a['image']);fixes=[];base=REFERENCE['code_address']
        def relative(i,off,target):
            if base<=target<base+a['code_bytes']:return
            if target==REFERENCE['reject_address']:parameter,add=5,0
            elif target==REFERENCE['move_code_address']:parameter,add=4,0
            else:
                parameter,add=0,target-REFERENCE['game_base'];n.need(add in (0x33267B8,0x3483C34,0x172F790,0x172F8A0,0x173B6F0,0x173B8D0,0x173BC20,0x2088770,0x21044A0)+tuple(r[0] for r in n.EXTRA_GLOBAL_REGIONS),'unknown relative target')
            fixes.append((i.address-base+off,i.address-base+i.size,parameter,4,add))
        for i in n.decode(blob[:a['code_bytes']],base):
            if i.group(n.capstone.CS_GRP_JUMP) or i.group(n.capstone.CS_GRP_CALL):relative(i,i.imm_offset,i.operands[0].imm)
            for op in i.operands:
                if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:relative(i,i.disp_offset,i.address+i.size+op.mem.disp)
            if i.imm_size==8:
                value=struct.unpack_from('<Q',i.bytes,i.imm_offset)[0]
                options=[(0,0x33267B8),(0,0x3483C34),(0,0x347CDD8),(2,0),(2,0x14),(3,0),(3,-0x70),(3,-0x48),(3,-0x50),(3,0xF8)]
                matches=[(p,add) for p,add in options if value==list(REFERENCE.values())[p]+add]
                n.need(len(matches)==1,'unknown absolute target');parameter,add=matches[0]
                fixes.append((i.address-base+i.imm_offset,0,parameter,8,add))
        for off,_,_,width,_ in fixes:blob[off:off+width]=bytes(width)
        name='ep_component33_'+kind
        lines.append('static const uint8_t '+name+'[] = {')
        lines += ['    '+','.join(f'0x{x:02x}' for x in blob[i:i+16])+',' for i in range(0,len(blob),16)]
        lines += ['};','static const EpComponent33Fixup '+name+'_fixups[] = {']
        lines += ['    {'+','.join(map(str,row))+'},' for row in fixes];lines+=['};']
        infos.append('    {'+','.join(map(str,(len(blob),a['code_bytes'],a['unwind_offset'],a['table_offset'],a['function_count'],len(fixes))))+','+name+','+name+'_fixups},')
        facts[kind]={k:a[k] for k in ('code_bytes','body_offset','table_offset','function_count')}
        facts[kind].update(image_bytes=len(blob),fixups=len(fixes),array_patches=len(a['array_patches']))
    lines+=['static const EpComponent33Template ep_component33_templates[] = {',*infos,'};']
    sources=n.profile()['functions'].values()
    lines+=['static const uint32_t ep_component33_sources[][2] = {']
    lines+=['    {'+str(f['start'])+','+str(f['end']-f['start'])+'},' for f in sources];lines+=['};']
    lines+=['static const uint32_t ep_component33_extra_globals[][2] = {']
    lines+=['    {'+str(a)+','+str(size)+'},' for a,size in n.EXTRA_GLOBAL_REGIONS];lines+=['};']
    return ('\n'.join(lines)+'\n').encode(),facts
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args();blob,facts=render()
    if a.write:HEADER.write_bytes(blob)
    else:n.need(HEADER.read_bytes()==blob,'component33 template differs')
    print(json.dumps({'passed':True,'variants':facts,'header_sha256':n.sha(blob),'game_access':False}))
