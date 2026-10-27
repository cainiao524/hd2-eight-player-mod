"""One eight-object insert/remove/reuse flow in owned emulator memory.

Native callbacks, field moves, capacity checks and hash value rewrites run;
only native hash insertion/erase services are ABI stubs. No other suite runs.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_resource_owner as g
from validate_loadout_consumers import (Flow,Binding,Addresses,Image as ConsumerImage,
    GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,ENGINE,SP,NAMES,R,U64,U32,STOP,MAPS,ROSTER,STORAGE,READY)
from validate_loadout_setup import (SetupAddresses,Placement,GroupAddresses,ResourceOwnerSource,
    RecordSource,record_source,countdown_source,resource_owner_source)
from validate_loadout_records import RecordsAddresses
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

OWNER_CODE=CODE+0xf0000
SOURCE=resource_owner_source();OWNER=SOURCE.owner;TABLE=OWNER+0x60000
class OwnerAddresses(c.Structure):
    _fields_=[('records',RecordsAddresses),('countdown_source',type(countdown_source())),('source',ResourceOwnerSource)]
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','insert','enqueue','move','remove')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class OwnerFlow(Flow):
    def __init__(self,dll,consumer,image,artifact):
        import generate_loadout_consumers as consumers
        super().__init__(consumers.build(),dll,consumer)
        self.owner_image=image;self.owner_art=artifact;self.moves=[];self.move_unwound=False;self.payloads={}
        self.map(OWNER,0x70000);self.map(OWNER_CODE,image.bytes);self.write(OWNER_CODE,bytes(image.data[:image.bytes]))
        capture=g.Capture()
        for source in artifact['sources']:
            for ins in capture.md.disasm(source['data'],source['start']):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not any(b<=target<e for b,e in g.GROUPS):
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for op in ins.operands:
                    if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                        target=ins.address+ins.size+ins.disp;self.map(GAME+target,16)
                        self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        self.write(GAME+0x3326428,U64(OWNER));self.write(OWNER+0x50,U64(TABLE)+U32(16)+U32(0xffffffff)+U32(1))
        self.write(TABLE,b'\xff'*128);self.write(OWNER+0x68,b'\xa7'*0xb0)
        for base,stride in ((SOURCE.objects,8),(SOURCE.phases,12),(SOURCE.rows,20),(SOURCE.states,4)):
            self.write(base+8*stride,b'\x7d'*16)
        for ident in range(9):
            self.write(self.object(ident)+8,U32(0x9100+ident)+U32(0x3000+ident)+U32(0x800+ident)+U32(int(ident<3 or ident==7)))
        self.flag=OWNER+0x61000;self.hash_inserts=[];self.hash_erases=[]

    def object(self,ident):return OWNER+0x50000+ident*32
    def snapshot(self):
        values=[self.value(n) for n in NAMES]
        for n in (6,7):
            value=self.value(f'xmm{n}');values.extend((value&((1<<64)-1),value>>64))
        return (c.c_uint64*12)(*values)
    def step(self,uc,address,size,user):
        g.need(address not in [GAME+b for b,e in g.GROUPS],'Owner path called an original relocated function')
        rcx,rdx,r8=self.value('rcx'),self.value('rdx'),self.value('r8')
        if address==OWNER_CODE+self.owner_image.move:
            self.moves.append((rdx,r8));self.move_sp=self.value('rsp');self.move_registers=self.snapshot()
            self.move_return=struct.unpack('<Q',self.read(self.move_sp,8))[0]
        if address==OWNER_CODE+self.owner_art['mapping'][0x66bcb4] and not self.move_unwound:
            stack=(c.c_ubyte*0x200).from_buffer_copy(self.read(self.move_sp-0x100,0x200))
            status=self.dll.resource_owner_unwind(c.byref(self.owner_image),address-OWNER_CODE,self.value('rsp')-self.move_sp,
                self.snapshot(),self.move_registers,stack,self.move_return)
            g.need(status==0,f'Owner dense-move unwind failed: {status}');self.move_unwound=True
        super().step(uc,address,size,user)
        if address==GAME+0x172f790:
            g.need(rcx==OWNER+0x50 and 0x9100<=rdx<=0x9108 and r8<8,'Hash insertion lost owner/key/slot')
            self.write(TABLE+(rdx&15)*8,U32(rdx)+U32(r8));self.hash_inserts.append((rdx,r8));uc.reg_write(R('rax'),r8)
        elif address==GAME+0x172f8a0:
            g.need(rcx==OWNER+0x50,'Hash erase lost owner')
            key,index=struct.unpack('<II',self.read(TABLE+(rdx&15)*8,8));g.need(key==rdx,'Hash erase missed a registered object')
            self.write(TABLE+(rdx&15)*8,b'\xff'*8);self.hash_erases.append(rdx);uc.reg_write(R('rax'),index)

    def call_owner(self,entry,ident,active=False):
        self.standalone_lookup=False;self.stop=None;self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP))
        self.write(self.flag,bytes((active,)))
        for i,n in enumerate(NAMES):self.uc.reg_write(R(n),0x11110000+i*0x101)
        for i in range(6,9):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        for n,v in (('rcx',OWNER),('rdx',self.object(ident)),('r8',self.flag)):self.uc.reg_write(R(n),v)
        try:self.uc.emu_start(OWNER_CODE+entry,0,count=30000)
        except Exception as error:
            rip=self.value('rip');source=max(((v,a) for a,v in self.owner_art['mapping'].items() if OWNER_CODE+v<=rip),default=(0,0))[1]
            raise RuntimeError(f'Owner emulator stop rip={rip:#x}, source={source:#x}') from error
        g.need(self.stop==STOP and self.value('rsp')==SP+8,'Owner callback did not return normally')
        for i,n in enumerate(NAMES):g.need(self.value(n)==0x11110000+i*0x101,'Owner callback corrupted nonvolatile state')

    def mark_record(self,ident):
        key,index=struct.unpack('<II',self.read(TABLE+ident*8,8));g.need(key==0x9100+ident,'Registration did not publish the object key')
        g.need(self.read(SOURCE.rows+index*20,20)==bytes(20),'Registration did not initialize its resource row')
        # Distinct imported state stands in for later engine callbacks; this
        # flow verifies that native dense moves retain every field by identity.
        payloads=(bytes([0x20+ident])*12,bytes([0x40+ident])*20,U32(0x60+ident))
        for base,stride,payload in zip((SOURCE.phases,SOURCE.rows,SOURCE.states),(12,20,4),payloads):self.write(base+index*stride,payload)
        self.payloads[ident]=payloads
    def expect(self,ids,counts):
        g.need(struct.unpack('<4I',self.read(OWNER,16))==counts,'Owner phase counts changed')
        for index,ident in enumerate(ids):
            g.need(self.read(SOURCE.objects+index*8,8)==U64(self.object(ident)),'Dense object identity lost')
            g.need(self.read(TABLE+ident*8,8)==U32(0x9100+ident)+U32(index),'Hash dense ordinal became stale')
            for base,stride,payload in zip((SOURCE.phases,SOURCE.rows,SOURCE.states),(12,20,4),self.payloads[ident]):
                g.need(self.read(base+index*stride,stride)==payload,'Dense move mixed object state')
        g.need(self.read(OWNER+0x68,0xb0)==b'\xa7'*0xb0,'Callback touched original four-slot banks')
        for base,stride in ((SOURCE.objects,8),(SOURCE.phases,12),(SOURCE.rows,20),(SOURCE.states,4)):
            g.need(self.read(base+8*stride,16)==b'\x7d'*16,'Owner bank boundary crossed')


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_resource_owner_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        modules=('session_code','loadout_lifecycle','loadout_consumers','loadout_setup','loadout_group','loadout_interactions','loadout_refresh',
                 'loadout_records','loadout_frame','loadout_mode','loadout_control','loadout_state','loadout_prompt','loadout_countdown','loadout_resources','loadout_resource_owner','loadout_resource_tick','loadout_resource_events','loadout_resource_ownership','loadout_resource_sync','loadout_resource_signals','loadout_resource_actions','loadout_resource_main','loadout_resource_update')
        command += [g.PROJECT/'mod/src'/('ep_'+n+'.cpp') for n in modules]
        command += [g.PROJECT/'tests'/('loadout_'+n+'_dll.cpp') for n in ('consumers','setup','resource_owner')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.resource_owner_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(Image)]
    dll.resource_owner_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer fixture binding failed')
    owner_binding=OwnerAddresses(RecordsAddresses(binding,record_source()),countdown_source(),SOURCE)
    owner_binding.records.common.lifecycle.code=OWNER_CODE;image=Image()
    g.need(dll.resource_owner_build(c.byref(owner_binding),c.byref(image))==0,'Owner binding failed')
    f=OwnerFlow(dll,consumer,image,g.build())
    for ident in range(8):
        f.call_owner(image.insert,ident,active=ident<3 or ident==7);f.mark_record(ident)
    f.expect([0,1,2,7,4,5,6,3],(8,8,8,4))
    f.call_owner(image.remove,1);f.expect([0,7,2,3,4,5,6],(8,7,7,3))
    f.call_owner(image.enqueue,8);f.mark_record(8);f.expect([0,7,2,3,4,5,6,8],(8,8,7,3))
    g.need(f.move_unwound and f.moves==[(7,3),(1,3),(3,7)],'Insert/remove did not use the shared native dense move')
    g.need(f.hash_erases==[0x9101] and len(f.hash_inserts)==9,'Registration/removal native service sequence changed')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=CODE+0x30000
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),CODE+0x70000,CODE+0x80000,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,CODE+0xd0000,countdown_source(),CODE+0xe0000,OWNER_CODE,SOURCE,CODE+0x110000,CODE+0x120000,CODE+0x130000,CODE+0x140000,CODE+0x150000,CODE+0x160000,CODE+0x170000,CODE+0x180000)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one eight-object insert/remove/reuse flow',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
