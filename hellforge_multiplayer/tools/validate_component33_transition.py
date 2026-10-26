"""Lossless pending promotion: synthetic execution, saved-source controls, Windows unwind."""
import argparse,ctypes as c,json,struct
from collections import Counter
from pathlib import Path
import native_component33_image as n
import validate_component33_images as core
from validate_component33_direct import Fixture as DirectFixture
from native_component33_library import Library,Addresses,Image
from generate_component33_templates import render,HEADER,REFERENCE
from build_unwind_offline import NAMES
from validate_component33_images import G,S,B,E,RSP,STACK,SEEDS,LAYOUT,u32,u64,reg,run
KIND='promote_pending';core.CODES[KIND]=G+0x10600000

def adopt(f,previous):
    for address,size in ((S,0x2B8),(B,0x490),(E,0x240)):f.put(address,previous.read(address,size))
    f.records={(name,i):f.read(f.slot(name,i),stride) for name,(_,_,stride) in LAYOUT.items() for i in range(8)}
    f.table=[(f.int32(S+0x14+8*i),f.int32(S+0x18+8*i)) for i in range(8)]
    f.keys=[f.int32(struct.unpack('<Q',f.records['pointer',i])[0]+8) for i in range(f.t)]
    return f

class Fixture(core.Fixture):
    def __init__(self,lib,t,d,p,**kw):
        super().__init__(lib,'mover',t,d,p,**kw)
        self.kind=KIND;self.artifact=lib.candidate(KIND,**core.addresses(KIND,self.game))
        f=n.profile()['functions'][KIND]
        self.start=self.game+f['start'] if self.original else core.addresses(KIND,self.game)['code_address']
        self.put(self.start,bytes.fromhex(f['body_hex']) if self.original else self.artifact['image'])
        self.uc.reg_write(reg('rcx'),S)
        # The original function increments P for every pending entity without
        # setting its flag. The candidate's explicit caller contract checks it.
        for i in range(d,t):self.put(E+0x40*i+0x14,u32(1))
    def check_model(self):
        n.need([self.int32(S+x) for x in (4,8,12,16)]==[2,self.t,self.t,self.p+self.t-self.d],'transition counts')
        n.need(self.uc.reg_read(reg('rax'))==self.t,'transition return value')
        before=[struct.unpack('<Q',self.records['pointer',i])[0] for i in range(self.t)]
        after=[struct.unpack('<Q',self.read(self.slot('pointer',i),8))[0] for i in range(self.t)]
        self.identities_preserved=len(set(after))==len(after) and set(after)==set(before)
        if self.original and self.p<self.d<self.t:
            n.need(not self.identities_preserved,'original loss counterexample changed');return
        n.need(self.identities_preserved,'active identity lost or duplicated')
        # Independent partition oracle: original prefix unchanged; pending
        # identities become the next prefix in original order; dense survivors
        # remain in the suffix. No implementation copy sequence is replayed.
        end=self.p+self.t-self.d
        n.need(after[:self.p]==before[:self.p] and after[self.p:end]==before[self.d:],'pending promotion order')
        n.need(set(after[end:])==set(before[self.p:self.d]),'dense survivor set')
        previous={entity:i for i,entity in enumerate(before)}
        for i,entity in enumerate(after):
            for name in ('primary','secondary'):
                n.need(self.read(self.slot(name,i),LAYOUT[name][2])==self.records[name,previous[entity]],'survivor payload changed')
            n.need((self.int32(entity+0x14)&1)==int(i<end),'final prefix flags')
        for i in range(4 if self.original else 8):
            n.need(self.read(self.slot('byte',i),1)==self.records['byte',i],'byte ownership changed')
            if i>=self.t:
                for name,(_,_,stride) in LAYOUT.items():n.need(self.read(self.slot(name,i),stride)==self.records[name,i],'inactive row changed')
        actual=[(self.int32(S+0x14+8*i),self.int32(S+0x18+8*i)) for i in range(8)]
        expected={self.int32(entity+8):i for i,entity in enumerate(after)}
        n.need([k for k,v in actual]==[k for k,v in self.table],'map buckets rehashed')
        n.need({k:v for k,v in actual if k}==expected,'map is not an active-row bijection')
        if not self.original:
            n.need(not any(STACK<=a<STACK+0x10000 for a,size in self.writes),'leaf transition wrote stack')
            n.need(not self.helper_entries,'leaf transition called helper')
            n.need(self.read(S+0x70,0x248)==b'\xa5'*0x248,'old arrays modified')
        n.need(self.read(B-0x80,0x80)==b'\xb6'*0x80 and self.read(B+0x490,0x80)==b'\xb6'*0x80,'sidecar canary changed')

def validate(lib,zig):
    header,facts=render();n.need(HEADER.read_bytes()==header,'stale templates')
    contexts=set();runs=[];controls=[];artifacts=[lib.path]
    def execute(f,expected='return',case='matrix'):
        f.execute(expected)
        if f.kind==KIND:contexts.update(f.contexts)
        runs.append(dict(kind=f.kind,t=f.t,d=f.d,p=f.p,original=f.original,case=case,outcome=f.outcome,
                         identities_preserved=getattr(f,'identities_preserved',None),instructions=len(f.trace)))
        return f
    original_comparisons=0
    for t in range(5):
        for d in range(t+1):
            for p in range(d+1):
                old=execute(Fixture(lib,t,d,p,original=True),case='original')
                if old.identities_preserved:
                    new=execute(Fixture(lib,t,d,p),case='original_equivalence')
                    n.need(old.read(S,0x70)==new.read(S,0x70),'original-equivalent header changed')
                    for name,(_,_,stride) in LAYOUT.items():
                        for i in range(4):n.need(old.read(old.slot(name,i),stride)==new.read(new.slot(name,i),stride),'original-equivalent arrays changed')
                    original_comparisons+=1
    for game in (G,G+0x80000000):
        for t in range(9):
            for d in range(t+1):
                for p in range(d+1):
                    f=execute(Fixture(lib,t,d,p,game=game))
                    again=adopt(Fixture(lib,t,t,p+t-d,game=game),f)
                    execute(again,case='idempotent')
                    n.need(again.read(S,0x2B8)==f.read(S,0x2B8) and again.read(B,0x490)==f.read(B,0x490),'repeat changed state')
    # Coherent alternate hash placement, including a full colliding map.
    for t in (4,8):
        f=Fixture(lib,t,2,1);f.put(S+0x68,u32(7));f.table=[(0,0)]*8
        for i in range(t):f.table[(7+i)&7]=(f.keys[i],i)
        f.put(S+0x14,b''.join(u32(k)+u32(v) for k,v in f.table));execute(f,case='alternate_hash')
    invalid=[('global',G+0x33267B8,u64(S+8)),('capacity',S+8,u32(9)),('dense',S+12,u32(7)),
             ('prefix',S+16,u32(4)),('map_pointer',S+0x58,u64(S+0x18)),('map_capacity',S+0x60,u32(16)),
             ('empty_sentinel',S+0x64,u32(0xFFFFFFFF)),('null_pointer',B+8,u64(0)),
             ('duplicate_pointer',B+8,u64(E)),('invalid_id',E+0x48,u32(0xFFFFFFFF)),
             ('missing_id',E+0x48,u32(999)),('ordinal',S+0x18+16,u32(7)),('extra_id',S+0x14,u32(999)),
             ('prefix_flag',E+0x14,u32(0)),('dense_flag',E+0x54,u32(1)),('pending_flag',E+0xD4,u32(0)),
             ('hash',S+0x68,u32(2))]
    for case,address,blob in invalid:
        f=Fixture(lib,6,3,1);f.put(address,blob);execute(f,'reject',case)
    f=Fixture(lib,6,3,1);f.uc.reg_write(reg('rcx'),S+8);execute(f,'reject','argument')
    f=Fixture(lib,6,3,1);f.put(S+0x14,f.read(S+0x1C,8));f.put(S+0x1C,bytes(8));execute(f,'reject','broken_probe_chain')
    f=Fixture(lib,8,3,1);f.put(E+0x1C8,u32(999));execute(f,'reject','full_map_missing_id')
    # Every pending identity must have its caller-owned promotion flag set.
    for i in range(8):
        f=Fixture(lib,8,0,0);f.put(E+0x40*i+0x14,u32(0));execute(f,'reject','pending_flag_each_slot')
    # Actual carried bytes across append -> promotion -> remove new identity ->
    # same-ID dense rejoin. Caller setup sets pending flags before promotion.
    chains=0
    for d in range(1,7):
        for p in range(d+1):
            f=core.Fixture(lib,'append',7,d,p)
            for i in range(d,7):f.put(E+0x40*i+0x14,u32(1))
            execute(f,case='chain_append')
            promoted=execute(adopt(Fixture(lib,8,d,p),f),case='chain_promote')
            ordinal=p+7-d
            removed=adopt(DirectFixture(lib,'direct_remove',8,8,p+8-d,ordinal=ordinal),promoted)
            removed.uc.reg_write(reg('rdx'),E+0x200);removed.put(E+0x210,u32(0xDEADBEEF))
            execute(removed,case='chain_remove')
            counts=[removed.int32(S+x) for x in (8,12,16)]
            joined=adopt(DirectFixture(lib,'direct_dense',*counts,flag=1),removed)
            execute(joined,case='chain_same_id_rejoin');chains+=1
    # Deliberate payload, map and count regressions must fail independent oracles.
    for name,pattern,expected in [('payload','0f114100','survivor payload changed'),
                                  ('map','418954c218','map is not an active-row bijection'),
                                  ('count','4189420c','transition counts')]:
        f=Fixture(lib,8,3,1);blob=bytearray(f.artifact['image']);needle=bytes.fromhex(pattern)
        at=blob.index(needle,f.artifact['body_offset']);blob[at:at+len(needle)]=b'\x90'*len(needle);f.put(f.start,bytes(blob))
        try:f.execute()
        except ValueError as ex:n.need(str(ex)==expected,'wrong mutation failure '+str(ex))
        else:raise ValueError('mutation escaped '+name)
        controls.append(dict(name=name,rejected=True,reason=expected))
    accepted=rejected=0
    cases=[REFERENCE]
    for name in REFERENCE:
        for value in (0,1,15,16,(1<<47)-16,1<<47,(1<<64)-1):cases.append({**REFERENCE,name:value})
    for name in ('component_address','storage_address','reject_address','move_code_address'):
        cases.append({**REFERENCE,name:REFERENCE['code_address']+16})
    for f in n.profile()['functions'].values():cases.append({**REFERENCE,'reject_address':REFERENCE['game_base']+f['start']})
    for a in cases:
        try:expected=n.build(KIND,**a)['image']
        except (ValueError,OverflowError,struct.error):expected=None
        out=Image();c.memset(c.byref(out),0xA5,c.sizeof(out));rc=lib.build(n.ALL_KINDS.index(KIND)+1,Addresses(**a),out)
        if expected is None:n.need(rc!=0 and not any(bytes(out)),'invalid placement accepted');rejected+=1
        else:n.need(rc==0 and bytes(out.data[:out.bytes])==expected,'placement mismatch');accepted+=1
    a=lib.candidate(KIND,**core.addresses(KIND));rows=sorted(contexts)
    # Insert a fictitious 16-byte stack allocation before the table. The correct
    # leaf has no stack allocation; Windows must expose the regression.
    bad=a['image'][:a['unwind_offset']]+bytes.fromhex('0104010004120000')+a['image'][a['table_offset']:]
    negative=bytearray(next(row for row in rows if struct.unpack_from('<I',row)[0]==a['body_offset']))
    struct.pack_into('<I',negative,8,1)
    expected=struct.pack('<9Q',*(SEEDS[k] for k in NAMES),G+0x10500000)
    def variant(blob,table,items):return struct.pack('<4I',len(blob),a['code_bytes'],table,len(items))+blob+expected+b''.join(items)
    path=n.PROJECT/'build/component33-promote-pending-unwind.bin'
    path.write_bytes(b'EPUWDV1\0'+struct.pack('<I',2)+variant(bad,a['table_offset']+4,[negative])+variant(a['image'],a['table_offset'],rows))
    exe=n.PROJECT/'build/native_component33_transition_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',n.PROJECT/'tests/native_component33_initialize_unwind_test.c','-o',exe])
    windows=json.loads(run([exe,path]));artifacts.extend((exe,path))
    paths=['native-component33.lock.json','tools/native_component33_image.py','tools/native_component33_library.py',
           'tools/generate_component33_templates.py','tools/validate_component33_images.py','tools/validate_component33_direct.py',
           'tools/validate_component33_transition.py','mod/src/ep_component33_image.h','mod/src/ep_component33_image.cpp',
           'mod/src/ep_component33_templates.h','tests/component33_image_dll.cpp','tests/native_component33_initialize_unwind_test.c','tools/build_unwind_offline.py']
    return dict(schema='hellforge_component33_pending_transition_validation_v1',passed=True,functional_runs=len(runs),
                run_types=dict(Counter(('original_' if r['original'] else 'candidate_')+r['kind']+'_'+r['outcome'] for r in runs)),
                runs=runs,original_equivalent_states=original_comparisons,original_loss_states=sum(r['identities_preserved'] is False for r in runs),
                chained_append_promote_remove_rejoin_sequences=chains,mutation_controls=controls,
                variant=facts[KIND],windows=windows,windows_unwind_contexts=windows['windows_unwind_contexts'],
                accepted_placements=accepted,rejected_placements=rejected,
                source_sha256={p:n.sha((n.PROJECT/p).read_bytes()) for p in paths},
                artifacts={p.name:dict(bytes=p.stat().st_size,sha256=n.sha(p.read_bytes())) for p in artifacts},
                game_access=False,native_execution_of_game_bodies=False,runtime_verified=False,multiplayer_verified=False,
                production_owner_bound=False,owner_inline_migrated=False,full_component33_lifecycle=False,
                limits=['New allocation-free leaf algorithm; original loss states intentionally change behavior.',
                        'Caller sets pending prefix flags and owns readable/writable lifetimes and whole-call synchronization.',
                        'During promotion P can exceed old D until the final D=T; concurrent observation is forbidden.',
                        'Byte rows and external resource cleanup remain caller-owned; owner 576CF0 inline loop is not redirected.'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--zig',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=validate(Library(a.library),a.zig);a.out.write_bytes((json.dumps(r,indent=2)+'\n').encode())
    print(json.dumps({k:r[k] for k in ('passed','functional_runs','run_types','windows_unwind_contexts','original_equivalent_states','original_loss_states','chained_append_promote_remove_rejoin_sequences','accepted_placements','rejected_placements','game_access')}))
