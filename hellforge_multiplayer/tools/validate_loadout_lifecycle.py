"""Execute three relocated native UI paths in owned emulator RAM.

Default: one eight-slot transition smoke check against the saved four-slot
body, READY preparation and two Windows unwind points. --full explicitly adds
the previous lifecycle regression. Resource services remain test stubs.
No receipts, hashes, archives, installation or game access.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'eight_player_candidate_20260927/.native-test-deps'))
import unicorn as u
from unicorn import x86_const as reg
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP
import generate_loadout_lifecycle as g

GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT = 0x180000000,0x190000000,0x220000000,0x230000000,0x240000000,0x190100000
STACK,STOP,ENGINE = 0x280000000,0x190200000,0x290000000
SP=STACK+0x1008
NAMES=('rbx','rbp','rsi','rdi','r12','r13','r14','r15')
R=lambda name: getattr(reg, 'UC_X86_REG_'+name.upper())
U64=lambda x: struct.pack('<Q',x)
U32=lambda x: struct.pack('<I',x)


class Addresses(c.Structure):
    _fields_=[(name,c.c_uint64) for name in ('game','code','screen','records','widgets','reject')]+[('capacity',c.c_uint32),('reserved',c.c_uint32)]


class Image(c.Structure):
    _fields_=[(name,c.c_uint32) for name in ('bytes','code_bytes','unwind_offset','table_offset','constructor','release','alternate_release','function_count','transition','handler_offset')]+[('data',c.c_ubyte*4096)]


def addresses(capacity=8):
    return Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,capacity,0)


class Fixture:
    def __init__(self, artifact, library, image, capacity, kind, variant, original=False, foreign=False,unwind_points=None):
        self.uc=u.Uc(u.UC_ARCH_X86,u.UC_MODE_64);self.pages=set();self.calls=[];self.unwinds=0
        self.unwind_points=unwind_points;self.transition_args=[]
        self.capacity=capacity;self.kind=kind;self.image=image;self.library=library;self.foreign=foreign;self.original=original
        self.records=SCREEN+0x10 if original else RECORDS
        self.widgets=SCREEN+0x53a78 if original else WIDGETS
        self.start=GAME+g.STARTS[kind] if original else CODE+artifact['entries'][kind]
        self.bounds=[(GAME+s['start'],GAME+s['end']) for s in artifact['sources']] if original else [(CODE+f[0],CODE+f[1]) for f in artifact['functions']]
        self.map(SCREEN,0x2739d0)
        self.map(RECORDS-0x1000,0x9f0*8+0x2000);self.map(WIDGETS-0x1000,0x1ee18*8+0x2000)
        self.map(STACK,0x2000);self.map(STOP,1);self.map(REJECT,1)
        self.map(ENGINE,0x1000);self.map(ENGINE+0x1782000,0x1000)
        self.write(self.records,bytes([0xa5])*(capacity*0x9f0))
        self.write(self.widgets,bytes([0xa5 if kind==0 else 0])*(capacity*0x1ee18))
        self.write(RECORDS-16,bytes([0x6b])*16);self.write(RECORDS+capacity*0x9f0,bytes([0x6b])*16)
        self.write(WIDGETS-16,bytes([0x7c])*16);self.write(WIDGETS+capacity*0x1ee18,bytes([0x7c])*16)
        capture=g.Capture();self.external=set()
        originals=[(s['start'],s['data']) for s in artifact['sources']]
        # Execute the real saved per-widget constructor; its nested resource
        # helpers are ABI stubs. Internal 14/7/4/6 loops are NOT expanded.
        originals.append((0x14aa5c0,capture.read(0x14aa5c0,0x26f)))
        self.widget_body=(GAME+0x14aa5c0,GAME+0x14aa82f)
        for base,data in originals:
            self.map(GAME+base,len(data));self.write(GAME+base,data)
            for ins in capture.md.disasm(data,base):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not any(a<=target<a+len(b) for a,b in originals):
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for operand in ins.operands:
                    if operand.type==X86_OP_MEM and operand.mem.base==X86_REG_RIP:
                        target=ins.address+ins.size+ins.disp;self.map(GAME+target,16)
                        if target==0x263c010:
                            # The process's mutable cookie is not in the saved
                            # code capture; use an explicit fixture value.
                            self.write(GAME+target,U64(0x6745ab23901f))
                        elif target<0x3000000:
                            self.write(GAME+target,capture.read(target,operand.size))
                        else:
                            self.write(GAME+target,U64(ENGINE) if operand.size==8 else U32(0xffffffff))
        self.map(CODE,image.bytes);self.write(CODE,bytes(image.data[:image.bytes]))
        if kind in (1,2):
            self.write(SCREEN+0xd2940,U64(variant))
            self.write(SCREEN+0xf948,U32(variant+1))
            self.write(SCREEN+0xf935,bytes([variant]))
            self.write(SCREEN+0xf936,b'\0');self.write(SCREEN+0x3b54,U32(2))
            for i in range(capacity):
                w=self.widgets+i*0x1ee18
                self.write(w+0x2098,U64((i+variant)%2))
                self.write(w+0x1ee0c,bytes([(i+variant)%2]))
                self.write(w+0x1c18,U32(0x1200+i if (i+variant)%2 else 0xffffffff))
        if kind==3:
            # Native virtual interfaces/global state are explicit test-owned
            # stand-ins. Exercise enabled service, animation and cleanup paths.
            vtable=ENGINE+0x20000;self.map(vtable,0x1000)
            for i in range(4):
                target=GAME+0x3001000+i*16
                self.external.add(target);self.map(target,1);self.write(target,b'\xc3')
            for at,value in ((ENGINE+0x10,vtable),(ENGINE+0xf0,vtable),
                             (vtable+0xc8,GAME+0x3001000),(vtable+0x628,GAME+0x3001010),
                             (ENGINE+0x288,GAME+0x3001020),(ENGINE+0x338,GAME+0x3001030),
                             (ENGINE+0x10f8,0x4455),(ENGINE+0xb398,0x7788)):
                self.map(at,8);self.write(at,U64(value))
            self.map(ENGINE+0xac560,1);self.write(ENGINE+0xac560,b'\1')
            self.map(ENGINE+0xb3a8,8);self.write(ENGINE+0xb3a8,U64(0))
            self.map(ENGINE+0x3520,0x20);self.write(ENGINE+0x3520,U32(1))
            self.cleanup=ENGINE+0x40000
            self.map(self.cleanup+0x1f8000,0x1000)
            self.write(ENGINE+0x3528,U64(self.cleanup));self.write(ENGINE+0x3530,U32(0x104))
            self.write(self.cleanup+0x1f8078,U64(0x7788));self.write(self.cleanup+0x1f8070,U32(3))
            self.write(self.cleanup+0x1f8012,b'\1');self.write(SCREEN+0x273990,b'\1')
            self.cookie=0x6745ab23901f
        self.before_screen=self.read(SCREEN,0x2739d0)
        self.before_records=self.read(RECORDS,capacity*0x9f0)
        self.before_widgets=self.read(WIDGETS,capacity*0x1ee18)
        self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP))
        for i,name in enumerate(NAMES):self.uc.reg_write(R(name),0x11110000+i*0x101)
        for i in range(6,9):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        self.uc.reg_write(R('rcx'),SCREEN+8 if foreign else SCREEN)
        self.uc.hook_add(u.UC_HOOK_CODE,self.step)

    def map(self,address,size):
        for page in range(address&~0xfff,(address+size+0xfff)&~0xfff,0x1000):
            if page not in self.pages:self.uc.mem_map(page,0x1000);self.pages.add(page)

    def write(self,address,data):self.uc.mem_write(address,data)
    def read(self,address,n):return bytes(self.uc.mem_read(address,n))
    def value(self,name):return self.uc.reg_read(R(name))

    def step(self,uc,address,size,user):
        if address in (STOP,REJECT):self.stop=address;uc.emu_stop();return
        if CODE<=address<CODE+self.image.code_bytes and (self.unwind_points is None or address-CODE in self.unwind_points):
            xmm=[v for i in range(6,9) for v in (self.value(f'xmm{i}')&((1<<64)-1),self.value(f'xmm{i}')>>64)]
            values=(c.c_uint64*14)(*(self.value(n) for n in NAMES),*xmm)
            stack=(c.c_ubyte*512).from_buffer_copy(self.read(SP-256,512))
            rc=self.library.loadout_unwind(c.byref(self.image),address-CODE,self.value('rsp')-SP,values,stack,STOP)
            g.need(rc==0,f'Unwind {address-CODE:x} failed: {rc}')
            self.unwinds+=1
            if self.unwind_points is not None:self.unwind_points.remove(address-CODE)
        if address==self.widget_body[0] or address in self.external:
            if self.kind==3 and address==GAME+0x2088770:
                g.need(self.value('rcx')==self.cookie,'Transition cookie check argument changed')
            if self.kind==3 and address==GAME+0x1451100:
                rsp=self.value('rsp');scratch=struct.unpack('<Q',self.read(rsp+0x38,8))[0]
                self.transition_args.append((self.value('rcx'),self.value('xmm1'),self.value('xmm2'),self.value('r9')&255,
                                             self.read(rsp+0x28,4),self.read(rsp+0x30,4),self.read(scratch,16)))
            self.calls.append((address-GAME,self.value('rcx'),self.value('rdx')))
            if address in self.external:
                # Clobber caller-saved integer registers, preserving the ABI's
                # nonvolatiles; then RET executes normally, including tailcalls.
                for name in ('rax','rcx','rdx','r8','r9','r10','r11'):uc.reg_write(R(name),0)

    def run(self):
        self.stop=None;self.uc.emu_start(self.start,0,count=100000)
        g.need(self.stop==(REJECT if self.foreign else STOP),'Lifecycle failed to terminate at expected exit')
        g.need(self.value('rsp')==SP+(0 if self.foreign else 8),'Wrong stack balance')
        for i,name in enumerate(NAMES):g.need(self.value(name)==0x11110000+i*0x101,'Nonvolatile register damaged')
        for i in range(6,9):g.need(self.value(f'xmm{i}')==(0x66660000+i)|((0xaaaa0000+i)<<64),'Nonvolatile XMM register damaged')
        if self.foreign:
            g.need(not self.calls and self.read(SCREEN,0x2739d0)==self.before_screen and
                   self.read(RECORDS,self.capacity*0x9f0)==self.before_records and
                   self.read(WIDGETS,self.capacity*0x1ee18)==self.before_widgets,'Foreign screen caused side effects')
        if not self.original:
            g.need(self.read(RECORDS-16,16)==bytes([0x6b])*16 and self.read(RECORDS+self.capacity*0x9f0,16)==bytes([0x6b])*16,'Record boundary crossed')
            g.need(self.read(WIDGETS-16,16)==bytes([0x7c])*16 and self.read(WIDGETS+self.capacity*0x1ee18,16)==bytes([0x7c])*16,'Widget boundary crossed')
        return self

    def groups(self):
        widgets=[[] for _ in range(self.capacity)];other=[]
        for target,rcx,rdx in self.calls:
            pointer=rdx if target==0xb22420 else rcx
            if self.widgets<=pointer<self.widgets+self.capacity*0x1ee18:
                i,offset=divmod(pointer-self.widgets,0x1ee18)
                widgets[i].append((target,offset,rcx if target==0xb22420 else 0))
            else:other.append((target,rcx))
        return widgets,other


def widget_choices(artifact,dll,image):
    # A fifth PLAYER uses widget #4. Its four INNER choices still use indices
    # 0..3, with a different stride. Execute the saved helper to prove both
    # address dimensions; widening its guard would reach the next nested state.
    capture=g.Capture();data=capture.read(0x189d050,0xc6)
    f=Fixture(artifact,dll,image,8,0,0)
    widget=WIDGETS+4*0x1ee18
    f.map(GAME+0x189d050,len(data));f.write(GAME+0x189d050,data)
    f.write(widget+0x134f0,b'\0') # Skip the helper's session broadcasts.
    for target in (0x11f2490,0x1893600,0xbe0800):
        f.external.add(GAME+target);f.map(GAME+target,1);f.write(GAME+target,b'\xc3')
    for index in (0,1,2,3,4,7,0xffffffff):
        f.calls=[];f.stop=None;f.uc.reg_write(R('rsp'),SP);f.write(SP,U64(STOP))
        f.uc.reg_write(R('rcx'),widget);f.uc.reg_write(R('rdx'),index);f.uc.reg_write(R('r8'),0x37)
        f.uc.emu_start(GAME+0x189d050,0,count=1000)
        g.need(f.stop==STOP and f.value('rsp')==SP+8,'Widget choice helper failed')
        targets=[(target,rcx) for target,rcx,rdx in f.calls]
        expected=[(0x11f2490,0x37),(0x1893600,widget+0xea38+index*0x12a8)] if index<4 else []
        g.need(targets==expected,'Per-widget choice limit confused with player capacity')
    return 7


def transition_smoke(artifact,dll):
    image=Image();g.need(dll.loadout_build(c.byref(addresses(8)),c.byref(image))==0,'Transition image rejected')
    old=Fixture(artifact,dll,image,4,3,0,original=True,unwind_points=set()).run()
    points={artifact['mapping'][0x1470b60],artifact['mapping'][0x1470d0d]}
    new=Fixture(artifact,dll,image,8,3,0,unwind_points=points).run()
    old_widgets,old_other=old.groups();new_widgets,new_other=new.groups()
    g.need(old_other==new_other,'Transition service ordering changed')
    expected=[(0x189e080,0,0),(0x1451100,0,0)]
    g.need(all(x==expected for x in old_widgets+new_widgets),'Transition missed a native widget')
    prior=[x[1:] for x in old.transition_args if old.widgets<=x[0]<old.widgets+4*0x1ee18]
    current=[x[1:] for x in new.transition_args if new.widgets<=x[0]<new.widgets+8*0x1ee18]
    g.need(len(prior)==4 and len(current)==8 and all(x==prior[0] for x in prior+current),'Animation ABI changed')
    for begin,end in ((0,0x10),(0x27d0,0x53a78),(0xcf2d8,0x2739d0)):
        g.need(new.read(SCREEN+begin,end-begin)==old.read(SCREEN+begin,end-begin),'Transition changed unrelated screen state')
    for f in (old,new):
        for begin,end in ((0x10,0x27d0),(0x53a78,0xcf2d8)):
            g.need(f.read(SCREEN+begin,end-begin)==f.before_screen[begin:end],'Transition directly altered inline arrays')
    g.need(new.read(new.cleanup+0x1f8070,4)==U32(0) and new.read(new.cleanup+0x1f8012,1)==b'\0','User-state cleanup skipped')
    g.need(not points and new.unwinds==2,'Required unwind/handler checks not reached')
    g.need(dll.loadout_prepare_test(c.byref(addresses(8)))==0,'Transition READY preparation/cleanup failed')
    return dict(passed=True,scope='eight-slot transition smoke',game_access=False,runtime_verified=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--zig',type=Path);parser.add_argument('--upstream',type=Path)
    parser.add_argument('--full',action='store_true',help='Explicitly run the existing lifecycle regression as well')
    parser.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_lifecycle_test.dll');args=parser.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required')
        args.library.parent.mkdir(parents=True,exist_ok=True)
        cmd=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
             '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared',
             g.PROJECT/'mod/src/ep_session_code.cpp',g.PROJECT/'mod/src/ep_loadout_lifecycle.cpp',g.PROJECT/'tests/loadout_lifecycle_dll.cpp','-o',args.library.resolve()]
        proc=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);g.need(proc.returncode==0,proc.stdout+proc.stderr)
    dll=c.CDLL(str(args.library.resolve()))
    dll.loadout_build.argtypes=[c.POINTER(Addresses),c.POINTER(Image)];dll.loadout_build.restype=c.c_int
    dll.loadout_prepare_test.argtypes=[c.POINTER(Addresses)];dll.loadout_prepare_test.restype=c.c_int
    dll.loadout_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64];dll.loadout_unwind.restype=c.c_int
    artifact=g.build();smoke=transition_smoke(artifact,dll)
    if not args.full:print(json.dumps(smoke));return
    scenarios=unwinds=0
    for kind in range(3):
        for variant in range(2 if kind else 1):
            image=Image();g.need(dll.loadout_build(c.byref(addresses(4)),c.byref(image))==0,'Four-slot image rejected')
            original=Fixture(artifact,dll,image,4,kind,variant,original=True).run();old_groups,old_other=original.groups()
            for capacity in (1,4,5,8):
                a=addresses(capacity);image=Image();g.need(dll.loadout_build(c.byref(a),c.byref(image))==0,'Configured image rejected')
                f=Fixture(artifact,dll,image,capacity,kind,variant).run();groups,other=f.groups()
                g.need(other==old_other,'Nonplayer callback sequence changed')
                for i,group in enumerate(groups):
                    expected=old_groups[i%4]
                    # Resource handle values intentionally follow player index.
                    expected=[(t,o,v+(i-i%4) if t==0xb22420 else v) for t,o,v in expected]
                    g.need(group==expected,f'Player {i} nested callbacks changed')
                if not kind:
                    g.need(f.value('rax')==SCREEN,'Constructor return changed')
                    for i in range(capacity):
                        g.need(f.read(RECORDS+i*0x9f0,0x9f0)==original.read(original.records,0x9f0),'Record initialization changed')
                        g.need(f.read(WIDGETS+i*0x1ee18,0x1ee18)==original.read(original.widgets,0x1ee18),'Widget initialization changed')
                # All inline members beyond the replaced arrays must retain the
                # original constructor/release behavior; adjacent objects too.
                for begin,end in ((0,0x10),(0x27d0,0x53a78),(0xcf2d8,0x2739d0)):
                    g.need(f.read(SCREEN+begin,end-begin)==original.read(SCREEN+begin,end-begin),'Adjacent screen members changed')
                g.need(f.read(SCREEN+0x10,4*0x9f0)==f.before_screen[0x10:0x27d0] and
                       f.read(SCREEN+0x53a78,4*0x1ee18)==f.before_screen[0x53a78:0xcf2d8],'Old inline arrays were still used')
                unwinds+=f.unwinds;scenarios+=1
            bad=Fixture(artifact,dll,image,8,kind,variant,foreign=True).run();unwinds+=bad.unwinds;scenarios+=1
    rejections=0
    cases=[]
    for field in ('game','code','screen','records','widgets','reject'):
        for value in (0,1,(1<<47)-1,1<<47,(1<<64)-1):
            a=addresses();setattr(a,field,value);cases.append(a)
    for field in ('capacity','reserved'):
        for value in ((0,9,0xffffffff) if field=='capacity' else (1,0xffffffff)):
            a=addresses();setattr(a,field,value);cases.append(a)
    for field in ('screen','records','widgets','reject'):
        a=addresses();setattr(a,field,CODE);cases.append(a)
    a=addresses();a.records=CODE+0xf00;cases.append(a)
    for value in (WIDGETS+16,SCREEN+0x10):
        a=addresses();a.records=value;cases.append(a)
    a=addresses();a.code=0x700000000000;cases.append(a)
    for a in cases:
        image=Image();c.memset(c.byref(image),0xa5,c.sizeof(image))
        g.need(dll.loadout_build(c.byref(a),c.byref(image))!=0 and bytes(image)==bytes(c.sizeof(image)),'Invalid layout partly emitted')
        rejections+=1
    image=Image();g.need(dll.loadout_build(None,c.byref(image))!=0 and dll.loadout_build(c.byref(addresses()),None)!=0,'Null API accepted')
    for capacity in (1,4,5,8):g.need(dll.loadout_prepare_test(c.byref(addresses(capacity)))==0,'READY allocation/unwind/discard failed')
    image=Image();g.need(dll.loadout_build(c.byref(addresses()),c.byref(image))==0,'Choice fixture image rejected')
    choices=widget_choices(artifact,dll,image)
    print(json.dumps(dict(passed=True,lifecycle_scenarios=scenarios,invalid_layouts=rejections+2,windows_unwind_contexts=unwinds,ready_lifecycles=4,widget_choice_scenarios=choices,game_access=False)))


if __name__=='__main__':main()
