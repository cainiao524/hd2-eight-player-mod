"""Execute C++ component33 bytes only in Unicorn and unwind synthetic contexts."""
import argparse,ctypes as c,json,struct,subprocess
from collections import Counter
from pathlib import Path
import native_component33_image as n
from native_component33_library import Library,Addresses,Image
from generate_component33_templates import render,HEADER,REFERENCE
from build_unwind_offline import NAMES
import unicorn
from unicorn.x86_const import *
G=0x7FF600000000;S=0x18500100400;B=0x18500800100;E=0x18500300000;META=0x18500400000
STACK=0x185F0000000;RSP=STACK+0x8008;STOP=G+0x104F0000;REJECT=G+0x104E0000
CODES={k:G+0x10400000+i*0x10000 for i,k in enumerate(n.KINDS)}
SEEDS={k:0x1234000012340000+i*0x100000001 for i,k in enumerate(NAMES)}
LAYOUT={'pointer':(0,0x70,8),'byte':(0x40,0x90,1),'primary':(0x50,0x98,0x50),'secondary':(0x2D0,0x1D8,0x38)}
u32=lambda x:struct.pack('<I',x);u64=lambda x:struct.pack('<Q',x)
def reg(name):return globals()['UC_X86_REG_'+name.upper()]
def addresses(kind,game=G):return dict(game_base=game,code_address=game+CODES[kind]-G,component_address=S,storage_address=B,move_code_address=game+CODES['mover']-G,reject_address=game+REJECT-G)

class Fixture:
    def __init__(self,lib,kind,t,d,p,*,flag=1,destination=0,source=0,ordinal=0,original=False,game=G):
        self.kind,self.t,self.d,self.p,self.flag=kind,t,d,p,flag
        self.destination,self.source,self.ordinal=destination,source,ordinal
        self.original,self.game=original,game;self.uc=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_64)
        self.pages=set();self.outcome=None;self.writes=[];self.trace=[];self.contexts=set();self.helper_entries=[]
        self.stop=game+STOP-G;self.reject=game+REJECT-G
        self.artifact=lib.candidate(kind,**addresses(kind,game));self.start=game+n.profile()['functions'][kind]['start'] if original else addresses(kind,game)['code_address']
        for k in n.KINDS:
            original_code=n.profile()['functions'][k]
            self.put(game+original_code['start'],bytes.fromhex(original_code['body_hex']))
            if not original:self.put(addresses(k,game)['code_address'],lib.candidate(k,**addresses(k,game))['image'])
        for k in ('map_insert','map_delete'):
            f=n.profile()['functions'][k];self.put(game+f['start'],bytes.fromhex(f['body_hex']))
        for a in (self.stop,self.reject):self.put(a,b'\xcc')
        self.put(game+0x33267B8,u64(S))
        self.put(game+0x3483C34,u32(0xFFFFFFFF))
        self.put(S-0x80,b'\xa5'*0x400);self.put(B-0x80,b'\xb6'*(0x490+0x100))
        self.put(S+4,u32(2)+u32(t)+u32(d)+u32(p));self.put(S+0x14,bytes(64));self.put(S+0x58,u64(S+0x14)+u32(8)+u32(0)+u32(1))
        self.put(META,bytes([flag]));self.records={};self.keys=[1+8*i for i in range(8)]
        slots=4 if original else 8
        for i in range(9):self.put(E+0x40*i,bytes(8)+u32(73 if i==8 else self.keys[i])+bytes(8)+u32(int(i<p) if i<8 else flag))
        for i in range(slots):
            for j,(name,(_,_,stride)) in enumerate(LAYOUT.items()):
                blob=u64(E+0x40*i) if name=='pointer' else bytes((i*37+j*61+x*5)&255 for x in range(stride))
                self.records[name,i]=blob;self.put(self.slot(name,i),blob)
        self.table=[(0,0)]*8
        for i in range(t):
            bucket=next((self.keys[i]+j)&7 for j in range(8) if self.table[(self.keys[i]+j)&7][0]==0)
            self.table[bucket]=(self.keys[i],i)
        self.put(S+0x14,b''.join(u32(k)+u32(v) for k,v in self.table))
        self.put(STACK,bytes(0x10000));self.put(RSP,u64(self.stop))
        for name,value in SEEDS.items():self.uc.reg_write(reg(name),value)
        for i in range(6,16):self.uc.reg_write(reg('xmm'+str(i)),(0x1122334455667788+i)*(1+(1<<64)))
        for name,value in dict(rsp=RSP,rcx=S if kind=='mover' else E+0x40*ordinal if kind=='remove' else E+0x200,
                               rdx=destination if kind=='mover' else META,r8=source if kind=='mover' else 0x8181).items():self.uc.reg_write(reg(name),value)
        self.uc.hook_add(unicorn.UC_HOOK_CODE,self.on_code)
        self.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE,lambda uc,a,ad,size,v,d:self.writes.append((ad,size)))
    def put(self,address,blob):
        for page in range(address&~0xFFF,(address+len(blob)+0xFFF)&~0xFFF,0x1000):
            if page not in self.pages:self.uc.mem_map(page,0x1000);self.pages.add(page)
        self.uc.mem_write(address,blob)
    def read(self,address,size):return bytes(self.uc.mem_read(address,size))
    def int32(self,address):return struct.unpack('<I',self.read(address,4))[0]
    def slot(self,name,i):
        new,old,stride=LAYOUT[name];return (S+old if self.original else B+new)+i*stride
    def state(self):return {page:self.read(page,0x1000) for page in self.pages if not STACK<=page<STACK+0x10000}
    def on_code(self,uc,pc,size,data):
        self.trace.append(pc)
        if pc in (self.stop,self.reject):self.outcome='return' if pc==self.stop else 'reject';uc.emu_stop();return
        if pc==self.game+0x172F790:self.helper_entries.append('map_insert')
        if pc==self.game+0x172F8A0:self.helper_entries.append('map_delete')
        if not self.original and self.start<=pc<self.start+self.artifact['code_bytes']:
            stack=bytearray(self.read(RSP-128,256));struct.pack_into('<Q',stack,128,G+0x10500000)
            self.contexts.add(struct.pack('<IiI8Q',pc-self.start,uc.reg_read(reg('rsp'))-RSP,0,*(uc.reg_read(reg(k)) for k in NAMES))+stack)
    def execute(self,expected='return'):
        self.before=self.state()
        try:self.uc.emu_start(getattr(self,'entry',self.start),0,count=100000)
        except unicorn.UcError as ex:raise ValueError(f'{self.kind} {self.t,self.d,self.p,self.ordinal,self.destination,self.source} pc={self.uc.reg_read(reg("rip")):x}') from ex
        n.need(self.outcome==expected,'wrong outcome '+str((self.kind,self.t,self.d,self.p,self.ordinal,self.outcome)))
        if expected=='reject':
            n.need(self.before==self.state() and not self.writes and not self.helper_entries,'refusal changed state/stack')
            n.need(self.uc.reg_read(reg('rsp'))==RSP,'refusal stack')
        else:
            allowed=[(STACK,0x10000),(S+4,0x50)]+getattr(self,'extra_writable',[])
            allowed += [(self.slot(name,0),stride*(4 if self.original else 8)) for name,(_,_,stride) in LAYOUT.items()]
            for address,size in self.writes:n.need(any(a<=address and address+size<=a+length for a,length in allowed),'unexpected write '+hex(address))
            n.need(self.uc.reg_read(reg('rsp'))==RSP+8,'return stack')
            for name,value in SEEDS.items():n.need(self.uc.reg_read(reg(name))==value,'nonvolatile '+name)
            for i in range(6,16):n.need(self.uc.reg_read(reg('xmm'+str(i)))==(0x1122334455667788+i)*(1+(1<<64)),'nonvolatile XMM')
            self.check_model()
        return self
    def check_model(self):
        records=dict(self.records);values={k:v for k,v in self.table if k};t,d,p=self.t,self.d,self.p
        def move(dst,src):
            if dst==src:return
            for name in ('pointer','primary','secondary'):records[name,dst]=records[name,src]
            key=struct.unpack('<Q',records['pointer',src])[0];key=self.int32(key+8);values[key]=dst
        high_water=2
        if self.kind=='mover':move(self.destination,self.source)
        elif self.kind in ('append','dense'):
            chosen=t if self.kind=='append' else p if self.flag else d
            if self.kind=='dense':
                if not self.original and d<t:move(t,d)
                if self.flag and p<d:move(d,p)
                p+=int(bool(self.flag));d+=1;high_water=max(2,d)
            t+=1;values[self.int32(E+0x208)]=chosen;records['pointer',chosen]=u64(E+0x200);records['primary',chosen]=bytes(0x50)
        else:
            values.pop(self.keys[self.ordinal]);hole=self.ordinal
            if hole<d:
                if hole<p:
                    p-=1
                    if p:move(hole,p)
                    hole=p
                t-=1;d-=1
                if d:move(hole,d)
                if not self.original and d<t:move(d,t)
            else:
                t-=1
                if hole!=t:move(hole,t)
        n.need([self.int32(S+x) for x in (8,12,16)]==[t,d,p],'counts differ from segment model')
        n.need(self.int32(S+4)==high_water,'high-water count field')
        for (name,index),blob in records.items():n.need(self.read(self.slot(name,index),len(blob))==blob,'array differs '+str((self.kind,self.t,self.d,self.p,name,index)))
        actual={self.int32(S+0x14+8*i):self.int32(S+0x18+8*i) for i in range(8) if self.int32(S+0x14+8*i)}
        n.need(actual==values,'ID map differs')
        if not self.original and self.kind in ('dense','remove'):
            # Independent survivor/bijection oracle, separate from copy order.
            initial={struct.unpack('<Q',self.records['pointer',i])[0]:i for i in range(self.t)}
            active=[struct.unpack('<Q',self.read(self.slot('pointer',i),8))[0] for i in range(t)]
            removed=struct.unpack('<Q',self.records['pointer',self.ordinal])[0] if self.kind=='remove' else None
            expected=(set(initial)-{removed}) if removed is not None else set(initial)|{E+0x200}
            n.need(len(active)==len(set(active)) and set(active)==expected,'lost or duplicated active identity')
            for i,entity in enumerate(active):
                n.need(actual.get(self.int32(entity+8))==i,'map is not an active-row bijection')
                if entity in initial:
                    for name in ('primary','secondary'):
                        n.need(self.read(self.slot(name,i),LAYOUT[name][2])==self.records[name,initial[entity]],'survivor payload changed')
                if i<d:n.need((self.int32(entity+0x14)&1)==int(i<p),'prefix flags diverged')
        if not self.original:n.need(self.read(S+0x70,0x2B8-0x70)==b'\xa5'*(0x2B8-0x70),'old arrays modified')
        n.need(self.read(B-0x80,0x80)==b'\xb6'*0x80 and self.read(B+0x490,0x80)==b'\xb6'*0x80,'sidecar canary modified')

def run(command):
    p=subprocess.run([str(x) for x in command],capture_output=True)
    n.need(p.returncode==0,p.stdout.decode(errors='replace')+p.stderr.decode(errors='replace'));return p.stdout

def validate(lib,zig):
    header,facts=render();facts={k:facts[k] for k in n.KINDS};n.need(HEADER.read_bytes()==header,'template mismatch')
    contexts={k:set() for k in n.KINDS};runs=[]
    def execute(f,expected='return'):
        f.execute(expected);contexts[f.kind].update(f.contexts)
        runs.append(dict(kind=f.kind,t=f.t,d=f.d,p=f.p,ordinal=f.ordinal,source=f.source,destination=f.destination,
                         original=f.original,outcome=f.outcome,reason=f.uc.reg_read(reg('r10')) if f.outcome=='reject' else 0,instructions=len(f.trace)))
    for original in (True,False):
        cap=4 if original else 8
        for t in range(cap):
            for d in range(t+1):
                execute(Fixture(lib,'append',t,d,min(d,1),original=original))
            for d in ((t,) if original else range(t+1)):
                for p in range(d+1):
                    for flag in (0,1):execute(Fixture(lib,'dense',t,d,p,flag=flag,original=original))
        for src in range(cap):
            for dst in range(cap):execute(Fixture(lib,'mover',cap,cap,2,source=src,destination=dst,original=original))
        for t in range(1,cap+1):
            for d in range(t+1):
                for p in ((min(d,1),) if original and d<t else range(d+1)):
                    for ordinal in range(d if original and d<t else 0,t):execute(Fixture(lib,'remove',t,d,p,ordinal=ordinal,original=original))
    # Carry actual emulator data across removal and reinsert the same identity,
    # including eight colliding IDs in the full eight-bucket map.
    for ordinal in range(8):
        removed=Fixture(lib,'remove',8,0,0,ordinal=ordinal);execute(removed)
        rejoined=Fixture(lib,'append',7,0,0)
        rejoined.put(S,removed.read(S,0x400));rejoined.put(B,removed.read(B,0x490))
        rejoined.put(E+0x208,u32(1+8*ordinal))
        rejoined.records={(name,i):rejoined.read(rejoined.slot(name,i),stride) for name,(_,_,stride) in LAYOUT.items() for i in range(8)}
        rejoined.table=[(rejoined.int32(S+0x14+8*i),rejoined.int32(S+0x18+8*i)) for i in range(8)]
        execute(rejoined)
    legacy=Fixture(lib,'remove',4,2,1,ordinal=0,original=True);execute(legacy)
    n.need(any(legacy.int32(S+0x18+8*i)>=3 for i in range(8) if legacy.int32(S+0x14+8*i)),'legacy pending-tail hazard not reproduced')
    # Refusals and pointer/count/identity failures before the original prologue.
    for kind in ('append','dense'):
        execute(Fixture(lib,kind,8,8,4),'reject')
        execute(Fixture(lib,kind,3,2,1))
    execute(Fixture(lib,'remove',5,3,1,ordinal=1))
    for kind in ('dense','remove'):
        count=7 if kind=='dense' else 8
        for address,blob in ((B+(count-1)*8,u64(0)),(E+8,u32(0xFFFFFFFF)),(E+0x14,u32(0)),
                             (E+2*0x40+0x14,u32(1)),(S+0x18+7*8,u32(0))):
            f=Fixture(lib,kind,count,3,2,ordinal=1);f.put(address,blob);execute(f,'reject')
    for kind in n.KINDS:
        changes=[(G+0x33267B8,u64(S+8)),(S+8,u32(9)),(S+12,u32(5)),(S+16,u32(5)),
                 (S+0x58,u64(S+0x18)),(S+0x60,u32(16)),(S+0x64,u32(0xFFFFFFFF))]
        for address,blob in changes:
            f=Fixture(lib,kind,4,4,2,ordinal=1,source=1,destination=7);f.put(address,blob);execute(f,'reject')
    for kind in ('append','dense'):
        f=Fixture(lib,kind,4,4,2);f.put(E+0x208,u32(1));execute(f,'reject')
        f=Fixture(lib,kind,4,4,2);f.put(S+0x18+8,u32(0));f.put(S+0x14+8,u32(0));execute(f,'reject')
    f=Fixture(lib,'remove',4,4,2,ordinal=1);f.put(E+0x40+8,u32(999));execute(f,'reject')
    f=Fixture(lib,'mover',4,4,2,source=1,destination=8);execute(f,'reject')
    f=Fixture(lib,'mover',4,4,2,source=1,destination=7);f.put(S+0x18+2*8,u32(0));execute(f,'reject')
    for kind in n.KINDS:execute(Fixture(lib,kind,4,4,2,ordinal=1,source=1,destination=3,game=G+0x80000000))
    # Full C++ images at changed bindings and invalid domains must match exactly.
    accepted=rejected=0
    for kind in n.KINDS:
        cases=[REFERENCE]
        for name in REFERENCE:
            for value in (0,1,15,16,(1<<47)-16,1<<47,(1<<64)-1):cases.append({**REFERENCE,name:value})
        for name in ('component_address','storage_address'):
            cases.append({**REFERENCE,name:REFERENCE[name]+0x100000000})
        for name in ('component_address','storage_address','reject_address','move_code_address'):
            cases.append({**REFERENCE,name:REFERENCE['code_address']+16})
        for a in cases:
            try:expected=n.build(kind,**a)['image']
            except (ValueError,OverflowError,struct.error):expected=None
            out=Image();c.memset(c.byref(out),0xA5,c.sizeof(out));rc=lib.build(n.KINDS.index(kind)+1,Addresses(**a),out)
            if expected is None:n.need(rc!=0 and bytes(out)==bytes(c.sizeof(out)),'invalid C++ input accepted');rejected+=1
            else:n.need(rc==0 and bytes(out.data[:out.bytes])==expected,'C++ relocation mismatch');accepted+=1
    for kind in (0,len(n.ALL_KINDS)+1):
        out=Image();n.need(lib.build(kind,Addresses(**REFERENCE),out)==1 and not any(bytes(out)),'invalid kind')
    n.need(lib.build(1,None,Image())==1 and lib.build(1,Addresses(**REFERENCE),None)==1,'null API')
    exe=n.PROJECT/'build/native_component33_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',n.PROJECT/'tests/native_component33_unwind_test.c','-o',exe])
    windows={};artifacts=[lib.path,exe]
    for kind in n.KINDS:
        a=lib.candidate(kind,**addresses(kind));rows=sorted(contexts[kind]);bad=bytearray(a['image'])
        uw=a['unwind_offset']+4
        index={'mover':5,'append':7,'dense':11,'remove':7}[kind]
        bad[uw+index]=0x30 if kind in ('mover','dense') else 0x50
        negative=bytearray(next(row for row in rows if struct.unpack_from('<I',row)[0]>a['body_offset']+24 and struct.unpack_from('<i',row,4)[0]<0 and any(struct.unpack_from('<Q',row,12+8*j)[0]!=SEEDS[k] for j,k in enumerate(NAMES))))
        struct.pack_into('<I',negative,8,1)
        expected=struct.pack('<9Q',*(SEEDS[k] for k in NAMES),G+0x10500000)
        def variant(image,items):return struct.pack('<4I',len(image),a['code_bytes'],a['table_offset'],len(items))+image+expected+b''.join(items)
        fixture=n.PROJECT/'build'/('component33-'+kind+'-unwind.bin')
        fixture.write_bytes(b'EPUWDV1\0'+struct.pack('<I',2)+variant(bad,[negative])+variant(a['image'],rows))
        windows[kind]=json.loads(run([exe,fixture]));artifacts.append(fixture)
    paths=['native-component33.lock.json','tools/native_component33_image.py','tools/native_component33_library.py',
           'tools/generate_component33_templates.py','tools/validate_component33_images.py','mod/src/ep_component33_image.h',
           'mod/src/ep_component33_image.cpp','mod/src/ep_component33_templates.h','tests/component33_image_dll.cpp',
           'tests/native_component33_unwind_test.c','tests/native_producer_unwind_test.c']
    return dict(schema='hellforge_component33_core_validation_v1',passed=True,variants=facts,functional_runs=len(runs),same_identity_remove_reinsert_sequences=8,legacy_pending_tail_hazard_reproduced=True,
                run_types=dict(Counter(('original_' if r['original'] else 'candidate_')+r['kind']+'_'+r['outcome'] for r in runs)),
                accepted_placements=accepted,rejected_placements=rejected,windows=windows,
                windows_unwind_contexts=sum(x['windows_unwind_contexts'] for x in windows.values()),runs=runs,
                source_sha256={**{p:n.sha((n.PROJECT/p).read_bytes()) for p in paths},n.profile()['evidence_path']:n.profile()['evidence_sha256']},
                artifacts={p.name:dict(bytes=p.stat().st_size,sha256=n.sha(p.read_bytes())) for p in artifacts},
                game_access=False,native_execution_of_game_bodies=False,runtime_verified=False,multiplayer_verified=False,
                production_owner_bound=False,full_component33_lifecycle=False,creation_transaction_implemented=False,
                limits=['Four core images only: mover, append, dense insert, remove. No publish/prepare API or automatic binding.',
                        'Original header, inline eight-bucket map and aliases retained; all four arrays require a lifetime-owned B binding.',
                        'Byte rows are intentionally not moved; copied pointer/primary/secondary preserve original differences.',
                        'Dense insert/remove preserve pending survivors; all active map entries and dense prefix flags are checked before writes. Remaining consumers and lifecycle have separate gates.',
                        'Readable entities, coherent prefix flags and synchronized ownership remain caller obligations.'])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--zig',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=validate(Library(a.library),a.zig);a.out.write_bytes((json.dumps(r,indent=2)+'\n').encode())
    print(json.dumps({k:r[k] for k in ('passed','functional_runs','run_types','accepted_placements','rejected_placements','windows_unwind_contexts','game_access')}))
