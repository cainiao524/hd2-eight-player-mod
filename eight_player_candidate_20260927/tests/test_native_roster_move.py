"""Independent x64 execution and integration checks for all four roster arrays.

Original comparison uses its actual four-slot layout. Eight-slot cases use the
new disjoint layout and an independent byte-copy/map oracle, never an oversized
overlapping version of the original four arrays. No live process is accessed.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; RESEARCH=ROOT.parent/'five_player_feasibility_20260927'
sys.path.insert(0,str(ROOT/'.native-test-deps'))
import capstone
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_REG_RIP
import unicorn
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn import x86_const as xr

EVIDENCE=RESEARCH/'roster_move_native_evidence.json'
EVIDENCE_SHA='115802c09eb15f840932667717731150aa347e7ae8a72245dd92e05a5e86a242'
BODY_SHA='b977816b8863034f0c247d0ee58779ab0f7d87cdb54eaa49ebfcdd5cab95434b'
ENTRY,END=0x60C410,0x60C5BE
GAME=0x7FF600000000
ROSTER,STORAGE,BUCKETS,ENTITIES=0x18200100400,0x18200800100,0x18200200100,0x18200300000
STACK,RSP=0x182F0000000,0x182F0008008
SEEDS={'rax':0x1011121314151617,'rbx':0x2122232425262728,'rbp':0x3132333435363738,
       'rsi':0x4142434445464748,'rdi':0x5152535455565758,'r9':0x6162636465666768,
       'r10':0x7172737475767778,'r11':0x8182838485868788,'r12':0x9192939495969798,
       'r13':0xA1A2A3A4A5A6A7A8,'r14':0xB1B2B3B4B5B6B7B8,'r15':0xC1C2C3C4C5C6C7C8}
NONVOLATILE=('rbx','rbp','rsi','rdi','r12','r13','r14','r15')
LAYOUT=[('pointer',0,0xE8,8),('primary',0x40,0x108,0x70),
        ('auxiliary',0x3C0,0x2C8,0x38),('property',0x580,0x3A8,0x20)]
RUNS=[]
sha=lambda b:hashlib.sha256(b).hexdigest()
u32=lambda n:struct.pack('<I',n)
u64=lambda n:struct.pack('<Q',n)
reg=lambda n:getattr(xr,'UC_X86_REG_'+n.upper())


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


SOURCE_PATH=ROOT/'Native/roster_move.py'; SOURCE_BYTES=SOURCE_PATH.read_bytes()
native=load('move_under_test',SOURCE_PATH)
bundle=load('bundle_under_test',ROOT/'Native/roster_bundle.py')
raw=EVIDENCE.read_bytes(); assert sha(raw)==EVIDENCE_SHA
rows=json.loads(raw)['move']['instructions'];chunks=[];cursor=ENTRY
for row in rows:
    b=bytes.fromhex(row['bytes']);assert int(row['rva'],16)==cursor and sha(b)==row['sha256']
    chunks.append(b);cursor+=len(b)
BODY=b''.join(chunks);assert cursor==END and len(rows)==78 and sha(BODY)==BODY_SHA


def parameters(game=GAME):
    return dict(game_base=game,code_address=game+0x10040000,
                roster_address=ROSTER,storage_address=STORAGE,reject_address=game+0x10048000)


def emit(**changes):
    args=parameters();args.update(changes);return native.build(BODY,**args)


def decode(blob,base):
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);md.detail=True
    ins=list(md.disasm(blob,base));assert sum(i.size for i in ins)==len(blob);return ins


def target(ins):return next(op.imm for op in ins.operands if op.type==X86_OP_IMM)


def expected_pages(before,changes):
    out={p:bytearray(v)for p,v in before.items()}
    for a,blob in changes:
        for i,v in enumerate(blob):out[(a+i)&~0xFFF][(a+i)&0xFFF]=v
    return {p:bytes(v)for p,v in out.items()}


class Fixture:
    def __init__(self,src=7,dst=2,*,original=False,game=GAME,actual_roster=ROSTER,
                 high_bits=False,data_mapped=True,changes=None):
        self.src,self.dst,self.original=src,dst,original
        self.game,self.actual_roster=game,actual_roster
        args=parameters(game);args.update(changes or {})
        self.artifact=native.build(BODY,**args)
        self.start=game+ENTRY if original else self.artifact['entry_address']
        self.stop,self.reject=game+0x10050000,self.artifact['reject_address']
        self.uc=Uc(UC_ARCH_X86,UC_MODE_64);self.pages=set();self.reads=[];self.writes=[];self.trace=[];self.outcome=None
        code=BODY if original else bytes.fromhex(self.artifact['code_hex'])
        self.map(self.start,len(code));self.write(self.start,code)
        self.map(self.stop,1);self.write(self.stop,b'\xcc')
        self.map(self.reject,1);self.write(self.reject,b'\xcc')
        self.map(STACK,0x10000);self.write(RSP,u64(self.stop))
        self.records={};self.map_values={};slots=4 if original else 8
        if data_mapped:
            for a,n in [(ROSTER-0x80,0x600),(STORAGE-0x80,0x780),(BUCKETS,0x100),(ENTITIES,0x1000)]:self.map(a,n)
            self.write(ROSTER+0xD0,u64(BUCKETS));self.write(ROSTER+0xD8,u32(8))
            self.write(ROSTER+0xDC,u32(0));self.write(ROSTER+0xE0,u32(1))
            for off in (0x80,0x84,0x88):self.write(ROSTER+off,u32(slots))
            # Destination's previous map entry was removed by the enclosing
            # caller. The retained source bytes are intentionally not cleared.
            keys=[i for i in range(slots) if i!=dst or src==dst]
            table=[(0,0xFFFFFFFF)]*8
            for j,i in enumerate(keys):
                slot=(1+j)&7;table[slot]=(1+i*8,i);self.map_values[i]=BUCKETS+slot*8+4
            for j,(key,value)in enumerate(table):self.write(BUCKETS+j*8,u32(key)+u32(value))
            for i in range(slots):
                entity=ENTITIES+i*0x40;self.write(entity+8,u32(1+i*8))
                for k,(name,off,old,stride)in enumerate(LAYOUT):
                    value=u64(entity) if name=='pointer' else bytes((j*7+i*41+k*67)&255 for j in range(stride))
                    if name=='property':value=value[:12]+u32((7-i)&7)+value[16:]
                    address=(ROSTER+old if original else STORAGE+off)+i*stride
                    self.write(address,value);self.records[(name,i)]=value
        for n,v in SEEDS.items():self.uc.reg_write(reg(n),v)
        for i in range(16):self.uc.reg_write(reg('xmm'+str(i)),(0x0102030405060708+i)*(1+(1<<64)))
        self.uc.reg_write(reg('rsp'),RSP);self.uc.reg_write(reg('rcx'),actual_roster)
        self.uc.reg_write(reg('rdx'),dst|(0xABCD1234<<32 if high_bits else 0))
        self.uc.reg_write(reg('r8'),src|(0x789ABCDE<<32 if high_bits else 0))
        self.initial_regs={n:self.uc.reg_read(reg(n))for n in SEEDS}
        self.before=self.snapshot()
        self.uc.hook_add(UC_HOOK_CODE,self.on_code)
        self.uc.hook_add(UC_HOOK_MEM_READ,lambda uc,a,addr,n,v,d:self.reads.append((addr,n)))
        self.uc.hook_add(UC_HOOK_MEM_WRITE,lambda uc,a,addr,n,v,d:self.writes.append((addr,n,v)))

    def map(self,a,n):
        for p in range(a&~0xFFF,(a+n+0xFFF)&~0xFFF,0x1000):
            if p not in self.pages:
                self.uc.mem_map(p,0x1000);self.uc.mem_write(p,b'\xA5'*0x1000);self.pages.add(p)
    def read(self,a,n):return bytes(self.uc.mem_read(a,n))
    def write(self,a,b):self.uc.mem_write(a,b)
    def snapshot(self):return {p:self.read(p,0x1000)for p in self.pages if not STACK<=p<STACK+0x10000}
    def on_code(self,uc,address,size,data):
        self.trace.append(address)
        if address in (self.stop,self.reject):
            self.outcome='return' if address==self.stop else 'reject';uc.emu_stop()
    def run(self,name):
        self.uc.emu_start(self.start,0,count=3000)
        assert self.outcome in ('return','reject'),'no bounded outcome'
        self.after=self.snapshot()
        RUNS.append(dict(name=name,original=self.original,source_ordinal=self.src,destination_ordinal=self.dst,
                         outcome=self.outcome,instructions=len(self.trace),game_base=hex(self.game)))
        return self


class MoveTests(unittest.TestCase):
    def success(self,f):
        self.assertEqual(f.outcome,'return')
        for n in NONVOLATILE:self.assertEqual(f.uc.reg_read(reg(n)),SEEDS[n],n)
        for i in range(6,16):self.assertEqual(f.uc.reg_read(reg('xmm'+str(i))),(0x0102030405060708+i)*(1+(1<<64)))
        self.assertEqual(f.uc.reg_read(reg('rsp')),RSP+8)
        changes=[];writes=[]
        if f.src!=f.dst:
            for name,off,old,stride in LAYOUT:
                a=(ROSTER+old if f.original else STORAGE+off)+f.dst*stride
                changes.append((a,f.records[(name,f.src)]))
                chunks=([8] if name=='pointer' else [16]*7 if name=='primary' else [16,16,16,8] if name=='auxiliary' else [16,16])
                pos=0
                for n in chunks:writes.append((a+pos,n));pos+=n
            changes.append((f.map_values[f.src],u32(f.dst)));writes.append((f.map_values[f.src],4))
        self.assertEqual(f.after,expected_pages(f.before,changes))
        # Unicorn 2.1.4 reports a MOVUPS store as two adjacent 8-byte
        # hooks. Compare the exact ordered byte-address stream so hook
        # granularity cannot create a false mismatch. This still rejects
        # extra, missing, duplicated or reordered writes; whole-page values
        # above independently verify every resulting byte.
        observed=[(a,n)for a,n,v in f.writes if not STACK<=a<STACK+0x10000]
        self.assertEqual([a+i for a,n in observed for i in range(n)],
                         [a+i for a,n in writes for i in range(n)])
        if f.src==f.dst:
            self.assertEqual(f.writes,[])
            self.assertEqual(f.reads,[(RSP,8)])
            for n,v in f.initial_regs.items():self.assertEqual(f.uc.reg_read(reg(n)),v,n)
        return {n:f.uc.reg_read(reg(n))for n in SEEDS}

    def reject(self,f,reason):
        self.assertEqual(f.outcome,'reject');self.assertEqual(f.before,f.after)
        self.assertEqual(f.writes,[]);self.assertEqual(f.reads,[])
        self.assertEqual(f.uc.reg_read(reg('rsp')),RSP)
        self.assertEqual(f.uc.reg_read(reg('r10')),reason)
        self.assertEqual(f.uc.reg_read(reg('rcx')),f.actual_roster)
        for n in NONVOLATILE:self.assertEqual(f.uc.reg_read(reg(n)),SEEDS[n])

    def test_01_pinned_full_body_and_layout(self):
        self.assertEqual(native.load_source(EVIDENCE),BODY)
        original=decode(BODY,ENTRY);self.assertEqual(len(original),78)
        self.assertFalse(any(i.group(capstone.CS_GRP_CALL)for i in original))
        self.assertFalse(any(op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP for i in original for op in i.operands))
        a=emit();self.assertEqual(a['property_address'],STORAGE+0x580)
        self.assertEqual(a['source_sha256'],BODY_SHA);self.assertEqual(a['evidence_sha256'],EVIDENCE_SHA)
        for k in ('installable','game_execution','multiplayer_verified'):self.assertIs(a[k],False)
        self.assertEqual(sha(bytes.fromhex(a['code_hex'])),a['code_sha256'])

    def test_02_all_64_moves_and_original_four_slot_comparison(self):
        cached={}
        for src in range(8):
            for dst in range(8):
                with self.subTest(src=src,dst=dst):
                    f=Fixture(src,dst).run(f'candidate_{src}_to_{dst}')
                    cached[src,dst]=self.success(f)
        for src in range(4):
            for dst in range(4):
                with self.subTest(original=True,src=src,dst=dst):
                    f=Fixture(src,dst,original=True).run(f'original_{src}_to_{dst}')
                    old=self.success(f)
                    # Number of hash probes differs if the table contains four
                    # rather than eight entities; compare ABI-preserved state.
                    for n in NONVOLATILE:self.assertEqual(old[n],cached[src,dst][n])

    def test_03_high_bits_and_second_aslr(self):
        for src,dst in ((0,7),(7,0),(4,3),(3,4)):
            self.success(Fixture(src,dst,game=0x700000000000,high_bits=True).run(f'highbits_{src}_{dst}'))

    def test_04_equal_low_dword_noop_even_with_unmapped_roster(self):
        for value in (0,7,8,0xFFFFFFFF):
            f=Fixture(value,value,actual_roster=0x40000000,data_mapped=False,high_bits=True).run(f'equal_{value:x}')
            self.success(f)

    def test_05_unequal_reject_before_any_data_or_stack_write(self):
        for src,dst,actual,reason in [(0,8,ROSTER,1),(8,0,ROSTER,2),
                                      (0xFFFFFFFF,7,ROSTER,2),(7,0x80000000,ROSTER,1),
                                      (8,9,0x40000000,1),(7,2,0x40000000,3)]:
            f=Fixture(src,dst,actual_roster=actual,data_mapped=False).run(f'reject_{src:x}_{dst:x}_{reason}')
            self.reject(f,reason)

    def test_06_only_full_array_displacements_and_two_splices_change_body(self):
        a=emit();base=a['code_address'];code=bytes.fromhex(a['code_hex']);expected=bytearray(BODY)
        original=decode(BODY,ENTRY);clone={i.address-base:i for i in decode(code[:len(BODY)],base)}
        groups={'primary':0,'auxiliary':0,'property':0}
        for i in original:
            offset=i.address-ENTRY
            for op in i.operands:
                if op.type!=X86_OP_MEM:continue
                old=op.mem.disp
                name,delta=(('primary',0x20)if 0x108<=old<=0x168 else ('auxiliary',0x1E0)if 0x2C8<=old<=0x2F8 else ('property',0x2C0)if 0x3A8<=old<=0x3B8 else (None,0))
                if name:
                    self.assertEqual(i.disp_size,4);groups[name]+=1
                    expected[offset+i.disp_offset:offset+i.disp_offset+4]=struct.pack('<i',old+delta)
            if i.group(capstone.CS_GRP_JUMP):
                self.assertEqual(target(clone[offset])-base,target(i)-ENTRY)
        self.assertEqual(groups,dict(primary=14,auxiliary=8,property=4))
        for off,n in ((9,5),(0x13A,7)):
            self.assertEqual(clone[off].mnemonic,'jmp')
            self.assertGreaterEqual(target(clone[off]),base+len(BODY))
            expected[off:off+n]=code[off:off+n]
        self.assertEqual(code[:len(BODY)],expected)
        # Roster map operands remain unmodified after restoring the original S.
        for off in (0x147,0x158,0x15F):self.assertEqual(bytes(clone[off].bytes),bytes(next(i for i in original if i.address==ENTRY+off).bytes))

    def test_07_reject_rel32_intersection_edges(self):
        a=emit();base=a['code_address'];code=bytes.fromhex(a['code_hex'])
        # Padding INT3 bytes also decode; identify only jumps to reject.
        jumps=[i for i in decode(code,base)if i.mnemonic=='jmp' and target(i)==a['reject_address']]
        self.assertEqual(len(jumps),3)
        lo=max(i.address+i.size-(1<<31)for i in jumps);hi=min(i.address+i.size+(1<<31)-1 for i in jumps)
        for address in (lo,hi):
            for src,dst,actual,reason in ((0,8,ROSTER,1),(8,0,ROSTER,2),(7,2,0x40000000,3)):
                f=Fixture(src,dst,actual_roster=actual,data_mapped=False,changes={'reject_address':address}).run(f'rel32_{address:x}_{reason}')
                self.reject(f,reason)
        for address in (lo-1,hi+1):
            with self.assertRaises(ValueError):emit(reject_address=address)

    def test_08_source_address_and_whole_storage_rejections(self):
        for b in (BODY[:-1],bytearray(BODY),bytes([BODY[0]^1])+BODY[1:]):
            with self.assertRaises(ValueError):native.build(b,**parameters())
        for changes in [dict(storage_address=0),dict(storage_address=0xE0),dict(storage_address=STORAGE+1),
                        dict(roster_address=ROSTER+1),dict(game_base=GAME+1),dict(code_address=GAME+ENTRY),
                        dict(storage_address=ROSTER+0x400),dict(reject_address=STORAGE+0x600),
                        dict(storage_address=(1<<47)-0x100),dict(code_address=(1<<47)-16),dict(reject_address=True)]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):emit(**changes)

    def test_09_bundle_shared_layout_and_cross_component_ranges(self):
        ps=bundle.pair.producer.load_source(RESEARCH/'roster_property_producer_native_evidence.json')
        rs=bundle.pair.receiver.load_source(RESEARCH/'roster_property_receive_evidence.json')
        params=dict(game_base=GAME,roster_address=ROSTER,storage_address=STORAGE,
                    move_code_address=GAME+0x10040000,producer_code_address=GAME+0x10000000,
                    receiver_code_address=GAME+0x10020000,move_reject_address=GAME+0x10048000,
                    producer_reject_address=GAME+0x10004000,receiver_reject_address=GAME+0x10024000)
        a=bundle.build(BODY,ps,rs,**params)
        self.assertEqual(a['storage_size_bytes'],0x680)
        for role in ('producer','receiver'):
            self.assertEqual(a['property_pair'][role]['property_address'],a['move']['property_address'])
        self.assertEqual(a['move'],emit())
        for changes in [dict(move_code_address=params['producer_code_address']+16),
                        dict(move_reject_address=params['receiver_reject_address']),
                        dict(producer_reject_address=STORAGE+0x100),
                        dict(receiver_code_address=GAME+ENTRY),
                        dict(storage_address=GAME+0x347CEF0)]:
            bad=dict(params);bad.update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):bundle.build(BODY,ps,rs,**bad)

    def test_10_producer_move_receiver_use_updated_entity_map(self):
        helper=load('producer_test_fixture',ROOT/'tests/test_native_roster_producer.py')
        f=helper.Fixture(ordinal=7,network=4).run('chain_producer')
        RUNS.append(dict(helper.RUNS[-1],role='producer'))
        b=helper.PROPERTY-0x580;s=helper.ROSTER
        f.map(b,0x680)
        for i in range(8):
            f.write(b+i*8,u64(helper.ENTITY if i==7 else helper.ENTITY+0x100+i*16))
            f.write(b+0x40+i*0x70,bytes((i*31+j)&255 for j in range(0x70)))
            f.write(b+0x3C0+i*0x38,bytes((i*47+j)&255 for j in range(0x38)))
        artifact=bundle.build(BODY,helper.BODY,helper.RECEIVER_BODY,game_base=GAME,roster_address=s,storage_address=b,
                              producer_code_address=GAME+0x10000000,receiver_code_address=GAME+0x10020000,
                              move_code_address=GAME+0x10040000,producer_reject_address=GAME+0x10004000,
                              receiver_reject_address=GAME+0x10024000,move_reject_address=GAME+0x10048000)
        self.assertEqual(artifact['property_pair']['producer'],f.artifact)
        m=artifact['move'];f.map(m['code_address'],m['size_bytes']);f.write(m['code_address'],bytes.fromhex(m['code_hex']))
        f.map(m['reject_address'],1);f.write(m['reject_address'],b'\xcc');f.reject=m['reject_address']
        f.seed();f.write(helper.RSP,u64(f.stop))
        for n,v in dict(rsp=helper.RSP,rcx=s,rdx=2,r8=7).items():f.uc.reg_write(reg(n),v)
        changes=[]
        for name,off,old,stride in LAYOUT:changes.append((b+off+2*stride,f.read(b+off+7*stride,stride)))
        changes.append((helper.BUCKETS+1*8+4,u32(2)))
        before=f.snapshot();f.outcome=None;f.trace=[];f.alloc_calls=[];f.index_calls=[]
        f.run('chain_move',m['entry_address']);RUNS.append(dict(helper.RUNS[-1],role='move'))
        self.assertEqual(f.outcome,'return');self.assertEqual(f.after,expected_pages(before,changes))
        self.assertEqual(f.alloc_calls,[])
        # Simulated incoming property changes first field but keeps index4.
        wire=u32(0x12345678)+f.read(helper.PAYLOAD+4,28)
        f.map(helper.WIRE,0x100);f.map(helper.CURSOR,4)
        f.write(helper.WIRE+20,wire);f.write(helper.CURSOR,u32(20))
        r=artifact['property_pair']['receiver'];f.map(r['code_address'],r['size_bytes']);f.write(r['code_address'],bytes.fromhex(r['code_hex']))
        f.map(r['reject_address'],1);f.write(r['reject_address'],b'\xcc');f.reject=r['reject_address']
        f.seed();f.write(helper.RSP,u64(f.stop))
        for n,v in dict(rsp=helper.RSP,rcx=s,rdx=17,r8=helper.WIRE,r9=helper.CURSOR).items():f.uc.reg_write(reg(n),v)
        before=f.snapshot();f.outcome=None;f.trace=[]
        f.run('chain_receiver',r['entry_address']);RUNS.append(dict(helper.RUNS[-1],role='receiver'))
        self.assertEqual(f.outcome,'return')
        self.assertEqual(f.after,expected_pages(before,[(helper.PROPERTY+2*32,wire),(helper.CURSOR,u32(52))]))
        self.assertEqual(f.read(helper.PROPERTY+7*32,32),f.read(helper.PAYLOAD,32))
        self.assertEqual(f.read(helper.PROPERTY+2*32+12,4),u32(4))
        for n,v in helper.SEEDS.items():self.assertEqual(f.uc.reg_read(reg(n)),v)
        self.assertEqual(f.uc.reg_read(reg('rsp')),helper.RSP+8)

    def test_11_source_evidence_unchanged(self):
        self.assertEqual(SOURCE_PATH.read_bytes(),SOURCE_BYTES)
        self.assertEqual(sha(EVIDENCE.read_bytes()),EVIDENCE_SHA)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MoveTests))
    source_names=['roster_move','roster_bundle','roster_property_pair','roster_producer','roster_receiver']
    evs=['roster_move_native_evidence.json','roster_property_producer_native_evidence.json',
         'roster_property_receive_evidence.json','roster_component_binding_evidence_v3.json']
    value={'status':'passed'if result.wasSuccessful()else'failed','test_methods_run':result.testsRun,
           'failure_count':len(result.failures),'error_count':len(result.errors),
           'failures':[{'test':str(t),'traceback':s}for t,s in result.failures],
           'errors':[{'test':str(t),'traceback':s}for t,s in result.errors],
           'source_sha256':{f'Native/{n}.py':sha((ROOT/f'Native/{n}.py').read_bytes())for n in source_names},
           'test_sha256':sha(Path(__file__).read_bytes()),
           'test_dependency_sha256':{'tests/test_native_roster_producer.py':sha((ROOT/'tests/test_native_roster_producer.py').read_bytes())},
           'evidence_sha256':{str((RESEARCH/n).relative_to(ROOT.parent)):sha((RESEARCH/n).read_bytes())for n in evs},
           'original_body_sha256':BODY_SHA,'original_size_bytes':430,'original_instruction_count':78,
           'python_version':sys.version,'unicorn_version':unicorn.__version__,'capstone_version':capstone.__version__,
           'fixture_synthetic':True,'game_process_accessed':False,'host_native_code_executed':False,
           'game_or_multiplayer_verified':False,'installable':False,'emulator_runs':RUNS,
           'verified_scope':['All64 source/destination combinations for four disjoint eight-record arrays; original four-slot comparison only',
                             'Exact whole-page mutation oracle, original write order, source retained, counts/header preserved, moved entity map value updated',
                             'Low32 ordinal semantics, equal no-op with unmapped inputs, unequal guard before data access or prologue stack write',
                             'Nonvolatile GPR/XMM and stack restoration,26 displacements and two splices, original internal branches',
                             'Three reject-branch range intersection boundaries; whole-storage and bundle cross-code/reject/global collision checks',
                             'Actual producer -> full-array move -> receiver execution uses updated entity map and same property binding'],
           'limits':['Synthetic memory only; valid map/source entity and caller-provided destination slot are preconditions',
                     'Original map empty/miss behavior remains unsafe for invalid inputs and is not fixed by ordinal/binding guards',
                     'Mover does not remove old map entries, clear source records, change counts or implement full compaction/removal',
                     'Bridge reuses successful allocator contract and manually supplies incoming payload; no real serializer/transport',
                     'No sidecar allocation, opaque-state migration, initialization/publication or lifetime/synchronization proof',
                     'No Windows unwind, reject continuation implementation, hook installation or multiplayer verification']}
    out=ROOT/'verification/native_roster_move_tests.json';out.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':value['status'],'test_methods_run':result.testsRun,'emulator_executions':len(RUNS),'report':str(out)}))
    raise SystemExit(0 if result.wasSuccessful()else 1)
