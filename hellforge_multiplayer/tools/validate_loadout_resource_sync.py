"""One resource-state emission -> dense move -> receive -> event flow.

Only the owned-memory flow below runs. Native hash/allocator/effect services
are explicit ABI stubs; row/phase fixtures do not prove their producers or
network delivery. No game access, full regression, or receipts.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_resource_sync as g
import generate_loadout_resource_signals as signals
import generate_loadout_resource_owner as owner
from validate_loadout_resource_owner import (OwnerFlow,OwnerAddresses,Image as OwnerImage,
    ConsumerImage,Binding,Addresses,RecordsAddresses,record_source,countdown_source,SOURCE,
    OWNER,OWNER_CODE,TABLE,SetupAddresses,Placement,GroupAddresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,
    REJECT,ENGINE,MAPS,ROSTER,STORAGE,SP,STOP,NAMES,R,U32,U64,READY)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

SYNC_CODE=CODE+0x140000;SIGNALS_CODE=CODE+0x150000
PAYLOAD=OWNER+0x62000;EVENTS=OWNER+0x63000;COUNT=OWNER+0x63100;CURSOR=OWNER+0x63200
ALLOCATOR=OWNER+0x64000;ALLOCATOR_HANDLE=OWNER+0x64080;STREAM=OWNER+0x65000
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','emit_initial','receive')]+[('data',c.c_ubyte*g.MAX_IMAGE)]
class SignalsImage(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','finish','reset_effect')]+[('data',c.c_ubyte*signals.MAX_IMAGE)]


class StateFlow(OwnerFlow):
    def __init__(self,dll,consumer,owner_image,image,signal_image,artifact,signal_artifact):
        super().__init__(dll,consumer,owner_image,owner.build())
        self.image=image;self.artifact=artifact;self.initial_unwound=False;self.allocations=0;self.events=[]
        self.images=((SYNC_CODE,image,artifact,g.GROUPS),(SIGNALS_CODE,signal_image,signal_artifact,signals.GROUPS))
        capture=g.Capture()
        for base,im,art,groups in self.images:
            self.map(base,im.bytes);self.write(base,bytes(im.data[:im.bytes]))
            for source in art['sources']:
                for ins in capture.md.disasm(source['data'],source['start']):
                    if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                        target=ins.operands[0].imm
                        if not any(b<=target<e for b,e in groups):
                            self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                    for op in ins.operands:
                        if op.type!=X86_OP_MEM or op.mem.base!=X86_REG_RIP:continue
                        target=ins.address+ins.size+ins.disp;self.map(GAME+target,16)
                        self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        self.write(GAME+0x3326428,U64(OWNER))
        self.write(ALLOCATOR_HANDLE,U64(ALLOCATOR));self.write(PAYLOAD,b'\xcc'*20)
        self.write(EVENTS,b'\xa5'*16+b'\xcc'*16+b'\x7d'*16);self.write(COUNT,U32(1)+b'\x7d'*12)
        self.write(STREAM,b'\xa5'*4+U32(4)+b'\x7d'*16);self.write(CURSOR,U32(4)+b'\x7d'*12)
        for ident in range(8):self.write(self.object(ident)+0x14,U32(1))

    def step(self,uc,address,size,user):
        g.need(address not in [GAME+b for b,e in g.GROUPS+signals.GROUPS],'State path executed an original relocated callback')
        rcx,rdx,r8,r9=(self.value(n) for n in ('rcx','rdx','r8','r9'))
        if address==SYNC_CODE+self.image.emit_initial:
            self.initial_sp=self.value('rsp');self.initial_registers=self.snapshot()
        if address==SYNC_CODE+self.artifact['mapping'][0x66be49] and not self.initial_unwound:
            stack=(c.c_ubyte*0x200).from_buffer_copy(self.read(self.initial_sp-0x100,0x200))
            status=self.dll.resource_sync_unwind(c.byref(self.image),address-SYNC_CODE,self.value('rsp')-self.initial_sp,
                self.snapshot(),self.initial_registers,stack,STOP)
            g.need(status==0,f'Initial state emitter unwind failed: {status}');self.initial_unwound=True
        if address==GAME+0x635f20:
            g.need(rdx==0x9107,'Phase reset selected a different object');self.events.append('phase-reset')
        elif address==GAME+0x808810:
            g.need(rcx==ENGINE and rdx==0x9107 and r8==0x6b9cab48 and not r9,'Resource effect dispatch changed')
            g.need(self.read(self.value('rsp')+0x28,4)==bytes(4),'Resource effect fifth argument changed');self.events.append('reset')
        elif address==GAME+0xfdd750:
            g.need(rdx==0x9107 and r8==0x107869ce and not r9,'Resource secondary effect selected a different object');self.events.append('effect')
        elif address==GAME+0x7caf40:
            g.need(rcx==ENGINE and rdx==0x9107 and r8==0x514 and not r9,'Resource completion effect changed');self.events.append('finish')
        elif address==GAME+0xfd97e0:
            g.need(rcx==0x807 and rdx==0x82830aed and r8==SOURCE.states and self.read(r8,4)==U32(5),'Completion replicated stale or wrong state')
            self.events.append('replicate-5')
        super().step(uc,address,size,user)
        if address==GAME+0x173b8d0:
            g.need(rcx==ALLOCATOR and rdx==4 and r8==4 and not self.allocations,'Initial payload allocation ABI changed')
            self.allocations+=1;uc.reg_write(R('rax'),PAYLOAD)

    def call_state(self,base,entry,args,stack_args=()):
        self.standalone_lookup=False;self.stop=None;self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP))
        for i,n in enumerate(NAMES):self.uc.reg_write(R(n),0x11110000+i*0x101)
        for i in range(6,9):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        for n,v in zip(('rcx','rdx','r8','r9'),args):self.uc.reg_write(R(n),v)
        for i,v in enumerate(stack_args):self.write(SP+0x28+i*8,U64(v))
        try:self.uc.emu_start(base+entry,0,count=30000)
        except Exception as error:
            rip=self.value('rip');art=next(a for b,im,a,groups in self.images if b==base)
            source=max(((v,a) for a,v in art['mapping'].items() if base+v<=rip),default=(0,0))[1]
            raise RuntimeError(f'Resource state stop rip={rip:#x}, source={source:#x}') from error
        g.need(self.stop==STOP and self.value('rsp')==SP+8,'Resource state callback did not return normally')
        for i,n in enumerate(NAMES):g.need(self.value(n)==0x11110000+i*0x101,'Resource state callback corrupted nonvolatile register')
        for i in range(6,9):g.need(self.value(f'xmm{i}')==(0x66660000+i)|((0xaaaa0000+i)<<64),'Resource state callback corrupted XMM state')


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_resource_sync_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        modules=('session_code','loadout_lifecycle','loadout_consumers','loadout_setup','loadout_group','loadout_interactions','loadout_refresh',
                 'loadout_records','loadout_frame','loadout_mode','loadout_control','loadout_state','loadout_prompt','loadout_countdown','loadout_resources',
                 'loadout_resource_owner','loadout_resource_tick','loadout_resource_events','loadout_resource_ownership','loadout_resource_sync','loadout_resource_signals')
        command += [g.PROJECT/'mod/src'/('ep_'+n+'.cpp') for n in modules]
        command += [g.PROJECT/'tests'/('loadout_'+n+'_dll.cpp') for n in ('consumers','setup','resource_owner','resource_sync','resource_signals')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.resource_owner_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(OwnerImage)]
    dll.resource_sync_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(Image)]
    dll.resource_signals_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(SignalsImage)]
    for name,image_type in (('resource_owner_unwind',OwnerImage),('resource_sync_unwind',Image)):
        getattr(dll,name).argtypes=[c.POINTER(image_type),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer fixture binding failed')
    a=OwnerAddresses(RecordsAddresses(binding,record_source()),countdown_source(),SOURCE);a.records.common.lifecycle.code=OWNER_CODE
    owner_image=OwnerImage();g.need(dll.resource_owner_build(c.byref(a),c.byref(owner_image))==0,'Owner fixture binding failed')
    a.records.common.lifecycle.code=SYNC_CODE;image=Image();g.need(dll.resource_sync_build(c.byref(a),c.byref(image))==0,'Resource sync binding failed')
    a.records.common.lifecycle.code=SIGNALS_CODE;signal_image=SignalsImage()
    g.need(dll.resource_signals_build(c.byref(a),c.byref(signal_image))==0,'Resource signals binding failed')
    f=StateFlow(dll,consumer,owner_image,image,signal_image,g.build(),signals.build())
    for ident in range(8):
        f.call_owner(owner_image.insert,ident,active=True)
        # Input fixtures for the callbacks; no claim of physical pod creation.
        payloads=(U32(1)+U32(0)+struct.pack('<f',0.25),U32(2)+U32(ident)+b'\x01\0\0\0'+bytes(8),U32(1+ident%3))
        for base,stride,data in zip((SOURCE.phases,SOURCE.rows,SOURCE.states),(12,20,4),payloads):f.write(base+ident*stride,data)
        f.payloads[ident]=payloads
    f.call_state(SYNC_CODE,image.emit_initial,(OWNER,f.object(7),0,EVENTS),(COUNT,ALLOCATOR_HANDLE))
    g.need(f.read(EVENTS,16)==b'\xa5'*16 and f.read(EVENTS+16,16)==U32(0x82830aed)+U32(1)+U64(PAYLOAD),'Initial state did not append the native record')
    g.need(f.read(COUNT,16)==U32(2)+b'\x7d'*12 and f.read(EVENTS+32,16)==b'\x7d'*16,'Initial emission crossed output count/record bounds')
    g.need(f.read(PAYLOAD,20)==bytes(4)+b'\xcc'*16 and f.read(SOURCE.states+7*4,4)==bytes(4),'Initial state did not reset eighth object/payload')
    f.payloads[7]=(*f.payloads[7][:2],U32(0))
    f.call_owner(owner_image.remove,0);f.expect([7,1,2,3,4,5,6],(8,7,7,7))
    # Native owned-prefix removal also calls the move entry for an unchanged
    # boundary index; its guarded self-move is intentionally a no-op.
    g.need([pair for pair in f.moves if pair[0]!=pair[1]]==[(0,7)] and f.hash_erases==[0x9100],'Removal did not relocate the eighth object through the shared move')
    f.call_state(SYNC_CODE,image.receive,(OWNER,0x9107,STREAM,CURSOR))
    g.need(f.read(SOURCE.states,4)==U32(4) and f.read(SOURCE.states+7*4,4)==bytes(4),'Received state ignored the new hash ordinal')
    g.need(f.read(CURSOR,16)==U32(8)+b'\x7d'*12 and f.read(STREAM,24)==b'\xa5'*4+U32(4)+b'\x7d'*16,'Reception changed packet data or consumed the wrong extent')
    f.call_state(SIGNALS_CODE,signal_image.reset_effect,(OWNER,0x9107,0,0))
    f.call_state(SIGNALS_CODE,signal_image.finish,(OWNER,7,0,0))
    f.payloads[7]=(*f.payloads[7][:2],U32(5));f.expect([7,1,2,3,4,5,6],(8,7,7,7))
    # A delayed notification for the removed object must be a normal no-op.
    f.call_state(SIGNALS_CODE,signal_image.reset_effect,(OWNER,0x9100,0,0))
    f.expect([7,1,2,3,4,5,6],(8,7,7,7))
    g.need(f.events==['phase-reset','reset','effect','finish','replicate-5'],'Resource notification sequence changed or a removed object emitted effects')
    g.need(f.initial_unwound and f.move_unwound and f.allocations==1,'Emitter/move did not retain unwind metadata and allocator ABI')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=CODE+0x30000
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),CODE+0x70000,CODE+0x80000,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,CODE+0xd0000,countdown_source(),CODE+0xe0000,OWNER_CODE,SOURCE,CODE+0x110000,CODE+0x120000,CODE+0x130000,SYNC_CODE,SIGNALS_CODE)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one initial-state/dense-move/receive/notification flow',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
