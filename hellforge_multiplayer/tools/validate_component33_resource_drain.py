"""Shared-owner queue draining and saved full UPDATE comparisons; offline only."""
import argparse,ctypes as c,json,struct,subprocess,sys
from pathlib import Path
import native_component33_image as n
import native_component33_resources as resource
import native_component33_resource_provider as provider
import validate_component33_resource_call as admission
import validate_component33_resource_services as services
import validate_component33_resources as r
import validate_component33_consumers as v
from native_component33_library import Library
SCENARIOS=('drain','blocked_one','blocked_max','empty_skips_sdk','global_unreadable','null_manager','flag_unreadable','code_mismatch','code_unreadable',
    'second_service_false','second_service_seh','service_mutation','resource_reentry','ignored_nested_fault','gate_seh','gate_mutation',
    'first_service_false','revision_exhausted','wrong_build','missing_service','full_512_queue','nested_owner','gate_changes_after_selection','drain_excludes_roster_reader')
def load(path):
    dll=c.CDLL(str(path.resolve()));dll.c33_resource_drain_test.argtypes=[c.c_uint];dll.c33_resource_drain_test.restype=c.c_uint
    dll.c33_resource_drain.argtypes=[c.POINTER(r.Binding),r.P,r.D,r.P,r.D,services.SERVICE,r.P];dll.c33_resource_drain.restype=c.c_int
    return dll
def arena(res,capacity,count,seed):
    raw=res.migrate_bytes(r.snapshot(seed=seed),capacity)
    rc,raw=res.reserve_bytes(raw,list(range(1,count+1)),capacity);n.need(rc==0,'queue setup capacity')
    out=bytearray(raw);struct.pack_into('<Q',out,32,count)
    for i in range(count):struct.pack_into('<Q',out,48+8*i,count-i)
    if count<capacity:struct.pack_into('<Q',out,48+8*(capacity-1),0xabcdef)
    return bytes(out)
class SavedDrain(r.Fixture):
    def __init__(self,lib,res,raw,capacity,blocked,active=0):
        super().__init__(lib,r.Images(res,capacity),'update',0,0,0,control=0,active=active)
        self.install(raw,res,capacity);f=resource.profile()['functions']['0x664520'];body=bytearray.fromhex(f['body_hex']);fixes=[]
        # Execute the entire saved function. Change only captured resource RIP
        # destinations and its queue-clear byte count, not branches or services.
        for ins in n.decode(bytes(body),f['start']):
            for op in ins.operands:
                if op.type==n.X86_OP_MEM and op.mem.base==n.X86_REG_RIP:
                    target=resource.target(self.arena,capacity,ins.address+ins.size+op.mem.disp)
                    if target is not None:
                        struct.pack_into('<i',body,ins.address-f['start']+ins.disp_offset,target-(self.game+ins.address+ins.size));fixes.append(ins.address)
            if ins.address==0x664b94:
                n.need(ins.operands[1].imm==1024,'saved queue clear size');struct.pack_into('<I',body,ins.address-f['start']+ins.imm_offset,capacity*8)
        n.need(fixes==[0x664b2f,0x664b50,0x664b89,0x664ba2],'drain source destinations')
        self.put(self.game+f['start'],bytes(body));self.start=self.game+f['start'];self.put(v.HEAP+0x190c,v.u32(blocked))
def validate(library,resources,core):
    dll=load(library);native=[];checks=0;runs=[];cases=[]
    def check(ok,name):
        nonlocal checks
        n.need(ok,name);checks+=1;cases.append(name)
    check(provider.HEADER.read_bytes()==provider.render(),'pinned_drain_tail_template')
    for mode,name in enumerate(SCENARIOS):
        p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode)],capture_output=True,text=True,timeout=30)
        n.need(p.returncode==0,name+': '+p.stdout+p.stderr);result=json.loads(p.stdout);checks+=result['checks'];native.append(dict(name=name,**result))
    res=r.Resources(resources);lib=Library(core)
    shapes=[(capacity,seed,count,blocked,0) for capacity in (128,512) for seed in (0,0xffffffff) for count in ((0,3,128) if capacity==128 else (0,3,129,512)) for blocked in (0,1)]
    shapes += [(128,1,3,0,1),(512,1,3,1,1)]
    for capacity,seed,count,blocked,active in shapes:
        raw=arena(res,capacity,count,seed);f=SavedDrain(lib,res,raw,capacity,blocked,active);expected=f.execute_resource()
        expected_calls=[(1,args[0]) for name,args in f.calls if name=='dispose'];clears=[args[:3] for name,args in f.calls if name=='clear_queue']
        data=c.create_string_buffer(raw,len(raw));scratch=c.create_string_buffer(len(raw));calls=[]
        @services.SERVICE
        def service(context,op,key):calls.append((op,key));return 1
        rc=0 if blocked else dll.c33_resource_drain(r.Binding(r.A,capacity,0),data,len(raw),scratch,len(raw),service,None)
        check(rc==0 and data.raw==expected,'complete_arena_equals_saved_update');check(calls==expected_calls,'exact_dispose_sequence')
        check(clears==([(r.A+48,0,capacity*8)] if count and not blocked else []),'full_queue_clear_condition')
        check(r.unpack(data.raw,capacity)[0]==r.unpack(raw,capacity)[0],'all_reference_buckets_preserved')
        runs.append(dict(capacity=capacity,seed=seed,queued=count,blocked=blocked,active=active,instructions=len(f.trace),whole_arena_equal=True,services_equal=True,services=len(calls)))
    for case in ('scratch_alias','scratch_short','invalid_queue','missing_service'):
        raw=arena(res,128,3,1)
        if case=='invalid_queue':raw=bytearray(raw);struct.pack_into('<Q',raw,32,129);raw=bytes(raw)
        data=c.create_string_buffer(raw,len(raw));scratch=c.create_string_buffer(len(raw));calls=[]
        @services.SERVICE
        def service(context,op,key):calls.append((op,key));return 1
        rc=dll.c33_resource_drain(r.Binding(r.A,128,0),data,len(raw),data if case=='scratch_alias' else scratch,len(raw)-8 if case=='scratch_short' else len(raw),services.SERVICE() if case=='missing_service' else service,None)
        check(rc!=0 and data.raw==raw and not calls,'preeffect_refusal_'+case)
    return dict(passed=True,checks=checks,native_scenarios=len(native),functional_runs=len(runs),game_access=False)
def main():
    ap=argparse.ArgumentParser()
    for k in ('zig','upstream','library','resources','core'):ap.add_argument('--'+k,type=Path)
    ap.add_argument('--worker',type=int);a=ap.parse_args();library=(a.library or n.PROJECT/'build/component33_resource_drain_test.dll').resolve()
    if a.worker is not None:print(json.dumps(dict(checks=load(library).c33_resource_drain_test(a.worker))));return
    if a.zig:
        command=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
            '-I',a.upstream.resolve()/'native/mod-sdk','-I',n.PROJECT/'mod/src','-shared',*(n.PROJECT/s for s in admission.SOURCES),n.PROJECT/'mod/src/ep_component33_resource_provider.cpp',n.PROJECT/'tests/component33_resource_drain_dll.cpp','-o',library]
        p=subprocess.run([str(x) for x in command],capture_output=True,text=True);n.need(p.returncode==0,p.stdout+p.stderr)
    print(json.dumps(validate(library,a.resources.resolve(),a.core.resolve())))
if __name__=='__main__':main()
