"""One saved screen-exit -> selection-commit flow in owned emulator memory.

Execute the changed C++-emitted image, use network record 7 and equipment ordinal
6, and unwind its nested delayed-save frame with Windows. Engine/resource
services are explicit test doubles. No full Mod build, old suites or game access.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_control as g
from generate_loadout_links import build as links
from validate_loadout_control import ControlAddresses,Image,CONTROL,Binding,MAPS,ROSTER,STORAGE
from validate_loadout_setup import record_source
from validate_loadout_lifecycle import (u,Addresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,
    STACK,SP,STOP,ENGINE,NAMES,R,U32,U64)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP


class ExitFlow:
    def __init__(self,dll,image,artifact):
        self.uc=u.Uc(u.UC_ARCH_X86,u.UC_MODE_64);self.pages=set();self.external={};self.calls=[]
        self.dll=dll;self.image=image;self.artifact=artifact;self.unwound=False;self.stop=None
        self.source=record_source();capture=g.Capture()
        for address,size in ((SCREEN,0x2739d0),(RECORDS,8*0x9f0+16),(WIDGETS,8*0x1ee18+16),
                             (ENGINE,0x200000),(ROSTER,0x1000),(STORAGE,0x680),(MAPS,64),
                             (STACK,0x3000),(STOP,1),(REJECT,1),(CONTROL,image.bytes)):
            self.map(address,size)
        # Map only this changed pair's native globals and service stand-ins.
        for source in artifact['sources'][3:]:
            for ins in capture.md.disasm(source['data'],source['start']):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not any(b<=target<e for b,e in g.GROUPS):self.service(GAME+target,target)
                for op in ins.operands:
                    if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                        target=ins.address+ins.size+ins.disp;self.map(GAME+target,max(16,op.size))
                        if ins.mnemonic!='lea':self.write(GAME+target,U64(ENGINE) if op.size==8 else U32(0xffffffff))
        blob=bytearray(image.data[:image.bytes]);routed=[]
        # Consume the same group-local links as production; the three preexisting
        # cleanup/reset bodies are stand-ins, not subjects of this focused test.
        for source,target,off,nxt,rva,entry in links():
            if source!=8:continue
            g.need(rva in (0x662880,0x662400,0x1467330),'Unexpected exit sibling')
            at=CODE+0x400000+len(routed)*16;self.service(at,rva)
            struct.pack_into('<i',blob,off,at-(CONTROL+nxt));routed.append(rva)
            self.external.pop(GAME+rva,None)
        g.need(set(routed)=={0x662880,0x662400,0x1467330},'Missing group-local exit link')
        self.write(CONTROL,blob)
        self.write(GAME+0x3326468,U64(ROSTER));self.write(GAME+0x33264f8,U64(ENGINE))
        self.write(GAME+0x3483c20,U32(0xffffffff));self.write(GAME+0x3483c34,U32(0xffffffff))
        self.write(GAME+0x348e3fc,U32(1));self.write(ENGINE+0x10,U32(1))
        self.write(ENGINE+0x17a298,U32(0xffffffff))
        self.write(ROSTER+0x84,U32(8)+U32(8))
        for i in range(8):
            desc=ENGINE+0xb0000+i*32
            self.write(STORAGE+i*8,U64(desc));self.write(desc+8,U32(0x1000+i));self.write(desc+0x14,U32(1))
            self.write(STORAGE+0x580+i*32,U32(100+i)+U32(0xff))
        for header,table,ordinal in ((ROSTER+0xd0,ENGINE+0xa0000,0),(ENGINE+0x930,ENGINE+0x90000,6)):
            self.write(header,U64(table)+U32(16)+U32(0xffffffff)+U32(1))
            self.write(table,b'\xff'*128);self.write(table,U32(0x1000)+U32(ordinal))
        self.write(SCREEN+0x27d0,U32(7)+U32(0xffffffff))
        self.write(SCREEN+0x27fe,b'\x01');self.write(SCREEN+0x2808,b'\x01')
        self.write(RECORDS+7*0x9f0+0x788,U32(0x707))
        self.write(WIDGETS+0x1edf0,U64(ENGINE+0x80000))
        self.write(ENGINE+0x80000+0x788,U32(1))
        self.map(GAME+0x37cb470,0x130)
        self.write(GAME+0x37cb470+0x118,U64(ENGINE+0x81000)+U32(1))
        self.write(ENGINE+0x81000,U32(0xc0ffee));self.write(self.source.equipment+6*0x40+0x10,U32(0xc0ffee))
        # The native actor/timer catalog is NOT a player bank. Supply its backing
        # explicitly; no claimed engine capacity follows from these fixtures.
        self.write(ENGINE+0x24,U32(8))
        for i in range(8):
            actor=ENGINE+0xc0000+i*32;self.write(ENGINE+0x50+i*8,U64(actor))
            self.write(actor+0x10,U32(0x900+i));self.write(ENGINE+0x12ee4+i*0x54,b'\x01')
        self.forbidden=[(SCREEN+0x10,SCREEN+0x27d0),(SCREEN+0x53a78,SCREEN+0xcf2d8),
                        (ROSTER+0xe8,ROSTER+0x428),(ENGINE+0xa7c,ENGINE+0xb7c)]
        for begin,end in self.forbidden:self.write(begin,b'\xa5'*(end-begin))
        self.write(RECORDS+8*0x9f0,b'\x6b'*16);self.write(WIDGETS+8*0x1ee18,b'\x7c'*16)
        self.uc.hook_add(u.UC_HOOK_CODE,self.step)
        self.uc.hook_add(u.UC_HOOK_MEM_READ|u.UC_HOOK_MEM_WRITE,self.memory)

    def map(self,address,size):
        for page in range(address&~4095,(address+size+4095)&~4095,4096):
            if page not in self.pages:self.uc.mem_map(page,4096);self.pages.add(page)
    def write(self,address,data):self.uc.mem_write(address,bytes(data))
    def read(self,address,size):return bytes(self.uc.mem_read(address,size))
    def value(self,name):return self.uc.reg_read(R(name))
    def service(self,address,rva):
        self.map(address,1);self.write(address,b'\xc3');self.external[address]=rva
    def memory(self,uc,access,address,size,value,user):
        g.need(not any(address<end and begin<address+size for begin,end in self.forbidden),
               f'Exit accessed old inline storage at {address:x}')
    def step(self,uc,address,size,user):
        if address in (STOP,REJECT):self.stop=address;uc.emu_stop();return
        g.need(address not in (GAME+0x1467790,GAME+0x1467b90,GAME+0x662880,GAME+0x662400,GAME+0x1467330),
               'Exit called an original relocated body')
        if address==CONTROL+self.artifact['mapping'][0x14679e0] and not self.unwound:
            registers=(c.c_uint64*8)(*(self.value(n) for n in NAMES))
            stack=(c.c_ubyte*0x800).from_buffer_copy(self.read(SP-0x400,0x800))
            result=self.dll.exit_unwind(c.byref(self.image),address-CONTROL,self.value('rsp')-SP,registers,stack,CONTROL,STOP)
            g.need(result==0,f'Nested exit unwind failed: {result}');self.unwound=True
        if address not in self.external:return
        rva=self.external[address];args=tuple(self.value(n) for n in ('rcx','rdx','r8','r9'));self.calls.append((rva,*args))
        if rva==0xfd9ba0:self.write(args[0],U32(args[1]))
        for name in ('rax','rcx','rdx','r8','r9','r10','r11'):uc.reg_write(R(name),0)
    def run(self):
        self.write(SP,U64(STOP));self.uc.reg_write(R('rsp'),SP);self.uc.reg_write(R('rcx'),SCREEN)
        for i,name in enumerate(NAMES):self.uc.reg_write(R(name),0x11110000+i*0x101)
        self.uc.emu_start(CONTROL+self.image.exit_screen,0,count=20000)
        g.need(self.stop==STOP and self.value('rsp')==SP+8,'Exit did not return')
        for i,name in enumerate(NAMES):g.need(self.value(name)==0x11110000+i*0x101,'Exit damaged a nonvolatile register')
        selected=RECORDS+7*0x9f0
        g.need([x[1] for x in self.calls if x[0] in (0x1751350,0xb4eec0)]==[selected,selected],'Selected record seven was lost')
        g.need(any(x[0]==0x66f190 and x[2:]==(0x1000,selected+0x188,0x707) for x in self.calls),'Wrong submitted record fields')
        g.need(any(x[0]==0x13620a0 and x[3]==selected for x in self.calls),'Wrong record handoff')
        g.need(self.read(ENGINE+0x80000+0x78c,4)==U32(0xc0ffee),'Equipment ordinal six/local widget mismatch')
        g.need(self.read(STORAGE+0x584,4)==U32(0xb5),'Exit flag updates missed owned B storage')
        g.need([x[1] for x in self.calls if x[0]==0xfd97e0]==list(range(0x900,0x908)),'Native actor cleanup changed')
        g.need([x[0] for x in self.calls if x[0] in (0x662880,0x662400,0x1467330)]==[0x662880,0x662400,0x1467330],'Cleanup order changed')
        g.need(self.unwound and self.read(SCREEN+0x2810,1)==b'\x01','Selection commit did not finish')
        g.need(self.read(RECORDS+8*0x9f0,16)==b'\x6b'*16 and self.read(WIDGETS+8*0x1ee18,16)==b'\x7c'*16,'Owned bank overflow')


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_exit_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(parents=True,exist_ok=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        command += [g.PROJECT/'mod/src'/('ep_'+name+'.cpp') for name in ('session_code','loadout_consumers','loadout_records','loadout_control')]
        command += [g.PROJECT/'tests/loadout_exit_dll.cpp','-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.exit_build.argtypes=[c.POINTER(ControlAddresses),c.POINTER(Image)]
    dll.exit_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64,c.c_uint64]
    binding=Binding(Addresses(GAME,CONTROL,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    a=ControlAddresses(binding,*(CODE+0x300000+i*16 for i in range(6)),record_source());image=Image()
    result=dll.exit_build(c.byref(a),c.byref(image));g.need(result==0,f'Control image build/seal rejected: {result}')
    ExitFlow(dll,image,g.build()).run()
    print(json.dumps(dict(passed=True,scope='one exit -> selection commit flow, network record 7, equipment ordinal 6, nested Windows unwind',
                         engine_services='test doubles',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
