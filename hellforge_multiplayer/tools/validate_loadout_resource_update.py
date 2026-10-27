"""One eight-object state/progress/transform-publication smoke flow.

All objects share the real relocated update. Mixed current phases exercise
normal state changes, the native type switch and missing optional records.
Only external services are ABI stubs. No game access or separate suite.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_resource_update as g
import generate_loadout_resource_owner as owner
from validate_loadout_resource_owner import (OwnerFlow,OwnerAddresses,Image as OwnerImage,
    ConsumerImage,Binding,Addresses,RecordsAddresses,record_source,countdown_source,SOURCE,
    OWNER,OWNER_CODE,SetupAddresses,Placement,GroupAddresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,
    REJECT,ENGINE,MAPS,ROSTER,STORAGE,SP,STOP,NAMES,R,U32,U64,READY)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

UPDATE_CODE=CODE+0x180000
COUNTDOWN=countdown_source();MANAGER=COUNTDOWN.manager;RESOURCES=COUNTDOWN.resources
CATALOG=OWNER+0x62000;CATALOG_HASH=OWNER+0x63000;CATALOG_ROWS=OWNER+0x64000
API_TABLE=ENGINE+0x50000;TRANSFORMS=ENGINE+0x51000
PROPERTY=GAME+0x3002000;TRANSFORM=GAME+0x3002010
ORDINALS=(3,0,6,2,1,7,4,5)
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','update')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class UpdateFlow(OwnerFlow):
    def __init__(self,dll,consumer,owner_image,image,artifact):
        super().__init__(dll,consumer,owner_image,owner.build())
        self.update_image=image;self.update_art=artifact;self.unwound=False
        self.notifications=[];self.transforms=[];self.property_calls=[];self.events=[];self.effects=[];self.switch_visits=0
        self.map(MANAGER,0x30000);self.map(UPDATE_CODE,image.bytes);self.write(UPDATE_CODE,bytes(image.data[:image.bytes]))
        capture=g.Capture()
        for source in artifact['sources']:
            for ins in capture.md.disasm(source['data'],source['start']):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not any(b<=target<e for b,e in g.GROUPS):
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for op in ins.operands:
                    if op.type!=X86_OP_MEM or op.mem.base!=X86_REG_RIP:continue
                    if ins.mnemonic=='lea':continue # address formation does not read the pointed-to data
                    target=ins.address+ins.size+ins.disp;self.map(GAME+target,16)
                    if target==0x263c018:
                        self.write(GAME+target,U32(0));continue # fixture CPU dispatch; not a saved process value
                    self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        for target,value in ((0x3326428,OWNER),(0x33265f0,MANAGER),(0x3326d88,CATALOG)):
            self.write(GAME+target,U64(value))
        self.write(ENGINE+0x18,U64(API_TABLE))
        self.write(API_TABLE+0x6d8,U64(PROPERTY));self.write(API_TABLE+0x90,U64(TRANSFORM))
        for target in (PROPERTY,TRANSFORM):
            self.external.add(target);self.map(target,1);self.write(target,b'\xc3')
        for i in range(8):
            self.write(self.object(i)+0x14,U32(1))
            self.write(TRANSFORMS+i*64,struct.pack('<16f',*(i*100+j+0.25 for j in range(16))))
            self.write(RESOURCES+i*0x4c,U32(0xffffffff)+bytes(64)+U64(0xd000+i))
        self.write(MANAGER+0x11d18,b'\xa7'*(4*0x4c));self.write(RESOURCES+8*0x4c,b'\x7d'*16)
        self.write(CATALOG+0x20,U64(CATALOG_HASH)+U32(16)+U32(0xffffffff)+U32(1))
        self.write(CATALOG+0x48,U64(CATALOG_ROWS));self.write(CATALOG_HASH,b'\xff'*128)
        # Catalog ordinal 9 is distinct from resource/player capacity 8.
        self.write(CATALOG_HASH+5*8,U32(0x9105)+U32(9));self.write(CATALOG_ROWS+9*100,U32(1))
        self.threshold=struct.unpack('<f',capture.read(0x23c72e8,4))[0]

    def step(self,uc,address,size,user):
        g.need(address!=GAME+0x66b090,'Update executed the old four-slot entry')
        rcx,rdx,r8,r9=(self.value(n) for n in ('rcx','rdx','r8','r9'))
        if address==UPDATE_CODE+self.update_art['mapping'][0x66b3b4] and not self.unwound:
            stack=(c.c_ubyte*0x200).from_buffer_copy(self.read(SP-0x100,0x200))
            status=self.dll.resource_update_unwind(c.byref(self.update_image),address-UPDATE_CODE,self.value('rsp')-SP,
                self.snapshot(),self.expected_registers,stack,STOP)
            g.need(status==0,f'Resource update unwind failed: {status}');self.unwound=True
        if address==UPDATE_CODE+self.update_art['mapping'][0x66b623]:self.switch_visits+=1
        if address==PROPERTY:
            g.need(0x3000<=rcx<0x3008 and rdx==0xe4a4586d,'Transform property query changed');self.property_calls.append(rcx-0x3000)
        elif address==TRANSFORM:
            g.need(0x3000<=rcx<0x3008 and rdx==0xa100+rcx-0x3000,'Transform service lost its descriptor')
            self.transforms.append(rcx-0x3000)
        elif address==GAME+0xfd97e0:
            ident=rcx-0x800;g.need(0<=ident<8 and rdx==0x82830aed and r8==SOURCE.states+ident*4,'State notification used an old bank or wrong object')
            self.notifications.append((ident,struct.unpack('<I',self.read(r8,4))[0]))
        elif address==GAME+0x635610:g.need(rdx==0x9106 and r8==3,'Blocked-state query changed')
        elif address==GAME+0x808810:
            g.need(r9==0 and self.read(self.value('rsp')+0x28,4)==U32(1),'Native state-event arguments changed')
            self.events.append((rdx,r8))
        elif address==GAME+0x843930:self.effects.append((rdx,r8))
        super().step(uc,address,size,user)
        if address==PROPERTY:uc.reg_write(R('rax'),0xa100+rcx-0x3000)
        elif address==TRANSFORM:uc.reg_write(R('rax'),TRANSFORMS+(rcx-0x3000)*64)

    def update(self):
        self.standalone_lookup=False;self.stop=None;self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP))
        for i,n in enumerate(NAMES):self.uc.reg_write(R(n),0x11110000+i*0x101)
        for i in range(6,9):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        self.expected_registers=self.snapshot()
        self.uc.reg_write(R('rcx'),OWNER);self.uc.reg_write(R('xmm1'),struct.unpack('<I',struct.pack('<f',0.25))[0])
        try:self.uc.emu_start(UPDATE_CODE+self.update_image.update,0,count=30000)
        except Exception as error:
            rip=self.value('rip');source=max(((v,a) for a,v in self.update_art['mapping'].items() if UPDATE_CODE+v<=rip),default=(0,0))[1]
            raise RuntimeError(f'Resource update stop rip={rip:#x}, source={source:#x}') from error
        g.need(self.stop==STOP and self.value('rsp')==SP+8,'Resource update did not return normally')
        g.need(list(self.snapshot())==list(self.expected_registers),'Resource update corrupted nonvolatile state')


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_resource_update_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        modules=('session_code','loadout_lifecycle','loadout_consumers','loadout_setup','loadout_group','loadout_interactions','loadout_refresh',
                 'loadout_records','loadout_frame','loadout_mode','loadout_control','loadout_state','loadout_prompt','loadout_countdown','loadout_resources',
                 'loadout_resource_owner','loadout_resource_tick','loadout_resource_events','loadout_resource_ownership','loadout_resource_sync',
                 'loadout_resource_signals','loadout_resource_actions','loadout_resource_main','loadout_resource_update')
        command += [g.PROJECT/'mod/src'/('ep_'+n+'.cpp') for n in modules]
        command += [g.PROJECT/'tests'/('loadout_'+n+'_dll.cpp') for n in ('consumers','setup','resource_owner','resource_update')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.resource_owner_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(OwnerImage)]
    dll.resource_update_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(Image)]
    dll.resource_update_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer fixture binding failed')
    a=OwnerAddresses(RecordsAddresses(binding,record_source()),COUNTDOWN,SOURCE);a.records.common.lifecycle.code=OWNER_CODE
    owner_image=OwnerImage();g.need(dll.resource_owner_build(c.byref(a),c.byref(owner_image))==0,'Owner fixture binding failed')
    a.records.common.lifecycle.code=UPDATE_CODE;image=Image();g.need(dll.resource_update_build(c.byref(a),c.byref(image))==0,'Resource update binding failed')
    f=UpdateFlow(dll,consumer,owner_image,image,g.build())
    expected_states=[]
    for ident,ordinal in enumerate(ORDINALS):
        f.call_owner(owner_image.insert,ident,active=True)
        phase=2 if ident>=5 else 1;state=4 if ident==6 else 1;flag=int(ident==6)
        timer=f.threshold;published_timer=42.0
        phases=U32(phase)+U32(flag)+struct.pack('<f',timer)
        rows=U32(state)+U32(ordinal)+bytes((1,flag,0,0))+struct.pack('<f',published_timer)+U32(0xa000+ident)
        f.write(SOURCE.phases+ident*12,phases);f.write(SOURCE.rows+ident*20,rows);f.write(SOURCE.states+ident*4,U32(state))
        next_state=4 if ident==6 else 3 if ident>=5 else 2;expected_states.append(next_state)
        f.payloads[ident]=(U32(phase)+U32(flag)+struct.pack('<f',timer if ident==6 else timer+0.25),
            U32(next_state)+U32(ordinal)+bytes((1,int(ident>=5),0,0))+struct.pack('<f',42.25 if ident==6 else 0)+U32(0xa000+ident),U32(next_state))
    f.update()
    f.expect(list(range(8)),(8,8,8,8))
    g.need(f.transforms==list(range(8)) and f.property_calls==list(range(8)),'Transform publication did not reach every resource object')
    g.need(f.notifications==[(i,state) for i,state in enumerate(expected_states) if i!=6],'State notifications lost object/state identity')
    g.need(f.events==[(0x9100+i,0xfa89b8eb if i>=5 else 0x6b9cab48) for i in range(8) if i!=6],'State event sequence changed')
    g.need(f.effects==[(0x9105,0x16aed43),(0x9107,0x16aed43)] and f.switch_visits==22,'Native type switch or missing-catalog cleanup changed')
    for ident,ordinal in enumerate(ORDINALS):
        expected=U32(0x9100+ident)+f.read(TRANSFORMS+ident*64,64)+U64(0xd000+ordinal)
        g.need(f.read(RESOURCES+ordinal*0x4c,0x4c)==expected,'Transform publication mixed object identity, ordinal or row tail')
    g.need(f.read(MANAGER+0x11d18,4*0x4c)==b'\xa7'*(4*0x4c) and f.read(RESOURCES+8*0x4c,16)==b'\x7d'*16,'Update touched old resource storage or crossed the shared bank')
    g.need(f.unwound,'Owned state unwind point not reached')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=CODE+0x30000
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),CODE+0x70000,CODE+0x80000,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,CODE+0xd0000,COUNTDOWN,CODE+0xe0000,OWNER_CODE,SOURCE,CODE+0x110000,CODE+0x120000,CODE+0x130000,CODE+0x140000,CODE+0x150000,CODE+0x160000,CODE+0x170000,UPDATE_CODE)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one resource-state/transform-publication flow',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
