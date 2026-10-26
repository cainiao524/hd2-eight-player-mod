"""One eight-slot update -> native record lookup -> player action smoke flow.

Owned emulator RAM and ABI stubs only. Three selected Windows unwind points,
one cancellable READY allocation. No regression matrix or game access.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_consumers as g
from validate_loadout_lifecycle import (Fixture,Addresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,
                                       STACK,STOP,ENGINE,SP,NAMES,R,U64,U32,u)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

MAPS,ROSTER,STORAGE,DESCS,PEER=0x250000000,0x260000000,0x260010000,0x270000000,0x710000
class Binding(c.Structure):
    _fields_=[('lifecycle',Addresses)]+[(x,c.c_uint64) for x in ('forward_map','inverse_map','roster','roster_storage')]
class Image(c.Structure):
    _fields_=[(x,c.c_uint32) for x in ('bytes','code_bytes','unwind_offset','table_offset','function_count','update','lookup','action')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class Flow(Fixture):
    def __init__(self,artifact,dll,image):
        self.uc=u.Uc(u.UC_ARCH_X86,u.UC_MODE_64);self.pages=set();self.external=set();self.calls=[]
        self.dll=dll;self.image=image;self.points={artifact['mapping'][0x146c3d1],artifact['mapping'][0x1471ae3]}
        self.lookup_point=artifact['mapping'][0x14706b6];self.lookup_checked=False
        for at,size in ((SCREEN,0x2739d0),(RECORDS,0x9f0*8+16),(WIDGETS,0x1ee18*8+16),
                        (MAPS,64),(ROSTER,0xe8),(STORAGE,0x680),(DESCS,0x1000),
                        (STACK,0x2000),(STOP,1),(REJECT,1),(ENGINE,0x80000),(CODE,image.bytes)):
            self.map(at,size)
        capture=g.Capture()
        for source in artifact['sources']:
            for i in capture.md.disasm(source['data'],source['start']):
                if (i.mnemonic=='call' or i.mnemonic.startswith('j')) and i.operands[0].type==X86_OP_IMM:
                    target=i.operands[0].imm
                    if not any(b<=target<e for b,e in g.GROUPS):
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for o in i.operands:
                    if o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP:
                        target=i.address+i.size+i.disp;self.map(GAME+target,16)
                        self.write(GAME+target,capture.read(target,o.size) if target<0x3000000 else U64(ENGINE) if o.size==8 else U32(0xffffffff))
        self.write(GAME+0x3326468,U64(ROSTER))
        # The character lookup's eight original entries are separate from the
        # session's eight identity records. Neither is a UI display ordinal.
        for i in capture.md.disasm(capture.read(0x146c47e,7),0x146c47e):
            self.write(GAME+i.address+i.size+i.disp,U64(ENGINE+0x40000))
        maps=(c.c_uint32*16)();g.need(dll.ui_maps(maps)==1,'Map initialization failed');self.write(MAPS,bytes(maps))
        self.write(ROSTER+0x80,U32(8)+U32(8)+U32(1))
        self.write(ENGINE+0x16390,U32(8));self.write(ENGINE+0x42b0,U32(1));self.write(ENGINE+0x429c,U32(14))
        self.order=[3,7,0,6,1,5,2,4]
        for i,network in enumerate(self.order):
            self.write(STORAGE+i*8,U64(DESCS+i*32));self.write(DESCS+i*32+8,U32(0x1000+i));self.write(DESCS+i*32+16,U32(100+i))
            self.write(STORAGE+0x580+i*32,U32(100+i));self.write(STORAGE+0x3c0+i*0x38,U64(PEER+i))
            self.write(ENGINE+0x16398+i*32,U64(PEER+i));self.write(ENGINE+0x163ac+i*32,U32(network))
            self.write(ENGINE+0x40000+i*0xc0,U64(PEER+i))
            self.write(RECORDS+i*0x9f0+0x9e8,U64(PEER+i));self.write(WIDGETS+i*0x1ee18+0x1edf0,U64(1))
        self.write(ENGINE+0x38,U64(ENGINE+0x20000));self.write(ENGINE+0x40,U64(ENGINE+0x21000))
        self.provider=GAME+0x3001000;self.resolver=GAME+0x3001010
        self.write(ENGINE+0x20008,U64(self.provider));self.write(ENGINE+0x21160,U64(self.resolver))
        for target in (self.provider,self.resolver):
            self.external.add(target);self.map(target,1);self.write(target,b'\xc3')
        for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
            self.write(SCREEN+begin,bytes([0xa5])*(end-begin))
        self.inline=self.read(SCREEN,0x2739d0)
        self.write(RECORDS+8*0x9f0,bytes([0x6b])*16);self.write(WIDGETS+8*0x1ee18,bytes([0x7c])*16)
        self.write(CODE,bytes(image.data[:image.bytes]));self.uc.hook_add(u.UC_HOOK_CODE,self.step)

    def step(self,uc,address,size,user):
        if address in (STOP,REJECT):self.stop=address;uc.emu_stop();return
        off=address-CODE
        if off in self.points or (self.standalone_lookup and off==self.lookup_point and not self.lookup_checked):
            xmm=[v for i in range(6,9) for v in (self.value(f'xmm{i}')&((1<<64)-1),self.value(f'xmm{i}')>>64)]
            registers=(c.c_uint64*14)(*(self.value(n) for n in NAMES),*xmm)
            stack=(c.c_ubyte*512).from_buffer_copy(self.read(SP-256,512))
            g.need(self.dll.ui_unwind(c.byref(self.image),off,self.value('rsp')-SP,registers,stack,STOP)==0,'Consumer unwind mismatch')
            self.points.discard(off)
            if off==self.lookup_point:self.lookup_checked=True
        if address in self.external:
            rcx,rdx=self.value('rcx'),self.value('rdx');rax=0
            if address==self.provider:rax=ENGINE
            elif address==self.resolver:rax=PEER+rdx-100
            elif address==GAME+0xfd9af0:rax=100+rcx-0x1000
            elif address==GAME+0xfd9ba0:self.write(rcx,U32(rdx))
            elif address==GAME+0x60b3b0:rax=0 if rdx==0x1007 else 1
            if address in (GAME+0x189ca20,GAME+0x1893d40):self.calls.append((address-GAME,rcx,rdx))
            for name in ('rax','rcx','rdx','r8','r9','r10','r11'):uc.reg_write(R(name),0)
            uc.reg_write(R('rax'),rax)

    def invoke(self,entry,rdx=0,r9=0):
        self.standalone_lookup=entry==self.image.lookup;self.stop=None
        self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP))
        for i,n in enumerate(NAMES):self.uc.reg_write(R(n),0x11110000+i*0x101)
        for i in range(6,9):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        for n,v in (('rcx',SCREEN),('rdx',rdx),('r9',r9)):self.uc.reg_write(R(n),v)
        self.uc.emu_start(CODE+entry,0,count=30000)
        g.need(self.stop==STOP and self.value('rsp')==SP+8,'Consumer did not return normally')
        for i,n in enumerate(NAMES):g.need(self.value(n)==0x11110000+i*0x101,'Consumer corrupted nonvolatile register')


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_consumers_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared',
                 g.PROJECT/'mod/src/ep_session_code.cpp',g.PROJECT/'mod/src/ep_loadout_consumers.cpp',
                 g.PROJECT/'tests/loadout_consumers_dll.cpp','-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()))
    dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(Image)];dll.ui_prepare.argtypes=[c.POINTER(Binding)]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)]
    dll.ui_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    artifact=g.build();image=Image();g.need(dll.ui_build(c.byref(binding),c.byref(image))==0,'Consumer image rejected')
    f=Flow(artifact,dll,image);f.invoke(image.update)
    inverse=list(struct.unpack('<8I',f.read(MAPS+32,32)));forward=list(struct.unpack('<8I',f.read(MAPS,32)))
    g.need(inverse==f.order and all(forward[n]==i for i,n in enumerate(inverse)),'Native update lost identity/slot mapping')
    expected=[(0x189ca20,WIDGETS+i*0x1ee18,RECORDS+i*0x9f0) for i in range(1,8)]
    g.need(f.calls==expected,'Native update did not reach all remote widgets/records')
    f.invoke(image.lookup,0x1007);g.need(f.value('rax')==RECORDS+7*0x9f0,'Native record lookup still uses inline/four-slot storage')
    f.invoke(image.action,PEER+7,0x35)
    g.need(f.calls[-1]==(0x1893d40,WIDGETS+7*0x1ee18+0xe670,0x35),'Native action targeted the wrong player')
    for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
        g.need(f.read(SCREEN+begin,end-begin)==f.inline[begin:end],'Consumer touched old inline arrays/maps')
    g.need(f.read(RECORDS+8*0x9f0,16)==bytes([0x6b])*16 and f.read(WIDGETS+8*0x1ee18,16)==bytes([0x7c])*16,'Storage boundary crossed')
    g.need(not f.points and f.lookup_checked,'Selected unwind point was not reached')
    g.need(dll.ui_prepare(c.byref(binding))==0,'Consumer READY prepare/discard failed')
    print(json.dumps(dict(passed=True,scope='one eight-slot update/lookup/action flow',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
