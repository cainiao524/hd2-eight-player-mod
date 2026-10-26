"""Saved direct entry bodies and batch resets in synthetic Unicorn memory only."""
import argparse,ctypes as c,json,struct
from collections import Counter
from pathlib import Path
import native_component33_image as n
import validate_component33_images as core
from native_component33_library import Library,Addresses,Image
from generate_component33_templates import render,HEADER,REFERENCE
from build_unwind_offline import NAMES
from validate_component33_images import G,S,B,E,META,RSP,SEEDS,LAYOUT,u32,u64,reg,run
KINDS=tuple(n.DIRECT_KINDS)+n.BATCH_KINDS
core.CODES.update({k:G+0x10510000+i*0x10000 for i,k in enumerate(KINDS)})

class Fixture(core.Fixture):
    def __init__(self,lib,kind,t,d,p,**kw):
        super().__init__(lib,n.DIRECT_KINDS.get(kind,'mover'),t,d,p,**kw)
        self.kind=kind;self.artifact=lib.candidate(kind,**core.addresses(kind,self.game))
        f=n.profile()['functions'][kind]
        self.start=self.game+f['start'] if self.original else core.addresses(kind,self.game)['code_address']
        self.put(self.start,bytes.fromhex(f['body_hex']) if self.original else self.artifact['image'])
        self.put(self.game+0x3483C34,u32(0xFFFFFFFF))
        if kind in n.DIRECT_KINDS:
            self.uc.reg_write(reg('rdx'),E+0x40*self.ordinal if kind=='direct_remove' else E+0x200)
            self.uc.reg_write(reg('r8'),META)
            self.put(E+0x40*self.ordinal+0x10,u32(0xDEADBEEF))
        else:
            self.uc.reg_write(reg('rdx'),self.flag)
            self.extra_writable=[(S,2)]
    def check_model(self):
        if self.kind in n.DIRECT_KINDS:
            kind=self.kind;self.kind=n.DIRECT_KINDS[kind]
            super().check_model();self.kind=kind
            if kind=='direct_remove':n.need(self.uc.reg_read(reg('rax'))==0xDEADBEEF,'lost remove return value')
            return
        expected=dict(self.records)
        if self.kind=='reset_dense' or not self.flag:
            for i in range(self.d):
                old=expected['primary',i]
                expected['primary',i]=b'\xff'*44+old[44:48]+(bytes(32) if self.kind=='reset_control' else old[48:])
        for (name,i),blob in expected.items():n.need(self.read(self.slot(name,i),len(blob))==blob,'batch row differs '+str((name,i)))
        n.need([self.int32(S+x) for x in (4,8,12,16)]==[2,self.t,self.d,self.p],'batch changed counts')
        n.need(self.read(S+0x14,64)==b''.join(u32(k)+u32(v) for k,v in self.table),'batch changed map')
        prior=getattr(self,'prior_flags',b'\xa5\xa5')
        n.need(self.read(S,2)==(bytes([prior[0],self.flag]) if self.kind=='reset_control' else bytes([1,prior[1]])),'batch flag differs')
        if not self.original:n.need(self.read(S+0x70,0x248)==b'\xa5'*0x248,'batch wrote original arrays')
        n.need(self.read(B-0x80,0x80)==b'\xb6'*0x80 and self.read(B+0x490,0x80)==b'\xb6'*0x80,'batch changed canary')

def validate(lib,zig):
    header,facts=render();n.need(HEADER.read_bytes()==header,'stale templates')
    contexts={k:set() for k in KINDS};runs=[];artifacts=[lib.path]
    def execute(f,expected='return',case='matrix'):
        f.execute(expected);contexts[f.kind].update(f.contexts)
        runs.append(dict(kind=f.kind,t=f.t,d=f.d,p=f.p,flag=f.flag,ordinal=f.ordinal,original=f.original,
                         outcome=f.outcome,case=case,instructions=len(f.trace)))
    for original in (True,False):
        cap=4 if original else 8
        for t in range(cap):
            for d in range(t+1):execute(Fixture(lib,'direct_append',t,d,min(d,1),original=original))
            for p in range(t+1):
                for flag in (0,1):execute(Fixture(lib,'direct_dense',t,t,p,flag=flag,original=original))
        for t in range(1,cap+1):
            for p in range(t+1):
                for ordinal in range(t):execute(Fixture(lib,'direct_remove',t,t,p,ordinal=ordinal,original=original))
            for d in range(t):
                for ordinal in range(d,t):execute(Fixture(lib,'direct_remove',t,d,min(d,1),ordinal=ordinal,original=original))
        for kind in n.BATCH_KINDS:
            for t in range(cap+1):
                for d in range(t+1):
                    for flag in ((0,1,255) if kind=='reset_control' else (1,)):
                        execute(Fixture(lib,kind,t,d,min(d,1),flag=flag,original=original))
    for kind in KINDS:
        changes=[(G+0x33267B8,u64(S+8)),(S+8,u32(9)),(S+12,u32(5)),(S+16,u32(5)),
                 (S+0x58,u64(S+0x18)),(S+0x60,u32(16)),(S+0x64,u32(0xFFFFFFFF))]
        for address,blob in changes:
            f=Fixture(lib,kind,4,4,2,ordinal=1);f.put(address,blob);execute(f,'reject','invalid_header')
        execute(Fixture(lib,kind,4,4,2,ordinal=1,game=G+0x80000000),case='shifted_game')
    for kind in ('direct_dense','direct_append'):execute(Fixture(lib,kind,8,8,4),'reject','full')
    execute(Fixture(lib,'direct_dense',5,3,1),'reject','pending_dense')
    execute(Fixture(lib,'direct_remove',5,3,1,ordinal=1),'reject','pending_remove')
    for kind in n.BATCH_KINDS:
        for label,address,blob in [
            ('null_active',B+8,u64(0)),('invalid_id',E+0x48,u32(0xFFFFFFFF)),
            ('missing_id',E+0x48,u32(999)),('wrong_ordinal',S+0x18+16,u32(7)),
            ('extra_entry',S+0x14,u32(999)),('changed_hash',S+0x68,u32(2))]:
            f=Fixture(lib,kind,4,4,2,flag=0);f.put(address,blob);execute(f,'reject',label)
        # All occupied buckets look valid to a linear scan, but the original
        # lookup stops at the newly empty home bucket before reaching the ID.
        f=Fixture(lib,kind,4,4,2,flag=0);f.put(S+0x14,f.read(S+0x1C,8));f.put(S+0x1C,bytes(8))
        execute(f,'reject','broken_probe_chain')
        # A different coherent multiplier must retain the original hash semantics.
        f=Fixture(lib,kind,8,8,2,flag=0);f.put(S+0x68,u32(7))
        f.table=[(0,0)]*8
        for i in range(8):
            bucket=next((f.keys[i]*7+j)&7 for j in range(8) if not f.table[(f.keys[i]*7+j)&7][0])
            f.table[bucket]=(f.keys[i],i)
        f.put(S+0x14,b''.join(u32(k)+u32(v) for k,v in f.table));execute(f,case='alternate_hash')
    # Preserve actual bytes across remove -> both batch resets -> same-ID rejoin.
    # Removal changes pointer order and map ordinals, so reset must follow them.
    for ordinal in range(8):
        previous=Fixture(lib,'direct_remove',8,8,4,ordinal=ordinal)
        execute(previous,case='lifecycle_remove')
        for kind in (*n.BATCH_KINDS,'direct_dense'):
            t,d,p=(previous.int32(S+x) for x in (8,12,16))
            f=Fixture(lib,kind,t,d,p,flag=int(ordinal<4) if kind=='direct_dense' else 0)
            f.put(S,previous.read(S,0x2B8));f.put(B,previous.read(B,0x490));f.put(E,previous.read(E,0x240))
            # Normalize only flags owned by preceding reset; the model tracks the
            # unchanged byte as well as the byte this particular reset changes.
            f.prior_flags=f.read(S,2)
            f.records={(name,i):f.read(f.slot(name,i),stride) for name,(_,_,stride) in LAYOUT.items() for i in range(8)}
            f.table=[(f.int32(S+0x14+8*i),f.int32(S+0x18+8*i)) for i in range(8)]
            if kind=='direct_dense':f.put(E+0x208,u32(1+8*ordinal))
            execute(f,case='lifecycle_'+kind);previous=f
    # Replay the unported pending-repartition body, including its real mover,
    # to distinguish source behavior from a defect introduced by relocation.
    pending=[];source=n.profile()['functions']['pending_repartition_evidence']
    for t in range(5):
        for d in range(t+1):
            for p in range(d+1):
                f=Fixture(lib,'direct_append',t,d,p,original=True)
                f.start=G+source['start'];f.put(f.start,bytes.fromhex(source['body_hex']))
                f.uc.reg_write(reg('rcx'),S);f.uc.emu_start(f.start,0,count=100000)
                n.need(f.outcome=='return','pending source did not return')
                pointers=[struct.unpack('<Q',f.read(f.slot('pointer',i),8))[0] for i in range(t)]
                preserved=sorted(pointers)==[E+0x40*i for i in range(t)]
                n.need(preserved==(t==d or p==d),'pending hazard domain changed')
                n.need([f.int32(S+x) for x in (8,12,16)]==[t,t,p+t-d],'pending source counts')
                pending.append(dict(t=t,d=d,p=p,active_identities_preserved=preserved,
                                    distinct_pointers=len(set(pointers)),instructions=len(f.trace)))
    accepted=rejected=0
    for kind in KINDS:
        cases=[REFERENCE]
        for name in REFERENCE:
            for value in (0,1,15,16,(1<<47)-16,1<<47,(1<<64)-1):cases.append({**REFERENCE,name:value})
        for name in ('component_address','storage_address','reject_address','move_code_address'):
            cases.append({**REFERENCE,name:REFERENCE['code_address']+16})
        for f in n.profile()['functions'].values():
            cases.append({**REFERENCE,'reject_address':REFERENCE['game_base']+f['start']})
        for a in cases:
            try:expected=n.build(kind,**a)['image']
            except (ValueError,OverflowError,struct.error):expected=None
            out=Image();c.memset(c.byref(out),0xA5,c.sizeof(out));rc=lib.build(n.ALL_KINDS.index(kind)+1,Addresses(**a),out)
            if expected is None:n.need(rc!=0 and not any(bytes(out)),'invalid placement accepted');rejected+=1
            else:n.need(rc==0 and bytes(out.data[:out.bytes])==expected,'placement mismatch');accepted+=1
    exe=n.PROJECT/'build/native_component33_direct_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',n.PROJECT/'tests/native_component33_initialize_unwind_test.c','-o',exe]);artifacts.append(exe)
    windows={}
    for kind in KINDS:
        a=lib.candidate(kind,**core.addresses(kind));rows=sorted(contexts[kind]);bad=bytearray(a['image'])
        root_uw=struct.unpack_from('<I',a['image'],a['table_offset']+12+8)[0]
        index={'direct_dense':5,'direct_append':7,'direct_remove':5,'reset_control':5,'reset_dense':5}[kind]
        bad[root_uw+index]={'direct_dense':0x54,'direct_append':0x50,'direct_remove':0x54,'reset_control':0x12,'reset_dense':0x30}[kind]
        negative=bytearray(next(row for row in rows if struct.unpack_from('<I',row)[0]>a['body_offset']+24 and struct.unpack_from('<i',row,4)[0]<0))
        struct.pack_into('<I',negative,8,1)
        expected=struct.pack('<9Q',*(SEEDS[k] for k in NAMES),G+0x10500000)
        def variant(image,items):return struct.pack('<4I',len(image),a['code_bytes'],a['table_offset'],len(items))+image+expected+b''.join(items)
        path=n.PROJECT/'build'/('component33-'+kind+'-unwind.bin')
        path.write_bytes(b'EPUWDV1\0'+struct.pack('<I',2)+variant(bad,[negative])+variant(a['image'],rows))
        windows[kind]=json.loads(run([exe,path]));artifacts.append(path)
    paths=['native-component33.lock.json','tools/native_component33_image.py','tools/native_component33_library.py',
           'tools/generate_component33_templates.py','tools/validate_component33_images.py','tools/validate_component33_direct.py',
           'mod/src/ep_component33_image.h','mod/src/ep_component33_image.cpp','mod/src/ep_component33_templates.h',
           'tests/component33_image_dll.cpp','tests/native_component33_initialize_unwind_test.c','tools/build_unwind_offline.py']
    return dict(schema='hellforge_component33_direct_validation_v1',passed=True,functional_runs=len(runs),same_identity_lifecycle_sequences=8,
                run_types=dict(Counter(('original_' if r['original'] else 'candidate_')+r['kind']+'_'+r['outcome'] for r in runs)),
                variants={k:facts[k] for k in KINDS},windows=windows,windows_unwind_contexts=sum(x['windows_unwind_contexts'] for x in windows.values()),
                accepted_placements=accepted,rejected_placements=rejected,runs=runs,
                original_pending_repartition_runs=len(pending),pending_repartition_cases=pending,
                original_pending_identity_loss_cases=sum(not x['active_identities_preserved'] for x in pending),
                source_sha256={p:n.sha((n.PROJECT/p).read_bytes()) for p in paths},
                artifacts={p.name:dict(bytes=p.stat().st_size,sha256=n.sha(p.read_bytes())) for p in artifacts},
                game_access=False,native_execution_of_game_bodies=False,runtime_verified=False,multiplayer_verified=False,
                production_owner_bound=False,full_component33_lifecycle=False,
                limits=['Direct helpers and batch-reset images only; no owner/preparation/publication.',
                        'Dense insert/removal with pending tail remains refused; original pending repartition loses active identities when P<D<T in the tested four-slot domain.',
                        'Readability, synchronization and all other consumers remain caller obligations.'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--zig',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=validate(Library(a.library),a.zig);a.out.write_bytes((json.dumps(r,indent=2)+'\n').encode())
    print(json.dumps({k:r[k] for k in ('passed','functional_runs','run_types','windows_unwind_contexts','accepted_placements','rejected_placements','game_access')}))
