"""Exercise C++ classification and Windows unwind; helper bodies remain contract stubs."""
import argparse,copy,ctypes as c,io,json,struct,unittest
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import native_classify_image as native
from native_property_library import Library,GetterAddresses,ClassifyImage as Image
from generate_classify_templates import render,HEADER,REFERENCE
from build_unwind_offline import run,NAMES
from verify_native_unwind_source import replay
PROJECT=native.PROJECT

def validate(library,zig):
    blob,facts=render();native.require(HEADER.read_bytes()==blob,'Classification template mismatch')
    replayed=replay(native.profile(),native.ROOT/'evidence/existing-code-evidence-25480438')
    p=native.load_fixture();lib=Library(library);native.bind_fixture(p,lib)
    contexts={k:{} for k in native.KINDS};observed=Counter();original_run=p.Fixture.run
    def run_fixture(f,name,entry=None):
        def record(uc,pc,size,data):
            if f.start<=pc<f.start+f.artifact['size_bytes']:
                stack=bytearray(f.read(p.RSP-128,256));struct.pack_into('<Q',stack,128,p.GAME+0x10100000)
                row=struct.pack('<IiI8Q',pc-f.start,uc.reg_read(p.reg('rsp'))-p.RSP,0,*(uc.reg_read(p.reg(n)) for n in NAMES))+stack
                contexts[f.kind][row]=None;observed[f.kind]+=1
        hook=None if f.original else f.uc.hook_add(p.UC_HOOK_CODE,record)
        try:return original_run(f,name,entry)
        finally:
            if hook is not None:f.uc.hook_del(hook)
    p.Fixture.run=run_fixture
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromTestCase(p.ClassifyTests))
    native.require(result.wasSuccessful(),stream.getvalue())
    functional_runs=list(p.RUNS)
    kinds={};api_checks=source_checks=0;artifacts=[lib.path]
    exe=PROJECT/'build/native_classify_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-DEP_STACK_PREFLIGHT=1','-DEP_CONTEXT_LIMIT=200000u','-O1','-Wall','-Werror',PROJECT/'tests/native_producer_unwind_test.c','-o',exe]);artifacts.append(exe)
    for number,kind in enumerate(native.KINDS,1):
        code=native.build(**p.params(kind));candidate=code['candidate'];cases=[REFERENCE]
        for field in REFERENCE:
            for value in (0,1,15,16,(1<<47)-16,1<<47,(1<<64)-1):cases.append({**REFERENCE,field:value})
        for field in ('roster_address','storage_address'):
            for shift in (0x1000,0x100000000,0x700000000000):cases.append({**REFERENCE,field:REFERENCE[field]+shift})
        ref=native.build(kind=kind,**REFERENCE)
        for delta in (0,ref['candidate']['size_bytes'],len(ref['image'])-1):cases.append({**REFERENCE,'reject_address':REFERENCE['code_address']+delta})
        for delta in (-(1<<31)-1,-(1<<31),(1<<31)-1,1<<31):
            for field in ('reject_address',):
                value=REFERENCE['code_address']+144+delta
                cases.append({**REFERENCE,field:value if field=='reject_address' else value&~15})
        for value in (0xE0,0xF0,REFERENCE['roster_address']+0x400):cases.append({**REFERENCE,'storage_address':value})
        accepted=rejected=0
        for a in cases:
            try:expected=native.build(kind=kind,**a)['image']
            except (ValueError,OverflowError):expected=None
            out=Image();c.memset(c.byref(out),0xA5,c.sizeof(out));rc=lib.classify(number,GetterAddresses(**a),out)
            if expected is None:
                native.require(rc!=0 and bytes(out)==bytes(c.sizeof(out)),'Invalid classification accepted/partly emitted: '+kind+str(a));rejected+=1
            else:
                native.require(rc==0 and bytes(out.data[:out.bytes])==expected,'Classification relocation differs: '+kind);accepted+=1
        for a,out in ((None,Image()),(GetterAddresses(**REFERENCE),None)):
            native.require(lib.classify(number,a,out)==1 and (out is None or bytes(out)==bytes(c.sizeof(out))),'Invalid classification API accepted');api_checks+=1
        a=GetterAddresses();out=Image();checks=c.c_uint32();rc=lib.classify_prepare(number,a,out,checks)
        native.require(rc==0,'Classification prepare failed at '+str(rc))
        values={name:getattr(a,name) for name in REFERENCE}
        native.require(bytes(out.data[:out.bytes])==native.build(kind=kind,**values)['image'],'Prepared classification differs')
        bad=copy.deepcopy(candidate);bad['source_sha256']='0'*64
        try:native.with_unwind(bad)
        except ValueError:source_checks+=1
        else:raise AssertionError('Changed classification source accepted')
        snapshot=copy.deepcopy(native.profile());frag=snapshot['functions'][kind]['fragments'][0];frag['unwind_hex']='09'+frag['unwind_hex'][2:]
        try:native.source.audit(snapshot,schema=snapshot['schema'],names=native.KINDS)
        except ValueError:source_checks+=1
        else:raise AssertionError('Original handler discarded')
        rows=list(contexts[kind]);negatives=[];bad=bytearray(code['image'])
        restore=bytes.fromhex('5f5e5b415941585a59')
        for reason,at in enumerate(code['rejection_offsets'],1):
            bad[at:at+15]=restore+b'\x41\xba'+struct.pack('<I',reason)
        probe=p.Fixture(kind);original_run(probe,'negative_path_selection')
        scratch=next(x for x in code['scratch_offsets'] if probe.start+x in probe.trace)
        patch=next(x for x in candidate['array_patches'] if x['emitted_address']==probe.start+scratch)
        scratch_end=scratch+len(bytes.fromhex(patch['replacement_hex']))-5
        bad[scratch:scratch+5]=b'\x55'+b'\x90'*4
        bad[scratch_end:scratch_end+5]=b'\x5d'+b'\x90'*4
        for params,pc in ((dict(t=0,d=0,p=0,ordinal=0),code['rejection_offsets'][1]+9),({},scratch+1)):
            f=p.Fixture(kind,**params);f.write(f.start,bytes(bad[:candidate['size_bytes']]))
            def record_old(uc,address,size,data):
                if address==f.start+pc:
                    stack=bytearray(f.read(p.RSP-128,256));struct.pack_into('<Q',stack,128,p.GAME+0x10100000)
                    negatives.append(struct.pack('<IiI8Q',pc,uc.reg_read(p.reg('rsp'))-p.RSP,1,*(uc.reg_read(p.reg(n)) for n in NAMES))+stack)
            hook=f.uc.hook_add(p.UC_HOOK_CODE,record_old)
            original_run(f,'reintroduced_stack_regression');f.uc.hook_del(hook)
        native.require(len(negatives)==2,'Reintroduced stack regression not reached')
        expected=struct.pack('<9Q',*(p.SEEDS[n] for n in NAMES),p.GAME+0x10100000)
        def variant(image,values):return struct.pack('<4I',len(image),candidate['size_bytes'],code['table_offset'],len(values))+image+expected+b''.join(values)
        path=PROJECT/('build/classify-'+kind+'-unwind-contexts.bin')
        path.write_bytes(b'EPUWDV1\0'+struct.pack('<I',2)+variant(bad,negatives)+variant(code['image'],rows));artifacts.append(path)
        windows=json.loads(run([exe,path]))
        kinds[kind]=dict(accepted=accepted,rejected=rejected,owner_checks=checks.value,
                         executed_instruction_contexts=observed[kind],windows_unwind_unique_contexts=windows['windows_unwind_contexts'],
                         reintroduced_stack_regressions_rejected=windows['legacy_rejection_failures_reproduced'])
    for number in (0,3,0xFFFFFFFF):
        out=Image();c.memset(c.byref(out),0xA5,c.sizeof(out));native.require(lib.classify(number,GetterAddresses(**REFERENCE),out)==1 and bytes(out)==bytes(c.sizeof(out)),'Invalid kind accepted');api_checks+=1
    paths=('native-classify.lock.json','tools/native_classify_image.py','tools/generate_classify_templates.py','tools/validate_classify_images.py',
           'tools/native_unwind_source.py','tools/verify_native_unwind_source.py','tools/native_property_library.py',
           'native-remove.lock.json','tools/native_remove_image.py','tools/native_insert_image.py','tools/native_mover_image.py',
           'mod/src/ep_classify_image.h','mod/src/ep_classify_image.cpp','mod/src/ep_classify_templates.h',
           'mod/src/ep_session_code.h','mod/src/ep_session_code.cpp','tests/property_image_dll.cpp','tests/native_producer_unwind_test.c')
    receipt=dict(schema='hellforge_native_classify_validation_v1',verified_at_utc=datetime.now(timezone.utc).isoformat(),passed=True,
                 source_replay=replayed,**facts,variant_checks=kinds,api_contract_checks=api_checks,source_guard_checks=source_checks,
                 functional_tests=result.testsRun,functional_runs=len(functional_runs),original_functional_runs=sum(r.get('original',False) for r in functional_runs),
                 functional_run_types=dict(Counter(('original_' if r.get('original') else '')+r.get('kind',r.get('component','other')) for r in functional_runs)),
                 source_sha256={path:native.sha((PROJECT/path).read_bytes()) for path in paths},
                 legacy_source_sha256={native.profile()['fixture_path']:native.profile()['fixture_sha256']},
                 artifacts={path.name:dict(bytes=path.stat().st_size,sha256=native.sha(path.read_bytes())) for path in artifacts},
                 game_access=False,temporary_helpers_are_contract_stubs=True,native_execution_of_game_bodies=False,common_writer_activation=False,production_quiescence_provider_bound=False,
                 runtime_verified=False,multiplayer_verified=False)
    for key in ('accepted','rejected','owner_checks','executed_instruction_contexts','windows_unwind_unique_contexts','reintroduced_stack_regressions_rejected'):
        receipt[key]=sum(row[key] for row in kinds.values())
    (PROJECT/'evidence/native-classify-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return {k:receipt[k] for k in ('passed','accepted','rejected','owner_checks','functional_tests','functional_runs','windows_unwind_unique_contexts','game_access')}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,required=True);p.add_argument('--zig',type=Path,required=True)
    args=p.parse_args();print(json.dumps(validate(args.library,args.zig.resolve())))
