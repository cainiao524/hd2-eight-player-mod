"""One main-update -> owned reset -> published-object query smoke flow.

One native controller consumes eight resource slots. Native catalog ordinals
stay independent. Services are ABI stubs, except the saved query leaf which
runs unchanged in owned emulator memory. No game access or broader suite.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_resource_main as g
import generate_loadout_resource_actions as actions
import generate_loadout_resource_owner as owner
from validate_loadout_resource_actions import Image as ActionsImage,ACTIONS_CODE
from validate_loadout_resource_owner import (OwnerFlow,OwnerAddresses,Image as OwnerImage,
    ConsumerImage,Binding,Addresses,RecordsAddresses,record_source,countdown_source,SOURCE,
    OWNER,OWNER_CODE,SetupAddresses,Placement,GroupAddresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,
    REJECT,ENGINE,MAPS,ROSTER,STORAGE,SP,STOP,NAMES,R,U32,U64,READY)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

MAIN_CODE=CODE+0x170000
COUNTDOWN=countdown_source();MANAGER=COUNTDOWN.manager;RESOURCES=COUNTDOWN.resources
CATALOG=OWNER+0x62000;HASH=OWNER+0x63000;ROWS=OWNER+0x64000;FLAGS=OWNER+0x65000;OUTPUT=OWNER+0x66000
class MainAddresses(c.Structure):
    _fields_=[('owner',OwnerAddresses),('reset_entry',c.c_uint64)]
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','update','query','handler_offset')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class MainFlow(OwnerFlow):
    def __init__(self,dll,consumer,owner_image,image,action_image,artifact):
        super().__init__(dll,consumer,owner_image,owner.build())
        self.main_image=image;self.main_art=artifact;self.action_image=action_image
        self.unwound=False;self.scanned=[];self.reset_calls=0;self.reset_commands=0;self.available_counts=[];self.leaf_calls=0
        self.map(MANAGER,0x30000);self.map(ENGINE,0x600000)
        capture=g.Capture()
        for base,img,art,groups in ((MAIN_CODE,image,artifact,g.GROUPS),(ACTIONS_CODE,action_image,actions.build(),actions.GROUPS)):
            self.map(base,img.bytes);self.write(base,bytes(img.data[:img.bytes]))
            for source in art['sources']:
                for ins in capture.md.disasm(source['data'],source['start']):
                    if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                        target=ins.operands[0].imm
                        if not any(b<=target<e for b,e in groups):
                            self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                    for op in ins.operands:
                        if op.type!=X86_OP_MEM or op.mem.base!=X86_REG_RIP:continue
                        target=ins.address+ins.size+ins.disp;self.map(GAME+target,16)
                        if target==0x263c010:continue # per-process cookie is supplied by this fixture below
                        self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        # This leaf's jump tables are in the saved workspace capture. Execute
        # them, preserving its private R9/R10/R11 ABI without an invented stub.
        self.external.discard(GAME+0x11957c0)
        leaf=capture.read(0x11957c0,0x1195a50-0x11957c0)
        self.map(GAME+0x11957c0,len(leaf));self.write(GAME+0x11957c0,leaf)
        for target,value in ((0x3326428,OWNER),(0x3326468,ROSTER),(0x33265f0,MANAGER),(0x3326d88,CATALOG)):
            self.write(GAME+target,U64(value))
        self.cookie=0xbb40e64e;self.write(GAME+0x263c010,U64(self.cookie))
        self.write(ENGINE+0x17a298,U32(0xffffffff))
        self.write(ENGINE+0x42b0,U32(0));self.write(ENGINE+0x4294,U32(0))
        self.write(MANAGER+0x20,U32(1)+U32(1));self.write(MANAGER+0x50,U64(self.object(0)))
        self.write(MANAGER+0x12ee1,b'\1\1') # phase transition invokes owned reset
        self.write(MANAGER+0x11d18,b'\xa7'*(4*0x4c))
        self.write(RESOURCES+8*0x4c,b'\x7d'*16)
        self.resource_rows=[]
        for i in range(8):
            row=U32(0xb200+i)+bytes([0x30+i])*(0x4c-4)
            self.write(RESOURCES+i*0x4c,row);self.resource_rows.append(row)
        self.write(ROSTER+0x84,U32(8)+U32(8));self.write(ROSTER+0xe8,b'\xa7'*32)
        for i in range(8):self.write(STORAGE+i*8,U64(self.object(i)))
        self.write(CATALOG+0x20,U64(HASH)+U32(16)+U32(0xffffffff)+U32(1))
        self.write(CATALOG+0x48,U64(ROWS)+U64(FLAGS));self.write(HASH,b'\xff'*128)
        for ident in range(1,8):
            index=9 if ident==7 else ident
            self.write(HASH+ident*8,U32(0x9100+ident)+U32(index))
            self.write(ROWS+index*100,U32(3 if ident==7 else 1));self.write(FLAGS+index*12,U32(1))

    def step(self,uc,address,size,user):
        g.need(address not in [GAME+b for b,e in g.GROUPS+actions.GROUPS],'Main flow called an original relocated entry')
        rcx,rdx,r8=(self.value(n) for n in ('rcx','rdx','r8'))
        if address==ACTIONS_CODE+self.action_image.reset:self.reset_calls+=1
        if address==MAIN_CODE+self.main_art['mapping'][0x660ca9] and not self.unwound:
            values=[self.value(n) for n in NAMES]
            for n in range(6,13):
                x=self.value(f'xmm{n}');values.extend((x&((1<<64)-1),x>>64))
            registers=(c.c_uint64*22)(*values)
            stack=(c.c_ubyte*0x300).from_buffer_copy(self.read(SP-0x200,0x300))
            status=self.dll.resource_main_unwind(c.byref(self.main_image),address-MAIN_CODE,self.value('rsp')-SP,registers,stack,STOP)
            g.need(status==0,f'Resource main GS unwind failed: {status}');self.unwound=True
        if address==GAME+0x635610:
            g.need(r8==3 and 0xb200<=rdx<0xb208,'Availability query lost resource identity/type');self.scanned.append(rdx)
        elif address==GAME+0xbde430:
            g.need(rcx==0xfd97c115 and rdx==(1<<64)-2 and self.value('r9')==1,'Main reset command changed')
            g.need(self.read(r8,16)==U32(1)+U32(4)+U64((0x9100<<8)|1),'Main reset lost shared first descriptor');self.reset_commands+=1
        elif address==GAME+0xfd97e0 and rdx==0xdb5dd0ac:
            g.need(rcx==0x800 and r8==MANAGER+0x12ee8,'Availability notification lost controller identity')
            self.available_counts.append(struct.unpack('<I',self.read(r8,4))[0])
        elif address==GAME+0x2088770:g.need(rcx==self.cookie,'Resource main cookie value changed')
        elif address==GAME+0x11957c0:self.leaf_calls+=1
        super().step(uc,address,size,user)
        if address==GAME+0x635610:uc.reg_write(R('rax'),int(rdx not in (0xb204,0xb207)))
        elif address==GAME+0xfd9a40:uc.reg_write(R('rax'),(rcx<<8)|1)

    def call_main(self,entry,rcx,rdx=0,r8=0):
        self.standalone_lookup=False;self.stop=None;self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP))
        for i,n in enumerate(NAMES):self.uc.reg_write(R(n),0x11110000+i*0x101)
        for i in range(6,13):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        for n,v in (('rcx',rcx),('rdx',rdx),('r8',r8),('xmm1',struct.unpack('<I',struct.pack('<f',0.125))[0])):self.uc.reg_write(R(n),v)
        try:self.uc.emu_start(MAIN_CODE+entry,0,count=30000)
        except Exception as error:
            rip=self.value('rip');source=max(((v,a) for a,v in self.main_art['mapping'].items() if MAIN_CODE+v<=rip),default=(0,0))[1]
            raise RuntimeError(f'Resource main stop rip={rip:#x}, source={source:#x}') from error
        g.need(self.stop==STOP and self.value('rsp')==SP+8,'Resource main did not return normally')
        for i,n in enumerate(NAMES):g.need(self.value(n)==0x11110000+i*0x101,'Resource main corrupted nonvolatile register')
        for i in range(6,13):g.need(self.value(f'xmm{i}')==(0x66660000+i)|((0xaaaa0000+i)<<64),'Resource main corrupted XMM state')


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_resource_main_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        modules=('session_code','loadout_lifecycle','loadout_consumers','loadout_setup','loadout_group','loadout_interactions','loadout_refresh',
                 'loadout_records','loadout_frame','loadout_mode','loadout_control','loadout_state','loadout_prompt','loadout_countdown','loadout_resources',
                 'loadout_resource_owner','loadout_resource_tick','loadout_resource_events','loadout_resource_ownership','loadout_resource_sync',
                 'loadout_resource_signals','loadout_resource_actions','loadout_resource_main','loadout_resource_update')
        command += [g.PROJECT/'mod/src'/('ep_'+n+'.cpp') for n in modules]
        command += [g.PROJECT/'tests'/('loadout_'+n+'_dll.cpp') for n in ('consumers','setup','resource_owner','resource_main')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.resource_owner_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(OwnerImage)]
    dll.resource_main_actions_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(ActionsImage)]
    dll.resource_main_build.argtypes=[c.POINTER(MainAddresses),c.POINTER(Image)]
    dll.resource_main_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer fixture binding failed')
    a=OwnerAddresses(RecordsAddresses(binding,record_source()),COUNTDOWN,SOURCE);a.records.common.lifecycle.code=OWNER_CODE
    owner_image=OwnerImage();g.need(dll.resource_owner_build(c.byref(a),c.byref(owner_image))==0,'Owner fixture binding failed')
    a.records.common.lifecycle.code=ACTIONS_CODE;action_image=ActionsImage()
    g.need(dll.resource_main_actions_build(c.byref(a),c.byref(action_image))==0,'Action fixture binding failed')
    a.records.common.lifecycle.code=MAIN_CODE;address=MainAddresses(a,ACTIONS_CODE+action_image.reset);image=Image()
    g.need(dll.resource_main_build(c.byref(address),c.byref(image))==0,'Resource main binding failed')
    f=MainFlow(dll,consumer,owner_image,image,action_image,g.build())
    for ident in range(8):
        f.call_owner(owner_image.insert,ident,active=True)
        phases=U32(2)+U32(ident&1)+struct.pack('<f',ident+0.25)
        rows=U32(2)+U32(ident)+b'\1\0\0\0'+bytes(8)
        f.write(SOURCE.phases+ident*12,phases);f.write(SOURCE.rows+ident*20,rows)
        f.payloads[ident]=(U32(1)+phases[4:],rows,bytes(4))
    f.call_main(image.update,MANAGER)
    g.need(f.scanned==list(range(0xb200,0xb208)) and f.available_counts==[2],'Main scan did not cover the expanded bank')
    g.need(f.reset_calls==1 and f.reset_commands==1 and f.read(MANAGER+0x12ee2,1)==b'\0','Main did not use the owned phase reset')
    g.need(f.read(MANAGER+0x12814,4)==U32(2),'Published controller did not receive availability count')
    f.expect(list(range(8)),(8,8,8,8))
    f.call_main(image.query,0,OUTPUT,0x4242)
    g.need(f.read(OUTPUT,4)==U32(0x9107) and f.value('rax')==OUTPUT and f.leaf_calls>1,'Published-object query lost the eighth object/private helper ABI')
    g.need(f.read(RESOURCES,8*0x4c)==b''.join(f.resource_rows) and f.read(RESOURCES+8*0x4c,16)==b'\x7d'*16,'Main scan modified resource storage or its boundary')
    g.need(f.read(MANAGER+0x11d18,4*0x4c)==b'\xa7'*(4*0x4c) and f.read(ROSTER+0xe8,32)==b'\xa7'*32,'Main flow touched old inline banks')
    g.need(f.unwound,'Main GS unwind point not reached')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=CODE+0x30000
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),CODE+0x70000,CODE+0x80000,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,CODE+0xd0000,COUNTDOWN,CODE+0xe0000,OWNER_CODE,SOURCE,CODE+0x110000,CODE+0x120000,CODE+0x130000,CODE+0x140000,CODE+0x150000,ACTIONS_CODE,MAIN_CODE,CODE+0x180000)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one main-update/reset/published-object-query flow',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
