"""Pinned resource cache rebinding. Numeric generation only; no target access."""
import argparse,functools,json,struct
import native_component33_image as n
import native_component33_consumers as consumer
LOCK=n.PROJECT/'native-component33-resources.lock.json'
LOCK_SHA='000f5c9193813e73fbe693aad2057eced69b2c1e81f509727bcb651849fed1f0'
HEADER=n.PROJECT/'mod/src/ep_component33_resources_template.h'

def size(capacity):
    n.need(128<=capacity<=65536 and capacity&(capacity-1)==0,'resource capacity')
    return 48+24*capacity
def target(address,capacity,rva):
    for start,length,offset in ((0x3798180,28,0),(0x348ba88,8,32),(0x3797550,1024,48),(0x3797960,2048,48+8*capacity)):
        if start<=rva<start+length:return address+offset+rva-start
    return None

@functools.lru_cache()
def profile():
    n.need(n.sha(LOCK.read_bytes())==LOCK_SHA,'resource lock changed');p=json.loads(LOCK.read_bytes());im=n.Image(n.ROOT/p['capture_directory']);observed=[]
    for f in p['functions'].values():
        raw=bytes.fromhex(f['body_hex']);n.need(n.sha(raw)==f['sha256'] and im.read(f['start'],f['end']-f['start'])==raw,'resource source changed')
        for row in f['fragments']:n.need(im.containing(row[0])==tuple(row),'resource fragment changed')
        for i in n.decode(raw,f['start']):
            for o in i.operands:
                if o.type==n.X86_OP_MEM and o.mem.base==n.X86_REG_RIP:
                    rva=i.address+i.size+o.mem.disp
                    if target(0,128,rva) is not None:observed.append((i.address,i.bytes.hex(),rva))
    expected=[(int(h['rva'],16),h['bytes'],int(h['target'],16)) for h in p['inventory']['hits']]
    n.need(sorted(observed)==sorted(expected) and len(observed)==59,'resource reference coverage changed')
    return p

@functools.lru_cache()
def descriptors():
    p=profile();fixups=[];windows=[]
    for index,kind in enumerate(consumer.KINDS,1):
        r=consumer.build(kind,**consumer.REFERENCE)
        for off,nxt,key,width,add in r['fixups']:
            if key=='game_base' and target(0,128,add) is not None:
                n.need(width==4,'resource relocation width');fixups.append((index,off,nxt,add))
    roots=(0x51ade0,0x664210,0xb5e710)
    constants={0x51adfa:1,0x664227:1,0x51ae6d:2,0x66428d:2,0x51adee:3,0x66421b:3}
    for root in roots:
        f=p['functions'][hex(root)]
        for i in n.decode(bytes.fromhex(f['body_hex']),root):
            t=None;off=i.disp_offset;width=i.disp_size
            for o in i.operands:
                if o.type==n.X86_OP_MEM and o.mem.base==n.X86_REG_RIP:
                    rva=i.address+i.size+o.mem.disp
                    if target(0,128,rva) is not None:t=rva
            # Capacity stores need BOTH the RIP destination and the immediate
            # changed in the same instruction, represented as two windows only
            # after merging by the emitter below.
            if t is not None:windows.append((i.address,i.size,off,width,t,bytes(i.bytes)))
            if i.address in constants:windows.append((i.address,i.size,i.imm_offset,i.imm_size,constants[i.address],bytes(i.bytes)))
    n.need(len(fixups)==25 and len(windows)==40,'resource descriptors changed')
    return fixups,windows

def consumer_image(kind,a,address,capacity):
    z=size(capacity);n.pointer(address,z,16);r=consumer.build(kind,**a);raw=bytearray(r['image'])
    regions=[(a['game_base'],0x4000000),(a['code_address'],4096),(a['component_address'],0x2b8),(a['storage_address'],0x490),(a['release_address'],4096),(a['reject_address'],1)]
    n.need(all(address+z<=v or v+l<=address for v,l in regions),'resource overlap')
    for index,off,nxt,rva in descriptors()[0]:
        if index==consumer.KINDS.index(kind)+1:struct.pack_into('<i',raw,off,target(address,capacity,rva)-a['code_address']-nxt)
    return {**r,'image':bytes(raw)}

def windows(game,address,capacity,reset):
    z=size(capacity);n.pointer(address,z,16);n.pointer(game,0x4000000,4096);n.pointer(reset,4096,16)
    n.need(all(address+z<=v or v+l<=address for v,l in ((game,0x4000000),(reset,4096))),'resource window overlap')
    result={}
    for rva,length,off,width,t,raw in descriptors()[1]:
        w=result.setdefault(rva,dict(rva=rva,bytes=length,expected=raw,replacement=bytearray(raw)))
        value=capacity if t==1 else 8*capacity if t==2 else (reset if t==3 else target(address,capacity,t))-game-rva-length
        n.need(width==4,'resource window width');struct.pack_into('<i',w['replacement'],off,value)
    return [dict(w,replacement=bytes(w['replacement'])) for w in result.values()]

def render():
    fixes,patches=descriptors();lines=['/* Generated from saved code; does not publish any window. */','static const ResourceFix ep_c33_resource_fixups[] = {']
    lines+=['    {'+','.join(map(str,row))+'},' for row in fixes];lines+=['};','static const ResourceWindow ep_c33_resource_window_templates[] = {']
    for rva,length,off,width,t,raw in patches:lines.append('    {'+','.join(map(str,(rva,length,off,width,t)))+',{'+','.join(map(str,raw))+'}},')
    lines+=['};'];return ('\n'.join(lines)+'\n').encode()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args();raw=render()
    if a.write:HEADER.write_bytes(raw)
    else:n.need(HEADER.read_bytes()==raw,'resource template stale')
    print(json.dumps(dict(passed=True,header_sha256=n.sha(raw),consumer_relocations=len(descriptors()[0]),original_window_fixups=len(descriptors()[1]),game_access=False)))
