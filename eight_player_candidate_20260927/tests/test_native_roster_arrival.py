"""Complete 6054F0 state update in synthetic Unicorn RAM, never live arrival.

The saved body and candidate run with captured FD9AF0. Opaque interface/color/
notification/cookie calls use explicit caller contracts. The filename follows
the research artifact name; no test claims this function appends a player.
"""
from __future__ import annotations
import hashlib, importlib.util, json, struct, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RESEARCH=ROOT.parent/'five_player_feasibility_20260927'
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
INPUT,FLAGOBJ,PUBLISH,ACTIVE,DIRTY=0x18201000000,0x18202000000,0x18203000000,0x18204000000,0x18205000000
CONTEXT,CONTEXT_MAP=0x18206000000,0x18208000000
ENGINE,VTA,VTB,VTF,VIRTUAL_CONTEXT,MATCH_OBJECT=0x18209000000,0x18209001000,0x18209002000,0x18209003000,0x18209004000,0x18209005000
COLOR_OBJECT,COLOR_TABLE,COLOR_CONTEXT=0x1820A000000,0x1820A001000,0x1820A002000
MODE,ASSOCIATED,UI_MANAGER,UI,CONFIG=0x1820B000000,0x1820C000000,0x1820D000000,0x1820E000000,0x1820F000000
STACK,RSP=0x182F0000000,0x182F0008008
COOKIE=0x12345678ABCDEF00
MISSING=0xE0012345
SEEDS={name:0xABCDEF0100000000+i for i,name in enumerate(('rbx','rbp','rsi','rdi','r12','r13','r14','r15'))}
LAYOUT=[('pointer',0,0xE8,8),('primary',0x40,0x108,0x70),('aux',0x3C0,0x2C8,0x38),('property',0x580,0x3A8,0x20)]
ARRAY_SITES={0x6055BB,0x6055CD,0x60561F,0x605626,0x605665,0x605684,0x605691,0x6056A6,0x6056B8,
             0x6056C8,0x6056D6,0x6056E6,0x6056F3,0x605700,0x605709,0x605758,0x605760,0x605801,0x60583C}
EVIDENCE=RESEARCH/'roster_arrival_native_evidence.json'
EVIDENCE_SHA='c3073ba7658599bc662d980397f21bf7a003f56a2b821cdcf4c2341fe05a2e64'
ADDRESSES=ROOT/'verification/native_roster_arrival_addresses_synthetic.json'
ADDRESSES_SHA='e2ca74722a5d6eed3d2ede6eebd1b7130a2a931e9316a92333f170559fc552a6'
SAMPLE=ROOT/'verification/native_roster_arrival_bundle_synthetic.json'
SAMPLE_SHA='a9268253612ad82778491308acec824e83a27afb1f9d19313994657f3dc248e0'
assert sha(ADDRESSES.read_bytes())==ADDRESSES_SHA and sha(SAMPLE.read_bytes())==SAMPLE_SHA
RUNS=[]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


native=load('arrival_under_test',ROOT/'Native/roster_arrival.py')
raw=EVIDENCE.read_bytes();assert sha(raw)==EVIDENCE_SHA
ev=json.loads(raw)
BODY=bytes.fromhex(ev['bodies']['0x6054f0']['bytes_hex'])
LEAF=bytes.fromhex(ev['bodies']['0xfd9af0']['bytes_hex'])
LITERALS={int(key,16):bytes.fromhex(item['bytes_hex']) for key,item in ev['readonly_literals'].items()}
assert len(BODY)==1111 and sha(BODY)=='6ad21683150fa35285c490fb75b00d8f0af68ab36dad70cbced0bccfc745288a'
assert len(LEAF)==174 and sha(LEAF)=='7fa3870d13305c77997147167ccca1f07b199c5011883b9d8442f31e831393fc'


def params(game=GAME):
    return dict(game_base=game,code_address=game+0x10600000,roster_address=S,storage_address=B,reject_address=game+0x10608000)


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
    def __init__(self,*,original=False,game=GAME,t=8,d=8,p=2,ordinal=0,context_flag=True,entity_flag=True,
                 eligibility=True,active='distinct',blocker=None,property_bit=True,converted=True,
                 mode=4,associated_match=True,associated_flag=True,color=True,ui=True,network=None,
                 config=True,multiplier=3,arguments=None):
        self.original,self.game,self.t,self.d,self.p,self.ordinal=original,game,t,d,p,ordinal
        self.context_flag,self.entity_flag,self.eligibility=context_flag,entity_flag,eligibility
        self.active,self.blocker,self.property_bit,self.converted=active,blocker,property_bit,converted
        self.mode,self.associated_match,self.associated_flag=mode,associated_match,associated_flag
        self.color,self.ui,self.config=color,ui,config
        self.network=ordinal if network is None else network
        self.keys=[11+8*i for i in range(8)];self.target=ENTITIES+ordinal*0x40
        self.uc=Uc(UC_ARCH_X86,UC_MODE_64);self.pages=set()
        self.events=[];self.trace=[];self.reads=[];self.writes=[];self.outcome=None
        self.stop,self.va,self.vb,self.vcolor,self.vevent=[game+0x10700000+i*0x10000 for i in range(5)]
        values=params(game);values.update(arguments or {});self.artifact=native.build(BODY,**values)
        self.start=game+0x6054F0 if original else self.artifact['entry_address'];self.reject=self.artifact['reject_address']
        for address,blob in [(self.start,BODY if original else bytes.fromhex(self.artifact['code_hex'])),
                              (game+0xFD9AF0,LEAF),(self.stop,b'\xcc'),(self.reject,b'\xcc'),
                              (self.va,b'\xc3'),(self.vb,b'\xc3'),(self.vcolor,b'\xc3'),(self.vevent,b'\xc3'),
                              (game+0x94C9C0,b'\xc3'),(game+0x60C2A0,b'\xc3'),(game+0x2088770,b'\xc3')]:
            self.map(address,len(blob));self.write(address,blob)
        for address,size in [(S-0x80,0x600),(B-0x80,0x780),(MAP,64),(ENTITIES,0x1000),(STACK,0x10000),
                              (INPUT,0x50),(FLAGOBJ+0x624,1),(PUBLISH+0x3EF280,8),(ACTIVE+0xB398,0x18),(DIRTY,1),
                              (CONTEXT+0xF1AEB0,0x18),(CONTEXT+0xF32F28,0x80),(CONTEXT_MAP,32),
                              (ENGINE,0x50),(VTA,0x10),(VTB+0x160,8),(VTF+0x480,8),
                              (COLOR_OBJECT,0x18),(COLOR_TABLE,8),(MODE+0xAC21C,4),
                              (ASSOCIATED,3*0x1690),(ASSOCIATED+0x2D200,4),(UI_MANAGER+0x1598,0x40),(CONFIG,0x44)]:
            self.map(address,size)
        globals64={0x3326468:S,0x346D538:PUBLISH,0x347CEF0:ACTIVE,0x347CE68:DIRTY,0x346BF98:CONTEXT,
                   0x3326308:ENGINE,0x347D6A0:COLOR_CONTEXT,0x3326340:MODE,0x347CE50:ASSOCIATED,
                   0x3326E68:UI_MANAGER,0x33266A0:CONFIG,0x263C010:COOKIE}
        for rva,value in globals64.items():self.map(game+rva,8);self.write(game+rva,u64(value))
        for rva,value in {0x3483C20:0xFFFFFFFF,0x3483C34:MISSING,0x348456C:0xD0717171,0x347D620:int(color)}.items():
            self.map(game+rva,4);self.write(game+rva,u32(value))
        for rva,blob in LITERALS.items():self.map(game+rva,len(blob));self.write(game+rva,blob)
        self.write(INPUT,bytes([context_flag]));self.write(INPUT+0x48,u64(FLAGOBJ));self.write(FLAGOBJ+0x624,bytes([eligibility]))
        self.owner_value=0x1234000056789000;self.write(S+8,u64(self.owner_value))
        self.write(ACTIVE+0xB398,u64(MATCH_OBJECT))
        self.write(ACTIVE+0xB3A8,u64(0 if active=='null' else MATCH_OBJECT if active=='equal' else MATCH_OBJECT+0x100))
        self.write(DIRTY,b'\0');self.write(CONFIG+8,u32(int(config)));self.write(CONFIG+0x40,u32(0x17))
        self.table=[(0,0xFFFFFFFF)]*8
        for off,value in ((0x80,t),(0x84,d),(0x88,p),(0xD8,8),(0xDC,0),(0xE0,multiplier)):self.write(S+off,u32(value))
        self.write(S+0xD0,u64(MAP))
        self.flags=[]
        for i in range(4 if original else 8):
            entity=ENTITIES+i*0x40;self.write(entity+8,u32(self.keys[i]));self.write(entity+0x14,bytes([entity_flag if i==ordinal else i&1]))
            if i<t:
                index=next((self.keys[i]*multiplier+j)&7 for j in range(8) if self.table[(self.keys[i]*multiplier+j)&7][0]==0)
                self.table[index]=(self.keys[i],i)
            for group,(name,off,old,stride) in enumerate(LAYOUT):
                blob=u64(entity) if name=='pointer' else bytes((i*31+j*7+group*67)&255 for j in range(stride))
                self.write(self.slot(name,i),blob)
            # Non-target records qualify by alternating the independent bit1
            # and bit11 paths. A designated blocker has neither.
            flags=(2 if i%2==0 else 0x800)|0xA0400000
            if i==blocker:flags=0xA0400000
            if i==ordinal:flags=0xA0400000|int(property_bit)
            self.flags.append(flags);self.write(self.slot('property',i)+4,u32(flags))
            self.write(self.slot('property',i)+0xC,u32(self.network if i==ordinal else 0x82000000+i))
            self.write(self.slot('aux',i)+0x18,u32(0xAB000000+i))
        for i,(key,value) in enumerate(self.table):self.write(MAP+i*8,u32(key)+u32(value))
        # Captured forward lookup takes a supplied valid hit at context index2.
        self.write(CONTEXT+0xF1AEB0,u64(CONTEXT_MAP));self.write(CONTEXT+0xF1AEB8,u32(4))
        self.write(CONTEXT+0xF1AEBC,u32(0));self.write(CONTEXT+0xF1AEC0,u32(1))
        for i in range(4):self.write(CONTEXT_MAP+i*8,u32(0)+u32(0xFFFFFFFF))
        self.write(CONTEXT_MAP+(self.keys[ordinal]&3)*8,u32(self.keys[ordinal])+u32(2))
        self.write(CONTEXT+0xF32F28+2*0x18,u32(0x1234 if converted else 0x7FFF))
        self.write(ENGINE,u64(COLOR_OBJECT));self.write(COLOR_OBJECT+0x10,u64(COLOR_TABLE));self.write(COLOR_TABLE,u64(self.vcolor))
        self.write(ENGINE+0x38,u64(VTA));self.write(VTA+8,u64(self.va))
        self.write(ENGINE+0x40,u64(VTB));self.write(VTB+0x160,u64(self.vb))
        self.write(ENGINE+0x10,u64(VTF));self.write(VTF+0x480,u64(self.vevent))
        self.write(MODE+0xAC21C,u32(mode));self.write(ASSOCIATED+0x2D200,u32(3))
        for i in range(3):
            value=(MATCH_OBJECT if converted else 0) if associated_match and i==1 else MATCH_OBJECT+0x100+i
            self.write(ASSOCIATED+i*0x1690,u64(value));self.write(ASSOCIATED+i*0x1690+0x29,bytes([associated_flag]))
        self.write(UI_MANAGER+0x1598,u32(3 if ui else 0))
        for i,tag in enumerate((0x3E,0x3D,0x3E)):
            address=UI+i*0x100000;self.map(address+0x518B0,0x18)
            self.write(UI_MANAGER+0x15A0+i*16,u64(address));self.write(UI_MANAGER+0x15A8+i*16,u32(tag))
            self.write(address+0x518B0,struct.pack('<2f',2.0+i,3.0+i));self.write(address+0x518C4,u32(7+i))
        self.seed();self.before=self.snapshot()
        self.uc.hook_add(UC_HOOK_CODE,self.on_code)
        self.uc.hook_add(UC_HOOK_MEM_READ,lambda uc,access,address,size,value,data:self.reads.append((uc.reg_read(reg('rip')),address,size)))
        self.uc.hook_add(UC_HOOK_MEM_WRITE,lambda uc,access,address,size,value,data:self.writes.append((uc.reg_read(reg('rip')),address,size,value)))

    def slot(self,name,i):
        _,off,old,stride=next(row for row in LAYOUT if row[0]==name)
        return (S+old if self.original else B+off)+i*stride
    def map(self,address,size):
        for page in range(address&~0xFFF,(address+size+0xFFF)&~0xFFF,0x1000):
            if page not in self.pages:self.uc.mem_map(page,0x1000);self.uc.mem_write(page,b'\xa5'*0x1000);self.pages.add(page)
    def read(self,address,size):return bytes(self.uc.mem_read(address,size))
    def write(self,address,blob):self.uc.mem_write(address,blob)
    def int32(self,address):return struct.unpack('<I',self.read(address,4))[0]
    def int64(self,address):return struct.unpack('<Q',self.read(address,8))[0]
    def snapshot(self):return {page:self.read(page,0x1000) for page in self.pages if not STACK<=page<STACK+0x10000}
    def counts(self):return [self.int32(S+off) for off in (0x80,0x84,0x88)]
    def seed(self):
        for name,value in SEEDS.items():self.uc.reg_write(reg(name),value)
        for i in range(6,16):self.uc.reg_write(reg('xmm'+str(i)),(0x0102030405060708+i)*(1+(1<<64)))
        for name,value in dict(rsp=RSP,rcx=0xDEAD0000,rdx=self.target,r8=INPUT,r9=0x9191919191919191).items():self.uc.reg_write(reg(name),value)
        self.write(RSP,u64(self.stop))
    def expected_color(self):
        if self.network<4:
            rgba=struct.unpack('<4f',LITERALS[0x213F4E0][self.network*16:self.network*16+16]);rgb=rgba[1:]
        else:rgb=(1.0,1.0,1.0)
        factor=struct.unpack('<f',LITERALS[0x23C79AC])[0]
        return struct.pack('<3f',*(x*factor for x in rgb))

    def on_code(self,uc,address,size,data):
        self.trace.append(address)
        if address in (self.stop,self.reject):self.outcome='return' if address==self.stop else 'reject';uc.emu_stop();return
        if address==self.game+0xFD9AF0:
            assert uc.reg_read(reg('ecx'))==self.keys[self.ordinal]
            self.events.append({'role':'actual_fd9af0','entity_id':self.keys[self.ordinal]});return
        role={self.va:'virtual_context',self.vb:'virtual_object',self.vcolor:'color',self.vevent:'player_count_event',
              self.game+0x94C9C0:'ui',self.game+0x60C2A0:'count',self.game+0x2088770:'cookie'}.get(address)
        if role is None:return
        rsp=uc.reg_read(reg('rsp'));assert rsp%16==8 and STACK<=rsp<STACK+0x10000
        args={name:uc.reg_read(reg(name)) for name in ('rcx','rdx','r8','r9')};returns={};event={'role':role,'args':args}
        assert self.counts()==[self.t,self.d,self.p]
        if role=='virtual_context':assert args['rcx']==ENGINE;returns={'rax':VIRTUAL_CONTEXT}
        elif role=='virtual_object':assert args['rcx']==VIRTUAL_CONTEXT and args['rdx']==0x1234;returns={'rax':MATCH_OBJECT}
        elif role=='color':
            assert args['rcx']==COLOR_CONTEXT and STACK<=args['rdx']<STACK+0x10000
            actual=self.read(args['rdx'],12);assert actual==self.expected_color(),(actual.hex(),self.expected_color().hex())
            event['rgb_float32_hex']=actual.hex()
        elif role=='ui':
            index=0 if args['rcx']==UI else 2
            assert args['rcx']==UI+index*0x100000 and args['rdx']==args['rcx']+0x3A538
            assert uc.reg_read(reg('xmm2'))&0xFFFFFFFF==int.from_bytes(struct.pack('<f',2.0+index),'little')
            assert uc.reg_read(reg('xmm3'))&0xFFFFFFFF==int.from_bytes(struct.pack('<f',3.0+index),'little')
            assert self.int32(rsp+0x28)==7+index and self.int32(rsp+0x30)==self.d
            assert self.int32(rsp+0x38)==0x3F800000 and self.int32(rsp+0x40)==(0x17 if self.config else 0)
            event['current_dense']=self.d
        elif role=='count':assert args['rdx']==self.d;event['current_dense']=self.d
        elif role=='player_count_event':
            assert self.read(args['rcx'],13)==b'player_count\0' and args['rdx']==self.d and args['r8']==VTF
            event['current_dense']=self.d
        elif role=='cookie':assert args['rcx']==COOKIE;event['synthetic_cookie_checked']=True
        self.events.append(event);self.write(rsp+8,b'\xc7'*32)
        for i,name in enumerate(('rax','rcx','rdx','r8','r9','r10','r11')):uc.reg_write(reg(name),0xCDCD000000000000+i)
        for i in range(6):uc.reg_write(reg('xmm'+str(i)),(0xAABBCCDDEEFF0000+i)*(1+(1<<64)))
        uc.reg_write(reg('rax'),0)
        for name,value in returns.items():uc.reg_write(reg(name),value)

    def run(self,name):
        self.uc.emu_start(self.start,0,count=30000);assert self.outcome is not None
        self.after=self.snapshot()
        RUNS.append(dict(name=name,original=self.original,t=self.t,d=self.d,p=self.p,ordinal=self.ordinal,
                         context_flag=self.context_flag,network=self.network,outcome=self.outcome,instructions=len(self.trace),
                         events=self.events,array_sites_executed=[] if self.original else [hex(row['original_rva']) for row in self.artifact['array_patches'] if row['emitted_address'] in self.trace]))
        return self


class ArrivalTests(unittest.TestCase):
    def abi(self,f,rejected=False):
        self.assertEqual(f.uc.reg_read(reg('rsp')),RSP if rejected else RSP+8)
        for name,value in SEEDS.items():self.assertEqual(f.uc.reg_read(reg(name)),value,name)
        for i in range(6,16):self.assertEqual(f.uc.reg_read(reg('xmm'+str(i))),(0x0102030405060708+i)*(1+(1<<64)))
    def success(self,f):
        self.assertEqual(f.outcome,'return');self.abi(f);self.assertEqual(f.counts(),[f.t,f.d,f.p])
        changes=[];flags=f.flags[f.ordinal]
        if f.context_flag:
            if f.eligibility and f.entity_flag:
                flags|=0x800;changes.append((f.slot('property',f.ordinal)+4,u32(flags)))
            status=1 if f.active in ('null','equal') else 8 if f.blocker is not None and f.blocker<f.d and f.blocker!=f.ordinal else 5
            changes.extend([(PUBLISH+0x3EF280,u64(f.owner_value)),(f.slot('primary',f.ordinal)+0x38,u32(status)),
                            (DIRTY,b'\1'),(f.slot('primary',f.ordinal)+0x60,u64(0))])
        aux=f.slot('aux',f.ordinal)
        changes.extend([(aux+8,u32(0x7FFF)),(aux+0x14,bytes([int(not(flags&1))])),(aux+0x20,u32(MISSING)),
                        (aux,u64(MATCH_OBJECT if f.converted else 0))])
        statuses=[]
        if flags&1:changes.append((aux+0x18,u32(3)));statuses.append(3)
        if f.mode==4 and f.associated_match and f.associated_flag:changes.append((aux+0x18,u32(1)));statuses.append(1)
        self.assertEqual(f.after,changed_pages(f.before,changes))
        self.assertEqual([value for rip,address,size,value in f.writes if address==aux+0x18],statuses)
        roles=['actual_fd9af0']+(['virtual_context','virtual_object'] if f.converted else [])
        if f.color:roles.append('color')
        if f.ui and f.mode==4:roles+=['ui','ui']
        roles+=['count','player_count_event','cookie'];self.assertEqual([e['role'] for e in f.events],roles)
        if not f.original:self.assertFalse(any(S+0xE8<=address<S+0x428 for rip,address,size in f.reads),'candidate read old inline roster')
        palette_reads=[(address,size) for rip,address,size in f.reads if f.game+0x213F4E0<=address<f.game+0x213F520]
        # Unicorn reports MOVUPS as two adjacent 8-byte memory accesses.
        self.assertEqual([byte for address,size in palette_reads for byte in range(address,address+size)],
                         list(range(f.game+0x213F4E0+f.network*16,f.game+0x213F4E0+f.network*16+16)) if f.network<4 else [])
        allowed=[(address,address+len(blob)) for address,blob in changes]
        self.assertTrue(all(STACK<=address and address+size<=STACK+0x10000 or any(lo<=address and address+size<=hi for lo,hi in allowed)
                            for rip,address,size,value in f.writes))
        # D-iteration accesses are distinguished from target pointer reads by RIP.
        site=f.game+0x605630 if f.original else f.artifact['instruction_address_map']['0x605630']
        stop=f.d if f.blocker is None or f.blocker>=f.d or f.blocker==f.ordinal else f.blocker+1
        expected=[(f.slot('pointer',i),8) for i in range(stop)] if f.context_flag and f.active=='distinct' else []
        self.assertEqual([(address,size) for rip,address,size in f.reads if rip==site],expected)
        if not f.original:self.array_sites(f,flags,statuses)

    def array_sites(self,f,flags,statuses):
        patches={row['original_rva']:row for row in f.artifact['array_patches']}
        n=f.ordinal;pr=f.slot('primary',n);aux=f.slot('aux',n);prop=f.slot('property',n)
        primary=1 if f.active in ('null','equal') else 8 if f.blocker is not None and f.blocker<f.d and f.blocker!=n else 5
        read={0x6055BB:[(f.slot('pointer',n),8)] if f.context_flag and f.eligibility else [],
              0x6055CD:[(prop+4,4)] if f.context_flag and f.eligibility and f.entity_flag else [],
              0x6056E6:[(prop+4,1)],0x605760:[(prop+0xC,4)],
              0x605801:[(aux,8)] if f.mode==4 else []}
        write={0x6055CD:read[0x6055CD],0x605665:[(pr+0x38,4)] if f.context_flag and primary==5 else [],
               0x605684:[(pr+0x38,4)] if f.context_flag and primary==8 else [],
               0x605691:[(pr+0x38,4)] if f.context_flag and primary==1 else [],
               0x6056A6:[(pr+0x60,8)] if f.context_flag else [],0x6056B8:[(aux+8,4)],
               0x6056C8:[],0x6056D6:[],0x6056F3:[(aux+0x14,1)],0x605700:[(aux+0x20,4)],
               0x605709:[(aux+0x18,4)] if flags&1 else [],0x605758:[(aux,8)],
               0x60583C:[(aux+0x18,4)] if f.mode==4 and f.associated_match and f.associated_flag else []}
        for old,patch in patches.items():
            lo=patch['emitted_address'];hi=lo+len(bytes.fromhex(patch['replacement_hex']))
            actual_read=[(address,size) for rip,address,size in f.reads if lo<=rip<hi]
            actual_write=[(address,size) for rip,address,size,value in f.writes if lo<=rip<hi]
            self.assertEqual(actual_read,read.get(old,[]),hex(old))
            self.assertEqual(actual_write,write.get(old,[]),hex(old))
            if old in (0x60561F,0x605626):self.assertEqual(lo in f.trace,f.context_flag and f.active=='distinct' and f.d>0)
        # Invalid-ordinal branch sites are preserved statically but deliberately
        # unreachable after a successful candidate guard.
        self.assertNotIn(patches[0x6056C8]['emitted_address'],f.trace)
        self.assertNotIn(patches[0x6056D6]['emitted_address'],f.trace)

    def test_01_fixed_source_decode_and_all_nineteen_patches(self):
        self.assertEqual(native.load_source(EVIDENCE),BODY)
        result=native.build(BODY,**params());blob=bytes.fromhex(result['code_hex']);rows=decode(blob,result['code_address'])
        self.assertEqual(sha(blob),result['code_sha256']);self.assertEqual(len(result['array_patches']),19)
        self.assertEqual({patch['original_rva'] for patch in result['array_patches']},ARRAY_SITES)
        boundaries={row.address for row in rows}
        for patch in result['array_patches']:
            self.assertIn(patch['emitted_address'],boundaries);self.assertEqual(blob[patch['emitted_address']-result['code_address']:][:len(bytes.fromhex(patch['replacement_hex']))].hex(),patch['replacement_hex'])
        for row in rows:
            if row.group(capstone.CS_GRP_JUMP):self.assertIn(row.operands[0].imm,boundaries|{result['reject_address']})
        with self.assertRaises(ValueError):native.build(bytes([BODY[0]^1])+BODY[1:],**params())

    def test_02_eight_slots_palette_and_four_slot_baseline(self):
        for ordinal in range(8):self.success(Fixture(ordinal=ordinal).run('eight_slots_four_palette_four_fallback'))
        for ordinal,options in enumerate([dict(context_flag=False,property_bit=False,associated_match=False),dict(active='null'),
                                          dict(active='distinct',blocker=3,entity_flag=False),dict(active='distinct',associated_flag=False)]):
            original=Fixture(original=True,t=4,d=4,ordinal=ordinal,**options).run('original_four_slot_baseline')
            candidate=Fixture(t=4,d=4,ordinal=ordinal,**options).run('candidate_four_slot_pair')
            self.success(original);self.success(candidate)
            for name,off,old,stride in LAYOUT:
                self.assertEqual([original.read(original.slot(name,i),stride) for i in range(4)],
                                 [candidate.read(candidate.slot(name,i),stride) for i in range(4)])
            self.assertEqual([e.get('rgb_float32_hex') for e in original.events if e['role']=='color'],
                             [e.get('rgb_float32_hex') for e in candidate.events if e['role']=='color'])

    def test_03_primary_aux_flags_pending_and_unchanged_current_counts(self):
        cases=[dict(ordinal=0,blocker=7),dict(ordinal=7,context_flag=False,property_bit=False,mode=3),
               dict(ordinal=7,eligibility=False,property_bit=True,associated_flag=False),
               dict(ordinal=7,entity_flag=False,property_bit=False,associated_match=False),
               dict(ordinal=7,active='equal',converted=False,associated_match=False),
               dict(ordinal=7,d=3,p=1,config=False),dict(t=1,d=0,p=0,ordinal=0,converted=False,associated_flag=False),
               dict(ordinal=7,network=0xFFFFFFFF,game=0x7FF800000000,multiplier=1),
               dict(ordinal=7,color=False,ui=False,mode=3)]
        visited=set()
        for options in cases:
            f=Fixture(**options).run('finite_state_branch_contracts');self.success(f)
            visited.update(row['original_rva'] for row in f.artifact['array_patches'] if row['emitted_address'] in f.trace)
        self.assertEqual(visited,ARRAY_SITES-{0x6056C8,0x6056D6})

    def test_04_all_preflight_rejections_restore_entry_arguments(self):
        cases=[('binding',1),('null_target',2),('null_context',3),('tracked_zero',4),('tracked_nine',4),
               ('dense_order',5),('prefix_order',5),('map_capacity',6),('empty_id',7),('invalid_id',7),
               ('missing_full',8),('missing_empty',8),('ordinal_eight',9),('ordinal_untracked',9),('pointer_binding',10)]
        for name,reason in cases:
            small=name in ('missing_empty','ordinal_untracked')
            f=Fixture(t=3 if small else 8,d=3 if small else 8,p=2,ordinal=1)
            if name=='binding':f.write(GAME+0x3326468,u64(0x40000000))
            elif name=='null_target':f.uc.reg_write(reg('rdx'),0)
            elif name=='null_context':f.uc.reg_write(reg('r8'),0)
            elif name=='tracked_zero':f.write(S+0x80,u32(0))
            elif name=='tracked_nine':f.write(S+0x80,u32(9))
            elif name=='dense_order':f.write(S+0x84,u32(9))
            elif name=='prefix_order':f.write(S+0x88,u32(9))
            elif name=='map_capacity':f.write(S+0xD8,u32(0))
            elif name=='empty_id':f.write(f.target+8,u32(0))
            elif name=='invalid_id':f.write(f.target+8,u32(0xFFFFFFFF))
            elif name.startswith('missing_'):f.write(f.target+8,u32(75))
            elif name=='pointer_binding':f.write(f.slot('pointer',1),u64(f.target+0x40))
            else:
                bucket=next(i for i,(key,value) in enumerate(f.table) if key==f.keys[1])
                f.write(MAP+bucket*8+4,u32(8 if name=='ordinal_eight' else 3))
            expected={name:f.uc.reg_read(reg(name)) for name in ('rcx','rdx','r8','r9')}
            f.before=f.snapshot();f.run('guard_'+name)
            self.assertEqual(f.outcome,'reject');self.assertEqual(f.uc.reg_read(reg('r10d')),reason);self.abi(f,True)
            self.assertEqual(f.after,f.before);self.assertEqual(f.events,[])
            for name,value in expected.items():self.assertEqual(f.uc.reg_read(reg(name)),value)
            self.assertTrue(all(STACK<=address and address+size<=STACK+0x10000 for rip,address,size,value in f.writes))

    def test_05_address_rel32_and_sixteen_function_bundle(self):
        for update in [dict(game_base=GAME+1),dict(code_address=GAME+0x6054F0),dict(storage_address=B+1),
                       dict(storage_address=S+0x100),dict(reject_address=B+0x500)]:
            values=params();values.update(update)
            with self.assertRaises(ValueError):native.build(BODY,**values)
        artifact=native.build(BODY,**params())
        jumps=[row for row in decode(bytes.fromhex(artifact['code_hex']),artifact['code_address'])
               if row.mnemonic=='jmp' and row.operands[0].imm==artifact['reject_address']]
        lo=max(row.address+row.size-(1<<31) for row in jumps);hi=min(row.address+row.size+(1<<31)-1 for row in jumps)
        for address in (lo,hi):
            f=Fixture(arguments={'reject_address':address});f.write(GAME+0x3326468,u64(0x40000000));f.before=f.snapshot()
            f.run('reject_rel32_boundary');self.assertEqual(f.outcome,'reject');self.assertEqual(f.uc.reg_read(reg('r10d')),1)
            self.abi(f,True);self.assertEqual(f.after,f.before);self.assertEqual(f.events,[])
        for address in (lo-1,hi+1):
            values=params();values['reject_address']=address
            with self.assertRaises(ValueError):native.build(BODY,**values)
        dep=native.departure;g=dep.getter;rm=native.remove;mv=native.move
        sources=[native.registry.load_sources(RESEARCH/'roster_registry_update_native_evidence.json'),
                 dep.load_source(RESEARCH/'roster_departure_native_evidence.json'),g.load_source(RESEARCH/'roster_getter_native_evidence.json'),
                 g.classify.load_sources(RESEARCH/'roster_classify_native_evidence.json'),rm.load_sources(RESEARCH/'roster_remove_native_evidence.json'),
                 rm.insert.load_sources(RESEARCH/'roster_insert_native_evidence.json'),mv.load_source(RESEARCH/'roster_move_native_evidence.json'),
                 rm.insert.base_bundle.pair.producer.load_source(RESEARCH/'roster_property_producer_native_evidence.json'),
                 rm.insert.base_bundle.pair.receiver.load_source(RESEARCH/'roster_property_receive_evidence.json')]
        counts=dep.player_count.load_sources(RESEARCH/'roster_player_count_native_evidence.json',RESEARCH/'roster_departure_callee_evidence.json')
        values=json.loads(ADDRESSES.read_bytes());values.update(player_count_context_source=counts['context'],player_count_filter_source=counts['filter'])
        result=native.build_bundle(BODY,*sources,**values)
        self.assertEqual(result,json.loads(SAMPLE.read_bytes()));self.assertEqual(len(result['known_regions']),62)
        self.assertEqual(result['shared_binding'],dict(game_base=GAME,roster_address=S,storage_address=B))
        self.assertEqual(result['arrival']['storage_address'],B)
        for field,value in [('arrival_code_address',values['registry_code_address']),('arrival_code_address',values['player_count_trampoline_address']),
                            ('arrival_reject_address',values['receiver_reject_address'])]:
            bad=dict(values);bad[field]=value
            with self.assertRaises(ValueError):native.build_bundle(BODY,*sources,**bad)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ArrivalTests))
    sources=['roster_arrival','roster_registry_update','roster_departure','roster_getter','roster_classify','roster_remove','roster_insert',
             'roster_move','roster_bundle','roster_property_pair','roster_producer','roster_receiver','player_count']
    build_evidence=['roster_registry_update_native_evidence.json','roster_departure_native_evidence.json','roster_getter_native_evidence.json',
                    'roster_classify_native_evidence.json','roster_remove_native_evidence.json','roster_insert_native_evidence.json',
                    'roster_move_native_evidence.json','roster_property_producer_native_evidence.json','roster_property_receive_evidence.json',
                    'roster_player_count_native_evidence.json','roster_departure_callee_evidence.json']
    executed=sorted({site for run in RUNS if not run['original'] for site in run['array_sites_executed']},key=lambda site:int(site,16))
    report=dict(status='passed' if result.wasSuccessful() else 'failed',test_methods_run=result.testsRun,
                failure_count=len(result.failures),error_count=len(result.errors),
                failures=[{'test':str(test),'traceback':tb} for test,tb in result.failures],
                errors=[{'test':str(test),'traceback':tb} for test,tb in result.errors],
                source_sha256={f'Native/{name}.py':sha((ROOT/f'Native/{name}.py').read_bytes()) for name in sources},
                test_sha256=sha(Path(__file__).read_bytes()),
                test_dependency_sha256={str(path.relative_to(ROOT)):expected for path,expected in [(ADDRESSES,ADDRESSES_SHA),(SAMPLE,SAMPLE_SHA)]},
                evidence_sha256={EVIDENCE.name:EVIDENCE_SHA,**{name:sha((RESEARCH/name).read_bytes()) for name in build_evidence}},
                evidence_scopes={'executed_saved_bodies_and_fixed_readonly_data':EVIDENCE.name,'build_bundle_only':build_evidence},
                saved_body_sha256={'0x6054f0':sha(BODY),'0xfd9af0':sha(LEAF)},
                captured_literals={hex(address):{'bytes_hex':blob.hex(),'sha256':sha(blob)} for address,blob in LITERALS.items()},
                python_version=sys.version,unicorn_version=unicorn.__version__,capstone_version=capstone.__version__,
                fixture_synthetic=True,game_process_accessed=False,host_native_code_executed=False,installable=False,
                emulator_runs=RUNS,
                execution_counts={'total':len(RUNS),'original_complete_return':sum(run['original'] for run in RUNS),
                                  'candidate':sum(not run['original'] for run in RUNS),
                                  'candidate_complete_return':sum(not run['original'] and run['outcome']=='return' for run in RUNS),
                                  'candidate_preflight_rejection':sum(run['outcome']=='reject' for run in RUNS)},
                nested_saved_fd9af0_entries_not_added_to_total=sum(event['role']=='actual_fd9af0' for run in RUNS for event in run['events']),
                array_site_coverage={'statically_verified_all19':[hex(site) for site in sorted(ARRAY_SITES)],
                                     'executed_candidate_valid_domain17':executed,
                                     'invalid_ordinal_only_static':['0x6056c8','0x6056d6']},
                oracle_scope={
                    'whole_memory':'All nonstack pages are compared with independent expected changes: target primary/property/aux fields, published original S+8 owner and dirty marker only; counts, maps, pointers, other records and canaries remain unchanged',
                    'array_sites':'All19 patched locations are pinned independently from saved disassembly. Valid-domain17 are checked by emitted RIP, exact read/write address/width and conditional presence; two invalid-ordinal-only branches are static-only. D traversal pointer reads and both LEA executions are separately checked',
                    'primary_state':'Context flag0 leaves primary/property/global-owner effects absent; flag1 retains original states1(null/equal active),5(all D entries qualified including D0),8(unqualified non-target dense record including slot7), plus target primary trailingQWORD reset',
                    'aux_state':'Association marker7FFF, inverse property bit0 byte, nondefault global missing DWORD and resolved object pointer retain exact widths; state3 conditional on propertybit0 then optional mode4 matching-record state1 are checked in write order',
                    'palette':'Fixed four64B-table rows are used only for network0..3 with exact16-byte read coverage; network4..7 andFFFFFFFF use original [1,1,1]*255 fallback with no palette access. Callback observes three float32 components, not fabricated eight-entry colors',
                    'counts':'Both UI callbacks, count helper and final player_count event receive unchanged current D, including zero and pending targets; no prediction/increment/clamp is added to this function',
                    'baseline_and_abi':'Four complete original four-slot cases pair with candidate outputs; other finite branches cover second ASLR, flags independent of P, pending n>=D, null conversion, absent matching mode record and disabled callbacks. Win64 nonvolatile GPR/XMM including XMM6, RSP and guard arguments are checked',
                    'bundle':'Sixteen roster functions plus existing count plan build to the pinned saved sample with62 regions/common S/B; other unchanged function suites are not rerun'},
                contract_stubs={
                    'FD9AF0':'Not a stub: captured174-byte body executes a valid supplied context-map hit at ordinal2; its record DWORD returns1234 or7FFF. Entry-sentinel/default and malformed/missing context-map branches are not executed',
                    'interface38+8':'Check RCX global engine context; return synthetic context pointer for next indirect call',
                    'interface40+160':'Check RCX prior context and EDX1234; return synthetic associated object pointer stored by real body in target aux',
                    'color_interface':'Check RCX color context and12-byte stack RGB vector computed by real palette/fallback/SSE operations; record bytes and preserve nonstack memory',
                    '94C9C0':'Check two tag3E listeners in order, UI object/derived record pointer, XMM2/XMM3 inputs and four stack arguments including unchanged D/float1/config; do not execute actual context or resources',
                    '60C2A0':'Check EDX current D; preserve nonstack memory; actual named resources/count helper not executed',
                    'interface10+480':'Check exact player_count literal, EDX current D and R8 interface pointer; normal CALL returns before cookie check, not a tail jump',
                    '2088770':'Check RCX equals supplied synthetic cookie after real prologue XOR/save and epilogue reload/XOR; security-check implementation is not executed',
                    'all_stubs':'Validate RSP%16=8 and shadow space, clobber all volatile GPR/XMM0..5, preserve nonvolatiles and fixture globals/roster; no actual game callback mutation/reentrancy'},
                limits=[
                    'The arrival filename is an artifact identifier; this body is not proved to append, create or initially admit a player',
                    'Binding/map/counts/target/context/sidecar readability and lifetime are supplied stable preconditions, not runtime ownership or synchronization validation',
                    'Original invalid-ordinal branches6056C8/6056D6 are statically relocated but unreachable after successful candidate guard; they are not counted as dynamic coverage',
                    'FD9AF0 uses valid found context-map records only; zero-capacity/full-table-miss/null-dereference hazards and entry-sentinel fallback are outside this execution scope',
                    'Opaque interface, palette callback, UI/count/final event and cookie routines are explicit contracts, not real resources, side effects or security implementation',
                    'Palette indices above3 intentionally preserve original fallback, not distinct per-player colors; UI/count consumers remain separate unverified integration requirements',
                    'No caller/hook, allocation/migration/cleanup, reentrant callback, rollback, unwind, installation, game process or multiplayer mission acceptance is performed'])
    (ROOT/'verification/native_roster_arrival_tests.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],methods=result.testsRun,executions=len(RUNS),failures=len(result.failures),errors=len(result.errors))))
    raise SystemExit(0 if result.wasSuccessful() else 1)
