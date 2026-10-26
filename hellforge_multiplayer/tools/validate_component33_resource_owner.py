"""Own-process allocation/lifetime checks; actual prepared bytes in Unicorn only."""
import argparse,ctypes as c,hashlib,json,struct
from pathlib import Path
import native_component33_image as n
import native_component33_resources as r
import native_component33_consumers as consumer
import validate_component33_storage as st
import validate_component33_resources as rt
import validate_component33_images as core
from native_component33_library import Library
from validate_component33_family import U,D,P,Memory

class Config(c.Structure):_fields_=[('desired_address',U),('capacity',D),('reserved',D)]
class ResourceInfo(c.Structure):_fields_=[('binding',rt.Binding),('arena_bytes',D),('allocation_bytes',D),('windows',rt.Plan)]

def validate(path,resource_path,core_path):
    dll=c.CDLL(str(path.resolve()));resources=rt.Resources(resource_path);m=0x10001;checks=0;scenarios=[];runs=[]
    def check(ok,msg):
        nonlocal checks
        checks+=1;n.need(ok,msg)
    def fn(name,args,rest=c.c_int):
        f=getattr(dll,'c33_storage_'+name);f.argtypes=args;f.restype=rest;return f
    prepare=fn('prepare_resources',[P,c.POINTER(st.Bindings),c.POINTER(st.Snapshot),c.POINTER(Config),c.POINTER(rt.Snapshot),c.POINTER(st.Info)])
    legacy=fn('prepare',[P,c.POINTER(st.Bindings),c.POINTER(st.Snapshot),c.POINTER(st.Info)])
    info=fn('info',[P,U,c.POINTER(st.Info)]);ri=fn('resources',[P,U,c.POINTER(ResourceInfo)])
    cancel=fn('cancel',[P,U]);retain=fn('retain_resources',[P,U,c.POINTER(st.Snapshot),c.POINTER(rt.Snapshot)])
    old_retain=fn('retain',[P,U,c.POINTER(st.Snapshot)])
    faults=fn('faults',[c.POINTER(D)],None);counts=fn('counts',[c.POINTER(D)])
    kernel=c.WinDLL('kernel32');query=kernel.VirtualQuery;query.argtypes=[P,c.POINTER(Memory),c.c_size_t];query.restype=c.c_size_t
    nt=c.WinDLL('ntdll');lookup=nt.RtlLookupFunctionEntry;lookup.argtypes=[U,c.POINTER(U),P];lookup.restype=P
    def reset(**kw):
        a=(D*7)()
        for k,v in kw.items():a[int(k)]=v
        faults(a)
    def stats():
        a=(D*7)();check(counts(a)==0,'SDK hook called');return list(a)
    def bindings(shift=0):return st.Bindings(0x180000000+shift,0x1a0000000+shift,0x210000000+shift,(U*20)(*(0x190000000+shift+i*0x10000 for i in range(20))))
    def view(h):
        v=st.Info();q=ResourceInfo();check(info(m,h,v) and ri(m,h,q),'owner/query missing');return v,q
    def memory(p,state=0x1000,protect=None):
        q=Memory();check(query(p,q,c.sizeof(q)) and q.state==state and (protect is None or q.protect==protect),'page state/protection '+hex(p))
    def all_free(b,config):
        for p in [b.desired_storage,*b.desired_code,config.desired_address]:memory(p,0x10000)
    def prepared(v,b,s,config,snap,pinned=False):
        w,q=view(v.handle);check(w.state==(4 if pinned else 2) and w.family.reserved_images==20,'owner state')
        check(q.binding.address==config.desired_address and q.binding.capacity==config.capacity and q.arena_bytes==r.size(config.capacity),'resource placement')
        check(q.allocation_bytes==2*((q.arena_bytes+4095)//4096*4096),'resource allocation/baseline span')
        memory(q.binding.address,protect=4);memory(q.binding.address+q.allocation_bytes//2,protect=2);memory(w.storage_address,protect=4)
        expected=resources.migrate_bytes(snap,config.capacity,q.binding.address)
        check(c.string_at(q.binding.address,q.arena_bytes)==expected==c.string_at(q.binding.address+q.allocation_bytes//2,q.arena_bytes),'arena/baseline bytes')
        check(c.string_at(w.storage_address,0x490)==st.expected(s),'owned B mismatch')
        for i,code in enumerate(w.family.code):
            check(code.state==(7 if pinned else 2) and code.pinned==int(pinned) and code.registered==1,'code lifetime')
            memory(code.base,protect=0x20);base=U();check(lookup(code.base,base,None) and base.value==code.base,'unwind missing')
            if 15<=i<=18:
                a=dict(game_base=b.game_base,code_address=code.base,component_address=s.component_address,storage_address=w.storage_address,release_address=w.family.code[18].base,reject_address=b.reject_address)
                ref=r.consumer_image(consumer.KINDS[i-15],a,q.binding.address,config.capacity)
                check(c.string_at(code.base,code.bytes)==ref['image'],'prepared consumer differs from independent resource relocation')
        plan=r.windows(b.game_base,q.binding.address,config.capacity,w.family.code[7].base)
        check(q.windows.count==len(plan)==38,'resource windows missing')
        for x,y in zip(q.windows.windows,plan):
            check(x.rva==y['rva'] and x.bytes==y['bytes'] and bytes(x.expected[:x.bytes])==y['expected'] and bytes(x.replacement[:x.bytes])==y['replacement'],'resource/reset window mismatch')
        return q
    b=bindings();s=st.snapshot(4,4,2);config=Config(0x1b0000000,256,0);snap=rt.snapshot([(7,0),(9,3),(17,1)],[7])
    for cap in (128,256,1024,65536):
        config.capacity=cap;v=st.Info();reset();check(prepare(m,b,s,config,snap,v)==0,'prepare capacity '+str(cap));prepared(v,b,s,config,snap)
        check(stats()==[22,21,20,20,0,0,0],'prepare operations');check(cancel(m,v.handle),'cancel capacity');all_free(b,config);scenarios.append('owned_capacity_'+str(cap))
    config.capacity=256
    for kind in ('capacity','reserved','resource_snapshot','alignment','upper_address','null_config','null_snapshot'):
        cfg=Config.from_buffer_copy(config);snapshot=rt.Snapshot.from_buffer_copy(snap);v=st.Info();reset()
        if kind=='capacity':cfg.capacity=129
        elif kind=='reserved':cfg.reserved=1
        elif kind=='resource_snapshot':snapshot.queued=129
        elif kind=='alignment':cfg.desired_address+=16
        elif kind=='upper_address':cfg.desired_address=0x7ffffffff000
        rc=prepare(m,b,s,None if kind=='null_config' else cfg,None if kind=='null_snapshot' else snapshot,v)
        check(rc!=0 and v.handle==0 and stats()==[0]*7,'preflight accepted '+kind);scenarios.append('reject_'+kind)
    for target in (b.game_base+0x2000000,s.component_address,b.reject_address,b.desired_storage):
        cfg=Config(target,256,0);v=st.Info();reset();check(prepare(m,b,s,cfg,snap,v)!=0 and not v.handle,'overlap accepted')
        check(stats()[2:5]==[0,0,0],'overlap reached code');all_free(b,cfg);scenarios.append('reject_overlap_'+hex(target))
    # Every actual allocation, protection, registration and code-cache flush.
    for operation,total in ((0,22),(1,21),(2,20),(3,20)):
        for nth in range(1,total+1):
            v=st.Info();reset(**{str(operation):nth});check(prepare(m,b,s,config,snap,v)!=0 and not v.handle,'failed preparation leaked owner')
            all_free(b,config);stats();scenarios.append('prepare_failure_'+str((operation,nth)))
    for operation,total in ((4,20),(5,22)):
        for nth in range(1,total+1):
            v=st.Info();reset();check(prepare(m,b,s,config,snap,v)==0,'cleanup prepare');reset(**{str(operation):nth})
            check(not cancel(m,v.handle),'cleanup failure ignored');w,q=view(v.handle);check(w.state==3 and q.windows.count==0,'cleanup advertised installable plan')
            memory(w.storage_address,protect=4)
            if operation==4 or nth<=21:check(q.binding.address==config.desired_address,'arena released before dependent code');memory(q.binding.address,protect=4)
            else:check(q.binding.address==0 and q.arena_bytes==0 and q.allocation_bytes==0,'freed arena still published');memory(config.desired_address,0x10000)
            reset();check(cancel(m,v.handle),'cleanup retry');all_free(b,config);scenarios.append('cleanup_failure_'+str((operation,nth)))
    reset(**{'2':2,'4':0xffffffff});v=st.Info();check(prepare(m,b,s,config,snap,v)==10,'automatic cleanup failure not surfaced')
    w,q=view(v.handle);check(w.state==3 and q.binding.address==config.desired_address and q.windows.count==0,'automatic cleanup lost arena');memory(w.storage_address,protect=4);memory(q.binding.address,protect=4)
    reset();check(cancel(m,v.handle),'automatic cleanup retry');all_free(b,config);scenarios.append('prepare_and_cleanup_double_failure')
    # Resource globals have one owner per game base, including mixed old/new APIs.
    for first_resource in (False,True):
        reset();v=st.Info();check((prepare(m,b,s,config,snap,v) if first_resource else legacy(m,b,s,v))==0,'conflict setup')
        b2=bindings(0x40000000);b2.game_base=b.game_base;s2=st.snapshot(4,4,2,component=s.component_address+0x40000000);q=st.Info();cfg=Config(config.desired_address+0x40000000,256,0);reset()
        check(prepare(m,b2,s2,cfg,snap,q)==12 and not q.handle and stats()==[0]*7,'second global resource owner accepted')
        if first_resource:check(legacy(m,b2,s2,q)==12,'legacy bypassed global owner');check(old_retain(m,v.handle,s)==1,'legacy retain bypassed resource freshness')
        else:check(retain(m,v.handle,s,snap)==1,'resource retain accepted legacy owner');out=ResourceInfo();check(not ri(m,v.handle,out) and bytes(out)==bytes(c.sizeof(out)),'legacy resource query')
        check(cancel(m,v.handle),'conflict cleanup');all_free(b,config);scenarios.append('same_game_conflict_'+str(first_resource))
    # Changed inputs/owned bytes are retryable and cause zero irreversible pins.
    reset();v=st.Info();check(prepare(m,b,s,config,snap,v)==0,'freshness setup');q=prepared(v,b,s,config,snap)
    before=c.string_at(q.binding.address,q.arena_bytes);old_b=c.string_at(v.storage_address,0x490)
    for fault in ('component','resource_reference','resource_queue','resource_seed','owned_B','owned_arena','invalid_resource'):
        fresh=st.Snapshot.from_buffer_copy(s);fresh_r=rt.Snapshot.from_buffer_copy(snap);reset()
        if fault=='component':fresh.component[0x90]^=1
        elif fault=='resource_reference':fresh_r=rt.snapshot([(7,0),(9,4),(17,1)],[7])
        elif fault=='resource_queue':fresh_r.queued=0
        elif fault=='resource_seed':fresh_r=rt.snapshot([(7,0),(9,3),(17,1)],[7],seed=1)
        elif fault=='owned_B':c.c_ubyte.from_address(v.storage_address+0x90).value^=1
        elif fault=='owned_arena':c.c_ubyte.from_address(q.binding.address+q.arena_bytes-1).value^=1
        else:fresh_r.queued=129
        check(retain(m,v.handle,fresh,fresh_r)==(13 if fault=='invalid_resource' else 7),'stale resource owner accepted '+fault)
        check(stats()==[0]*7 and view(v.handle)[0].state==2,'stale request changed lifetime')
        c.memmove(v.storage_address,old_b,len(old_b));c.memmove(q.binding.address,before,len(before));scenarios.append('freshness_'+fault)
    wrong=ResourceInfo();check(not ri(m+1,v.handle,wrong) and not cancel(m+1,v.handle) and retain(m+1,v.handle,s,snap)==11,'owner isolation')
    check(retain(m,v.handle,s,None)==1 and old_retain(m,v.handle,s)==1,'freshness API missing snapshot')
    reset(**{'6':1});check(retain(m,v.handle,s,snap)==9,'pin failure not returned');w,q=view(v.handle)
    check(w.state==2 and all(x.state==2 and not x.pinned for x in w.family.code),'partial lifetime after pin failure')
    reset();check(cancel(m,v.handle),'pin failure cleanup');all_free(b,config);scenarios.append('pin_failure_atomic_retryable')
    # Execute COPIES of real resource-bound prepared code and owned migration.
    # All game services remain the existing synthetic fixture; no native call
    # into generated game code, and no game process or game memory is touched.
    lib=Library(core_path);game=0x180000000;new_b=0x18500800000
    core.B=rt.B=rt.v.B=new_b
    code=[game+0x10400000+i*0x10000 for i in range(len(n.ALL_KINDS))]
    code += [game+0x10a00000]+[rt.v.params(k,game)['code_address'] for k in consumer.KINDS]+[game+0x10d00000]
    b=st.Bindings(game,game+core.REJECT-core.G,new_b,(U*20)(*code));config=Config(game+rt.A-rt.G,256,0)
    seed=rt.Fixture(lib,rt.Images(resources,256,config.desired_address),'acquire',4,4,2,game=game,ordinal=3)
    source=st.Snapshot();source.component_address=source.global_component=core.S;source.invalid_entity_id=0xffffffff;source.entity_count=4;source.component[:]=seed.read(core.S,0x2b8)
    for i in range(4):
        for new,old,size in core.LAYOUT.values():source.component[old+i*size:old+(i+1)*size]=seed.read(new_b+new+i*size,size)
        source.entities[i]=st.Entity(core.E+64*i,struct.unpack('<I',seed.read(core.E+64*i+8,4))[0],struct.unpack('<I',seed.read(core.E+64*i+20,4))[0])
    # The generic fixture's map descriptor and placement use seed=1.
    snap=rt.snapshot([(0x50000+i,1+i%3) for i in range(128)]);v=st.Info();reset()
    check(prepare(m,b,source,config,snap,v)==0,'instruction integration prepare');q=prepared(v,b,source,config,snap)
    class ActualImages:
        def build(self,kind,**a):
            image=v.family.code[15+consumer.KINDS.index(kind)];ref=r.consumer_image(kind,a,q.binding.address,256)
            raw=c.string_at(image.base,image.bytes);check(image.base==a['code_address'] and raw==ref['image'],'fixture did not use prepared bytes');ref['image']=raw;return ref
    for kind in ('acquire','release'):
        f=rt.Fixture(lib,ActualImages(),kind,4,4,2,game=game,ordinal=3)
        f.put(core.S,bytes(source.component));f.put(new_b,c.string_at(v.storage_address,0x490));f.header=f.read(core.S+4,0x6c);f.old=f.read(core.S+0x70,0x248)
        raw=c.string_at(q.binding.address,q.arena_bytes)
        if kind=='release':raw=resources.migrate_bytes(rt.snapshot([(0x10001+3*128,1)]),256,q.binding.address)
        else:
            rc,raw=resources.reserve_bytes(raw,[0x10001+3*128],256,q.binding.address);check(rc==0,'explicit complete-key admission')
        f.install(raw,resources,256);result=f.execute_resource();rows,queue=rt.unpack(result,256)
        if kind=='acquire':check(sum(name=='load' for name,args in f.calls)==1 and rows[0x10001+3*128]==1 and len(rows)==129,'prepared acquire semantics')
        else:check(rows[0x10001+3*128]==0 and queue==[0x10001+3*128],'prepared release semantics')
        check(c.string_at(q.binding.address,q.arena_bytes)==resources.migrate_bytes(snap,256,q.binding.address),'Unicorn changed host allocation')
        runs.append({'kind':kind,'instructions':len(f.trace),'uses_actual_prepared_bytes':True,'host_arena_unchanged':True})
    # Ignore inactive queue tail; preserve every other prepared byte.
    fresh_r=rt.Snapshot.from_buffer_copy(snap);fresh_r.queue[127]=0x777;reset();check(retain(m,v.handle,source,fresh_r)==0,'resource retain rejected unchanged meaningful snapshot')
    check(stats()==[0,0,0,0,0,0,1],'retention operations');q=prepared(v,b,source,config,snap,True)
    check(not cancel(m,v.handle) and retain(m,v.handle,source,snap)==11,'retained owner became cancellable');scenarios.append('whole_owner_retained_with_inactive_tail')
    free=kernel.FreeLibrary;free.argtypes=[P];free.restype=c.c_int;check(free(dll._handle),'FreeLibrary')
    q=prepared(v,b,source,config,snap,True);check(stats()[-1]==1,'retained module not pinned');scenarios.append('retained_B_arena_baseline_code_survive_FreeLibrary')
    return dict(passed=True,checks=checks,scenarios=scenarios,scenarios_count=len(scenarios),instruction_runs=runs,capacities=[128,256,1024,65536],code_images=20,component_windows=8,resource_windows=38,
        real_allocations=True,real_page_protection=True,real_unwind_registration=True,real_module_pin=True,game_access=False,hooks_installed=0,
        limits=['Supplied snapshots and own allocations only; no embedded game-resource ownership transferred.','This ownership fixture does not exercise whole-call demand admission; the separate resource-call receipt covers that scoped integration. Reset timing and production publication remain unimplemented.','No native game-code invocation, native UI validation, fifth client, eight-client mission or installable multiplayer completion.'])

def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--resources',type=Path,required=True);p.add_argument('--core',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=validate(a.library,a.resources,a.core);root=Path(__file__).resolve().parents[1]
    sources=['mod/src/ep_component33_storage.h','mod/src/ep_component33_storage.cpp','mod/src/ep_component33_family.h','mod/src/ep_component33_family.cpp',
        'mod/src/ep_component33_resources.h','mod/src/ep_component33_resources.cpp','mod/src/ep_component33_resources_template.h','mod/src/ep_session_code.cpp','mod/src/ep_session_code.h',
        'tests/component33_storage_dll.cpp','tools/validate_component33_resource_owner.py','tools/validate_component33_storage.py','tools/validate_component33_family.py',
        'tools/validate_component33_resources.py','tools/native_component33_resources.py','tools/validate_component33_consumers.py','tools/native_component33_consumers.py','tools/validate_component33_images.py','tools/native_component33_image.py','tools/native_component33_library.py']
    references=['native-component33-storage-validation.json','native-component33-resources-validation.json','native-component33-validation.json']
    for name in references:sources+=list(json.loads((root/'evidence'/name).read_bytes())['source_sha256'])
    result['schema']='hellforge_component33_resource_owner_validation_v1'
    result['source_sha256']={name:hashlib.sha256((root/name if (root/name).is_file() else root.parent/name).read_bytes()).hexdigest() for name in dict.fromkeys(sources)}
    result['reference_validation_sha256']={name:hashlib.sha256((root/'evidence'/name).read_bytes()).hexdigest() for name in references}
    result['artifacts']={x.name:dict(bytes=x.stat().st_size,sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (a.library,a.resources,a.core)}
    a.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:result[k] for k in ('passed','checks','scenarios_count','code_images','resource_windows','game_access')}))
if __name__=='__main__':main()
