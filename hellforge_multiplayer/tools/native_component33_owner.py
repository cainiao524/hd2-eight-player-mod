"""Pinned in-place owner window; numeric generation, never a patch installer."""
import argparse,functools,json,struct
import native_component33_image as n
LOCK=n.PROJECT/'native-component33-owner.lock.json'
LOCK_SHA='438ea27161073d055567ec93fd7b3e20990984577b049962d814245c9458a4ef'
HEADER=n.PROJECT/'mod/src/ep_component33_owner_template.h'

@functools.lru_cache()
def profile():
    n.need(n.sha(LOCK.read_bytes())==LOCK_SHA,'owner lock changed')
    r=json.loads(LOCK.read_bytes());im=n.Image(n.ROOT/r['capture_directory']);owner=r['owner']
    raw=im.read(owner['start'],owner['end']-owner['start'])
    n.need(n.sha(raw)==owner['sha256'],'owner function changed')
    for key in ('prologue','window','continuation','epilogue','next_component','prologue_constant'):
        f=r[key];blob=bytes.fromhex(f['body_hex'])
        n.need(len(blob)==f['end']-f['start'] and n.sha(blob)==f['sha256'] and im.read(f['start'],len(blob))==blob,'owner source changed: '+key)
    for f in [owner['fragment'],*r['next_fragments']]:
        n.need(im.containing(f['start'])==(f['start'],f['end'],f['unwind_rva']),'owner runtime row changed')
        blob=bytes.fromhex(f['unwind_hex']);n.need(im.read(f['unwind_rva'],len(blob))==blob,'owner unwind changed')
    w=r['window'];rows=n.decode(raw,owner['start'])
    for i in rows:
        if i.group(n.capstone.CS_GRP_JUMP) and i.operands[0].type==n.X86_OP_IMM:
            target=i.operands[0].imm
            n.need(not(w['start']<target<w['end'] and not w['start']<=i.address<w['end']),'external direct branch enters replaced window')
    n.need(w['end']-w['start']==75 and bytes.fromhex(w['body_hex'])[:17].hex()=='488db3a03c00008b7e0c8b46083bf8733a','owner prefix changed')
    return r

def build(game_base,promote_address):
    r=profile();n.pointer(game_base,0x3483C38,4096);n.pointer(promote_address,4096,16)
    ranges=[(f['start'],f['end']) for f in n.profile()['functions'].values()]
    ranges += [(r[k]['start'],r[k]['end']) for k in ('owner','next_component','prologue_constant')]
    ranges += [(a,a+size) for a,size in n.EXTRA_GLOBAL_REGIONS]+[(0x33267B8,0x33267C0),(0x3483C34,0x3483C38)]
    n.need(all(promote_address+4096<=game_base+a or game_base+b<=promote_address for a,b in ranges),'promoter overlaps source/global')
    w=r['window'];target=game_base+w['start'];expected=bytes.fromhex(w['body_hex'])
    out=bytearray(expected[:17]);out.extend(bytes.fromhex('488bce e8'));call_offset=len(out)-1
    out.extend(struct.pack('<i',promote_address-(target+len(out)+4)))
    out.extend(bytes.fromhex('8bf8 8b5610 3bf8 e9'))
    out.extend(struct.pack('<i',len(expected)-(len(out)+4)))
    out.extend(b'\x90'*(len(expected)-len(out)))
    return dict(target=target,bytes=len(out),call_offset=call_offset,expected=expected,replacement=bytes(out))

def render():
    p=build(0x180000000,0x190000000);replacement=bytearray(p['replacement']);replacement[p['call_offset']+1:p['call_offset']+5]=bytes(4)
    lines=['/* Generated owner inline window. No installation or game access.',
           ' * Lock SHA256 '+n.sha(LOCK.read_bytes()),' */']
    for name,blob in (('expected',p['expected']),('replacement',replacement)):
        lines+=['static const uint8_t ep_component33_owner_'+name+'[] = {']
        lines+=['    '+','.join(f'0x{b:02x}' for b in blob[i:i+16])+',' for i in range(0,len(blob),16)];lines+=['};']
    lines+=['static const uint32_t ep_component33_owner_call_offset = '+str(p['call_offset'])+';']
    return ('\n'.join(lines)+'\n').encode()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args();data=render()
    if a.write:HEADER.write_bytes(data)
    else:n.need(HEADER.read_bytes()==data,'stale owner template')
    print(json.dumps(dict(passed=True,window_bytes=75,header_sha256=n.sha(data),game_access=False)))
