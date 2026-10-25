"""Validate the receiver's relocated code and unwind on synthetic contexts."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import struct

import native_receiver_unwind as native
from build_unwind_offline import NAMES, run

ROOT,PROJECT=native.ROOT,native.PROJECT


def load():
    lock=json.loads((PROJECT/'native-storage.lock.json').read_bytes())
    for path,expected in lock['legacy_source_sha256'].items():
        native.require(native.sha((ROOT/path).read_bytes())==expected,'Changed pinned source: '+path)
    path=ROOT/'eight_player_candidate_20260927/tests/test_native_roster_receiver.py'
    spec=importlib.util.spec_from_file_location('receiver_unwind_fixture',path)
    r=importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
    native.require(r.unicorn.__version__==lock['unicorn'],'Wrong emulator')
    return r


def fixture(r,fixed):
    old_build,old_uc=r.native.build,r.Uc
    def wrapped(source,**addresses):
        return native.with_unwind(old_build(source,**addresses),conditional_rejection=fixed)['candidate']
    r.native.build=wrapped
    artifact=native.with_unwind(native.original(**r.parameters()),conditional_rejection=fixed)
    start=r.DEFAULT_GAME+0x10000000; size=artifact['candidate']['size_bytes']
    contexts=[]; scenarios=[]; visited=set()
    def record(uc,address,n,data):
        if start<=address<start+size:
            offset=address-start; visited.add(offset)
            fail=not fixed and offset in artifact['rejection_transfer_offsets']
            contexts.append(struct.pack('<IiI8Q',offset,uc.reg_read(r.register('rsp'))-r.ENTRY_RSP,int(fail),
                                        *(uc.reg_read(r.register(name)) for name in NAMES))+
                            bytes(uc.mem_read(r.ENTRY_RSP-128,256)))
    def constructor(*args,**kwargs):
        uc=old_uc(*args,**kwargs); uc.hook_add(r.UC_HOOK_CODE,record); return uc
    r.Uc=constructor
    cases=[(dict(ordinal=i,network_index=(3*i+2)%8),0) for i in range(8)]
    cases += [(dict(ordinal=8),1),(dict(ordinal=0xFFFFFFFF),1),(dict(input_roster=r.WRONG_ROSTER),2),
              (dict(entity=0xFFFFFFFF),1),(dict(capacity=0),1),(dict(buckets=[(0,0xFFFFFFFF)]*8),1),
              (dict(buckets=[(100+i,0) for i in range(8)]),1),
              (dict(ordinal=7,buckets=[(33,0),(25,0),(17,7)]+[(0,0xFFFFFFFF)]*5),0),
              (dict(ordinal=6,network_index=0xFEDCBA98),0)]
    try:
        for params,reason in cases:
            result=r.emulate(name='receiver_unwind',**params)
            verify=r.NativeRosterReceiverTests()
            if reason: verify.assert_rejected(result,reason)
            else:
                verify.assert_registers_returned(result); verify.assert_memory_success(result)
            scenarios.append({'input':params,'outcome':result['outcome'],'instructions':len(result['trace'])})
    finally:
        r.native.build=old_build; r.Uc=old_uc
    packet=struct.pack('<IIII',len(artifact['image']),size,artifact['table_offset'],len(contexts))+artifact['image']
    packet+=struct.pack('<9Q',*(r.REGISTER_SEEDS[n] for n in NAMES),r.DEFAULT_GAME+0x10006000)+b''.join(contexts)
    return packet,artifact,scenarios,len(contexts),len(visited)


def placement_checks(r):
    args=r.parameters(); old=native.original(**args)
    # Use the last E9's old offset, before adding the longer prologue/branches.
    md=native.capstone.Cs(native.capstone.CS_ARCH_X86,native.capstone.CS_MODE_64); md.detail=True
    jumps=[i.address for i in md.disasm(bytes.fromhex(old['code_hex']),args['code_address'])
           if i.mnemonic=='jmp' and i.operands[0].type==native.X86_OP_IMM and i.operands[0].imm==args['reject_address']]
    edge={**args,'reject_address':max(jumps)+5-(1<<31)}
    overlap={**args,'reject_address':args['code_address']+old['size_bytes']+1}
    for case,message in ((edge,'rel32 range'),(overlap,'overlaps')):
        legacy=native.original(**case)
        try: native.with_unwind(legacy)
        except ValueError as error: native.require(message in str(error),'Wrong placement refusal')
        else: raise AssertionError('Invalid placement accepted')
    changed=dict(old); changed['code_hex']='00'+old['code_hex'][2:]
    try: native.with_unwind(changed)
    except ValueError as error: native.require('Changed code' in str(error),'Wrong source refusal')
    else: raise AssertionError('Changed source accepted')
    return 3


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--zig',type=Path,required=True)
    args=parser.parse_args(); zig=args.zig.resolve()
    lock=json.loads((PROJECT/'upstream.lock.json').read_bytes())
    native.require(native.sha(zig.read_bytes())==lock['zig']['exe_sha256'],'Changed compiler')
    native.require(run([zig,'version']).decode().strip()==lock['zig']['version'],'Wrong compiler')
    build=PROJECT/'build'; build.mkdir(exist_ok=True)
    r=load(); guards=placement_checks(r)
    old,*_=fixture(r,False); new,artifact,scenarios,contexts,visited=fixture(r,True)
    data=build/'receiver-unwind-contexts.bin'; data.write_bytes(b'EPUWDV1\0'+struct.pack('<I',2)+old+new)
    image=build/'receiver-unwind-image.bin'; image.write_bytes(artifact['image'])
    exe=build/'native_receiver_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-Wall','-Werror','-O1',
         PROJECT/'tests/native_producer_unwind_test.c','-o',exe])
    result=json.loads(run([exe,data]))
    native.require(result['windows_unwind_contexts']==contexts,'Incomplete context verification')
    result.update(placement_and_source_refusals=guards,unique_instruction_positions=visited)
    paths=('tools/native_receiver_unwind.py','tools/build_receiver_unwind_offline.py','tools/native_producer_unwind.py',
           'tools/build_unwind_offline.py','tests/native_producer_unwind_test.c','native-storage.lock.json','upstream.lock.json',
           'tools/native_unwind_source.py','native-unwind-source.lock.json')
    receipt={'schema':'hellforge_native_receiver_unwind_v1','verified_at_utc':datetime.now(timezone.utc).isoformat(),
             **result,'game_build':25480438,'receiver_rva':'0x60C890','scenarios':scenarios,
             'code_bytes':artifact['candidate']['size_bytes'],'unwind_hex':native.UNWIND.hex(),
             'unwind_offset':artifact['unwind_offset'],'table_offset':artifact['table_offset'],
             'normalized_prologue_bytes':len(native.CANONICAL_PROLOGUE),
             'negative_control':'Same normalized prologue and unwind data, original E9 rejection transfers',
             'image_protection':'PAGE_READWRITE; no native candidate execution',
             'function_tables_registered_and_removed_in_test':2,'real_game_hooks_installed':False,
             'original_unwind_source':artifact['candidate']['original_unwind_source'],
             'runtime_original_exception_table_verified':False,'runtime_verified':False,'multiplayer_verified':False,
             'source_sha256':{p:native.sha((PROJECT/p).read_bytes()) for p in paths},
             'artifacts':{p.name:{'bytes':p.stat().st_size,'sha256':native.sha(p.read_bytes())} for p in (exe,data,image)}}
    (PROJECT/'evidence/native-receiver-unwind-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result))


if __name__=='__main__': main()
