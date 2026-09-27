"""Finite complete-departure x64 tests with real registry helpers and explicit callbacks.

All memory is synthetic Unicorn RAM. Captured registry helpers perform their
actual lookup/list edits; notification and engine operations use narrow caller
contracts recorded below. No process, executable allocation or installation.
"""
from __future__ import annotations
import hashlib, importlib.util, json, struct, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT.parent / 'five_player_feasibility_20260927'
sys.path.insert(0, str(ROOT / '.native-test-deps'))
import capstone, unicorn
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as xr

sha = lambda blob: hashlib.sha256(blob).hexdigest()
u32 = lambda value: struct.pack('<I', value)
u64 = lambda value: struct.pack('<Q', value)
reg = lambda name: getattr(xr, 'UC_X86_REG_' + name.upper())
GAME = 0x7FF600000000
S, B, MAP, ENTITIES = 0x18200100400, 0x18200800100, 0x18200200100, 0x18200300000
CONTEXT, VTABLE = 0x18200400000, 0x18200401000
MODE, MANAGER, UI_MANAGER, UI, CONFIG = [0x18200500000 + i * 0x2000000 for i in range(5)]
ASSOC_CONTEXT, ASSOC_MAP, ASSOC_MAP2 = 0x18210000000, 0x18211000000, 0x18211001000
MANAGER_MAP, RESOURCE_BASE = 0x18212000000, 0x18213000000
NETWORK_CONTEXT, SPAWN_CONTEXT, DISCONNECT_CONTEXT = 0x18214000000, 0x18215000000, 0x18216000000
STACK, RSP = 0x182F0000000, 0x182F0008008
ASSOC = ASSOC_CONTEXT + 0xF32F18 + 2 * 0x18
ASSOC_LOOKUP_ID, ASSOC_ID, CONTROLLER_ID, CREATED_ID = 0x123, 0xA313, 0x39, 0xB417
SEEDS = {name: 0xABCDEF0100000000 + i for i, name in enumerate(('rbx', 'rbp', 'rsi', 'rdi', 'r12', 'r13', 'r14', 'r15'))}
LAYOUT = [('pointer', 0, 0xE8, 8), ('primary', 0x40, 0x108, 0x70),
          ('aux', 0x3C0, 0x2C8, 0x38), ('property', 0x580, 0x3A8, 0x20)]
NETWORKS = [0x80000007, 0xFFFFFFFE, 0x7FFFFFFF, 0x12345678, 0xABCDEF04, 0x10000, 0xFFFFFFFF, 0xFEDCBA98]
PRIMARY = {0xB0B020: 0x490, 0xB11C20: 0xEB0, 0xB0F820: 0xB50}
STUBS = {0x139C360: 'network', 0x13462C0: 'disconnected', 0x838680: 'associated_controller',
         0xA747D0: 'record_reset', 0xA74700: 'record_query', 0xA77800: 'record_flag',
         0x135A4A0: 'link_old', 0xBE21A0: 'relationship_old', 0x13BFB40: 'create_output',
         0x135AB10: 'link_output', 0xBE16F0: 'relationship_output', 0xFDC310: 'queue_entity',
         0x94C9C0: 'ui', 0x60C2A0: 'count'}
EVIDENCE_PINS = {
    'roster_departure_native_evidence.json': '0280267b6f32d4a24f15c69da317d1c2c7a93adb136d4252ff93e09a8d67e609',
    'roster_departure_callee_evidence.json': '04e16b4b9a301ba2fbd796528df6e53f9d3d8a25626cd459cc9f1329edd5d0d0',
    'roster_getter_native_evidence.json': '1360863bfe1f1f6ce640ef049776d3b31703a1cbfe2bea3f90bf20555f69e0fd',
    'roster_remove_native_evidence.json': '67563b2d12860c814096b1d45338dd271ad13975c3ba4f96169a92473ab061af',
    'roster_departure_aux_evidence.json': '43507a33e177e0a3f43bb0afe16dce99c59a059d57a5a15ec09a7c6d105793df',
    'roster_classify_native_evidence.json': 'f20165dad6823edc40fbcdf0434123139f1c80d9222a2b20d3f4c067768e9e33',
    'roster_insert_native_evidence.json': '794c357a56b2aa28cfd1061374afe27c1a3a2c06d31ce4ca736e4b783e41b497',
    'roster_move_native_evidence.json': '115802c09eb15f840932667717731150aa347e7ae8a72245dd92e05a5e86a242',
    'roster_property_producer_native_evidence.json': 'f73ec903d06f2304f4f944c25e011a7ef86d78737cb1b197101a1c96daaabacb',
    'roster_property_receive_evidence.json': 'bad5661771df280dd5e982b765d2f4ab1c73de9ae7e86e974751af6c3c383c10',
    'roster_player_count_native_evidence.json': '8f0fad49d9f5bc7e95ffe8735007b59c302034704707602c8d8093ad795676e3',
}
ADDRESSES = ROOT / 'verification/native_roster_departure_addresses_synthetic.json'
ADDRESSES_SHA = 'c24a3b5cb6ce31ca8a5fae5c803de41fd06a8baafa8962b08abfa7673f36b231'
assert sha(ADDRESSES.read_bytes()) == ADDRESSES_SHA
for evidence_name in EVIDENCE_PINS:
    assert sha((RESEARCH / evidence_name).read_bytes()) == EVIDENCE_PINS[evidence_name]
RUNS = []


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def evidence(name):
    blob = (RESEARCH / name).read_bytes()
    assert sha(blob) == EVIDENCE_PINS[name], name
    return json.loads(blob)


dep_ev = evidence('roster_departure_native_evidence.json')
callee_ev = evidence('roster_departure_callee_evidence.json')
remove_ev = evidence('roster_remove_native_evidence.json')
BODY = bytes.fromhex(dep_ev['bodies']['0x605950']['bytes_hex'])
BODIES = {0x606820: bytes.fromhex(dep_ev['bodies']['0x606820']['bytes_hex'])}
BODIES.update({entry: bytes.fromhex(callee_ev['bodies'][hex(entry)]['bytes_hex']) for entry in [*PRIMARY, 0xFD9C80]})
aux_ev = evidence('roster_departure_aux_evidence.json')
# Captured instructions preserve ECX for the subsequent create-output callsite.
BODIES[0xFD9D40] = bytes.fromhex(aux_ev['bodies']['0xfd9d40']['bytes_hex'])
assert sha(BODIES[0xFD9D40]) == '27627b0418666a4ce50917587d9dd779c3736a8af2272a3a3c955f94cb3701ed'
FLOAT_ONE = bytes.fromhex(aux_ev['literals']['0x23c6d70']['bytes_hex'])
assert FLOAT_ONE == bytes.fromhex('0000803f') and sha(FLOAT_ONE) == aux_ev['literals']['0x23c6d70']['sha256']
native = load('departure_under_test', ROOT / 'Native/roster_departure.py')
getter = load('departure_getter_dependency', ROOT / 'Native/roster_getter.py')
remove = load('departure_remove_dependency', ROOT / 'Native/roster_remove.py')
move = load('departure_move_dependency', ROOT / 'Native/roster_move.py')
GETTER = getter.load_source(RESEARCH / 'roster_getter_native_evidence.json')


def params(game=GAME):
    return dict(game_base=game, code_address=game + 0x10200000, roster_address=S, storage_address=B,
                getter_code_address=game + 0x100F0000, reject_address=game + 0x10208000)


def decode(blob, address):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail = True
    rows = list(md.disasm(blob, address)); assert sum(row.size for row in rows) == len(blob)
    return rows


def changed_pages(before, changes):
    result = {page: bytearray(blob) for page, blob in before.items()}
    for address, blob in changes:
        for i, byte in enumerate(blob): result[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte
    return {page: bytes(blob) for page, blob in result.items()}


class Fixture:
    def __init__(self, *, t=8, d=6, p=2, ordinal=1, original=False, game=GAME,
                 associated=False, associated_flag=True, controller=True, query=True,
                 disconnected=True, deferred=False, mode=4, manager_loop=True, ui=True,
                 multiplier=1, args=None):
        self.t, self.d, self.p, self.ordinal = t, d, p, ordinal
        self.original, self.game, self.associated = original, game, associated
        self.associated_flag, self.controller, self.query = associated_flag, controller, query
        self.disconnected, self.deferred, self.mode = disconnected, deferred, mode
        self.manager_loop, self.ui = manager_loop, ui
        self.keys = [11 + i * 8 for i in range(8)]
        self.target = ENTITIES + ordinal * 0x40
        self.uc = Uc(UC_ARCH_X86, UC_MODE_64)
        self.pages, self.events, self.trace, self.reads, self.writes = set(), [], [], [], []
        self.read_sites, self.extra_helpers = [], {}
        self.expected_changes, self.primary_lists = [], {}
        self.stop, self.tail, self.predicate = game + 0x10300000, game + 0x10220000, game + 0x10210000
        values = params(game); values.update(args or {})
        self.artifact = native.build(BODY, **values)
        self.start = game + 0x605950 if original else self.artifact['entry_address']
        self.reject = self.artifact['reject_address']
        for address, blob in [(self.start, BODY if original else bytes.fromhex(self.artifact['code_hex'])),
                              (self.reject, b'\xcc'), (self.stop, b'\xcc'), (self.tail, b'\xc3'), (self.predicate, b'\xc3')]:
            self.map(address, len(blob)); self.write(address, blob)
        for entry, blob in BODIES.items(): self.map(game + entry, len(blob)); self.write(game + entry, blob)
        g = getter.build(GETTER, game_base=game, code_address=values['getter_code_address'], roster_address=S,
                         storage_address=B, reject_address=game + 0x100F8000)
        self.getter_entry, self.getter_reject = g['entry_address'], g['reject_address']
        for address, blob in [(g['code_address'], bytes.fromhex(g['code_hex'])), (g['reject_address'], b'\xcc')]:
            self.map(address, len(blob)); self.write(address, blob)
        for entry in STUBS: self.map(game + entry, 1); self.write(game + entry, b'\xc3')
        for address, size in [(S - 0x80, 0x600), (B - 0x80, 0x780), (MAP - 0x80, 0x100), (ENTITIES, 0x1000),
                              (STACK, 0x10000), (CONTEXT, 0x20), (VTABLE, 0x1000), (MODE + 0xAC21C, 4),
                              (MANAGER, 0x200), (UI_MANAGER, 0x2000), (CONFIG, 0x48),
                              (DISCONNECT_CONTEXT + 0x31276, 1), (ASSOC - 0x80, 0x100)]: self.map(address, size)
        for rva, value in {0x3326468:S, 0x347CE60:NETWORK_CONTEXT, 0x3326340:MODE, 0x3326308:CONTEXT,
                           0x3326D20:MANAGER, 0x3326E68:UI_MANAGER, 0x33266A0:CONFIG, 0x346BF98:ASSOC_CONTEXT,
                           0x346D500:SPAWN_CONTEXT, 0x347CE18:DISCONNECT_CONTEXT}.items():
            self.map(game + rva, 8); self.write(game + rva, u64(value))
        for rva in (0x3483C20, 0x3483C34, 0x348452C):
            self.map(game + rva, 4); self.write(game + rva, u32(0xFFFFFFFF))
        for rva, item in dep_ev['notification_literals'].items():
            blob = bytes.fromhex(item['bytes_hex']); assert sha(blob) == item['sha256']
            self.map(game + int(rva,16), len(blob)); self.write(game + int(rva,16), blob)
        self.map(game + 0x23C6D70, 4); self.write(game + 0x23C6D70, FLOAT_ONE)
        self.write(CONTEXT + 0x10, u64(VTABLE)); self.write(CONTEXT + 0x18, u64(VTABLE))
        self.write(VTABLE + 0x480, u64(self.tail)); self.write(VTABLE + 0x720, u64(self.predicate))
        self.write(MODE + 0xAC21C, u32(mode)); self.write(DISCONNECT_CONTEXT + 0x31276, bytes([disconnected]))
        self.write(CONFIG + 8, u32(1)); self.write(CONFIG + 0x40, u32(0x17))
        for off, value in ((0x80,t),(0x84,d),(0x88,p),(0xD8,8),(0xDC,0),(0xE0,multiplier)):
            self.write(S + off, u32(value))
        self.write(S + 0xD0, u64(MAP))
        table = [(0,0xFFFFFFFF)] * 8
        for i in range(4 if original else 8):
            entity = ENTITIES + i * 0x40
            self.write(entity + 8, u32(self.keys[i])); self.write(entity + 0x10, u32(0xC0000000 + i))
            self.write(entity + 0x14, bytes([int(i < p)]))
            if i < t:
                bucket = next((self.keys[i] * multiplier + j)&7 for j in range(8) if table[(self.keys[i]*multiplier+j)&7][0]==0)
                table[bucket] = (self.keys[i],i)
            for group,(name,off,old,stride) in enumerate(LAYOUT):
                blob = u64(entity) if name=='pointer' else bytes((i*31+j*7+group*67)&255 for j in range(stride))
                self.write(self.slot(name,i),blob)
            self.write(self.slot('primary',i),u32(0x731 + i))
            self.write(self.slot('property',i),u32(ASSOC_LOOKUP_ID if associated and i==ordinal else 0x7FFF))
            self.write(self.slot('property',i)+0xC,u32(NETWORKS[i]))
        self.table = table
        for bucket,(key,value) in enumerate(table): self.write(MAP+bucket*8,u32(key)+u32(value))
        self.resource = 0x731 + ordinal
        self.setup_primary()
        self.setup_associated()
        self.setup_ui()
        self.seed(); self.outcome = None; self.before = self.snapshot()
        self.uc.hook_add(UC_HOOK_CODE, self.on_code)
        def on_read(uc,access,address,size,value,data):
            self.reads.append((address,size)); self.read_sites.append((uc.reg_read(reg('rip')),address,size))
        self.uc.hook_add(UC_HOOK_MEM_READ, on_read)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, lambda uc,access,address,size,value,data:self.writes.append((address,size)))

    def slot(self,name,ordinal):
        _,off,old,stride = next(row for row in LAYOUT if row[0]==name)
        return (S+old if self.original else B+off)+ordinal*stride

    def map(self,address,size):
        for page in range(address&~0xFFF,(address+size+0xFFF)&~0xFFF,0x1000):
            if page not in self.pages:
                self.uc.mem_map(page,0x1000); self.uc.mem_write(page,b'\xa5'*0x1000); self.pages.add(page)
    def read(self,address,size): return bytes(self.uc.mem_read(address,size))
    def write(self,address,blob): self.uc.mem_write(address,blob)
    def int32(self,address): return struct.unpack('<I',self.read(address,4))[0]
    def int64(self,address): return struct.unpack('<Q',self.read(address,8))[0]
    def snapshot(self): return {page:self.read(page,0x1000) for page in self.pages if not STACK<=page<STACK+0x10000}
    def counts(self): return [self.int32(S+off) for off in (0x80,0x84,0x88)]

    def setup_primary(self):
        # Real helpers delete owner S plus matching ID, keeping both other-ID
        # and other-owner records. Nonempty remainder avoids allocator cleanup.
        for index,(entry,base) in enumerate(PRIMARY.items()):
            table,records,items = [RESOURCE_BASE+index*0x10000+j*0x1000 for j in range(3)]
            for address,size in ((table,32),(records,16),(items,72)): self.map(address,size)
            self.write(UI_MANAGER+base+0x28,u64(table))
            self.write(UI_MANAGER+base+0x30,u32(4)); self.write(UI_MANAGER+base+0x34,u32(0)); self.write(UI_MANAGER+base+0x38,u32(1))
            self.write(UI_MANAGER+base+0x18,u64(records)); self.write(UI_MANAGER+base+0x40,bytes([self.deferred]))
            for i in range(4): self.write(table+i*8,u32(0)+u32(0xFFFFFFFF))
            self.write(table+(self.resource&3)*8,u32(self.resource)+u32(0))
            self.write(records,u64(items)+u32(3)+u32(0x72654321))
            values = [(S,self.keys[self.ordinal]),(S,self.keys[self.ordinal]+1),(S+0x10000,self.keys[self.ordinal])]
            blobs = [u64(owner)+u64(0x1234567800000000+i)+u32(key)+u32(0xABCD0000+i) for i,(owner,key) in enumerate(values)]
            for i,blob in enumerate(blobs): self.write(items+i*24,blob)
            self.primary_lists[entry]=(records,items,blobs)
            if self.ordinal<self.p:
                self.expected_changes += [(items,u64(0))] if self.deferred else [(records+8,u32(2)),(items,blobs[2])]

    def setup_associated(self):
        self.write(ASSOC+8,u32(ASSOC_ID)); self.write(ASSOC+0xC,u32(CONTROLLER_ID))
        self.write(ASSOC+0x10,u32(0x0ABC1234)); self.write(ASSOC+0x14,bytes([self.associated_flag]))
        # Both captured getters resolve a real nonzero map ordinal; these maps
        # and memory are supplied fixtures, not claimed runtime allocations.
        for offset,table,key in [(0xF22EC8,ASSOC_MAP,ASSOC_LOOKUP_ID),(0xF1AEB0,ASSOC_MAP2,ASSOC_ID)]:
            self.map(ASSOC_CONTEXT+offset,0x18); self.map(table,32)
            self.write(ASSOC_CONTEXT+offset,u64(table)); self.write(ASSOC_CONTEXT+offset+8,u32(4))
            self.write(ASSOC_CONTEXT+offset+12,u32(0)); self.write(ASSOC_CONTEXT+offset+16,u32(1))
            for i in range(4): self.write(table+i*8,u32(0)+u32(0xFFFFFFFF))
            self.write(table+(key&3)*8,u32(key)+u32(2))
        self.map(MANAGER_MAP,32)
        self.write(MANAGER+0xF8,u64(MANAGER_MAP)); self.write(MANAGER+0x100,u32(4))
        self.write(MANAGER+0x104,u32(0)); self.write(MANAGER+0x108,u32(1))
        for i in range(4): self.write(MANAGER_MAP+i*8,u32(0)+u32(0xFFFFFFFF))
        self.write(MANAGER_MAP+(ASSOC_ID&3)*8,u32(ASSOC_ID)+u32(2))
        self.record = MANAGER+0x53DD48+2*0x1238
        self.map(self.record,0x1238)
        self.loop_id = 0xAC17
        loop_entities = ENTITIES+0x500
        self.write(loop_entities+8,u32(self.loop_id)); self.write(loop_entities+0x14,b'\1')
        self.write(loop_entities+0x40+8,u32(self.loop_id+1)); self.write(loop_entities+0x40+0x14,b'\0')
        # Same associated, null, flag0, mismatched owner type, eligible one.
        pointers = [ASSOC if self.associated else 0,0,loop_entities+0x40,loop_entities,loop_entities]
        self.write(MANAGER+0x6C,u32(len(pointers) if self.manager_loop else 0))
        for i,pointer in enumerate(pointers):
            self.write(MANAGER+0x110+i*8,u64(pointer))
            location=MANAGER+0x5478A4+i*0x78; self.map(location,4)
            self.write(location,u32(0xC0000000+self.ordinal+(i==3)))

    def setup_ui(self):
        self.write(UI_MANAGER+0x15C0,u32(3 if self.ui else 0))
        for i,tag in enumerate((0x3E,0x3D,0x3E)):
            address=UI+i*0x100000; self.map(address+0x518B0,0x18)
            self.write(UI_MANAGER+0x15C8+i*16,u64(address)); self.write(UI_MANAGER+0x15D0+i*16,u32(tag))
            self.write(address+0x518B0,struct.pack('<2f',2.0+i,3.0+i)); self.write(address+0x518C4,u32(7+i))

    def seed(self):
        for name,value in SEEDS.items(): self.uc.reg_write(reg(name),value)
        for i in range(6,16): self.uc.reg_write(reg('xmm'+str(i)),(0x0102030405060708+i)*(1+(1<<64)))
        for name,value in dict(rsp=RSP,rcx=0xDEAD0000,rdx=self.target,r8=0x8181818181818181,r9=0x9191919191919191).items():
            self.uc.reg_write(reg(name),value)
        self.write(RSP,u64(self.stop))

    def stub(self,role):
        uc=self.uc; rsp=uc.reg_read(reg('rsp'))
        assert rsp%16==8 and STACK<=rsp<STACK+0x10000
        assert self.counts()==[self.t,self.d,self.p]
        args={name:uc.reg_read(reg(name)) for name in ('rcx','rdx','r8','r9')}
        event={'kind':'contract_stub','role':role,'args':args,'counts':self.counts()}
        key=self.keys[self.ordinal]
        returns={}
        if role=='network': assert args['rcx']==NETWORK_CONTEXT and (args['rdx']&0xFFFFFFFF)==NETWORKS[self.ordinal]
        elif role=='disconnected':
            assert args['rcx']==self.target and self.read(args['rdx'],13)==b'disconnected\0'
            assert args['r8']&255==1 and args['r9']==0
        elif role=='controller_check':
            assert args['rcx']==CONTROLLER_ID
            returns={'rax':int(self.controller),'rcx':0x43210001}
        elif role=='associated_controller': assert args['rcx']==0x43210001 and args['rdx']==CONTROLLER_ID and args['r8']==0
        elif role in ('record_reset','record_query','record_flag'):
            assert args['rcx']==self.record
            if role=='record_reset': assert args['rdx']==0
            if role=='record_query': returns={'rax':int(self.query)}
            if role=='record_flag': assert args['rdx']==1 and uc.reg_read(reg('xmm2'))==0
        elif role=='link_old': assert args['rdx']==key and args['r8']==ASSOC_ID
        elif role=='relationship_old': assert args['rdx']==ASSOC_ID and args['r8']==key
        elif role=='create_output':
            assert args['rcx']==SPAWN_CONTEXT and args['r8']==ASSOC_ID and args['r9']==CONTROLLER_ID
            out=args['rdx']; assert STACK<=out<STACK+0x10000
            for off,value,size in [(0x28,1,4),(0x30,0,4),(0x38,1,1),(0x40,0,4),(0x48,0,4),(0x50,0,4),(0x58,0,1)]:
                assert int.from_bytes(self.read(rsp+off,size),'little')==value,(hex(off),self.read(rsp+off,size).hex())
            self.write(out,u32(CREATED_ID)); event['output_id']=CREATED_ID
        elif role=='link_output': assert args['rdx']==key and args['r8']==CREATED_ID
        elif role=='relationship_output': assert args['rdx']==CREATED_ID and args['r8']==key
        elif role=='queue_entity': assert args['rcx']==ASSOC_CONTEXT and args['rdx'] in (ASSOC_ID,self.loop_id)
        elif role=='ui':
            index=0 if args['rcx']==UI else 2
            assert args['rcx']==UI+index*0x100000 and args['rdx']==args['rcx']+0x3A538
            assert uc.reg_read(reg('xmm2'))&0xFFFFFFFF==int.from_bytes(struct.pack('<f',2.0+index),'little')
            assert uc.reg_read(reg('xmm3'))&0xFFFFFFFF==int.from_bytes(struct.pack('<f',3.0+index),'little')
            expected=(self.d-1)&0xFFFFFFFF if self.original else self.d-int(self.ordinal<self.d)
            assert self.int32(rsp+0x28)==7+index and self.int32(rsp+0x30)==expected
            assert self.int32(rsp+0x38)==0x3F800000 and self.int32(rsp+0x40)==0x17
            event['remaining_dense']=self.int32(rsp+0x30)
        elif role=='count':
            expected=(self.d-1)&0xFFFFFFFF if self.original else self.d-int(self.ordinal<self.d)
            assert args['rdx']==expected; event['remaining_dense']=args['rdx']
        elif role=='tail':
            assert self.read(args['rcx'],13)==b'player_count\0' and args['rdx']==self.d
            assert rsp==RSP; event['pre_remove_dense']=args['rdx']
        else: raise AssertionError(role)
        self.events.append(event)
        self.write(rsp+8,b'\xc7'*32)
        for i,name in enumerate(('rax','rcx','rdx','r8','r9','r10','r11')): uc.reg_write(reg(name),0xCDCD000000000000+i)
        for i in range(6): uc.reg_write(reg('xmm'+str(i)),(0xAABBCCDDEEFF0000+i)*(1+(1<<64)))
        uc.reg_write(reg('rax'),0)
        for name,value in returns.items(): uc.reg_write(reg(name),value)

    def on_code(self,uc,address,size,data):
        self.trace.append(address)
        if address in (self.stop,self.reject,self.getter_reject):
            self.outcome='return' if address==self.stop else 'reject'; uc.emu_stop(); return
        entry=address-self.game
        if entry in BODIES or address==self.getter_entry or address in self.extra_helpers:
            event={'kind':'actual_helper','entry':self.extra_helpers.get(address,hex(entry)),'counts':self.counts()}
            if entry in PRIMARY:
                assert uc.reg_read(reg('ecx'))==self.resource and uc.reg_read(reg('rdx'))==S and uc.reg_read(reg('r8d'))==self.keys[self.ordinal]
                event.update(resource=self.resource,owner=S,entity_id=self.keys[self.ordinal])
            if entry==0xFD9C80: assert uc.reg_read(reg('ecx'))==(ASSOC_LOOKUP_ID if self.associated else 0x7FFF)
            if entry==0xFD9D40: assert uc.reg_read(reg('ecx'))==ASSOC_ID
            self.events.append(event)
        role='tail' if address==self.tail else 'controller_check' if address==self.predicate else STUBS.get(entry)
        if role: self.stub(role)

    def run(self,name,entry=None,component='departure'):
        self.uc.emu_start(self.start if entry is None else entry,0,count=50000)
        assert self.outcome is not None,'bounded run did not finish'
        self.after=self.snapshot()
        record=dict(name=name,component=component,original=self.original,t=self.t,d=self.d,p=self.p,ordinal=self.ordinal,
                    entry_rva=hex((self.start if entry is None else entry)-self.game),
                    associated=self.associated,associated_flag=self.associated_flag,controller=self.controller,query=self.query,
                    deferred=self.deferred,mode=self.mode,outcome=self.outcome,instructions=len(self.trace),
                    actual_helper_entries=[event['entry'] for event in self.events if event['kind']=='actual_helper'],
                    contract_events=[event for event in self.events if event['kind']=='contract_stub'])
        RUNS.append(record)
        return self


class DepartureTests(unittest.TestCase):
    def abi(self,f,rejected=False):
        self.assertEqual(f.uc.reg_read(reg('rsp')),RSP if rejected else RSP+8)
        for name,value in SEEDS.items(): self.assertEqual(f.uc.reg_read(reg(name)),value,name)
        for i in range(6,16): self.assertEqual(f.uc.reg_read(reg('xmm'+str(i))),(0x0102030405060708+i)*(1+(1<<64)))

    def success(self,f):
        self.assertEqual(f.outcome,'return'); self.abi(f)
        self.assertEqual(f.counts(),[f.t,f.d,f.p])
        self.assertEqual(f.after,changed_pages(f.before,f.expected_changes))
        roles=[event['role'] for event in f.events if event['kind']=='contract_stub']
        expected=[]
        if f.ordinal<f.p and f.disconnected: expected.append('disconnected')
        expected.append('network')
        full=f.associated and f.associated_flag and f.mode==4 and f.ordinal>=f.p and f.controller
        if f.associated and f.associated_flag and f.mode==4 and f.ordinal>=f.p: expected.append('controller_check')
        if full:
            expected+=['associated_controller','record_reset','record_query']
            if f.query: expected.append('record_flag')
            expected+=['link_old','relationship_old','create_output','link_output','relationship_output']
        if f.associated and f.associated_flag: expected.append('queue_entity')
        if f.manager_loop: expected.append('queue_entity')
        if f.ui and f.mode==4: expected+=['ui','ui']
        expected+=['count','tail']; self.assertEqual(roles,expected)
        queue=[event['args']['rdx'] for event in f.events if event.get('role')=='queue_entity']
        self.assertEqual(queue,([ASSOC_ID] if f.associated and f.associated_flag else [])+([f.loop_id] if f.manager_loop else []))
        actual=[event['entry'] for event in f.events if event['kind']=='actual_helper']
        self.assertEqual(actual.count(hex(0x606820 if f.original else f.getter_entry-f.game)),1)
        for entry in PRIMARY: self.assertEqual(actual.count(hex(entry)),int(f.ordinal<f.p))
        self.assertEqual(actual.count('0xfd9c80'),1)
        self.assertEqual(actual.count('0xfd9d40'),int(full))
        if f.ordinal<f.p:
            self.assertEqual(f.reads.count((f.slot('primary',f.ordinal),4)),3)
            self.assertGreaterEqual(f.reads.count((f.slot('pointer',f.ordinal),8)),2)
            primary_positions=[i for i,event in enumerate(f.events) if event.get('entry') in {hex(entry) for entry in PRIMARY}]
            self.assertEqual([f.events[i]['entry'] for i in primary_positions],[hex(entry) for entry in PRIMARY])
            self.assertLess(next(i for i,e in enumerate(f.events) if e.get('role')=='network'),primary_positions[0])
            self.assertLess(primary_positions[-1],next(i for i,e in enumerate(f.events) if e.get('entry')=='0xfd9c80'))
        self.assertIn((f.slot('property',f.ordinal),4),f.reads)
        self.assertIn((f.slot('property',f.ordinal)+0xC,4),f.reads)
        if not f.original:
            self.assertFalse(any(S+0xE8<=address<S+0x428 for address,size in f.reads),'candidate read old inline array')
            for patch in f.artifact['array_patches']:
                old=patch['original_rva']
                expected_read=old==0x605A5B or f.ordinal<f.p or old in (0x605A0D,0x605B96)
                sites=[row for row in f.read_sites if patch['emitted_address']<=row[0]<patch['emitted_address']+len(bytes.fromhex(patch['replacement_hex']))]
                self.assertEqual(len(sites),int(expected_read),hex(old))
                if sites:
                    name='pointer' if old in (0x605A0D,0x605B96) else 'property' if old==0x605A5B else 'primary'
                    self.assertEqual(sites[0][1:],(f.slot(name,f.ordinal),8 if name=='pointer' else 4))
        # Every nonstack emulated store must belong to real owner-list edits.
        allowed=[(address,address+len(blob)) for address,blob in f.expected_changes]
        self.assertTrue(all(STACK<=address and address+size<=STACK+0x10000 or
                            any(lo<=address and address+size<=hi for lo,hi in allowed) for address,size in f.writes))

    def test_01_fixed_source_decode_and_layout(self):
        self.assertEqual(native.load_source(RESEARCH/'roster_departure_native_evidence.json'),BODY)
        artifact=native.build(BODY,**params()); blob=bytes.fromhex(artifact['code_hex'])
        self.assertEqual(sha(blob),artifact['code_sha256']); decode(blob,artifact['entry_address'])
        with self.assertRaises(ValueError): native.build(bytes([BODY[0]^1])+BODY[1:],**params())

    def test_02_original_four_slot_full_path_pairs(self):
        for options in [dict(ordinal=1,p=2,associated=True,deferred=False),
                        dict(ordinal=1,p=2,associated=False,deferred=True),
                        dict(ordinal=2,p=1,associated=True,query=True),
                        dict(ordinal=2,p=1,associated=True,query=False),
                        dict(ordinal=2,p=1,associated=True,controller=False),
                        dict(ordinal=2,p=1,associated=True,associated_flag=False),
                        dict(ordinal=1,p=2,associated=True,mode=3,disconnected=False)]:
            original=Fixture(t=4,d=4,original=True,**options).run('original_dense_baseline')
            candidate=Fixture(t=4,d=4,**options).run('candidate_dense_pair')
            self.success(original); self.success(candidate)
            def semantic(f):
                return [(event['role'],event.get('remaining_dense'),event.get('pre_remove_dense'),
                         event['args']['rdx'] if event['role']=='queue_entity' else None)
                        for event in f.events if event['kind']=='contract_stub']
            self.assertEqual(semantic(original),semantic(candidate))
            for entry in PRIMARY:
                rec,items,_=original.primary_lists[entry]
                self.assertEqual(original.read(rec,16),candidate.read(rec,16)); self.assertEqual(original.read(items,72),candidate.read(items,72))

    def test_03_eight_slot_dense_and_pending_count_semantics(self):
        for t in range(5,9):
            self.success(Fixture(t=t,d=3,p=1,ordinal=t-1,associated=True).run('pending_five_through_eight'))
        self.success(Fixture(t=8,d=0,p=0,ordinal=7,associated=False).run('pending_zero_dense_no_underflow'))
        self.success(Fixture(t=8,d=8,p=8,ordinal=7,associated=True,deferred=True,
                             game=0x7FF800000000,multiplier=3).run('slot_seven_primary_second_aslr'))
        self.success(Fixture(t=8,d=8,p=0,ordinal=7,associated=True).run('slot_seven_full_associated'))

    def test_04_minimal_branch_omissions(self):
        self.success(Fixture(t=1,d=1,p=0,ordinal=0,associated=False,ui=False,manager_loop=False).run('minimal_no_associated_ui_or_manager'))

    def test_05_preflight_rejects_before_any_external_effect(self):
        cases=[('binding',1),('null',2),('tracked_zero',3),('tracked_nine',3),('dense_order',4),('prefix_order',4),
               ('map_capacity',5),('empty_id',6),('invalid_id',6),('missing_full',7),('missing_empty',7),
               ('ordinal_untracked',8),('pointer_binding',9),('prefix_flag_clear',10),('nonprefix_flag_set',10)]
        for name,reason in cases:
            f=Fixture(t=3 if name=='missing_empty' else 8, d=2 if name=='missing_empty' else 6,p=2,ordinal=1)
            if name=='binding': f.write(f.game+0x3326468,u64(0x40000000))
            elif name=='null': f.uc.reg_write(reg('rdx'),0)
            elif name=='tracked_zero': f.write(S+0x80,u32(0))
            elif name=='tracked_nine': f.write(S+0x80,u32(9))
            elif name=='dense_order': f.write(S+0x84,u32(9))
            elif name=='prefix_order': f.write(S+0x88,u32(7))
            elif name=='map_capacity': f.write(S+0xD8,u32(4))
            elif name=='empty_id': f.write(f.target+8,u32(0))
            elif name=='invalid_id': f.write(f.target+8,u32(0xFFFFFFFF))
            elif name in ('missing_full','missing_empty'): f.write(f.target+8,u32(75))
            elif name=='ordinal_untracked':
                bucket=next(i for i,item in enumerate(f.table) if item[0]==f.keys[f.ordinal])
                f.write(MAP+bucket*8+4,u32(8))
            elif name=='pointer_binding': f.write(f.slot('pointer',f.ordinal),u64(f.target+0x40))
            elif name=='prefix_flag_clear': f.write(f.target+0x14,b'\0')
            elif name=='nonprefix_flag_set': f.write(S+0x88,u32(0))
            expected_args={r:f.uc.reg_read(reg(r)) for r in ('rcx','rdx','r8','r9')}
            f.before=f.snapshot();f.run('guard_'+name)
            self.assertEqual(f.outcome,'reject'); self.assertEqual(f.uc.reg_read(reg('r10d')),reason)
            self.abi(f,True); self.assertEqual(f.events,[]); self.assertEqual(f.after,f.before)
            for r,value in expected_args.items(): self.assertEqual(f.uc.reg_read(reg(r)),value,r)
            self.assertTrue(all(STACK<=address and address+size<=STACK+0x10000 for address,size in f.writes))

    def test_06_pending_departure_then_real_map_delete_and_move(self):
        f=Fixture(t=8,d=3,p=1,ordinal=4,associated=True).run('pending_departure_before_removal')
        self.success(f)
        prediction=next(event['remaining_dense'] for event in f.events if event.get('role')=='count')
        self.assertEqual(prediction,3)
        rs=remove.load_sources(RESEARCH/'roster_remove_native_evidence.json')
        removal=remove.build(rs['registered'],kind='registered',game_base=GAME,code_address=GAME+0x100C0000,
                             roster_address=S,storage_address=B,move_code_address=GAME+0x10040000,reject_address=GAME+0x100C8000)
        mover=move.build(move.load_source(RESEARCH/'roster_move_native_evidence.json'),game_base=GAME,
                         code_address=GAME+0x10040000,roster_address=S,storage_address=B,reject_address=GAME+0x10048000)
        deletion=bytes.fromhex(remove_ev['bodies']['0x172f8a0']['bytes_hex'])
        self.assertEqual(sha(deletion),'d58cc9dbb3c79864b4ca0692be1fcf3a31ec267c059f7c904063aed53d05ec4f')
        for address,blob in [(removal['entry_address'],bytes.fromhex(removal['code_hex'])),(removal['reject_address'],b'\xcc'),
                              (mover['entry_address'],bytes.fromhex(mover['code_hex'])),(mover['reject_address'],b'\xcc'),
                              (GAME+0x172F8A0,deletion)]: f.map(address,len(blob)); f.write(address,blob)
        f.extra_helpers={GAME+0x172F8A0:'0x172f8a0',mover['entry_address']:'candidate_mover'}
        actual=[]
        f.uc.hook_add(UC_HOOK_CODE,lambda uc,address,size,data: actual.append(address)
                      if address in (GAME+0x172F8A0,mover['entry_address']) else None)
        before_records={(name,i):f.read(f.slot(name,i),stride) for name,off,old,stride in LAYOUT for i in range(8)}
        f.events=[];f.trace=[];f.reads=[];f.read_sites=[];f.writes=[];f.outcome=None
        f.seed();f.uc.reg_write(reg('rcx'),f.target);f.before=f.snapshot()
        f.run('actual_remove_after_departure',removal['entry_address'],'remove')
        self.assertEqual(f.outcome,'return');self.abi(f);self.assertEqual(f.counts(),[7,prediction,1])
        self.assertEqual(actual,[GAME+0x172F8A0,mover['entry_address']])
        self.assertEqual([event['entry'] for event in f.events],['0x172f8a0','candidate_mover'])
        active=f.keys[:4]+[f.keys[7]]+f.keys[5:7]
        pairs=[struct.unpack('<II',f.read(MAP+i*8,8)) for i in range(8)]
        self.assertEqual({key:ordinal for key,ordinal in pairs if key},{key:i for i,key in enumerate(active)})
        for key,ordinal in {key:i for i,key in enumerate(active)}.items():
            for probe in range(8):
                k,v=pairs[(key+probe)&7]
                self.assertNotEqual(k,0)
                if k==key: self.assertEqual(v,ordinal);break
            else: self.fail('unprobeable surviving key')
        changes=[(S+0x80,u32(7)),(MAP,f.read(MAP,64))]
        for name,off,old,stride in LAYOUT: changes.append((f.slot(name,4),before_records[name,7]))
        self.assertEqual(f.after,changed_pages(f.before,changes))
        # The actual candidate getter must follow the moved ID to nonzero slot4.
        f.t=7;f.ordinal=4;f.events=[];f.trace=[];f.reads=[];f.read_sites=[];f.writes=[];f.outcome=None
        f.seed();f.uc.reg_write(reg('edx'),f.keys[7]);f.before=f.snapshot()
        f.run('getter_after_pending_tail_move',f.getter_entry,'getter')
        self.assertEqual(f.outcome,'return');self.abi(f);self.assertEqual(f.after,f.before)
        self.assertEqual(f.uc.reg_read(reg('rax')),NETWORKS[7]);self.assertIn((B+0x580+4*0x20+0xC,4),f.reads)
        f.events=[];f.trace=[];f.reads=[];f.read_sites=[];f.writes=[];f.outcome=None
        f.seed();f.uc.reg_write(reg('edx'),f.keys[4]);f.before=f.snapshot()
        f.run('deleted_id_missing_after_departure',f.getter_entry,'getter')
        self.assertEqual(f.outcome,'return');self.abi(f);self.assertEqual(f.after,f.before)
        self.assertEqual(f.uc.reg_read(reg('rax')),0xFFFFFFFF)

    def test_07_addresses_rel32_and_thirteen_function_count_bundle(self):
        for update in [dict(game_base=GAME+1),dict(code_address=GAME+0x605950),dict(storage_address=B+1),
                       dict(storage_address=S+0x100),dict(reject_address=B+0x500),
                       dict(getter_code_address=params()['code_address'])]:
            values=params();values.update(update)
            with self.assertRaises(ValueError): native.build(BODY,**values)
        artifact=native.build(BODY,**params())
        jumps=[row for row in decode(bytes.fromhex(artifact['code_hex']),artifact['code_address'])
               if row.mnemonic=='jmp' and row.operands[0].type==capstone.x86.X86_OP_IMM and row.operands[0].imm==artifact['reject_address']]
        lo=max(row.address+row.size-(1<<31) for row in jumps)
        hi=min(row.address+row.size+(1<<31)-1 for row in jumps)
        for address in (lo,hi):
            f=Fixture(args={'reject_address':address}); f.write(f.game+0x3326468,u64(0x40000000));f.before=f.snapshot()
            f.run('reject_rel32_boundary');self.assertEqual(f.outcome,'reject');self.abi(f,True)
            self.assertEqual(f.after,f.before);self.assertEqual(f.events,[])
        for address in (lo-1,hi+1):
            values=params();values['reject_address']=address
            with self.assertRaises(ValueError): native.build(BODY,**values)
        addresses=json.loads(ADDRESSES.read_bytes())
        sources=[BODY,GETTER,getter.classify.load_sources(RESEARCH/'roster_classify_native_evidence.json'),
                 remove.load_sources(RESEARCH/'roster_remove_native_evidence.json'),
                 remove.insert.load_sources(RESEARCH/'roster_insert_native_evidence.json'),
                 move.load_source(RESEARCH/'roster_move_native_evidence.json'),
                 remove.insert.base_bundle.pair.producer.load_source(RESEARCH/'roster_property_producer_native_evidence.json'),
                 remove.insert.base_bundle.pair.receiver.load_source(RESEARCH/'roster_property_receive_evidence.json')]
        counts=native.player_count.load_sources(RESEARCH/'roster_player_count_native_evidence.json',RESEARCH/'roster_departure_callee_evidence.json')
        kwargs=dict(addresses,player_count_context_source=counts['context'],player_count_filter_source=counts['filter'])
        result=native.build_bundle(*sources,**kwargs)
        self.assertEqual(result['departure']['storage_address'],B);self.assertEqual(result['departure']['roster_address'],S)
        calls=[r for r in result['departure']['relocations'] if r.get('getter_callsite_replaced')]
        self.assertEqual(len(calls),1);self.assertEqual(calls[0]['target_address'],addresses['getter_code_address'])
        self.assertEqual(result['player_count']['patches'][0]['replacement_hex'],'b808000000')
        for field,value in [('departure_code_address',addresses['getter_code_address']),
                            ('departure_reject_address',addresses['receiver_reject_address']),
                            ('player_count_trampoline_address',addresses['departure_code_address']),
                            ('player_count_trampoline_address',addresses['classify_code_addresses']['enter'])]:
            bad=dict(kwargs);bad[field]=value
            with self.assertRaises(ValueError): native.build_bundle(*sources,**bad)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DepartureTests))
    sources=('roster_departure','roster_getter','roster_classify','roster_remove','roster_insert','roster_move',
             'roster_bundle','roster_property_pair','roster_producer','roster_receiver','player_count')
    nested={}
    for run in RUNS:
        for entry in run['actual_helper_entries']:
            if entry!=run['entry_rva']: nested[entry]=nested.get(entry,0)+1
    report=dict(status='passed' if result.wasSuccessful() else 'failed',test_methods_run=result.testsRun,
                failure_count=len(result.failures),error_count=len(result.errors),
                failures=[{'test':str(test),'traceback':tb} for test,tb in result.failures],
                errors=[{'test':str(test),'traceback':tb} for test,tb in result.errors],
                source_sha256={f'Native/{name}.py':sha((ROOT/f'Native/{name}.py').read_bytes()) for name in sources},
                test_sha256=sha(Path(__file__).read_bytes()),evidence_sha256=EVIDENCE_PINS,
                test_dependency_sha256={str(ADDRESSES.relative_to(ROOT)):ADDRESSES_SHA},
                executed_saved_body_sha256={hex(entry):sha(blob) for entry,blob in BODIES.items()},
                python_version=sys.version,unicorn_version=unicorn.__version__,capstone_version=capstone.__version__,
                fixture_synthetic=True,game_process_accessed=False,host_native_code_executed=False,installable=False,
                emulator_runs=RUNS,
                execution_counts={'total':len(RUNS),'candidate':sum(not run['original'] for run in RUNS),
                                  'original_departure_baseline':sum(run['original'] for run in RUNS),
                                  'candidate_departure_complete_return':sum(not run['original'] and run['component']=='departure' and run['outcome']=='return' for run in RUNS),
                                  'candidate_departure_preflight_rejection':sum(run['component']=='departure' and run['outcome']=='reject' for run in RUNS),
                                  'candidate_remove_chain':sum(run['component']=='remove' for run in RUNS),
                                  'candidate_getter_chain':sum(run['component']=='getter' for run in RUNS)},
                nested_helper_entries_not_added_to_top_level_total=nested,
                fixed_float_literal={'rva':'0x23c6d70','bytes_hex':FLOAT_ONE.hex(),'evidence':'roster_departure_aux_evidence.json'},
                contracts={
                    'shared_state':'Binding S, map, P/D/T, target identity and all array records remain stable throughout callbacks; true primary helpers only edit separate synthetic owner registries',
                    'three_primary_helpers':'Actual captured B0B020/B11C20/B0F820 each see resource from target primary, RDX original S, R8D target ID; three 24B owners distinguish owner and ID; verify immediate swap-last deletion or deferred owner-null; nonempty registry only',
                    'associated_lookups':'Actual captured FD9C80 (7FFF direct-null or valid found) and FD9D40 valid found; supplied context maps resolve nonzero ordinal2. FD9D40 preserves ECX naturally for subsequent create-output R8D',
                    'disconnected':'13462C0 stub checks original target pointer, exact disconnected literal, R8B1/R9D0; no game notification implementation',
                    'controller_virtual':'context.vtable+720 stub checks ECX controller ID, returns AL eligibility and a specified volatile RCX consumed unchanged by 838680',
                    'associated_record_calls':'838680/A747D0/A74700/A77800 stubs check controller ID/zero, manager record address, reset EDX0, query AL, conditional flag EDX1 and XMM2 zero',
                    'associated_relationships':'135A4A0/BE21A0 and 135AB10/BE16F0 stubs check exact target/associated/output ID orientation and order',
                    'create_output':'13BFB40 stub checks RCX context, stack out-DWORD pointer, preserved associated ID R8D, resolved controller R9D, all seven stack arguments; writes only that DWORD with synthetic created ID',
                    'manager_queue':'FDC310 stub checks context and associated or eligible-loop entity ID; fixtures include same associated pointer, null, unset flag, mismatched type and one eligible record; real queue/reentrancy not emulated',
                    'notifications':'139C360 network DWORD, two eligible 94C9C0 UI callbacks, 60C2A0 EDX prediction, tail exact player_count literal/current pre-remove D; precise order checked; callbacks do not implement actual notifications or assets',
                    'stub_abi':'Each contract stub validates call-entry RSP%16=8, writes 32-byte shadow space, clobbers volatile GPR/XMM0..5 and preserves nonvolatile state; all return effects explicitly listed',
                    'remove_chain':'Synthetic harness invokes departure then registered remove with actual captured map-delete and candidate mover; four full records move slot7 to slot4, map remains bijective/probeable, true getter follows moved ID and deleted ID misses',
                    'bundle':'Thirteen roster function artifacts plus player-count patch plan built and checked for common binding/getter target and cross-region overlap; other twelve functions and count-filter suite are not rerun here'},
                limits=[
                    'Finite complete-body cases do not prove every engine state, callback failure, associated resource lifetime or caller reachability',
                    'Stable binding/map/count/array state is a supplied precondition; no reentrant callback, state-change recovery or rollback is proved',
                    'Primary helper registry-empty cleanup, allocator callback and map-key deletion are outside these nonempty owner-list cases',
                    'FD9C80 and FD9D40 arbitrary malformed or missing-map paths are not generalized as safe; only proven sentinel-null and supplied valid hits are exercised',
                    'Associated controller/resource/link/creation/queue operations use explicit caller contracts, including a successful synthetic output ID, not real resource or notification implementations',
                    'Remaining-D prediction is a new candidate policy; preserved tail reads pre-removal D under stable state. UI/count consumers are stubs; zero-to-one clamp and named resources above four are not resolved',
                    'The departure-remove sequence is a synthetic harness, not execution of outer FDC820, actual hooks or production caller synchronization',
                    'The separate count-plan build does not execute full 94C9C0 context or connect all notification callbacks end to end',
                    'No native executor, executable allocation, unwind, installation, game process, runtime asset validation or multiplayer acceptance'])
    out=ROOT/'verification/native_roster_departure_tests.json'
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],methods=result.testsRun,executions=len(RUNS),failures=len(result.failures),errors=len(result.errors))))
    raise SystemExit(0 if result.wasSuccessful() else 1)
