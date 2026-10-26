"""Pinned registry/association clones with complete Windows chained unwind.

Saved bytes only. The registry's other tags keep their original external calls;
their contracts and earlier effects are not converted into rollback guarantees.
"""
import json,struct
import native_remove_image as common
ROOT,PROJECT=common.ROOT,common.PROJECT
load,require,sha,source=common.load,common.require,common.sha,common.source
KINDS=('update','association')
KEYS=('0xb54e00','0x606520')
LOCK=PROJECT/'native-registry.lock.json'
LOCK_SHA256='0130519db9642a033b2a1a6fe8aaec10a3e480b40dfed73ecbfe0b58b201b3c9'

def profile():
    raw=LOCK.read_bytes();require(sha(raw)==LOCK_SHA256,'Registry source lock changed');data=json.loads(raw)
    source.audit(data,schema='hellforge_captured_registry_unwind_v1',names=KINDS);return data

def legacy():
    for path,digest in profile()['legacy_source_sha256'].items():
        require(sha((ROOT/path).read_bytes())==digest,'Registry dependency changed: '+path)
    return load('pinned_registry',ROOT/'eight_player_candidate_20260927/Native/roster_registry_update.py')

def with_unwind(candidate,kind):
    fn=profile()['functions'][kind];root=kind=='update';base=candidate['code_address']
    require(candidate['source_sha256']==fn['code_sha256'],'Registry source identity changed')
    raw=bytes.fromhex(candidate['code_hex']);require(sha(raw)==candidate['code_sha256'],'Registry code changed')
    code=bytearray(raw);mapping=candidate['instruction_address_map'];frags=fn['fragments']
    rejection_bytes=47 if root else 11;reasons=range(1,10) if root else (1,3,4)
    end=len(raw)-len(reasons)*rejection_bytes
    if root:
        old=legacy();original=old.load_sources(ROOT/fn['evidence_path'])[KEYS[0]]
        restore=original[0x346:0x368]
        require(len(restore)==34,'Registry restore changed')
        for n,reason in enumerate(reasons):
            at=end+n*rejection_bytes;mov=b'\x41\xba'+struct.pack('<I',reason)
            require(code[at:at+42]==b'\x8b\xcb'+restore+mov,'Registry rejection changed')
            # Windows must see ADD RSP / POPs followed immediately by the tail
            # branch. R10D is volatile and can be set before the restoration.
            code[at:at+42]=b'\x8b\xcb'+mov+restore
    else:
        for n,reason in enumerate(reasons):
            at=end+n*rejection_bytes
            require(code[at:at+6]==b'\x41\xba'+struct.pack('<I',reason),'Association rejection changed')
    cursor=(len(code)+3)&~3;image=bytearray(code)+bytes(cursor-len(code));rows=[];mapped={}
    def put(blob):
        nonlocal image
        require(len(image)%4==0,'Unaligned unwind blob')
        offset=len(image);image+=blob;return offset
    leaf=put(b'\x01\0\0\0')
    body=candidate['body_address']-base
    if body:rows.append((0,body,leaf))
    for fragment in frags:
        a,b,u=struct.unpack('<III',bytes.fromhex(fragment['runtime_function_hex']))
        begin=mapping[hex(a)]-base;stop=end if b==int(fn['end_exclusive'],16) else mapping[hex(b)]-base
        uw=bytearray.fromhex(fragment['unwind_hex'])
        original=legacy().load_sources(ROOT/fn['evidence_path'])[KEYS[KINDS.index(kind)]]
        require(code[begin:begin+uw[1]]==original[a-int(fn['entry'],16):a-int(fn['entry'],16)+uw[1]],'Changed registry prologue')
        if uw[0]>>3==4:
            parent=struct.unpack('<III',uw[-12:]);require(parent in mapped,'Unresolved registry unwind parent')
            uw[-12:]=struct.pack('<III',*mapped[parent])
        row=(begin,stop,put(uw));rows.append(row);mapped[(a,b,u)]=row
    if root:
        uw=bytearray.fromhex(frags[1]['unwind_hex']);require(uw[0]==33 and uw[1]==25,'Registry conditional saves changed')
        uw[1]=0;at=4
        while at<4+2*uw[2]:
            require(uw[at+1]&15==4,'Unexpected registry save');uw[at]=0;at+=4
        parent=struct.unpack('<III',uw[-12:]);uw[-12:]=struct.pack('<III',*mapped[parent])
        reject_unwind=put(uw)
    else:reject_unwind=put(b'\x01\0\0\0')
    rows.append((end,len(code),reject_unwind));table=len(image)
    require(all(a<b and (i==0 or rows[i-1][1]==a) for i,(a,b,_) in enumerate(rows)),'Incomplete registry unwind coverage')
    for row in rows:image+=struct.pack('<III',*row)
    updated={**candidate,'code_hex':bytes(code).hex(),'code_sha256':sha(code),
        'status':'offline_registry_with_unwind','runtime_verified':False,'unwind_registered':False}
    return dict(candidate=updated,image=bytes(image),unwind_offset=leaf,table_offset=table,function_count=len(rows),
                rejection_offset=end,rejection_bytes=rejection_bytes,rejection_reasons=list(reasons))

def build(**addresses):
    old=legacy();fn=profile()['functions']['update'];original=old.build(old.load_sources(ROOT/fn['evidence_path']),**addresses)
    artifacts={kind:with_unwind(original['functions'][key],kind) for kind,key in zip(KINDS,KEYS)}
    regions=[dict(r) for r in original['known_regions']]
    for kind,key in zip(KINDS,KEYS):
        next(r for r in regions if r['name']=='registry '+key)['size_bytes']=len(artifacts[kind]['image'])
    old._check_regions(regions)
    return dict(candidate={**original,'functions':{key:artifacts[kind]['candidate'] for kind,key in zip(KINDS,KEYS)},
                           'known_regions':regions},artifacts=artifacts)

def load_fixture():
    d=profile();p=ROOT/d['fixture_path'];require(sha(p.read_bytes())==d['fixture_sha256'],'Registry fixture changed')
    m=load('hellforge_registry_fixture',p)
    require(m.unicorn.__version__=='2.1.4' and m.capstone.__version__=='5.0.7','Wrong emulator/decoder');return m

def bind_fixture(module,library=None):
    def emit(bodies,**addresses):
        require(all(sha(bodies[k])==profile()['functions'][name]['code_sha256'] for name,k in zip(KINDS,KEYS)),'Changed registry inputs')
        ref=build(**addresses)
        return library.registry_candidate(addresses,ref) if library else ref['candidate']
    module.native.build=emit
    # The pinned test also checks its historical fifteen-function bundle byte
    # for byte. Keep that independent legacy assertion while changing the two
    # functions exercised by Fixture; do not rewrite the historical golden file.
    module.native.build_bundle=legacy().build_bundle
