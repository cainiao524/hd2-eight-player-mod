"""One native record-sync flow, with different network/UI/source orderings.

Owned emulator RAM and ABI stubs only. Covers the added records, local reset,
inactive-peer cleanup, one chained unwind, and common READY/discard. No game
access, receipts, fingerprints, full regression or production activation.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_records as g
import generate_loadout_consumers as consumers
from validate_loadout_consumers import (Binding,Image as ConsumerImage,Flow,Addresses,GAME,CODE,SCREEN,
    RECORDS,WIDGETS,REJECT,ENGINE,NAMES,R,U64,U32,MAPS,ROSTER,STORAGE,PEER,SP,STOP)
from validate_loadout_setup import SetupAddresses,Placement,GroupAddresses,SETUP,RecordSource,record_source
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

SYNC=CODE+0x70000
class RecordsAddresses(c.Structure):
    _fields_=[('common',Binding),('source',RecordSource)]
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','handler_offset')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class RecordsFlow(Flow):
    def __init__(self,dll,consumer,image,artifact):
        super().__init__(consumers.build(),dll,consumer)
        self.points=set();self.unwound=False;self.probed=False;self.observed=[];self.record_image=image
        self.unwind_point=SYNC+artifact['mapping'][0x146fd10];self.cookie=0x953701ab827
        self.map(SP-0x2000,0x3000);self.map(SYNC,image.bytes);self.write(SYNC,bytes(image.data[:image.bytes]))
        capture=g.Capture()
        for ins in capture.md.disasm(artifact['source'],g.START):
            if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                target=ins.operands[0].imm
                if not g.START<=target<g.END:
                    self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
            for op in ins.operands:
                if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                    target=ins.address+ins.size+ins.disp;self.map(GAME+target,0x1000)
                    if ins.mnemonic=='lea':continue
                    data=U64(self.cookie) if target==0x263c010 else U64(ENGINE) if op.size==8 else U32(0xffffffff)
                    self.write(GAME+target,data)
        self.write(GAME+0x3326468,U64(ROSTER));self.write(GAME+0x33264f8,U64(ENGINE))
        self.write(ENGINE+0xb398,U64(PEER+1));self.write(SCREEN+0x27d0,U32(0xffffffff))
        # Retain one stale record (network 2) whose entity is now absent.
        for network in range(8):self.write(RECORDS+network*0x9f0+0x9e8,U64(0xdead))
        self.ui_order=[7,3,0,6,1,5,2,4];self.forward=[self.ui_order.index(n) for n in range(8)]
        self.write(MAPS,struct.pack('<16I',*(self.forward+self.ui_order)))
        self.source_order=[6,2,5,0,7,4,1,3];self.source=record_source()
        self.write(ENGINE+0x930,U64(ENGINE+0x50000));self.write(ENGINE+0x938,U32(16)+U32(0xffffffff)+U32(1))
        self.write(ENGINE+0x50000,b'\xff'*128)
        self.write(ENGINE+0x10,U64(ENGINE+0x45000)+U32(8))
        # Canary the former source banks. Their contents cannot serve as a
        # fallback for any of the newly bound arrays.
        self.write(ENGINE+0x948,b'\xa6'*(0xc7c-0x948))
        for dense,ordinal in enumerate(self.source_order):
            self.write(STORAGE+0x584+dense*32,U32(2))
            self.write(ENGINE+0x50000+dense*8,U32(0x1000+dense)+U32(ordinal))
            self.write(self.source.actors+ordinal*8,U64(ENGINE+0x47000+ordinal*32))
            self.write(ENGINE+0x47010+ordinal*32,U32(0x9000+ordinal))
            row=self.source.equipment+ordinal*0x40
            for offset,value in ((0,0x2000+ordinal),(4,0xb000+ordinal),(8,0xc000+ordinal),
                (12,0xd000+ordinal),(16,0x15),(0x28,0xe000+ordinal),(0x2c,0xf000+ordinal),(0x38,0),(0x3c,0x3c)):
                self.write(row+offset,U32(value))
            self.write(self.source.status+ordinal*0x44,bytes([0x40+ordinal]))
            self.write(ENGINE+0x45000+ordinal*8,U64(ENGINE+0x46000+ordinal*32))
            self.write(ENGINE+0x46000+ordinal*32,U32(0x2000+ordinal)+U32(0xa000+ordinal))
        self.source_bytes=[self.read(a,n) for a,n in ((self.source.actors,64),(self.source.equipment,512),(self.source.status,8*0x44))]

    def step(self,uc,address,size,user):
        if address==self.unwind_point and not self.unwound:
            registers=(c.c_uint64*8)(*(self.value(n) for n in NAMES))
            stack=(c.c_ubyte*0x1700).from_buffer_copy(self.read(SP-0x1600,0x1700))
            status=self.dll.records_unwind(c.byref(self.record_image),address-SYNC,self.value('rsp')-SP,registers,stack,STOP)
            g.need(status==0,f'Record-sync unwind failed: {status}');self.unwound=True
        if address==GAME+0x21045c0:
            g.need(self.value('rax')==0x1490,'Stack probe size changed');self.probed=True;return
        if address in self.external:
            rcx,rdx,r8=self.value('rcx'),self.value('rdx'),self.value('r8')
            if address==GAME+0xfd98c0:self.write(rcx,U32(0 if rdx==106 else 1))
            elif address==GAME+0x1361f40:self.write(rdx+8,bytes([0x20+r8-PEER])*0x9f0)
            elif address==GAME+0x20988f0:self.write(rcx,self.read(rdx,r8))
            elif address==GAME+0x208aaa0:self.write(rcx,bytes([rdx&255])*r8)
            elif address==GAME+0x2088770:g.need(rcx==self.cookie,'GS cookie changed')
            if address-GAME in (0x189ca20,0x189d050,0x188fb30):self.observed.append((address-GAME,rcx,rdx,r8))
        super().step(uc,address,size,user)


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_records_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        command += [g.PROJECT/'mod/src'/n for n in ('ep_session_code.cpp','ep_loadout_lifecycle.cpp','ep_loadout_consumers.cpp','ep_loadout_setup.cpp','ep_loadout_group.cpp','ep_loadout_interactions.cpp','ep_loadout_refresh.cpp','ep_loadout_records.cpp','ep_loadout_frame.cpp','ep_loadout_mode.cpp','ep_loadout_control.cpp')]
        command += [g.PROJECT/'tests'/n for n in ('loadout_consumers_dll.cpp','loadout_setup_dll.cpp','loadout_records_dll.cpp')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()))
    dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage)];dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)]
    dll.records_build.argtypes=[c.POINTER(RecordsAddresses),c.POINTER(Image)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.records_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer))==0,'Consumer binding failed')
    binding.lifecycle.code=SYNC;a=RecordsAddresses(binding,record_source());image=Image()
    g.need(dll.records_build(c.byref(a),c.byref(image))==0,'Record-sync binding failed')
    artifact=g.build();f=RecordsFlow(dll,consumer,image,artifact)
    try:f.invoke(SYNC-CODE,1)
    except Exception as error:
        offset=f.value('rip')-SYNC
        source=max(((v,k) for k,v in artifact['mapping'].items() if isinstance(k,int) and v<=offset),default=(0,0))[1]
        registers={n:hex(f.value(n)) for n in ('rax','rbx','rcx','rdx','rsi','rdi','r8','r9','r12','r13','r14','r15','rsp')}
        raise AssertionError(f'Saved instruction {source:X}, image offset {offset:X}, registers={registers}: {error}') from error
    g.need(f.probed and f.unwound,'Probe/unwind path missed')
    for dense,network in enumerate(f.order):
        peer=struct.unpack('<Q',f.read(RECORDS+network*0x9f0+0x9e8,8))[0]
        g.need(peer==(0 if network==2 else PEER+dense),'Record identity or inactive-peer cleanup failed')
        if network==2:continue
        ordinal=f.source_order[dense];record=RECORDS+network*0x9f0
        for offset,value in ((0x120,0xa000+ordinal),(0x124,0xb000+ordinal),(0x128,0xc000+ordinal),
                             (0x12c,0xd000+ordinal),(0x134,0xe000+ordinal),(0x138,0xf000+ordinal)):
            g.need(f.read(record+offset,4)==U32(value),'Source ordinal was confused with network/UI index')
        g.need(f.read(record+0x148,1)==bytes([0x40+ordinal]),'Source status came from old storage')
    widgets=[WIDGETS+i*0x1ee18 for i in range(8)]
    g.need([x[1] for x in f.observed if x[0]==0x188fb30]==[w+0x1fa8 for w in widgets],'Local reset omitted a widget')
    g.need([(x[1],x[2]) for x in f.observed if x[0]==0x189d050]==[(w,j) for w in widgets for j in range(4)],'Player count changed inner equipment choices')
    g.need([(x[1],x[2]) for x in f.observed if x[0]==0x189ca20]==[(WIDGETS,RECORDS+7*0x9f0)],'Local widget received wrong record')
    for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
        g.need(f.read(SCREEN+begin,end-begin)==f.inline[begin:end],'Record-sync touched old inline storage/maps')
    g.need(f.read(ENGINE+0x948,0xc7c-0x948)==b'\xa6'*(0xc7c-0x948),'Old source banks changed')
    g.need(f.read(RECORDS+8*0x9f0,16)==b'\x6b'*16 and f.read(WIDGETS+8*0x1ee18,16)==b'\x7c'*16,'Capacity boundary crossed')
    g.need([f.read(at,n) for at,n in ((f.source.actors,64),(f.source.equipment,512),(f.source.status,8*0x44))]==f.source_bytes,'Source snapshot was overwritten')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=SETUP
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),SYNC,CODE+0x80000,CODE+0x90000,CODE+0xa0000)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one eight-slot record-sync/reset flow and common preparation',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
