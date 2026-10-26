"""Migrate supplied snapshots and execute migrated C++ data only in Unicorn."""
import argparse,ctypes as c,json,struct,subprocess
from pathlib import Path
import native_component33_image as n
from validate_component33_family import U,D,P,Info as Family,Memory
from native_component33_library import Library
from validate_component33_images import Fixture,LAYOUT,S,B,E,reg

class Entity(c.Structure):_fields_=[('address',U),('id',D),('flags',D)]
class Snapshot(c.Structure):
    _fields_=[('component_address',U),('global_component',U),('invalid_entity_id',D),('entity_count',D),('component',c.c_ubyte*0x2b8),('entities',Entity*4)]
class Migration(c.Structure):_fields_=[('data',c.c_ubyte*0x490)]
class Bindings(c.Structure):
    _fields_=[('game_base',U),('reject_address',U),('desired_storage',U),('desired_code',U*20)]
class Info(c.Structure):
    _fields_=[('handle',U),('storage_address',U),('state',D),('storage_bytes',D),('family_result',D),('family',Family)]
def put(s,off,fmt,*v):struct.pack_into('<'+fmt,s.component,off,*v)
def get(s,off,fmt='I'):return struct.unpack_from('<'+fmt,s.component,off)[0]
def snapshot(t,d,p,seed=2,reverse=False,component=0x200000000):
    s=Snapshot();s.component_address=s.global_component=component;s.invalid_entity_id=0xffffffff;s.entity_count=t
    s.component[:]=bytes((i*17+43)&255 for i in range(0x2b8))
    put(s,8,'III',t,d,p);s.component[0x14:0x54]=bytes(64);put(s,0x58,'QIII',component+0x14,8,0,seed)
    for i in range(t):
        k=(t-1-i if reverse else i);address=0x220000000+k*0x80;identity=1+k*8;flags=0xa500|int(i<p) if i<d else 0xb501
        put(s,0x70+8*i,'Q',address);s.entities[t-1-i]=Entity(address,identity,flags)
        bucket=(identity*seed)&7
        while get(s,0x14+8*bucket):bucket=(bucket+1)&7
        put(s,0x14+8*bucket,'II',identity,i)
    return s
def expected(s):
    # Independently place each logical slot/field; do not copy the production
    # block-copy sequence or derive destinations from its emitted result.
    b=bytearray(0x490)
    for i in range(4):
        for new,old,size in LAYOUT.values():b[new+i*size:new+(i+1)*size]=s.component[old+i*size:old+(i+1)*size]
    return bytes(b)

def validate(path,core):
    dll=c.CDLL(str(path.resolve()));m=0x10001;checks=0;scenarios=[];integrations=[]
    def check(ok,msg):
        nonlocal checks
        checks+=1;n.need(ok,msg)
    def fn(name,args,rest=c.c_int):
        f=getattr(dll,'c33_storage_'+name);f.argtypes=args;f.restype=rest;return f
    migrate=fn('migrate',[c.POINTER(Snapshot),c.POINTER(Migration)])
    prepare=fn('prepare',[P,c.POINTER(Bindings),c.POINTER(Snapshot),c.POINTER(Info)])
    info=fn('info',[P,U,c.POINTER(Info)]);cancel=fn('cancel',[P,U]);retain=fn('retain',[P,U,c.POINTER(Snapshot)])
    faults=fn('faults',[c.POINTER(D)],None);counts=fn('counts',[c.POINTER(D)])
    kernel=c.WinDLL('kernel32');query=kernel.VirtualQuery;query.argtypes=[P,c.POINTER(Memory),c.c_size_t];query.restype=c.c_size_t
    nt=c.WinDLL('ntdll');lookup=nt.RtlLookupFunctionEntry;lookup.argtypes=[U,c.POINTER(U),P];lookup.restype=P
    def reset(**kw):
        a=(D*7)()
        for k,v in kw.items():a[int(k)]=v
        faults(a)
    def stats():
        a=(D*7)();check(counts(a)==0,'SDK hook called');return list(a)
    def bindings(shift=0):return Bindings(0x180000000+shift,0x1a0000000+shift,0x210000000+shift,(U*20)(*(0x190000000+shift+i*0x10000 for i in range(20))))
    def view(h):
        v=Info();check(info(m,h,v),'owner missing');return v
    def is_free(p):
        q=Memory();check(query(p,q,c.sizeof(q)) and q.state==0x10000,'page not released')
    def all_free(b):
        for p in [b.desired_storage,*b.desired_code]:is_free(p)
    def prepared(v,b,s,retained=False):
        check(v.state==(4 if retained else 2) and v.storage_bytes==0x490 and v.family.reserved_images==20,'owner state')
        q=Memory();check(query(v.storage_address,q,c.sizeof(q)) and q.protect==4,'B is not RW')
        check(c.string_at(v.storage_address,0x490)==expected(s),'B bytes')
        for i,code in enumerate(v.family.code):
            check(code.state==(7 if retained else 2) and code.pinned==int(retained) and code.registered==1,'code ownership')
            check(code.base==b.desired_code[i] and query(code.base,q,c.sizeof(q)) and q.protect==0x20,'code placement/protection')
            base=U();check(lookup(code.base,base,None) and base.value==code.base,'unwind missing')
            if i<14:
                ref=n.build(n.ALL_KINDS[i],game_base=b.game_base,code_address=code.base,component_address=s.component_address,
                    storage_address=v.storage_address,move_code_address=v.family.code[0].base,reject_address=b.reject_address)
                check(c.string_at(code.base,code.bytes)==ref['image'],'family does not use owned B')
    # All old partition shapes, collision seeds, and nonordinal pointer/ID order.
    for reverse,seed in ((False,2),(True,0x80000001)):
        for t in range(5):
            for d in range(t+1):
                for p in range(d+1):
                    s=snapshot(t,d,p,seed,reverse);before=bytes(s);out=Migration();check(migrate(s,out)==0,'migration rejected valid shape')
                    check(bytes(out.data)==expected(s),'migration bytes');check(bytes(s)==before,'source changed')
                    scenarios.append(f'migrate_{reverse}_{t}_{d}_{p}')
    bad=[]
    def mutation(name,change):
        s=snapshot(4,3,1);change(s);bad.append((name,s))
    mutation('global',lambda s:setattr(s,'global_component',s.component_address+8))
    mutation('pointer',lambda s:setattr(s,'component_address',1))
    mutation('fifth_source',lambda s:put(s,8,'I',5))
    mutation('dense',lambda s:put(s,12,'I',5))
    mutation('prefix',lambda s:put(s,16,'I',4))
    mutation('entities_count',lambda s:setattr(s,'entity_count',3))
    mutation('map_pointer',lambda s:put(s,0x58,'Q',s.component_address+0x18))
    mutation('map_capacity',lambda s:put(s,0x60,'I',4))
    mutation('map_mode',lambda s:put(s,0x64,'I',1))
    mutation('duplicate_ordinal',lambda s:put(s,0x18+3*8,'I',0))
    mutation('map_extra',lambda s:put(s,0x14,'II',77,3))
    mutation('map_hole',lambda s:put(s,0x14+2*8,'I',0))
    mutation('null_entity',lambda s:put(s,0x70,'Q',0))
    mutation('foreign_entity',lambda s:put(s,0x70,'Q',0x220008000))
    mutation('duplicate_entity',lambda s:setattr(s.entities[0],'address',s.entities[1].address))
    mutation('duplicate_id',lambda s:setattr(s.entities[0],'id',s.entities[1].id))
    mutation('invalid_id',lambda s:setattr(s.entities[0],'id',s.invalid_entity_id))
    mutation('dense_flags',lambda s:setattr(s.entities[3],'flags',0))
    # Keep occupancy/ordinals consistent but put a real key beyond an empty
    # probe bucket. Scanning the whole table would incorrectly accept this.
    def unreachable(s):
        s.component[0x14:0x54]=bytes(64)
        for i in range(4):put(s,0x14+8*((i+4)&7),'II',1+i*8,i)
    mutation('unreachable_map',unreachable)
    for name,s in bad:
        out=Migration();c.memset(c.byref(out),0xa5,c.sizeof(out));before=bytes(s)
        check(migrate(s,out)!=0 and not any(bytes(out)),'invalid snapshot accepted '+name);check(bytes(s)==before,'bad snapshot changed');scenarios.append('reject_'+name)
    out=Migration();check(migrate(None,out)!=0 and not any(bytes(out)) and migrate(snapshot(0,0,0),None)!=0,'null migration')

    # Feed C++ migration output into the existing C++ append/remove emulation.
    # This actually crosses the old four-slot boundary and checks old arrays.
    lib=Library(core)
    for t,d,p in ((0,0,0),(4,4,2),(4,2,1),(4,0,0)):
        f=Fixture(lib,'append',t,d,p);s=Snapshot();s.component_address=s.global_component=S;s.invalid_entity_id=0xffffffff;s.entity_count=t
        s.component[:]=f.read(S,0x2b8)
        for i in range(4):
            for name,(_,old,size) in LAYOUT.items():s.component[old+i*size:old+(i+1)*size]=f.records[name,i]
        for i in range(t):s.entities[i]=Entity(E+0x40*i,f.int32(E+0x40*i+8),f.int32(E+0x40*i+0x14))
        data=Migration();check(migrate(s,data)==0,'integration migration');f.put(S,bytes(s.component));f.put(B,bytes(data.data));f.old_arrays_snapshot=bytes(s.component[0x70:])
        for i in range(8):
            for name,(new,_,size) in LAYOUT.items():f.records[name,i]=bytes(data.data[new+i*size:new+(i+1)*size])
        f.execute();check(f.int32(S+8)==t+1,'new slot not appended');check(f.read(S+0x70,0x248)==bytes(s.component[0x70:]),'old arrays touched')
        integrations.append(dict(operation='append',old_total=t,dense=d,prefix=p,new_total=t+1))
        g=Fixture(lib,'remove',t+1,d,p,ordinal=t)
        g.put(S,f.read(S,0x2b8));g.put(B,f.read(B,0x490));g.put(E,f.read(E,0x240));g.old_arrays_snapshot=f.old_arrays_snapshot
        g.uc.reg_write(reg('rcx'),E+0x200);g.keys[t]=73
        g.table=[(g.int32(S+0x14+i*8),g.int32(S+0x18+i*8)) for i in range(8)]
        for i in range(8):
            for name,(new,_,size) in LAYOUT.items():g.records[name,i]=g.read(B+new+i*size,size)
        g.execute();check(g.int32(S+8)==t,'removal after migration');check(g.read(S+0x70,0x248)==bytes(s.component[0x70:]),'removal touched old arrays')
        integrations.append(dict(operation='remove_appended',old_total=t+1,new_total=t))

    for shift in (0,0x40000000):
        reset();b=bindings(shift);s=snapshot(4,3,1,reverse=True,component=0x200000000+shift);v=Info();check(prepare(m,b,s,v)==0,'owner prepare');prepared(v,b,s)
        other=Info();check(prepare(m+1,b,s,other)==12 and not other.handle,'overlapping S accepted')
        check(not cancel(m+1,v.handle) and not info(m+1,v.handle,other),'owner identity')
        saved=Info.from_buffer_copy(v);check(cancel(m,v.handle),'cancel');check(not info(m,saved.handle,other),'stale owner');all_free(b);scenarios.append('owner_cancel_'+hex(shift))
    for kind,steps in ((0,range(1,22)),(1,(1,8,20)),(2,(1,8,20)),(3,(1,8,20))):
        for step in steps:
            reset(**{str(kind):step});b=bindings();v=Info();check(prepare(m,b,snapshot(4,3,1),v) in (8,9),'failure not propagated')
            check(not v.handle,'failed owner leaked');all_free(b);scenarios.append(f'owner_fault_{kind}_{step}')
    # A code cleanup failure must retain B; after retry succeeds it may be freed.
    reset(**{'3':8,'4':0xffffffff});b=bindings();s=snapshot(4,3,1);v=Info()
    check(prepare(m,b,s,v)==10 and v.state==3 and v.family.handle,'code cleanup state')
    check(c.string_at(v.storage_address,0x490)==expected(s),'B released before code cleanup')
    check(retain(m,v.handle,s)==11,'cleanup owner retained');reset();check(cancel(m,v.handle),'code cleanup retry');all_free(b);scenarios.append('code_cleanup_keeps_B')
    reset(**{'0':2,'5':0xffffffff});v=Info();check(prepare(m,b,s,v)==10 and v.state==3 and not v.family.handle,'B cleanup state')
    reset();check(cancel(m,v.handle),'B cleanup retry');all_free(b);scenarios.append('B_cleanup_retry')
    reset();v=Info();check(prepare(m,b,s,v)==0,'cancel-fault prepare')
    reset(**{'5':21});check(not cancel(m,v.handle),'B cancel failure hidden');pending=view(v.handle)
    check(pending.state==3 and not pending.family.handle and pending.storage_address==v.storage_address,'B cancel ownership lost')
    check(c.string_at(pending.storage_address,0x490)==expected(s),'B prematurely freed')
    reset();check(cancel(m,v.handle),'B cancel retry');all_free(b);scenarios.append('prepared_B_cancel_retry')
    reset();v=Info();check(prepare(m,b,s,v)==0,'freshness prepare')
    for name,change in (('opaque',lambda x:put(x,0x1d8,'I',0xfeed)),('control',lambda x:put(x,0,'I',0x1234)),('flags',lambda x:setattr(x.entities[0],'flags',x.entities[0].flags^0x10))):
        now=Snapshot.from_buffer_copy(s);change(now);check(retain(m,v.handle,now)==7,'changed snapshot retained '+name);prepared(view(v.handle),b,s);scenarios.append('stale_'+name)
    at=v.storage_address+0x48;old=c.c_ubyte.from_address(at).value;c.c_ubyte.from_address(at).value=1
    check(retain(m,v.handle,s)==7,'changed B retained');c.c_ubyte.from_address(at).value=old
    reset(**{'6':1});check(retain(m,v.handle,s)==9,'failed pin accepted');prepared(view(v.handle),b,s)
    # Reordering equivalent entity snapshots is not an identity change.
    current=Snapshot.from_buffer_copy(s);current.entities[:]=list(reversed(list(s.entities)))
    reset();check(retain(m,v.handle,current)==0,'retain');prepared(view(v.handle),b,s,True)
    check(not cancel(m,v.handle) and retain(m,v.handle,s)==11,'retention reversed')
    free=kernel.FreeLibrary;free.argtypes=[P];free.restype=c.c_int;check(free(dll._handle),'FreeLibrary');prepared(view(v.handle),b,s,True)
    scenarios.extend(['stale_B','pin_failure','retain_reordered_snapshot','retained_B_and_code_survive_FreeLibrary']);stats()
    return dict(passed=True,checks=checks,scenarios=scenarios,integration_runs=integrations,migration_shapes=70,
        migrated_arrays=4,source_bytes=0x2b8,storage_bytes=0x490,owned_code_images=20,
        source_addresses_dereferenced=False,native_game_code_executed=False,targets_modified=False,
        sdk_hook_calls=0,resource_references_shallow=True,resource_ownership_transferred=False,
        production_snapshot_provider_bound=False,whole_call_exclusion_implemented=False,production_owner_bound=False,
        installed=False,runtime_verified=False,multiplayer_verified=False,game_access=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True);p.add_argument('--core',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    sources=['mod/src/ep_component33_resources.h','mod/src/ep_component33_resources.cpp','mod/src/ep_component33_resources_template.h','mod/src/ep_component33_outer.h','mod/src/ep_component33_outer.cpp','mod/src/ep_component33_outer_template.h','tools/native_component33_outer.py','native-component33-outer.lock.json','mod/src/ep_component33_consumers.h','mod/src/ep_component33_consumers.cpp','mod/src/ep_component33_consumers_template.h','tools/native_component33_consumers.py','native-component33-consumers.lock.json','mod/src/ep_component33_storage.h','mod/src/ep_component33_storage.cpp','tests/component33_storage_dll.cpp','tools/validate_component33_storage.py',
        'mod/src/ep_component33_family.h','mod/src/ep_component33_family.cpp','mod/src/ep_session_code.h','mod/src/ep_session_code.cpp',
        'mod/src/ep_component33_image.h','mod/src/ep_component33_image.cpp','mod/src/ep_component33_templates.h','mod/src/ep_component33_owner_template.h',
        'mod/src/ep_component33_readers.h','mod/src/ep_component33_readers.cpp','mod/src/ep_component33_readers_template.h',
        'tools/validate_component33_family.py','tools/validate_component33_images.py','tools/native_component33_library.py','tools/native_component33_image.py','native-component33.lock.json',
        'tools/native_component33_readers.py','tools/native_component33_owner.py','tools/generate_component33_templates.py','tools/build_unwind_offline.py',
        'native-component33-readers.lock.json','native-component33-owner.lock.json']
    dll=n.PROJECT/'build/component33_storage_test.dll'
    command=[a.zig,'c++','-std=c++17','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-I',a.upstream/'native/mod-sdk',
        *(n.PROJECT/s for s in ('mod/src/ep_component33_resources.cpp','mod/src/ep_component33_outer.cpp','mod/src/ep_component33_consumers.cpp','mod/src/ep_component33_family.cpp','mod/src/ep_component33_image.cpp','mod/src/ep_component33_readers.cpp','tests/component33_storage_dll.cpp')),'-o',dll]
    r=subprocess.run(list(map(str,command)),capture_output=True);n.need(r.returncode==0,r.stderr.decode(errors='replace'))
    result=validate(dll,a.core);result.update(schema='hellforge_component33_storage_validation_v1',source_sha256={s:n.sha((n.PROJECT/s).read_bytes()) for s in sources},
        artifacts={x.name:dict(bytes=x.stat().st_size,sha256=n.sha(x.read_bytes())) for x in (dll,a.core)})
    a.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:result[k] for k in ('passed','checks','migration_shapes','owned_code_images','game_access')}))
if __name__=='__main__':main()
