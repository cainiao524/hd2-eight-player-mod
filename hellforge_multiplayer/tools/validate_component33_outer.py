"""Execute both saved component33 registry callers, C++ getters and RELEASE."""
import argparse,ctypes as c,json,struct
from pathlib import Path
import native_component33_outer as outer
import native_component33_consumers as consumer
import native_component33_image as n
import validate_component33_consumers as v
import validate_component33_images as core
from validate_component33_readers import Window
from native_component33_library import Library,Image
from validate_component33_images import G,S,B,E,RSP,STACK,SEEDS,NAMES,reg,u32,u64,run

REGISTRY=v.HEAP+0x1400000;POOL=v.HEAP+0x1800000;MANAGER=v.HEAP+0x2000000
GPRS=('rax','rcx','rdx','rbx','rbp','rsi','rdi','r8','r9','r10','r11','r12','r13','r14','r15','rsp')
class Plan(c.Structure):_fields_=[('bridge',Image),('windows',Window*5)]
class Outer:
    def __init__(self,path):
        self.path=path.resolve();self.dll=c.CDLL(str(self.path));self.fn=self.dll.c33_outer_build
        self.fn.argtypes=[c.POINTER(v.Addresses),c.POINTER(Plan)];self.fn.restype=c.c_int
    def build(self,**a):
        r=outer.build(**a);p=Plan();n.need(self.fn(v.Addresses(**a),p)==0,'outer C++ refused')
        n.need(bytes(p.bridge.data[:p.bridge.bytes])==r['image'],'outer C++ bytes differ')
        n.need(all(getattr(p.bridge,k)==r[k] for k in ('code_bytes','unwind_offset','table_offset','function_count')),'outer metadata')
        for x,y in zip(p.windows,r['windows']):
            n.need((x.target,x.bytes,x.call_offset)==tuple(y[k] for k in ('target','bytes','call_offset')) and bytes(x.expected[:x.bytes])==y['expected'] and bytes(x.replacement[:x.bytes])==y['replacement'],'outer window differs')
        return r

class Fixture(v.Fixture):
    def __init__(self,lib,images,bridge,name,t,d,p,*,game=G,original=False,ordinal=None,match=True,resource_count=1,queued=False,refresh_resource=True):
        self.outer_ready=False;self.outer_name=name;self.parent_blobs={};self.getter_count=0;self.release_ordinals=[];self.pending=None
        super().__init__(lib,images,'release',t,d,p,game=game,original=original,ordinal=ordinal,flag=int(name=='release'),match=match,resource_count=resource_count,queued=queued)
        self.bindings=dict(v.params('release',game),code_address=game+0x10d00000)
        self.plan=bridge.build(**self.bindings)
        self.put(self.bindings['code_address'],self.plan['image'])
        for key,f in outer.profile()['callers'].items():
            raw=bytearray.fromhex(f['body_hex'])
            if not original:
                for w in self.plan['windows']:
                    if game+f['start']<=w['target']<game+f['end']:
                        at=w['target']-game-f['start'];raw[at:at+w['bytes']]=w['replacement']
            self.parent_blobs[key]=bytes(raw);self.put(game+f['start'],bytes(raw))
        self.put(REGISTRY,bytes(0x2100));self.put(game+0x3326e68,u64(REGISTRY))
        self.put(REGISTRY+0xd10,u32(1));self.put(REGISTRY+0xd18,u64(S)+u32(0x7c))
        self.put(REGISTRY+0x1f78,u32(1));self.put(REGISTRY+0x1f80,u64(S)+u32(0x7c))
        self.put(game+0x346bf98,u64(MANAGER));self.put(MANAGER+0xf12580,u64(POOL));self.put(POOL,bytes(0x3100))
        handle=0x12000+self.ordinal;self.put(POOL+(handle&1)*16,u64(handle)+u64(0))
        if refresh_resource:
            self.put(POOL+0x20,u64(0x10001+self.ordinal*128)+bytes(8)+u32(1000)+u32(0))
            self.put(POOL+0x820,u32(1))
        self.uc.reg_write(reg('rcx'),v.OWNER+self.ordinal*0x100 if match else v.OWNER+0x1000)
        self.uc.reg_write(reg('rdx'),0x1234)
        self.start=game+outer.profile()['callers'][name]['start']
        self.blob,self.table,self.count,self.offsets=self.outer_unwind_image()
        self.outer_ready=True
    def outer_unwind_image(self):
        blob=bytearray();offsets={};rows=[]
        def align():
            while len(blob)%16:blob.append(0)
        for name,f in outer.profile()['callers'].items():
            align();off=len(blob);offsets[name+'_parent']=off;blob.extend(self.parent_blobs[name]);align();uws={}
            for row in f['fragments']:
                uws[row['unwind_rva']]=len(blob);blob.extend(bytes.fromhex(row['unwind_hex']));align()
            for row in f['fragments']:
                uw=uws[row['unwind_rva']];rows.append((off+row['start']-f['start'],off+row['end']-f['start'],uw))
                if blob[uw]>>3&4:
                    at=uw+4+((blob[uw+2]+1)&~1)*2;a,b,u=struct.unpack_from('<III',blob,at)
                    struct.pack_into('<III',blob,at,off+a-f['start'],off+b-f['start'],uws[u])
        for key,r in (('bridge',self.plan),('release',self.images['release'])):
            align();off=len(blob);offsets[key]=off;blob.extend(r['image']);seen=set()
            for j in range(r['function_count']):
                a,b,u=struct.unpack_from('<III',r['image'],r['table_offset']+j*12);rows.append((off+a,off+b,off+u))
                if u not in seen and blob[off+u]>>3&4:
                    at=off+u+4+((blob[off+u+2]+1)&~1)*2;chain=struct.unpack_from('<III',blob,at);struct.pack_into('<III',blob,at,*(x+off for x in chain))
                seen.add(u)
        table=len(blob)
        for row in rows:blob.extend(struct.pack('<III',*row))
        return bytes(blob),table,len(rows),offsets
    def code_regions(self):
        for key,f in outer.profile()['callers'].items():yield self.game+f['start'],f['end']-f['start'],self.offsets[key+'_parent'],1
        yield self.bindings['code_address'],self.plan['code_bytes'],self.offsets['bridge'],2
        yield v.params('release',self.game)['code_address'],self.images['release']['code_bytes'],self.offsets['release'],2
    def normalize(self,value):
        if not self.outer_ready:return super().normalize(value)
        if RSP-512<=value<RSP+128:return 0x200000000+value-RSP
        for base,length,off,_ in self.code_regions():
            if base<=value<base+length:return 0x100000000+off+value-base
        return value
    def on_code(self,uc,pc,size,data):
        if self.outer_ready:
            if not self.original:
                for base,length,off,levels in self.code_regions():
                    if base<=pc<base+length:
                        stack=bytearray(self.read(RSP-512,640));struct.pack_into('<Q',stack,512,G+0x10500000)
                        for j in range(0,640,8):struct.pack_into('<Q',stack,j,self.normalize(struct.unpack_from('<Q',stack,j)[0]))
                        self.rows.add(struct.pack('<IiII8Q',off+pc-base,uc.reg_read(reg('rsp'))-RSP,0,levels,*(self.normalize(uc.reg_read(reg(x))) for x in NAMES))+stack)
                for w in outer.profile()['windows']:
                    if pc==self.game+w['start'] and w['target']!='release':
                        ordinal=uc.reg_read(reg('rax' if w['target']==outer.KINDS[0] else 'rdi'))
                        self.pending=(w,{k:uc.reg_read(reg(k)) for k in GPRS},uc.reg_read(reg('eflags')),ordinal)
                    if self.pending and pc==self.game+self.pending[0]['end']:
                        win,regs,flags,ordinal=self.pending;destination='rcx' if win['target']==outer.KINDS[0] else 'rax'
                        n.need(uc.reg_read(reg(destination))==struct.unpack('<Q',self.read(B+ordinal*8,8))[0],'outer getter wrong identity')
                        n.need(all(uc.reg_read(reg(k))==value for k,value in regs.items() if k!=destination),'outer getter clobbered a live register')
                        n.need((uc.reg_read(reg('eflags'))^flags)&~0x8d5==0,'outer getter changed non-arithmetic flags')
                        self.pending=None;self.getter_count+=1
            if pc==self.entries['release']:
                self.release_ordinals.append(uc.reg_read(reg('rdx')))
                n.need(uc.reg_read(reg('rcx'))==S and uc.reg_read(reg('r8'))&255==self.flag,'outer release ABI')
        # Reuse only the explicit resource-service stubs; collect frames using
        # the combined parent/bridge/release layout above, not the helper layout.
        original=self.original;self.original=True
        try:super().on_code(uc,pc,size,data)
        finally:self.original=original
    def execute_outer(self,expected='return'):
        before=self.state()
        if expected=='return':super().execute_consumer()
        else:
            self.uc.emu_start(self.start,0,count=150000);n.need(self.outcome==expected,'outer guard outcome')
            n.need(before==self.state() and not self.calls and not self.release_ordinals,'outer refusal changed data/services')
            n.need(all(STACK<=a and a+z<=STACK+0x10000 for a,z in self.writes),'outer refusal escaped stack')
        if expected=='return':
            n.need(self.release_ordinals==([self.ordinal] if self.match and self.d else []),'outer selected wrong ordinal')
            expected_reads=(self.ordinal+1 if self.match and self.d else self.d)+(1 if self.outer_name=='refresh' and self.match and self.d else 0)
            if not self.original:n.need(self.getter_count==expected_reads,'outer getter coverage')
        return self

def validate(lib,images,bridge,zig):
    n.need(outer.HEADER.read_bytes()==outer.render(),'outer header stale');runs=[];contexts=set();pairs=0
    def execute(f,expected='return',case='matrix'):
        f.execute_outer(expected);contexts.update(f.rows);runs.append(dict(caller=f.outer_name,t=f.t,d=f.d,p=f.p,ordinal=f.ordinal,original=f.original,game_base=hex(f.game),case=case,outcome=f.outcome,instructions=len(f.trace),getters=f.getter_count,releases=f.release_ordinals));return f
    for name in outer.profile()['callers']:
        for t,d,p,extra in ((0,0,0,{}),(1,1,0,{}),(4,4,2,{}),(4,2,1,{}),(4,4,2,dict(match=False)),(4,4,2,dict(resource_count=2)),(4,4,2,dict(queued=True)),(4,4,2,dict(refresh_resource=False))):
            old=execute(Fixture(lib,images,bridge,name,t,d,p,original=True,**extra),'return','original')
            new=execute(Fixture(lib,images,bridge,name,t,d,p,**extra),'return','equivalent')
            n.need(old.canonical()==new.canonical(),'outer original equivalence '+str((name,t,d,p,extra)));pairs+=1
        for game in (G,G+0x80000000):
            for t,d,p in ((5,5,2),(8,8,4),(8,3,1),(8,0,0)):
                for ordinal in range(d) if d else (0,):
                    f=execute(Fixture(lib,images,bridge,name,t,d,p,game=game,ordinal=ordinal))
                    if d:
                        n.need(f.int32(v.TABLE+(ordinal+1)*16+8)==(0 if name=='release' else 1),'outer resource count')
                        n.need(f.int32(game+0x348ba88)==int(name=='release'),'outer queue count')
            execute(Fixture(lib,images,bridge,name,8,8,4,game=game,match=False),'return','no_match')
        for label,address,blob in (('global',G+0x33267b8,u64(S+8)),('total',S+8,u32(9)),('dense',S+12,u32(9)),('prefix',S+16,u32(9)),('map_pointer',S+0x58,u64(S+0x18)),('map_size',S+0x60,u32(4)),('map_mode',S+0x64,u32(1)),('null',B,u64(0)),('identity',E+8,u32(0xffffffff)),('map_ordinal',S+0x20,u32(7)),('registry_alias',REGISTRY+(0xd18 if name=='release' else 0x1f80),u64(S+8))):
            f=Fixture(lib,images,bridge,name,8,8,4);f.put(address,blob);execute(f,'reject',label)
    mutations=[]
    for i,w in enumerate(outer.profile()['windows']):
        f=Fixture(lib,images,bridge,w['caller'],8,8,4);f.put(G+w['start'],bytes.fromhex(w['expected_hex']))
        try:f.execute_outer()
        except (ValueError,core.unicorn.UcError):pass
        else:raise ValueError('old outer window escaped '+hex(w['start']))
        n.need(G+w['start'] in f.trace,'mutation was not reached')
        if w['target']=='release':n.need(G+0x6659e0 in f.trace,'old RELEASE not reached')
        else:n.need(any(S+0x70<=a<S+0x2b8 for a,z in f.reads),'old outer array not read')
        mutations.append(hex(w['start']))
    accepted=rejected=0;placements=[outer.REFERENCE,{**outer.REFERENCE,'game_base':outer.REFERENCE['game_base']+0x80000000}]
    for key in outer.REFERENCE:
        for value in (0,1,1<<47,(1<<47)-16):placements.append({**outer.REFERENCE,key:value})
    for key in ('component_address','storage_address','release_address','reject_address'):placements.append({**outer.REFERENCE,key:outer.REFERENCE['code_address']+16})
    for rva,z in outer.protected():placements.append({**outer.REFERENCE,'code_address':outer.REFERENCE['game_base']+(rva&~15)})
    for key in ('code_address','release_address','reject_address'):placements.append({**outer.REFERENCE,key:outer.REFERENCE['game_base']+0x100000000})
    for a in placements:
        try:outer.build(**a);valid=True
        except (ValueError,struct.error,OverflowError):valid=False
        p=Plan();c.memset(c.byref(p),0xa5,c.sizeof(p));rc=bridge.fn(v.Addresses(**a),p)
        n.need((rc==0)==valid and (valid or not any(bytes(p))),'outer placement agreement')
        if valid:bridge.build(**a);accepted+=1
        else:rejected+=1
    n.need(bridge.fn(None,Plan())!=0 and bridge.fn(v.Addresses(**outer.REFERENCE),None)!=0,'outer null contract')
    sample=Fixture(lib,images,bridge,'release',8,8,4);blob=sample.blob;rows=sorted(contexts);bad=bytearray(blob)
    # Corrupt one bridge's volatile-save allocation; the nested parent frame
    # must not conceal a missing stack slot in its unwind metadata.
    bridge_table=sample.offsets['bridge']+sample.plan['table_offset'];uw=sample.offsets['bridge']+struct.unpack_from('<I',blob,bridge_table+8)[0]
    bad[uw+5]^=0x10
    target=sample.offsets['bridge']+10
    negative=bytearray(next(r for r in rows if struct.unpack_from('<I',r)[0]==target));struct.pack_into('<I',negative,8,1)
    packed=bytearray(b'EPCCNW1\0'+u32(2))
    for image,items in ((bad,[negative]),(blob,rows)):
        packed.extend(struct.pack('<4I',len(image),sample.table,sample.count,len(items)));packed.extend(image)
        packed.extend(struct.pack('<9Q',*(SEEDS[k] for k in NAMES),G+0x10500000));packed.extend(b''.join(items))
    fixture=n.PROJECT/'build/component33-outer-unwind.bin';fixture.write_bytes(packed);exe=n.PROJECT/'build/native_component33_outer_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',n.PROJECT/'tests/native_component33_outer_unwind_test.c','-o',exe]);windows=json.loads(run([exe,fixture]))
    sources=['native-component33-outer.lock.json','tools/native_component33_outer.py','tools/validate_component33_outer.py','mod/src/ep_component33_outer.h','mod/src/ep_component33_outer.cpp','mod/src/ep_component33_outer_template.h','tests/component33_outer_dll.cpp','tests/native_component33_outer_unwind_test.c','tools/validate_component33_consumers.py','tools/native_component33_consumers.py','native-component33-consumers.lock.json','tools/validate_component33_readers.py','tools/native_component33_image.py','tools/validate_component33_images.py','tools/native_component33_library.py','native-component33.lock.json']
    return dict(schema='hellforge_component33_outer_validation_v1',passed=True,functional_runs=len(runs),runs=runs,original_equivalence_pairs=pairs,
        windows=windows,windows_unwind_contexts=windows['windows_unwind_contexts'],windows_emitted=5,pointer_load_windows=3,same_family_release_windows=2,
        accepted_placements=accepted,rejected_placements=rejected,old_window_mutation_controls=mutations,original_parent_unwind_retained=True,
        component33_registry_paths_emulated=True,unrelated_registry_tags_emulated=False,live_getter_registers_preserved=True,
        source_sha256={p:n.sha((n.PROJECT/p).read_bytes()) for p in sources},artifacts={p.name:dict(bytes=p.stat().st_size,sha256=n.sha(p.read_bytes())) for p in (bridge.path,images.path,exe,fixture)},
        external_resource_callbacks_stubbed=True,resource_queue_capacity_enlarged=False,resource_transaction_implemented=False,
        production_owner_bound=False,installed=False,runtime_verified=False,multiplayer_verified=False,game_access=False,native_execution_of_game_bodies=False,
        limits=['Complete saved caller entry, component33 registry dispatch, search, release, refresh and epilogue executed; other registry tags not exercised.', 'Original resource callbacks use explicit stubs and a synthetic template pool. Queue admission, cross-caller resource ownership, fault compensation and common publication remain pending.', 'Getter preflight may write its own stack; refusal does not undo earlier enclosing work. Arithmetic flags are dead until the pinned following CMP/TEST.'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--consumers',type=Path,required=True);p.add_argument('--outer',type=Path,required=True);p.add_argument('--zig',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=validate(Library(a.library),v.Consumers(a.consumers),Outer(a.outer),a.zig);a.out.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({k:result[k] for k in ('passed','functional_runs','original_equivalence_pairs','windows_unwind_contexts','accepted_placements','rejected_placements','game_access')}))
