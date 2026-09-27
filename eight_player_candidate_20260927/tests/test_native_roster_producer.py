"""Execute saved producer and local-index leaf in synthetic x64 memory.

Only the allocator is represented by an explicit Win64 contract hook. The
producer, local-index helper and receiver bridge execute actual saved/emitted
instructions in Unicorn, never in a game or as host-native functions.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT.parent / 'five_player_feasibility_20260927'
sys.path.insert(0, str(ROOT / '.native-test-deps'))
import capstone
from capstone.x86_const import X86_OP_MEM, X86_OP_IMM, X86_REG_RIP
import unicorn
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as xr

EVIDENCE = RESEARCH / 'roster_property_producer_native_evidence.json'
EVIDENCE_SHA = 'f73ec903d06f2304f4f944c25e011a7ef86d78737cb1b197101a1c96daaabacb'
BINDING = RESEARCH / 'roster_component_binding_evidence_v3.json'
BINDING_SHA = '274833c418bfa7dec4e4097dda5031f3a11e8c69689ae4ed758e75a40481c2e2'
RECEIVER_EVIDENCE = RESEARCH / 'roster_property_receive_evidence.json'
RECEIVER_SHA = 'bad5661771df280dd5e982b765d2f4ab1c73de9ae7e86e974751af6c3c383c10'
BODY_SHA = '8b9a20e5207ae395e99e45f153cba1994ff50c10cb258101fd16a74285824c34'
LEAF_SHA = 'a87faad9809cfc17449641152c938f42b5063daf33cf506360d93d6e1eb976f9'
ENTRY, END, LEAF_ENTRY = 0x60C640, 0x60C882, 0x134F190
SENTINEL, GLOBAL, INDEX_GLOBAL, ALLOCATOR = 0x3483C20, 0x3326468, 0x347CEF0, 0x173B8D0
SPLICE, RESUME = 0x89, 0x8E
GAME = 0x7FF600000000
ROSTER, WRONG = 0x18200100400, 0x18200120400
BUCKETS, ENTITY = 0x18200200100, 0x18200210100
DESCRIPTORS, COUNT = 0x18200300100, 0x18200400100
PAYLOAD, PROPERTY = 0x18200500200, 0x18200800100
ALLOC_BOX, ALLOC_OBJECT = 0x18200900100, 0x18200910100
INDEX_OWNER, LOCAL_PEER = 0x18201000000, 0x18202000000
REMOTE, REMOTE_BUCKETS, REMOTE_PROPERTY = 0x18203000400, 0x18203100100, 0x18203200100
WIRE, CURSOR = 0x18203300100, 0x18203400100
STACK, RSP = 0x182F0000000, 0x182F0008008
SEEDS = {'rbx':0x1122334455667788, 'rbp':0x2233445566778899,
         'rsi':0x33445566778899AA, 'rdi':0x445566778899AABB,
         'r12':0x5566778899AABBCC, 'r13':0x66778899AABBCCDD,
         'r14':0x778899AABBCCDDEE, 'r15':0x8899AABBCCDDEEFF}
HASHES = [0x0F27C68E,0xCD889DBC,0x086C3722,0xB03B8BCE,
          0x7ED6949C,0xEBEE098F,0xBD74FB92,0x83C8F804]
RUNS = []


def sha(blob): return hashlib.sha256(blob).hexdigest()
def u32(v): return struct.pack('<I', v)
def u64(v): return struct.pack('<Q', v)
def reg(n): return getattr(xr, 'UC_X86_REG_' + n.upper())


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


SOURCE_PATH = ROOT / 'Native/roster_producer.py'
SOURCE_BYTES = SOURCE_PATH.read_bytes()
native = module('producer_under_test', SOURCE_PATH)
RECEIVER_PATH = ROOT / 'Native/roster_receiver.py'
RECEIVER_BYTES = RECEIVER_PATH.read_bytes()
receiver = module('receiver_bridge_under_test', RECEIVER_PATH)


def reconstruct(path, pin, field, entry, end, digest):
    raw = path.read_bytes()
    assert sha(raw) == pin, path
    rows = json.loads(raw)[field]['instructions']
    chunks, pos = [], entry
    for row in rows:
        blob = bytes.fromhex(row['bytes'])
        assert int(row['rva'],16) == pos and sha(blob) == row['sha256']
        chunks.append(blob)
        pos += len(blob)
    result = b''.join(chunks)
    assert pos == end and sha(result) == digest
    return result


BODY = reconstruct(EVIDENCE, EVIDENCE_SHA, 'producer', ENTRY, END, BODY_SHA)
LEAF = reconstruct(BINDING, BINDING_SHA, 'proven_leaf', LEAF_ENTRY, 0x134F1EC, LEAF_SHA)
RECEIVER_BODY = reconstruct(RECEIVER_EVIDENCE, RECEIVER_SHA, 'receiver',
                            0x60C890, 0x60C9BF,
                            '23d53b4f2f46ec26d23d79b958ee31d469910217ea843fb92bd98cf24c017411')


def parameters(game=GAME):
    return dict(game_base=game, code_address=game+0x10000000,
                roster_address=ROSTER, property_address=PROPERTY,
                reject_address=game+0x10004000)


def emit(**changes):
    args = parameters()
    args.update(changes)
    return native.build(BODY, **args)


def decode(blob, address):
    md = capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
    md.detail = True
    result = list(md.disasm(blob,address))
    assert sum(i.size for i in result) == len(blob)
    return result


def target(ins):
    return next(op.imm for op in ins.operands if op.type == X86_OP_IMM)


class Fixture:
    def __init__(self, *, original=False, ordinal=0, network=7, count=3,
                 game=GAME, entity=17, capacity=8, buckets=None,
                 actual_roster=ROSTER, index_mode='found', changes=None,
                 allocation_storage=True):
        self.original, self.ordinal, self.count = original, ordinal, count
        self.game, self.network, self.actual_roster = game, network, actual_roster
        self.entity = entity
        args = parameters(game)
        args.update(changes or {})
        self.artifact = native.build(BODY, **args)
        self.start = game+ENTRY if original else self.artifact['entry_address']
        self.stop, self.reject = game+0x10008000, self.artifact['reject_address']
        self.uc = Uc(UC_ARCH_X86,UC_MODE_64)
        self.pages, self.reads, self.writes, self.trace = set(), [], [], []
        self.alloc_calls, self.index_calls, self.outcome = [], [], None
        code = BODY if original else bytes.fromhex(self.artifact['code_hex'])
        for a,n in [(ROSTER-0x80,0x700),(WRONG-0x80,0x700),(BUCKETS,0x100),
                    (ENTITY,0x20),(DESCRIPTORS-0x80,0x400),(COUNT,4),
                    (PROPERTY-0x80,0x200),(ALLOC_BOX,8),(ALLOC_OBJECT,8),
                    (INDEX_OWNER,0x18000),(LOCAL_PEER+0xB398,8),(STACK,0x10000),
                    (game+SENTINEL,4),(game+GLOBAL,8),(game+INDEX_GLOBAL,8),
                    (game+ALLOCATOR,1),(game+LEAF_ENTRY,len(LEAF)),
                    (self.start,len(code)),(self.stop,1),(self.reject,1)]:
            self.map(a,n)
        if allocation_storage: self.map(PAYLOAD-0x80,0x100)
        self.uc.mem_write(self.start,code)
        self.uc.mem_write(game+LEAF_ENTRY,LEAF)
        for a in (self.stop,self.reject,game+ALLOCATOR): self.uc.mem_write(a,b'\xcc')
        self.write(game+SENTINEL,u32(0xFFFFFFFF))
        self.write(game+GLOBAL,u64(actual_roster))
        self.write(game+INDEX_GLOBAL,u64(INDEX_OWNER))
        self.write(ENTITY+8,u32(entity))
        self.write(COUNT,u32(count))
        self.write(ALLOC_BOX,u64(ALLOC_OBJECT))
        if buckets is None:
            buckets=[(0,0xFFFFFFFF)]*capacity
            if capacity: buckets[entity & (capacity-1)]=(entity,ordinal)
        assert len(buckets)==capacity
        self.setup_map(ROSTER,BUCKETS,capacity,buckets)
        self.setup_map(WRONG,BUCKETS,capacity,buckets)
        # Synthetic confirmed-peer storage supports helper execution only. It
        # does not establish the real client's capacity or connection behavior.
        self.write(INDEX_OWNER+0x162C8,u64(LOCAL_PEER))
        self.write(LOCAL_PEER+0xB398,u64(0x123456789ABCDEF0))
        self.write(INDEX_OWNER+0x16390,u32(0 if index_mode=='empty' else 8))
        for i in range(8):
            peer=0x123456789ABCDEF0 if i==5 and index_mode=='found' else 0x9000+i
            self.write(INDEX_OWNER+0x16398+i*32,u64(peer))
            self.write(INDEX_OWNER+0x163AC+i*32,u32(network))
        self.expected_network = network if index_mode=='found' else 0xFFFFFFFF
        self.write(RSP,u64(self.stop))
        self.write(RSP+0x28,u64(COUNT))
        self.write(RSP+0x30,u64(ALLOC_BOX))
        self.seed()
        # Entry RCX is deliberately not the roster: saved producer uses GLOBAL.
        for n,v in dict(rsp=RSP,rcx=0xDEAD0000,rdx=ENTITY,r8=0xBEEF0000,r9=DESCRIPTORS).items():
            self.uc.reg_write(reg(n),v)
        self.before = self.snapshot()
        self.uc.hook_add(UC_HOOK_CODE,self.on_code)
        self.uc.hook_add(UC_HOOK_MEM_READ,lambda uc,a,addr,n,v,d:self.reads.append((addr,n)))
        self.uc.hook_add(UC_HOOK_MEM_WRITE,lambda uc,a,addr,n,v,d:self.writes.append((addr,n,v)))

    def map(self,a,n):
        for p in range(a & ~0xFFF,(a+n+0xFFF)&~0xFFF,0x1000):
            if p not in self.pages:
                self.uc.mem_map(p,0x1000)
                self.uc.mem_write(p,b'\xA5'*0x1000)
                self.pages.add(p)

    def write(self,a,b): self.uc.mem_write(a,b)
    def read(self,a,n): return bytes(self.uc.mem_read(a,n))
    def seed(self):
        for n,v in SEEDS.items(): self.uc.reg_write(reg(n),v)
    def snapshot(self):
        return {p:self.read(p,0x1000) for p in self.pages if not STACK<=p<STACK+0x10000}
    def setup_map(self,s,b,cap,items):
        self.write(s+0xD0,u64(b))
        self.write(s+0xD8,u32(cap))
        self.write(s+0xDC,u32(0))
        self.write(s+0xE0,u32(1))
        for i,(key,value) in enumerate(items): self.write(b+i*8,u32(key)+u32(value))

    def on_code(self,uc,address,size,data):
        self.trace.append(address)
        if address in (self.stop,self.reject):
            self.outcome='return' if address==self.stop else 'reject'
            uc.emu_stop()
        elif address==self.game+ALLOCATOR:
            sp=uc.reg_read(reg('rsp'))
            args=tuple(uc.reg_read(reg(n)) for n in ('rcx','rdx','r8'))
            assert args==(ALLOC_OBJECT,32,4), args
            assert sp & 15 == 8
            self.alloc_calls.append({'arguments':list(args),'return_to':hex(struct.unpack('<Q',self.read(sp,8))[0])})
            return_to=struct.unpack('<Q',self.read(sp,8))[0]
            for k,n in enumerate(('rax','rcx','rdx','r8','r9','r10','r11')):
                uc.reg_write(reg(n),0xABC0000000000000+k)
            for k in range(6): uc.reg_write(reg('xmm'+str(k)),0xABCDEF+k)
            uc.reg_write(reg('rax'),PAYLOAD)
            uc.reg_write(reg('rsp'),sp+8)
            uc.reg_write(reg('rip'),return_to)
        elif address==self.game+LEAF_ENTRY:
            self.index_calls.append({'r11':uc.reg_read(reg('r11'))})

    def run(self,name,start=None):
        self.uc.emu_start(self.start if start is None else start,0,count=6000)
        assert self.outcome in ('return','reject'), 'no bounded outcome'
        self.after=self.snapshot()
        RUNS.append({'name':name,'original':self.original,'outcome':self.outcome,
                     'ordinal':self.ordinal,'network_dword':self.expected_network,
                     'game_base':hex(self.game),'instructions':len(self.trace),
                     'allocator_contract_calls':len(self.alloc_calls),
                     'actual_index_leaf_calls':len(self.index_calls)})
        return self


def expected_pages(before, changes):
    result={p:bytearray(b) for p,b in before.items()}
    for a,blob in changes:
        for i,byte in enumerate(blob): result[(a+i)&~0xFFF][(a+i)&0xFFF]=byte
    return {p:bytes(b) for p,b in result.items()}


class ProducerTests(unittest.TestCase):
    def success(self,f):
        self.assertEqual(f.outcome,'return')
        for n,v in SEEDS.items(): self.assertEqual(f.uc.reg_read(reg(n)),v,n)
        self.assertEqual(f.uc.reg_read(reg('rsp')),RSP+8)
        self.assertEqual(f.uc.reg_read(reg('rax')),2*(f.count+7))
        self.assertEqual(len(f.alloc_calls),1)
        self.assertEqual(f.index_calls,[{'r11':f.ordinal}])
        record=struct.pack('<8I',0x7FFF,0,0,f.expected_network,0,0,0,0)
        descriptors=b''.join(struct.pack('<IIQ',h,1 if i<4 else 2,PAYLOAD+i*4) for i,h in enumerate(HASHES))
        destination=(f.actual_roster+0x3A8 if f.original else PROPERTY)+f.ordinal*32
        self.assertEqual(f.after,expected_pages(f.before,[(destination,record),(PAYLOAD,record),
                         (DESCRIPTORS+f.count*16,descriptors),(COUNT,u32(f.count+8))]))
        writes=[(a,n) for a,n,v in f.writes if not STACK<=a<STACK+0x10000]
        expected=[]
        for i in range(8):
            expected += [(destination+i*4,4),(PAYLOAD+i*4,4),
                         (DESCRIPTORS+(f.count+i)*16,4),(DESCRIPTORS+(f.count+i)*16+4,4),
                         (DESCRIPTORS+(f.count+i)*16+8,8),(COUNT,4)]
        self.assertEqual(writes,expected)

    def rejected(self,f,reason):
        self.assertEqual(f.outcome,'reject')
        self.assertEqual(f.after,f.before)
        self.assertEqual(f.alloc_calls,[])
        self.assertEqual(f.index_calls,[])
        self.assertEqual(f.uc.reg_read(reg('r10')),reason)
        self.assertEqual(f.uc.reg_read(reg('rbx')),f.ordinal)
        self.assertEqual(f.uc.reg_read(reg('rbp')),f.actual_roster)
        self.assertEqual(f.uc.reg_read(reg('r14')),DESCRIPTORS)
        self.assertEqual(f.uc.reg_read(reg('r15')),0)
        self.assertEqual(f.uc.reg_read(reg('rsp')),RSP-0x38)
        for n in ('rsi','r12','r13'): self.assertEqual(f.uc.reg_read(reg(n)),SEEDS[n])
        for offset,n in [(8,'rbx'),(16,'rbp'),(24,'rsi'),(-8,'rdi'),(-16,'r14'),(-24,'r15')]:
            self.assertEqual(f.read(RSP+offset,8),u64(SEEDS[n]))
        if reason==2: self.assertEqual(f.uc.reg_read(reg('rax')),ROSTER)
        self.assertFalse(any(a==ALLOC_BOX for a,n in f.reads))
        self.assertFalse(any(DESCRIPTORS<=a<DESCRIPTORS+0x300 for a,n in f.reads))

    def test_01_pinned_sources_and_contract(self):
        self.assertEqual(native.load_source(EVIDENCE),BODY)
        self.assertEqual(len(decode(BODY,ENTRY)),130)
        self.assertEqual(len(decode(LEAF,LEAF_ENTRY)),22)
        a=emit()
        self.assertEqual(a['source_sha256'],BODY_SHA)
        self.assertEqual(a['evidence_sha256'],EVIDENCE_SHA)
        for key in ('installable','game_execution','multiplayer_verified'): self.assertIs(a[key],False)
        self.assertIsNone(a['entry_or_callsite_patch'])
        self.assertEqual(sha(bytes.fromhex(a['code_hex'])),a['code_sha256'])

    def test_02_all_ordinals_and_distinct_network_indices_against_original(self):
        for game in (GAME,0x700000000000):
            for ordinal,network in enumerate((7,0,6,1,5,2,4,3)):
                for original in (True,False):
                    with self.subTest(game=hex(game),ordinal=ordinal,original=original):
                        f=Fixture(original=original,ordinal=ordinal,network=network,count=1+ordinal,game=game)
                        self.success(f.run(f'ordinal_{ordinal}_original_{original}_{game:x}'))

    def test_03_collision_and_actual_leaf_missing_or_full_dword(self):
        buckets=[(0,0xFFFFFFFF)]*8
        for i in range(8): buckets[(1+i)&7]=(1+i*8,7-i)
        f=Fixture(entity=57,ordinal=0,buckets=buckets,network=0xFEDCBA98).run('full_hash_wrap')
        self.success(f)
        self.assertEqual([(a,n) for a,n in f.reads if BUCKETS<=a<BUCKETS+64],
                         [(BUCKETS+((1+i)&7)*8,4) for i in range(8)]+[(BUCKETS+4,4)])
        for mode in ('missing','empty'):
            self.success(Fixture(ordinal=7,index_mode=mode).run('index_'+mode))

    def test_04_ordinal_and_binding_reject_before_allocation(self):
        for ordinal in (8,0x80000000,0xFFFFFFFF):
            self.rejected(Fixture(ordinal=ordinal,allocation_storage=False).run(f'ordinal_reject_{ordinal:x}'),1)
        for ordinal,reason in ((3,2),(0xFFFFFFFF,1)):
            self.rejected(Fixture(ordinal=ordinal,actual_roster=WRONG,allocation_storage=False).run(f'wrong_binding_{ordinal:x}'),reason)

    def test_05_map_miss_and_sentinel(self):
        cases=[dict(entity=0xFFFFFFFF),dict(capacity=0,buckets=[]),
               dict(buckets=[(0,0xFFFFFFFF)]*8),dict(entity=65,buckets=[(1+i*8,2) for i in range(8)])]
        for i,options in enumerate(cases):
            f=Fixture(ordinal=0xFFFFFFFF,allocation_storage=False,**options).run(f'map_miss_{i}')
            self.rejected(f,1)

    def test_06_relocations_and_preserved_internal_branches(self):
        a=emit(); code=bytes.fromhex(a['code_hex']); base=a['code_address']
        old=decode(BODY,GAME+ENTRY); new={i.address-base:i for i in decode(code[:len(BODY)],base)}
        expected=bytearray(BODY); external=[]
        for i in old:
            off=i.address-(GAME+ENTRY)
            for op in i.operands:
                if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                    dest=i.address+i.size+op.mem.disp
                    expected[off+i.disp_offset:off+i.disp_offset+4]=struct.pack('<i',dest-(base+off+i.size))
                    actual=new[off]
                    self.assertEqual(actual.address+actual.size+actual.disp,dest)
                    external.append((off+i.disp_offset,off+i.size,dest))
            if i.group(capstone.CS_GRP_CALL):
                dest=target(i)
                expected[off+i.imm_offset:off+i.imm_offset+4]=struct.pack('<i',dest-(base+off+i.size))
                self.assertEqual(target(new[off]),dest)
                external.append((off+i.imm_offset,off+i.size,dest))
            elif i.group(capstone.CS_GRP_JUMP):
                self.assertEqual(target(new[off])-base,target(i)-(GAME+ENTRY))
        self.assertEqual(len(external),4)
        expected[SPLICE:RESUME]=b'\xe9'+struct.pack('<i',a['trampoline_address']-(base+SPLICE+5))
        self.assertEqual(code[:len(BODY)],expected)
        tail=decode(code[a['trampoline_address']-base:],a['trampoline_address'])
        self.assertEqual([i.mnemonic for i in tail],['cmp','jae','movabs','cmp','jne','movabs','mov','jmp','mov','jmp','mov','jmp'])
        self.assertEqual(target(tail[0]),8)
        self.assertEqual(target(tail[1]),tail[8].address)
        self.assertEqual(target(tail[2]),ROSTER)
        self.assertEqual(target(tail[4]),tail[10].address)
        self.assertEqual(target(tail[5]),PROPERTY-0x3A8)
        self.assertEqual(bytes(tail[6].bytes),BODY[SPLICE:RESUME])
        self.assertEqual(target(tail[7]),base+RESUME)
        for i in (9,11): self.assertEqual(target(tail[i]),a['reject_address'])

    def test_07_external_relocation_intersection_bounds(self):
        terms=[]
        for i in decode(BODY,ENTRY):
            for op in i.operands:
                if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                    terms.append((GAME+i.address+i.size+op.mem.disp,i.address-ENTRY+i.size))
            if i.group(capstone.CS_GRP_CALL): terms.append((GAME+target(i),i.address-ENTRY+i.size))
        low=max(t-n-(1<<31)+1 for t,n in terms)
        high=min(t-n+(1<<31) for t,n in terms)
        lower=(low+15)&~15; upper=high&~15
        for address in (lower,upper):
            f=Fixture(ordinal=7,changes=dict(code_address=address,reject_address=address+0x4000))
            self.success(f.run(f'relocation_bound_{address:x}'))
        for address in (lower-16,upper+16):
            with self.assertRaises(ValueError): emit(code_address=address,reject_address=address+0x4000)

    def test_08_rejection_jump_bounds_and_invalid_inputs(self):
        a=emit(); b=a['trampoline_address']; code=bytes.fromhex(a['code_hex'])
        ips=[i.address+i.size for i in decode(code[b-a['code_address']:],b)
             if i.mnemonic=='jmp' and target(i)==a['reject_address']]
        self.assertEqual(len(ips),2)
        lo=max(n-(1<<31) for n in ips); hi=min(n+(1<<31)-1 for n in ips)
        for address in (lo,hi):
            for ordinal,actual,reason in ((8,ROSTER,1),(3,WRONG,2)):
                f=Fixture(ordinal=ordinal,actual_roster=actual,allocation_storage=False,changes={'reject_address':address})
                self.rejected(f.run(f'reject_bound_{address:x}_{reason}'),reason)
        for address in (lo-1,hi+1):
            with self.assertRaises(ValueError): emit(reject_address=address)
        for source in (BODY[:-1],BODY+b'\0',bytearray(BODY),bytes([BODY[0]^1])+BODY[1:]):
            with self.assertRaises(ValueError): native.build(source,**parameters())
        for change in [dict(game_base=GAME+1),dict(code_address=GAME+0x10000001),
                       dict(property_address=ROSTER+0x400),dict(roster_address=ROSTER+1),
                       dict(property_address=0x3A0),dict(reject_address=True),
                       dict(code_address=(1<<47)-16),dict(property_address=(1<<47)-8),
                       dict(code_address=GAME+ENTRY),dict(reject_address=PROPERTY+255)]:
            with self.subTest(change=change), self.assertRaises(ValueError): emit(**change)

    def test_09_producer_payload_to_actual_receiver_across_ordinal_and_binding(self):
        for remote in (False,True):
            f=Fixture(ordinal=7,network=4).run(f'bridge_producer_{remote}')
            self.success(f)
            # Assemble the eight descriptor values in their original order.
            # This is a format bridge, not execution of the game's serializer.
            wire=b''.join(f.read(struct.unpack('<Q',f.read(DESCRIPTORS+(f.count+i)*16+8,8))[0],4) for i in range(8))
            s=REMOTE if remote else ROSTER
            p=REMOTE_PROPERTY if remote else PROPERTY
            b=REMOTE_BUCKETS if remote else BUCKETS
            for addr,size in [(s,0x700),(p-0x80,0x200),(b,64),(WIRE,0x100),(CURSOR,4)]: f.map(addr,size)
            f.setup_map(s,b,8,[(0,0xFFFFFFFF),(25,2)]+[(0,0xFFFFFFFF)]*6)
            cursor=20
            f.write(WIRE+cursor,wire); f.write(CURSOR,u32(cursor))
            a=receiver.build(RECEIVER_BODY,game_base=GAME,code_address=GAME+0x10020000,
                             roster_address=s,property_address=p,reject_address=GAME+0x10024000)
            blob=bytes.fromhex(a['code_hex'])
            f.map(a['entry_address'],len(blob)); f.write(a['entry_address'],blob)
            f.map(a['reject_address'],1); f.write(a['reject_address'],b'\xcc')
            f.reject=a['reject_address']; f.seed(); f.write(RSP,u64(f.stop))
            for n,v in dict(rsp=RSP,rcx=s,rdx=25,r8=WIRE,r9=CURSOR).items(): f.uc.reg_write(reg(n),v)
            before=f.snapshot(); f.reads=[]; f.writes=[]; f.trace=[]; f.outcome=None
            f.alloc_calls=[]; f.index_calls=[]
            f.run(f'bridge_receiver_{remote}',a['entry_address'])
            self.assertEqual(f.outcome,'return')
            self.assertEqual(f.after,expected_pages(before,[(p+2*32,wire),(CURSOR,u32(cursor+32))]))
            self.assertEqual(f.read(p+2*32+12,4),u32(4))
            self.assertEqual(f.read(PROPERTY+7*32,32),wire)
            for n,v in SEEDS.items(): self.assertEqual(f.uc.reg_read(reg(n)),v)
            self.assertEqual(f.uc.reg_read(reg('rsp')),RSP+8)
            self.assertEqual(f.uc.reg_read(reg('rax')),cursor+32)
            self.assertEqual(f.alloc_calls,[])

    def test_10_inputs_unchanged(self):
        self.assertEqual(SOURCE_PATH.read_bytes(),SOURCE_BYTES)
        self.assertEqual(RECEIVER_PATH.read_bytes(),RECEIVER_BYTES)
        for p,h in [(EVIDENCE,EVIDENCE_SHA),(BINDING,BINDING_SHA),(RECEIVER_EVIDENCE,RECEIVER_SHA)]:
            self.assertEqual(sha(p.read_bytes()),h)


def report(result):
    value={'status':'passed' if result.wasSuccessful() else 'failed',
           'test_methods_run':result.testsRun,'failure_count':len(result.failures),'error_count':len(result.errors),
           'failures':[{'test':str(t),'traceback':s} for t,s in result.failures],
           'errors':[{'test':str(t),'traceback':s} for t,s in result.errors],
           'source_sha256':{'Native/roster_producer.py':sha(SOURCE_BYTES),'Native/roster_receiver.py':sha(RECEIVER_BYTES)},
           'test_sha256':sha(Path(__file__).read_bytes()),
           'evidence_sha256':{str(p.relative_to(ROOT.parent)):h for p,h in [(EVIDENCE,EVIDENCE_SHA),(BINDING,BINDING_SHA),(RECEIVER_EVIDENCE,RECEIVER_SHA)]},
           'original_body_sha256':BODY_SHA,'original_size_bytes':len(BODY),'original_instruction_count':130,
           'index_leaf_sha256':LEAF_SHA,'python_version':sys.version,
           'unicorn_version':unicorn.__version__,'capstone_version':capstone.__version__,
           'fixture_synthetic':True,'game_process_accessed':False,'host_native_code_executed':False,
           'game_or_multiplayer_verified':False,'installable':False,'emulator_runs':RUNS,
           'allocator_scope':'Contract hook checks allocator object, size32, alignment4 and Win64 call alignment; returns mapped32bytes and clobbers volatile GPR/XMM. Does not execute real allocation, ownership, failure or recovery.',
           'verified_scope':['Actual saved producer and local-index leaf, emitted producer, all eight ordinals and permuted network indices at two high ASLR bases',
                             'Exact record/payload/descriptor/count changes and write order; nonvolatile GPR/RSP restoration',
                             'Hash collision/full wrap, sentinel/map miss, invalid ordinal/binding rejected before allocator',
                             'Two RIP references and two external calls relocated, internal branches retained, rel32 intersection boundaries',
                             'Producer descriptor values fed to actual receiver, different destination ordinal, same/different roster and sidecar binding'],
           'limits':['Saved code and synthetic memory only; original ordinals4..7 use deliberately oversized inline storage',
                     'Entry RCX is ignored by this saved producer; roster is read from global3326468 before binding guard',
                     'Allocator successful contract only; actual allocator failure, lifetime, ownership and synchronization not verified',
                     'Confirmed-peer helper data are synthetic; no proof that real client storage or service admits eight peers',
                     'Bridge assembles descriptor values without running game serializer, dispatch, transport or remote peers',
                     'Rejection stops with original interior frame; no recovery/abort or Windows unwind implementation',
                     'No hook installation/removal, concurrent callbacks, other roster consumers or multiplayer lifecycle verification']}
    out=ROOT/'verification/native_roster_producer_tests.json'
    out.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(out),'status':value['status'],'test_methods_run':result.testsRun,'emulator_executions':len(RUNS)}))


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProducerTests))
    report(result)
    raise SystemExit(0 if result.wasSuccessful() else 1)
