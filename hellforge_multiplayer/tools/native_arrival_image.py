"""Saved state-update clone with its original GS handler and fixed frame.

The historical arrival filename is not evidence of character creation. This
module reads repository evidence only; it never discovers or accesses a game.
"""
import json,struct
import native_remove_image as common
ROOT,PROJECT=common.ROOT,common.PROJECT
load,require,sha,source=common.load,common.require,common.sha,common.source
LOCK=PROJECT/'native-arrival.lock.json'
LOCK_SHA256='1d31cbf5676a860f47203246cb0266bfeb8fee213476cd138d173fcb7d89f275'

def profile():
    raw=LOCK.read_bytes();require(sha(raw)==LOCK_SHA256,'State-update source lock changed');data=json.loads(raw)
    source.audit(data,schema='hellforge_captured_arrival_gs_unwind_v1',names=('arrival',),gs_functions=('arrival',))
    return data

def legacy():
    for path,digest in profile()['legacy_source_sha256'].items():
        require(sha((ROOT/path).read_bytes())==digest,'State-update dependency changed: '+path)
    return load('pinned_arrival',ROOT/'eight_player_candidate_20260927/Native/roster_arrival.py')

def with_unwind(candidate):
    fn=profile()['functions']['arrival'];base=candidate['code_address']
    require(candidate['source_sha256']==fn['code_sha256'] and candidate['evidence_sha256']==fn['evidence_sha256'],'State-update source identity changed')
    code=bytearray.fromhex(candidate['code_hex']);require(sha(code)==candidate['code_sha256'],'State-update code changed')
    body=candidate['body_address']-base;require(body==496 and len(code)==1917,'State-update layout changed')
    restore=bytes.fromhex('5f5e5b415941585a59');rejections=[]
    for reason in range(1,11):
        mov=b'\x41\xba'+struct.pack('<I',reason);pattern=restore+mov+b'\xe9'
        require(code.count(pattern)==1,'State-update rejection changed');at=code.index(pattern)
        # Retain recognizable Windows epilogues at every rejection instruction.
        code[at:at+len(restore)+len(mov)]=mov+restore;rejections.append(at)
    original=bytes.fromhex(fn['fragments'][0]['unwind_hex'])
    require(original.hex()=='19310c00226807001d7415001d6414001d5413001d3412001df216e0a044100260000000','Unknown state-update GS format')
    # The prologue's sole RIP operand is relocated; its operation boundaries,
    # frame (128 + pushed R14), cookie at frame+96, and home saves stay intact.
    old=legacy();raw=old.load_source(ROOT/fn['evidence_path']);mapping=candidate['instruction_address_map']
    for offset in (0,5,10,15,20,22,29,34,41,44,49):
        require(mapping[hex(old.ENTRY+offset)]-base==body+offset,'Moved GS prologue operation')
    require(code[body:body+37]==raw[:37] and code[body+41:body+49]==raw[41:49],'Changed GS frame/cookie setup')
    code+=b'\x90'*((-len(code))%16);handler=len(code)
    code+=b'\xe9'+old.rel32(base+handler+5,candidate['game_base']+0x21044a0)
    image=code+bytes((-len(code))%4);prefix=len(image);image+=common.PREFLIGHT_UNWIND
    uw=len(image);image+=original[:28]+struct.pack('<II',handler,96)
    leaf=len(image);image+=b'\x01\0\0\0';table=len(image)
    rows=((0,body,prefix),(body,handler,uw),(handler,len(code),leaf))
    for row in rows:image+=struct.pack('<III',*row)
    regions=[dict(r) for r in candidate['known_regions']];regions[0]['size_bytes']=len(image)
    for i,a in enumerate(regions):
        old.pointer(a['address'],a['size_bytes'],1,a['name']);require(a['address']>=0x10000,'State-update address below user range')
        for b in regions[i+1:]:require(not old.overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),'Complete GS image overlap')
    updated={**candidate,'code_hex':code.hex(),'code_sha256':sha(code),'size_bytes':len(code),'known_regions':regions,
        'status':'offline_state_update_with_original_gs_handler','runtime_verified':False,'unwind_registered':False}
    return dict(candidate=updated,image=bytes(image),unwind_offset=uw,table_offset=table,function_count=3,
        handler_offset=handler,handler_target=candidate['game_base']+0x21044a0,cookie_offset=96,rejection_offsets=rejections)

def build(**addresses):
    old=legacy();fn=profile()['functions']['arrival']
    return with_unwind(old.build(old.load_source(ROOT/fn['evidence_path']),**addresses))

def load_fixture():
    data=profile();path=ROOT/data['fixture_path'];require(sha(path.read_bytes())==data['fixture_sha256'],'State-update fixture changed')
    m=load('hellforge_arrival_fixture',path)
    require(m.unicorn.__version__=='2.1.4' and m.capstone.__version__=='5.0.7','Wrong emulator/decoder');return m

def bind_fixture(module,library=None):
    def emit(body,**addresses):
        require(type(body) is bytes and sha(body)==profile()['functions']['arrival']['code_sha256'],'State-update input changed')
        ref=build(**addresses)
        full=library.arrival_candidate(addresses,ref) if library else ref['candidate']
        # The frozen fixture validates the root's CFG, not the separate GS
        # trampoline. C++ image equality above includes that trampoline and all
        # metadata; the dedicated GS test executes it in synthetic memory.
        root=bytes.fromhex(full['code_hex'])[:1917]
        return {**full,'code_hex':root.hex(),'code_sha256':sha(root),'size_bytes':len(root)}
    module.native.build=emit
    module.native.build_bundle=legacy().build_bundle
