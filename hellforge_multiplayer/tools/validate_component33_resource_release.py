"""Standalone release/deferred SDK integration and saved RELEASE equivalence."""
import argparse,ctypes as c,json,struct,subprocess,sys
from pathlib import Path
import native_component33_image as n
import validate_component33_resource_call as admission
import validate_component33_resource_services as services
import validate_component33_resources as r
import validate_component33_consumers as v
from native_component33_library import Library
SCENARIOS=('immediate','deferred_without_callbacks','deferred_then_reacquire','dispose_failure','dispose_seh','ignored_nested_fault',
    'resource_reentry','code_mismatch','package_unreadable','ordinal_outside_dense','ordinal_overflow','invalid_defer_flag','resolver_not_used','missing_immediate_service','map_mismatch')
def load(path):
    dll=c.CDLL(str(path.resolve()));dll.c33_resource_release_test.argtypes=[c.c_uint];dll.c33_resource_release_test.restype=c.c_uint
    dll.c33_resource_release.argtypes=[c.POINTER(r.Binding),r.P,r.D,c.POINTER(r.U),r.D,r.D,r.P,r.D,services.SERVICE,r.P];dll.c33_resource_release.restype=c.c_int
    return dll
def validate(library,resources,core):
    dll=load(library);native=[];checks=0;runs=[];cases=[]
    def check(ok,name):
        nonlocal checks
        n.need(ok,name);checks+=1;cases.append(name)
    for mode,name in enumerate(SCENARIOS):
        p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode)],capture_output=True,text=True,timeout=30)
        n.need(p.returncode==0,name+': '+p.stdout+p.stderr);result=json.loads(p.stdout);checks+=result['checks'];native.append(dict(name=name,**result))
    res=r.Resources(resources);lib=Library(core)
    for capacity in (128,512):
        for seed in (0,1,0xffffffff):
            for deferred in (0,1):
                raw=res.migrate_bytes(r.snapshot([(101,2),(102,1),(103,0),(104,3),(105,0)],[103],seed),capacity)
                raw=bytearray(raw);struct.pack_into('<Q',raw,48+7*8,0xabcdef);raw=bytes(raw)
                keys=[101,102,101,103,104,101,999];package=bytearray(0x3030);struct.pack_into('<I',package,0x800,7)
                for i,key in enumerate(keys):struct.pack_into('<Q',package,i*0x20,key)
                # Nonzero keys of disabled groups must not be released.
                struct.pack_into('<Q',package,0x808,104)
                f=r.Fixture(lib,r.Images(res,capacity),'release',8,8,4,ordinal=7,flag=deferred);f.put(v.PKG+7*0x4000,bytes(package));f.install(raw,res,capacity)
                expected=f.execute_resource();expected_calls=[(1,args[0]) for name,args in f.calls if name=='dispose']
                arena=c.create_string_buffer(raw,len(raw));scratch=c.create_string_buffer(len(raw));sequence=(r.U*len(keys))(*keys);calls=[]
                @services.SERVICE
                def service(context,op,key):calls.append((op,key));return 1
                rc=dll.c33_resource_release(r.Binding(r.A,capacity,0),arena,len(raw),sequence,len(keys),deferred,scratch,len(raw),service,None)
                check(rc==0 and arena.raw==expected,'complete_arena_equals_saved_release');check(calls==expected_calls,'service_trace_equals_saved_release')
                check(r.unpack(arena.raw,capacity)==({101:0,102:0,103:0,104:2,105:0},[103,102,101] if deferred else [103]),'release_order_and_references')
                runs.append(dict(capacity=capacity,seed=seed,deferred=bool(deferred),instructions=len(f.trace),whole_arena_equal=True,services_equal=True,services=len(calls)))
    for case in ('zero_key','too_many','scratch_alias','key_alias','bad_flag','invalid_queue'):
        raw=res.migrate_bytes(r.snapshot([(101,1)]),128)
        if case=='invalid_queue':raw=bytearray(raw);struct.pack_into('<Q',raw,32,129);raw=bytes(raw)
        arena=c.create_string_buffer(raw,len(raw));scratch=c.create_string_buffer(len(raw));sequence=(r.U*2)(101,0 if case=='zero_key' else 101);calls=[]
        @services.SERVICE
        def service(context,op,key):calls.append((op,key));return 1
        rc=dll.c33_resource_release(r.Binding(r.A,128,0),arena,len(raw),c.cast(arena,c.POINTER(r.U)) if case=='key_alias' else sequence,
            385 if case=='too_many' else 2,2 if case=='bad_flag' else 1,arena if case=='scratch_alias' else scratch,len(raw),service,None)
        check(rc!=0 and arena.raw==raw and not calls,'atomic_refusal_'+case)
    source=set(json.loads((n.PROJECT/'evidence/native-component33-resource-provider-validation.json').read_bytes())['source_sha256'])
    source.update(('tests/component33_resource_release_dll.cpp','tools/validate_component33_resource_release.py'))
    return dict(schema='hellforge_component33_resource_release_validation_v1',passed=True,checks=checks,native_scenarios=len(native),scenarios=native,functional_runs=len(runs),runs=runs,cases=cases,
        standalone_release_sdk_provider=True,shared_retained_owner=True,deferred_queue_atomic=True,release_skips_acquire_reservation=True,
        release_skips_resolver_and_thresholds=True,existing_zero_buckets_preserved=True,deferred_to_acquire_queue_cancellation=True,
        immediate_failure_partial_effects_preserved=True,callback_abi_bound=False,original_entry_bound=False,queue_drain_bound=False,safe_reset_lifecycle_verified=False,
        installed=False,game_access=False,native_execution_of_game_bodies=False,runtime_verified=False,multiplayer_verified=False,
        source_sha256={s:n.sha((n.PROJECT/s if (n.PROJECT/s).exists() else n.PROJECT.parent/s).read_bytes()) for s in sorted(source)},
        reference_validation_sha256={f:n.sha((n.PROJECT/'evidence'/f).read_bytes()) for f in ('native-component33-resource-provider-validation.json','native-component33-resource-services-validation.json')},
        artifacts={p.name:dict(bytes=p.stat().st_size,sha256=n.sha(p.read_bytes())) for p in (library,resources,core)},
        limitations=['Explicit provider API only; original game entries and all writers are not routed.',
            'No queue drain, reset timing, embedded resource transfer or service compensation is supplied.',
            'Saved RELEASE executes in Unicorn with synthetic package/services; native DLL uses only owned fixtures.',
            'Actual resolver/service target code is absent from the reviewed capture; no native ABI is invented.',
            'All real gameplay, UI, concurrency and performance remain unverified.'])
def main():
    ap=argparse.ArgumentParser()
    for k in ('zig','upstream','library','resources','core','out'):ap.add_argument('--'+k,type=Path)
    ap.add_argument('--worker',type=int);a=ap.parse_args();library=(a.library or n.PROJECT/'build/component33_resource_release_test.dll').resolve()
    if a.worker is not None:print(json.dumps(dict(checks=load(library).c33_resource_release_test(a.worker))));return
    if a.zig:
        command=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
            '-I',a.upstream.resolve()/'native/mod-sdk','-I',n.PROJECT/'mod/src','-shared',*(n.PROJECT/s for s in admission.SOURCES),n.PROJECT/'mod/src/ep_component33_resource_provider.cpp',n.PROJECT/'tests/component33_resource_release_dll.cpp','-o',library]
        process=subprocess.run([str(x) for x in command],capture_output=True,text=True);n.need(process.returncode==0,process.stdout+process.stderr)
    result=validate(library,a.resources.resolve(),a.core.resolve());a.out.write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps({k:result[k] for k in ('passed','checks','native_scenarios','functional_runs','game_access')}))
if __name__=='__main__':main()
