"""Execute fixed original/candidate insertions and real map/move helpers offline."""
from __future__ import annotations
import hashlib,importlib.util,json,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RESEARCH=ROOT.parent/'five_player_feasibility_20260927'
sys.path.insert(0,str(ROOT/'.native-test-deps'))
import capstone,unicorn
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_REG_RBX,X86_REG_R11,X86_REG_RIP
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn import x86_const as xr
sha=lambda b:hashlib.sha256(b).hexdigest()
u32=lambda n:struct.pack('<I',n)
u64=lambda n:struct.pack('<Q',n)
reg=lambda n:getattr(xr,'UC_X86_REG_'+n.upper())
GAME=0x7FF600000000
S,B,MAP,ENTITY,FLAGS=0x18200100400,0x18200800100,0x18200200100,0x18200300000,0x18200400000
STACK,RSP=0x182F0000000,0x182F0008008
NEW=ENTITY+0x800;NEW_ID=73
LAYOUT=[('pointer',0,0xE8,8),('primary',0x40,0x108,0x70),('aux',0x3C0,0x2C8,0x38),('property',0x580,0x3A8,0x20)]
SEEDS={n:0xABCDEF0100000000+i for i,n in enumerate(('rbx','rbp','rsi','rdi','r12','r13','r14','r15'))}
EVIDENCE=RESEARCH/'roster_insert_native_evidence.json'
EVIDENCE_SHA='794c357a56b2aa28cfd1061374afe27c1a3a2c06d31ce4ca736e4b783e41b497'
KINDS={'dense_legacy':(0x60CA80,0x60CB9F),'append_legacy':(0x60CBA0,0x60CC6B),
       'append_registered':(0x540850,0x54091E),'dense_registered':(0x540920,0x540A3E)}
RUNS=[]
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
native=load('insert_under_test',ROOT/'Native/roster_insert.py')
raw=EVIDENCE.read_bytes();assert sha(raw)==EVIDENCE_SHA
ev=json.loads(raw)
def reconstruct(rows,entry,end):
    parts=[];cursor=entry
    for row in rows:
        b=bytes.fromhex(row['bytes']);assert int(row['rva'],16)==cursor and sha(b)==row['sha256']
        parts.append(b);cursor+=len(b)
    assert cursor==end;return b''.join(parts)
SOURCES={k:reconstruct(ev['inserts'][hex(a)]['instructions'],a,z)for k,(a,z)in KINDS.items()}
MAP_BODY=reconstruct(ev['map_helper']['instructions'],0x172F790,0x172F7FE)
assert sha(MAP_BODY)=='57814b81c7a60e8d4ea989757b9a7d6d3dc3cfd9a81bc315794ca37b8885b375'
mev=json.loads((RESEARCH/'roster_move_native_evidence.json').read_bytes())
MOVE_BODY=reconstruct(mev['move']['instructions'],0x60C410,0x60C5BE)
def params(kind,game=GAME):
    i=list(KINDS).index(kind)
    return dict(kind=kind,game_base=game,code_address=game+0x10060000+i*0x10000,
                reject_address=game+0x10068000+i*0x10000,roster_address=S,storage_address=B,move_code_address=game+0x10040000)
def decode(blob,base):
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);md.detail=True
    rows=list(md.disasm(blob,base));assert sum(i.size for i in rows)==len(blob);return rows
def expected_pages(before,changes):
    after={p:bytearray(b)for p,b in before.items()}
    for a,blob in changes:
        for i,v in enumerate(blob):after[(a+i)&~0xFFF][(a+i)&0xFFF]=v
    return {p:bytes(b)for p,b in after.items()}


class Fixture:
    def __init__(self,kind,t=7,d=7,p=3,flag=1,*,original=False,game=GAME,actual_s=S,roster_mapped=True,changes=None):
        self.kind,self.t,self.d,self.p,self.flag=kind,t,d,p,flag
        self.original,self.game=original,game
        self.uc=Uc(UC_ARCH_X86,UC_MODE_64);self.pages=set();self.writes=[];self.reads=[];self.trace=[];self.calls=[]
        args=params(kind,game);args.update(changes or {})
        self.a=native.build(SOURCES[kind],**args)
        self.start=game+KINDS[kind][0]if original else self.a['entry_address']
        self.reject=self.a['reject_address'];self.move_reject=game+0x10048000;self.stop=game+0x100F0000
        code=SOURCES[kind]if original else bytes.fromhex(self.a['code_hex'])
        self.map(self.start,len(code));self.write(self.start,code)
        for a in (self.reject,self.move_reject,self.stop):self.map(a,1);self.write(a,b'\xcc')
        self.map(game+0x172F790,len(MAP_BODY));self.write(game+0x172F790,MAP_BODY)
        ma=native.move.build(MOVE_BODY,game_base=game,code_address=game+0x10040000,roster_address=S,
                             storage_address=B,reject_address=self.move_reject)
        self.move_entry=game+0x60C410 if original else ma['entry_address']
        mc=MOVE_BODY if original else bytes.fromhex(ma['code_hex'])
        self.map(self.move_entry,len(mc));self.write(self.move_entry,mc)
        self.map(game+0x3326468,8);self.write(game+0x3326468,u64(actual_s))
        self.map(STACK,0x10000);self.write(RSP,u64(self.stop))
        self.records={};self.table=[(0,0xFFFFFFFF)]*8
        if roster_mapped:
            for a,n in ((S-0x80,0x600),(B-0x80,0x780),(MAP,0x100),(ENTITY,0x1000),(FLAGS,1)):self.map(a,n)
            self.write(S+0x80,u32(t));self.write(S+0x84,u32(d));self.write(S+0x88,u32(p));self.write(S+0x7C,u32(2))
            self.write(S+0xD0,u64(MAP));self.write(S+0xD8,u32(8));self.write(S+0xDC,u32(0));self.write(S+0xE0,u32(1))
            self.write(FLAGS,bytes([flag]));self.write(NEW+8,u32(NEW_ID))
            slots=4 if original else 8
            for i in range(slots):
                entity=ENTITY+i*0x40;self.write(entity+8,u32(1+i*8))
                if i<min(t,slots):self.table[(1+i)&7]=(1+i*8,i)
                for k,(name,off,old,stride)in enumerate(LAYOUT):
                    blob=u64(entity)if name=='pointer'else bytes((i*31+j*7+k*67)&255 for j in range(stride))
                    self.records[name,i]=blob;self.write(self.slot(name,i),blob)
            for i,(key,v)in enumerate(self.table):self.write(MAP+8*i,u32(key)+u32(v))
        self.seed()
        self.outcome=None;self.before=self.snapshot()
        self.uc.hook_add(UC_HOOK_CODE,self.on_code)
        self.uc.hook_add(UC_HOOK_MEM_READ,lambda uc,a,ad,n,v,data:self.reads.append((ad,n)))
        self.uc.hook_add(UC_HOOK_MEM_WRITE,lambda uc,a,ad,n,v,data:self.writes.append((ad,n)))
    def slot(self,name,i):
        _,off,old,stride=next(x for x in LAYOUT if x[0]==name)
        return (S+old if self.original else B+off)+i*stride
    def seed(self):
        for n,v in SEEDS.items():self.uc.reg_write(reg(n),v)
        for i in range(6,16):self.uc.reg_write(reg('xmm'+str(i)),(0x0102030405060708+i)*(1+(1<<64)))
        legacy=self.kind.endswith('legacy');dense=self.kind.startswith('dense')
        values=dict(rsp=RSP,rax=0xABABABABABABABAB,r9=0x9191919191919191,
                    rcx=0xABCD if legacy else NEW,rdx=NEW if legacy else FLAGS,
                    r8=FLAGS if dense else 0x8181818181818181)
        for n,v in values.items():self.uc.reg_write(reg(n),v)
        self.argument_regs={n:self.uc.reg_read(reg(n))for n in ('rcx','rdx','r8','r9')}
    def map(self,a,n):
        for p in range(a&~0xFFF,(a+n+0xFFF)&~0xFFF,0x1000):
            if p not in self.pages:self.uc.mem_map(p,0x1000);self.uc.mem_write(p,b'\xa5'*0x1000);self.pages.add(p)
    def write(self,a,b):self.uc.mem_write(a,b)
    def read(self,a,n):return bytes(self.uc.mem_read(a,n))
    def snapshot(self):return {p:self.read(p,0x1000)for p in self.pages if not STACK<=p<STACK+0x10000}
    def on_code(self,uc,address,size,data):
        self.trace.append(address)
        if address in (self.stop,self.reject,self.move_reject):
            self.outcome='return'if address==self.stop else'reject';uc.emu_stop()
        if address in (self.move_entry,self.game+0x172F790):
            self.calls.append({'kind':'move'if address==self.move_entry else'map','t':struct.unpack('<I',self.read(S+0x80,4))[0],
                               'd':struct.unpack('<I',self.read(S+0x84,4))[0],'p':struct.unpack('<I',self.read(S+0x88,4))[0]})
    def run(self,name):
        self.uc.emu_start(self.start,0,count=10000)
        assert self.outcome is not None,'no bounded outcome'
        self.after=self.snapshot()
        RUNS.append(dict(name=name,kind=self.kind,original=self.original,t=self.t,d=self.d,p=self.p,flag=self.flag,
                         outcome=self.outcome,instructions=len(self.trace),helper_calls=self.calls))
        return self


class InsertTests(unittest.TestCase):
    def success(self,f):
        self.assertEqual(f.outcome,'return')
        dense=f.kind.startswith('dense');chosen=(f.p if f.flag else f.d)if dense else f.t
        changes=[];table=list(f.table)
        moving=dense and f.flag and f.p<f.d
        if moving:
            for name,off,old,stride in LAYOUT:changes.append((f.slot(name,f.d),f.records[name,f.p]))
            j=next(i for i,(key,val)in enumerate(table)if key==1+8*f.p);table[j]=(table[j][0],f.d)
        if not dense or f.flag:changes.append((f.slot('primary',chosen),bytes(0x70)))
        aux=bytearray(0x38);aux[0x14]=1
        changes.extend([(f.slot('aux',chosen),bytes(aux)),(f.slot('pointer',chosen),u64(NEW)),(S+0x80,u32(f.t+1))])
        if dense:
            changes.extend([(S+0x84,u32(f.d+1)),(S+0x7C,u32(max(2,f.d+1)))])
            if f.flag:changes.append((S+0x88,u32(f.p+1)))
        # Independent bounded linear-probe insertion, preserving keys except new key.
        bucket=next((1+i)&7 for i in range(8)if table[(1+i)&7][0]==0)
        table[bucket]=(NEW_ID,chosen)
        for i,(key,val)in enumerate(table):changes.append((MAP+8*i,u32(key)+u32(val)))
        self.assertEqual(f.after,expected_pages(f.before,changes))
        self.assertEqual(f.uc.reg_read(reg('rsp')),RSP+8)
        for n,v in SEEDS.items():self.assertEqual(f.uc.reg_read(reg(n)),v,n)
        for i in range(6,16):self.assertEqual(f.uc.reg_read(reg('xmm'+str(i))),(0x0102030405060708+i)*(1+(1<<64)))
        self.assertEqual([c['kind']for c in f.calls],(['move']if moving else[])+['map'])
        map_call=f.calls[-1]
        self.assertEqual(map_call['t'],f.t+int(dense))
        self.assertEqual(map_call['d'],f.d+int(dense))
        return chosen
    def rejected(self,f,reason):
        self.assertEqual(f.outcome,'reject');self.assertEqual(f.uc.reg_read(reg('r10')),reason)
        self.assertEqual(f.before,f.after);self.assertEqual(f.writes,[]);self.assertEqual(f.calls,[])
        self.assertEqual(f.uc.reg_read(reg('rsp')),RSP)
        for n,v in dict(SEEDS,**f.argument_regs).items():self.assertEqual(f.uc.reg_read(reg(n)),v,n)

    def test_01_full_source_and_all_instruction_relocations(self):
        self.assertEqual(native.load_sources(EVIDENCE),SOURCES)
        for kind,source in SOURCES.items():
            a=native.build(source,**params(kind));out=bytes.fromhex(a['code_hex'])
            rows={i.address:i for i in decode(out,a['entry_address'])}
            self.assertEqual(a['code_sha256'],sha(out));count=0
            for ins in decode(source,KINDS[kind][0]):
                ad=a['instruction_address_map'][hex(ins.address)];new=rows[ad]
                mems=[op.mem for op in ins.operands if op.type==X86_OP_MEM and X86_REG_RBX in (op.mem.base,op.mem.index)]
                m=next((m for m in mems if m.disp==0xE8 or 0x108<=m.disp<0x178 or 0x2C8<=m.disp<0x300),None)
                if m:
                    self.assertEqual(new.mnemonic,'movabs');self.assertEqual(new.operands[1].imm,B-0xE8)
                    patched=rows[ad+new.size];pm=next(op.mem for op in patched.operands if op.type==X86_OP_MEM)
                    self.assertEqual(patched.mnemonic,ins.mnemonic)
                    self.assertEqual(pm.base,X86_REG_R11 if m.base==X86_REG_RBX else m.base)
                    self.assertEqual(pm.index,X86_REG_R11 if m.index==X86_REG_RBX else m.index)
                    delta=0 if m.disp==0xE8 else 0x20 if m.disp<0x178 else 0x1E0
                    self.assertEqual(pm.disp,m.disp+delta);self.assertEqual(pm.scale,m.scale);count+=1
                elif ins.group(capstone.CS_GRP_JUMP)or ins.group(capstone.CS_GRP_CALL):
                    target=ins.operands[0].imm
                    dest=a['instruction_address_map'].get(hex(target),GAME+target)
                    if target==0x60C410:dest=GAME+0x10040000
                    self.assertEqual(new.mnemonic,ins.mnemonic);self.assertEqual(new.operands[0].imm,dest)
                elif any(op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP for op in ins.operands):
                    self.assertEqual(new.address+new.size+new.disp,GAME+0x3326468)
                elif ins.mnemonic=='cmp'and ins.op_str=='eax, 4':self.assertEqual(new.op_str,'eax, 8')
                else:self.assertEqual(bytes(new.bytes),bytes(ins.bytes))
            self.assertEqual(count,14)

    def test_02_all_supported_append_count_partitions(self):
        for kind in ('append_legacy','append_registered'):
            for original in (False,True):
                for t in range(4 if original else 8):
                    for d in range(t+1):
                        for p in range(d+1):
                            with self.subTest(kind=kind,original=original,t=t,d=d,p=p):
                                self.success(Fixture(kind,t,d,p,original=original).run('append_partition'))

    def test_03_all_supported_dense_prefix_and_flag_paths(self):
        for kind in ('dense_legacy','dense_registered'):
            for original in (False,True):
                for t in range(4 if original else 8):
                    for p in range(t+1):
                        for flag in (0,1):
                            with self.subTest(kind=kind,original=original,t=t,p=p,flag=flag):
                                self.success(Fixture(kind,t,t,p,flag,original=original).run('dense_prefix'))

    def test_04_nonzero_flag_and_second_aslr(self):
        for kind in KINDS:
            self.success(Fixture(kind,7,7,2,255,game=0x7FF800000000).run('second_aslr_nonzero_flag'))

    def test_05_guard_before_prologue_entity_or_array_access(self):
        for kind in KINDS:
            for t,d,p,reason in [(8,8,4,2),(0xFFFFFFFF,0,0,2),(7,8,1,3),(7,7,8,3)]:
                with self.subTest(kind=kind,t=t,d=d,p=p):self.rejected(Fixture(kind,t,d,p).run('invalid_count'),reason)
            f=Fixture(kind,actual_s=0x40000000,roster_mapped=False).run('unmapped_wrong_binding')
            self.rejected(f,1)
            self.assertEqual(f.reads,[(GAME+0x3326468,8)])
            if kind.startswith('dense'):self.rejected(Fixture(kind,7,6,3).run('pending_tail'),4)

    def test_06_source_addresses_and_cross_bundle_rejections(self):
        for kind in KINDS:
            for changes in [dict(storage_address=B+1),dict(code_address=GAME+KINDS[kind][0]),
                            dict(reject_address=B+0x500),dict(storage_address=S+0x100),
                            dict(move_code_address=params(kind)['code_address']),dict(game_base=GAME+1)]:
                args=params(kind);args.update(changes)
                with self.subTest(kind=kind,changes=changes),self.assertRaises(ValueError):native.build(SOURCES[kind],**args)
            with self.assertRaises(ValueError):native.build(bytes([SOURCES[kind][0]^1])+SOURCES[kind][1:],**params(kind))
        p=base_params();ps=native.base_bundle.pair.producer.load_source(RESEARCH/'roster_property_producer_native_evidence.json')
        rs=native.base_bundle.pair.receiver.load_source(RESEARCH/'roster_property_receive_evidence.json')
        a=native.build_bundle(SOURCES,MOVE_BODY,ps,rs,**p)
        for kind,b in a['inserts'].items():
            self.assertEqual(b['storage_address'],a['shared_binding']['storage_address'])
            self.assertEqual(b['move_code_address'],a['base_bundle']['move']['code_address'])
        for field,key,address in [('insert_code_addresses','dense_legacy',p['producer_code_address']),
                                  ('insert_reject_addresses','dense_registered',p['receiver_reject_address']),
                                  ('insert_code_addresses','append_registered',params('dense_legacy')['code_address'])]:
            bad=json.loads(json.dumps(p));bad[field][key]=address
            with self.assertRaises(ValueError):native.build_bundle(SOURCES,MOVE_BODY,ps,rs,**bad)

    def test_07_rejection_rel32_intersection_boundaries(self):
        for kind in ('append_registered','dense_registered'):
            a=native.build(SOURCES[kind],**params(kind));ins=decode(bytes.fromhex(a['code_hex']),a['code_address'])
            jumps=[i for i in ins if i.mnemonic=='jmp'and i.operands[0].imm==a['reject_address']]
            self.assertEqual(len(jumps),4)
            low=max(i.address+i.size-(1<<31)for i in jumps);high=min(i.address+i.size+(1<<31)-1 for i in jumps)
            for address in (low,high):self.rejected(Fixture(kind,8,8,4,changes={'reject_address':address}).run('reject_rel32_edge'),2)
            for address in (low-1,high+1):
                args=params(kind);args['reject_address']=address
                with self.assertRaises(ValueError):native.build(SOURCES[kind],**args)

    def test_08_eight_successive_appends_then_reject_ninth(self):
        for kind in ('append_legacy','append_registered'):
            f=Fixture(kind,0,0,0)
            for i in range(8):
                entity=NEW+i*0x20;entity_id=NEW_ID+8*i
                f.write(entity+8,u32(entity_id));f.seed();f.write(RSP,u64(f.stop))
                f.uc.reg_write(reg('rdx'if kind.endswith('legacy')else'rcx'),entity)
                f.before=f.snapshot();f.outcome=None;f.trace=[];f.calls=[];f.writes=[];f.t=i
                f.run('successive_append_'+str(i))
                aux=bytearray(0x38);aux[0x14]=1;bucket=(1+i)&7
                changes=[(f.slot('primary',i),bytes(0x70)),(f.slot('aux',i),bytes(aux)),
                         (f.slot('pointer',i),u64(entity)),(S+0x80,u32(i+1)),(MAP+8*bucket,u32(entity_id)+u32(i))]
                self.assertEqual(f.outcome,'return');self.assertEqual(f.after,expected_pages(f.before,changes))
                self.assertEqual(f.calls,[{'kind':'map','t':i,'d':0,'p':0}])
                for n,v in SEEDS.items():self.assertEqual(f.uc.reg_read(reg(n)),v)
                self.assertEqual(f.uc.reg_read(reg('rsp')),RSP+8)
            # The ninth attempt leaves all eight records/map entries intact.
            f.seed();f.write(RSP,u64(f.stop));f.before=f.snapshot();f.outcome=None;f.trace=[];f.calls=[];f.writes=[];f.t=8
            self.rejected(f.run('ninth_append_rejected'),2)

    def test_09_insert_then_property_producer_receiver(self):
        helper=load('producer_chain_fixture',ROOT/'tests/test_native_roster_producer.py')
        table=[(0,0xFFFFFFFF)]*8
        for i in range(7):table[(5+i)&7]=(101+8*i,i)
        f=helper.Fixture(ordinal=7,network=4,buckets=table)
        b=helper.PROPERTY-0x580;s=helper.ROSTER;f.map(b,0x680)
        f.write(s+0x80,u32(7));f.write(s+0x84,u32(7));f.write(s+0x88,u32(3))
        kind='append_registered';p=base_params();p['storage_address']=b
        artifact=native.build_bundle(SOURCES,MOVE_BODY,helper.BODY,helper.RECEIVER_BODY,**p)
        self.assertEqual(artifact['base_bundle']['property_pair']['producer'],f.artifact)
        a=artifact['inserts'][kind];f.map(a['code_address'],a['size_bytes']);f.write(a['code_address'],bytes.fromhex(a['code_hex']))
        f.map(a['reject_address'],1);f.write(a['reject_address'],b'\xcc');f.reject=a['reject_address']
        f.map(GAME+0x172F790,len(MAP_BODY));f.write(GAME+0x172F790,MAP_BODY)
        f.seed();f.write(helper.RSP,u64(f.stop))
        for n,v in dict(rsp=helper.RSP,rcx=helper.ENTITY).items():f.uc.reg_write(reg(n),v)
        before=f.snapshot();f.outcome=None
        f.run('chain_insert',a['entry_address']);RUNS.append(dict(helper.RUNS[-1],role='insert'))
        aux=bytearray(0x38);aux[0x14]=1
        self.assertEqual(f.outcome,'return')
        self.assertEqual(f.after,expected_pages(before,[(b+7*8,u64(helper.ENTITY)),(b+0x40+7*0x70,bytes(0x70)),
                         (b+0x3C0+7*0x38,bytes(aux)),(s+0x80,u32(8)),(helper.BUCKETS+4*8,u32(17)+u32(7))]))
        # Reuse the existing producer suite's fixed field/descriptor oracle.
        f.seed();f.write(helper.RSP,u64(f.stop));f.write(helper.RSP+0x28,u64(helper.COUNT));f.write(helper.RSP+0x30,u64(helper.ALLOC_BOX))
        for n,v in dict(rsp=helper.RSP,rcx=0xDEAD0000,rdx=helper.ENTITY,r8=0xBEEF0000,r9=helper.DESCRIPTORS).items():f.uc.reg_write(reg(n),v)
        f.reject=f.artifact['reject_address'];f.before=f.snapshot();f.outcome=None;f.trace=[];f.reads=[];f.writes=[]
        f.run('chain_producer');RUNS.append(dict(helper.RUNS[-1],role='producer'));helper.ProducerTests().success(f)
        wire=u32(0x12345678)+f.read(helper.PAYLOAD+4,28)
        f.map(helper.WIRE,0x100);f.map(helper.CURSOR,4);f.write(helper.WIRE+20,wire);f.write(helper.CURSOR,u32(20))
        a=artifact['base_bundle']['property_pair']['receiver'];f.map(a['code_address'],a['size_bytes']);f.write(a['code_address'],bytes.fromhex(a['code_hex']))
        f.map(a['reject_address'],1);f.write(a['reject_address'],b'\xcc');f.reject=a['reject_address']
        f.seed();f.write(helper.RSP,u64(f.stop))
        for n,v in dict(rsp=helper.RSP,rcx=s,rdx=17,r8=helper.WIRE,r9=helper.CURSOR).items():f.uc.reg_write(reg(n),v)
        before=f.snapshot();f.outcome=None;f.trace=[];f.alloc_calls=[];f.index_calls=[]
        f.run('chain_receiver',a['entry_address']);RUNS.append(dict(helper.RUNS[-1],role='receiver'))
        self.assertEqual(f.alloc_calls,[]);self.assertEqual(f.index_calls,[])
        self.assertEqual(f.outcome,'return');self.assertEqual(f.after,expected_pages(before,[(helper.PROPERTY+7*32,wire),(helper.CURSOR,u32(52))]))
        for n,v in helper.SEEDS.items():self.assertEqual(f.uc.reg_read(reg(n)),v)
        self.assertEqual(f.uc.reg_read(reg('rsp')),helper.RSP+8)


def base_params():
    return dict(game_base=GAME,roster_address=S,storage_address=B,move_code_address=GAME+0x10040000,
                producer_code_address=GAME+0x10000000,receiver_code_address=GAME+0x10020000,
                move_reject_address=GAME+0x10048000,producer_reject_address=GAME+0x10004000,receiver_reject_address=GAME+0x10024000,
                insert_code_addresses={k:params(k)['code_address']for k in KINDS},
                insert_reject_addresses={k:params(k)['reject_address']for k in KINDS})


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InsertTests))
    source_names=['roster_insert','roster_bundle','roster_property_pair','roster_producer','roster_receiver','roster_move']
    evidence_names=['roster_insert_native_evidence.json','roster_move_native_evidence.json','roster_property_producer_native_evidence.json','roster_property_receive_evidence.json','roster_component_binding_evidence_v3.json']
    report={'status':'passed'if result.wasSuccessful()else'failed','test_methods_run':result.testsRun,
            'failure_count':len(result.failures),'error_count':len(result.errors),
            'failures':[{'test':str(t),'traceback':s}for t,s in result.failures],
            'errors':[{'test':str(t),'traceback':s}for t,s in result.errors],
            'source_sha256':{f'Native/{n}.py':sha((ROOT/f'Native/{n}.py').read_bytes())for n in source_names},
            'test_sha256':sha(Path(__file__).read_bytes()),
            'test_dependency_sha256':{'tests/test_native_roster_producer.py':sha((ROOT/'tests/test_native_roster_producer.py').read_bytes())},
            'evidence_sha256':{str((RESEARCH/n).relative_to(ROOT.parent)):sha((RESEARCH/n).read_bytes())for n in evidence_names},
            'python_version':sys.version,'unicorn_version':unicorn.__version__,'capstone_version':capstone.__version__,
            'fixture_synthetic':True,'game_process_accessed':False,'host_native_code_executed':False,'installable':False,
            'emulator_runs':RUNS,'limits':['Valid map/new key/empty slot and actual caller lifetime/synchronization are assumed',
             'Dense candidates reject pending tails D<T; actual game caller contract remains unproven',
             'Producer/receiver chain uses allocator contract and synthetic incoming bytes, not real serializer or transport',
             'No entry hooks, Windows unwind, rejection handler, game or multiplayer validation']}
    out=ROOT/'verification/native_roster_insert_tests.json';out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'methods':result.testsRun,'executions':len(RUNS),'failures':len(result.failures),'errors':len(result.errors)}))
    raise SystemExit(0 if result.wasSuccessful()else 1)
