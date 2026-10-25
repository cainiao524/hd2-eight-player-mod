"""Validate C++ mover semantics in Unicorn and synthetic contexts in Windows."""
import argparse,copy,ctypes as c,io,json,struct,unittest
from datetime import datetime,timezone
from pathlib import Path
import native_mover_image as native
from native_property_library import Library,GetterAddresses,Addresses,Image
from generate_mover_template import render,HEADER,REFERENCE
from build_unwind_offline import run,NAMES
from verify_native_unwind_source import replay
from capstone.x86_const import X86_OP_MEM
PROJECT=native.PROJECT

def validate(library,zig):
    blob,facts=render();native.require(HEADER.read_bytes()==blob,'Mover template mismatch')
    source=replay(native.profile(),native.ROOT/'evidence/existing-code-evidence-25480438')
    p=native.load_fixture();contexts=[];code=native.build(**p.parameters());lib=Library(library)
    p.native.build=native.emitter(lib)
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
    # Test 06 asserts the superseded trampoline layout; 09/10 use their own
    # legacy bundle emitter. New full-image integration lives in the engine suite.
    names=[n for n in unittest.defaultTestLoader.getTestCaseNames(p.MoveTests) if int(n[5:7]) in (1,2,3,4,5,7,8,11)]
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream).run(unittest.TestSuite(p.MoveTests(n) for n in names))
    native.require(result.wasSuccessful(),stream.getvalue())
    # Independent operand decoding verifies all 26 displacement changes and
    # every relocated branch; do not reuse the emitter's displacement table.
    candidate=code['candidate'];base=candidate['entry_address'];raw=bytes.fromhex(candidate['code_hex'])
    native.require(raw[96:118]==native.PROLOGUE,'Uniform prologue changed')
    mapping={int(k,16):v for k,v in candidate['instruction_address_map'].items()}
    decoded={i.address:i for i in p.decode(raw,base)};groups={'primary':0,'auxiliary':0,'property':0};branches=0
    for i in p.decode(p.BODY,p.ENTRY):
        if i.address<p.ENTRY+16:continue
        at=mapping[i.address];expected=bytearray(i.bytes)
        if i.address in (0x60C454,0x60C459,0x60C45E):
            native.require(raw[at-base:at-base+5]==b'\x90'*5,'Late save not removed');continue
        if i.address==0x60C54A:
            native.require(raw[at-base:at-base+10]==b'\x48\xbb'+struct.pack('<Q',p.ROSTER),'Map base not restored');at+=10
        if i.group(p.capstone.CS_GRP_JUMP):
            native.require(p.target(decoded[at])==mapping[p.target(i)],'Body branch changed');branches+=1;continue
        for op in i.operands:
            if op.type!=X86_OP_MEM:continue
            old=op.mem.disp
            name,delta=('primary',0x20) if 0x108<=old<=0x168 else ('auxiliary',0x1E0) if 0x2C8<=old<=0x2F8 else ('property',0x2C0) if 0x3A8<=old<=0x3B8 else (None,0)
            if name:
                groups[name]+=1;struct.pack_into('<i',expected,i.disp_offset,old+delta)
        native.require(bytes(decoded[at].bytes)==bytes(expected),'Unexpected mover instruction change')
    native.require(groups==dict(primary=14,auxiliary=8,property=4),'Changed displacement coverage')
    cases=[REFERENCE]
    for field in REFERENCE:
        for value in (0,1,15,16,(1<<47)-16,1<<47,(1<<64)-1):cases.append({**REFERENCE,field:value})
    for field in ('roster_address','storage_address'):
        for shift in (0x1000,0x100000000,0x700000000000):cases.append({**REFERENCE,field:REFERENCE[field]+shift})
    for delta in (0,557,558,611):cases.append({**REFERENCE,'reject_address':REFERENCE['code_address']+delta})
    for end in (73,84,95):
        for delta in (-(1<<31)-1,-(1<<31),(1<<31)-1,1<<31):
            cases.append({**REFERENCE,'reject_address':REFERENCE['code_address']+end+delta})
    cases += [{**REFERENCE,'storage_address':v} for v in (0xE0,0xF0,REFERENCE['roster_address']+0x400)]
    counts={'accepted':0,'rejected':0}
    for a in cases:
        try:expected=native.build(**a)['image']
        except (ValueError,OverflowError):expected=None
        out=Image();c.memset(c.byref(out),0xA5,c.sizeof(out));rc=lib.mover(GetterAddresses(**a),out)
        if expected is None:
            native.require(rc!=0 and bytes(out)==bytes(c.sizeof(out)),'Invalid mover accepted/partly emitted');counts['rejected']+=1
        else:
            native.require(rc==0 and bytes(out.data[:out.bytes])==expected,'Mover relocation mismatch');counts['accepted']+=1
    for a,out in ((None,Image()),(GetterAddresses(**REFERENCE),None)):
        native.require(lib.mover(a,out)==1 and (out is None or bytes(out)==bytes(c.sizeof(out))),'Invalid mover API accepted')
    a=Addresses();image=Image();checks=c.c_uint32();prepared=lib.prepare(4,a,image,checks)
    native.require(prepared==0,'Mover prepare lifecycle failed at '+str(prepared))
    vals=dict(game_base=a.game_base,code_address=a.code_address,roster_address=a.roster_address,storage_address=a.property_address,reject_address=a.reject_address)
    native.require(bytes(image.data[:image.bytes])==native.build(**vals)['image'],'Prepared mover differs')
    data=copy.deepcopy(native.profile());frag=data['functions']['mover']['fragments'][0];frag['unwind_hex']='09'+frag['unwind_hex'][2:]
    try:native.common.source.audit(data,schema=data['schema'],names=('mover',))
    except ValueError:pass
    else:raise AssertionError('Original language handler discarded')
    negative=bytearray(next(row for row in contexts if struct.unpack_from('<I',row)[0]>=121 and struct.unpack_from('<Q',row,12)[0]!=p.SEEDS['rbx']))
    struct.pack_into('<I',negative,8,1);bad=bytearray(code['image']);bad[code['unwind_offset']+18]=6
    expected=struct.pack('<9Q',*(p.SEEDS[n] for n in NAMES),p.GAME+0x10100000)
    def variant(image,rows):return struct.pack('<4I',len(image),candidate['size_bytes'],code['table_offset'],len(rows))+image+expected+b''.join(rows)
    build=PROJECT/'build';fixture=build/'mover-unwind-contexts.bin'
    fixture.write_bytes(b'EPUWDV1\0'+struct.pack('<I',2)+variant(bad,[negative])+variant(code['image'],contexts))
    exe=build/'native_mover_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',PROJECT/'tests/native_producer_unwind_test.c','-o',exe])
    windows=json.loads(run([exe,fixture]))
    paths=('native-mover.lock.json','tools/native_mover_image.py','tools/generate_mover_template.py','tools/validate_mover_image.py',
           'tools/native_unwind_source.py','tools/native_getter_image.py','tools/verify_native_unwind_source.py','tools/native_property_library.py',
           'mod/src/ep_mover_image.h','mod/src/ep_mover_image.cpp','mod/src/ep_mover_template.h',
           'mod/src/ep_session_code.h','mod/src/ep_session_code.cpp','tests/property_image_dll.cpp','tests/native_producer_unwind_test.c')
    receipt=dict(schema='hellforge_native_mover_validation_v1',verified_at_utc=datetime.now(timezone.utc).isoformat(),passed=True,
                 source_replay=source,**counts,api_contract_checks=2,source_handler_guard_checks=1,owner_checks=checks.value,
                 functional_tests=result.testsRun,functional_runs=len(p.RUNS),original_functional_runs=sum(r['original'] for r in p.RUNS),
                 windows_unwind_contexts=windows['windows_unwind_contexts'],displacement_counts=groups,relocated_internal_branches=branches,
                 injected_metadata_faults_rejected=windows['legacy_rejection_failures_reproduced'],**facts,
                 source_sha256={path:native.sha((PROJECT/path).read_bytes()) for path in paths},
                 legacy_source_sha256={native.profile()['fixture_path']:native.profile()['fixture_sha256']},
                 artifacts={path.name:dict(bytes=path.stat().st_size,sha256=native.sha(path.read_bytes())) for path in (fixture,exe,lib.path)},
                 game_access=False,native_execution_of_game_bodies=False,runtime_verified=False,multiplayer_verified=False,
                 common_writer_activation=False,production_quiescence_provider_bound=False)
    (PROJECT/'evidence/native-mover-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return {key:receipt[key] for key in ('passed','accepted','rejected','functional_tests','functional_runs','windows_unwind_contexts','owner_checks','game_access')}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,required=True);p.add_argument('--zig',type=Path,required=True)
    args=p.parse_args();print(json.dumps(validate(args.library,args.zig.resolve())))
