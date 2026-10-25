"""Removal images with canonical reject epilogues and constant body stack depth."""
import json,struct
import native_insert_image as common
ROOT,PROJECT=common.ROOT,common.PROJECT
load,require,sha,source=common.load,common.require,common.sha,common.source
KINDS=('legacy','registered')
LOCK=PROJECT/'native-remove.lock.json'
LOCK_SHA256='0d5142914bfdafe1a9e55ef4c4d5afd86287851b2d2dca2869ae1ca757045d02'
# Volatile argument pushes count as eight-byte allocations; only nonvolatiles
# need register restoration. Each operation becomes valid at its instruction end.
PREFLIGHT_UNWIND=bytes.fromhex('0109070009700860073006020402020201020000')
MOVER_BYTES=common.MOVER_BYTES

def profile():
    raw=LOCK.read_bytes();require(sha(raw)==LOCK_SHA256,'Removal source lock changed');data=json.loads(raw)
    source.audit(data,schema='hellforge_captured_remove_unwind_v1',names=KINDS);return data

def legacy():
    common.legacy()  # Check the complete inherited source set before loading.
    return load('pinned_remove',ROOT/'eight_player_candidate_20260927/Native/roster_remove.py')

def with_unwind(candidate):
    data=profile();kind=candidate['kind'];fn=data['functions'][kind];old=legacy()
    require(candidate['source_sha256']==fn['code_sha256'] and candidate['evidence_sha256']==fn['evidence_sha256'],'Changed removal identity')
    code=bytearray.fromhex(candidate['code_hex']);require(sha(code)==candidate['code_sha256'],'Changed removal code')
    body=candidate['body_address']-candidate['code_address'];require(body==448,'Changed removal preflight size')
    original=old.load_sources(ROOT/fn['evidence_path'])[kind];unwind=bytes.fromhex(fn['fragments'][0]['unwind_hex'])
    require(code[body:body+unwind[1]]==original[:unwind[1]],'Changed removal prologue')
    restore=bytes.fromhex('5f5e5b415941585a59');rejections=[]
    for reason in range(1,9):
        mov=b'\x41\xba'+struct.pack('<I',reason);pattern=restore+mov+b'\xe9'
        require(code.count(pattern)==1,'Changed removal rejection layout');at=code.index(pattern)
        code[at:at+len(restore)+len(mov)]=mov+restore;rejections.append(at)
    # Both original bodies have entry RSP-0x28 at calls. RSP+0x38 is the
    # caller-provided second home slot; outside the nested callee's shadow area
    # and the legacy saved RBX at RSP+0x30. No additional stack adjustment needed.
    for before,after in [('504883ec28','4889442438'),('4883c42858','488b442438')]:
        a,b=bytes.fromhex(before),bytes.fromhex(after);require(code.count(a)==1,'Changed pending repair stack');code[code.index(a):code.index(a)+len(a)]=b
    prefix=(len(code)+3)&~3;uw=prefix+len(PREFLIGHT_UNWIND);table=uw+len(unwind)
    image=bytes(code)+bytes(prefix-len(code))+PREFLIGHT_UNWIND+unwind+struct.pack('<6I',0,body,prefix,body,len(code),uw)
    regions=[dict(r) for r in candidate['known_regions']];regions[0]['size_bytes']=len(image)
    for r in regions:
        if r['name']=='mover code':r['size_bytes']=MOVER_BYTES
    regions.append(dict(name='original mover',address=candidate['game_base']+0x60C410,size_bytes=430))
    for i,a in enumerate(regions):
        old.pointer(a['address'],a['size_bytes'],1,a['name'])
        for b in regions[i+1:]:require(not old.overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),'Complete removal/mover image overlap')
    result={**candidate,'known_regions':regions,'code_hex':code.hex(),'code_sha256':sha(code),
            'status':'offline_native_remove_with_unwind','unwind_registered':False,'runtime_verified':False,'mover_image_bytes':MOVER_BYTES}
    return dict(candidate=result,image=image,unwind_offset=uw,table_offset=table,function_count=2,prefix_unwind_offset=prefix,rejection_offsets=rejections)

def build(**addresses):
    old=legacy();fn=profile()['functions'][addresses['kind']]
    return with_unwind(old.build(old.load_sources(ROOT/fn['evidence_path'])[addresses['kind']],**addresses))

def load_fixture():
    d=profile();path=ROOT/d['fixture_path'];require(sha(path.read_bytes())==d['fixture_sha256'],'Removal fixture changed')
    m=load('hellforge_remove_fixture',path)
    require(m.unicorn.__version__=='2.1.4' and m.capstone.__version__=='5.0.7','Wrong emulator/decoder');return m

def emitter(library):
    def emit(body,**addresses):
        require(type(body) is bytes and sha(body)==profile()['functions'][addresses['kind']]['code_sha256'],'Changed removal input')
        ref=build(**addresses)
        return library.remove_candidate(addresses,ref) if library else ref['candidate']
    return emit

def bind_fixture(module,library):
    module.native.build=emitter(library)
    module.move.build=common.mover.emitter(library)
    module.insert.build=common.emitter(library)
