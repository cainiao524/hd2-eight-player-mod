"""One main-frame -> record sync -> UI flow in owned emulated memory.

Native services outside this group are ABI stubs. This does not prove game
behavior, remaining native routing, installation or publication. No receipts,
fingerprints, old-suite execution or game access.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_frame as g
import generate_loadout_mode as mode
import generate_loadout_records as records
from validate_loadout_records import (RecordsFlow,RecordsAddresses,Image as RecordsImage,
    ConsumerImage,Binding,Addresses,RecordSource,record_source,SetupAddresses,Placement,GroupAddresses,
    GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,ENGINE,MAPS,ROSTER,STORAGE,PEER,SYNC,SETUP,SP,STOP,NAMES,R,U32,U64)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

FRAME=CODE+0x80000
class FrameAddresses(c.Structure):
    _fields_=[('records',RecordsAddresses),('sync_records',c.c_uint64),('update',c.c_uint64),('lookup',c.c_uint64),('open_mode',c.c_uint64),('leave',c.c_uint64)]
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','handler_offset','frame','local_update')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class FrameFlow(RecordsFlow):
    def __init__(self,dll,consumer,record_image,record_artifact,image,artifact):
        super().__init__(dll,consumer,record_image,record_artifact)
        self.unwound=True # The one unwind sample below belongs to the caller.
        self.frame_unwound=False;self.frame_image=image;self.artifact=artifact;self.entered=[];self.scanned=[];self.saw_last_item=False
        self.map(FRAME,image.bytes);self.write(FRAME,bytes(image.data[:image.bytes]));self.map(ENGINE,0x600000)
        capture=g.Capture()
        for source in artifact['sources']:
            for ins in capture.md.disasm(source['data'],source['start']):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not any(b<=target<e for b,e in g.GROUPS) and target not in (0x146fc40,0x146c2f0,0x1470650):
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for op in ins.operands:
                    if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                        target=ins.address+ins.size+ins.disp;self.map(GAME+target,0x1000)
                        if ins.mnemonic=='lea':continue
                        value=U64(self.cookie) if target==0x263c010 else U64(ENGINE) if op.size==8 else struct.pack('<f',1.0)
                        self.write(GAME+target,value)
        self.write(GAME+0x3326468,U64(ROSTER));self.write(GAME+0x33264f8,U64(ENGINE))
        self.write(ENGINE+0xb398,U64(PEER));self.write(ENGINE+0x17a298,U32(0xffffffff))
        self.write(SCREEN+8,U32(1));self.write(SCREEN+0x2739c8,U32(7))
        self.write(SCREEN+0x2739cc,U32(0xffffffff));self.write(SCREEN+0x273998,b'\x01')
        self.write(SCREEN+0x27fb,b'\x01');self.write(SCREEN+0x27d0,U32(0xffffffff))
        for i in range(8):
            self.write(WIDGETS+i*0x1ee18+0x134e4,U32(0xffffffff))
            self.write(RECORDS+i*0x9f0+0x788,U32(0))
        self.ui_order=self.order[:];self.forward=[self.order.index(n) for n in range(8)]
        self.write(MAPS,struct.pack('<16I',*(self.forward+self.ui_order)))
        self.map(GAME+0x32fed40,0x1000);self.map(GAME+0x328d2a0,0x1000)
        # No matching optional debug style; the four-entry catalog remains four.
        for i in range(4):self.write(GAME+0x21437d0+i*0x50,b'\x02')
        self.uc.reg_write(R('xmm9'),0x66660009+(0xaaaa0009<<64))

    def step(self,uc,address,size,user):
        if address in (FRAME+self.frame_image.local_update,SYNC,CODE):self.entered.append(address)
        if address==FRAME+self.artifact['mapping'][0x1469a95] and not self.frame_unwound:
            values=[self.value(n) for n in NAMES]
            for n in range(6,10):
                value=self.value(f'xmm{n}');values.extend((value&((1<<64)-1),value>>64))
            registers=(c.c_uint64*16)(*values);stack=(c.c_ubyte*0x700).from_buffer_copy(self.read(SP-0x600,0x700))
            status=self.dll.frame_unwind(c.byref(self.frame_image),address-FRAME,self.value('rsp')-SP,registers,stack,STOP)
            g.need(status==0,f'Main frame unwind failed: {status}');self.frame_unwound=True
        if address==FRAME+self.artifact['mapping'][0x1469d60]:self.scanned.append(self.value('r14'))
        if address==FRAME+self.artifact['mapping'][0x1469e10]:self.saw_last_item=self.value('r9')&255==1
        rcx,rdx,r8=self.value('rcx'),self.value('rdx'),self.value('r8')
        super().step(uc,address,size,user)
        if address==GAME+0x134f190:self.uc.reg_write(R('rax'),3)
        elif address==GAME+0x11ebb40:self.uc.reg_write(R('rax'),1)
        elif address==GAME+0x1361f40:
            # Plausible empty item arrays except a sentinel in network slot 7.
            self.write(rdx+8+0x788,U32(1 if r8==PEER+1 else 0))
            if r8==PEER+1:self.write(rdx+8+0x188,U32(0x21))


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_frame_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        command += [g.PROJECT/'mod/src'/n for n in ('ep_session_code.cpp','ep_loadout_lifecycle.cpp','ep_loadout_consumers.cpp','ep_loadout_setup.cpp','ep_loadout_group.cpp','ep_loadout_interactions.cpp','ep_loadout_refresh.cpp','ep_loadout_records.cpp','ep_loadout_frame.cpp','ep_loadout_mode.cpp','ep_loadout_control.cpp')]
        command += [g.PROJECT/'tests'/n for n in ('loadout_consumers_dll.cpp','loadout_setup_dll.cpp','loadout_records_dll.cpp','loadout_frame_dll.cpp')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()))
    dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage)];dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)]
    dll.records_build.argtypes=[c.POINTER(RecordsAddresses),c.POINTER(RecordsImage)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.frame_build.argtypes=[c.POINTER(FrameAddresses),c.POINTER(Image)]
    dll.frame_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer))==0,'Consumer binding failed')
    binding.lifecycle.code=SYNC;record_binding=RecordsAddresses(binding,record_source());record_image=RecordsImage()
    g.need(dll.records_build(c.byref(record_binding),c.byref(record_image))==0,'Record binding failed')
    a=FrameAddresses(record_binding,SYNC,CODE+consumer.update,CODE+consumer.lookup,CODE+0x90000+mode.build()['entries'][1],CODE+0xa0000);a.records.common.lifecycle.code=FRAME
    image=Image();g.need(dll.frame_build(c.byref(a),c.byref(image))==0,'Frame binding failed')
    artifact=g.build();record_artifact=records.build();f=FrameFlow(dll,consumer,record_image,record_artifact,image,artifact)
    try:f.invoke(FRAME-CODE+image.frame)
    except Exception as error:
        offset=f.value('rip')-FRAME
        source=max(((v,k) for k,v in artifact['mapping'].items() if v<=offset),default=(0,0))[1]
        regs={n:hex(f.value(n)) for n in ('rip','rax','rbx','rcx','rdx','rsi','rdi','r8','r9','r11','r12','r13','r14','r15','rsp')}
        raise AssertionError(f'Saved frame instruction {source:X}, registers={regs}: {error}') from error
    g.need(f.frame_unwound and f.probed,'Main/child frame path missed')
    g.need(f.entered==[FRAME+image.local_update,SYNC,CODE],'Frame skipped or reordered grouped updates')
    g.need(f.scanned==[RECORDS+i*0x9f0+0x788 for i in range(8)] and f.saw_last_item,'Frame did not consume the final record')
    for dense,network in enumerate(f.order):
        record=RECORDS+network*0x9f0;peer=struct.unpack('<Q',f.read(record+0x9e8,8))[0]
        g.need(peer==(0 if network==2 else PEER+dense),'Frame record identity changed')
        if network!=2:g.need(f.read(record+0x124,4)==U32(0xb000+f.source_order[dense]),'Source/network ordering was confused')
    g.need(f.read(MAPS+3*4,4)==U32(0) and f.read(MAPS+32,4)==U32(3),'Local slot zero map is inconsistent')
    for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
        g.need(f.read(SCREEN+begin,end-begin)==f.inline[begin:end],'Frame touched old inline storage/maps')
    g.need(f.read(RECORDS+8*0x9f0,16)==b'\x6b'*16 and f.read(WIDGETS+8*0x1ee18,16)==b'\x7c'*16,'Capacity boundary crossed')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=SETUP
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),SYNC,FRAME,CODE+0x90000,CODE+0xa0000)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one main-frame record/UI flow and common preparation',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
