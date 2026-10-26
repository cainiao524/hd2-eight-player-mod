"""Saved departure instructions and all thirteen original unwind fragments.

The pre-removal callbacks keep their original ordering. No game access and no
promise of rollback, quiescence, or named resources for player counts 5..8.
"""
import json,struct
import native_remove_image as common
import native_getter_image as getter
ROOT,PROJECT=common.ROOT,common.PROJECT
load,require,sha,source=common.load,common.require,common.sha,common.source
LOCK=PROJECT/'native-departure.lock.json'
LOCK_SHA256='68e0993431ff7f205746769d662a9409aa526421c20eb9b1cceaad209692c75b'
GETTER_BYTES=388

def profile():
    raw=LOCK.read_bytes();require(sha(raw)==LOCK_SHA256,'Departure source lock changed');data=json.loads(raw)
    source.audit(data,schema='hellforge_captured_departure_unwind_v1',names=('departure',));return data

def legacy():
    for path,digest in profile()['legacy_source_sha256'].items():
        require(sha((ROOT/path).read_bytes())==digest,'Departure dependency changed: '+path)
    return load('pinned_departure',ROOT/'eight_player_candidate_20260927/Native/roster_departure.py')

def with_unwind(candidate):
    fn=profile()['functions']['departure'];base=candidate['code_address']
    require(candidate['source_sha256']==fn['code_sha256'] and candidate['evidence_sha256']==fn['evidence_sha256'],'Departure source identity changed')
    code=bytearray.fromhex(candidate['code_hex']);require(sha(code)==candidate['code_sha256'],'Departure code changed')
    body=candidate['body_address']-base;require(body==544,'Departure guard changed')
    restore=bytes.fromhex('5f5e5b415941585a59');rejections=[]
    for reason in range(1,11):
        mov=b'\x41\xba'+struct.pack('<I',reason);pattern=restore+mov+b'\xe9'
        require(code.count(pattern)==1,'Departure rejection changed');at=code.index(pattern)
        code[at:at+len(restore)+len(mov)]=mov+restore;rejections.append(at)
    mapping=candidate['instruction_address_map'];image=bytearray(code)+bytes((-len(code))%4)
    prefix=len(image);image+=common.PREFLIGHT_UNWIND;rows=[(0,body,prefix)];parents={}
    for fragment in fn['fragments']:
        a,b,u=struct.unpack('<III',bytes.fromhex(fragment['runtime_function_hex']))
        begin=mapping[hex(a)]-base;end=len(code) if b==int(fn['end_exclusive'],16) else mapping[hex(b)]-base
        original=bytes.fromhex(fragment['unwind_hex']);ops=bytearray();slot=0
        def offset(value):
            result=mapping[hex(a+value)]-base-begin
            require(0<=result<=255,'Departure prologue exceeds unwind byte');return result
        while slot<original[2]:
            pc,opcode=original[4+2*slot:6+2*slot];op,info=opcode&15,opcode>>4;slot+=1
            pc=offset(pc)
            if op==0:ops+=bytes((pc,opcode))
            elif op==2:
                require(a==int(fn['entry'],16) and info==15,'Unexpected departure allocation')
                # The two prediction locals enlarge the fixed frame 128 -> 144.
                ops+=bytes((pc,1))+struct.pack('<H',0x90//8)
            elif op in (4,8):
                require(slot<original[2],'Truncated departure save')
                value=struct.unpack_from('<H',original,4+2*slot)[0];slot+=1
                require(op!=8 or info==6,'Unexpected departure XMM save')
                # Physical entry home slots remain unchanged; their offsets from
                # the enlarged frame grow along with the shifted local saves.
                ops+=bytes((pc,opcode))+struct.pack('<H',value+(2 if op==4 else 1))
            else:raise ValueError('Unexpected departure unwind operation')
        uw=bytearray((original[0],offset(original[1]),len(ops)//2,0))+ops
        uw+=bytes((-len(uw))%4)
        if original[0]==33:
            parent=struct.unpack('<III',original[-12:]);require(parent in parents,'Missing departure parent')
            uw+=struct.pack('<III',*parents[parent])
        row=(begin,end,len(image));rows.append(row);parents[(a,b,u)]=row;image+=uw
    require(len(rows)==14 and all(a<b and (i==0 or rows[i-1][1]==a) for i,(a,b,_) in enumerate(rows)),'Incomplete departure coverage')
    table=len(image)
    for row in rows:image+=struct.pack('<III',*row)
    old=legacy();regions=[dict(r) for r in candidate['known_regions']]
    for region in regions:
        if region['name']=='departure code':region['size_bytes']=len(image)
        if region['name']=='shared getter code':region['size_bytes']=GETTER_BYTES
        old.pointer(region['address'],region['size_bytes'],1,region['name'])
        require(region['address']>=0x10000,'Departure address below Windows user allocation range')
    for i,a in enumerate(regions):
        for b in regions[i+1:]:require(not old.overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),'Complete departure image overlap')
    updated={**candidate,'code_hex':code.hex(),'code_sha256':sha(code),'known_regions':regions,
             'status':'offline_departure_with_unwind','runtime_verified':False,'unwind_registered':False}
    return dict(candidate=updated,image=bytes(image),unwind_offset=prefix,table_offset=table,function_count=len(rows),rejection_offsets=rejections)

def build(**addresses):
    old=legacy();fn=profile()['functions']['departure']
    return with_unwind(old.build(old.load_source(ROOT/fn['evidence_path']),**addresses))

def load_fixture():
    d=profile();path=ROOT/d['fixture_path'];require(sha(path.read_bytes())==d['fixture_sha256'],'Departure fixture changed')
    m=load('hellforge_departure_fixture',path)
    require(m.unicorn.__version__=='2.1.4' and m.capstone.__version__=='5.0.7','Wrong emulator/decoder');return m

def bind_fixture(module,library=None):
    def emit(body,**addresses):
        require(type(body) is bytes and sha(body)==profile()['functions']['departure']['code_sha256'],'Departure input changed')
        ref=build(**addresses)
        return library.departure_candidate(addresses,ref) if library else ref['candidate']
    module.native.build=emit
    # Keep the old full-bundle golden assertion independent of the new image.
    module.native.build_bundle=legacy().build_bundle
