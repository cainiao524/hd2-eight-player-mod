"""Pinned package/threshold getter bodies from the existing offline capture."""
import json
import native_component33_image as n
LOCK=n.PROJECT/'native-component33-resource-provider.lock.json'
HEADER=n.PROJECT/'mod/src/ep_component33_resource_provider_template.h'
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
    return ('\n'.join(lines)+'\n').encode()
if __name__=='__main__':
    HEADER.write_bytes(render());print(json.dumps(dict(header_sha256=n.sha(HEADER.read_bytes()),game_access=False)))
