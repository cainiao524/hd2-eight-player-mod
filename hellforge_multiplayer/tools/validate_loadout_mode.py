"""One open -> return loadout mode flow, with eight permuted player slots.

Only this changed flow runs. Native services are ABI stubs in owned emulated
memory; this is not gameplay/service-capacity evidence. No game access,
receipt, fingerprint, full regression or installation.
"""
from validate_loadout_consumers import READY,BLOCKED
from validate_loadout_setup import countdown_source
from validate_loadout_setup import resource_owner_source
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_mode as g
import generate_loadout_consumers as consumers
from validate_loadout_consumers import (Flow,Binding,Image as ConsumerImage,Addresses,
    GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,ENGINE,MAPS,ROSTER,STORAGE,PEER,SP,STOP,NAMES,R,U32,U64)
from validate_loadout_setup import SetupAddresses,Placement,GroupAddresses,SETUP,record_source
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

MODE=CODE+0x90000
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','handler_offset','mode','open')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class ModeFlow(Flow):
    def __init__(self,dll,consumer,image,artifact):
        super().__init__(consumers.build(),dll,consumer)
        self.points=set();self.mode_image=image;self.artifact=artifact;self.observed=[];self.unwound=False
        self.cookie=0x9a637cb415;self.map(ENGINE,0x600000)
        self.map(MODE,image.bytes);self.write(MODE,bytes(image.data[:image.bytes]));self.map(SP-0x1000,0x2000)
        capture=g.Capture()
        for source in artifact['sources']:
            for ins in capture.md.disasm(source['data'],source['start']):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not any(b<=target<e for b,e in g.GROUPS):
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for op in ins.operands:
                    if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                        target=ins.address+ins.size+ins.disp;self.map(GAME+target,16)
                        if ins.mnemonic=='lea':continue
                        data=U64(self.cookie) if target==0x263c010 else capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff)
                        self.write(GAME+target,data)
        self.write(GAME+0x3326468,U64(ROSTER))
        self.write(ROSTER+0xd0,U64(ENGINE+0x50000)+U32(16)+U32(0xffffffff)+U32(1))
        self.write(ENGINE+0x50000,b'\xff'*128)
        for i in range(8):
            self.write(ENGINE+0x50000+i*8,U32(0x1000+i)+U32(i))
            self.write(WIDGETS+i*0x1ee18+0x1edf8,U32(0x1000+i))
            self.write(WIDGETS+i*0x1ee18+0x1ee00,U64(PEER+i))
        self.write(MAPS,struct.pack('<16I',*([self.order.index(n) for n in range(8)]+self.order)))
        self.write(SCREEN+8,U32(0));self.write(SCREEN+0x27d4,U32(3));self.write(SCREEN+0x27fe,b'\x01')
        self.write(ENGINE+0x4ec0,U32(1))
        # Preserve distinct API tables; service stubs never dereference native
        # targets or call a real client. These are fixture-owned vtables.
        api=ENGINE+0x700000;self.map(api,0x3000)
        self.write(GAME+0x3326308,U64(api));self.write(GAME+0x3326318,U64(api+0x1000))
        self.write(api+0x10,U64(api+0x2000))
        for location,target in ((api+0x2628,GAME+0x3001100),(api+0x1288,GAME+0x3001110),(api+0x1338,GAME+0x3001120)):
            self.write(location,U64(target));self.external.add(target);self.map(target,1);self.write(target,b'\xc3')

    def step(self,uc,address,size,user):
        if address==MODE+self.artifact['mapping'][0x147176d] and not self.unwound:
            values=[self.value(n) for n in NAMES]
            for n in range(6,10):
                value=self.value(f'xmm{n}');values.extend((value&((1<<64)-1),value>>64))
            registers=(c.c_uint64*16)(*values);stack=(c.c_ubyte*0x400).from_buffer_copy(self.read(SP-0x300,0x400))
            result=self.dll.mode_unwind(c.byref(self.mode_image),address-MODE,self.value('rsp')-SP,registers,stack,STOP)
            g.need(result==0,f'Mode unwind failed: {result}');self.unwound=True
        rcx,rdx,r8=self.value('rcx'),self.value('rdx'),self.value('r8')
        if address==GAME+0x2088770:g.need(rcx==self.cookie,'Mode GS cookie mismatch')
        if address in (GAME+0x139c970,GAME+0x189e080,GAME+0x1451100):self.observed.append((address-GAME,rcx,rdx,r8))
        if address==GAME+0xbde430:
            g.need(rcx==0xfbc8e61e and self.read(r8+4,4)==U32(4),'Event argument type was widened as player count')
            self.observed.append((address-GAME,rcx,rdx,r8))
        super().step(uc,address,size,user)
        if address==GAME+0x173a120:self.write(rcx,bytes(16));uc.reg_write(R('rax'),rcx)
        elif address in (GAME+0x607610,GAME+0x606820):uc.reg_write(R('rax'),1)

    def run(self,offset,mode=0,notify=0):
        self.uc.reg_write(R('xmm9'),0x66660009+(0xaaaa0009<<64));self.uc.reg_write(R('r8'),notify)
        try:self.invoke(MODE-CODE+offset,mode)
        except Exception as error:
            off=self.value('rip')-MODE
            source=max(((v,k) for k,v in self.artifact['mapping'].items() if v<=off),default=(0,0))[1]
            regs={n:hex(self.value(n)) for n in ('rip','rax','rbx','rcx','rdx','rsi','rdi','r8','r9','r11','r12','r13','r14','r15','rsp')}
            raise AssertionError(f'Saved mode instruction {source:X}, registers={regs}: {error}') from error


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_mode_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        command += [g.PROJECT/'mod/src'/n for n in ('ep_session_code.cpp','ep_loadout_lifecycle.cpp','ep_loadout_consumers.cpp','ep_loadout_setup.cpp','ep_loadout_group.cpp','ep_loadout_interactions.cpp','ep_loadout_refresh.cpp','ep_loadout_records.cpp','ep_loadout_frame.cpp','ep_loadout_mode.cpp','ep_loadout_control.cpp','ep_loadout_state.cpp','ep_loadout_prompt.cpp','ep_loadout_countdown.cpp','ep_loadout_resources.cpp','ep_loadout_resource_owner.cpp','ep_loadout_resource_tick.cpp','ep_loadout_resource_events.cpp','ep_loadout_resource_ownership.cpp','ep_loadout_resource_sync.cpp','ep_loadout_resource_signals.cpp','ep_loadout_resource_actions.cpp','ep_loadout_resource_main.cpp')]
        command += [g.PROJECT/'tests'/n for n in ('loadout_consumers_dll.cpp','loadout_setup_dll.cpp','loadout_mode_dll.cpp')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.mode_build.argtypes=[c.POINTER(Binding),c.POINTER(Image)]
    dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.mode_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer binding failed')
    binding.lifecycle.code=MODE;image=Image();g.need(dll.mode_build(c.byref(binding),c.byref(image))==0,'Mode binding failed')
    artifact=g.build();f=ModeFlow(dll,consumer,image,artifact)
    widgets=[WIDGETS+i*0x1ee18 for i in range(8)]
    f.run(image.open)
    g.need(f.read(SCREEN+8,4)==U32(1) and f.read(SCREEN+0x273996,1)==b'\x01','Open wrapper did not change mode')
    g.need([x[2] for x in f.observed if x[0]==0x139c970]==f.order,'Mode notifications omitted or confused extra network slots')
    g.need([(x[1],x[2],x[3]) for x in f.observed if x[0]==0x189e080]==[(w,1,1) for w in widgets],'Open omitted player widgets')
    f.observed.clear();f.run(image.mode,0,1)
    g.need(f.read(SCREEN+8,4)==U32(0) and f.unwound,'Return mode/unwind path missed')
    g.need([(x[1],x[2],x[3]) for x in f.observed if x[0]==0x189e080]==[(w,0,1) for w in widgets],'Return omitted player widgets')
    g.need([x[1] for x in f.observed if x[0]==0x1451100 and x[1] in widgets]==widgets,'Return omitted widget animations')
    g.need(sum(x[0]==0xbde430 for x in f.observed)==1,'Native event type path missed')
    g.need(f.read(WIDGETS+0x5834,4)==U32(1) and f.read(WIDGETS+0x1ee08,4)==U32(1),'Local mapped widget state did not update')
    for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
        g.need(f.read(SCREEN+begin,end-begin)==f.inline[begin:end],'Mode touched old inline storage/maps')
    g.need(f.read(WIDGETS+8*0x1ee18,16)==b'\x7c'*16,'Mode crossed widget capacity')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=SETUP
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),CODE+0x70000,CODE+0x80000,MODE,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,CODE+0xd0000,countdown_source(),CODE+0xe0000,CODE+0xf0000,resource_owner_source(),CODE+0x110000,CODE+0x120000,CODE+0x130000,CODE+0x140000,CODE+0x150000,CODE+0x160000,CODE+0x170000)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one eight-player open/return mode flow and common preparation',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
