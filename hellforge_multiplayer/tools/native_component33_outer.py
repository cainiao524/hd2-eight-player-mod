"""Five pinned outer windows and two register-preserving B getters; no installer."""
import argparse,functools,json,struct
import native_component33_image as n
import native_component33_consumers as consumer
LOCK=n.PROJECT/'native-component33-outer.lock.json'
LOCK_SHA='fd88538a474d72c419aadd1045ac0721d61692bcb4ba9ad50fe1ab285456583c'
HEADER=n.PROJECT/'mod/src/ep_component33_outer_template.h'
REFERENCE=dict(consumer.REFERENCE)
KINDS=('r14_rax_to_rcx','rsi_rdi_to_rax')

@functools.lru_cache()
def profile():
    n.need(n.sha(LOCK.read_bytes())==LOCK_SHA,'outer lock changed')
    p=json.loads(LOCK.read_bytes());im=n.Image(n.ROOT/p['capture_directory']);consumer.profile()
    for f in p['callers'].values():
        raw=bytes.fromhex(f['body_hex'])
        n.need(len(raw)==f['end']-f['start'] and n.sha(raw)==f['sha256'] and im.read(f['start'],len(raw))==raw,'outer source changed')
        instructions=n.decode(raw[:f['code_end']-f['start']],f['start'])
        for r in f['fragments']:
            n.need(im.containing(r['start'])==(r['start'],r['end'],r['unwind_rva']) and im.read(r['unwind_rva'],len(bytes.fromhex(r['unwind_hex'])))==bytes.fromhex(r['unwind_hex']),'outer unwind changed')
        for w in p['windows']:
            if not f['start']<=w['start']<f['end']:continue
            expected=bytes.fromhex(w['expected_hex'])
            n.need(len(expected)==5 and im.read(w['start'],5)==expected and n.sha(expected)==w['sha256'],'outer window changed')
            for i in instructions:
                if (i.group(n.capstone.CS_GRP_JUMP) or i.group(n.capstone.CS_GRP_CALL)) and i.operands[0].type==n.X86_OP_IMM:
                    n.need(not w['start']<i.operands[0].imm<w['end'],'outside edge enters window')
            if w['target']!='release':
                following=bytes.fromhex(w['following_hex']);n.need(im.read(w['end'],len(following))==following,'flag liveness source changed')
                rows=n.decode(following,w['end']);n.need(rows[-1].mnemonic in ('cmp','test') and all(i.mnemonic=='mov' for i in rows[:-1]),'flags used before replacement')
    # The first parent contains a compiler jump table after its RET; do not
    # mistake those data bytes for instructions. Validate every saved target.
    f=p['callers']['release'];raw=bytes.fromhex(f['body_hex'])
    targets=struct.unpack_from('<13I',raw,0xb524b8-f['start'])
    n.need(max(raw[0xb524ec-f['start']:])<13 and 0xb51fd0 in targets,'registry switch table changed')
    n.need(all(f['start']<=v<f['code_end'] and all(not w['start']<v<w['end'] for w in p['windows']) for v in targets),'switch enters window')
    return p

@functools.lru_cache()
def protected():
    spans=list(consumer.protected())
    for f in profile()['callers'].values():
        spans.append((f['start'],f['end']-f['start']))
        for i in n.decode(bytes.fromhex(f['body_hex'])[:f['code_end']-f['start']],f['start']):
            for o in i.operands:
                if o.type==n.X86_OP_MEM and o.mem.base==n.X86_REG_RIP:
                    rva=i.address+i.size+o.mem.disp
                    if rva:spans.append((rva,max(8,o.size)))
    return sorted(set(spans))

def build(**a):
    p=profile();g=a['game_base'];code=a['code_address'];regions=[(code,4096,16),(a['component_address'],0x2b8,8),(a['storage_address'],0x490,16),(a['release_address'],4096,16),(a['reject_address'],1,1)]
    n.pointer(g,0x379819c,4096)
    for address,size,align in regions:
        n.pointer(address,size,align);n.need(all(address+size<=g+x or g+x+z<=address for x,z in protected()),'outer protected overlap')
    n.need(all(x+z<=y or y+l<=x for j,(x,z,_) in enumerate(regions) for y,l,_ in regions[j+1:]),'outer overlap')
    out=bytearray();fixups=[];entries={};rows=[]
    def emit(h):out.extend(bytes.fromhex(h) if isinstance(h,str) else h)
    def mov(reg,key,add=0):
        emit(bytes([0x48|(reg>>3),0xb8+(reg&7)]));fixups.append((len(out),0,key,8,add));emit(struct.pack('<Q',a[key]+add))
    for kind in KINDS:
        while len(out)%16:emit('90')
        start=len(out);entries[kind]=start;codes=[];local=[];labels={}
        def branch(label,cc=None):
            emit('e9' if cc is None else bytes([0x0f,cc]));local.append((len(out),label));emit(bytes(4))
        # Only volatile scratch registers are pushed. The displaced MOV's
        # destination is the one register deliberately not restored.
        saved=[0 if kind==KINDS[0] else 1,2,8,9,10,11]
        for reg in saved:
            emit((b'\x41' if reg>=8 else b'')+bytes([0x50+(reg&7)]));codes.append((len(out)-start,2))
        prologue=len(out)-start
        emit('488bd0' if kind==KINDS[0] else '488bd7')
        mov(10,'component_address');emit('4d39d6' if kind==KINDS[0] else '4c39d6');branch('refuse',0x85)
        mov(0,'game_base',0x33267b8);emit('4c3910');branch('refuse',0x85)
        emit('4883fa08');branch('refuse',0x83)
        emit('41837a0808');branch('refuse',0x87)
        emit('418b4a0c 413b4a08');branch('refuse',0x87)
        emit('413b4a10');branch('refuse',0x82)
        emit('39ca');branch('refuse',0x83)
        mov(0,'component_address',0x14);emit('49394258');branch('refuse',0x85)
        emit('41837a6008');branch('refuse',0x85)
        emit('41837a6400');branch('refuse',0x85)
        mov(0,'storage_address');emit('4c8b1cd0 4d85db');branch('refuse',0x84)
        emit('458b4308 4585c0');branch('refuse',0x84)
        mov(0,'game_base',0x3483c34);emit('443b00');branch('refuse',0x84)
        emit('4589c1 450faf4a68 4183e107 b908000000');labels['probe']=len(out)
        emit('473b44ca14');branch('found',0x84)
        emit('43837cca1400');branch('refuse',0x84)
        emit('41ffc1 4183e107 ffc9');branch('probe',0x85);branch('refuse')
        labels['found']=len(out);emit('433954ca18');branch('refuse',0x85)
        emit('498bcb' if kind==KINDS[0] else '498bc3')
        def restore():
            for j,reg in enumerate(saved):emit(bytes([0x48|(4 if reg>=8 else 0),0x8b,0x44+((reg&7)<<3),0x24,(5-j)*8]))
            emit('4883c430')
        restore();emit('c3');labels['refuse']=len(out);restore();emit('e9')
        fixups.append((len(out),len(out)+4,'reject_address',4,0));emit(struct.pack('<i',a['reject_address']-code-len(out)-4))
        end=len(out)
        for off,label in local:struct.pack_into('<i',out,off,labels[label]-off-4)
        rows.append((start,end,prologue,codes))
    code_bytes=len(out)
    while len(out)%4:emit('00')
    first_unwind=len(out);functions=[]
    for start,end,prologue,codes in rows:
        uw=len(out);emit(bytes([1,prologue,len(codes),0]))
        for offset,op in reversed(codes):emit(bytes([offset,op]))
        functions.append((start,end,uw))
    table=len(out)
    for row in functions:emit(struct.pack('<III',*row))
    windows=[]
    for w in p['windows']:
        dest=a['release_address'] if w['target']=='release' else code+entries[w['target']]
        target=g+w['start'];windows.append(dict(target=target,bytes=5,call_offset=0,expected=bytes.fromhex(w['expected_hex']),replacement=b'\xe8'+struct.pack('<i',dest-target-5)))
    n.need(len(out)<=4096,'outer image size')
    return dict(image=bytes(out),code_bytes=code_bytes,unwind_offset=first_unwind,table_offset=table,function_count=len(functions),entries=entries,fixups=fixups,windows=windows)

def render():
    r=build(**REFERENCE);raw=bytearray(r['image']);lines=['/* Generated pinned component33 outer bridge; no installer. */']
    for off,_,_,width,_ in r['fixups']:raw[off:off+width]=bytes(width)
    lines.append('static const uint8_t ep_c33_outer_image[] = {')
    lines.extend('    '+','.join(f'0x{x:02x}' for x in raw[i:i+16])+',' for i in range(0,len(raw),16));lines.append('};')
    keys=list(REFERENCE)
    lines.append('static const EpC33OuterFixup ep_c33_outer_fixups[] = {')
    lines.extend('    {'+','.join(map(str,(off,nxt,keys.index(key),width,add)))+'},' for off,nxt,key,width,add in r['fixups']);lines.append('};')
    lines.append('static const EpC33OuterWindowTemplate ep_c33_outer_windows[] = {')
    for w in profile()['windows']:
        entry=0xffffffff if w['target']=='release' else r['entries'][w['target']]
        lines.append('    {'+str(w['start'])+','+str(entry)+',{'+','.join(str(x) for x in bytes.fromhex(w['expected_hex']))+'}},')
    lines.append('};\nstatic const uint32_t ep_c33_outer_protected[][2] = {')
    lines.extend('    {'+str(x)+','+str(z)+'},' for x,z in protected());lines.append('};')
    for k in ('code_bytes','unwind_offset','table_offset','function_count'):lines.append('static const uint32_t ep_c33_outer_'+k+' = '+str(r[k])+';')
    return ('\n'.join(lines)+'\n').encode()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args();raw=render()
    if a.write:HEADER.write_bytes(raw)
    else:n.need(HEADER.read_bytes()==raw,'outer template stale')
    print(json.dumps(dict(passed=True,header_sha256=n.sha(raw),game_access=False)))
