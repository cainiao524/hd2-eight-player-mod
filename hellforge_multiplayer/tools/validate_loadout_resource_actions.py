"""One phase reset -> resource activation -> completion callback flow.

Eight registered resource objects use a separate ordinal mapping. Native
actor notifications and completion-catalog indices remain independent.
Services are ABI stubs; no physical objects, transport or game access.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_resource_actions as g
import generate_loadout_resource_owner as owner
from validate_loadout_resource_owner import (OwnerFlow,OwnerAddresses,Image as OwnerImage,
    ConsumerImage,Binding,Addresses,RecordsAddresses,record_source,countdown_source,SOURCE,
    OWNER,OWNER_CODE,TABLE,SetupAddresses,Placement,GroupAddresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,
    REJECT,ENGINE,MAPS,ROSTER,STORAGE,SP,STOP,NAMES,R,U32,U64,READY)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

ACTIONS_CODE=CODE+0x160000
COUNTDOWN=countdown_source();MANAGER=COUNTDOWN.manager;RESOURCES=COUNTDOWN.resources
CATALOG=OWNER+0x62000;CATALOG_HASH=OWNER+0x63000;CATALOG_ROWS=OWNER+0x64000
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','activate','reset','complete')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class ActionFlow(OwnerFlow):
    def __init__(self,dll,consumer,owner_image,image,artifact):
        super().__init__(dll,consumer,owner_image,owner.build())
        self.image=image;self.artifact=artifact;self.reset_unwound=False
        self.handles=[];self.commands=[];self.notifications=[];self.modes=[];self.parents=0
        self.map(MANAGER,0x30000);self.map(ACTIONS_CODE,image.bytes);self.write(ACTIONS_CODE,bytes(image.data[:image.bytes]))
        capture=g.Capture()
        for source in artifact['sources']:
            for ins in capture.md.disasm(source['data'],source['start']):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not any(b<=target<e for b,e in g.GROUPS):
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for op in ins.operands:
                    if op.type!=X86_OP_MEM or op.mem.base!=X86_REG_RIP:continue
                    target=ins.address+ins.size+ins.disp;self.map(GAME+target,16)
                    self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        for target,value in ((0x3326428,OWNER),(0x3326468,ROSTER),(0x33265f0,MANAGER),(0x3326d78,CATALOG)):
            self.write(GAME+target,U64(value))
        self.write(ENGINE+0x42b0,U32(0));self.write(ENGINE+0x4294,U32(0))
        self.write(MANAGER+0x24,U32(2));self.write(MANAGER+0x50,U64(self.object(0))+U64(self.object(1)))
        self.write(MANAGER+0x12ee1,b'\0')
        for i in range(2):self.write(MANAGER+0x12ee2+i*0x54,b'\1')
        self.write(MANAGER+0x11d18,b'\xa7'*(4*0x4c))
        self.write(RESOURCES+8*0x4c,b'\x7d'*16)
        self.resource_rows=[]
        for i in range(8):
            row=U32(0xb200+i)+bytes([0x30+i])*(0x4c-4)
            self.write(RESOURCES+i*0x4c,row);self.resource_rows.append(row)
        self.write(ROSTER+0x84,U32(8)+U32(8));self.write(ROSTER+0xe8,b'\xa7'*32)
        for i,ident in enumerate((4,0,1,2,3,5,6,7)):self.write(STORAGE+i*8,U64(self.object(ident)))
        for ident in range(9):self.write(self.object(ident)+0x14,U32(1))
        self.write(CATALOG+0x20,U64(CATALOG_HASH)+U32(16)+U32(0xffffffff)+U32(1))
        self.write(CATALOG+0x48,U64(CATALOG_ROWS));self.write(CATALOG_HASH,b'\xff'*128)
        # Index 9 deliberately exceeds player capacity: this native catalog
        # stores unrelated components and retains its independent allocation.
        self.write(CATALOG_HASH+8*8,U32(0x9108)+U32(9));self.write(CATALOG_ROWS+9*64+0x14,U32(6)+U32(6))

    def step(self,uc,address,size,user):
        g.need(address not in [GAME+b for b,e in g.GROUPS],'Action executed an original relocated callback')
        rcx,rdx,r8,r9=(self.value(n) for n in ('rcx','rdx','r8','r9'))
        if address==ACTIONS_CODE+self.image.reset:
            self.reset_sp=self.value('rsp');self.reset_registers=self.snapshot()
        if address==ACTIONS_CODE+self.artifact['mapping'][0x6624ca] and not self.reset_unwound:
            stack=(c.c_ubyte*0x200).from_buffer_copy(self.read(self.reset_sp-0x100,0x200))
            result=self.dll.resource_actions_unwind(c.byref(self.image),address-ACTIONS_CODE,self.value('rsp')-self.reset_sp,
                self.snapshot(),self.reset_registers,stack,STOP)
            g.need(result==0,f'Phase-reset unwind failed: {result}');self.reset_unwound=True
        if address==GAME+0x119f910:
            g.need(rcx==self.object(8),'Completion parent lookup lost its actor');self.parents+=1
        elif address==GAME+0xfd9a40:
            self.handles.append(rcx)
        elif address==GAME+0xbde430:
            payload=self.read(r8,16)
            if rcx==0xfd97c115:
                g.need(rdx==(1<<64)-2 and r9==1 and payload==U32(1)+U32(4)+U64((0x9104<<8)|1),'Reset did not use the shared first descriptor/native argument record')
                self.commands.append('reset')
            else:
                g.need(rcx==0x70dd8901 and rdx==(1<<64)-1 and r9==2,'Activation command identity changed')
                g.need(payload==U32(1)+U32(4)+U64((0xb205<<8)|1),'Activation did not read the mapped resource ordinal')
                tag,kind,pointer=struct.unpack('<IIQ',self.read(r8+16,16))
                g.need((tag,kind)==(0,4) and self.read(pointer,1)==b'\1','Activation boolean record changed');self.commands.append('activate')
        elif address==GAME+0xfd97e0:
            g.need(rcx in (0x800,0x801) and rdx==0x865ca1f3,'Actor notification identity changed')
            index=rcx-0x800;g.need(r8==MANAGER+0x12ee2+index*0x54,'Native actor notification row changed')
            self.notifications.append((index,self.read(r8,1)[0]))
        elif address==GAME+0x13260f0:
            g.need(rdx==0xe and not r8,'Native activation mode changed');self.modes.append(rdx)
        super().step(uc,address,size,user)
        if address==GAME+0x119f910:uc.reg_write(R('rax'),self.object(7))
        elif address==GAME+0xfd9a40:uc.reg_write(R('rax'),(rcx<<8)|1)

    def call_action(self,entry,rcx,rdx=0):
        self.standalone_lookup=False;self.stop=None;self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP))
        for i,n in enumerate(NAMES):self.uc.reg_write(R(n),0x11110000+i*0x101)
        for i in range(6,9):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        self.uc.reg_write(R('rcx'),rcx);self.uc.reg_write(R('rdx'),rdx)
        try:self.uc.emu_start(ACTIONS_CODE+entry,0,count=30000)
        except Exception as error:
            rip=self.value('rip');source=max(((v,a) for a,v in self.artifact['mapping'].items() if ACTIONS_CODE+v<=rip),default=(0,0))[1]
            raise RuntimeError(f'Resource action stop rip={rip:#x}, source={source:#x}') from error
        g.need(self.stop==STOP and self.value('rsp')==SP+8,'Resource action did not return normally')
        for i,n in enumerate(NAMES):g.need(self.value(n)==0x11110000+i*0x101,'Resource action corrupted nonvolatile register')
        for i in range(6,9):g.need(self.value(f'xmm{i}')==(0x66660000+i)|((0xaaaa0000+i)<<64),'Resource action corrupted XMM state')


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_resource_actions_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        modules=('session_code','loadout_lifecycle','loadout_consumers','loadout_setup','loadout_group','loadout_interactions','loadout_refresh',
                 'loadout_records','loadout_frame','loadout_mode','loadout_control','loadout_state','loadout_prompt','loadout_countdown','loadout_resources',
                 'loadout_resource_owner','loadout_resource_tick','loadout_resource_events','loadout_resource_ownership','loadout_resource_sync','loadout_resource_signals','loadout_resource_actions','loadout_resource_main')
        command += [g.PROJECT/'mod/src'/('ep_'+n+'.cpp') for n in modules]
        command += [g.PROJECT/'tests'/('loadout_'+n+'_dll.cpp') for n in ('consumers','setup','resource_owner','resource_actions')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.resource_owner_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(OwnerImage)]
    dll.resource_actions_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(Image)]
    dll.resource_actions_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer fixture binding failed')
    a=OwnerAddresses(RecordsAddresses(binding,record_source()),COUNTDOWN,SOURCE);a.records.common.lifecycle.code=OWNER_CODE
    owner_image=OwnerImage();g.need(dll.resource_owner_build(c.byref(a),c.byref(owner_image))==0,'Owner fixture binding failed')
    a.records.common.lifecycle.code=ACTIONS_CODE;image=Image();g.need(dll.resource_actions_build(c.byref(a),c.byref(image))==0,'Resource action binding failed')
    f=ActionFlow(dll,consumer,owner_image,image,g.build())
    for ident,ordinal in enumerate((3,0,6,2,1,7,4,5)):
        f.call_owner(owner_image.insert,ident,active=True)
        # Existing metadata/timers are input fixtures, not physical pod proof.
        phases=U32(0)+U32(ident&1)+struct.pack('<f',ident+0.25)
        rows=U32(2)+U32(ordinal)+b'\1\0\0\0'+bytes(8)
        f.write(SOURCE.phases+ident*12,phases);f.write(SOURCE.rows+ident*20,rows)
        f.payloads[ident]=(U32(1)+phases[4:],rows,bytes(4))
    f.call_action(image.reset,MANAGER)
    g.need(f.notifications==[(0,0),(1,0)],'Reset did not clear native actor flags')
    f.expect(list(range(8)),(8,8,8,8))
    f.call_action(image.activate,MANAGER,5)
    f.call_action(image.complete,f.object(8))
    # Retire the independent native catalog record, then deliver a late
    # callback; its cleanup must preserve registers without further effects.
    f.write(CATALOG_HASH+8*8,b'\xff'*8);f.call_action(image.complete,f.object(8))
    g.need(f.commands==['reset','reset','activate','activate'] and f.handles==[0x9104,0x9104,0xb205,0xb205],'Action used an old bank or emitted after catalog retirement')
    g.need(f.notifications==[(0,0),(1,0),(0,1),(1,1),(0,1),(1,1)] and f.modes==[14,14] and f.parents==2,'Native activation notification sequence changed')
    f.expect(list(range(8)),(8,8,8,8))
    g.need(f.read(RESOURCES,8*0x4c)==b''.join(f.resource_rows) and f.read(RESOURCES+8*0x4c,16)==b'\x7d'*16,'Resource read altered rows or crossed capacity')
    g.need(f.read(MANAGER+0x11d18,4*0x4c)==b'\xa7'*(4*0x4c) and f.read(ROSTER+0xe8,32)==b'\xa7'*32,'Action touched old resource/descriptor storage')
    g.need(f.reset_unwound,'Phase-reset unwind point was not reached')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=CODE+0x30000
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),CODE+0x70000,CODE+0x80000,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,CODE+0xd0000,COUNTDOWN,CODE+0xe0000,OWNER_CODE,SOURCE,CODE+0x110000,CODE+0x120000,CODE+0x130000,CODE+0x140000,CODE+0x150000,ACTIONS_CODE,CODE+0x170000)
    result=dll.setup_group(c.byref(group));g.need(result==0,f'Common READY/discard failed: {result}')
    print(json.dumps(dict(passed=True,scope='one phase-reset/resource-activation/completion flow',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
