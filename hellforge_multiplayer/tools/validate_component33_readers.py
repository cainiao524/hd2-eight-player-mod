"""Execute saved post-creation loops and C++ bridge/reset in synthetic memory."""
import argparse,ctypes as c,json,struct
from pathlib import Path
import native_component33_readers as reader
import native_component33_image as n
import validate_component33_images as core
import component33_initialization_fixture as init
from native_component33_library import Library,Image
from validate_component33_images import G,S,B,E,RSP,STACK,SEEDS,NAMES,reg,u32,u64,run

class Addresses(c.Structure):
    _fields_=[(k,c.c_uint64) for k in reader.REFERENCE]
class Window(c.Structure):
    _fields_=[('target',c.c_uint64),('bytes',c.c_uint32),('call_offset',c.c_uint32),('expected',c.c_ubyte*16),('replacement',c.c_ubyte*16)]
class Plan(c.Structure):
    _fields_=[('bridge',Image),('windows',Window*2)]
class Readers:
    def __init__(self,path):
        self.path=Path(path).resolve();self.dll=c.CDLL(str(self.path));self.fn=self.dll.component33_readers_test_build
        self.fn.argtypes=[c.POINTER(Addresses),c.POINTER(Plan)];self.fn.restype=c.c_int
    def build(self,a):
        r=reader.build(**a);p=Plan();n.need(self.fn(Addresses(**a),p)==0,'reader C++ emission failed')
        n.need(bytes(p.bridge.data[:p.bridge.bytes])==r['image'],'reader image mismatch')
        n.need(tuple(getattr(p.bridge,k) for k in ('code_bytes','unwind_offset','table_offset','function_count'))==tuple(r[k] for k in ('code_bytes','unwind_offset','table_offset','function_count')),'reader metadata')
        for x,y in zip(p.windows,r['windows']):
            n.need((x.target,x.bytes,x.call_offset)==tuple(y[k] for k in ('target','bytes','call_offset')) and bytes(x.expected[:x.bytes])==y['expected'] and bytes(x.replacement[:x.bytes])==y['replacement'],'reader window mismatch')
        return r

class Fixture(init.Fixture):
    def __init__(self,lib,readers,name,t,d,*,game=G,original=False):
        self.contract=None;self.calls=[];self.rows=set();self.getter_calls=0;self.name=name
        super().__init__(lib,'reset',t,0,game=game,original=original)
        saved=n.profile()['functions']['reset'];self.put(game+saved['start'],bytes.fromhex(saved['body_hex']))
        self.d=d;self.p=min(d,1);self.put(S+12,u32(d)+u32(self.p));self.put(S,b'\xa5\xa5')
        self.a=dict(game_base=game,code_address=game+0x10900000,component_address=S,storage_address=B,
                    reset_address=self.start,reject_address=self.reject)
        # Original execution still generates the candidate using its real reset
        # address, then runs the unmodified original caller and helper instead.
        if original:self.a['reset_address']=init.addresses('reset',game)['code_address']
        self.plan=readers.build(self.a);self.contract=reader.profile()['callers'][name];f=self.contract
        self.parent=bytearray.fromhex(f['body_hex']);self.window=self.plan['windows'][int(name=='batch')]
        if not original:
            at=self.window['target']-game-f['start'];self.parent[at:at+self.window['bytes']]=self.window['replacement']
        self.put(game+f['start'],bytes(self.parent));self.put(self.a['code_address'],self.plan['image'])
        self.entry=game+f['start'];self.windows_blob,self.windows_table,self.windows_functions,self.bridge_off,self.reset_off=self.unwind_image()
    def unwind_image(self):
        f=self.contract;blob=bytearray(self.parent)
        def align():
            while len(blob)%16:blob.append(0)
        align();bridge=len(blob);blob.extend(self.plan['image']);align();reset=len(blob);blob.extend(self.artifact['image']);align()
        uwmap={}
        for row in f['fragments']:
            uwmap[row['unwind_rva']]=len(blob);blob.extend(bytes.fromhex(row['unwind_hex']));align()
        rows=[]
        for row in f['fragments']:
            off=uwmap[row['unwind_rva']];flags=blob[off]>>3;end=off+4+((blob[off+2]+1)&~1)*2
            if flags&4:
                a,b,uw=struct.unpack_from('<III',blob,end);struct.pack_into('<III',blob,end,a-f['start'],b-f['start'],uwmap[uw])
            rows.append((row['start']-f['start'],row['end']-f['start'],off))
        rows.append((bridge,bridge+self.plan['code_bytes'],bridge+self.plan['unwind_offset']))
        changed=set()
        for i in range(self.artifact['function_count']):
            a,b,uw=struct.unpack_from('<III',self.artifact['image'],self.artifact['table_offset']+i*12);rows.append((reset+a,reset+b,reset+uw))
            if uw not in changed and blob[reset+uw]>>3&4:
                at=reset+uw+4+((blob[reset+uw+2]+1)&~1)*2
                chain=struct.unpack_from('<III',blob,at);struct.pack_into('<III',blob,at,*(x+reset for x in chain))
            changed.add(uw)
        table=len(blob)
        for row in rows:blob.extend(struct.pack('<III',*row))
        return bytes(blob),table,len(rows),bridge,reset
    def normalize(self,v):
        if RSP-512<=v<RSP+128:return 0x200000000+v-RSP
        f=self.contract
        for base,length,off in ((self.game+f['start'],len(self.parent),0),(self.a['code_address'],self.plan['code_bytes'],self.bridge_off),(self.start,self.artifact['code_bytes'],self.reset_off)):
            if base<=v<base+length:return 0x100000000+v-base+off
        return v
    def on_code(self,uc,pc,size,data):
        self.trace.append(pc)
        if pc in (self.stop,self.reject):self.outcome='return' if pc==self.stop else 'reject';uc.emu_stop();return
        f=self.contract
        if f is None:return
        root=self.game+f['start'];offset=None;levels=1
        if root<=pc<root+len(self.parent):offset=pc-root
        elif not self.original:
            for base,length,off in ((self.a['code_address'],self.plan['code_bytes'],self.bridge_off),(self.start,self.artifact['code_bytes'],self.reset_off)):
                if base<=pc<base+length:offset=pc-base+off;levels=2
        if offset is not None and not self.original:
            stack=bytearray(self.read(RSP-512,640));struct.pack_into('<Q',stack,512,G+0x10500000)
            for i in range(0,len(stack),8):struct.pack_into('<Q',stack,i,self.normalize(struct.unpack_from('<Q',stack,i)[0]))
            self.rows.add(struct.pack('<IiII8Q',offset,uc.reg_read(reg('rsp'))-RSP,0,levels,*(self.normalize(uc.reg_read(reg(k))) for k in NAMES))+stack)
        if pc==self.game+f['frame_end']:
            uc.reg_write(reg('rip'),self.game+(0xADDC78 if self.name=='single' else 0xB62249));return
        if pc==self.game+(0xADDC7A if self.name=='single' else 0xB62271):
            uc.reg_write(reg('rip'),self.game+f['post_creation']);return
        if pc==self.a['code_address']:
            self.getter_calls+=1;n.need(uc.reg_read(reg('rsp'))==RSP-(272 if self.name=='single' else 288),'reader call frame')
            n.need(uc.reg_read(reg('rcx'))==S and uc.reg_read(reg('rdx'))==len(self.calls),'reader caller ABI')
        if pc in (self.start,self.game+0x664430):
            entity=uc.reg_read(reg('rdx'));self.calls.append(entity)
            n.need(uc.reg_read(reg('rcx'))==S,'reset caller S')
        if pc==self.game+f['after_loop']:
            n.need(uc.reg_read(reg('rdi'))==self.d,'loop did not retain final ordinal')
            uc.reg_write(reg('rip'),self.game+f['epilogue']);return
        if self.name=='batch' and pc==self.game+0xB6247F:uc.reg_write(reg('rip'),self.game+0xB6248B)
    def execute_loop(self,expected='return'):
        header_before=self.read(S+4,0x6C)
        self.uc.emu_start(self.entry,0,count=50000);n.need(self.outcome==expected,'reader outcome '+str(self.outcome))
        if expected=='return':
            n.need(self.calls==[E+64*i for i in range(self.d)],'wrong reset identity/order')
            n.need(self.getter_calls==(0 if self.original else self.d),'bridge call count')
            n.need(self.read(S,2)==b'\x01\x01','post-creation flag order')
            n.need(self.uc.reg_read(reg('rsp'))==RSP+8,'caller return stack')
            for k,v in SEEDS.items():n.need(self.uc.reg_read(reg(k))==v,'caller nonvolatile '+k)
            for i in range(6,16):n.need(self.uc.reg_read(reg('xmm'+str(i)))==(0x1122334455667788+i)*(1+(1<<64)),'caller XMM')
        for (name,i),old in self.records.items():
            expected_row=b'\xff'*44+old[44:] if name=='primary' and i<len(self.calls)-(1 if expected=='reject' and self.calls else 0) else old
            n.need(self.read(self.slot(name,i),len(old))==expected_row,'post-creation payload '+str((name,i)))
        n.need(self.read(S+0x14,64)==b''.join(u32(k)+u32(v) for k,v in self.table),'caller map changed')
        n.need(self.read(S+4,0x6C)==header_before,'caller header changed')
        n.need(self.read(B-0x80,0x80)==b'\xb6'*0x80 and self.read(B+0x490,0x80)==b'\xb6'*0x80,'reader storage canary')
        if not self.original:n.need(self.read(S+0x70,0x248)==b'\xa5'*0x248,'caller touched old arrays')
        allowed=[(STACK,0x10000),(S,2)]+[(self.slot('primary',i),44) for i in range(self.d)]
        for a,z in self.writes:n.need(any(lo<=a and a+z<=lo+length for lo,length in allowed),'caller unexpected write')
        return self

def validate(lib,readers,zig):
    n.need(reader.HEADER.read_bytes()==reader.render(),'reader header stale');runs=[];contexts={name:set() for name in reader.profile()['callers']};samples={}
    def execute(f,expected='return',case='matrix'):
        f.execute_loop(expected);contexts[f.name].update(f.rows);samples[f.name]=f
        runs.append(dict(caller=f.name,t=f.t,d=f.d,original=f.original,game_base=hex(f.game),outcome=f.outcome,case=case,reset_calls=len(f.calls),bridge_calls=f.getter_calls));return f
    for name in contexts:
        for game in (G,G+0x80000000):
            for t,d in ((0,0),(1,1),(4,4),(5,5),(8,8),(8,3),(8,0)):
                execute(Fixture(lib,readers,name,t,d,game=game))
        for t,d in ((0,0),(4,4),(4,2)):
            execute(Fixture(lib,readers,name,t,d,original=True),case='original')
        f=Fixture(lib,readers,name,8,8);f.put(S+8,u32(9));execute(f,'reject','count_bound')
        n.need(f.read(S,2)==b'\xa5\x01' and not f.calls,'guard did not preserve original pre-call flag write')
        f=Fixture(lib,readers,name,8,8);f.put(B,u64(0));f.records['pointer',0]=u64(0);execute(f,'reject','null_pointer')
        # Later helper refusal cannot undo an earlier entity reset or the flag.
        f=Fixture(lib,readers,name,8,8);f.put(E+64+8,u32(999));execute(f,'reject','late_identity_failure')
        n.need(len(f.calls)==2 and f.read(S,2)==b'\xa5\x01','late refusal did not retain partial work')
    controls=[]
    for name in contexts:
        f=Fixture(lib,readers,name,8,8);f.put(f.window['target'],f.window['expected']);fault=[]
        f.uc.hook_add(core.unicorn.UC_HOOK_MEM_INVALID,lambda uc,a,ad,z,v,d:(fault.append(ad) or False))
        try:f.uc.emu_start(f.entry,0,count=50000)
        except core.unicorn.UcError as ex:n.need(ex.errno==core.unicorn.UC_ERR_READ_UNMAPPED,'wrong old-reader failure')
        n.need(fault and f.calls==[0xA5A5A5A5A5A5A5A5] and f.uc.reg_read(reg('rip'))==f.game+0x664434,'old reader not detected');controls.append(name+'.old_window')
        f=Fixture(lib,readers,name,8,8)
        off=next(off for off,key in f.plan['fixups'] if key=='reset_address');f.put(f.a['code_address']+off,u64(f.game+0x664430))
        try:f.execute_loop()
        except ValueError as ex:
            n.need(str(ex)=="post-creation payload ('primary', 0)" and f.read(S+0x98,44)==b'\xff'*44 and f.read(B+0x50,44)==f.records['primary',0][:44],'wrong old-reset failure')
        else:raise ValueError('original reset mutation escaped')
        controls.append(name+'.old_reset')
    accepted=rejected=0
    placements=[reader.REFERENCE,{**reader.REFERENCE,'game_base':reader.REFERENCE['game_base']+0x80000000}]
    for key in reader.REFERENCE:
        for value in (0,1,1<<47,(1<<47)-16):placements.append({**reader.REFERENCE,key:value})
    for key in ('component_address','storage_address','reset_address','reject_address'):placements.append({**reader.REFERENCE,key:reader.REFERENCE['code_address']+16})
    for off,size in reader.protected():placements.append({**reader.REFERENCE,'code_address':reader.REFERENCE['game_base']+(off&~15)})
    placements.append({**reader.REFERENCE,'code_address':reader.REFERENCE['game_base']+0x100000000})
    for a in placements:
        try:ref=reader.build(**a)
        except (ValueError,struct.error,OverflowError):ref=None
        out=Plan();c.memset(c.byref(out),0xa5,c.sizeof(out));rc=readers.fn(Addresses(**a),out)
        if ref is None:n.need(rc!=0 and not any(bytes(out)),'reader accepted bad placement');rejected+=1
        else:readers.build(a);accepted+=1
    out=Plan();n.need(readers.fn(None,out)!=0 and not any(bytes(out)) and readers.fn(Addresses(**reader.REFERENCE),None)!=0,'reader null contract')
    fixture=n.PROJECT/'build/component33-readers-unwind.bin';packed=bytearray(b'EPRDRW1\0'+u32(4))
    for name in contexts:
        sample=Fixture(lib,readers,name,8,8);blob=sample.windows_blob;rows=sorted(contexts[name]);table=sample.windows_table
        # Original parent ALLOC_LARGE operand: corrupt only its stack size.
        parent_uw=struct.unpack_from('<I',blob,table+8)[0];bad=bytearray(blob);bad[parent_uw+(14 if name=='single' else 6)]^=1
        neg=bytearray(next(x for x in rows if struct.unpack_from('<I',x)[0]==sample.contract['post_creation']-sample.contract['start']));struct.pack_into('<I',neg,8,1)
        for image,items in ((bad,[neg]),(blob,rows)):
            packed.extend(struct.pack('<4I',len(image),table,sample.windows_functions,len(items)));packed.extend(image)
            packed.extend(struct.pack('<9Q',*(SEEDS[k] for k in NAMES),G+0x10500000));packed.extend(b''.join(items))
    fixture.write_bytes(packed);exe=n.PROJECT/'build/native_component33_readers_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',n.PROJECT/'tests/native_component33_readers_unwind_test.c','-o',exe]);windows=json.loads(run([exe,fixture]))
    paths=['native-component33-readers.lock.json','tools/native_component33_readers.py','tools/validate_component33_readers.py','mod/src/ep_component33_readers.h','mod/src/ep_component33_readers.cpp','mod/src/ep_component33_readers_template.h','tests/component33_readers_dll.cpp','tests/native_component33_readers_unwind_test.c','tools/component33_initialization_fixture.py','tools/validate_component33_images.py','tools/native_component33_image.py','tools/native_component33_library.py','native-component33.lock.json']
    return dict(schema='hellforge_component33_post_creation_readers_validation_v1',passed=True,functional_runs=len(runs),runs=runs,
        windows=windows,windows_unwind_contexts=windows['windows_unwind_contexts'],old_reader_mutation_controls=controls,
        accepted_placements=accepted,rejected_placements=rejected,reader_windows_emitted=2,bridge_image_emitted=True,
        per_entity_reset_target_rva='0x664430',batch_reset_dense_used=False,late_failure_partial_reset_reproduced=True,
        selected_caller_paths_emulated=True,whole_creation_caller_emulated=False,original_parent_unwind_retained=True,
        source_sha256={p:n.sha((n.PROJECT/p).read_bytes()) for p in paths},artifacts={p.name:dict(bytes=p.stat().st_size,sha256=n.sha(p.read_bytes())) for p in (lib.path,readers.path,exe,fixture)},
        production_owner_bound=False,installed=False,runtime_verified=False,multiplayer_verified=False,game_access=False,native_execution_of_game_bodies=False,
        limits=['Execute saved entry frame/conditional saves, post-creation loop and epilogue only; creation, other actions and parent GS checks skipped.',
            'Original D==0 bypass and pre-call flag write retained; no complete admission/creation transaction or rollback.',
            'All windows, exact bridge/reset images, owner instance, remaining readers/writers and lifetimes require coordinated publication.'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--readers',type=Path,required=True);p.add_argument('--zig',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=validate(Library(a.library),Readers(a.readers),a.zig);a.out.write_bytes((json.dumps(r,indent=2)+'\n').encode());print(json.dumps({k:r[k] for k in ('passed','functional_runs','windows_unwind_contexts','accepted_placements','rejected_placements','game_access')}))
