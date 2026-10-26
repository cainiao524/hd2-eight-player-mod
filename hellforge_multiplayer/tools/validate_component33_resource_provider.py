"""SDK-backed resource provider in owned memory, saved real getters in Unicorn."""
import argparse,collections,ctypes as c,json,struct,subprocess,sys
from pathlib import Path
import native_component33_image as n
import native_component33_resource_provider as source
import validate_component33_resource_call as call
import validate_component33_resources as r
import validate_component33_consumers as v
from native_component33_library import Library
SCENARIOS=('eighth_entity_collision_package','no_entity','getter_code_mismatch','getter_code_unreadable',
    'package_read_failure','missing_package','invalid_component_map','disabled_groups','threshold_entity_missing',
    'threshold_tag_missing','sdk_read_budget','resolver_unavailable','resolver_seh','ignored_nested_resolver_fault',
    'load_failure','build_mismatch','load_seh','component_binding_changed','package_address_overflow','count_overflow','sdk_truncated')
class Result(c.Structure):_fields_=[(k,c.c_uint32) for k in ('status','owner_result','demand_count','executed','source_status','read_bytes','resolve_calls','reserved')]
class Probe(c.Structure):_fields_=[('checks',c.c_uint32),('keys',c.c_uint32),('result',Result),('service_keys',c.c_uint64*384)]
def worker(library,mode):
    dll=c.CDLL(str(library.resolve()));fn=dll.c33_resource_provider_test;fn.argtypes=[c.c_uint32,c.POINTER(Probe)];fn.restype=None
    p=Probe();fn(mode,p)
    return dict(checks=p.checks,service_keys=list(p.service_keys[:p.keys]),result={k:getattr(p.result,k) for k,_ in Result._fields_})
class Fixture(r.Fixture):
    def on_code(self,uc,pc,size,data):
        if getattr(self,'real_getters',False) and pc in (self.game+0x4f6430,self.game+0x7af0a0):
            self.getters[hex(pc-self.game)]+=1;self.trace.append(pc);return
        super().on_code(uc,pc,size,data)
def validate(library,resources,core):
    p=source.profile();n.need(source.HEADER.read_bytes()==source.render(),'provider template stale')
    native=[];results={};checks=1;runs=[]
    for mode,name in enumerate(SCENARIOS):
        command=[sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode)]
        process=subprocess.run(command,capture_output=True,text=True,timeout=30)
        n.need(process.returncode==0,name+': '+process.stdout+process.stderr)
        result=json.loads(process.stdout);checks+=result['checks'];results[mode]=result
        native.append(dict(name=name,checks=result['checks'],result=result['result'],services=len(result['service_keys']),service_keys_sha256=n.sha(struct.pack('<'+'Q'*len(result['service_keys']),*result['service_keys']))))
    res=r.Resources(resources);lib=Library(core)
    for mode in (0,7,8,9):
        f=Fixture(lib,r.Images(res,512),'acquire',8,8,4,ordinal=7)
        f.real_getters=True;f.getters=collections.Counter()
        for row in p['functions'].values():f.put(f.game+row['start'],bytes.fromhex(row['body_hex']))
        root=v.HEAP+0x200000;table=v.HEAP+0x100000;manager=v.HEAP+0x300000
        f.put(f.game+0x346bf98,struct.pack('<Q',root));f.put(root+0xf12580,struct.pack('<Q',table))
        f.put(table,struct.pack('<QIIQII',0x12007,1,0,0x12005,0,0));package=bytearray(0x3030)
        values=[100,0,1,0x7fffffff,0x80000000,0xffffffff]
        for g,value in enumerate(values):
            struct.pack_into('<I',package,g*0x808+0x800,0 if mode==7 else 101+g)
            for i in range(64):
                off=g*0x808+i*0x20;struct.pack_into('<Q',package,off,999+g*64+i);struct.pack_into('<II',package,off+16,value,value)
        f.put(table+32+0x3030,bytes(package));f.put(f.game+0x3326998,struct.pack('<Q',manager))
        f.put(manager+8,struct.pack('<I',6 if mode==8 else 8))
        f.put(manager+0x68,struct.pack('<8Q',*(v.E+i*64 for i in (0,1,2,3,4,6,7,5))))
        f.put(v.E+64+16,struct.pack('<I',0x7fff));row=bytearray(0x58);struct.pack_into('<I',row,0,6)
        for g,value in enumerate(values):struct.pack_into('<I',row,4+g*4,9999 if mode==9 else 101+g);struct.pack_into('<I',row,0x30+g*4,value)
        f.put(manager+0x26688+6*0x58,bytes(row))
        raw=res.migrate_bytes(r.snapshot(seed=1),512);rc,raw=res.reserve_bytes(raw,list(range(999,999+384)),512);n.need(rc==0,'comparison admission')
        f.install(raw,res,512);after=f.execute_resource()
        keys=[args[0] for name,args in f.calls if name=='load']
        n.need(keys==results[mode]['service_keys'],'SDK provider differs from saved complete getters');checks+=1
        counts,_=r.unpack(after,512);n.need({k:v for k,v in counts.items() if v}==dict(collections.Counter(keys)),'saved reference totals');checks+=1
        n.need(f.getters['0x4f6430']==2 and f.getters['0x7af0a0']==(0 if mode==7 else 6),'real getters bypassed');checks+=1
        runs.append(dict(scenario=SCENARIOS[mode],instructions=len(f.trace),package_body_executions=f.getters['0x4f6430'],threshold_body_executions=f.getters['0x7af0a0'],service_keys_equal=True,services=len(keys)))
    sources=set(json.loads((n.PROJECT/'evidence/native-component33-resource-call-validation.json').read_bytes())['source_sha256'])
    sources.update(['mod/src/ep_component33_resource_provider.h','mod/src/ep_component33_resource_provider.cpp','mod/src/ep_component33_resource_provider_template.h',
        'tests/component33_resource_provider_dll.cpp','tools/native_component33_resource_provider.py','tools/validate_component33_resource_provider.py','native-component33-resource-provider.lock.json'])
    ref='native-component33-resource-services-validation.json'
    return dict(schema='hellforge_component33_resource_provider_validation_v1',passed=True,checks=checks,native_scenarios=len(native),scenarios=native,
        functional_runs=len(runs),runs=runs,sdk_reader_implemented=True,read_code_source_gate=True,sdk_read_limit=65536,
        explicit_shared_owner_integration=True,eighth_entity_selection_verified=True,saved_package_and_threshold_bodies_executed=True,
        package_queries_frozen_from_two_to_one=True,identity_resolver_is_contract_stub=True,resource_services_are_contract_stubs=True,
        production_resolver_abi_bound=False,production_service_abi_bound=False,all_game_writers_covered=False,original_entry_bound=False,
        source_coherence_in_game_verified=False,native_execution_of_game_bodies=False,callback_internal_reads_counted=False,
        installed=False,game_access=False,runtime_verified=False,multiplayer_verified=False,
        source_sha256={s:n.sha((n.PROJECT/s if (n.PROJECT/s).exists() else n.PROJECT.parent/s).read_bytes()) for s in sorted(sources)},
        reference_validation_sha256={ref:n.sha((n.PROJECT/'evidence'/ref).read_bytes())},
        artifacts={f.name:dict(bytes=f.stat().st_size,sha256=n.sha(f.read_bytes())) for f in (library,resources,core)},
        limitations=['SDK reads in native tests map only owned fixtures; real game access is not performed.',
            'Source reads are bounded at 64 KiB; accesses inside explicit resolver/service callbacks are outside that SDK counter.',
            'Saved real package/threshold bodies run in Unicorn; their indirect object resolver and resource services remain stubs.',
            'All-writer exclusion, resolver/service ABI, original entry routing, resource reset and runtime performance remain unverified.',
            'Frozen provider moves package/threshold lookup before resource effects; coherence and resolver side effects require production proof.'])
def main():
    ap=argparse.ArgumentParser()
    for name in ('zig','upstream','library','resources','core','out'):ap.add_argument('--'+name,type=Path)
    ap.add_argument('--worker',type=int);a=ap.parse_args()
    if a.worker is not None:print(json.dumps(worker(a.library,a.worker)));return
    library=(a.library or n.PROJECT/'build/component33_resource_provider_test.dll').resolve()
    if a.zig:
        command=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
            '-I',a.upstream.resolve()/'native/mod-sdk','-I',n.PROJECT/'mod/src','-shared',*(n.PROJECT/s for s in call.SOURCES),
            n.PROJECT/'mod/src/ep_component33_resource_provider.cpp',n.PROJECT/'tests/component33_resource_provider_dll.cpp','-o',library]
        process=subprocess.run([str(x) for x in command],capture_output=True,text=True);n.need(process.returncode==0,process.stdout+process.stderr)
    result=validate(library,a.resources.resolve(),a.core.resolve());a.out.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({k:result[k] for k in ('passed','checks','native_scenarios','functional_runs','game_access')}))
if __name__=='__main__':main()
