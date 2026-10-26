"""Two saved post-creation windows and a shared leaf bridge; never install."""
import argparse,functools,json,struct
import native_component33_image as n
LOCK=n.PROJECT/'native-component33-readers.lock.json'
LOCK_SHA='32813972fd78649230245c5a0bc600a621ea8800f3243cc2c87b3b84dcaa5d08'
HEADER=n.PROJECT/'mod/src/ep_component33_readers_template.h'
REFERENCE=dict(game_base=0x180000000,code_address=0x190000000,component_address=0x210000000,
               storage_address=0x220000000,reset_address=0x190010000,reject_address=0x190020000)

@functools.lru_cache()
def profile():
    n.need(n.sha(LOCK.read_bytes())==LOCK_SHA,'reader lock changed')
    r=json.loads(LOCK.read_bytes());im=n.Image(n.ROOT/r['capture_directory'])
    n.profile()
    for f in r['callers'].values():
        for x in (f,f['window']):
            raw=bytes.fromhex(x['body_hex'])
            n.need(len(raw)==x['end']-x['start'] and n.sha(raw)==x['sha256'] and im.read(x['start'],len(raw))==raw,'caller source changed')
        for x in f['fragments']:
            n.need(im.containing(x['start'])==(x['start'],x['end'],x['unwind_rva']),'caller fragment changed')
            n.need(im.read(x['unwind_rva'],len(bytes.fromhex(x['unwind_hex'])))==bytes.fromhex(x['unwind_hex']),'caller unwind changed')
        w=f['window']
        for i in n.decode(bytes.fromhex(f['body_hex']),f['start']):
            if (i.group(n.capstone.CS_GRP_JUMP) or i.group(n.capstone.CS_GRP_CALL)) and i.operands[0].type==n.X86_OP_IMM:
                n.need(not(w['start']<i.operands[0].imm<w['end'] and not w['start']<=i.address<w['end']),'outside edge enters replaced window')
    return r

def protected():
    return [(f['start'],f['end']-f['start']) for f in n.profile()['functions'].values()]+list(n.EXTRA_GLOBAL_REGIONS)+[(0x33267B8,8),(0x3483C34,4)]+[(f['start'],f['end']-f['start']) for f in profile()['callers'].values()]

def build(**a):
    r=profile();g=a['game_base'];code=a['code_address'];s=a['component_address'];b=a['storage_address']
    regions=[(code,4096),(s,0x2B8),(b,0x490),(a['reset_address'],4096),(a['reject_address'],1)]
    n.pointer(g,0x3483C38,4096)
    for (address,size),align in zip(regions,(16,8,16,16,1)):n.pointer(address,size,align)
    regions += [(g+x,size) for x,size in protected()]
    n.need(all(x+size<=y or y+length<=x for i,(x,size) in enumerate(regions) for y,length in regions[i+1:]),'reader overlap')
    out=bytearray();fixes=[];rejects=[]
    def emit(h):out.extend(bytes.fromhex(h))
    def mov(op,key,value):emit(op);fixes.append((len(out),key));out.extend(struct.pack('<Q',value))
    def refuse(cc):emit('0f'+cc);rejects.append(len(out));out.extend(bytes(4))
    mov('49bb','component_address',s);emit('4c39d9');refuse('85')
    mov('48b8','global_component',g+0x33267B8);emit('4c3918');refuse('85')
    emit('4883fa08');refuse('83') # full 64-bit ordinal < 8
    emit('41837b0808');refuse('87')
    emit('418b430c 413b4308');refuse('87')
    emit('413b4310');refuse('82')
    emit('39c2');refuse('83') # ordinal < D
    mov('48b8','storage_address',b);emit('488b14d0 4885d2');refuse('84')
    mov('48b8','reset_address',a['reset_address']);emit('ffe0') # same caller frame, tail to per-entity RESET
    fail=len(out);mov('48b8','reject_address',a['reject_address']);emit('ffe0')
    for off in rejects:struct.pack_into('<i',out,off,fail-off-4)
    code_bytes=len(out)
    while len(out)%4:out.append(0)
    uw=len(out);out.extend(bytes.fromhex('01000000'));table=len(out);out.extend(struct.pack('<III',0,code_bytes,uw))
    windows=[]
    for name,f in r['callers'].items():
        w=f['window'];target=g+w['start'];p=bytearray() if name=='single' else bytearray.fromhex('488bce 8bd7')
        off=len(p);p.append(0xe8);p.extend(struct.pack('<i',code-target-off-5));p.extend(b'\x90'*(w['end']-w['start']-len(p)))
        windows.append(dict(target=target,bytes=len(p),call_offset=off,expected=bytes.fromhex(w['body_hex']),replacement=bytes(p)))
    return dict(image=bytes(out),code_bytes=code_bytes,unwind_offset=uw,table_offset=table,function_count=1,fixups=fixes,windows=windows)

def render():
    p=build(**REFERENCE);lines=['/* Generated saved post-creation bridge; no installer. */']
    def array(name,blob):
        lines.append('static const uint8_t '+name+'[] = {')
        lines.extend('    '+','.join(f'0x{x:02x}' for x in blob[i:i+16])+',' for i in range(0,len(blob),16));lines.append('};')
    raw=bytearray(p['image'])
    for off,key in p['fixups']:raw[off:off+8]=bytes(8)
    array('ep_c33_reader_image',raw)
    for i,w in enumerate(p['windows']):
        array('ep_c33_reader_expected_'+str(i),w['expected']);raw=bytearray(w['replacement']);raw[w['call_offset']+1:w['call_offset']+5]=bytes(4);array('ep_c33_reader_patch_'+str(i),raw)
    keys=['component_address','global_component','storage_address','reset_address','reject_address']
    lines.append('static const uint32_t ep_c33_reader_fixups[][2] = {'+','.join('{'+str(off)+','+str(keys.index(key))+'}' for off,key in p['fixups'])+'};')
    lines.append('static const uint32_t ep_c33_reader_protected[][2] = {'+','.join('{'+str(a)+','+str(z)+'}' for a,z in protected())+'};')
    for k in ('code_bytes','unwind_offset','table_offset'):lines.append('static const uint32_t ep_c33_reader_'+k+' = '+str(p[k])+';')
    return ('\n'.join(lines)+'\n').encode()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--write',action='store_true');args=ap.parse_args();data=render()
    if args.write:HEADER.write_bytes(data)
    else:n.need(HEADER.read_bytes()==data,'reader template stale')
    print(json.dumps(dict(passed=True,header_sha256=n.sha(data),game_access=False)))
