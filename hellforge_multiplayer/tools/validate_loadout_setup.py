"""One owned-memory setup -> update -> action integration smoke flow.

ABI stubs do not render UI or verify layout. One setup unwind snapshot and
one all-image READY/discard cycle; no full regression or game access.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_setup as g
import generate_loadout_consumers as consumers
from validate_loadout_consumers import (Binding,Image as ConsumerImage,Flow,MAPS,ROSTER,STORAGE,PEER,
    Addresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,ENGINE,SP,NAMES,R,U64,U32,STOP)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

SETUP=CODE+0x30000
class Placement(c.Structure):
    _fields_=[(n,c.c_float) for n in ('offset_x','offset_y','anchor_x','anchor_y','pivot_x','pivot_y')]
class SetupAddresses(c.Structure):
    _fields_=[('common',Binding),('placements',Placement*8)]
class SetupImage(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','handler_offset','placements_offset')]+[('data',c.c_ubyte*g.MAX_IMAGE)]
class RecordSource(c.Structure):
    _fields_=[(n,c.c_uint64) for n in ('manager','actors','equipment','status')]

def record_source():return RecordSource(ENGINE,ENGINE+0x60000,ENGINE+0x61000,ENGINE+0x62000)

class GroupAddresses(c.Structure):
    _fields_=[('setup',SetupAddresses),('lifecycle_code',c.c_uint64),('consumers_code',c.c_uint64),('interactions_code',c.c_uint64),('refresh_code',c.c_uint64),('record_source',RecordSource),('records_code',c.c_uint64)]


class SetupFlow(Flow):
    def __init__(self,artifact,dll,image,setup_artifact,setup_image):
        super().__init__(artifact,dll,image)
        self.points=set();self.setup_image=setup_image;self.setup_point=SETUP+setup_artifact['mapping'][0x1466af0]
        self.setup_unwound=False;self.setup_calls=[];self.attachments=[];self.cookie=0x6745ab23901f
        capture=g.Capture()
        for ins in capture.md.disasm(setup_artifact['source'],g.START):
            if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                target=ins.operands[0].imm
                if not g.START<=target<g.END:
                    self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
            for op in ins.operands:
                if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                    target=ins.address+ins.size+ins.disp;self.map(GAME+target,max(16,op.size))
                    if target==0x263c010:data=U64(self.cookie)
                    elif target<0x3000000:data=capture.read(target,op.size)
                    else:data=U64(ENGINE) if op.size==8 else bytes(op.size)
                    self.write(GAME+target,data)
        self.map(SETUP,setup_image.bytes);self.write(SETUP,bytes(setup_image.data[:setup_image.bytes]))
        self.write(SCREEN,U64(ENGINE+0x70000))
        self.write(ENGINE+0x162c8,U64(ENGINE+0x60000));self.write(ENGINE+0x6b398,U64(PEER))
        self.map(ENGINE+0x55f000,0x1000)
        # Native menu-control capacity 16, independent of the player loop.
        self.write(SCREEN+0x1d9e0+0x36028,b'\xff'*64)
        # Force native setup to replace stale map contents, including slots 4..7.
        self.write(MAPS,b'\xa5'*64)

    def step(self,uc,address,size,user):
        if address==self.setup_point and not self.setup_unwound:
            xmm=self.value('xmm6');values=(c.c_uint64*10)(*(self.value(n) for n in NAMES),xmm&((1<<64)-1),xmm>>64)
            stack=(c.c_ubyte*1024).from_buffer_copy(self.read(SP-512,1024))
            g.need(self.dll.setup_unwind(c.byref(self.setup_image),address-SETUP,self.value('rsp')-SP,values,stack,STOP)==0,'Setup unwind/cookie metadata mismatch')
            self.setup_unwound=True
        if address in self.external:
            rcx,rdx=self.value('rcx'),self.value('rdx')
            if address==GAME+0x2088770:g.need(rcx==self.cookie,'Native setup cookie check changed')
            if WIDGETS<=rcx<WIDGETS+8*0x1ee18 and (rcx-WIDGETS)%0x1ee18==0 and address-GAME in (0x189ae00,0x14476a0,0x144f160,0x144f0d0):
                self.setup_calls.append((address-GAME,(rcx-WIDGETS)//0x1ee18,rdx))
            if address==GAME+0x144c5c0 and rcx==SCREEN+0x2820 and WIDGETS<=rdx<WIDGETS+8*0x1ee18:
                self.attachments.append(rdx)
        super().step(uc,address,size,user)

    def setup(self):
        self.standalone_lookup=False;self.stop=None
        self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP))
        for i,n in enumerate(NAMES):self.uc.reg_write(R(n),0x11110000+i*0x101)
        for i in range(6,9):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        self.uc.reg_write(R('rcx'),SCREEN);self.uc.emu_start(SETUP,0,count=20000)
        g.need(self.stop==STOP and self.value('rsp')==SP+8,'Setup did not return normally')
        for i,n in enumerate(NAMES):g.need(self.value(n)==0x11110000+i*0x101,'Setup corrupted nonvolatile register')


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_setup_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        command += [g.PROJECT/'mod/src'/n for n in ('ep_session_code.cpp','ep_loadout_lifecycle.cpp','ep_loadout_consumers.cpp','ep_loadout_setup.cpp','ep_loadout_group.cpp','ep_loadout_interactions.cpp','ep_loadout_refresh.cpp','ep_loadout_records.cpp')]
        command += [g.PROJECT/'tests/loadout_consumers_dll.cpp',g.PROJECT/'tests/loadout_setup_dll.cpp','-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()))
    dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage)];dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)]
    dll.setup_build.argtypes=[c.POINTER(SetupAddresses),c.POINTER(SetupImage)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.setup_unwind.argtypes=[c.POINTER(SetupImage),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    setup=SetupAddresses();setup.common=Binding.from_buffer_copy(binding);setup.common.lifecycle.code=SETUP
    # Synthetic distinct coordinates exercise the ABI, not screen fit.
    for i in range(8):setup.placements[i]=Placement(i*3,111+i*5,0.138+(i%4)*0.241,0.5*(i//4),0.5,0)
    image=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(image))==0,'Consumer image rejected')
    si=SetupImage();g.need(dll.setup_build(c.byref(setup),c.byref(si))==0,'Setup image rejected')
    f=SetupFlow(consumers.build(),dll,image,g.build(),si);f.setup()
    expected=[]
    for i,placement in enumerate(setup.placements):
        pairs=struct.unpack('<3Q',bytes(placement));expected.extend([(0x189ae00,i,10)]+[(target,i,value) for target,value in zip((0x14476a0,0x144f160,0x144f0d0),pairs)])
    g.need(f.setup_calls==expected and f.attachments==[WIDGETS+i*0x1ee18 for i in range(8)],'Setup omitted/repositioned the wrong native widget')
    forward=list(struct.unpack('<8I',f.read(MAPS,32)));inverse=list(struct.unpack('<8I',f.read(MAPS+32,32)))
    g.need(forward==[0xffffffff]*3+[0]+[0xffffffff]*4 and inverse==[3]+[0xffffffff]*7,'Native setup did not reset/bind all map slots')
    f.invoke(image.update);f.invoke(image.action,PEER+7,0x35)
    g.need(list(struct.unpack('<8I',f.read(MAPS+32,32)))==f.order and f.calls[-1]==(0x1893d40,WIDGETS+7*0x1ee18+0xe670,0x35),'Setup/update/action storage diverged')
    for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
        g.need(f.read(SCREEN+begin,end-begin)==f.inline[begin:end],'Setup or consumer touched old arrays/maps')
    g.need(f.setup_unwound,'Setup unwind point was missed')
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),CODE+0x70000)
    g.need(dll.setup_group(c.byref(group))==0,'Shared READY/discard failed')
    print(json.dumps(dict(passed=True,scope='one setup/update/action flow and shared READY group',game_access=False,layout_verified=False,runtime_verified=False)))


if __name__=='__main__':main()
