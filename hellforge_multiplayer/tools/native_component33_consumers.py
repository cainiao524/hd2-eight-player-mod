"""Relocate four saved component33 consumers; never read or execute a target."""
import argparse,functools,json,struct
import native_component33_image as n
LOCK=n.PROJECT/'native-component33-consumers.lock.json'
LOCK_SHA='1b2fba2a5dc2267fa9a1585ab9bd27888c7a5a9c2441faa278e35ea85beb4a12'
HEADER=n.PROJECT/'mod/src/ep_component33_consumers_template.h'
KINDS=('update','acquire','defer','release')
REFERENCE=dict(game_base=0x180000000,code_address=0x190000000,component_address=0x210000000,
               storage_address=0x220000000,release_address=0x190010000,reject_address=0x190020000)

@functools.lru_cache()
def profile():
    n.need(n.sha(LOCK.read_bytes())==LOCK_SHA,'consumer lock changed')
    p=json.loads(LOCK.read_bytes());im=n.Image(n.ROOT/p['capture_directory']);n.profile()
    for f in p['functions'].values():
        raw=bytes.fromhex(f['body_hex'])
        n.need(len(raw)==f['end']-f['start'] and n.sha(raw)==f['sha256'] and im.read(f['start'],len(raw))==raw,'consumer source changed')
        for r in f['fragments']:
            raw=bytes.fromhex(r['unwind_hex'])
            n.need(im.containing(r['start'])==(r['start'],r['end'],r['unwind_rva']) and im.read(r['unwind_rva'],len(raw))==raw,'consumer unwind changed')
    return p

@functools.lru_cache()
def protected():
    spans=[(f['start'],f['end']-f['start']) for f in list(profile()['functions'].values())+list(n.profile()['functions'].values())]
    spans+=list(n.EXTRA_GLOBAL_REGIONS)+[(0x33267b8,8),(0x3483c34,4),(0x3797550,0x400),(0x3798180,28)]
    for f in profile()['functions'].values():
        for i in n.decode(bytes.fromhex(f['body_hex']),f['start']):
            for o in i.operands:
                if o.type==n.X86_OP_MEM and o.mem.base==n.X86_REG_RIP:spans.append((i.address+i.size+o.mem.disp,max(8,o.size)))
            if i.group(n.capstone.CS_GRP_CALL) and i.operands[0].type==n.X86_OP_IMM:spans.append((i.operands[0].imm,1))
    return sorted(set(spans))

def build(kind,**a):
    n.need(kind in KINDS,'consumer kind');f=profile()['functions'][kind];g=a['game_base'];s=a['component_address'];b=a['storage_address'];code=a['code_address']
    n.pointer(g,0x379819c,4096)
    regions=[(code,4096,16),(s,0x2b8,8),(b,0x490,16),(a['reject_address'],1,1)]
    n.pointer(a['release_address'],4096,16)
    if kind in ('acquire','defer'):regions.append((a['release_address'],4096,16))
    for p,z,align in regions:
        n.pointer(p,z,align)
        n.need(all(p+z<=g+v or g+v+l<=p for v,l in protected()),'consumer protected overlap')
    n.need(all(p+z<=q or q+l<=p for j,(p,z,_) in enumerate(regions) for q,l,_ in regions[j+1:]),'consumer overlap')
    n.need(b>=0x70,'storage bias underflow')
    out=bytearray();labels={};fixes=[];absfix=[];mapping={};patches=[]
    def emit(v):out.extend(bytes.fromhex(v) if isinstance(v,str) else v)
    def mov(reg,key,add=0):
        emit(bytes([0x48|(reg>>3),0xb8+(reg&7)]));absfix.append((len(out),key,add));emit(struct.pack('<Q',a[key]+add))
    def branch(target,cc=None,call=False):
        emit('e8' if call else 'e9' if cc is None else bytes([0x0f,cc]));fixes.append((len(out),target));emit(bytes(4))
    def label(k):labels[k]=len(out)
    # Keep RDX and the release flag (R8) intact through bounded identity checks.
    # No stack or data writes before refusal. All dense/pending pointers and
    # original eight-bucket probe identities must agree with the supplied S/B.
    emit('4d89c1');mov(10,'component_address');emit('4c39d1');branch('reject',0x85)
    mov(0,'game_base',0x33267b8);emit('4c3910');branch('reject',0x85)
    emit('41837a0808');branch('reject',0x87)
    emit('418b4a0c 413b4a08');branch('reject',0x87)
    emit('413b4a10');branch('reject',0x82)
    if kind=='release':emit('39ca');branch('reject',0x83)
    mov(0,'component_address',0x14);emit('49394258');branch('reject',0x85)
    emit('41837a6008');branch('reject',0x85)
    emit('41837a6400');branch('reject',0x85)
    emit('31c9 4531c0');label('occupied')
    emit('41837cca1400');branch('empty',0x84);emit('41ffc0');label('empty')
    emit('ffc1 83f908');branch('occupied',0x82)
    emit('453b4208');branch('reject',0x85)
    emit('4531db 41837a0800');branch('ready',0x84)
    label('active');mov(0,'storage_address');emit('4a8b04d8 4885c0');branch('reject',0x84)
    emit('8b4008 85c0');branch('reject',0x84)
    emit('3b05');fixes.append((len(out),0x3483c34));emit(bytes(4));branch('reject',0x84)
    emit('4189c0 450faf4268 4183e007 b908000000');label('probe')
    emit('433b44c214');branch('found',0x84)
    emit('43837cc21400');branch('reject',0x84)
    emit('41ffc0 4183e007 ffc9');branch('probe',0x85);branch('reject')
    label('found');emit('47395cc218');branch('reject',0x85)
    emit('41ffc3 453b5a08');branch('active',0x82)
    label('ready');mov(1,'component_address');emit('4d89c8');branch('body')
    label('reject');branch('external')
    while len(out)%16:emit('90')
    label('body');body=len(out);source=bytes.fromhex(f['body_hex'])
    for i in n.decode(source,f['start']):
        mapping[i.address]=len(out);raw=bytearray(i.bytes);patch=None
        if kind=='update':
            for o in i.operands:
                if o.type!=n.X86_OP_MEM:continue
                if 'r13' not in (i.reg_name(o.mem.base),i.reg_name(o.mem.index)):continue
                if o.mem.disp==0x70:patch=(13,-0x70,'pointer')
                elif 0x1d8<=o.mem.disp<=0x20c:patch=(13,0xf8,'secondary')
            # Four derived addresses without an array displacement. The 4/5
            # constants in this body are property categories, not player caps.
            if i.address in (0x664827,0x66489d,0x664917,0x664a10):
                bias={0x664827:0xf8,0x66489d:-0x48,0x664917:-0x70,0x664a10:-0x48}[i.address]
                patch=(13,bias,'derived')
        elif kind in ('acquire','defer') and i.address in (0x6656f0,0x66574c,0x665970):patch=(6,-0x70,'pointer')
        elif kind=='release' and i.address==0x665a04:patch=(1,-0x70,'pointer_destination')
        if patch:
            reg,bias,field=patch;mov(reg,'storage_address',bias);emit(raw)
            if field!='pointer_destination':mov(reg,'component_address')
            patches.append(dict(rva=hex(i.address),array=field,bias=bias));continue
        if (i.group(n.capstone.CS_GRP_JUMP) or i.group(n.capstone.CS_GRP_CALL)) and i.operands[0].type==n.X86_OP_IMM:
            branch(i.operands[0].imm,None if i.mnemonic in ('call','jmp') else raw[1] if raw[0]==0x0f else raw[0]+0x10,call=i.mnemonic=='call')
        else:
            for o in i.operands:
                if o.type==n.X86_OP_MEM and o.mem.base==n.X86_REG_RIP:
                    target=i.address+i.size+o.mem.disp;fixes.append((len(out)+i.disp_offset,('rip',target,len(out)+i.size)))
            emit(raw)
    mapping[f['end']]=len(out)
    relative=[]
    for off,target in fixes:
        nxt=off+4
        if isinstance(target,tuple):_,rva,nxt=target;dest=g+rva;parameter='game_base';add=rva
        elif target=='external':dest=a['reject_address'];parameter='reject_address';add=0
        elif isinstance(target,str):dest=code+labels[target];parameter=None
        elif target in mapping:dest=code+mapping[target];parameter=None
        elif target==0x6659e0:dest=a['release_address'];parameter='release_address';add=0
        else:dest=g+target;parameter='game_base';add=target
        struct.pack_into('<i',out,off,dest-code-nxt)
        if parameter is not None:relative.append((off,nxt,parameter,4,add))
    code_bytes=len(out)
    while len(out)%4:emit('00')
    leaf=len(out);emit('01000000');uwmap={};offsets=[]
    for r in f['fragments']:
        uwmap[r['unwind_rva']]=len(out);offsets.append(len(out));emit(bytes.fromhex(r['unwind_hex']))
    for r,off in zip(f['fragments'],offsets):
        raw=bytes.fromhex(r['unwind_hex']);start=r['start']
        # Conditional prologues and chained fragments retain exact saved
        # registers; every relocated prologue instruction boundary is remapped.
        def mapped(v):
            n.need(start+v in mapping,'unwind boundary');v=mapping[start+v]-mapping[start]
            n.need(0<=v<=255,'unwind prologue range');return v
        out[off+1]=mapped(raw[1]);at=4
        while at<4+raw[2]*2:
            op=raw[at+1]&15;n.need(op in (0,2,4),'unwind opcode')
            out[off+at]=mapped(raw[at]);at+=4 if op==4 else 2
        if raw[0]>>3&4:
            at=4+((raw[2]+1)&~1)*2;begin,end,uw=struct.unpack_from('<III',raw,at)
            struct.pack_into('<III',out,off+at,mapping[begin],mapping[end],uwmap[uw])
    table=len(out);rows=[(0,body,leaf)]+[(mapping[r['start']],mapping[r['end']],off) for r,off in zip(f['fragments'],offsets)]
    for row in rows:emit(struct.pack('<III',*row))
    n.need(len(out)<=4096,'consumer image overflow')
    n.need(len(patches)==dict(update=18,acquire=2,defer=1,release=1)[kind],'consumer coverage changed '+str(len(patches)))
    return dict(image=bytes(out),code_bytes=code_bytes,body_offset=body,unwind_offset=leaf,table_offset=table,function_count=len(rows),
        array_patches=patches,instruction_map=mapping,fixups=relative+[(off,0,key,8,add) for off,key,add in absfix])

def render():
    lines=['/* Generated from pinned saved component33 consumers; no installer. */'];infos=[]
    keys=list(REFERENCE)
    for kind in KINDS:
        r=build(kind,**REFERENCE);raw=bytearray(r['image']);name='ep_c33_consumer_'+kind
        for off,_,_,width,_ in r['fixups']:raw[off:off+width]=bytes(width)
        lines.append('static const uint8_t '+name+'[] = {')
        lines.extend('    '+','.join(f'0x{x:02x}' for x in raw[i:i+16])+',' for i in range(0,len(raw),16));lines+=['};','static const EpC33ConsumerFixup '+name+'_fixups[] = {']
        lines.extend('    {'+','.join(map(str,(off,nxt,keys.index(key),width,add)))+'},' for off,nxt,key,width,add in r['fixups']);lines.append('};')
        infos.append('    {'+','.join(map(str,(len(raw),r['code_bytes'],r['unwind_offset'],r['table_offset'],r['function_count'],len(r['fixups']))))+','+name+','+name+'_fixups},')
    lines+=['static const EpC33ConsumerTemplate ep_c33_consumer_templates[] = {',*infos,'};']
    lines+=['static const uint32_t ep_c33_consumer_protected[][2] = {']
    lines.extend('    {'+str(p)+','+str(z)+'},' for p,z in protected());lines.append('};')
    return ('\n'.join(lines)+'\n').encode()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args();raw=render()
    if a.write:HEADER.write_bytes(raw)
    else:n.need(HEADER.read_bytes()==raw,'consumer template stale')
    print(json.dumps(dict(passed=True,images={k:{x:build(k,**REFERENCE)[x] for x in ('code_bytes','function_count')} for k in KINDS},header_sha256=n.sha(raw),game_access=False)))
