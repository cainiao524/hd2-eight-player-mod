"""One five-slot native navigation -> edit -> close smoke flow.

Non-power-of-two capacity exercises both wrap directions. ABI stubs and
owned emulator RAM only; one unwind snapshot and common READY/discard cycle.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_interactions as g
import generate_loadout_consumers as consumers
from validate_loadout_consumers import (Binding,Image as ConsumerImage,Flow,Addresses,GAME,CODE,
    SCREEN,RECORDS,WIDGETS,REJECT,ENGINE,SP,NAMES,R,U64,U32,STOP,MAPS,ROSTER,STORAGE)
from validate_loadout_setup import SetupAddresses,Placement,GroupAddresses,SETUP,record_source
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

INTERACTIONS=CODE+0x50000
REFRESH=CODE+0x60000
class InteractionAddresses(c.Structure):
    _fields_=[('common',Binding),('refresh_entry',c.c_uint64)]
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','input','edit','close')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class InteractionsFlow(Flow):
    def __init__(self,dll,consumer_image,artifact,image):
        super().__init__(consumers.build(),dll,consumer_image)
        self.points=set();self.interactions=image;self.input_action=8;self.observed=[]
        # The existing Windows helper consumes only this identical metadata
        # prefix and data region. Copy into its actual struct type for FFI.
        self.unwind_image=ConsumerImage.from_buffer_copy(image)
        self.unwind_point=INTERACTIONS+artifact['mapping'][0x146dd44];self.unwound=False
        capture=g.Capture()
        for source in artifact['sources']:
            for ins in capture.md.disasm(source['data'],source['start']):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not any(b<=target<e for b,e in g.GROUPS):
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for op in ins.operands:
                    if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                        target=ins.address+ins.size+ins.disp
                        if ins.mnemonic=='lea':continue
                        self.map(GAME+target,max(16,op.size))
                        self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        self.write(GAME+0x3326468,U64(ROSTER));self.write(ROSTER+0x80,U32(5)+U32(5)+U32(1))
        self.write(ROSTER+0xd0,U64(ENGINE+0x70000));self.write(ROSTER+0xd8,U32(1)+U32(0xffffffff)+U32(1))
        self.write(ENGINE+0x70000,U32(0x1000)+U32(0))
        self.map(ENGINE+0xb9000,0x4000);self.write(ENGINE+0x1ce0,U32(1))
        self.write(ENGINE+0xb9ce8,U32(0xcafe)+U32(0x12345678))
        self.write(SCREEN+0x2739c8,U32(3));self.write(SCREEN+0x27d0,U32(4))
        self.write(RECORDS+5*0x9f0,b'\x6b'*(3*0x9f0));self.write(WIDGETS+5*0x1ee18,b'\x7c'*(3*0x1ee18))
        self.write(INTERACTIONS,bytes(image.data[:image.bytes])) if INTERACTIONS in self.pages else self._image(image)

    def _image(self,image):
        self.map(INTERACTIONS,image.bytes);self.write(INTERACTIONS,bytes(image.data[:image.bytes]))

    def step(self,uc,address,size,user):
        if address==self.unwind_point and not self.unwound:
            xmm=[v for i in range(6,9) for v in (self.value(f'xmm{i}')&((1<<64)-1),self.value(f'xmm{i}')>>64)]
            registers=(c.c_uint64*14)(*(self.value(n) for n in NAMES),*xmm)
            stack=(c.c_ubyte*512).from_buffer_copy(self.read(SP-256,512))
            result=self.dll.ui_unwind(c.byref(self.unwind_image),address-INTERACTIONS,self.value('rsp')-SP,registers,stack,STOP)
            g.need(result==0,f'Input unwind failed: {result}');self.unwound=True
        if address in self.external and address-GAME in (0x1899eb0,0x1895770,0x875ec0,0x18932f0,0x189e2f0):
            self.observed.append((address-GAME,self.value('rcx'),self.value('rdx'),self.value('r8')))
        super().step(uc,address,size,user)
        if address==GAME+0x189c250:uc.reg_write(R('rax'),self.input_action)
        if address==GAME+0x18d5a90:uc.reg_write(R('rax'),3)

    def operation(self,entry):
        self.invoke(INTERACTIONS-CODE+entry,ENGINE+0x30000)


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_interactions_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        command += [g.PROJECT/'mod/src'/n for n in ('ep_session_code.cpp','ep_loadout_lifecycle.cpp','ep_loadout_consumers.cpp','ep_loadout_setup.cpp','ep_loadout_group.cpp','ep_loadout_interactions.cpp','ep_loadout_refresh.cpp','ep_loadout_records.cpp','ep_loadout_frame.cpp','ep_loadout_mode.cpp','ep_loadout_control.cpp')]
        command += [g.PROJECT/'tests'/n for n in ('loadout_consumers_dll.cpp','loadout_setup_dll.cpp','loadout_interactions_dll.cpp')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()))
    dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage)];dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)]
    dll.interaction_build.argtypes=[c.POINTER(InteractionAddresses),c.POINTER(Image)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.ui_unwind.argtypes=[c.POINTER(ConsumerImage),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,5,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer))==0,'Consumer binding failed')
    binding.lifecycle.code=INTERACTIONS;linked=InteractionAddresses(binding,REFRESH)
    image=Image();g.need(dll.interaction_build(c.byref(linked),c.byref(image))==0,'Interaction binding failed')
    f=InteractionsFlow(dll,consumer,g.build(),image)
    for action,expected in ((8,4),(8,0),(7,4)):
        f.input_action=action;f.operation(image.input)
        g.need(struct.unpack('<I',f.read(SCREEN+0x2739c8,4))[0]==expected,'Configured focus did not wrap')
        target=0x1895770 if action==7 else 0x1899eb0
        member=0x595f0 if action==7 else 0x593d0
        g.need(f.observed[-1][:2]==(target,WIDGETS+expected*0x1ee18+member-0x53a78),'Navigation called the wrong widget')
    f.write(SCREEN+0x2818,U32(3)+U32(2));f.write(SCREEN+0x24b4e8,U32(0xcafe));f.operation(image.edit)
    g.need(f.read(RECORDS+4*0x9f0+0x128,4)==U32(0x12345678),'Fifth record edit was lost')
    g.need(f.observed[-1]==(0x875ec0,ENGINE,0x1000,0x12345678),'Native edit service arguments changed')
    for i in range(4):f.write(WIDGETS+0x63738-0x53a78+i*0x12a8,b'\x08\0')
    f.observed=[];f.operation(image.close)
    g.need([x[1] for x in f.observed if x[0]==0x189e2f0]==[WIDGETS+i*0x1ee18 for i in range(5)],'Close did not update all configured widgets')
    g.need([x[1] for x in f.observed if x[0]==0x18932f0]==[WIDGETS+0x63738-0x53a78+i*0x12a8-0x1288 for i in range(4)],'Inner equipment count changed')
    for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
        g.need(f.read(SCREEN+begin,end-begin)==f.inline[begin:end],'Interaction touched old inline storage')
    g.need(f.read(RECORDS+5*0x9f0,3*0x9f0)==b'\x6b'*(3*0x9f0) and f.read(WIDGETS+5*0x1ee18,3*0x1ee18)==b'\x7c'*(3*0x1ee18),'Configured capacity exceeded')
    g.need(f.unwound,'Input unwind point missed')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=SETUP
    for i in range(5):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,INTERACTIONS,REFRESH,record_source(),CODE+0x70000,CODE+0x80000,CODE+0x90000,CODE+0xa0000)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one five-slot navigation/edit/close flow and common preparation',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
