"""Four pinned insertion paths with native mover extents and two unwind ranges."""
import importlib.util,json,struct
import native_producer_unwind as common
import native_unwind_source as source
import native_mover_image as mover
ROOT,PROJECT=common.ROOT,common.PROJECT
require,sha=common.require,common.sha
KINDS=('dense_legacy','append_legacy','append_registered','dense_registered')
LOCK=PROJECT/'native-insert.lock.json'
LOCK_SHA256='f33a753bfad144b45e6e4c6cc64bae9a53347f17034c1e932cae7ec29a27ec40'
MOVER_BYTES=len(mover.build(game_base=0x180000000,code_address=0x190000000,roster_address=0x200000000,
                          storage_address=0x210000000,reject_address=0x190010000)['image'])

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def profile():
    raw=LOCK.read_bytes();require(sha(raw)==LOCK_SHA256,'Insertion source lock changed');data=json.loads(raw)
    source.audit(data,schema='hellforge_captured_insert_unwind_v1',names=KINDS);return data

def legacy():
    pins=json.loads((PROJECT/'native-storage.lock.json').read_bytes())
    for path,expected in pins['legacy_source_sha256'].items():require(sha((ROOT/path).read_bytes())==expected,'Changed pinned source: '+path)
    return load('pinned_insert',ROOT/'eight_player_candidate_20260927/Native/roster_insert.py')

def with_unwind(candidate):
    data=profile();kind=candidate['kind'];fn=data['functions'][kind];base=candidate['code_address']
    require(candidate['source_sha256']==fn['code_sha256'] and candidate['evidence_sha256']==fn['evidence_sha256'],'Changed insertion identity')
    code=bytes.fromhex(candidate['code_hex']);require(sha(code)==candidate['code_sha256'],'Changed insertion code')
    body=candidate['body_address']-base;require(body==144,'Changed insertion preflight size')
    unwind=bytes.fromhex(fn['fragments'][0]['unwind_hex'])
    original=legacy().load_sources(ROOT/fn['evidence_path'])[kind]
    require(code[body:body+unwind[1]]==original[:unwind[1]],'Changed insertion prologue')
    leaf=(len(code)+3)&~3;uw=leaf+4;table=uw+len(unwind)
    image=code+bytes(leaf-len(code))+b'\x01\0\0\0'+unwind+struct.pack('<6I',0,body,leaf,body,len(code),uw)
    regions=[dict(r) for r in candidate['known_regions']]
    regions[0]['size_bytes']=len(image)
    for r in regions:
        if r['name']=='mover code':r['size_bytes']=MOVER_BYTES
    regions.append(dict(name='original mover',address=candidate['game_base']+0x60C410,size_bytes=430))
    old=legacy()
    for i,a in enumerate(regions):
        old.pointer(a['address'],a['size_bytes'],1,a['name'])
        for b in regions[i+1:]:require(not old.overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),'Complete insertion/mover image overlap')
    result={**candidate,'known_regions':regions,'status':'offline_native_insert_with_unwind','unwind_registered':False,
            'mover_image_bytes':MOVER_BYTES,'runtime_verified':False}
    return dict(candidate=result,image=image,unwind_offset=uw,table_offset=table,function_count=2)

def build(**addresses):
    old=legacy();fn=profile()['functions'][addresses['kind']]
    return with_unwind(old.build(old.load_sources(ROOT/fn['evidence_path'])[addresses['kind']],**addresses))

def load_fixture():
    data=profile();p=ROOT/data['fixture_path'];require(sha(p.read_bytes())==data['fixture_sha256'],'Changed insertion fixture')
    m=load('hellforge_insert_fixture',p)
    require(m.unicorn.__version__=='2.1.4' and m.capstone.__version__=='5.0.7','Wrong emulator/decoder');return m

def emitter(library):
    def emit(source,**addresses):
        require(type(source) is bytes and sha(source)==profile()['functions'][addresses['kind']]['code_sha256'],'Changed insertion input')
        return library.insert_candidate(addresses,build(**addresses))
    return emit

def bind_fixture(module,library):
    module.native.build=emitter(library)
    mover.bind_insertion_fixture(module,library)
