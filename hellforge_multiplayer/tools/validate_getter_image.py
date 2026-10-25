"""Execute the native-emitted getter in synthetic RAM and verify Windows unwind."""
import argparse,copy,ctypes as c,io,json,struct,unittest
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import native_getter_image as native
from native_property_library import Library,GetterAddresses,Addresses,Image
from generate_getter_template import render,HEADER,REFERENCE
from build_unwind_offline import run,NAMES
from verify_native_unwind_source import replay

PROJECT=native.PROJECT


def validate(library,zig):
    blob,facts=render();native.require(HEADER.read_bytes()==blob,'Getter template mismatch')
    source=replay(native.profile(),native.ROOT/'evidence/existing-code-evidence-25480438')
    p=native.load_fixture();legacy=p.native.build;contexts=[];code=native.build(**p.params());base=p.params()['code_address']
    counts={'accepted':0,'rejected':0};lib=Library(library)
    def build(source,**addresses):
        ref=native.with_unwind(legacy(source,**addresses))
        return lib.getter_candidate(addresses,ref)
    p.native.build=build
    original_run=p.Fixture.run
    def run_fixture(f,name):
        def record(uc,pc,size,data):
            if f.start<=pc<f.start+f.artifact['size_bytes']:
                stack=bytearray(f.read(p.RSP-128,256));struct.pack_into('<Q',stack,128,p.GAME+0x10100000)
                contexts.append(struct.pack('<IiI8Q',pc-f.start,uc.reg_read(p.reg('rsp'))-p.RSP,0,
                                            *(uc.reg_read(p.reg(n)) for n in NAMES))+stack)
        hook=None if f.original else f.uc.hook_add(p.UC_HOOK_CODE,record)
        try:return original_run(f,name)
        finally:
            if hook is not None:f.uc.hook_del(hook)
    p.Fixture.run=run_fixture
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(p.GetterTests))
    native.require(result.wasSuccessful(),stream.getvalue())
    # Compare whole images and rejected address domains, not just opcodes.
    cases=[REFERENCE]
    for field in REFERENCE:
        for value in (0,1,15,16,(1<<47)-16,1<<47,(1<<64)-1):cases.append({**REFERENCE,field:value})
    for field in ('roster_address','storage_address'):
        for shift in (0x1000,0x100000000,0x700000000000):cases.append({**REFERENCE,field:REFERENCE[field]+shift})
    for off,n in ((0,388),(354,34)):
        for delta in (0,n-1):cases.append({**REFERENCE,'reject_address':REFERENCE['code_address']+off+delta})
    for delta in (-(1<<31)-1,-(1<<31),(1<<31)-1,1<<31):
        cases.append({**REFERENCE,'reject_address':REFERENCE['code_address']+354+delta})
    for target,after in ((0x3483C20,26),(0x3326468,33)):
        for edge in (REFERENCE['game_base']+target-after+(1<<31),REFERENCE['game_base']+target-after-((1<<31)-1)):
            for delta in (-16,0,16):
                address=(edge&~15)+delta;cases.append({**REFERENCE,'code_address':address,'reject_address':address+0x10000})
    for a in cases:
        try:expected=native.build(**a)['image']
        except (ValueError,OverflowError):expected=None
        out=Image();c.memset(c.byref(out),0xA5,c.sizeof(out));rc=lib.getter(GetterAddresses(**a),out)
        if expected is None:
            native.require(rc!=0 and bytes(out)==bytes(c.sizeof(out)),'Invalid getter accepted/partly emitted');counts['rejected']+=1
        else:
            native.require(rc==0 and bytes(out.data[:out.bytes])==expected,'Getter relocation mismatch');counts['accepted']+=1
    for a,out in ((None,Image()),(GetterAddresses(**REFERENCE),None)):
        native.require(lib.getter(a,out)==1 and (out is None or bytes(out)==bytes(c.sizeof(out))),'Invalid getter API accepted')
    a=Addresses();image=Image();checks=c.c_uint32()
    native.require(lib.prepare(3,a,image,checks)==0,'Getter prepare lifecycle failed')
    vals=dict(game_base=a.game_base,code_address=a.code_address,roster_address=a.roster_address,storage_address=a.property_address,reject_address=a.reject_address)
    native.require(bytes(image.data[:image.bytes])==native.build(**vals)['image'],'Prepared getter differs')
    # Source guards must reject changed identity and original language handlers.
    bad=copy.deepcopy(code['candidate']);bad['source_sha256']='0'*64
    try:native.with_unwind(bad)
    except ValueError:pass
    else:raise AssertionError('Changed source accepted')
    data=copy.deepcopy(native.profile());frag=data['functions']['getter']['fragments'][0]
    frag['unwind_hex']='09'+frag['unwind_hex'][2:]
    try:native.source.audit(data,schema=data['schema'],names=('getter',))
    except ValueError:pass
    else:raise AssertionError('Original language handler discarded')
    # Deliberately corrupt only the RBX saved-slot offset in a negative control.
    negative=bytearray(next(row for row in contexts if struct.unpack_from('<I',row)[0]>=20 and struct.unpack_from('<Q',row,12)[0]!=p.SEEDS['rbx']))
    struct.pack_into('<I',negative,8,1);bad_image=bytearray(code['image']);bad_image[code['unwind_offset']+18]=5
    expected=struct.pack('<9Q',*(p.SEEDS[n] for n in NAMES),p.GAME+0x10100000)
    def variant(image,rows):return struct.pack('<4I',len(image),code['candidate']['size_bytes'],code['table_offset'],len(rows))+image+expected+b''.join(rows)
    build_dir=PROJECT/'build';fixture=build_dir/'getter-unwind-contexts.bin'
    fixture.write_bytes(b'EPUWDV1\0'+struct.pack('<I',2)+variant(bad_image,[negative])+variant(code['image'],contexts))
    exe=build_dir/'native_getter_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',PROJECT/'tests/native_producer_unwind_test.c','-o',exe])
    windows=json.loads(run([exe,fixture]))
    paths=('native-getter.lock.json','tools/native_getter_image.py','tools/generate_getter_template.py','tools/validate_getter_image.py',
           'tools/native_unwind_source.py','tools/verify_native_unwind_source.py','tools/native_property_library.py',
           'mod/src/ep_getter_image.h','mod/src/ep_getter_image.cpp','mod/src/ep_getter_template.h',
           'mod/src/ep_session_code.h','mod/src/ep_session_code.cpp','tests/property_image_dll.cpp','tests/native_producer_unwind_test.c')
    receipt=dict(schema='hellforge_native_getter_validation_v1',verified_at_utc=datetime.now(timezone.utc).isoformat(),passed=True,
                 source_replay=source,**counts,api_contract_checks=2,source_guard_checks=2,owner_checks=checks.value,
                 functional_tests=result.testsRun,functional_runs=len(p.RUNS),windows_unwind_contexts=windows['windows_unwind_contexts'],
                 functional_run_types=dict(Counter(('original_' if r.get('original') else '')+r['component'] for r in p.RUNS)),
                 injected_metadata_faults_rejected=windows['legacy_rejection_failures_reproduced'],**facts,
                 source_sha256={path:native.sha((PROJECT/path).read_bytes()) for path in paths},
                 legacy_source_sha256={native.profile()['fixture_path']:native.profile()['fixture_sha256']},
                 artifacts={path.name:dict(bytes=path.stat().st_size,sha256=native.sha(path.read_bytes())) for path in (fixture,exe,lib.path)},
                 game_access=False,native_execution_of_game_bodies=False,runtime_verified=False,multiplayer_verified=False)
    (PROJECT/'evidence/native-getter-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return {key:receipt[key] for key in ('passed','accepted','rejected','functional_tests','functional_runs','windows_unwind_contexts','owner_checks','game_access')}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--library',type=Path,required=True);parser.add_argument('--zig',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(validate(args.library,args.zig.resolve())))
