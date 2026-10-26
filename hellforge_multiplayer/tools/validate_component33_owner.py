"""Execute the pinned owner frame, patched inline window and next component offline."""
import argparse,ctypes as c,json,struct
from pathlib import Path
import native_component33_owner as owner
import native_component33_image as n
import validate_component33_transition as tr
from native_component33_library import Library
from validate_component33_images import G,S,B,E,RSP,STACK,SEEDS,NAMES,reg,u32,u64,run

class Patch(c.Structure):
    _fields_=[('target',c.c_uint64),('bytes',c.c_uint32),('call_offset',c.c_uint32),('expected',c.c_ubyte*75),('replacement',c.c_ubyte*75)]

def bind(lib):
    fn=lib.dll.component33_owner_test_build;fn.argtypes=[c.c_uint64,c.c_uint64,c.POINTER(Patch)];fn.restype=c.c_int
    return fn

def emitted(fn,game,promote):
    p=Patch();reference=owner.build(game,promote)
    n.need(fn(game,promote,p)==0,'C++ owner emission failed')
    n.need((p.target,p.bytes,p.call_offset)==tuple(reference[k] for k in ('target','bytes','call_offset')),'owner metadata mismatch')
    n.need(bytes(p.expected)==reference['expected'] and bytes(p.replacement)==reference['replacement'],'owner bytes mismatch')
    return reference

class Fixture(tr.Fixture):
    def __init__(self,lib,fn,t,d,p,*,next_count=2,original=False,game=G):
        self.owner_contexts=set();self.calls=0;self.next_reached=False;self.next_count=next_count;self.continued=False
        super().__init__(lib,t,d,p,original=original,game=game)
        self.contract=owner.profile();r=self.contract;self.owner=S-0x3CA0;self.next=S+0x2B8
        im=n.Image(n.ROOT/r['capture_directory']);self.raw_owner=im.read(r['owner']['start'],r['owner']['end']-r['owner']['start'])
        self.owner_code=bytearray(self.raw_owner);self.patch=emitted(fn,game,tr.core.addresses(tr.KIND,game)['code_address'])
        at=r['window']['start']-r['owner']['start']
        if not original:self.owner_code[at:at+75]=self.patch['replacement']
        self.promote_offset=(len(self.owner_code)+15)&~15
        self.put(game+r['owner']['start'],bytes(self.owner_code))
        for key in ('next_component','prologue_constant'):
            f=r[key];self.put(game+f['start'],bytes.fromhex(f['body_hex']))
        self.put(self.owner,bytes(0x40));self.put(self.next,bytes(0x60));self.put(self.next+8,u32(next_count)+u32(0)+u32(0))
        self.uc.reg_write(reg('rcx'),self.owner);self.uc.reg_write(reg('rdx'),0x12345678)
        self.entry=game+r['owner']['start'];self.snapshots=[]

    def on_code(self,uc,pc,size,data):
        self.trace.append(pc)
        if pc in (self.stop,self.reject):self.outcome='return' if pc==self.stop else 'reject';uc.emu_stop();return
        r=getattr(self,'contract',None)
        if r is None:return
        root=self.game+r['owner']['start'];end=self.game+r['owner']['end']
        promoter=tr.core.addresses(tr.KIND,self.game)['code_address']
        if not self.original and (root<=pc<end or promoter<=pc<promoter+self.artifact['code_bytes']):
            offset=pc-root if root<=pc<end else self.promote_offset+pc-promoter
            stack=bytearray(self.read(RSP-128,256));struct.pack_into('<Q',stack,128,G+0x10500000)
            if promoter<=pc<promoter+self.artifact['code_bytes']:
                ret=struct.unpack_from('<Q',stack,64)[0]
                n.need(ret==self.patch['target']+self.patch['call_offset']+5,'promoter return address')
                struct.pack_into('<Q',stack,64,ret-self.game+G)
            xmm=uc.reg_read(reg('xmm6'))
            self.owner_contexts.add(struct.pack('<IiI8Q2Q',offset,uc.reg_read(reg('rsp'))-RSP,0,
                *(uc.reg_read(reg(k)) for k in NAMES),xmm&((1<<64)-1),xmm>>64)+stack)
        if pc==self.game+r['prologue']['end']:
            # Omit unrelated component updates; retain the actual entry frame.
            uc.reg_write(reg('rip'),self.game+r['window']['start']);return
        if pc==promoter:
            self.calls+=1;n.need(uc.reg_read(reg('rsp'))==RSP-64,'owner call alignment/stack depth')
            n.need(uc.reg_read(reg('rcx'))==S,'owner passed wrong component')
        if pc==self.game+r['continuation']['start']:
            self.continued=True
            n.need(uc.reg_read(reg('rsi'))==S and uc.reg_read(reg('rdi'))==self.t and uc.reg_read(reg('rax'))==self.t,'owner continuation live registers')
            if self.d<self.t:n.need(uc.reg_read(reg('rdx'))==self.p+self.t-self.d,'pending continuation EDX')
            else:n.need(uc.reg_read(reg('rdx'))==0x12345678,'no-pending volatile passthrough')
        if pc==self.game+0x577B6B:
            # Original inline loop stores D at 577B68, after the window.
            writes=self.writes;self.writes=[(a,z) for a,z in writes if not STACK<=a<STACK+0x10000]
            try:tr.Fixture.check_model(self)
            finally:self.writes=writes
        if pc==self.game+r['next_component']['start']:
            self.next_reached=True;n.need(uc.reg_read(reg('rcx'))==self.next,'next component argument')
        if pc==self.game+r['continuation']['end']:
            n.need(self.int32(self.next+12)==self.next_count and self.int32(self.next+16)==self.next_count,'next component did not complete')
            uc.reg_write(reg('rip'),self.game+r['epilogue']['start'])

    def execute_owner(self,expected='return'):
        before=self.state();self.uc.emu_start(self.entry,0,count=20000)
        n.need(self.outcome==expected,'owner outcome '+str(self.outcome))
        if expected=='reject':
            n.need(self.state()==before and not self.continued and not self.next_reached,'rejected pending path changed data or continued')
            n.need(all(STACK<=a and a+z<=STACK+0x10000 for a,z in self.writes),'rejection wrote data')
            n.need(self.uc.reg_read(reg('rsp'))==RSP-64,'rejection lost owner call frame')
        else:
            n.need(self.continued and self.next_reached,'owner continuation missing')
            n.need(self.calls==int(not self.original and self.d<self.t),'wrong promotion routing')
            n.need(self.uc.reg_read(reg('rsp'))==RSP+8,'owner return stack')
            for name,value in SEEDS.items():n.need(self.uc.reg_read(reg(name))==value,'owner nonvolatile '+name)
            for i in range(6,16):n.need(self.uc.reg_read(reg('xmm'+str(i)))==(0x1122334455667788+i)*(1+(1<<64)),'owner XMM preservation')
            allowed=[(STACK,0x10000),(S+4,0x50),(self.next+12,8)]+[(self.slot(k,0),stride*(4 if self.original else 8)) for k,(_,_,stride) in tr.LAYOUT.items()]
            for a,z in self.writes:n.need(any(lo<=a and a+z<=lo+length for lo,length in allowed),'unexpected owner write '+hex(a))
        return self

def validate(lib,zig):
    fn=bind(lib);n.need(owner.HEADER.read_bytes()==owner.render(),'owner template stale');r=owner.profile();runs=[];contexts=set()
    def execute(f,expected='return'):
        f.execute_owner(expected);contexts.update(f.owner_contexts)
        runs.append(dict(t=f.t,d=f.d,p=f.p,next_count=f.next_count,original=f.original,game_base=hex(f.game),
            outcome=f.outcome,promotion_calls=f.calls,next_component_reached=f.next_reached,identities_preserved=getattr(f,'identities_preserved',None)))
        return f
    cases=[(0,0,0),(4,4,2),(5,4,4),(5,4,2),(8,7,3),(8,0,0),(8,8,8),(8,3,0),(8,3,3),(2,1,0)]
    for game in (G,G+0x80000000):
        for next_count in (0,2):
            for t,d,p in cases:execute(Fixture(lib,fn,t,d,p,next_count=next_count,game=game))
    for state in ((4,2,1),(4,2,2),(4,4,1),(0,0,0)):
        old=execute(Fixture(lib,fn,*state,original=True));new=execute(Fixture(lib,fn,*state))
        if old.identities_preserved:
            n.need(old.read(S,0x70)==new.read(S,0x70),'equivalent owner header mismatch')
            for name,(_,_,stride) in tr.LAYOUT.items():
                for i in range(4):n.need(old.read(old.slot(name,i),stride)==new.read(new.slot(name,i),stride),'equivalent owner arrays mismatch')
    for address,blob in ((G+0x33267B8,u64(S+8)),(S+8,u32(9)),(E+0xD4,u32(0)),(S+0x58,u64(S+0x18))):
        f=Fixture(lib,fn,8,3,1);f.put(address,blob);execute(f,'reject')
    # Lossy routing or omitted live-out restoration must fail this real caller test.
    mutation_controls=[]
    for label in ('old_inline','missing_rdi_restore'):
        f=Fixture(lib,fn,8,3,1)
        if label=='old_inline':f.put(f.patch['target'],f.patch['expected'])
        else:f.put(f.patch['target']+f.patch['call_offset']+5,b'\x90\x90')
        try:f.execute_owner()
        except (ValueError,tr.core.unicorn.UcError) as ex:
            if label=='old_inline':
                n.need(isinstance(ex,tr.core.unicorn.UcError) and ex.errno==tr.core.unicorn.UC_ERR_READ_UNMAPPED and
                       f.uc.reg_read(reg('rip'))==f.game+0x6660D5,'wrong old-inline failure')
            else:n.need(type(ex) is ValueError and str(ex)=='owner continuation live registers','wrong missing-restore failure')
            mutation_controls.append(label)
        else:raise ValueError('owner mutation escaped '+label)
    accepted=rejected=0
    pairs=[(G,tr.core.addresses(tr.KIND)['code_address']),(G+0x80000000,G+0x90600000)]
    pairs += [(v,G+0x10600000) for v in (0,1,(1<<47)-4096,1<<47)]
    pairs += [(G,v) for v in (0,1,1<<47,(1<<47)-16,G+0x100000000)]
    pairs += [(G,G+(a&~15)) for a in (0x576CF0,0x577B16,0x6689A0,0x23C6C38,0x33267B8,0x3483C34)]
    pairs += [(G,G+f['start']&~15) for f in n.profile()['functions'].values()]
    for game,promote in pairs:
        try:ref=owner.build(game,promote)
        except (ValueError,OverflowError,struct.error):ref=None
        out=Patch();c.memset(c.byref(out),0xA5,c.sizeof(out));rc=fn(game,promote,out)
        if ref is None:n.need(rc!=0 and not any(bytes(out)),'invalid owner placement accepted');rejected+=1
        else:n.need(rc==0 and bytes(out.replacement)==ref['replacement'],'owner placement differs');accepted+=1
    n.need(fn(G,G+0x10600000,None)!=0,'null owner output accepted')
    # Register the original owner frame plus the new leaf; unwind both levels.
    sample=Fixture(lib,fn,8,3,1);blob=bytearray(sample.owner_code)
    blob.extend(bytes(sample.promote_offset-len(blob)));blob.extend(sample.artifact['image'][:sample.artifact['code_bytes']]);code_bytes=len(blob)
    while len(blob)%4:blob.append(0)
    uw=len(blob);blob.extend(bytes.fromhex(r['owner']['fragment']['unwind_hex']));leaf=len(blob);blob.extend(bytes.fromhex('01000000'));table=len(blob)
    blob.extend(struct.pack('<6I',0,len(sample.owner_code),uw,sample.promote_offset,code_bytes,leaf))
    bad=bytearray(blob);bad[uw+6]=1 # Wrong XMM6 save offset; original is 2*16.
    rows=sorted(contexts);negative=bytearray(next(x for x in rows if struct.unpack_from('<I',x)[0]==r['window']['start']-r['owner']['start']))
    struct.pack_into('<I',negative,8,1)
    expected=struct.pack('<9Q',*(SEEDS[k] for k in NAMES),G+0x10500000)
    def variant(image,items):return struct.pack('<4I',len(image),code_bytes,table,len(items))+image+expected+b''.join(items)
    fixture=n.PROJECT/'build/component33-owner-unwind.bin';fixture.write_bytes(b'EPUWDV1\0'+struct.pack('<I',2)+variant(bad,[negative])+variant(blob,rows))
    exe=n.PROJECT/'build/native_component33_owner_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',n.PROJECT/'tests/native_component33_owner_unwind_test.c','-o',exe])
    windows=json.loads(run([exe,fixture]))
    paths=['native-component33-owner.lock.json','tools/native_component33_owner.py','tools/validate_component33_owner.py',
        'native-component33.lock.json','tools/native_component33_image.py','tools/native_component33_library.py','tools/validate_component33_images.py',
        'tools/validate_component33_transition.py','tools/validate_component33_direct.py','mod/src/ep_component33_image.h',
        'mod/src/ep_component33_image.cpp','mod/src/ep_component33_templates.h','mod/src/ep_component33_owner_template.h',
        'tests/component33_image_dll.cpp','tests/native_component33_owner_unwind_test.c','tests/native_producer_unwind_test.c']
    return dict(schema='hellforge_component33_owner_inline_validation_v1',passed=True,functional_runs=len(runs),runs=runs,
        mutation_controls=mutation_controls,accepted_placements=accepted,rejected_placements=rejected,windows=windows,
        windows_unwind_contexts=windows['windows_unwind_contexts'],original_identity_loss_reproduced=True,
        owner_inline_patch_emitted=True,selected_owner_path_emulated=True,whole_owner_emulated=False,
        original_owner_unwind_retained=True,leaf_to_owner_unwind_verified=True,next_component_original_code_executed=True,
        source_sha256={p:n.sha((n.PROJECT/p).read_bytes()) for p in paths},
        artifacts={p.name:dict(bytes=p.stat().st_size,sha256=n.sha(p.read_bytes())) for p in (lib.path,exe,fixture)},
        game_access=False,native_execution_of_game_bodies=False,production_owner_bound=False,installed=False,runtime_verified=False,multiplayer_verified=False,
        limits=['Original owner prologue/window/next-component/epilogue only; unrelated owner updates omitted.',
            'Original no-pending D>=T bypass retained; not a complete owner admission guard.',
            'Next component remains fixed-four original code and is only tested empty or P=D pending states.',
            'Exact owner instance, prefix flags, lifetimes, remaining readers/writers, whole-call exclusion and coordinated publication remain pending.'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--zig',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=validate(Library(a.library),a.zig);a.out.write_bytes((json.dumps(r,indent=2)+'\n').encode())
    print(json.dumps({k:r[k] for k in ('passed','functional_runs','windows_unwind_contexts','accepted_placements','rejected_placements','game_access')}))
