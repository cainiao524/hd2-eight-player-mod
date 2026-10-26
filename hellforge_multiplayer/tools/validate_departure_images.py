"""Validate saved departure semantics and wide Windows GPR/XMM6 unwinding."""
import argparse,ctypes as c,io,json,struct,unittest
from datetime import datetime,timezone
from pathlib import Path
import native_departure_image as native
from build_unwind_offline import run,NAMES
from verify_native_unwind_source import replay
from native_departure_library import Library,Addresses,Image
from generate_departure_template import render,HEADER,REFERENCE
PROJECT=native.PROJECT

def validate(library,zig):
    blob,facts=render();native.require(HEADER.read_bytes()==blob,'Departure template changed')
    lib=Library(library)
    replayed=replay(native.profile(),native.ROOT/'evidence/existing-code-evidence-25480438')
    p=native.load_fixture();native.bind_fixture(p,lib);art=native.build(**p.params());contexts={};original_run=p.Fixture.run
    expected_pc=p.GAME+0x10500000;expected_xmm=((0x0102030405060708+6)*(1+(1<<64))).to_bytes(16,'little')
    def row(f,uc,pc,fail=0):
        stack=bytearray(f.read(p.RSP-256,384));struct.pack_into('<Q',stack,256,expected_pc)
        return struct.pack('<IiI8Q',pc-f.start,uc.reg_read(p.reg('rsp'))-p.RSP,fail,*(uc.reg_read(p.reg(n)) for n in NAMES))+uc.reg_read(p.reg('xmm6')).to_bytes(16,'little')+stack
    def run_fixture(f,name,entry=None,component='departure'):
        def record(uc,pc,size,data):
            if f.start<=pc<f.start+f.artifact['size_bytes']:contexts[row(f,uc,pc)]=None
        h=None if f.original else f.uc.hook_add(p.UC_HOOK_CODE,record)
        try:return original_run(f,name,entry,component)
        finally:
            if h is not None:f.uc.hook_del(h)
    p.Fixture.run=run_fixture
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromTestCase(p.DepartureTests))
    native.require(result.wasSuccessful(),stream.getvalue());functional=list(p.RUNS)
    expected=struct.pack('<9Q',*(p.SEEDS[n] for n in NAMES),expected_pc)+expected_xmm
    def pack(image,rows):return struct.pack('<4I',len(image),art['candidate']['size_bytes'],art['table_offset'],len(rows))+image+expected+b''.join(rows)
    # The old rejection order restores the stack before setting R10D, so a PC
    # at that MOV is no longer recognized as an epilogue by Windows.
    bad=bytearray(art['image']);old=native.legacy().build(p.BODY,**p.params());bad[:old['size_bytes']]=bytes.fromhex(old['code_hex'])
    f=p.Fixture();f.write(f.game+0x3326468,p.u64(0x40000000));f.write(f.start,bytes(bad[:old['size_bytes']]))
    rejected=[];target=f.start+art['rejection_offsets'][0]+9
    def rejection(uc,pc,size,data):
        if pc==target:rejected.append(row(f,uc,pc,1))
    h=f.uc.hook_add(p.UC_HOOK_CODE,rejection);original_run(f,'negative_old_rejection');f.uc.hook_del(h)
    native.require(len(rejected)==1,'Missing old rejection control');variants=[pack(bytes(bad),rejected)]
    rows=[struct.unpack_from('<III',art['image'],art['table_offset']+12*i) for i in range(art['function_count'])]
    sample=next(r for r in contexts if rows[4][0]+art['image'][rows[4][2]+1]<=struct.unpack_from('<I',r)[0]<rows[4][1] and struct.unpack_from('<i',r,4)[0]==-168)
    negative=bytearray(sample);struct.pack_into('<I',negative,8,1)
    for index,opcode,wrong in ((1,1,16),(4,8,6)):
        bad=bytearray(art['image']);at=rows[index][2];slot=0;changed=False
        while slot<bad[at+2]:
            op=bad[at+5+slot*2]&15
            if op==opcode:struct.pack_into('<H',bad,at+6+slot*2,wrong);changed=True;break
            slot+=2 if op in (1,4,8) else 1
        native.require(changed,'Missing frame/XMM negative control');variants.append(pack(bytes(bad),[negative]))
    variants.append(pack(art['image'],list(contexts)))
    target=PROJECT/'build/departure-unwind-contexts.bin';target.write_bytes(b'EPUWDX1\0'+struct.pack('<I',4)+b''.join(variants))
    exe=PROJECT/'build/native_departure_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',PROJECT/'tests/native_departure_unwind_test.c','-o',exe])
    windows=json.loads(run([exe,target]))
    cases=[REFERENCE,{k:v+0x100000000 for k,v in REFERENCE.items()}]
    for field in REFERENCE:
        for value in (0,1,15,16,(1<<47)-16,1<<47,(1<<64)-1):cases.append({**REFERENCE,field:value})
    for field in REFERENCE:
        for delta in (-0x1000,0x1000,0x10000):cases.append({**REFERENCE,field:REFERENCE[field]+delta})
    for first in REFERENCE:
        for second in REFERENCE:
            if first!=second:cases.append({**REFERENCE,first:REFERENCE[second]})
    for value in (REFERENCE['code_address']+2264,REFERENCE['code_address']+2711,REFERENCE['getter_code_address']+387):cases.append({**REFERENCE,'reject_address':value})
    for field in ('code_address','getter_code_address','reject_address'):
        for delta in (-(1<<31)-1,-(1<<31),(1<<31)-1,1<<31):cases.append({**REFERENCE,field:REFERENCE[field]+delta})
    accepted=rejected=0
    for addresses in cases:
        try:ref=native.build(**addresses)['image']
        except (ValueError,OverflowError):ref=None
        out=Image();c.memset(c.byref(out),0xA5,c.sizeof(out));rc=lib.emit(Addresses(**addresses),out)
        if ref is None:
            native.require(rc!=0 and bytes(out)==bytes(c.sizeof(out)),'Invalid departure placement accepted: '+str(addresses));rejected+=1
        else:
            native.require(rc==0 and bytes(out.data[:out.bytes])==ref,'Departure relocation differs: '+str(addresses));accepted+=1
    for addresses,out in ((None,Image()),(Addresses(**REFERENCE),None)):
        native.require(lib.emit(addresses,out)==1 and (out is None or bytes(out)==bytes(c.sizeof(out))),'Invalid departure API accepted')
    checks=c.c_uint32();rc=lib.prepare(checks);native.require(rc==0,'Departure owner check failed at '+str(rc))
    paths=['native-departure.lock.json','tools/native_departure_image.py','tools/validate_departure_images.py','tests/native_departure_unwind_test.c',
           'tools/generate_departure_template.py','tools/native_departure_library.py','tests/departure_image_dll.cpp','tests/property_image_dll.cpp',
           'mod/src/ep_departure_image.h','mod/src/ep_departure_image.cpp','mod/src/ep_departure_templates.h','mod/src/ep_session_code.h','mod/src/ep_session_code.cpp']
    receipt=dict(schema='hellforge_native_departure_validation_v1',passed=True,verified_at_utc=datetime.now(timezone.utc).isoformat(),
        source_replay=replayed,functional_tests=result.testsRun,functional_runs=len(functional),original_functional_runs=sum(r['original'] for r in functional),
        windows_unwind_contexts=windows['windows_unwind_contexts'],negative_controls=windows['negative_controls_rejected'],
        candidate_code_bytes=art['candidate']['size_bytes'],image_bytes=len(art['image']),function_count=art['function_count'],
        accepted_placements=accepted,rejected_placements=rejected,api_contract_checks=2,owner_checks=checks.value,
        source_sha256={p:native.sha((PROJECT/p).read_bytes()) for p in paths},
        artifacts={p.name:dict(bytes=p.stat().st_size,sha256=native.sha(p.read_bytes())) for p in (lib.path,exe,target)},
        legacy_source_sha256={**native.profile()['legacy_source_sha256'],native.profile()['fixture_path']:native.profile()['fixture_sha256']},
        frame_bytes=144,stack_depth_bytes=168,verified_nonvolatile_xmm=[6],game_access=False,native_execution_of_game_bodies=False,
        runtime_verified=False,multiplayer_verified=False,callbacks_are_contract_stubs=True,late_rejection_rolls_back_prior_effects=False)
    (PROJECT/'evidence/native-departure-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return {k:receipt[k] for k in ('passed','functional_tests','functional_runs','accepted_placements','rejected_placements','owner_checks','windows_unwind_contexts','negative_controls','game_access')}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--zig',type=Path,required=True);parser.add_argument('--library',type=Path,required=True)
    a=parser.parse_args();print(json.dumps(validate(a.library.resolve(),a.zig.resolve())))
