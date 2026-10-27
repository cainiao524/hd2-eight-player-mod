"""One eight-object resource update/ready-query flow in owned emulator memory.

Imported initialization fields model the still-unported engine callbacks.
Native update/scans/hash reads run; engine/property/event services are stubs.
One update unwind snapshot and common prepare/discard, no other suite runs.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_resource_tick as g
import generate_loadout_resource_owner as owner
from validate_loadout_resource_owner import (OwnerFlow,OwnerAddresses,Image as OwnerImage,
    ConsumerImage,Binding,Addresses,RecordsAddresses,record_source,countdown_source,SOURCE,
    OWNER,OWNER_CODE,SetupAddresses,Placement,GroupAddresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,
    REJECT,ENGINE,MAPS,ROSTER,STORAGE,SP,STOP,NAMES,R,U32,U64,READY)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

TICK_CODE=CODE+0x110000
COUNTDOWN=countdown_source();MANAGER=COUNTDOWN.manager;RESOURCES=COUNTDOWN.resources
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','update','any_ready','slot_ready')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class TickFlow(OwnerFlow):
    def __init__(self,dll,consumer,owner_image,image,artifact):
        super().__init__(dll,consumer,owner_image,owner.build())
        self.tick_image=image;self.tick_art=artifact;self.tick_unwound=False;self.events=[];self.property_reads=[];self.free_checks=[]
        self.map(TICK_CODE,image.bytes);self.write(TICK_CODE,bytes(image.data[:image.bytes]));self.map(MANAGER,0x60000)
        capture=g.Capture()
        for source in artifact['sources']:
            for ins in capture.md.disasm(source['data'],source['start']):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not any(b<=target<e for b,e in g.GROUPS):
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for op in ins.operands:
                    if op.type!=X86_OP_MEM or op.mem.base!=X86_REG_RIP or ins.mnemonic=='lea':continue
                    target=ins.address+ins.size+ins.disp
                    # Unsampled CPU dispatch state belongs to the unexercised
                    # catalog aggregation branch; leave it unmapped.
                    if target==0x263c018:continue
                    self.map(GAME+target,16)
                    self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        self.write(GAME+0x3326428,U64(OWNER));self.write(GAME+0x33265f0,U64(MANAGER))
        self.property_id=GAME+0x3002000;self.property_data=GAME+0x3002010
        for target in (self.property_id,self.property_data):
            self.external.add(target);self.map(target,1);self.write(target,b'\xc3')
        self.write(GAME+0x3326308,U64(ENGINE));self.write(ENGINE+0x18,U64(ENGINE+0x71000))
        self.write(ENGINE+0x716d8,U64(self.property_id));self.write(ENGINE+0x71090,U64(self.property_data))
        self.write(MANAGER+0x11d18,b'\xa7'*(4*0x4c));self.write(RESOURCES,b'\xa9'*(8*0x4c))
        self.write(RESOURCES+8*0x4c,b'\x7d'*16);self.transforms=[]
        for ident in range(8):
            self.write(self.object(ident)+0x14,U32(1));self.write(RESOURCES+ident*0x4c,U32(0xffffffff))
            transform=bytes((ident*29+j)%256 for j in range(64));self.transforms.append(transform)
            self.write(MANAGER+0x54000+ident*64,transform)

    def step(self,uc,address,size,user):
        g.need(address not in [GAME+b for b,e in g.GROUPS],'Update/query called an original relocated entry')
        rcx,rdx,r8=self.value('rcx'),self.value('rdx'),self.value('r8')
        if address==TICK_CODE+self.tick_image.update:
            self.tick_sp=self.value('rsp');self.tick_registers=self.snapshot()
        if address==TICK_CODE+self.tick_art['mapping'][0x66b4ad] and not self.tick_unwound:
            stack=(c.c_ubyte*0x200).from_buffer_copy(self.read(self.tick_sp-0x100,0x200))
            status=self.dll.resource_tick_unwind(c.byref(self.tick_image),address-TICK_CODE,self.value('rsp')-self.tick_sp,
                self.snapshot(),self.tick_registers,stack,STOP)
            g.need(status==0,f'Resource update unwind failed: {status}');self.tick_unwound=True
        super().step(uc,address,size,user)
        if address==self.property_id:
            g.need(rdx==0xe4a4586d and 0x3000<=rcx<0x3008,'Update property identity changed');uc.reg_write(R('rax'),7)
        elif address==self.property_data:
            g.need(rdx==7 and 0x3000<=rcx<0x3008,'Update property data identity changed')
            self.property_reads.append(rcx);uc.reg_write(R('rax'),MANAGER+0x54000+(rcx-0x3000)*64)
        elif address==GAME+0x635610:
            g.need(r8==3,'Resource availability type changed');self.free_checks.append(rdx);uc.reg_write(R('rax'),0)
        elif address==GAME+0xfd97e0:
            g.need(rcx==0x807 and rdx==0x82830aed and r8==SOURCE.states+7*4,'State replication targeted the wrong object/cell')
            self.events.append((rdx,struct.unpack('<I',self.read(r8,4))[0]))
        elif address==GAME+0x635f20:self.events.append(('ready',rdx))

    def call_tick(self,entry,rcx=MANAGER,rdx=0):
        self.standalone_lookup=False;self.stop=None;self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP))
        for i,n in enumerate(NAMES):self.uc.reg_write(R(n),0x11110000+i*0x101)
        for i in range(6,9):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        self.uc.reg_write(R('rcx'),rcx);self.uc.reg_write(R('rdx'),rdx);self.uc.reg_write(R('xmm1'),struct.unpack('<I',struct.pack('<f',0.25))[0])
        try:self.uc.emu_start(TICK_CODE+entry,0,count=50000)
        except Exception as error:
            rip=self.value('rip');source=max(((v,a) for a,v in self.tick_art['mapping'].items() if TICK_CODE+v<=rip),default=(0,0))[1]
            raise RuntimeError(f'Update/query emulator stop rip={rip:#x}, source={source:#x}, '+repr({n:hex(self.value(n)) for n in ('rax','rbx','rcx','rdx','rsi','rdi','rbp','r8','r9','r10','r11','r12','r13','r14','r15')})) from error
        g.need(self.stop==STOP and self.value('rsp')==SP+8,'Resource update/query did not return normally')
        for i,n in enumerate(NAMES):g.need(self.value(n)==0x11110000+i*0x101,'Resource update/query corrupted nonvolatile register')
        for i in range(6,9):g.need(self.value(f'xmm{i}')==(0x66660000+i)|((0xaaaa0000+i)<<64),'Resource update corrupted XMM state')
        return self.value('rax')&255


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_resource_tick_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        modules=('session_code','loadout_lifecycle','loadout_consumers','loadout_setup','loadout_group','loadout_interactions','loadout_refresh',
                 'loadout_records','loadout_frame','loadout_mode','loadout_control','loadout_state','loadout_prompt','loadout_countdown','loadout_resources','loadout_resource_owner','loadout_resource_tick','loadout_resource_events','loadout_resource_ownership')
        command += [g.PROJECT/'mod/src'/('ep_'+n+'.cpp') for n in modules]
        command += [g.PROJECT/'tests'/('loadout_'+n+'_dll.cpp') for n in ('consumers','setup','resource_owner','resource_tick')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.resource_owner_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(OwnerImage)]
    dll.resource_tick_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(Image)]
    dll.resource_tick_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer fixture binding failed')
    a=OwnerAddresses(RecordsAddresses(binding,record_source()),COUNTDOWN,SOURCE);a.records.common.lifecycle.code=OWNER_CODE
    owner_image=OwnerImage();g.need(dll.resource_owner_build(c.byref(a),c.byref(owner_image))==0,'Owner fixture binding failed')
    a.records.common.lifecycle.code=TICK_CODE;image=Image();g.need(dll.resource_tick_build(c.byref(a),c.byref(image))==0,'Resource update binding failed')
    f=TickFlow(dll,consumer,owner_image,image,g.build());order=[3,0,6,2,5,1,4,7]
    for ident,ordinal in enumerate(order):
        f.call_owner(owner_image.insert,ident,active=True)
        # Imported initialization stands in for unported native callbacks;
        # this does not establish additional physical resources/pods in-game.
        f.write(SOURCE.phases+ident*12,struct.pack('<IB3xf',2 if ident==7 else 1,int(ident==7),0.25))
        f.write(SOURCE.rows+ident*20,struct.pack('<IIBB2xfI',2,ordinal,1,0,0.5,0x99000000+ident))
        f.write(SOURCE.states+ident*4,U32(2))
    g.need(f.call_tick(image.any_ready)==0 and f.call_tick(image.slot_ready,rdx=7)==0,'Unpopulated resource was reported ready')
    f.call_tick(image.update,rcx=OWNER)
    for ident,ordinal in enumerate(order):
        g.need(f.read(RESOURCES+ordinal*0x4c,0x4c)==U32(0x9100+ident)+f.transforms[ident]+b'\xa9'*8,'Update mixed resource identity/transform or changed reserved bytes')
        state=4 if ident==7 else 2;elapsed=0.0 if ident==7 else 0.75
        g.need(f.read(SOURCE.rows+ident*20,20)==struct.pack('<IIBB2xfI',state,ordinal,1,0,elapsed,0x99000000+ident),'Resource row state/timer/identity changed')
        g.need(f.read(SOURCE.states+ident*4,4)==U32(state),'State replication cell did not follow the object')
    g.need(f.call_tick(image.any_ready)==1 and f.call_tick(image.slot_ready,rdx=7)==1,'Ready query did not reach the eighth resource')
    g.need(f.property_reads==list(range(0x3000,0x3008)) and f.free_checks==[0x9107] and f.events==[(0x82830aed,4),('ready',0x9107)],'Native resource/event sequence changed')
    g.need(f.tick_unwound and struct.unpack('<4I',f.read(OWNER,16))==(8,8,8,8),'Update unwind/counts changed')
    g.need(f.read(OWNER+0x68,0xb0)==b'\xa7'*0xb0 and f.read(MANAGER+0x11d18,4*0x4c)==b'\xa7'*(4*0x4c),'Update/query touched original four-slot storage')
    for base,stride in ((SOURCE.objects,8),(SOURCE.phases,12),(SOURCE.rows,20),(SOURCE.states,4),(RESOURCES,0x4c)):
        g.need(f.read(base+8*stride,16)==b'\x7d'*16,'Resource bank boundary crossed')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=CODE+0x30000
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),CODE+0x70000,CODE+0x80000,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,CODE+0xd0000,COUNTDOWN,CODE+0xe0000,OWNER_CODE,SOURCE,TICK_CODE,CODE+0x120000,CODE+0x130000)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one eight-resource update/ready-query flow',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
