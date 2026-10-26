"""Frozen resource execution: real owned storage plus saved acquire equivalence.

All service callbacks and package/threshold providers are synthetic. Native
code touches only this test's allocations; saved game bodies run in Unicorn.
"""
import argparse,ctypes as c,json,struct,subprocess,sys
from pathlib import Path
import native_component33_image as n
import validate_component33_resource_call as admission
import validate_component33_resources as r
import validate_component33_consumers as v
from native_component33_library import Library
from validate_component33_images import reg

SCENARIOS=('frozen_mixed_resources','dispose_refusal','load_refusal','dispose_seh','load_seh',
    'service_mutates_arena','service_reentry','ignored_nested_owner_failure','provider_snapshot_mutated',
    'capacity_before_services','no_entity','provider_unavailable','load_scope_blocks_roster')
SERVICE=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_uint32,c.c_uint64)

def load(path):
    dll=admission.load(path)
    dll.c33_resource_service_test.argtypes=[c.c_uint];dll.c33_resource_service_test.restype=c.c_uint
    dll.c33_resource_execute.argtypes=[c.POINTER(r.Binding),r.P,r.D,c.POINTER(r.U),r.D,c.POINTER(r.U),r.D,r.P,r.D,SERVICE,r.P]
    dll.c33_resource_execute.restype=c.c_int
    return dll

class Fixture(r.Fixture):
    def on_code(self,uc,pc,size,data):
        tag=uc.reg_read(reg('r8')) if getattr(self,'ready',False) and pc==self.game+0x7af0a0 else None
        super().on_code(uc,pc,size,data)
        if tag is not None:uc.reg_write(reg('rax'),self.thresholds[tag-1])

def validate(library,resources,core):
    dll=load(library);native=[];checks=0;runs=[];cases=[]
    def check(ok,name):
        nonlocal checks
        n.need(ok,name);checks+=1;cases.append(name)
    for i,name in enumerate(SCENARIOS):
        p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(i)],capture_output=True,text=True,timeout=30)
        n.need(p.returncode==0,'native services scenario '+name+': '+p.stdout+p.stderr)
        result=json.loads(p.stdout);checks+=result['checks'];native.append(dict(name=name,**result))
    res=r.Resources(resources);lib=Library(core)
    # Compare whole arena bytes AND exact service order against saved acquire
    # (including its release call), not a second implementation of the loop.
    for seed in (0,1,0xffffffff):
        for cap in (128,512):
            s=admission.Snapshot();s.thresholds[:]=[100,50,0,0x80000000,0,0xffffffff]
            rows=[(0,101,100,100),(0,102,101,101),(0,103,0,200),(0,101,0,200),
                  (0,104,0,10),(1,105,0,100),(1,106,0,100),(2,107,0,0xffffffff),
                  (3,108,0x80000000,0xffffffff),(5,109,0xffffffff,0xffffffff)]
            indexes=[0]*6
            for g,key,lower,upper in rows:
                off=g*0x808+indexes[g]*0x20;indexes[g]+=1
                struct.pack_into('<Q',s.package,off,key);struct.pack_into('<II',s.package,off+16,upper,lower)
            for g in (0,1,3,5):struct.pack_into('<I',s.package,g*0x808+0x800,g+1)
            d=admission.Demand();check(dll.c33_acquire_demand(s,d)==1,'collect_mixed')
            refs=[1,2,0,1,1,0,2,1,0,0];initial=res.migrate_bytes(r.snapshot(list(zip(range(101,111),refs)),[103,109,110],seed),cap)
            acquired=list(d.keys[:d.count]);released=[key for g,key,lo,hi in rows if g!=2]
            rc,raw=res.reserve_bytes(initial,acquired,cap);check(rc==0,'admit_mixed')
            f=Fixture(lib,r.Images(res,cap),'acquire',8,8,4,ordinal=7)
            f.thresholds=list(s.thresholds);f.ready=True;f.put(v.PKG+7*0x4000,bytes(s.package));f.install(raw,res,cap)
            expected=f.execute_resource();expected_calls=[(1 if name=='dispose' else 2,args[0]) for name,args in f.calls if name in ('dispose','load')]
            arena=c.create_string_buffer(raw,len(raw));scratch=c.create_string_buffer(len(raw));calls=[]
            old=(r.U*len(released))(*released);new=(r.U*len(acquired))(*acquired)
            @SERVICE
            def service(context,operation,key):
                calls.append((operation,key))
                # Provider-owned input may change after the first service.
                c.memset(old,0,c.sizeof(old));c.memset(new,0,c.sizeof(new));return 1
            rc=dll.c33_resource_execute(r.Binding(r.A,cap,0),arena,len(raw),old,len(old),new,len(new),scratch,len(raw),service,None)
            check(rc==0 and arena.raw==expected,'full_arena_equals_saved_acquire')
            check(calls==expected_calls and len(calls)==8,'service_order_equals_saved_acquire')
            check(r.unpack(arena.raw,cap)==({101:2,102:1,103:1,104:0,105:1,106:1,107:2,108:1,109:1,110:0},[110]),'unfiltered_release_and_queued_reacquire')
            runs.append(dict(capacity=cap,seed=seed,source_rva='0x6656c0',release_rva='0x6659e0',instructions=len(f.trace),services=len(calls),whole_arena_equal=True,provider_sequences_mutated=True))
    # Refusal must happen before even the first DISPOSE, including partial
    # valid prefixes followed by a missing/zero/overflowing acquisition.
    for case in ('missing_later','zero_acquire','zero_release','overflow','scratch_alias','source_alias','too_many'):
        raw=res.migrate_bytes(r.snapshot([(101,1),(102,2**64-1 if case=='overflow' else 1)]),128)
        arena=c.create_string_buffer(raw,len(raw));scratch=c.create_string_buffer(len(raw));calls=[]
        old=(r.U*2)(101,0 if case=='zero_release' else 102)
        new=(r.U*2)(101,999 if case=='missing_later' else 0 if case=='zero_acquire' else 102)
        @SERVICE
        def service(context,operation,key):calls.append((operation,key));return 1
        rc=dll.c33_resource_execute(r.Binding(r.A,128,0),arena,len(raw),old,2,
            c.cast(arena,c.POINTER(r.U)) if case=='source_alias' else new,385 if case=='too_many' else 2,
            arena if case=='scratch_alias' else scratch,len(raw),service,None)
        check(rc!=0 and not calls and arena.raw==raw,'atomic_preflight_'+case)
    sources=set(['tools/validate_component33_resource_services.py']);references={}
    for name in ('native-component33-resource-call-validation.json','native-component33-resources-validation.json'):
        path=n.PROJECT/'evidence'/name;data=json.loads(path.read_bytes());sources.update(data.get('source_sha256',{}));references[name]=n.sha(path.read_bytes())
    return dict(schema='hellforge_component33_resource_services_validation_v1',passed=True,checks=checks,
        native_scenarios=len(native),scenarios=native,functional_runs=len(runs),runs=runs,cases=cases,
        frozen_snapshot_execution=True,full_release_then_filtered_acquire=True,queued_reacquire_verified=True,
        complete_arena_and_service_trace_match_saved_source=True,shared_retained_resource_roster_scope=True,
        service_failure_stops_sequence=True,ignored_nested_owner_fault_stops_sequence=True,
        callback_mutation_quarantines=True,callback_seh_quarantines=True,callback_compensation=False,
        production_snapshot_provider_bound=False,production_resource_services_bound=False,original_entry_routing_bound=False,
        all_game_writers_covered=False,safe_reset_lifecycle_verified=False,native_game_bodies_invoked=False,
        installed=False,game_access=False,runtime_verified=False,multiplayer_verified=False,
        source_sha256={s:n.sha((n.PROJECT/s if (n.PROJECT/s).exists() else n.PROJECT.parent/s).read_bytes()) for s in sorted(sources)},
        reference_validation_sha256=references,
        artifacts={p.name:dict(bytes=p.stat().st_size,sha256=n.sha(p.read_bytes())) for p in (library,resources,core)},
        limitations=['Saved instruction comparisons use stable synthetic package, threshold and service helpers.',
            'The six-group frozen package replaces two original package lookups; runtime provider coherence and helper side effects remain unverified.',
            'Owned native scenarios and Unicorn source comparisons are separate tests, not execution of game bodies inside the native owner.',
            'Service failures quarantine after partial effects; no rollback or recovery is claimed.',
            'A full resource-arena copy and comparison surrounds every external service; game performance is unmeasured.',
            'No game, installation, process or memory access; production ABI, entry routing and reset lifecycle remain unbound.'])

def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--resources',type=Path);p.add_argument('--core',type=Path);p.add_argument('--out',type=Path);p.add_argument('--worker',type=int);a=p.parse_args()
    if a.worker is not None:print(json.dumps(dict(checks=load(a.library).c33_resource_service_test(a.worker))));return
    result=validate(a.library,a.resources,a.core);a.out.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({k:result[k] for k in ('passed','checks','native_scenarios','functional_runs','game_access')}))

if __name__=='__main__':main()
