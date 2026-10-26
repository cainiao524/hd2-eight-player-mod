"""State-update semantics, original GS checker, placement and Windows unwind."""
import argparse,ctypes as c,io,json,struct,unittest
from datetime import datetime,timezone
from pathlib import Path
import native_arrival_image as native
from build_unwind_offline import run,NAMES
from verify_native_unwind_source import replay
from native_arrival_library import Library,Addresses,Image
from generate_arrival_template import render,HEADER,REFERENCE
PROJECT=native.PROJECT

def gs_cases(p,library):
    """Execute the emitted thunk and both saved GS bodies in synthetic RAM.

    Only __security_check_cookie is intercepted; assert its exact RCX argument.
    Corruption stops there, rather than simulating a successful security check.
    """
    results=[];data=native.profile();old=native.load('gs_capture',native.ROOT/data['capture_reader_path'])
    saved=old.Image(native.ROOT/'evidence/existing-code-evidence-25480438')
    for part in data['gs_handler'].values():
        if not isinstance(part,dict):continue
        raw=bytes.fromhex(part['bytes_hex']);native.require(native.sha(raw)==part['sha256'] and saved.read(int(part['rva'],16),len(raw))==raw,'GS body differs from saved capture')
    for game in (p.GAME,p.GAME+0x200000000):
        for corrupt in (False,True):
            f=p.Fixture(game=game);art=native.build(**p.params(game));candidate=library.arrival_candidate(p.params(game),art)
            f.map(f.start,len(art['image']));f.write(f.start,art['image'])
            for part in ('handler','check'):
                item=data['gs_handler'][part];addr=game+int(item['rva'],16);raw=bytes.fromhex(item['bytes_hex']);f.map(addr,len(raw));f.write(addr,raw)
            dispatcher=p.STACK+0x200;frame=p.RSP-136;call_rsp=p.STACK+0x4008
            f.write(dispatcher+8,p.u64(f.start));f.write(dispatcher+16,p.u64(f.start+art['table_offset']+12))
            f.write(dispatcher+56,p.u64(f.start+art['unwind_offset']+32))
            f.write(frame+96,p.u64(p.COOKIE^frame^int(corrupt)));f.write(call_rsp,p.u64(f.stop))
            for name,value in [('rcx',0),('rdx',frame),('r8',0),('r9',dispatcher),('rsp',call_rsp)]:f.uc.reg_write(p.reg(name),value)
            # The root fixture hooks are intentionally removed: only this GS
            # path's hook may interpret the checker/stop sites.
            for attr in ('code_hook','read_hook','write_hook'):
                if hasattr(f,attr):f.uc.hook_del(getattr(f,attr))
            events=[];trace=[]
            def check(uc,pc,size,user):
                trace.append(pc)
                if pc==game+0x2088770:
                    actual=uc.reg_read(p.reg('rcx'));native.require(actual==p.COOKIE^int(corrupt),'Original GS checker received wrong cookie')
                    events.append('corrupt_cookie' if corrupt else 'valid_cookie')
                    if corrupt:uc.emu_stop()
                    else:
                        sp=uc.reg_read(p.reg('rsp'));uc.reg_write(p.reg('rip'),int.from_bytes(f.read(sp,8),'little'));uc.reg_write(p.reg('rsp'),sp+8)
                elif pc==f.stop:events.append('returned');uc.emu_stop()
            # Use a clean emulator so the frozen fixture's anonymous hook IDs
            # cannot silently intercept this separate handler experiment.
            uc=p.Uc(p.UC_ARCH_X86,p.UC_MODE_64)
            for page in f.pages:uc.mem_map(page,4096);uc.mem_write(page,f.read(page,4096))
            for name in NAMES+('rcx','rdx','r8','r9','rsp'):uc.reg_write(p.reg(name),f.uc.reg_read(p.reg(name)))
            f.uc=uc;uc.hook_add(p.UC_HOOK_CODE,check)
            uc.emu_start(f.start+art['handler_offset'],0,count=500)
            native.require(events==(['corrupt_cookie'] if corrupt else ['valid_cookie','returned']),'GS flow did not finish as expected')
            native.require(game+0x21044a0 in trace and game+0x21044c0 in trace and game+0x2088770 in trace,'GS forwarding skipped a saved body')
            if not corrupt:
                native.require(uc.reg_read(p.reg('rax'))==1 and uc.reg_read(p.reg('rsp'))==call_rsp+8,'Original handler disposition/stack changed')
                native.require(all(uc.reg_read(p.reg(n))==p.SEEDS[n] for n in NAMES),'GS nonvolatile register changed')
            results.append(dict(game_base=hex(game),corrupt=corrupt,outcome=events[-1],instructions=len(trace),security_check_argument=hex(p.COOKIE^int(corrupt))))
    return results

def validate(library,zig):
    blob,facts=render();native.require(HEADER.read_bytes()==blob,'State-update template changed');lib=Library(library)
    replayed=replay(native.profile(),native.ROOT/'evidence/existing-code-evidence-25480438')
    p=native.load_fixture();native.bind_fixture(p,lib);art=native.build(**p.params());contexts={};original_run=p.Fixture.run
    expected_pc=p.GAME+0x10700000;expected_xmm=((0x0102030405060708+6)*(1+(1<<64))).to_bytes(16,'little')
    def row(f,uc,pc,fail=0):
        stack=bytearray(f.read(p.RSP-256,384));struct.pack_into('<Q',stack,256,expected_pc)
        return struct.pack('<IiI8Q',pc-f.start,uc.reg_read(p.reg('rsp'))-p.RSP,fail,*(uc.reg_read(p.reg(n)) for n in NAMES))+uc.reg_read(p.reg('xmm6')).to_bytes(16,'little')+stack
    def run_fixture(f,name):
        def record(uc,pc,size,user):
            if f.start<=pc<f.start+f.artifact['size_bytes']:contexts[row(f,uc,pc)]=None
        h=None if f.original else f.uc.hook_add(p.UC_HOOK_CODE,record)
        try:return original_run(f,name)
        finally:
            if h is not None:f.uc.hook_del(h)
    p.Fixture.run=run_fixture
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromTestCase(p.ArrivalTests))
    native.require(result.wasSuccessful(),stream.getvalue());functional=list(p.RUNS)
    expected=struct.pack('<9Q',*(p.SEEDS[n] for n in NAMES),expected_pc)+expected_xmm
    def pack(image,rows):return struct.pack('<4I',len(image),art['candidate']['size_bytes'],art['table_offset'],len(rows))+image+expected+b''.join(rows)
    bad=bytearray(art['image']);old=native.legacy().build(p.BODY,**p.params());bad[:old['size_bytes']]=bytes.fromhex(old['code_hex'])
    f=p.Fixture();f.write(f.game+0x3326468,p.u64(0x40000000));f.write(f.start,bytes(bad[:old['size_bytes']]))
    rejected=[];target=f.start+art['rejection_offsets'][0]+9
    def rejection(uc,pc,size,user):
        if pc==target:rejected.append(row(f,uc,pc,1))
    h=f.uc.hook_add(p.UC_HOOK_CODE,rejection);original_run(f,'negative_old_rejection');f.uc.hook_del(h)
    native.require(len(rejected)==1,'Missing old rejection control');variants=[pack(bytes(bad),rejected)]
    sample=next(r for r in contexts if struct.unpack_from('<i',r,4)[0]==-136 and r[76:92]!=expected_xmm)
    negative=bytearray(sample);struct.pack_into('<I',negative,8,1)
    for off,value in ((25,0xe2),(6,6)):
        bad=bytearray(art['image']);bad[art['unwind_offset']+off]=value;variants.append(pack(bytes(bad),[negative]))
    variants.append(pack(art['image'],list(contexts)))
    target=PROJECT/'build/arrival-unwind-contexts.bin';target.write_bytes(b'EPUWDX1\0'+struct.pack('<I',4)+b''.join(variants))
    exe=PROJECT/'build/native_arrival_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',PROJECT/'tests/native_arrival_unwind_test.c','-o',exe])
    windows=json.loads(run([exe,target]));gs=gs_cases(p,lib)
    cases=[REFERENCE,{k:v+0x100000000 for k,v in REFERENCE.items()}]
    for field in REFERENCE:
        for value in (0,1,15,16,(1<<47)-16,1<<47,(1<<64)-1):cases.append({**REFERENCE,field:value})
    for field in REFERENCE:
        for delta in (-0x1000,0x1000,0x10000):cases.append({**REFERENCE,field:REFERENCE[field]+delta})
    for first in REFERENCE:
        for second in REFERENCE:
            if first!=second:cases.append({**REFERENCE,first:REFERENCE[second]})
    for value in (REFERENCE['code_address']+1917,REFERENCE['code_address']+2023):cases.append({**REFERENCE,'reject_address':value})
    for field in ('code_address','reject_address'):
        for delta in (-(1<<31)-1,-(1<<31),(1<<31)-1,1<<31):cases.append({**REFERENCE,field:REFERENCE[field]+delta})
    accepted=rejected=0
    for addresses in cases:
        try:ref=native.build(**addresses)['image']
        except (ValueError,OverflowError):ref=None
        out=Image();c.memset(c.byref(out),0xA5,c.sizeof(out));rc=lib.emit(Addresses(**addresses),out)
        if ref is None:
            native.require(rc!=0 and bytes(out)==bytes(c.sizeof(out)),'Invalid state-update placement accepted: '+str(addresses));rejected+=1
        else:
            native.require(rc==0 and bytes(out.data[:out.bytes])==ref,'State-update relocation differs: '+str(addresses));accepted+=1
    for addresses,out in ((None,Image()),(Addresses(**REFERENCE),None)):
        native.require(lib.emit(addresses,out)==1 and (out is None or bytes(out)==bytes(c.sizeof(out))),'Invalid state-update API accepted')
    checks=c.c_uint32();rc=lib.prepare(checks);native.require(rc==0,'State-update owner check failed at '+str(rc))
    paths=['native-arrival.lock.json','tools/native_arrival_image.py','tools/validate_arrival_images.py','tests/native_arrival_unwind_test.c',
        'tools/generate_arrival_template.py','tools/native_arrival_library.py','tests/arrival_image_dll.cpp','tests/departure_image_dll.cpp','tests/property_image_dll.cpp',
        'mod/src/ep_arrival_image.h','mod/src/ep_arrival_image.cpp','mod/src/ep_arrival_templates.h','mod/src/ep_session_code.h','mod/src/ep_session_code.cpp',
        'tools/native_unwind_source.py','tools/verify_native_unwind_source.py']
    receipt=dict(schema='hellforge_native_arrival_validation_v1',passed=True,verified_at_utc=datetime.now(timezone.utc).isoformat(),
        source_replay=replayed,functional_tests=result.testsRun,functional_runs=len(functional),original_functional_runs=sum(r['original'] for r in functional),
        windows_unwind_contexts=windows['windows_unwind_contexts'],gs_handler_dispatches=windows['gs_handler_dispatches'],negative_controls=windows['negative_controls_rejected'],
        candidate_code_bytes=art['candidate']['size_bytes'],image_bytes=len(art['image']),function_count=art['function_count'],
        accepted_placements=accepted,rejected_placements=rejected,api_contract_checks=2,owner_checks=checks.value,
        gs_execution_cases=gs,gs_metadata_rejection_cases=15,
        source_sha256={p:native.sha((PROJECT/p).read_bytes()) for p in paths},
        artifacts={p.name:dict(bytes=p.stat().st_size,sha256=native.sha(p.read_bytes())) for p in (lib.path,exe,target)},
        legacy_source_sha256={**native.profile()['legacy_source_sha256'],native.profile()['fixture_path']:native.profile()['fixture_sha256']},
        frame_bytes=128,stack_depth_bytes=136,verified_nonvolatile_xmm=[6],game_access=False,native_execution_of_game_bodies=False,
        runtime_verified=False,multiplayer_verified=False,callbacks_are_contract_stubs=True,group_integrated=True,character_creation_proven=False)
    (PROJECT/'evidence/native-arrival-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return {k:receipt[k] for k in ('passed','functional_tests','functional_runs','accepted_placements','rejected_placements','owner_checks','windows_unwind_contexts','gs_handler_dispatches','negative_controls','game_access')}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--zig',type=Path,required=True);parser.add_argument('--library',type=Path,required=True)
    a=parser.parse_args();print(json.dumps(validate(a.library.resolve(),a.zig.resolve())))
