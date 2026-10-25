"""Build and verify the producer's unwind image using Unicorn + Windows APIs."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

import native_producer_unwind as native

ROOT, PROJECT = native.ROOT, native.PROJECT
NAMES = ('rbx','rbp','rsi','rdi','r12','r13','r14','r15')


def run(args):
    r = subprocess.run([str(x) for x in args], capture_output=True, cwd=ROOT)
    if r.returncode:
        raise RuntimeError(r.stdout.decode(errors='replace') + r.stderr.decode(errors='replace'))
    return r.stdout


def load():
    lock = json.loads((PROJECT / 'native-storage.lock.json').read_bytes())
    for path, expected in lock['legacy_source_sha256'].items():
        native.require(native.sha((ROOT / path).read_bytes()) == expected, 'Changed pinned source: ' + path)
    path = ROOT / 'eight_player_candidate_20260927/tests/test_native_roster_producer.py'
    spec = importlib.util.spec_from_file_location('producer_unwind_fixture', path)
    p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
    native.require(p.unicorn.__version__ == lock['unicorn'], 'Wrong emulator')
    return p


def fixture(p, fixed):
    original = p.native.build
    def wrapped(source, **args):
        return native.with_unwind(original(source, **args), conditional_rejection=fixed)['candidate']
    p.native.build = wrapped
    contexts, scenarios = [], []
    args = p.parameters()
    image = native.with_unwind(native.original(**args), conditional_rejection=fixed)
    boundary = p.GAME + 0x10000000
    size = image['candidate']['size_bytes']
    cases = [dict(ordinal=i, network=(i*3+2)%8) for i in range(8)]
    cases += [dict(ordinal=8), dict(ordinal=0xFFFFFFFF), dict(actual_roster=p.WRONG), dict(index_mode='empty')]
    try:
        for params in cases:
            f = p.Fixture(**params)
            def record(uc, address, n, data):
                if boundary <= address < boundary + size:
                    offset = address-boundary
                    failed = not fixed and offset in image['legacy_rejection_offsets']
                    contexts.append(struct.pack('<IiI8Q',offset,uc.reg_read(p.reg('rsp'))-p.RSP,int(failed),
                                                *(uc.reg_read(p.reg(n)) for n in NAMES)) + f.read(p.RSP-128,256))
            f.uc.hook_add(p.UC_HOOK_CODE, record)
            f.run('producer_unwind')
            verifier = p.ProducerTests()
            if params.get('ordinal',0) >= 8: verifier.rejected(f,1)
            elif 'actual_roster' in params: verifier.rejected(f,2)
            else: verifier.success(f)
            scenarios.append({'input': params, 'outcome': f.outcome, 'instructions':len(f.trace)})
    finally:
        p.native.build=original
    data = struct.pack('<IIII',len(image['image']),size,image['table_offset'],len(contexts)) + image['image']
    data += struct.pack('<9Q',*(p.SEEDS[n] for n in NAMES),p.GAME+0x10008000) + b''.join(contexts)
    return data, image, scenarios, len(contexts)


def placement_checks(p):
    args=p.parameters(); old=native.original(**args)
    offsets=native.with_unwind(old)['legacy_rejection_offsets']
    # The old final E9 fits at INT32_MIN, but the longer JNZ sequence cannot.
    edge={**args,'reject_address':args['code_address']+max(offsets)+5-(1<<31)}
    overlap={**args,'reject_address':args['code_address']+old['size_bytes']+1}
    for case, message in ((edge,'rel32 range'),(overlap,'overlaps')):
        legacy=native.original(**case)  # Must be accepted by the old emitter.
        try: native.with_unwind(legacy)
        except ValueError as error: native.require(message in str(error),'Wrong placement refusal')
        else: raise AssertionError('Unsafe extended image was accepted')
    changed=dict(old); changed['code_hex']='00'+old['code_hex'][2:]
    try: native.with_unwind(changed)
    except ValueError as error: native.require('Changed code' in str(error),'Wrong fingerprint refusal')
    else: raise AssertionError('Changed source was accepted')
    return 3


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--zig',type=Path,required=True)
    args=parser.parse_args(); zig=args.zig.resolve()
    lock=json.loads((PROJECT/'upstream.lock.json').read_bytes())
    native.require(native.sha(zig.read_bytes())==lock['zig']['exe_sha256'],'Changed compiler')
    native.require(run([zig,'version']).decode().strip()==lock['zig']['version'],'Wrong compiler')
    build=PROJECT/'build'; build.mkdir(exist_ok=True)
    p=load(); guards=placement_checks(p)
    old, _, _, _=fixture(p,False); new, artifact, scenarios, contexts=fixture(p,True)
    data_path=build/'producer-unwind-contexts.bin'; data_path.write_bytes(b'EPUWDV1\0'+struct.pack('<I',2)+old+new)
    image_path=build/'producer-unwind-image.bin'; image_path.write_bytes(artifact['image'])
    exe=build/'native_producer_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-Wall','-Werror','-O1',
         PROJECT/'tests/native_producer_unwind_test.c','-o',exe])
    result=json.loads(run([exe,data_path]))
    native.require(result['windows_unwind_contexts']==contexts,'Incomplete context validation')
    result['placement_and_source_refusals']=guards
    receipt={'schema':'hellforge_native_producer_unwind_v1','verified_at_utc':datetime.now(timezone.utc).isoformat(),
             **result,'game_build':25480438,'producer_rva':'0x60C640','scenarios':scenarios,
             'code_bytes':artifact['candidate']['size_bytes'],'unwind_hex':native.UNWIND.hex(),
             'table_offset':artifact['table_offset'],'unwind_offset':artifact['unwind_offset'],
             'image_protection':'PAGE_READWRITE; no native execution of candidate code',
             'negative_control':'Same normalized prologue and unwind metadata, but original E9 rejection branches',
             'function_tables_registered_and_removed_in_test':2,'real_game_hooks_installed':False,
             'receiver_unwind_implemented':False,'runtime_verified':False,'multiplayer_verified':False,
             'source_sha256':{str(path.relative_to(ROOT)).replace('\\','/'):native.sha(path.read_bytes()) for path in
                              (PROJECT/'tools/native_producer_unwind.py',PROJECT/'tools/build_unwind_offline.py',
                               PROJECT/'tests/native_producer_unwind_test.c',PROJECT/'native-storage.lock.json',
                               PROJECT/'upstream.lock.json')},
             'artifacts':{x.name:{'bytes':x.stat().st_size,'sha256':native.sha(x.read_bytes())} for x in (exe,data_path,image_path)}}
    (PROJECT/'evidence/native-producer-unwind-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result))


if __name__=='__main__': main()
