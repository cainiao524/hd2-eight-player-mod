"""Owned resource admission in the real shared scope; no game access.

The native callbacks are synthetic. Independently compare the collector with
actual saved acquire instructions in Unicorn, including all six groups.
"""
import argparse,collections,ctypes as c,json,struct,subprocess,sys
from pathlib import Path
import native_component33_image as n
import native_component33_consumers as consumer
import validate_component33_consumers as v
import validate_component33_resources as r
from native_component33_library import Library
from validate_component33_images import reg

class Snapshot(c.Structure):
    _fields_=[('package',c.c_ubyte*0x3030),('thresholds',c.c_uint32*6)]
class Demand(c.Structure):
    _fields_=[('count',c.c_uint32),('reserved',c.c_uint32),('keys',c.c_uint64*384)]

SCENARIOS=('complete_384','capacity_refusal','collect_scope_blocks_roster','execute_scope_blocks_roster',
    'execute_seh','collect_seh','collect_reentry','collect_mutates_arena','snapshot_unavailable',
    'no_match','execute_failure','execute_reentry','close_drains','prepared_refused','wrong_game',
    'scratch_allocation_failure','nested_roster_scope','duplicate_384','revision_exhausted','execute_corrupts_arena')
SOURCES=['mod/src/'+s for s in ('ep_session_code.cpp','ep_component33_storage.cpp','ep_component33_family.cpp',
    'ep_component33_image.cpp','ep_component33_readers.cpp','ep_component33_consumers.cpp',
    'ep_component33_outer.cpp','ep_component33_resources.cpp','ep_roster_call.cpp','ep_player_join_call.cpp')]

def load(path):
    dll=c.CDLL(str(path.resolve()));f=dll.c33_acquire_demand
    f.argtypes=[c.POINTER(Snapshot),c.POINTER(Demand)];f.restype=c.c_int
    dll.c33_resource_call_test.argtypes=[c.c_uint];dll.c33_resource_call_test.restype=c.c_uint
    return dll

def validate(library,resources,core):
    dll=load(library);native=[];checks=0;runs=[]
    for i,name in enumerate(SCENARIOS):
        p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(i)],capture_output=True,text=True,timeout=30)
        n.need(p.returncode==0,'native scope scenario '+name+': '+p.stdout+p.stderr)
        result=json.loads(p.stdout);checks+=result['checks'];native.append(dict(name=name,**result))
    class Fixture(r.Fixture):
        def on_code(self,uc,pc,size,data):
            if getattr(self,'sampling',False):
                if pc==self.qualifier:self.selected.append(uc.reg_read(reg('r8')))
                tag=uc.reg_read(reg('r8')) if pc==self.game+0x7af0a0 else None
            else:tag=None
            super().on_code(uc,pc,size,data)
            if tag is not None:uc.reg_write(reg('rax'),self.thresholds[tag-1])
    res=r.Resources(resources);lib=Library(core)
    for case in ('all_384','unsigned_bounds_duplicates','disabled_groups'):
        s=Snapshot();s.thresholds[:]=[0,1,100,0x7fffffff,0x80000000,0xffffffff]
        for g,value in enumerate(s.thresholds):
            struct.pack_into('<I',s.package,g*0x808+0x800,0 if case=='disabled_groups' and g%2 else g+1)
            for row in range(64):
                key=999+g*64+row;upper=lower=value
                if case=='unsigned_bounds_duplicates':
                    key=999+row%11
                    upper,lower=((value,value),(0xffffffff,0),(0,0),(0xffffffff,0xffffffff),(0x7fffffff,0x80000000),(0xffffffff,value))[row%6]
                    if row%7==0:key=0
                offset=g*0x808+row*0x20;struct.pack_into('<Q',s.package,offset,key);struct.pack_into('<II',s.package,offset+16,upper,lower)
        before=bytes(s);d=Demand();n.need(dll.c33_acquire_demand(s,d)==1 and bytes(s)==before and not d.reserved,'pure collector changed source');checks+=1
        keys=list(d.keys[:d.count]);n.need(not any(d.keys[d.count:]),'unused demand slots');checks+=1
        images=r.Images(res,512);f=Fixture(lib,images,'acquire',8,8,4,ordinal=7)
        f.thresholds=list(s.thresholds);f.selected=[];f.qualifier=v.params('acquire')['code_address']+f.images['acquire']['instruction_map'][0x6657d0];f.sampling=True
        f.put(v.PKG+7*0x4000,bytes(s.package))
        raw=res.migrate_bytes(r.snapshot(seed=1),512);rc,raw=res.reserve_bytes(raw,keys,512);n.need(rc==0,'complete demand refused');checks+=1
        f.install(raw,res,512);after=f.execute_resource();counts,queue=r.unpack(after,512)
        n.need(keys==f.selected,'collector differs from saved acquire source '+case);checks+=1
        n.need(counts==dict(collections.Counter(keys)) and not queue,'saved acquire reference totals');checks+=1
        if case=='all_384':n.need(d.count==384 and len(set(keys))==384,'not all six groups');checks+=1
        runs.append(dict(case=case,keys=d.count,unique=len(set(keys)),instructions=len(f.trace),source_rva='0x6656c0',source_selection_rva='0x6657d0'))
    d=Demand();c.memset(c.byref(d),0xa5,c.sizeof(d));n.need(dll.c33_acquire_demand(None,d)==0 and not any(bytes(d)) and dll.c33_acquire_demand(Snapshot(),None)==0,'null collector');checks+=1
    sources=set(SOURCES+['mod/src/ep_component33_resource_call.cpp','mod/src/ep_component33_resource_call.h',
        'mod/src/ep_roster_owner.cpp','mod/src/ep_roster_owner.h','mod/src/ep_native_roster.cpp','mod/src/ep_native_roster.h','mod/src/ep_roster_api.h',
        'tests/component33_resource_call_dll.cpp','tools/validate_component33_resource_call.py'])
    references={}
    for name in ('native-component33-resource-owner-validation.json','native-component33-resources-validation.json'):
        path=n.PROJECT/'evidence'/name
        if path.exists():
            data=json.loads(path.read_bytes());sources.update(data.get('source_sha256',{}));sources.update(data.get('test_source_sha256',{}));references[name]=n.sha(path.read_bytes())
    # Explicit headers capture transitive production dependencies even when a
    # preceding receipt owns a narrower test fixture.
    sources.update(p.relative_to(n.PROJECT).as_posix() for p in (n.PROJECT/'mod/src').glob('ep_component33*.h'))
    return dict(schema='hellforge_component33_resource_call_validation_v1',passed=True,checks=checks,
        native_scenarios=len(native),scenarios=native,functional_runs=len(runs),runs=runs,
        retained_resource_owner_bound=True,shared_roster_whole_call_scope=True,complete_six_group_demand=True,
        pre_effect_admission=True,refusal_preserves_arena_and_revision=True,callback_seh_quarantines=True,
        native_execution_of_game_bodies=False,production_demand_provider_bound=False,production_resource_services_bound=False,
        automatic_entry_hooks_bound=False,all_game_writers_covered=False,safe_reset_lifecycle_verified=False,
        installed=False,game_access=False,runtime_verified=False,multiplayer_verified=False,
        source_sha256={p:n.sha((n.PROJECT/p if (n.PROJECT/p).is_file() else n.PROJECT.parent/p).read_bytes()) for p in sorted(sources)},reference_validation_sha256=references,
        artifacts={p.name:dict(bytes=p.stat().st_size,sha256=n.sha(p.read_bytes())) for p in (library,resources,core)},
        limits=['Call-scoped integration is invoked with owned-memory callbacks, not native game providers or hooks.',
            'Executor must consume the admitted snapshot; replaying original acquire with independent lookups does not meet this contract.',
            'Saved-source comparison uses stubbed external services in Unicorn.',
            'Two arena-sized heap buffers per call are temporary; runtime allocation/performance has not been measured.',
            'Reset lifetime and other game writers/readers still require integration; callback failure is quarantine, not rollback.'])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('zig','upstream','library','resources','core','out'):p.add_argument('--'+name,type=Path)
    p.add_argument('--worker',type=int);a=p.parse_args()
    if a.worker is not None:
        print(json.dumps(dict(passed=True,checks=load(a.library).c33_resource_call_test(a.worker))));return
    library=(a.library or n.PROJECT/'build/component33_resource_call_test.dll').resolve()
    if a.zig:
        command=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
            '-I',a.upstream.resolve()/'native/mod-sdk','-I',n.PROJECT/'mod/src','-shared',
            *(n.PROJECT/s for s in SOURCES),n.PROJECT/'tests/component33_resource_call_dll.cpp','-o',library]
        result=subprocess.run([str(x) for x in command],capture_output=True,text=True);n.need(result.returncode==0,result.stdout+result.stderr)
    result=validate(library,a.resources.resolve(),a.core.resolve());a.out.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({k:result[k] for k in ('passed','checks','native_scenarios','functional_runs','game_access')}))

if __name__=='__main__':main()
