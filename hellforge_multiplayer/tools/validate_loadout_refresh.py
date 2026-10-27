"""One input -> refresh -> close flow across the actual prepared image links.

Owned emulator memory and ABI stubs only. One nested chained-unwind snapshot,
one common READY/discard cycle. No game access or full regression.
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
import generate_loadout_refresh as g
import generate_loadout_interactions as interaction_generator
import generate_loadout_consumers as consumers
from validate_loadout_consumers import (Binding,Image as ConsumerImage,Flow,Addresses,GAME,CODE,SCREEN,
    RECORDS,WIDGETS,REJECT,ENGINE,NAMES,R,U64,U32,MAPS,ROSTER,STORAGE)
from validate_loadout_interactions import Image as InteractionImage,InteractionAddresses,INTERACTIONS,REFRESH
from validate_loadout_setup import SetupAddresses,Placement,GroupAddresses,SETUP,record_source
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

class RefreshAddresses(c.Structure):
    _fields_=[('common',Binding),('close_entry',c.c_uint64)]
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','handler_offset')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class RefreshFlow(Flow):
    def __init__(self,dll,consumer_image,interaction_artifact,interaction_image,artifact,image):
        super().__init__(consumers.build(),dll,consumer_image)
        self.points=set();self.refresh_image=image;self.observed=[];self.cookie=0x6745ab23901f
        self.unwind_point=REFRESH+artifact['mapping'][0x146ea7b];self.unwound=False;self.refresh_entered=False
        capture=g.Capture();sources=interaction_artifact['sources']+[dict(start=g.START,end=g.END,data=artifact['source'])]
        groups=interaction_generator.GROUPS+((g.START,g.END),)
        for source in sources:
            for ins in capture.md.disasm(source['data'],source['start']):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not any(b<=target<e for b,e in groups):
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for op in ins.operands:
                    if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP and ins.mnemonic!='lea':
                        target=ins.address+ins.size+ins.disp;self.map(GAME+target,max(16,op.size))
                        data=U64(self.cookie) if target==0x263c010 else capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff)
                        self.write(GAME+target,data)
        self.write(GAME+0x3326468,U64(ROSTER));self.write(SCREEN+0x27d0,U32(7))
        # Refresh/close use the optional control at +1EE00, distinct from
        # the update consumer's peer control at +1EDF0.
        for i in range(8):self.write(WIDGETS+i*0x1ee18+0x1ee00,U64(1))
        for at,item in ((INTERACTIONS,interaction_image),(REFRESH,image)):
            self.map(at,item.bytes);self.write(at,bytes(item.data[:item.bytes]))

    def registers(self):
        xmm=[v for i in range(6,9) for v in (self.value(f'xmm{i}')&((1<<64)-1),self.value(f'xmm{i}')>>64)]
        return (c.c_uint64*14)(*(self.value(n) for n in NAMES),*xmm)

    def step(self,uc,address,size,user):
        if address==REFRESH:
            self.refresh_entered=True;self.entry_sp=self.value('rsp');self.entry_registers=self.registers()
            self.entry_return=struct.unpack('<Q',self.read(self.entry_sp,8))[0]
        if address==self.unwind_point and not self.unwound:
            stack=(c.c_ubyte*512).from_buffer_copy(self.read(self.entry_sp-256,512))
            status=self.dll.refresh_unwind(c.byref(self.refresh_image),address-REFRESH,self.value('rsp')-self.entry_sp,
                self.registers(),stack,self.entry_registers,self.entry_return)
            g.need(status==0,f'Nested refresh unwind failed: {status}');self.unwound=True
        if address in self.external:
            rcx,rdx,r8=self.value('rcx'),self.value('rdx'),self.value('r8')
            if address-GAME in (0x189e2f0,0x189ceb0,0x18d8710,0x18932f0):self.observed.append((address-GAME,rcx,rdx,r8))
            if address==GAME+0x1896a00:self.write(rdx,U32(0x37))
            if address==GAME+0x2088770:g.need(rcx==self.cookie,'Refresh GS cookie mismatch')
        super().step(uc,address,size,user)
        if address==GAME+0x189c250:uc.reg_write(R('rax'),1)


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_refresh_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        command += [g.PROJECT/'mod/src'/n for n in ('ep_session_code.cpp','ep_loadout_lifecycle.cpp','ep_loadout_consumers.cpp','ep_loadout_setup.cpp','ep_loadout_group.cpp','ep_loadout_interactions.cpp','ep_loadout_refresh.cpp','ep_loadout_records.cpp','ep_loadout_frame.cpp','ep_loadout_mode.cpp','ep_loadout_control.cpp','ep_loadout_state.cpp','ep_loadout_prompt.cpp','ep_loadout_countdown.cpp','ep_loadout_resources.cpp','ep_loadout_resource_owner.cpp','ep_loadout_resource_tick.cpp','ep_loadout_resource_events.cpp','ep_loadout_resource_ownership.cpp','ep_loadout_resource_sync.cpp','ep_loadout_resource_signals.cpp')]
        command += [g.PROJECT/'tests'/n for n in ('loadout_consumers_dll.cpp','loadout_setup_dll.cpp','loadout_interactions_dll.cpp','loadout_refresh_dll.cpp')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()))
    dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64];dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)]
    dll.interaction_build.argtypes=[c.POINTER(InteractionAddresses),c.POINTER(InteractionImage)]
    dll.refresh_build.argtypes=[c.POINTER(RefreshAddresses),c.POINTER(Image)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.refresh_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.POINTER(c.c_uint64),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer binding failed')
    binding.lifecycle.code=INTERACTIONS;ia=InteractionAddresses(binding,REFRESH);interactions=InteractionImage()
    g.need(dll.interaction_build(c.byref(ia),c.byref(interactions))==0,'Interaction link failed')
    binding.lifecycle.code=REFRESH;ra=RefreshAddresses(binding,INTERACTIONS+interactions.close);image=Image()
    g.need(dll.refresh_build(c.byref(ra),c.byref(image))==0,'Refresh link failed')
    f=RefreshFlow(dll,consumer,interaction_generator.build(),interactions,g.build(),image)
    f.invoke(INTERACTIONS-CODE+interactions.input,ENGINE+0x30000)
    g.need(f.refresh_entered and f.unwound,'Input bypassed the bound refresh')
    widgets=[WIDGETS+i*0x1ee18 for i in range(8)]
    g.need([(x[1],x[2]) for x in f.observed if x[0]==0x189e2f0]==[(w,1) for w in widgets]+[(w,0) for w in widgets],'Refresh/close lost a configured widget')
    g.need([x[1] for x in f.observed if x[0]==0x189ceb0]==widgets+widgets,'Nested widget refresh did not use shared storage')
    g.need([x[1:] for x in f.observed if x[0]==0x18d8710]==[(SCREEN+0xd2850,0x37,RECORDS+7*0x9f0)],'Eighth record was not passed to the native editor')
    choices=[WIDGETS+0x63738-0x53a78+i*0x12a8-0x1288 for i in range(4)]
    g.need([x[1] for x in f.observed if x[0]==0x18932f0]==choices+choices,'Equipment choices changed with player capacity')
    g.need(f.read(SCREEN+0x273990,1)==b'\0','Nested close did not restore edit state')
    for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
        g.need(f.read(SCREEN+begin,end-begin)==f.inline[begin:end],'Nested refresh used old inline arrays/maps')
    g.need(f.read(RECORDS+8*0x9f0,16)==b'\x6b'*16 and f.read(WIDGETS+8*0x1ee18,16)==b'\x7c'*16,'Capacity boundary crossed')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=SETUP
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,INTERACTIONS,REFRESH,record_source(),CODE+0x70000,CODE+0x80000,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,CODE+0xd0000,countdown_source(),CODE+0xe0000,CODE+0xf0000,resource_owner_source(),CODE+0x110000,CODE+0x120000,CODE+0x130000,CODE+0x140000,CODE+0x150000)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one eight-slot input/refresh/close flow and common preparation',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
