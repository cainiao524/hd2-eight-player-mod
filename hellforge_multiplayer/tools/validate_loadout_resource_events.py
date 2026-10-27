"""One registration -> property initialization -> publication flow.

The eighth name starts outside capacity, then becomes hellpod8. Property
strings and transforms come from explicit native-service stubs; row metadata
is produced by the relocated callback itself. No live game or other suite.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_resource_events as g
import generate_loadout_resource_owner as owner
from validate_loadout_resource_owner import (OwnerFlow,OwnerAddresses,Image as OwnerImage,
    ConsumerImage,Binding,Addresses,RecordsAddresses,record_source,countdown_source,SOURCE,
    OWNER,OWNER_CODE,SetupAddresses,Placement,GroupAddresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,
    REJECT,ENGINE,MAPS,ROSTER,STORAGE,SP,STOP,NAMES,R,U32,U64,READY)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

EVENTS_CODE=CODE+0x120000
COUNTDOWN=countdown_source();MANAGER=COUNTDOWN.manager;RESOURCES=COUNTDOWN.resources
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','initialize','publish')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class EventsFlow(OwnerFlow):
    def __init__(self,dll,consumer,owner_image,image,artifact):
        super().__init__(dll,consumer,owner_image,owner.build())
        self.events_image=image;self.events_art=artifact;self.init_unwound=False
        self.resets=[];self.name_reads=[];self.transform_reads=[]
        self.map(EVENTS_CODE,image.bytes);self.write(EVENTS_CODE,bytes(image.data[:image.bytes]));self.map(MANAGER,0x60000)
        capture=g.Capture()
        for source in artifact['sources']:
            for ins in capture.md.disasm(source['data'],source['start']):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not any(b<=target<e for b,e in g.GROUPS):
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for op in ins.operands:
                    if op.type!=X86_OP_MEM or op.mem.base!=X86_REG_RIP or ins.mnemonic=='lea':continue
                    target=ins.address+ins.size+ins.disp;self.map(GAME+target,16)
                    self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        self.write(GAME+0x3326428,U64(OWNER));self.write(GAME+0x33265f0,U64(MANAGER))
        self.property_id=GAME+0x3002000;self.property_data=GAME+0x3002010;self.property_name=GAME+0x3002020
        for target in (self.property_id,self.property_data,self.property_name):
            self.external.add(target);self.map(target,1);self.write(target,b'\xc3')
        self.write(GAME+0x3326308,U64(ENGINE));self.write(ENGINE+0x18,U64(ENGINE+0x71000))
        self.write(ENGINE+0x716d8,U64(self.property_id));self.write(ENGINE+0x71090,U64(self.property_data))
        self.write(ENGINE+0xb8,U64(ENGINE+0x72000));self.write(ENGINE+0x72000,U64(ENGINE+0x73000));self.write(ENGINE+0x73010,U64(self.property_name))
        self.write(MANAGER+0x11d18,b'\xa7'*(4*0x4c));self.write(RESOURCES,b'\xa9'*(8*0x4c))
        self.write(RESOURCES+8*0x4c,b'\x7d'*16);self.transforms=[]
        self.names=[f'hellpod{i+1}'.encode() for i in range(8)];self.names[7]=b'hellpod9'
        for ident in range(8):
            self.write(self.object(ident)+0x14,U32(1));self.write(RESOURCES+ident*0x4c,U32(0xffffffff))
            transform=bytes((ident*29+j)%256 for j in range(64));self.transforms.append(transform)
            self.write(MANAGER+0x54000+ident*64,transform)

    def step(self,uc,address,size,user):
        g.need(address not in [GAME+b for b,e in g.GROUPS],'Callback used an original relocated entry')
        g.need(address!=GAME+0x210d170,'Initialization fell back to four-name comparisons')
        rcx,rdx,r8,r9=(self.value(n) for n in ('rcx','rdx','r8','r9'))
        if address==EVENTS_CODE+self.events_image.initialize:
            self.init_sp=self.value('rsp');self.init_registers=self.snapshot()
        if address==EVENTS_CODE+self.events_art['mapping'][0x66ae19] and not self.init_unwound:
            stack=(c.c_ubyte*0x200).from_buffer_copy(self.read(self.init_sp-0x100,0x200))
            status=self.dll.resource_events_unwind(c.byref(self.events_image),address-EVENTS_CODE,self.value('rsp')-self.init_sp,
                self.snapshot(),self.init_registers,stack,STOP)
            g.need(status==0,f'Resource initialization unwind failed: {status}');self.init_unwound=True
        super().step(uc,address,size,user)
        if address==self.property_name:
            g.need(0x3000<=rdx<0x3008 and r8==1 and r9==0xd4c943cb,'Name property ABI changed')
            ident=rdx-0x3000;name=MANAGER+0x52000+ident*32
            self.write(name,self.names[ident]+b'\0');self.write(rcx,U64(name)+U32(3)+U32(0));uc.reg_write(R('rax'),rcx)
            self.name_reads.append(rdx)
        elif address==self.property_id:
            g.need(rdx==0xe4a4586d and 0x3000<=rcx<0x3008,'Transform property identity changed');uc.reg_write(R('rax'),7)
        elif address==self.property_data:
            g.need(rdx==7 and 0x3000<=rcx<0x3008,'Transform property data identity changed')
            self.transform_reads.append(rcx);uc.reg_write(R('rax'),MANAGER+0x54000+(rcx-0x3000)*64)
        elif address==GAME+0x635f20:self.resets.append(rdx)

    def call_event(self,entry,ident):
        self.standalone_lookup=False;self.stop=None;self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP));self.write(self.flag,b'\x01')
        for i,n in enumerate(NAMES):self.uc.reg_write(R(n),0x11110000+i*0x101)
        for i in range(6,9):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        for n,v in (('rcx',OWNER),('rdx',self.object(ident)),('r8',self.flag)):self.uc.reg_write(R(n),v)
        try:self.uc.emu_start(EVENTS_CODE+entry,0,count=30000)
        except Exception as error:
            rip=self.value('rip');source=max(((v,a) for a,v in self.events_art['mapping'].items() if EVENTS_CODE+v<=rip),default=(0,0))[1]
            raise RuntimeError(f'Resource callback stop rip={rip:#x}, source={source:#x}, '+repr({n:hex(self.value(n)) for n in ('rax','rbx','rcx','rdx','rsi','rdi','rbp','r8','r9','r10','r11')})) from error
        g.need(self.stop==STOP and self.value('rsp')==SP+8,'Resource callback did not return normally')
        for i,n in enumerate(NAMES):g.need(self.value(n)==0x11110000+i*0x101,'Resource callback corrupted nonvolatile register')
        for i in range(6,9):g.need(self.value(f'xmm{i}')==(0x66660000+i)|((0xaaaa0000+i)<<64),'Resource callback corrupted XMM state')


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_resource_events_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        modules=('session_code','loadout_lifecycle','loadout_consumers','loadout_setup','loadout_group','loadout_interactions','loadout_refresh',
                 'loadout_records','loadout_frame','loadout_mode','loadout_control','loadout_state','loadout_prompt','loadout_countdown','loadout_resources','loadout_resource_owner','loadout_resource_tick','loadout_resource_events','loadout_resource_ownership')
        command += [g.PROJECT/'mod/src'/('ep_'+n+'.cpp') for n in modules]
        command += [g.PROJECT/'tests'/('loadout_'+n+'_dll.cpp') for n in ('consumers','setup','resource_owner','resource_events')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.resource_owner_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(OwnerImage)]
    dll.resource_events_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(Image)]
    dll.resource_events_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer fixture binding failed')
    a=OwnerAddresses(RecordsAddresses(binding,record_source()),COUNTDOWN,SOURCE);a.records.common.lifecycle.code=OWNER_CODE
    owner_image=OwnerImage();g.need(dll.resource_owner_build(c.byref(a),c.byref(owner_image))==0,'Owner fixture binding failed')
    a.records.common.lifecycle.code=EVENTS_CODE;image=Image();g.need(dll.resource_events_build(c.byref(a),c.byref(image))==0,'Resource callback binding failed')
    f=EventsFlow(dll,consumer,owner_image,image,g.build())
    for ident in range(8):
        f.call_owner(owner_image.insert,ident,active=True)
        # Old metadata is deliberately stale so native reinitialization must
        # produce a new ordinal; the fixture never assigns the final ordinal.
        f.write(SOURCE.phases+ident*12,struct.pack('<IB3xf',2,1,0.25))
        f.write(SOURCE.rows+ident*20,struct.pack('<IIBB2xfI',5,6,1,0,0.5,0x99000000+ident))
        f.call_event(image.initialize,ident);f.call_event(image.publish,ident)
    g.need(f.read(SOURCE.rows+7*20,20)==struct.pack('<IIBB2xfI',2,0xffffffff,0,0,0.5,0x99000007),'Out-of-capacity name retained stale row metadata')
    g.need(f.read(RESOURCES+7*0x4c,0x4c)==U32(0xffffffff)+b'\xa9'*72 and f.transform_reads==list(range(0x3000,0x3007)),'Invalid name published or read a transform')
    f.names[7]=b'hellpod8';f.call_event(image.initialize,7);f.call_event(image.publish,7)
    for ident in range(8):
        g.need(f.read(RESOURCES+ident*0x4c,0x4c)==U32(0x9100+ident)+f.transforms[ident]+b'\xa9'*8,'Callback mixed resource identity/transform or changed reserved bytes')
        g.need(f.read(SOURCE.rows+ident*20,20)==struct.pack('<IIBB2xfI',2,ident,1,0,0.5,0x99000000+ident),'Property callback did not initialize its resource row')
        g.need(f.read(SOURCE.phases+ident*12,12)==struct.pack('<IB3xf',0,0,0.25),'Initialization phase reset changed')
        g.need(f.read(SOURCE.states+ident*4,4)==bytes(4),'Initialization modified the unrelated replicated state')
    g.need(f.name_reads==list(range(0x3000,0x3008))+[0x3007] and f.transform_reads==list(range(0x3000,0x3008)) and f.resets==list(range(0x9100,0x9108))+[0x9107],'Native property/reset callback sequence changed')
    g.need(f.init_unwound and struct.unpack('<4I',f.read(OWNER,16))==(8,8,8,8),'Callback unwind/counts changed')
    g.need(f.read(OWNER+0x68,0xb0)==b'\xa7'*0xb0 and f.read(MANAGER+0x11d18,4*0x4c)==b'\xa7'*(4*0x4c),'Callback touched original four-slot storage')
    for base,stride in ((SOURCE.objects,8),(SOURCE.phases,12),(SOURCE.rows,20),(SOURCE.states,4),(RESOURCES,0x4c)):
        g.need(f.read(base+8*stride,16)==b'\x7d'*16,'Resource bank boundary crossed')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=CODE+0x30000
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),CODE+0x70000,CODE+0x80000,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,CODE+0xd0000,COUNTDOWN,CODE+0xe0000,OWNER_CODE,SOURCE,CODE+0x110000,EVENTS_CODE,CODE+0x130000)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one eight-resource initialization/publication flow',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
