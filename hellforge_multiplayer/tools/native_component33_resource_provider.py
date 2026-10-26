"""Pinned package/threshold getter bodies from the existing offline capture."""
import json
import native_component33_image as n
import native_component33_resources as resources
LOCK=n.PROJECT/'native-component33-resource-provider.lock.json'
HEADER=n.PROJECT/'mod/src/ep_component33_resource_provider_template.h'
NATIVE_CALLS=(('resolve',0x6656c0,0x665704,0x665724),('load',0x6656c0,0x665847,0x66585b),('dispose',0x6659e0,0x665ada,0x665aee),('defer',0x665940,0x665985,0x6659a5))

def native_call_sources():
    p=json.loads(resources.LOCK.read_bytes())
    p['functions']['0x665940']=json.loads((n.PROJECT/'native-component33-consumers.lock.json').read_bytes())['functions']['defer']
    return [(name,start,bytes.fromhex(p['functions'][hex(root)]['body_hex'])[start-root:end-root]) for name,root,start,end in NATIVE_CALLS]

def render_native_calls():
    lines=['/* Saved Win64 engine call sites; no target implementation inferred. */']
    for name,start,raw in native_call_sources():
        lines.append('static const uint8_t ep_c33_native_'+name+'_source[]={')
        lines+=['    '+','.join('0x'+format(x,'02x') for x in raw[i:i+16])+',' for i in range(0,len(raw),16)];lines.append('};')
    return '\n'.join(lines)+'\n'
def profile():
    p=json.loads(LOCK.read_bytes());im=n.Image(n.ROOT/p['capture_directory'])
    n.need(p['game_build']=='25480438','source build')
    for name,f in p['functions'].items():
        raw=bytes.fromhex(f['body_hex']);n.need(len(raw)==f['end']-f['start'] and n.sha(raw)==f['sha256'] and im.read(f['start'],len(raw))==raw,'saved getter changed')
        n.decode(raw,f['start'])
    n.need(p['functions']['package']['start']==0x4f6430 and p['functions']['package']['end']==0x4f649b,'package body')
    n.need(im.containing(0x7af0a0)[:2]==(p['functions']['threshold']['start'],p['functions']['threshold']['end']),'threshold body')
    return p
def render():
    lines=['/* Complete saved getter bodies, build 25480438; generated offline. */']
    for name,f in profile()['functions'].items():
        raw=bytes.fromhex(f['body_hex']);lines.append('static const uint8_t ep_c33_'+name+'_source[]={')
        lines+=['    '+','.join('0x'+format(x,'02x') for x in raw[i:i+16])+',' for i in range(0,len(raw),16)];lines.append('};')
    f=resources.profile()['functions']['0x664520']
    raw=bytes.fromhex(f['body_hex'])[0x664b2f-f['start']:0x664ba9-f['start']]
    n.need(sum(i.size for i in n.decode(raw,0x664b2f))==122,'complete drain tail')
    lines.append('/* Saved UPDATE drain tail, before its unchanged epilogue. */')
    lines.append('static const uint8_t ep_c33_drain_source[]={')
    lines+=['    '+','.join('0x'+format(x,'02x') for x in raw[i:i+16])+',' for i in range(0,len(raw),16)];lines.append('};')
    return ('\n'.join(lines)+'\n'+render_native_calls()).encode()
if __name__=='__main__':
    HEADER.write_bytes(render());print(json.dumps(dict(header_sha256=n.sha(HEADER.read_bytes()),game_access=False)))
