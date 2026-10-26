"""Run saved registry/associated-ID instructions, C++ emitters and Windows unwind."""
import argparse,ctypes as c,io,json,struct,unittest
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import native_registry_image as native
from native_property_library import Library,RegistryAddresses,RegistryImage
from generate_registry_templates import render,HEADER,REFERENCE
from build_unwind_offline import run,NAMES
from verify_native_unwind_source import replay
PROJECT=native.PROJECT

def validate(library,zig):
    blob,facts=render();native.require(HEADER.read_bytes()==blob,'Registry template mismatch')
    replayed=replay(native.profile(),native.ROOT/'evidence/existing-code-evidence-25480438')
    p=native.load_fixture();lib=Library(library);native.bind_fixture(p,lib)
    contexts={k:{} for k in native.KINDS};observed=Counter();original_run=p.Fixture.run
    expected_pc=p.GAME+0x10500000
    def row(f,uc,pc,start,fail=0):
        stack=bytearray(f.read(p.RSP-128,256));struct.pack_into('<Q',stack,128,expected_pc)
        return struct.pack('<IiI8Q',pc-start,uc.reg_read(p.reg('rsp'))-p.RSP,fail,*(uc.reg_read(p.reg(n)) for n in NAMES))+stack
    def run_fixture(f,name,phase='root'):
        kind='update' if phase=='root' else 'association';key=native.KEYS[native.KINDS.index(kind)]
        start=f.functions[key]['code_address'];end=start+f.functions[key]['size_bytes']
        def record(uc,pc,size,data):
            if start<=pc<end:contexts[kind][row(f,uc,pc,start)]=None;observed[kind]+=1
        hook=None if f.original else f.uc.hook_add(p.UC_HOOK_CODE,record)
        try:return original_run(f,name,phase)
        finally:
            if hook is not None:f.uc.hook_del(hook)
    p.Fixture.run=run_fixture
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromTestCase(p.RegistryTests))
    native.require(result.wasSuccessful(),stream.getvalue());functional=list(p.RUNS)
    exe=PROJECT/'build/native_registry_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-DEP_REGISTRY=1','-DEP_CONTEXT_LIMIT=200000u','-O1','-Wall','-Werror',PROJECT/'tests/native_producer_unwind_test.c','-o',exe])
    arts=native.build(**p.params())['artifacts'];variants={};artifacts=[lib.path,exe];api_checks=0
    for number,kind in enumerate(native.KINDS,1):
        art=arts[kind];code=art['candidate'];bad=bytearray(art['image']);negatives=[]
        if kind=='update':
            original=native.legacy().build(p.SOURCES,**p.params())['functions'][native.KEYS[0]]
            bad[:code['size_bytes']]=bytes.fromhex(original['code_hex'])
            f=p.Fixture(global_s=p.S+0x1000);f.write(f.root_entry,bytes(bad[:code['size_bytes']]))
            target=art['rejection_offset']+art['rejection_bytes']+36
            def old_order(uc,pc,size,data):
                if pc==f.root_entry+target:negatives.append(row(f,uc,pc,f.root_entry,1))
            h=f.uc.hook_add(p.UC_HOOK_CODE,old_order);original_run(f,'legacy_rejection_order');f.uc.hook_del(h)
            native.require(len(negatives)==1,'Legacy rejection regression not exercised')
        else:
            # An intentionally omitted callee frame must fail; the valid image
            # keeps all original saved registers and entry/exit leaf ranges.
            body_uw=struct.unpack_from('<III',bad,art['table_offset']+12)[2]
            bad[body_uw:body_uw+4]=b'\x01\0\0\0'
            sample=next(r for r in contexts[kind] if struct.unpack_from('<i',r,4)[0]<0 and struct.unpack_from('<I',r,0)[0]>110)
            neg=bytearray(sample);struct.pack_into('<I',neg,8,1);negatives.append(bytes(neg))
        expected=struct.pack('<9Q',*(p.SEEDS[n] for n in NAMES),expected_pc)
        def variant(image,rows):return struct.pack('<4I',len(image),code['size_bytes'],art['table_offset'],len(rows))+image+expected+b''.join(rows)
        path=PROJECT/('build/registry-'+kind+'-unwind-contexts.bin')
        path.write_bytes(b'EPUWDV1\0'+struct.pack('<I',2)+variant(bad,negatives)+variant(art['image'],list(contexts[kind])));artifacts.append(path)
        windows=json.loads(run([exe,path]));variants[kind]={**facts[kind],**windows,'executed_instruction_contexts':observed[kind]}
        owner_checks=c.c_uint32();rc=lib.registry_prepare(number,owner_checks)
        native.require(rc==0,'Registry ownership/metadata test failed at '+str(rc));variants[kind]['owner_checks']=owner_checks.value
        baseline={k:v for k,v in REFERENCE.items() if k!='helper_reject_address'}
        if number==2:baseline.update(code_address=REFERENCE['helper_code_address'],helper_code_address=0,reject_address=REFERENCE['helper_reject_address'])
        bad_bindings=[]
        for field in ('game_base','code_address','roster_address','storage_address','reject_address'):
            for value in (0,1,(1<<47),(1<<64)-1):bad_bindings.append({**baseline,field:value})
        for field in ('code_address','roster_address','storage_address'):
            bad_bindings.append({**baseline,field:baseline[field]+1})
        for field in ('roster_address','storage_address','reject_address'):
            bad_bindings.append({**baseline,field:baseline['code_address']})
        if number==1:bad_bindings+=[{**baseline,'helper_code_address':v} for v in (0,1,baseline['code_address'],baseline['storage_address'])]
        for a in bad_bindings:
            out=RegistryImage();c.memset(c.byref(out),0xA5,c.sizeof(out))
            native.require(lib.registry(number,RegistryAddresses(**a),out)!=0 and bytes(out)==bytes(c.sizeof(out)),'Registry invalid placement accepted: '+str(a));api_checks+=1
        for a,out in ((None,RegistryImage()),(RegistryAddresses(**baseline),None)):
            native.require(lib.registry(number,a,out)==1 and (out is None or bytes(out)==bytes(c.sizeof(out))),'Invalid registry API accepted');api_checks+=1
    for number in (0,3,0xFFFFFFFF):
        out=RegistryImage();c.memset(c.byref(out),0xA5,c.sizeof(out))
        native.require(lib.registry(number,RegistryAddresses(),out)==1 and bytes(out)==bytes(c.sizeof(out)),'Invalid registry kind accepted');api_checks+=1
    paths=['native-registry.lock.json','tools/native_registry_image.py','tools/generate_registry_templates.py','tools/validate_registry_images.py',
        'tools/native_property_library.py','tools/native_unwind_source.py','tools/verify_native_unwind_source.py',
        'mod/src/ep_registry_image.h','mod/src/ep_registry_image.cpp','mod/src/ep_registry_templates.h',
        'mod/src/ep_session_code.h','mod/src/ep_session_code.cpp','tests/property_image_dll.cpp','tests/native_producer_unwind_test.c']
    receipt=dict(schema='hellforge_native_registry_validation_v1',passed=True,verified_at_utc=datetime.now(timezone.utc).isoformat(),
        source_replay=replayed,variants=variants,api_contract_checks=api_checks,functional_tests=result.testsRun,functional_runs=len(functional),
        original_functional_runs=sum(r['original'] for r in functional),functional_run_types=dict(Counter(('original_' if r['original'] else '')+r['component'] for r in functional)),
        windows_unwind_contexts=sum(r['windows_unwind_contexts'] for r in variants.values()),
        source_sha256={path:native.sha((PROJECT/path).read_bytes()) for path in paths},
        legacy_source_sha256={**native.profile()['legacy_source_sha256'],native.profile()['fixture_path']:native.profile()['fixture_sha256']},
        artifacts={path.name:dict(bytes=path.stat().st_size,sha256=native.sha(path.read_bytes())) for path in artifacts},
        game_access=False,native_execution_of_game_bodies=False,runtime_verified=False,multiplayer_verified=False,
        other_tag_callbacks_are_contract_stubs=True,late_rejection_rolls_back_prior_effects=False)
    (PROJECT/'evidence/native-registry-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return {k:receipt[k] for k in ('passed','functional_tests','functional_runs','api_contract_checks','windows_unwind_contexts','game_access')}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--library',type=Path,required=True);parser.add_argument('--zig',type=Path,required=True)
    a=parser.parse_args();print(json.dumps(validate(a.library.resolve(),a.zig.resolve())))
