"""Native resource admission plus saved consumer/reset/registry execution."""
import argparse,ctypes as c,json,struct,subprocess
from pathlib import Path
import native_component33_resources as resource
import native_component33_consumers as consumer
import native_component33_image as n
import validate_component33_consumers as v
import validate_component33_outer as outer
from native_component33_library import Library,Image
from validate_component33_images import G,S,B,E,RSP,STACK,SEEDS,reg,u32,u64

A=G+0x12000000;RESET=G+0x12100000
U=c.c_uint64;D=c.c_uint32;P=c.c_void_p
class Binding(c.Structure):_fields_=[('address',U),('capacity',D),('reserved',D)]
class Entry(c.Structure):_fields_=[('key',U),('references',U)]
class Snapshot(c.Structure):_fields_=[('seed',D),('reserved',D),('queued',U),('entries',Entry*128),('queue',U*128)]
class Window(c.Structure):_fields_=[('rva',D),('bytes',D),('expected',c.c_ubyte*16),('replacement',c.c_ubyte*16)]
class Plan(c.Structure):_fields_=[('count',D),('reserved',D),('windows',Window*48)]
def snapshot(entries=(),queue=(),seed=2):
    s=Snapshot();s.seed=seed;s.queued=len(queue)
    for key,refs in entries:
        for j in range(128):
            at=(key*seed+j)&127
            if not s.entries[at].key:s.entries[at]=Entry(key,refs);break
        else:raise ValueError('snapshot full')
    for j,key in enumerate(queue):s.queue[j]=key
    return s
def unpack(raw,capacity):
    rows=dict((key,refs) for key,refs in struct.iter_unpack('<QQ',raw[48+8*capacity:]) if key)
    count=struct.unpack_from('<Q',raw,32)[0];queue=list(struct.unpack_from('<'+'Q'*count,raw,48))
    return rows,queue

class Resources:
    def __init__(self,path):
        self.path=path.resolve();self.dll=c.CDLL(str(self.path))
        signatures={'migrate':[c.POINTER(Binding),c.POINTER(Snapshot),P,D],'validate':[c.POINTER(Binding),P,D],
            'reserve':[c.POINTER(Binding),P,D,c.POINTER(U),D,P,D],
            'consumer':[D,c.POINTER(v.Addresses),c.POINTER(Binding),c.POINTER(Image)],'windows':[U,c.POINTER(Binding),U,c.POINTER(Plan)]}
        for name,args in signatures.items():
            f=getattr(self.dll,'c33_resource_'+name);f.argtypes=args;f.restype=c.c_int;setattr(self,name,f)
    def migrate_bytes(self,s,capacity=256,address=A):
        b=Binding(address,capacity,0);out=c.create_string_buffer(resource.size(capacity));n.need(self.migrate(b,s,out,len(out))==0,'migration failed');return out.raw
    def validate_bytes(self,raw,capacity=256,address=A):
        return self.validate(Binding(address,capacity,0),c.create_string_buffer(raw,len(raw)),len(raw))
    def reserve_bytes(self,raw,keys,capacity=256,address=A):
        b=Binding(address,capacity,0);out=c.create_string_buffer(raw,len(raw));scratch=c.create_string_buffer(len(raw));keys=(U*len(keys))(*keys)
        result=self.reserve(b,out,len(raw),keys,len(keys),scratch,len(raw));return result,out.raw
    def window_plan(self,game=G,capacity=256,address=A):
        p=Plan();n.need(self.windows(game,Binding(address,capacity,0),game+RESET-G,p)==0,'window refused')
        expected=resource.windows(game,address,capacity,game+RESET-G);n.need(p.count==len(expected),'window count')
        for w,r in zip(p.windows,expected):
            n.need(w.rva==r['rva'] and w.bytes==r['bytes'] and bytes(w.expected[:w.bytes])==r['expected'] and bytes(w.replacement[:w.bytes])==r['replacement'],'window mismatch')
        return expected
class Images:
    def __init__(self,resources,capacity=256,address=A):self.resources=resources;self.capacity=capacity;self.address=address;self.path=resources.path
    def build(self,kind,**a):
        r=resource.consumer_image(kind,a,self.address,self.capacity);out=Image()
        n.need(self.resources.consumer(consumer.KINDS.index(kind)+1,v.Addresses(**a),Binding(self.address,self.capacity,0),out)==0,'native resource image refused')
        n.need(bytes(out.data[:out.bytes])==r['image'],'resource image mismatch')
        n.need(all(getattr(out,k)==r[k] for k in ('code_bytes','unwind_offset','table_offset','function_count')),'resource metadata changed')
        return r
class Checks:
    def install(self,raw,resources,capacity,*,external=False):
        self.arena=self.game+A-G;self.capacity=capacity;self.resources=resources;self.reset_calls=0
        n.need(resources.validate_bytes(raw,capacity,self.arena)==0,'input arena invalid');self.put(self.arena,raw)
        self.put(self.arena-16,b'\xa5'*16);self.put(self.arena+len(raw),b'\xa5'*16)
        self.original_resources=[(p,self.read(p,z)) for p,z in ((self.game+0x3797550,1024),(self.game+0x3797960,2048),(self.game+0x3798180,28),(self.game+0x348ba88,8),(v.TABLE,2048))]
        if external:
            for w in resources.window_plan(self.game,capacity,self.arena):
                p=self.game+w['rva'];n.need(self.read(p,w['bytes'])==w['expected'],'source window bytes');self.put(p,w['replacement'])
    def on_code(self,uc,pc,size,data):
        if pc==self.game+RESET-G:
            self.reset_calls+=1;sp=uc.reg_read(reg('rsp'));uc.reg_write(reg('rip'),struct.unpack('<Q',self.read(sp,8))[0]);uc.reg_write(reg('rsp'),sp+8);return
        # Existing unwind tests cover these byte-identical frames. Collect only
        # service effects here; address-only patches introduce no stack changes.
        saved=self.original;self.original=True
        try:super().on_code(uc,pc,size,data)
        finally:self.original=saved
    def execute_resource(self):
        self.uc.emu_start(self.start,0,count=2000000);n.need(self.outcome=='return','resource execution did not return')
        n.need(self.uc.reg_read(reg('rsp'))==RSP+8,'resource return stack')
        for k,x in SEEDS.items():n.need(self.uc.reg_read(reg(k))==x,'resource nonvolatile '+k)
        for i in range(6,16):n.need(self.uc.reg_read(reg('xmm'+str(i)))==(0x1122334455667788+i)*(1+(1<<64)),'resource nonvolatile XMM')
        n.need(self.read(S+4,0x6c)==self.header and self.read(S+0x70,0x248)==self.old,'component changed')
        n.need(not any(a<S+0x2b8 and S+0x70<a+z for a,z in self.reads),'resource path used old component array')
        for p,old in self.original_resources:n.need(self.read(p,len(old))==old,'old resource globals mutated')
        for a,z in self.reads:n.need(not any(a<p+len(old) and p<a+z for p,old in self.original_resources),'old resource globals read')
        n.need(self.read(self.arena-16,16)==b'\xa5'*16 and self.read(self.arena+resource.size(self.capacity),16)==b'\xa5'*16,'resource canary')
        allowed=[(STACK,0x10000),(S,2),(B,0x490),(self.arena,resource.size(self.capacity))]
        for a,z in self.writes:n.need(any(lo<=a and a+z<=lo+length for lo,length in allowed),'resource write escaped '+hex(a))
        raw=self.read(self.arena,resource.size(self.capacity));n.need(self.resources.validate_bytes(raw,self.capacity,self.arena)==0,'result arena invalid');return raw
class Fixture(Checks,v.Fixture):pass
class OuterFixture(Checks,outer.Fixture):pass

def validate(resources,lib,legacy,bridge):
    n.need(resource.HEADER.read_bytes()==resource.render(),'resource template stale');cases=[];runs=[]
    def check(ok,name):n.need(ok,name);cases.append(name)
    live=[(0x50000+i,1+i%3) for i in range(128)]
    for cap in (128,256,1024):
        for seed in (0,1,2,0xffffffff):
            s=snapshot(live,seed=seed);raw=resources.migrate_bytes(s,cap);check(resources.validate_bytes(raw,cap)==0 and unpack(raw,cap)==(dict(live),[]),f'migrate_{cap}_{seed}')
            rc,new=resources.reserve_bytes(raw,[0x10001,0x10001,0],cap)
            if cap==128:check(rc==2 and new==raw,'full_admission_unchanged_'+str(seed))
            else:check(rc==0 and unpack(new,cap)==({**dict(live),0x10001:0},[]),'capacity_admission_'+str(cap)+'_'+str(seed))
    queued=[0x60000+i for i in range(128)];s=snapshot([(k,0) for k in queued],queued);raw=resources.migrate_bytes(s,128)
    rc,new=resources.reserve_bytes(raw,[0x10001],128);check(rc==2 and new==raw,'queued_keys_not_evicted')
    raw=resources.migrate_bytes(snapshot([(k,0) for k in queued]),128)
    rc,new=resources.reserve_bytes(raw,[0x10001]*384,128);check(rc==0 and unpack(new,128)==({0x10001:0},[]),'inactive_keys_reclaimed_duplicate_requests_deduplicated')
    rc,new=resources.reserve_bytes(raw,list(range(1,130)),128);check(rc==2 and new==raw,'partial_reservation_failure_atomic')
    for refs,keys,expected in ((2**64-1,[7],2),(2**64-2,[7,7],2),(2**64-2,[7],0)):
        raw=resources.migrate_bytes(snapshot([(7,refs)]));rc,new=resources.reserve_bytes(raw,keys)
        check(rc==expected and (expected==0 or new==raw) and unpack(new,256)[0][7]==refs,'reference_overflow_'+str((refs,len(keys))))
    for fault in ('queue_count','queue_unknown','queue_duplicate','queue_live','empty_refs','duplicate_key','wrong_probe'):
        s=snapshot([(1,0),(2,1)],[1]);
        if fault=='queue_count':s.queued=129
        elif fault=='queue_unknown':s.queue[0]=77
        elif fault=='queue_duplicate':s.queued=2;s.queue[1]=1
        elif fault=='queue_live':s.queue[0]=2
        elif fault=='empty_refs':s.entries[0].references=1
        elif fault=='duplicate_key':s.entries[3]=Entry(1,0)
        else:s.entries[120]=s.entries[2];s.entries[2]=Entry()
        out=c.create_string_buffer(b'\xa5'*resource.size(256));before=out.raw
        check(resources.migrate(Binding(A,256,0),s,out,resource.size(256))==3 and out.raw==before,'reject_'+fault)
    # The earlier forced queue=128 with only eight resident keys is invalid.
    s=snapshot([(1,1)]);s.queued=128;out=c.create_string_buffer(resource.size(256))
    check(resources.migrate(Binding(A,256,0),s,out,len(out))==3,'earlier_queue_counterexample_is_incoherent')
    for original in (True,False):
        f=v.Fixture(lib,legacy,'acquire',4,4,2,original=original,ordinal=3)
        s=snapshot(live);f.put(v.TABLE,bytes(s.entries));f.put(G+0x3798198,u32(s.seed))
        try:f.uc.emu_start(f.start,0,count=200000)
        except v.core.unicorn.UcError:pass
        else:raise ValueError('full table failure disappeared')
        pc=f.uc.reg_read(reg('rip'));instruction=n.decode(f.read(pc,3),pc)[0]
        check(instruction.mnemonic=='mov' and instruction.op_str=='qword ptr [rax], r8' and sum(name=='load' for name,args in f.calls)==1,'full_table_load_before_fault_'+str(original))
        check(f.uc.reg_read(reg('rax'))==0,'full_table_null_destination_'+str(original))
    for game in (G,G+0x80000000):
        arena=game+A-G;images=Images(resources,256,arena)
        for ordinal in (0,4,7):
            key=0x10001+ordinal*128;raw=resources.migrate_bytes(snapshot(live),256,arena)
            rc,raw=resources.reserve_bytes(raw,[key],256,arena);n.need(rc==0,'admission failed')
            f=Fixture(lib,images,'acquire',8,8,4,game=game,ordinal=ordinal);f.install(raw,resources,256);raw=f.execute_resource()
            check(unpack(raw,256)[0][key]==1 and sum(k=='load' for k,a in f.calls)==1,'expanded_acquire_'+hex(game)+'_'+str(ordinal));runs.append('acquire')
            f=Fixture(lib,images,'release',8,8,4,game=game,ordinal=ordinal,flag=1);f.install(raw,resources,256);raw=f.execute_resource()
            check(unpack(raw,256)[0][key]==0 and unpack(raw,256)[1]==[key],'expanded_defer_'+hex(game)+'_'+str(ordinal));runs.append('release')
            f=Fixture(lib,images,'acquire',8,8,4,game=game,ordinal=ordinal);f.install(raw,resources,256);raw=f.execute_resource()
            check(unpack(raw,256)[0][key]==1 and not unpack(raw,256)[1] and not any(k=='load' for k,a in f.calls),'queued_reacquire_'+hex(game)+'_'+str(ordinal));runs.append('acquire')
        # A coherent 129th deferred key after migration to 256 buckets.
        raw=resources.migrate_bytes(snapshot([(k,0) for k in queued],queued),256,arena);key=0x10001+7*128
        rc,raw=resources.reserve_bytes(raw,[key],256,arena);n.need(rc==0,'queue growth admission');data=bytearray(raw)
        for i in range(256):
            if struct.unpack_from('<Q',data,48+8*256+16*i)[0]==key:struct.pack_into('<Q',data,48+8*256+16*i+8,1)
        f=Fixture(lib,images,'release',8,8,4,game=game,ordinal=7,flag=1);f.install(bytes(data),resources,256);raw=f.execute_resource()
        check(unpack(raw,256)[1]==queued+[key],'coherent_129th_deferred_'+hex(game));runs.append('release_129')
        f=Fixture(lib,images,'update',8,8,4,game=game,control=0,active=0);f.install(raw,resources,256);raw=f.execute_resource()
        check(not unpack(raw,256)[1] and sum(k=='dispose' for k,a in f.calls)==129,'drain_129_'+hex(game));runs.append('update_drain')
        # Full saved registry refresh body, with its resource RIP windows and
        # the prior outer pointer/release windows applied together.
        raw=resources.migrate_bytes(snapshot(live),256,arena);rc,raw=resources.reserve_bytes(raw,[key],256,arena)
        f=OuterFixture(lib,images,bridge,'refresh',8,8,4,game=game,ordinal=7)
        for entry in (0x51ade0,0x664210):
            source=resource.profile()['functions'][hex(entry)];f.put(game+entry,bytes.fromhex(source['body_hex']))
        f.install(raw,resources,256,external=True);raw=f.execute_resource()
        check(unpack(raw,256)[0][key]==1 and f.release_ordinals==[7],'outer_refresh_resources_'+hex(game));runs.append('outer_refresh')
        for entry in (0x51ade0,0x664210):
            f=Fixture(lib,images,'update',8,8,4,game=game)
            for origin in (0x51ade0,0x664210,0xb5e710):
                source=resource.profile()['functions'][hex(origin)];f.put(game+origin,bytes.fromhex(source['body_hex']))
            f.put(game+RESET-G,b'\xc3');f.start=game+entry;dirty=bytearray(raw);dirty[48:48+256*8]=b'\xee'*(256*8)
            f.install(bytes(dirty),resources,256,external=True);after=f.execute_resource()
            check(unpack(after,256)==({},[]) and after[48:48+256*8]==bytes(256*8) and f.reset_calls==1,'reset_rebound_'+hex(game)+'_'+hex(entry));runs.append('reset')
    mutations=[]
    for kind,rva in (('release',0x3797550),('acquire',0x3798180)):
        images=Images(resources);f=Fixture(lib,images,kind,8,8,4,ordinal=7,flag=1);key=0x10001+7*128
        raw=resources.migrate_bytes(snapshot([(key,1)]));f.install(raw,resources,256)
        old=consumer.build(kind,**v.params(kind))['image'];index=consumer.KINDS.index(kind)+1
        _,off,nxt,_=next(row for row in resource.descriptors()[0] if row[0]==index and row[3]==rva)
        f.put(v.params(kind)['code_address']+off,old[off:off+4])
        try:f.execute_resource()
        except ValueError as error:n.need('old resource globals' in str(error),'unexpected mutation failure')
        else:raise ValueError('old resource reference survived')
        mutations.append(kind)
    # Refuse malformed emission arguments and preserve zeroed output.
    for cap,address in ((127,A),(129,A),(131072,A),(256,0),(256,S),(256,G+0x3797550),(256,G+0x10b00000),(256,A+0x200000000)):
        out=Image();c.memset(c.byref(out),0xa5,c.sizeof(out));rc=resources.consumer(1,v.Addresses(**v.params('update')),Binding(address,cap,0),out)
        check(rc!=0 and not any(bytes(out)),'emission_refused_'+str((cap,address)))
    raw=resources.migrate_bytes(snapshot(live));p=c.create_string_buffer(raw,len(raw));key=(U*1)(1);before=p.raw
    check(resources.reserve(Binding(A,256,0),p,len(raw),key,1,p,len(raw))==4 and p.raw==before,'scratch_alias_refused')
    for game,address,cap,reset in ((0,A,256,RESET),(G,0,256,RESET),(G,A,129,RESET),(G,A,256,0),
        (G,G+0x3797550,256,RESET),(G,RESET,256,RESET),(G,A+0x200000000,256,RESET),(G,A,256,RESET+0x200000000)):
        plan=Plan();c.memset(c.byref(plan),0xa5,c.sizeof(plan))
        check(resources.windows(game,Binding(address,cap,0),reset,plan)!=0 and not any(bytes(plan)),'window_emission_refused_'+str((game,address,cap,reset)))
    sources=['mod/src/ep_component33_resources.h','mod/src/ep_component33_resources.cpp','mod/src/ep_component33_resources_template.h','tests/component33_resources_dll.cpp','tools/native_component33_resources.py','tools/validate_component33_resources.py','native-component33-resources.lock.json',
        'mod/src/ep_component33_consumers.cpp','mod/src/ep_component33_consumers_template.h','tools/native_component33_consumers.py','native-component33-consumers.lock.json','tools/validate_component33_consumers.py','tools/validate_component33_outer.py','tools/native_component33_outer.py','native-component33-outer.lock.json','tools/native_component33_image.py','tools/native_component33_library.py','tools/validate_component33_images.py']
    return dict(schema='hellforge_component33_resources_validation_v1',passed=True,checks=len(cases),cases=cases,functional_runs=len(runs),runs=runs,
        resource_globals=59,consumer_relocations=25,original_window_fixups=40,merged_original_windows=len(resources.window_plan()),
        configurable_capacity_range=[128,65536],tested_capacities=[128,256,1024],snapshot_validation=True,capacity_failure_atomic=True,
        coherent_129th_deferred_verified=True,full_table_load_before_fault_reproduced=True,old_queue_counterexample_incoherent=True,old_global_mutations_rejected=mutations,
        native_resource_services=False,production_demand_collector=False,arena_lifetime_owner_bound=False,whole_call_exclusion=False,
        safe_reset_lifecycle_verified=False,resource_callback_compensation=False,installed=False,game_access=False,runtime_verified=False,multiplayer_verified=False,
        source_sha256={s:n.sha((n.PROJECT/s).read_bytes()) for s in sources},artifacts={p.name:dict(bytes=p.stat().st_size,sha256=n.sha(p.read_bytes())) for p in (resources.path,lib.path,legacy.path,bridge.path)},
        limits=['Caller supplies complete prospective demand and local coherent snapshot. No source pointer is dereferenced.', 'Admission is before service effects; it is not callback rollback or owner integration.', 'Original reset windows preserve unconditional clearing; production must prove safe lifetime or replace reset semantics.', 'Global reference inventory covers captured unwind-backed instructions; undecoded suffixes and dynamic aliases are not completeness proof.'])

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('resources','library','consumers','outer','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();r=validate(Resources(a.resources),Library(a.library),v.Consumers(a.consumers),outer.Outer(a.outer));a.out.write_bytes((json.dumps(r,indent=2)+'\n').encode());print(json.dumps({k:r[k] for k in ('passed','checks','functional_runs','merged_original_windows','game_access')}))
