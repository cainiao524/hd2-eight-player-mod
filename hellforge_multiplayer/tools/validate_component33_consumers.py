"""C++ consumer images in Unicorn, with saved originals and synthetic services."""
import argparse,ctypes as c,json,struct
from pathlib import Path
import native_component33_consumers as consumer
import native_component33_image as n
import validate_component33_images as core
from native_component33_library import Library,Image
from validate_component33_images import G,S,B,E,RSP,STACK,SEEDS,NAMES,LAYOUT,reg,u32,u64,run

CODE={k:G+0x10b00000+i*0x10000 for i,k in enumerate(consumer.KINDS)}
HEAP=0x18501000000;PKG=HEAP+0x20000;TABLE=HEAP+0x80000;API=HEAP+0x90000
STUB={name:G+0x10c00000+i*0x100 for i,name in enumerate(('context','resolve','load','dispose','resource_context','resource_free','resource_make'))}
OWNER=0x18502000000

class Addresses(c.Structure):_fields_=[(k,c.c_uint64) for k in consumer.REFERENCE]
class Consumers:
    def __init__(self,path):
        self.path=path.resolve();self.dll=c.CDLL(str(self.path));self.fn=self.dll.c33_consumer_build
        self.fn.argtypes=[c.c_uint32,c.POINTER(Addresses),c.POINTER(Image)];self.fn.restype=c.c_int
    def build(self,kind,**a):
        r=consumer.build(kind,**a);out=Image();n.need(self.fn(consumer.KINDS.index(kind)+1,Addresses(**a),out)==0,'consumer C++ refused')
        n.need(bytes(out.data[:out.bytes])==r['image'],'C++/independent image mismatch')
        n.need(all(getattr(out,k)==r[k] for k in ('code_bytes','unwind_offset','table_offset','function_count')),'consumer metadata')
        return r

def params(kind,game=G):
    return dict(game_base=game,code_address=game+CODE[kind]-G,component_address=S,storage_address=B,
                release_address=game+CODE['release']-G,reject_address=game+core.REJECT-G)

class Fixture(core.Fixture):
    def __init__(self,lib,images,kind,t,d,p,*,original=False,game=G,ordinal=None,flag=1,control=1,active=1,resource_count=1,queued=False,match=True):
        self.consumer_ready=False
        super().__init__(lib,'mover',t,d,p,original=original,game=game)
        self.kind=kind;self.ordinal=(d-1 if ordinal is None and d else 0) if ordinal is None else ordinal;self.flag=flag
        self.control=control;self.active=active;self.resource_count=resource_count;self.queued=queued;self.match=match
        self.calls=[];self.rows=set();self.reads=[];self.images={};self.entries={}
        for k,f in consumer.profile()['functions'].items():
            artifact=images.build(k,**params(k,game));self.images[k]=artifact;self.put(params(k,game)['code_address'],artifact['image'])
            self.put(game+f['start'],bytes.fromhex(f['body_hex']));self.entries[k]=game+f['start'] if original else params(k,game)['code_address']
        self.artifact=self.images[kind];self.start=self.entries[kind]
        for rva,size in consumer.protected():
            # Only fill data pages, never overwrite already placed source code.
            if rva>=0x3000000:self.put(game+rva,bytes(size))
        self.put(game+0x33267b8,u64(S));self.put(game+0x3483c34,u32(0xffffffff))
        self.put(S,bytes((control,active)))
        for i in range(8):
            self.put(E+64*i,u64(0x12000+i));self.put(E+64*i+16,u32(10+i))
            self.put(PKG+i*0x4000,bytes(0x3030));self.put(PKG+i*0x4000,u64(0x10001+i*128))
            self.put(PKG+i*0x4000+16,u32(1000)+u32(0));self.put(PKG+i*0x4000+0x800,u32(1))
        for i in range(4 if original else 8):
            primary=bytearray(b'\xff'*44+bytes(36));secondary=bytearray(56)
            for j in range(4):struct.pack_into('<Q',primary,48+8*j,0xa000+i*4+j)
            for j in range(1,14):struct.pack_into('<I',secondary,j*4,1)
            struct.pack_into('<I',secondary,0,0x5500+i)
            self.put(self.slot('primary',i),bytes(primary));self.put(self.slot('secondary',i),bytes(secondary))
        self.put(TABLE,bytes(128*16));self.put(game+0x3798180,u64(TABLE)+u32(128)+bytes(4)+u64(0)+u32(1))
        for i in range(8):self.put(TABLE+(i+1)*16,u64(0x10001+i*128)+u64(resource_count))
        self.put(game+0x3797550,bytes(0x400));self.put(game+0x348ba88,u64(0))
        if queued:self.put(game+0x3797550,u64(0x10001+self.ordinal*128)+u64(0xdead));self.put(game+0x348ba88,u64(2))
        self.put(API,bytes(0x2000))
        for rva,ptr in ((0x3326308,API),(0x3326340,API),(0x33265f0,API),(0x3326998,API),
                        (0x347cdd8,HEAP),(0x347cef0,HEAP),(0x346d530,HEAP)):
            self.put(game+rva,u64(ptr))
        self.put(HEAP,bytes(0x14000));self.put(HEAP+0xb3a8,u64(OWNER+self.ordinal*0x100 if match else OWNER+0x1000))
        self.put(API+8,u64(API+0x800));self.put(API+0x10,u64(API+0x800));self.put(API+0x38,u64(API+0x100));self.put(API+0x40,u64(API+0x200))
        table_stubs=((0x108,'context'),(0x360,'resolve'),(0xaf0,'load'),(0xb00,'dispose'),(0xc10,'resource_context'),(0xb88,'resource_free'),(0xb78,'resource_make'))
        for off,name in table_stubs:self.put(API+off,u64(game+STUB[name]-G))
        self.put(API+0x10e8,u64(API+0x1800))
        for address in list(STUB.values())+[G+x for x in (0x4f6430,0x7af0a0,0x664be0,0x665350,0x664f70,0xfd97e0,0x208aaa0)]:self.put(game+address-G,b'\xc3')
        self.uc.reg_write(reg('rcx'),S)
        self.uc.reg_write(reg('rdx'),self.ordinal if kind=='release' else OWNER+self.ordinal*0x100 if match else OWNER+0x1000)
        self.uc.reg_write(reg('r8'),flag)
        self.old=self.read(S+0x70,0x248);self.header=self.read(S+4,0x6c)
        self.blob,self.table,self.count,self.offsets=self.unwind_image()
        self.uc.hook_add(core.unicorn.UC_HOOK_MEM_READ,lambda uc,a,ad,z,v,d:self.reads.append((ad,z)))
        self.consumer_ready=True
    def unwind_image(self):
        blob=bytearray();offsets={};rows=[]
        for k,r in self.images.items():
            while len(blob)%16:blob.append(0)
            off=len(blob);offsets[k]=off;blob.extend(r['image']);seen=set()
            for i in range(r['function_count']):
                a,b,uw=struct.unpack_from('<III',r['image'],r['table_offset']+12*i);rows.append((off+a,off+b,off+uw))
                if uw not in seen and blob[off+uw]>>3&4:
                    at=off+uw+4+((blob[off+uw+2]+1)&~1)*2
                    chain=struct.unpack_from('<III',blob,at);struct.pack_into('<III',blob,at,*(x+off for x in chain))
                seen.add(uw)
        table=len(blob)
        for r in rows:blob.extend(struct.pack('<III',*r))
        return bytes(blob),table,len(rows),offsets
    def normalize(self,value):
        if RSP-512<=value<RSP+128:return 0x200000000+value-RSP
        for k,r in self.images.items():
            base=params(k,self.game)['code_address']
            if base<=value<base+r['code_bytes']:return 0x100000000+self.offsets[k]+value-base
        return value
    def on_code(self,uc,pc,size,data):
        if not self.consumer_ready:return
        self.trace.append(pc)
        if pc in (self.stop,self.reject):self.outcome='return' if pc==self.stop else 'reject';uc.emu_stop();return
        if not self.original:
            for k,r in self.images.items():
                base=params(k,self.game)['code_address']
                if base<=pc<base+r['code_bytes']:
                    stack=bytearray(self.read(RSP-512,640));struct.pack_into('<Q',stack,512,G+0x10500000)
                    for i in range(0,640,8):struct.pack_into('<Q',stack,i,self.normalize(struct.unpack_from('<Q',stack,i)[0]))
                    levels=2 if k=='release' and self.kind!='release' else 1
                    self.rows.add(struct.pack('<IiII8Q',self.offsets[k]+pc-base,uc.reg_read(reg('rsp'))-RSP,0,levels,
                        *(self.normalize(uc.reg_read(reg(x))) for x in NAMES))+stack)
        values={x:uc.reg_read(reg(x)) for x in ('rcx','rdx','r8','r9')};result=None;name=None
        def at(rva):return pc==self.game+rva
        if at(STUB['context']-G):result=API+0x1800;name='context'
        elif at(STUB['resolve']-G):result=OWNER+(values['rdx']-10)*0x100;name='resolve'
        elif at(0x4f6430):result=PKG+(values['rcx']-0x12000)*0x4000;name='package'
        elif at(0x7af0a0):result=100;name='time'
        elif at(0x208aaa0):self.put(values['rcx'],bytes(values['r8']));name='clear_queue'
        else:
            for key in ('load','dispose','resource_context','resource_free','resource_make'):
                if at(STUB[key]-G):name=key;result=0xabc0 if key=='resource_make' else None
            for rva,label in ((0x664be0,'property'),(0x665350,'special'),(0x664f70,'variant'),(0xfd97e0,'publish')):
                if at(rva):name=label
        if name:
            used={'context':(), 'resolve':('rcx','rdx'), 'package':('rcx',), 'time':('rcx','rdx','r8'),
                'clear_queue':('rcx','rdx','r8'), 'load':('rcx',), 'dispose':('rcx',),
                'resource_context':('rcx',),'resource_free':('rcx','rdx','r8'),'resource_make':tuple(values),
                'property':('rdx','r8','r9'),'special':('rdx','r8'),'variant':('rdx','r8','r9'),
                'publish':('rcx','rdx','r8')}[name]
            self.calls.append((name,tuple(value if key in used else 0 for key,value in values.items())))
            if result is not None:uc.reg_write(reg('rax'),result)
            sp=uc.reg_read(reg('rsp'));uc.reg_write(reg('rip'),struct.unpack('<Q',self.read(sp,8))[0]);uc.reg_write(reg('rsp'),sp+8)
    def execute_consumer(self,expected='return'):
        before=self.state()
        try:self.uc.emu_start(self.start,0,count=150000)
        except core.unicorn.UcError as ex:raise ValueError(f'{self.kind} t/d/p={self.t,self.d,self.p} ordinal={self.ordinal} pc={self.uc.reg_read(reg("rip")):x}') from ex
        n.need(self.outcome==expected,'consumer outcome '+str((self.kind,self.outcome)))
        if expected=='reject':
            n.need(before==self.state() and not self.writes and not self.calls,'refusal changed state')
            n.need(self.uc.reg_read(reg('rsp'))==RSP,'refusal stack')
        else:
            n.need(self.uc.reg_read(reg('rsp'))==RSP+8,'consumer return stack')
            for name,value in SEEDS.items():n.need(self.uc.reg_read(reg(name))==value,'consumer nonvolatile '+name)
            for i in range(6,16):n.need(self.uc.reg_read(reg('xmm'+str(i)))==(0x1122334455667788+i)*(1+(1<<64)),'consumer nonvolatile XMM')
        n.need(self.read(S+4,0x6c)==self.header,'consumer map/count mutation')
        if not self.original:
            n.need(self.read(S+0x70,0x248)==self.old,'old arrays modified')
            n.need(not any(a<S+0x2b8 and S+0x70<a+z for a,z in self.reads),'old arrays read')
        n.need(self.read(B-0x80,0x80)==b'\xb6'*0x80 and self.read(B+0x490,0x80)==b'\xb6'*0x80,'consumer canary')
        allowed=[(STACK,0x10000),(S,2),(TABLE,2048),(self.game+0x3797550,0x400),(self.game+0x348ba88,8)]
        allowed += [(self.slot(name,0),stride*(4 if self.original else 8)) for name,(_,_,stride) in LAYOUT.items()]
        for address,size in self.writes:n.need(any(lo<=address and address+size<=lo+length for lo,length in allowed),'consumer write escaped '+hex(address))
        return self
    def canonical(self):
        slots=4 if self.original else 8
        def v(x):
            for name,(new,old,stride) in LAYOUT.items():
                start=self.slot(name,0)
                if start<=x<start+slots*stride:return ('array',name,x-start)
            return x
        return dict(rows={(name,i):self.read(self.slot(name,i),stride) for name,(_,_,stride) in LAYOUT.items() for i in range(4)},
            control=self.read(S,2),table=self.read(TABLE,2048),queue=self.read(self.game+0x3797550,0x400),
            queued=self.read(self.game+0x348ba88,8),calls=[(name,tuple(v(x) for x in args)) for name,args in self.calls])

def validate(lib,images,zig):
    n.need(consumer.HEADER.read_bytes()==consumer.render(),'consumer header stale');runs=[];contexts=set();comparisons=0
    def execute(f,expected='return',case='matrix'):
        f.execute_consumer(expected);contexts.update(f.rows);runs.append(dict(kind=f.kind,t=f.t,d=f.d,p=f.p,ordinal=f.ordinal,
            flag=f.flag,original=f.original,outcome=f.outcome,case=case,instructions=len(f.trace),calls=len(f.calls)));return f
    cases=[]
    for kind in consumer.KINDS:
        for t,d,p in ((0,0,0),(1,1,0),(4,4,2),(4,2,1)):
            if kind=='release' and not d:continue
            for flag in ((0,1) if kind=='release' else (1,)):
                cases.append((kind,t,d,p,dict(flag=flag)))
    cases+=[('update',4,4,2,dict(control=0)),('update',4,4,2,dict(active=0)),('update',4,4,2,dict(queued=True)),
            ('acquire',4,4,2,dict(resource_count=0,queued=True)),('acquire',4,4,2,dict(resource_count=2)),
            ('acquire',4,4,2,dict(match=False)),('defer',4,4,2,dict(match=False))]
    for kind,t,d,p,args in cases:
        old=execute(Fixture(lib,images,kind,t,d,p,original=True,**args),case='original')
        new=execute(Fixture(lib,images,kind,t,d,p,**args),case='equivalent')
        n.need(old.canonical()==new.canonical(),'consumer original equivalence '+str((kind,t,d,p,args)));comparisons+=1
    for game in (G,G+0x80000000):
        for kind in consumer.KINDS:
            for t,d,p in ((5,5,2),(8,8,4),(8,3,1),(8,0,0)):
                if kind=='release' and not d:continue
                for ordinal in (range(d) if kind=='release' else (None,)):
                    for flag in ((0,1) if kind=='release' else (1,)):
                        f=execute(Fixture(lib,images,kind,t,d,p,game=game,ordinal=ordinal,flag=flag))
                        if kind=='release':
                            n.need(struct.unpack('<Q',f.read(TABLE+(f.ordinal+1)*16+8,8))[0]==0,'wrong resource released')
                            n.need(f.int32(game+0x348ba88)==flag,'deferred count')
                            if flag:n.need(f.read(game+0x3797550,8)==u64(0x10001+f.ordinal*128),'wrong deferred identity')
                        if kind in ('acquire','defer') and d:
                            calls=[args[0] for name,args in f.calls if name=='package']
                            n.need(calls==[0x12000+d-1]*(2 if kind=='acquire' else 1),'selected wrong dense entity')
                        if kind=='update':
                            entities={args[1] for name,args in f.calls if name in ('property','special','variant')}
                            n.need(entities=={E+64*i for i in range(d)},'update omitted dense entity')
                            n.need(sum(name=='publish' for name,args in f.calls)==4*p,'update prefix publication count')
    for kind in consumer.KINDS:
        for label,address,blob in (('global',G+0x33267b8,u64(S+8)),('total',S+8,u32(9)),('dense',S+12,u32(9)),('prefix',S+16,u32(9)),
            ('map_pointer',S+0x58,u64(S+0x18)),('map_size',S+0x60,u32(4)),('map_mode',S+0x64,u32(1)),
            ('null_entity',B+56,u64(0)),('map_identity',S+0x18+56,u32(0)),('invalid_id',E+8,u32(0xffffffff))):
            f=Fixture(lib,images,kind,8,8,4);f.put(address,blob);f.header=f.read(S+4,0x6c);execute(f,'reject',label)
    for ordinal in (8,0xffffffff):execute(Fixture(lib,images,'release',8,8,4,ordinal=ordinal),'reject','ordinal')
    mutations=[]
    for kind in consumer.KINDS:
        f=Fixture(lib,images,kind,8,8,4);r=f.images[kind]
        first=r['array_patches'][0];start=r['instruction_map'][int(first['rva'],16)]
        # Rebind the first migrated instruction to its original inline S base.
        f.put(f.start+start+2,u64(S));faults=[]
        f.uc.hook_add(core.unicorn.UC_HOOK_MEM_INVALID,lambda uc,a,ad,z,v,d:(faults.append(ad) or False))
        try:f.execute_consumer()
        except (ValueError,core.unicorn.UcError):pass
        else:raise ValueError('old-array mutation escaped '+kind)
        n.need(any(a<S+0x2b8 and S+0x70<a+z for a,z in f.reads),'mutation did not reach old array')
        mutations.append(kind+'.old_array')
    for kind in ('acquire','defer'):
        f=Fixture(lib,images,kind,8,8,4);r=f.images[kind]
        off,nxt,key,width,add=next(x for x in r['fixups'] if x[2]=='release_address')
        f.put(f.start+off,struct.pack('<i',f.game+0x6659e0-f.start-nxt))
        try:f.execute_consumer()
        except (ValueError,core.unicorn.UcError):pass
        else:raise ValueError('old release mutation escaped')
        n.need(f.game+0x6659e0 in f.trace,'old release was not called');mutations.append(kind+'.old_release')
    # Preserve a concrete original limitation instead of claiming that array
    # relocation implements resource queue admission. This deliberately
    # incoherent count=128 / zero-filled-queue state is not normal reachability
    # evidence. One more deferred item
    # at count 128 overwrites the first qword after the saved 1024-byte queue.
    f=Fixture(lib,images,'release',8,8,4,ordinal=7,flag=1)
    n.need(f.read(G+0x3797550,1024)==bytes(1024),'counterexample assumes empty queue storage')
    f.put(G+0x348ba88,u64(128));f.put(G+0x3797950,b'\xcc'*8)
    try:f.execute_consumer()
    except ValueError as error:n.need('write escaped' in str(error),'wrong queue capacity counterexample')
    else:raise ValueError('queue overflow evidence disappeared; update contract')
    n.need(f.int32(G+0x348ba88)==129 and f.read(G+0x3797950,8)==u64(0x10001+7*128),'queue counterexample not reproduced')
    accepted=rejected=0
    for kind in consumer.KINDS:
        placements=[consumer.REFERENCE,{**consumer.REFERENCE,'game_base':consumer.REFERENCE['game_base']+0x80000000}]
        for key in consumer.REFERENCE:
            for value in (0,1,1<<47,(1<<47)-16):placements.append({**consumer.REFERENCE,key:value})
        for key in ('component_address','storage_address','release_address','reject_address'):placements.append({**consumer.REFERENCE,key:consumer.REFERENCE['code_address']+16})
        for rva,size in consumer.protected():placements.append({**consumer.REFERENCE,'code_address':consumer.REFERENCE['game_base']+(rva&~15)})
        placements.append({**consumer.REFERENCE,'code_address':consumer.REFERENCE['game_base']+0x100000000})
        for a in placements:
            try:consumer.build(kind,**a);valid=True
            except (ValueError,struct.error,OverflowError):valid=False
            out=Image();c.memset(c.byref(out),0xa5,c.sizeof(out));rc=images.fn(consumer.KINDS.index(kind)+1,Addresses(**a),out)
            n.need((rc==0)==valid and (valid or not any(bytes(out))),'placement agreement')
            if valid:images.build(kind,**a);accepted+=1
            else:rejected+=1
    for kind in (0,5):n.need(images.fn(kind,Addresses(**consumer.REFERENCE),Image())!=0,'unknown kind')
    n.need(images.fn(1,None,Image())!=0 and images.fn(1,Addresses(**consumer.REFERENCE),None)!=0,'null arguments')
    sample=Fixture(lib,images,'update',8,8,4);blob=sample.blob;rows=sorted(contexts);bad=bytearray(blob)
    root=consumer.profile()['functions']['update']['fragments'][0];uw=struct.unpack_from('<I',blob,sample.table+12+8)[0]
    # Change the root's stack-allocation unwind operation, keeping its body.
    raw=bytes.fromhex(root['unwind_hex']);pos=next(i for i in range(4,4+raw[2]*2,2) if raw[i+1]&15==2)
    bad[uw+pos+1]^=0x10
    off=sample.images['update']['instruction_map'][0x664539];negative=bytearray(next(r for r in rows if struct.unpack_from('<I',r)[0]==off));struct.pack_into('<I',negative,8,1)
    packed=bytearray(b'EPCCNW1\0'+u32(2))
    for image,items in ((bad,[negative]),(blob,rows)):
        packed.extend(struct.pack('<4I',len(image),sample.table,sample.count,len(items)));packed.extend(image)
        packed.extend(struct.pack('<9Q',*(SEEDS[k] for k in NAMES),G+0x10500000));packed.extend(b''.join(items))
    fixture=n.PROJECT/'build/component33-consumers-unwind.bin';fixture.write_bytes(packed)
    exe=n.PROJECT/'build/native_component33_consumers_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',n.PROJECT/'tests/native_component33_consumers_unwind_test.c','-o',exe]);windows=json.loads(run([exe,fixture]))
    sources=['native-component33-consumers.lock.json','tools/native_component33_consumers.py','tools/validate_component33_consumers.py',
        'mod/src/ep_component33_consumers.h','mod/src/ep_component33_consumers.cpp','mod/src/ep_component33_consumers_template.h',
        'tests/component33_consumers_dll.cpp','tests/native_component33_consumers_unwind_test.c','tools/native_component33_image.py',
        'tools/validate_component33_images.py','tools/native_component33_library.py','native-component33.lock.json']
    return dict(schema='hellforge_component33_consumers_validation_v1',passed=True,functional_runs=len(runs),runs=runs,
        original_equivalence_pairs=comparisons,windows=windows,windows_unwind_contexts=windows['windows_unwind_contexts'],
        accepted_placements=accepted,rejected_placements=rejected,consumer_images=4,
        old_array_and_helper_mutation_controls=mutations,deferred_queue_overflow_counterexample_reproduced=True,
        deferred_queue_overflow_counterexample_is_incoherent=True,
        source_sha256={p:n.sha((n.PROJECT/p).read_bytes()) for p in sources},
        artifacts={p.name:dict(bytes=p.stat().st_size,sha256=n.sha(p.read_bytes())) for p in (images.path,exe,fixture)},
        original_resource_queue_capacity=128,queue_capacity_enlarged=False,resource_transaction_implemented=False,
        external_resource_callbacks_stubbed=True,remaining_inline_consumers_closed=False,production_owner_bound=False,
        installed=False,runtime_verified=False,multiplayer_verified=False,game_access=False,native_execution_of_game_bodies=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--consumers',type=Path,required=True);p.add_argument('--zig',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=validate(Library(a.library),Consumers(a.consumers),a.zig);a.out.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({k:result[k] for k in ('passed','functional_runs','original_equivalence_pairs','windows_unwind_contexts','accepted_placements','rejected_placements','game_access')}))
