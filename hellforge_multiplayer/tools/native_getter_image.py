"""Pinned eight-slot network-index getter with its captured unwind contract."""
import importlib.util
import json
import struct
import native_producer_unwind as common
import native_unwind_source as source

ROOT,PROJECT=common.ROOT,common.PROJECT
require,sha=common.require,common.sha
LOCK=PROJECT/'native-getter.lock.json'
LOCK_SHA256='2ec11c0046408233a263c86d91e84309b153458d6f3863b38a5894adb75b19d9'
PROLOGUE=bytes.fromhex('48895c240848896c2410488974241848897c2420')
UNWIND=bytes.fromhex('01140800147404000f6403000a54020005340100')


def profile():
    raw=LOCK.read_bytes();require(sha(raw)==LOCK_SHA256,'Getter source lock changed')
    data=json.loads(raw);source.audit(data,schema='hellforge_captured_getter_unwind_v1',names=('getter',))
    require(data['functions']['getter']['fragments'][0]['unwind_hex']==UNWIND.hex(),'Changed getter saves')
    return data


def original(**addresses):
    lock=json.loads((PROJECT/'native-storage.lock.json').read_bytes())
    for rel,expected in lock['legacy_source_sha256'].items():
        require(sha((ROOT/rel).read_bytes())==expected,'Changed pinned source: '+rel)
    path=ROOT/'eight_player_candidate_20260927/Native/roster_getter.py'
    spec=importlib.util.spec_from_file_location('pinned_hellforge_getter',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.build(module.load_source(ROOT/profile()['functions']['getter']['evidence_path']),**addresses)


def with_unwind(candidate):
    data=profile();function=data['functions']['getter'];base=candidate['entry_address']
    require(candidate['source_sha256']==function['code_sha256'] and candidate['evidence_sha256']==function['evidence_sha256'] and
            candidate['target_profile']['build']==data['build'],'Getter code/source binding changed')
    code=bytes.fromhex(candidate['code_hex'])
    require(sha(code)==candidate['code_sha256'] and code.startswith(PROLOGUE),'Getter prologue changed')
    offset=(len(code)+3)&~3;table=offset+len(UNWIND)
    image=code+bytes(offset-len(code))+UNWIND+struct.pack('<III',0,len(code),offset)
    require(base+len(image)<=1<<47,'Getter image outside canonical range')
    for region in candidate['known_regions'][1:]:
        a,n=region['address'],region['size_bytes']
        require(base>=a+n or a>=base+len(image),'Getter metadata overlaps referenced data')
    result=dict(candidate)
    result.update(status='offline_native_getter_with_unwind',unwind_registered=False,original_unwind_source={'snapshot_sha256':LOCK_SHA256,'captured_fragments':1,'captured_language_handlers':False,'runtime_table_verified':False})
    return dict(candidate=result,image=image,unwind_offset=offset,table_offset=table,function_count=1)


def build(**addresses):
    return with_unwind(original(**addresses))


def load_fixture():
    data=profile();path=ROOT/data['fixture_path'];require(sha(path.read_bytes())==data['fixture_sha256'],'Changed getter fixture')
    spec=importlib.util.spec_from_file_location('hellforge_getter_fixture',path)
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    require(fixture.unicorn.__version__=='2.1.4' and fixture.capstone.__version__=='5.0.7','Wrong emulator/decoder')
    return fixture
