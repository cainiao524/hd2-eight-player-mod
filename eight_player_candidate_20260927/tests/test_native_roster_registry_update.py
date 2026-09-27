"""Saved x64 registry traversal with synthetic state and explicit opaque calls.

Root/helper candidates and captured FD9BA0 execute in Unicorn. Other-tag calls
are caller-ABI contracts, including observable external writes; rejection is
never reported as rollback of earlier registry entries. No live process use.
"""
from __future__ import annotations
import hashlib, importlib.util, json, struct, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT.parent/'five_player_feasibility_20260927'
sys.path.insert(0,str(ROOT/'.native-test-deps'))
import capstone, unicorn
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn import x86_const as xr
sha=lambda blob:hashlib.sha256(blob).hexdigest()
u32=lambda n:struct.pack('<I',n)
u64=lambda n:struct.pack('<Q',n)
reg=lambda name:getattr(xr,'UC_X86_REG_'+name.upper())
GAME=0x7FF600000000
S,B,MAP,ENTITIES=0x18200100400,0x18200800100,0x18200200100,0x18200300000
REGISTRY,CONTEXT,CONTEXT_MAP=0x18202000000,0x18203000000,0x18204000000
OBJ2E,OBJ73,OBJ115=0x18205000000,0x18206000000,0x18207000000
MAP73,BUFFER,OUT=0x18208000000,0x18209000000,0x1820A000000
ENGINE,VTA,VTB,VIRTUAL_CONTEXT,MATCH_OBJECT=0x1820B000000,0x1820B001000,0x1820B002000,0x1820B003000,0x1820B004000
OWNER_CONTEXT=0x1820B005000
STACK,RSP=0x182F0000000,0x182F0008008
MISSING,CONTEXT_MISSING=0xE0012345,0xD0717171
CLIENTS=[0x81000000+i*17 for i in range(8)]
ASSOC_IDS=[0x105+i*16 for i in range(8)]
NETWORKS=[0xF1000000+i*0x123 for i in range(8)]
LAYOUT=[('pointer',0,0xE8,8),('primary',0x40,0x108,0x70),('aux',0x3C0,0x2C8,0x38),('property',0x580,0x3A8,0x20)]
SEEDS={name:0xABCDEF0100000000+i for i,name in enumerate(('rbx','rbp','rsi','rdi','r12','r13','r14','r15'))}
EVIDENCE=RESEARCH/'roster_registry_update_native_evidence.json'
EVIDENCE_SHA='7a8f289ea8ddf85d1b2010a39d9cedc4599e9846db8936b9e215cbd4a96740e1'
ADDRESSES=ROOT/'verification/native_roster_registry_update_addresses_synthetic.json'
ADDRESSES_SHA='9e55ffae537f449fea5ffc7a8fe63df4204963c2090acd75ccd57d0b3b0fc432'
assert sha(ADDRESSES.read_bytes())==ADDRESSES_SHA
SAMPLE=ROOT/'verification/native_roster_registry_update_bundle_synthetic.json'
SAMPLE_SHA='01925487570c19244c577f2a8664e733f64c047f9914b30428105e02ead5198c'
assert sha(SAMPLE.read_bytes())==SAMPLE_SHA
RUNS=[]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


native=load('registry_update_under_test',ROOT/'Native/roster_registry_update.py')
raw=EVIDENCE.read_bytes()
assert sha(raw)==EVIDENCE_SHA
ev=json.loads(raw)
SOURCES=native.load_sources(EVIDENCE)
BODY={key:bytes.fromhex(value['bytes_hex']) for key,value in ev['bodies'].items()}


def params(game=GAME):
    return dict(game_base=game,code_address=game+0x10400000,helper_code_address=game+0x10410000,
                roster_address=S,storage_address=B,reject_address=game+0x10408000,helper_reject_address=game+0x10418000)


def decode(blob,address):
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);md.detail=True
    rows=list(md.disasm(blob,address));assert sum(row.size for row in rows)==len(blob)
    return rows


def changed_pages(before,changes):
    result={page:bytearray(blob) for page,blob in before.items()}
    for address,blob in changes:
        for i,byte in enumerate(blob):result[(address+i)&~0xFFF][(address+i)&0xFFF]=byte
    return {page:bytes(blob) for page,blob in result.items()}


class Fixture:
    def __init__(self,*,original=False,game=GAME,t=8,d=8,p=2,target=7,query=None,tags=(0x69,),
                 flags=None,statuses=None,associated=None,buffer_exists=True,converted=True,
                 object_match=True,global_s=S,registry_s=S,roster_mapped=True,changes=None):
        self.original,self.game,self.t,self.d,self.p,self.target=original,game,t,d,p,target
        self.query=CLIENTS[target] if query is None else query
        self.tags=list(tags);self.buffer_exists=buffer_exists;self.converted=converted;self.object_match=object_match
        self.flags=list(flags) if flags is not None else [i&1 for i in range(8)]
        self.statuses=list(statuses) if statuses is not None else [2 if i%3==0 else 0xAB000000+i for i in range(8)]
        self.associated=list(associated) if associated is not None else ASSOC_IDS[:]
        self.keys=[11+i*8 for i in range(8)]
        self.uc=Uc(UC_ARCH_X86,UC_MODE_64);self.pages=set()
        self.events=[];self.trace=[];self.reads=[];self.writes=[];self.write_sites=[];self.lookup_calls=0;self.property_calls=0
        self.extra_changes=[];self.phase='root';self.outcome=None
        self.stop=game+0x10500000;self.virtual_a=game+0x10510000;self.virtual_b=game+0x10520000
        values=params(game);values.update(changes or {})
        self.artifact=native.build(SOURCES,**values)
        self.functions=self.artifact['functions']
        self.root_entry=game+0xB54E00 if original else self.functions['0xb54e00']['code_address']
        self.helper_entry=game+0x606520 if original else self.functions['0x606520']['code_address']
        self.reject,self.helper_reject=values['reject_address'],values['helper_reject_address']
        for key in ('0xb54e00','0x606520'):
            address=game+int(key,16) if original else self.functions[key]['code_address']
            blob=BODY[key] if original else bytes.fromhex(self.functions[key]['code_hex'])
            self.map(address,len(blob));self.write(address,blob)
        leaf=BODY['0xfd9ba0'];self.map(game+0xFD9BA0,len(leaf));self.write(game+0xFD9BA0,leaf)
        for address,blob in [(self.stop,b'\xcc'),(self.reject,b'\xcc'),(self.helper_reject,b'\xcc'),
                              (game+0x7B5760,b'\xc3'),(game+0xFD9AF0,b'\xc3'),(game+0x1731A60,b'\xc3'),
                              (self.virtual_a,b'\xc3'),(self.virtual_b,b'\xc3')]:self.map(address,len(blob));self.write(address,blob)
        for address,size in [(REGISTRY+0x1000,0x1000),(STACK,0x10000),(ENTITIES,0x1000),
                              (CONTEXT+0xF22EC8,0x20),(CONTEXT+0xF32F20,8*0x18),(CONTEXT_MAP,0x100),
                              (OBJ2E,4),(OBJ73+0x37D58,0x120),(MAP73,32),(BUFFER,32),(OUT,4),
                              (OBJ115,3*0x1690),(OBJ115+0x2D200,4),(OBJ115+0x2FC80,4),
                              (ENGINE,0x50),(VTA,0x20),(VTB+0x160,8),(OWNER_CONTEXT+0x10,8)]:self.map(address,size)
        for rva,value in {0x3326E68:REGISTRY,0x3326468:global_s,0x346BF98:CONTEXT,0x3326308:ENGINE,0x3326348:OWNER_CONTEXT}.items():
            self.map(game+rva,8);self.write(game+rva,u64(value))
        for rva,value in {0x3483C20:0xFFFFFFFF,0x3483C34:MISSING,0x348456C:CONTEXT_MISSING}.items():
            self.map(game+rva,4);self.write(game+rva,u32(value))
        self.write(REGISTRY+0x10F0,u32(len(self.tags)))
        for i,tag in enumerate(self.tags):
            self.write(REGISTRY+0x1100+i*16,u32(tag))
            self.write(REGISTRY+0x10F8+i*16,u64({0x69:registry_s,0x73:OBJ73,0x115:OBJ115,0x2E:OBJ2E}.get(tag,0x40000000)))
        self.write(OBJ2E,u32(0x42));self.write(OUT,u32(0xAABBCCDD))
        if roster_mapped:
            for address,size in ((S-0x80,0x600),(B-0x80,0x780),(MAP,64)):self.map(address,size)
            for off,value in ((0x80,t),(0x84,d),(0x88,p),(0xD8,8),(0xDC,0),(0xE0,3)):self.write(S+off,u32(value))
            self.write(S+0xD0,u64(MAP));self.table=[(0,0xFFFFFFFF)]*8
            for i in range(4 if original else 8):
                entity=ENTITIES+i*0x40;self.write(entity+8,u32(self.keys[i]));self.write(entity+0x14,bytes([self.flags[i]]))
                if i<t:
                    index=next((self.keys[i]*3+j)&7 for j in range(8) if self.table[(self.keys[i]*3+j)&7][0]==0)
                    self.table[index]=(self.keys[i],i)
                for group,(name,off,old,stride) in enumerate(LAYOUT):
                    blob=u64(entity) if name=='pointer' else bytes((i*31+j*7+group*67)&255 for j in range(stride))
                    self.write(self.slot(name,i),blob)
                self.write(self.slot('aux',i)+0x18,u32(self.statuses[i]))
                self.write(self.slot('property',i),u32(self.associated[i]))
                self.write(self.slot('property',i)+4,u32(0xABCD1235+i*4))
                self.write(self.slot('property',i)+0xC,u32(NETWORKS[i]))
            for i,(key,value) in enumerate(self.table):self.write(MAP+i*8,u32(key)+u32(value))
        self.write(CONTEXT+0xF22EC8,u64(CONTEXT_MAP));self.write(CONTEXT+0xF22ED0,u32(16))
        self.write(CONTEXT+0xF22ED4,u32(0));self.write(CONTEXT+0xF22ED8,u32(3))
        context_table=[(0,0xFFFFFFFF)]*16
        for i,key in enumerate(ASSOC_IDS):
            index=next((key*3+j)&15 for j in range(16) if context_table[(key*3+j)&15][0]==0)
            context_table[index]=(key,i);self.write(CONTEXT+0xF32F20+i*0x18,u32(CLIENTS[i]))
        for i,(key,value) in enumerate(context_table):self.write(CONTEXT_MAP+i*8,u32(key)+u32(value))
        self.write(OBJ73+0x37D58,u64(MAP73));self.write(OBJ73+0x37D60,u32(4))
        self.write(OBJ73+0x37D64,u32(0));self.write(OBJ73+0x37D68,u32(1))
        for i in range(4):self.write(MAP73+i*8,u32(0)+u32(0xFFFFFFFF))
        self.write(MAP73+(self.keys[target]&3)*8,u32(self.keys[target])+u32(3))
        self.object_record=OBJ73+0x37D98+3*0x28
        self.write(BUFFER,u32(0x62048502 if buffer_exists else 0xDADADADA))
        self.write(OWNER_CONTEXT+0x10,u64(0x1234567800012345));self.write(ENGINE+0x38,u64(VTA));self.write(ENGINE+0x40,u64(VTB))
        self.write(VTA+8,u64(self.virtual_a));self.write(VTB+0x160,u64(self.virtual_b))
        self.write(OBJ115+0x2D200,u32(3));self.write(OBJ115+0x2FC80,u32(0x31))
        for i in range(3):self.write(OBJ115+i*0x1690,u64(MATCH_OBJECT if i==1 and object_match else MATCH_OBJECT+0x100+i))
        self.seed('root');self.before=self.snapshot()
        self.uc.hook_add(UC_HOOK_CODE,self.on_code)
        self.uc.hook_add(UC_HOOK_MEM_READ,lambda uc,access,address,size,value,data:self.reads.append((uc.reg_read(reg('rip')),address,size)))
        def on_write(uc,access,address,size,value,data):
            self.writes.append((address,size));self.write_sites.append((uc.reg_read(reg('rip')),address,size))
        self.uc.hook_add(UC_HOOK_MEM_WRITE,on_write)

    def map(self,address,size):
        for page in range(address&~0xFFF,(address+size+0xFFF)&~0xFFF,0x1000):
            if page not in self.pages:self.uc.mem_map(page,0x1000);self.uc.mem_write(page,b'\xa5'*0x1000);self.pages.add(page)
    def write(self,address,blob):self.uc.mem_write(address,blob)
    def read(self,address,size):return bytes(self.uc.mem_read(address,size))
    def int32(self,address):return struct.unpack('<I',self.read(address,4))[0]
    def int64(self,address):return struct.unpack('<Q',self.read(address,8))[0]
    def snapshot(self):return {page:self.read(page,0x1000) for page in self.pages if not STACK<=page<STACK+0x10000}
    def slot(self,name,i):
        _,off,old,stride=next(row for row in LAYOUT if row[0]==name)
        return (S+old if self.original else B+off)+i*stride
    def counts(self):return [self.int32(S+off) for off in (0x80,0x84,0x88)]
    def seed(self,phase):
        self.phase=phase
        for name,value in SEEDS.items():self.uc.reg_write(reg(name),value)
        for i in range(6,16):self.uc.reg_write(reg('xmm'+str(i)),(0x0102030405060708+i)*(1+(1<<64)))
        arguments=dict(rsp=RSP,rcx=(S if phase=='helper' else self.query),rdx=(OUT if phase=='helper' else 0xD0D0000000000002),
                       r8=(self.query if phase=='helper' else 0xE0E0000000000003),r9=0xF0F0000000000004)
        for name,value in arguments.items():self.uc.reg_write(reg(name),value)
        self.write(RSP,u64(self.stop))

    def clobber(self,rsp,returns):
        self.write(rsp+8,b'\xc7'*32)
        for i,name in enumerate(('rax','rcx','rdx','r8','r9','r10','r11')):self.uc.reg_write(reg(name),0xCDCD000000000000+i)
        for i in range(6):self.uc.reg_write(reg('xmm'+str(i)),(0xAABBCCDDEEFF0000+i)*(1+(1<<64)))
        self.uc.reg_write(reg('rax'),0)
        for name,value in returns.items():self.uc.reg_write(reg(name),value)

    def on_code(self,uc,address,size,data):
        self.trace.append(address)
        if address in (self.stop,self.reject,self.helper_reject):
            self.outcome='return' if address==self.stop else 'reject';uc.emu_stop();return
        if address==self.helper_entry and self.phase=='root':
            assert uc.reg_read(reg('rcx'))==S and uc.reg_read(reg('r8d'))==self.query
            self.events.append({'role':'actual_roster_helper'})
        if address==self.game+0xFD9BA0:
            self.lookup_calls+=1
            assert STACK<=uc.reg_read(reg('rcx'))<STACK+0x10000
            self.events.append({'role':'actual_fd9ba0','associated_id':uc.reg_read(reg('edx'))});return
        role={self.game+0x7B5760:'tag2e',self.game+0xFD9AF0:'tag115_convert',self.virtual_a:'virtual_a',
              self.virtual_b:'virtual_b',self.game+0x1731A60:'tag73_record'}.get(address)
        if role is None:return
        rsp=uc.reg_read(reg('rsp'));assert rsp%16==8 and STACK<=rsp<STACK+0x10000
        args={name:uc.reg_read(reg(name)) for name in ('rcx','rdx','r8','r9')}
        returns={};event={'role':role,'args':args}
        if role=='tag2e':
            assert args['rcx']==OBJ2E and args['rdx']==self.query
            value=self.int32(OBJ2E)+1;self.write(OBJ2E,u32(value));self.extra_changes.append((OBJ2E,u32(value)))
        elif role=='tag115_convert':
            assert args['rcx']==self.query;returns={'rax':0x1234 if self.converted else 0x7FFF}
        elif role=='virtual_a':assert args['rcx']==ENGINE;returns={'rax':VIRTUAL_CONTEXT}
        elif role=='virtual_b':assert args['rcx']==VIRTUAL_CONTEXT and args['rdx']==0x1234;returns={'rax':MATCH_OBJECT}
        elif role=='tag73_record':
            assert args['rcx']==self.object_record and args['rdx']==0x62048502
            self.property_calls+=1
            if not self.buffer_exists and self.property_calls==1:returns={'rax':0}
            else:returns={'rax':BUFFER}
            if not self.buffer_exists and self.property_calls==2:
                payload=self.read(rsp+0x28,16)
                assert payload==b'\xa5'*8+b'\0'+b'\xa5'*3+u32(2),payload.hex()
                event['uninitialized_prefix_preserved_hex']=payload.hex()
        self.events.append(event);self.clobber(rsp,returns)

    def run(self,name,phase='root'):
        self.uc.emu_start(self.helper_entry if phase=='helper' else self.root_entry,0,count=30000)
        assert self.outcome is not None,'bounded run did not finish'
        self.after=self.snapshot()
        RUNS.append(dict(name=name,component=phase,original=self.original,t=self.t,d=self.d,p=self.p,target=self.target,
                         query=self.query,tags=self.tags,outcome=self.outcome,instructions=len(self.trace),
                         actual_fd9ba0_entries=self.lookup_calls,contract_and_helper_events=self.events))
        return self


class RegistryTests(unittest.TestCase):
    def abi(self,f,rejected=False):
        self.assertEqual(f.uc.reg_read(reg('rsp')),RSP if rejected else RSP+8)
        for name,value in SEEDS.items():self.assertEqual(f.uc.reg_read(reg(name)),value,name)
        for i in range(6,16):self.assertEqual(f.uc.reg_read(reg('xmm'+str(i))),(0x0102030405060708+i)*(1+(1<<64)))
    def assert_changes(self,f,changes):
        self.assertEqual(f.after,changed_pages(f.before,changes))
        if not f.original:
            self.assertFalse(any(S+0xE8<=address<S+0x428 for rip,address,size in f.reads),'old inline roster read')
    def array_sites(self,f,key,matched):
        if f.original:return
        item=f.functions[key]
        patches={row['original_rva']:row for row in item['array_patches']}
        isroot=key=='0xb54e00'
        start=0xB5501C if isroot else 0x606559
        self.assertEqual(patches[start]['emitted_address'] in f.trace,f.d>0)
        read_rva=0xB55030 if isroot else 0x606560
        actual=[(address,size) for rip,address,size in f.reads if rip==item['mapping'][hex(read_rva)]]
        self.assertEqual(actual,[(f.slot('property',i),4) for i in range(f.d if matched is None else matched+1)])
        def access(site,entries):
            patch=patches[site];lo=patch['emitted_address'];hi=lo+len(bytes.fromhex(patch['replacement_hex']))
            return [(address,size) for rip,address,size in entries if lo<=rip<hi]
        for site in ((0xB55057,0xB550E9) if isroot else (0x606622,)):
            self.assertEqual(access(site,f.reads),[] if matched is None else [(f.slot('pointer',matched),8)])
        if isroot:
            self.assertEqual(access(0xB550CD,f.reads),[] if matched is None else [(f.slot('aux',matched)+0x18,4)])
            self.assertEqual(access(0xB550D8,f.write_sites),[] if matched is None or f.statuses[matched]==2 else [(f.slot('aux',matched)+0x18,4)])
            property_access=[] if matched is None or not(f.flags[matched]&1) else [(f.slot('property',matched)+4,4)]
            self.assertEqual(access(0xB550FB,f.reads),property_access)
            self.assertEqual(access(0xB550FB,f.write_sites),property_access)
    def root_success(self,f,matched=None):
        self.assertEqual(f.outcome,'return');self.abi(f)
        changes=list(f.extra_changes)
        if 0x69 in f.tags:
            expected_calls=f.d if matched is None else matched+1
            self.assertEqual(f.lookup_calls,expected_calls)
            if matched is not None:
                if f.statuses[matched]!=2:changes.append((f.slot('aux',matched)+0x18,u32(1)))
                if f.flags[matched]&1:changes.append((f.slot('property',matched)+4,u32((0xABCD1235+matched*4)&0xFFFFFFFE)))
                self.assertGreaterEqual(sum((address,size)==(f.slot('pointer',matched),8) for rip,address,size in f.reads),2)
            self.array_sites(f,'0xb54e00',matched)
        else:self.assertEqual(f.lookup_calls,0)
        if 0x73 in f.tags and matched is not None:
            self.assertEqual(f.property_calls,1 if f.buffer_exists else 2)
            if f.buffer_exists:changes.append((BUFFER+0xC,b'\0'))
            else:changes.append((BUFFER,u32(0x62048502)+b'\xa5'*8+b'\0'+b'\xa5'*3+u32(2)))
        if 0x73 in f.tags:self.array_sites(f,'0x606520',matched)
        if 0x115 in f.tags:
            changes.append((OBJ115+0x2FC80,u32(0x32)))
            if f.converted and f.object_match:
                changes.extend([(OBJ115+0x1690+0x20,u64(0x1234567800012345)),(OBJ115+0x1690+0x29,b'\1')])
        self.assert_changes(f,changes)
        if S&~0xFFF in f.pages:self.assertEqual(f.counts(),[f.t,f.d,f.p])
    def helper_success(self,f,matched=None):
        self.assertEqual(f.outcome,'return');self.abi(f)
        self.assertEqual(f.uc.reg_read(reg('rax')),OUT)
        self.assert_changes(f,[(OUT,u32(MISSING if matched is None else f.keys[matched]))])
        self.assertEqual(f.events,[])
        if matched is not None:self.assertIn((f.slot('pointer',matched),8),[(address,size) for rip,address,size in f.reads])
        self.array_sites(f,'0x606520',matched)

    def test_01_fixed_sources_and_complete_decode(self):
        self.assertEqual(SOURCES['0xb54e00'],BODY['0xb54e00']);self.assertEqual(SOURCES['0x606520'],BODY['0x606520'])
        artifact=native.build(SOURCES,**params())
        for key in ('0xb54e00','0x606520'):
            item=artifact['functions'][key];blob=bytes.fromhex(item['code_hex'])
            rows=decode(blob,item['code_address']);self.assertEqual(sha(blob),item['code_sha256'])
            boundaries={row.address for row in rows}
            direct_calls={GAME+rva for rva in (0xFD9AF0,0xFD9BA0,0x7B5760,0x1731A60)}|{params()['helper_code_address']}
            for row in rows:
                if row.group(capstone.CS_GRP_JUMP) and row.operands[0].type==capstone.x86.X86_OP_IMM:
                    self.assertIn(row.operands[0].imm,boundaries|{item['reject_address']})
                if row.group(capstone.CS_GRP_CALL) and row.operands[0].type==capstone.x86.X86_OP_IMM:
                    self.assertIn(row.operands[0].imm,direct_calls)
            for patch in item['array_patches']:
                self.assertIn(patch['emitted_address'],boundaries)
                self.assertEqual(blob[patch['emitted_address']-item['code_address']:][:len(bytes.fromhex(patch['replacement_hex']))].hex(),patch['replacement_hex'])
        for key in SOURCES:
            bad=dict(SOURCES);bad[key]=bytes([BODY[key][0]^1])+BODY[key][1:]
            with self.assertRaises(ValueError):native.build(bad,**params())

    def test_02_tag69_all_eight_slots_and_four_slot_original_pairs(self):
        for i in range(8):self.root_success(Fixture(target=i).run('all_eight_tag69_slots'),i)
        for i in range(4):
            original=Fixture(original=True,t=4,d=4,target=i).run('original_tag69_baseline')
            candidate=Fixture(t=4,d=4,target=i).run('candidate_tag69_pair')
            self.root_success(original,i);self.root_success(candidate,i)
            for name,off,old,stride in LAYOUT:
                self.assertEqual([original.read(original.slot(name,j),stride) for j in range(4)],
                                 [candidate.read(candidate.slot(name,j),stride) for j in range(4)])
        self.root_success(Fixture(target=7,game=0x7FF800000000).run('tag69_second_aslr'),7)

    def test_03_true_helper_eight_slots_dense_limit_missing_and_sentinels(self):
        for i in range(8):
            f=Fixture(tags=(),target=i);f.seed('helper');f.before=f.snapshot()
            self.helper_success(f.run('helper_all_eight_slots','helper'),i)
        for i in range(4):
            for original in (True,False):
                f=Fixture(tags=(),target=i,t=4,d=4,original=original);f.seed('helper');f.before=f.snapshot()
                self.helper_success(f.run('helper_original_candidate_baseline','helper'),i)
        for options in [dict(t=0,d=0,p=0,target=0),dict(t=8,d=3,p=1,target=7),
                        dict(target=7,query=0x91717171),dict(target=7,associated=[0x7FFF]*8,query=CONTEXT_MISSING)]:
            f=Fixture(tags=(),**options);f.seed('helper');f.before=f.snapshot()
            self.helper_success(f.run('helper_ordinary_missing','helper'))
        # Root FD9BA0 returns context-missing for 7FFF and may match it;
        # 606520 deliberately skips 7FFF. Both original distinctions remain.
        f=Fixture(target=0,associated=[0x7FFF]*8,query=CONTEXT_MISSING).run('tag69_sentinel_conversion_can_match')
        self.root_success(f,0)
        for options in [dict(t=0,d=0,p=0,target=0),dict(t=8,d=3,p=1,target=7),dict(query=0x91717171)]:
            self.root_success(Fixture(**options).run('tag69_no_dense_match'))
        for options in [dict(t=0,d=0,p=0,target=0),dict(target=7,query=0x91717171)]:
            f=Fixture(**options);f.write(S+0xD8,u32(0));f.before=f.snapshot()
            self.root_success(f.run('tag69_map_capacity_only_checked_after_match'))
        f=Fixture(tags=(),target=7,global_s=0x40000000);f.seed('helper');f.before=f.snapshot()
        self.helper_success(f.run('helper_explicit_S_not_global_binding','helper'),7)
        # Duplicate inverse result must stop at first dense match.
        associated=ASSOC_IDS[:];associated[1]=ASSOC_IDS[5]
        f=Fixture(target=5,associated=associated).run('tag69_first_duplicate_match')
        self.root_success(f,1)

    def test_04_tag73_existing_and_fallback_preserve_foreign_object(self):
        for exists in (True,False):
            f=Fixture(target=7,tags=(0x73,),buffer_exists=exists).run('tag73_true_helper_eighth_slot')
            self.root_success(f,7)
            self.assertEqual([e['role'] for e in f.events],['actual_roster_helper']+['tag73_record']*(1 if exists else 2))
        for options in [dict(t=0,d=0,p=0,target=0),dict(t=8,d=3,p=1,target=7),dict(associated=[0x7FFF]*8)]:
            f=Fixture(tags=(0x73,),**options).run('tag73_ordinary_missing')
            self.root_success(f);self.assertEqual(f.property_calls,0)
        for original in (True,False):
            f=Fixture(t=4,d=4,target=3,tags=(0x73,),original=original,buffer_exists=False).run('tag73_original_candidate_fallback')
            self.root_success(f,3)

    def test_05_other_tags_empty_registry_and_mixed_order(self):
        for tags in [(),(0x999,),(0x2E,0x115,0x999)]:
            for original in (True,False):
                f=Fixture(tags=tags,original=original,t=4,d=4,target=1,global_s=0x40000000,roster_mapped=False).run('nonroster_tags_no_binding_requirement')
                self.root_success(f)
                roles=[e['role'] for e in f.events]
                self.assertEqual(roles,[] if not tags or tags==(0x999,) else ['tag2e','tag115_convert','virtual_a','virtual_b'])
        for converted,match in [(False,True),(True,False)]:
            f=Fixture(tags=(0x115,),converted=converted,object_match=match).run('tag115_preserved_no_matching_record')
            self.root_success(f)
        f=Fixture(tags=(0x2E,0x69,0x73,0x115,0x999),target=7).run('mixed_registry_order')
        self.root_success(f,7)
        self.assertEqual([e['role'] for e in f.events],['tag2e']+['actual_fd9ba0']*8+
                         ['actual_roster_helper','tag73_record','tag115_convert','virtual_a','virtual_b'])

    def test_06_root_guards_and_prior_registry_effects_are_not_rollback(self):
        cases=[('registry_binding',1),('global_binding',2),('tracked_nine',3),('dense_order',4),('prefix_order',4),
               ('null_pointer',5),('empty_entity',6),('invalid_entity',7),('missing_full',7),('missing_empty',7),
               ('ordinal_eight',7),('ordinal_untracked',7),('map_capacity',8),('ordinal_wrong',9)]
        late={'null_pointer','empty_entity','invalid_entity','missing_full','missing_empty','ordinal_eight','ordinal_untracked','map_capacity','ordinal_wrong'}
        for name,reason in cases:
            small=name in ('missing_empty','ordinal_untracked')
            f=Fixture(t=2 if small else 8,d=2 if small else 8,p=0 if small else 2,target=1)
            if name=='registry_binding':f.write(REGISTRY+0x10F8,u64(0x40000000))
            elif name=='global_binding':f.write(GAME+0x3326468,u64(0x40000000))
            elif name=='tracked_nine':f.write(S+0x80,u32(9))
            elif name=='dense_order':f.write(S+0x84,u32(9))
            elif name=='prefix_order':f.write(S+0x88,u32(9))
            elif name=='null_pointer':f.write(f.slot('pointer',1),u64(0))
            elif name=='empty_entity':f.write(ENTITIES+0x40+8,u32(0))
            elif name=='invalid_entity':f.write(ENTITIES+0x40+8,u32(0xFFFFFFFF))
            elif name.startswith('missing_'):f.write(ENTITIES+0x40+8,u32(75))
            elif name=='map_capacity':f.write(S+0xD8,u32(4))
            else:
                bucket=next(i for i,(key,value) in enumerate(f.table) if key==f.keys[1])
                f.write(MAP+bucket*8+4,u32(8 if name=='ordinal_eight' else 2 if name=='ordinal_untracked' else 0))
            f.before=f.snapshot();f.run('root_guard_'+name)
            self.assertEqual(f.outcome,'reject');self.assertEqual(f.uc.reg_read(reg('r10d')),reason)
            self.assertEqual(f.uc.reg_read(reg('ecx')),f.query);self.abi(f,True)
            self.assertEqual(f.after,f.before);self.assertEqual(f.lookup_calls,2 if name in late else 0)
            self.assertTrue(all(e['role']=='actual_fd9ba0' for e in f.events))
            self.assertTrue(all(STACK<=address and address+size<=STACK+0x10000 for address,size in f.writes))
        for tag,reason in [(0x69,2),(0x73,1)]:
            f=Fixture(tags=(tag,),t=0,d=0,p=0,target=0,global_s=0x40000000)
            f.before=f.snapshot();f.run('binding_rejection_precedes_empty_dense')
            self.assertEqual(f.outcome,'reject');self.assertEqual(f.uc.reg_read(reg('r10d')),reason)
            self.abi(f,True);self.assertEqual(f.after,f.before);self.assertEqual(f.events,[])
        # A valid earlier tag2E has an explicit irreversible-for-this-call
        # marker effect. The following tag's rejection restores registers but
        # leaves that earlier effect intact, as the real traversal contract says.
        f=Fixture(tags=(0x2E,0x69),target=1);f.write(ENTITIES+0x40+8,u32(0));f.before=f.snapshot()
        f.run('earlier_registry_effect_survives_late_rejection')
        self.assertEqual(f.outcome,'reject');self.assertEqual(f.uc.reg_read(reg('r10d')),6)
        self.abi(f,True);self.assertEqual(f.uc.reg_read(reg('ecx')),f.query)
        self.assertEqual(f.after,changed_pages(f.before,[(OBJ2E,u32(0x43))]))
        self.assertEqual([e['role'] for e in f.events],['tag2e','actual_fd9ba0','actual_fd9ba0'])
        # Tag73 prechecks before entering its helper; this is not a nested
        # rejection unwinder or permission for concurrently changing S.
        f=Fixture(tags=(0x73,),target=1);f.write(S+0x80,u32(9));f.before=f.snapshot();f.run('tag73_counts_precheck')
        self.assertEqual(f.outcome,'reject');self.assertEqual(f.uc.reg_read(reg('r10d')),3)
        self.abi(f,True);self.assertEqual(f.events,[]);self.assertEqual(f.after,f.before)

    def test_07_standalone_helper_entry_rejects_without_stack_or_output_writes(self):
        for name,reason in [('binding',1),('tracked_nine',3),('dense_order',4),('prefix_order',4)]:
            f=Fixture(tags=());f.seed('helper')
            if name=='binding':f.uc.reg_write(reg('rcx'),0x40000000)
            elif name=='tracked_nine':f.write(S+0x80,u32(9))
            elif name=='dense_order':f.write(S+0x84,u32(9))
            else:f.write(S+0x88,u32(9))
            expected={name:f.uc.reg_read(reg(name)) for name in ('rcx','rdx','r8')}
            f.before=f.snapshot();f.run('helper_guard_'+name,'helper')
            self.assertEqual(f.outcome,'reject');self.assertEqual(f.uc.reg_read(reg('r10d')),reason)
            self.abi(f,True);self.assertEqual(f.events,[]);self.assertEqual(f.writes,[]);self.assertEqual(f.after,f.before)
            for name,value in expected.items():self.assertEqual(f.uc.reg_read(reg(name)),value)

    def test_08_addresses_rel32_and_fifteen_function_bundle(self):
        for update in [dict(game_base=GAME+1),dict(code_address=GAME+0xB54E00),dict(helper_code_address=params()['code_address']),
                       dict(storage_address=B+1),dict(storage_address=S+0x100),dict(reject_address=B+0x500),
                       dict(helper_reject_address=params()['reject_address'])]:
            values=params();values.update(update)
            with self.assertRaises(ValueError):native.build(SOURCES,**values)
        artifact=native.build(SOURCES,**params())
        for key,field in [('0xb54e00','reject_address'),('0x606520','helper_reject_address')]:
            item=artifact['functions'][key]
            jumps=[row for row in decode(bytes.fromhex(item['code_hex']),item['code_address'])
                   if row.mnemonic=='jmp' and row.operands[0].type==capstone.x86.X86_OP_IMM and row.operands[0].imm==item['reject_address']]
            lo=max(row.address+row.size-(1<<31) for row in jumps);hi=min(row.address+row.size+(1<<31)-1 for row in jumps)
            for address in (lo,hi):
                f=Fixture(changes={field:address})
                if key=='0xb54e00':f.write(GAME+0x3326468,u64(0x40000000));phase='root';reason=2
                else:f.seed('helper');f.uc.reg_write(reg('rcx'),0x40000000);phase='helper';reason=1
                f.before=f.snapshot();f.run('reject_rel32_boundary',phase)
                self.assertEqual(f.outcome,'reject');self.assertEqual(f.uc.reg_read(reg('r10d')),reason);self.abi(f,True)
                self.assertEqual(f.after,f.before);self.assertEqual(f.events,[])
            for address in (lo-1,hi+1):
                values=params();values[field]=address
                with self.assertRaises(ValueError):native.build(SOURCES,**values)
        dep=native.departure;g=dep.getter;rm=native.remove;mv=native.move
        ds=[dep.load_source(RESEARCH/'roster_departure_native_evidence.json'),g.load_source(RESEARCH/'roster_getter_native_evidence.json'),
            g.classify.load_sources(RESEARCH/'roster_classify_native_evidence.json'),rm.load_sources(RESEARCH/'roster_remove_native_evidence.json'),
            rm.insert.load_sources(RESEARCH/'roster_insert_native_evidence.json'),mv.load_source(RESEARCH/'roster_move_native_evidence.json'),
            rm.insert.base_bundle.pair.producer.load_source(RESEARCH/'roster_property_producer_native_evidence.json'),
            rm.insert.base_bundle.pair.receiver.load_source(RESEARCH/'roster_property_receive_evidence.json')]
        counts=dep.player_count.load_sources(RESEARCH/'roster_player_count_native_evidence.json',RESEARCH/'roster_departure_callee_evidence.json')
        values=json.loads(ADDRESSES.read_bytes());values.update(player_count_context_source=counts['context'],player_count_filter_source=counts['filter'])
        bundle=native.build_bundle(SOURCES,*ds,**values)
        self.assertEqual(bundle,json.loads(SAMPLE.read_bytes()))
        self.assertEqual(bundle['shared_binding'],dict(game_base=GAME,roster_address=S,storage_address=B))
        self.assertEqual(bundle['registry_update']['shared_binding'],bundle['base_bundle']['shared_binding'])
        self.assertEqual(len(bundle['known_regions']),59)
        calls=[row for row in bundle['registry_update']['functions']['0xb54e00']['relocations'] if row.get('helper_callsite_replaced')]
        self.assertEqual(len(calls),1);self.assertEqual(calls[0]['target_address'],values['registry_helper_code_address'])
        for field,value in [('registry_code_address',values['departure_code_address']),
                            ('registry_helper_code_address',values['getter_code_address']),
                            ('registry_reject_address',values['receiver_reject_address']),
                            ('registry_code_address',values['player_count_trampoline_address'])]:
            bad=dict(values);bad[field]=value
            with self.assertRaises(ValueError):native.build_bundle(SOURCES,*ds,**bad)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RegistryTests))
    sources=['roster_registry_update','roster_departure','roster_getter','roster_classify','roster_remove','roster_insert',
             'roster_move','roster_bundle','roster_property_pair','roster_producer','roster_receiver','player_count']
    build_evidence=['roster_departure_native_evidence.json','roster_getter_native_evidence.json','roster_classify_native_evidence.json',
                    'roster_remove_native_evidence.json','roster_insert_native_evidence.json','roster_move_native_evidence.json',
                    'roster_property_producer_native_evidence.json','roster_property_receive_evidence.json',
                    'roster_player_count_native_evidence.json','roster_departure_callee_evidence.json']
    def count(original,component,outcome):return sum(run['original']==original and run['component']==component and run['outcome']==outcome for run in RUNS)
    report=dict(status='passed' if result.wasSuccessful() else 'failed',test_methods_run=result.testsRun,
                failure_count=len(result.failures),error_count=len(result.errors),
                failures=[{'test':str(test),'traceback':tb} for test,tb in result.failures],
                errors=[{'test':str(test),'traceback':tb} for test,tb in result.errors],
                source_sha256={f'Native/{name}.py':sha((ROOT/f'Native/{name}.py').read_bytes()) for name in sources},
                test_sha256=sha(Path(__file__).read_bytes()),
                test_dependency_sha256={str(path.relative_to(ROOT)):expected for path,expected in [(ADDRESSES,ADDRESSES_SHA),(SAMPLE,SAMPLE_SHA)]},
                evidence_sha256={EVIDENCE.name:EVIDENCE_SHA,**{name:sha((RESEARCH/name).read_bytes()) for name in build_evidence}},
                evidence_scopes={'executed_saved_bodies':EVIDENCE.name,'build_bundle_only':build_evidence},
                saved_body_sha256={key:sha(blob) for key,blob in BODY.items()},
                python_version=sys.version,unicorn_version=unicorn.__version__,capstone_version=capstone.__version__,
                fixture_synthetic=True,game_process_accessed=False,host_native_code_executed=False,installable=False,
                emulator_runs=RUNS,
                execution_counts={'total':len(RUNS),'original_baseline':sum(run['original'] for run in RUNS),
                                  'candidate':sum(not run['original'] for run in RUNS),
                                  'original_root_return':count(True,'root','return'),'original_helper_return':count(True,'helper','return'),
                                  'candidate_root_return':count(False,'root','return'),'candidate_root_reject':count(False,'root','reject'),
                                  'candidate_helper_return':count(False,'helper','return'),'candidate_helper_reject':count(False,'helper','reject')},
                nested_helper_entries_not_added_to_total={
                    'actual_saved_fd9ba0':sum(run['actual_fd9ba0_entries'] for run in RUNS),
                    'original_606520_called_by_original_root':sum(event['role']=='actual_roster_helper' for run in RUNS if run['original'] for event in run['contract_and_helper_events']),
                    'candidate_606520_called_by_candidate_root':sum(event['role']=='actual_roster_helper' for run in RUNS if not run['original'] for event in run['contract_and_helper_events'])},
                oracle_scope={
                    'full_memory':'Every successful run compares all nonstack pages against independently enumerated expected changes, keeping unrelated records, registry maps, S counts, primary bytes and canaries unchanged',
                    'array_sites':'Candidate root six patches and helper two patches are checked against decoded instruction boundaries; each exercised memory operation is checked by emitted RIP, exact slot address, access width and conditional presence, including LEA-derived traversal',
                    'tag69':'Original four-slot complete pairs and all eight candidate ordinals, aux2 retained/other DWORDs become1, property flag masked only when entity bit0 is set; bit0 is deliberately independent of P, first duplicate conversion stops the search, pending beyond D is not scanned',
                    'helper':'Complete 606520 executes as captured or candidate; returns entity ID and original OUT pointer, preserves nondefault global missing value, scans only D, skips7FFF and uses explicit RCX S independently of global S',
                    'context_leaf':'Actual captured 220-byte FD9BA0 executes valid context hits and 7FFF context-default conversion, including the semantic difference from helper skipping7FFF; ordinary search misses use valid conversions unequal to the input ID',
                    'rejection':'Root restores original entry RSP/nonvolatile registers/ECX input ID; helper entry guards preserve RCX/RDX/R8 and OUT with no writes including stack. Rejection after an earlier tag2E contract-stub marker leaves that marker intact; it is not rollback',
                    'bundle':'Fifteen roster functions plus player-count plan are built, match the pinned saved sample, and share S/B; cross-component overlaps and both reject-rel32 endpoint ranges are checked; older suites are not rerun'},
                contract_stubs={
                    '0x7b5760':'Tag2E: check RCX entry object and EDX input ID, increment a synthetic external marker DWORD; this demonstrates an earlier opaque effect without executing real 7B5760',
                    '0xfd9af0':'Tag115 forward conversion: check ECX input ID, return chosen conversion 1234 or7FFF; this is not execution of the saved FD9AF0 body',
                    'context.interface38+8':'Check RCX global3326308 context, return an opaque context pointer for the second indirect call',
                    'context.interface40+160':'Check returned RCX and EDX conversion1234, return a synthetic object pointer; original root searches real1690h records and writes owner from distinct global3326348+10h, flag and counter',
                    '0x1731a60':'Tag73 foreign-object record: check RCX object+37D98+3*28h and EDX62048502; either return an existing correctly keyed buffer once or null then writable buffer. Original fallback preserves supplied nonzero first8 stack bytes, initializes only its stated remaining bytes and copies the complete16B payload',
                    'all_stubs':'Validate Win64 entry stack alignment, overwrite32B shadow, clobber volatile GPR/XMM0..5, preserve nonvolatiles; no registry/roster/context reentrancy or mutation beyond the explicit tag2E marker'},
                limits=[
                    'Synthetic valid registry, S/B, entity pointers, context maps/backing and serialized lifetimes are supplied; guards do not establish OS readability, ownership or synchronization',
                    'Context zero-capacity/full-table misses, empty-key false hits or arbitrary invalid map values remain original hazards and are not claimed safe by these valid fixtures',
                    'Root late guard prevents current tag69 roster writes but cannot undo earlier opaque registry-entry effects; no rollback or general nested-helper rejection unwinder is tested',
                    'Tag73 property-record access, tag115 conversion/indirect calls and tag2E effects are declared contract stubs; real resource behavior, failures and callbacks are not executed',
                    'Tag73 fallback intentionally retains opaque stack bytes; passing this comparison does not validate their game-specific ownership or initialization contract',
                    'No new getter/removal chain was added; existing components are included only in the common artifact build and their unchanged suites were not rerun',
                    'Finite original/candidate tests do not prove runtime assets, publication/migration/cleanup, hooks, unwind, live integration, installation or five-through-eight-account mission acceptance'])
    (ROOT/'verification/native_roster_registry_update_tests.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],methods=result.testsRun,executions=len(RUNS),failures=len(result.failures),errors=len(result.errors))))
    raise SystemExit(0 if result.wasSuccessful() else 1)
