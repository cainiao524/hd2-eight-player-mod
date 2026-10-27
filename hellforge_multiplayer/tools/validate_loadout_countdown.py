"""One frame countdown -> eight assignments -> repeat lookup flow.

Owned memory, real relocated countdown/lookup/reset bodies, ABI stubs for
external resource/event services; one unwind snapshot and common preparation.
No game access, receipts, fingerprints or old regression suites.
"""
from validate_loadout_setup import resource_owner_source
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_countdown as g
import generate_loadout_frame as frame
import generate_loadout_records as records
import generate_loadout_mode as mode
import generate_loadout_state as state
from validate_loadout_frame import (FrameFlow,FrameAddresses,Image as FrameImage,FRAME,
    RecordsAddresses,RecordsImage,ConsumerImage,Binding,Addresses,record_source,SetupAddresses,
    Placement,GroupAddresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,ENGINE,MAPS,ROSTER,STORAGE,
    PEER,SYNC,SETUP,SP,STOP,NAMES,R,U32,U64,READY,BLOCKED)
from validate_loadout_setup import CountdownSource,countdown_source
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

COUNTDOWN=CODE+0xd0000
SOURCE=countdown_source();MANAGER=SOURCE.manager;RESOURCES=SOURCE.resources
class CountdownAddresses(c.Structure):
    _fields_=[('records',RecordsAddresses),('source',CountdownSource),('context_action',c.c_uint64),('transition',c.c_uint64)]
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','update','resource_lookup','reset_timers')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class CountdownFlow(FrameFlow):
    def __init__(self,dll,consumer,record_image,frame_image,image,artifact):
        super().__init__(dll,consumer,record_image,records.build(),frame_image,frame.build())
        self.frame_unwound=True;self.countdown_unwound=False;self.countdown_image=image;self.countdown_art=artifact
        self.allocations=[];self.lookups=[];self.free_checks=[];self.resets=0;self.lookup_results=[]
        self.external.discard(COUNTDOWN);self.map(COUNTDOWN,image.bytes);self.write(COUNTDOWN,bytes(image.data[:image.bytes]))
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
                    if ins.mnemonic=='lea':continue
                    self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        self.write(GAME+0x3326468,U64(ROSTER));self.write(GAME+0x33265f0,U64(MANAGER))
        self.map(MANAGER,0x60000);self.write(MANAGER+0x24,U32(2))
        for i in range(2):
            actor=MANAGER+0x30000+i*32;self.write(MANAGER+0x50+i*8,U64(actor))
            self.write(actor+0x10,U32(0x7fff));self.write(MANAGER+0x12ee3+i*0x54,b'\x01')
        # Replication is disabled in this fixture; the original reset still
        # clears both actor flags. Native queue capacity is not established here.
        self.write(GAME+0x346bf98,U64(MANAGER+0x40000));self.write(MANAGER+0x40008,U64(MANAGER+0x41000))
        self.write(MANAGER+0x4401d,b'\x01')
        self.catalog=MANAGER+0x50000;self.table=MANAGER+0x51000;self.rows=MANAGER+0x52000
        self.write(GAME+0x3326d78,U64(self.catalog));self.write(self.catalog+0x20,U64(self.table)+U32(16)+U32(0xffffffff)+U32(1))
        self.write(self.catalog+0x48,U64(self.rows));self.write(self.table,b'\xff'*128)
        self.resource_order=[6,2,5,0,7,4,1,3]
        for dense in range(8):
            self.write(self.table+dense*8,U32(0x6000+dense)+U32(dense));self.write(self.rows+dense*64,U32(0xdead))
            self.write(RESOURCES+dense*0x4c,U32(0x9000+self.resource_order[dense]))
        self.write(MANAGER+0x11d18,b'\xa7'*(4*0x4c));self.write(RESOURCES+8*0x4c,b'\x7d'*16)
        self.write(SCREEN+0x27fe,b'\x01');self.write(SCREEN+0x273997,b'\0')
        self.write(SCREEN+0x280a,b'\0');self.write(SCREEN+0x280b,b'\0')
        self.write(SCREEN+0x27399c,U32(0))

    def saved_registers(self):
        values=[self.value(n) for n in NAMES]
        for n in (6,7):
            value=self.value(f'xmm{n}');values.extend((value&((1<<64)-1),value>>64))
        return (c.c_uint64*12)(*values)

    def step(self,uc,address,size,user):
        g.need(address not in (GAME+0x146a5b0,GAME+0x661fa0,GAME+0x662880),'Countdown used an original moved callee')
        rcx,rdx,r8=self.value('rcx'),self.value('rdx'),self.value('r8')
        if address==COUNTDOWN+self.countdown_image.update:
            self.entry_sp=self.value('rsp');self.entry_registers=self.saved_registers()
            self.return_address=struct.unpack('<Q',self.read(self.entry_sp,8))[0]
        if address==COUNTDOWN+self.countdown_image.resource_lookup:self.lookups.append(r8)
        if address==COUNTDOWN+self.countdown_image.reset_timers:self.resets+=1
        if address==COUNTDOWN+self.countdown_art['mapping'][0x146a6ec]:
            self.lookup_results.append(struct.unpack('<I',self.read(self.value('rax'),4))[0])
        if address==COUNTDOWN+self.countdown_art['mapping'][0x146a79c] and not self.countdown_unwound:
            stack=(c.c_ubyte*0x200).from_buffer_copy(self.read(self.entry_sp-0x100,0x200))
            status=self.dll.countdown_unwind(c.byref(self.countdown_image),address-COUNTDOWN,self.value('rsp')-self.entry_sp,
                self.saved_registers(),self.entry_registers,stack,self.return_address)
            g.need(status==0,f'Countdown unwind failed: {status}');self.countdown_unwound=True
        if address==GAME+0xbde430 and rcx==0x42f5d99f:
            g.need(self.read(r8,8)==U32(1)+U32(4),'Resource event argument type changed')
            resource=struct.unpack('<Q',self.read(r8+8,8))[0];dense=rdx-PEER
            g.need(0<=dense<8 and 0x9000<=resource<0x9008,'Resource event lost player/resource identity')
            self.allocations.append((dense,resource));self.write(self.rows+dense*64,U32(resource))
        super().step(uc,address,size,user)
        if address==GAME+0x635610:
            g.need(r8==3,'Resource category changed');self.free_checks.append(rdx)
            uc.reg_write(R('rax'),int(rdx not in [v for _,v in self.allocations]))
        elif address==GAME+0x606630:
            g.need(rcx==MANAGER and 0x1000<=r8<0x1008,'Lookup component/source identity changed')
            self.write(rdx,U32(0x6000+r8-0x1000));uc.reg_write(R('rax'),rdx)
        elif address==GAME+0xfd9a40:uc.reg_write(R('rax'),rcx)


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_countdown_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        modules=('session_code','loadout_lifecycle','loadout_consumers','loadout_setup','loadout_group',
                 'loadout_interactions','loadout_refresh','loadout_records','loadout_frame','loadout_mode',
                 'loadout_control','loadout_state','loadout_prompt','loadout_countdown','loadout_resources','loadout_resource_owner','loadout_resource_tick','loadout_resource_events','loadout_resource_ownership','loadout_resource_sync','loadout_resource_signals','loadout_resource_actions','loadout_resource_main')
        command += [g.PROJECT/'mod/src'/('ep_'+n+'.cpp') for n in modules]
        command += [g.PROJECT/'tests'/('loadout_'+n+'_dll.cpp') for n in ('consumers','setup','records','frame','countdown')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.countdown_build.argtypes=[c.POINTER(CountdownAddresses),c.POINTER(Image)]
    dll.records_build.argtypes=[c.POINTER(RecordsAddresses),c.POINTER(RecordsImage)]
    dll.frame_build.argtypes=[c.POINTER(FrameAddresses),c.POINTER(FrameImage)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.countdown_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer binding failed')
    binding.lifecycle.code=SYNC;rb=RecordsAddresses(binding,record_source());record_image=RecordsImage()
    g.need(dll.records_build(c.byref(rb),c.byref(record_image))==0,'Record binding failed')
    a=CountdownAddresses(rb,SOURCE,CODE+0xb0000+state.build()['entries'][2],CODE+0x40000)
    a.records.common.lifecycle.code=COUNTDOWN;image=Image()
    g.need(dll.countdown_build(c.byref(a),c.byref(image))==0,'Countdown binding failed')
    fb=FrameAddresses(rb,SYNC,CODE+consumer.update,CODE+consumer.lookup,CODE+0x90000+mode.build()['entries'][1],
                     CODE+0xa0000,CODE+0xb0000+state.build()['entries'][1],CODE+0xb0000,CODE+0xc0000,READY,BLOCKED,COUNTDOWN)
    fb.records.common.lifecycle.code=FRAME;frame_image=FrameImage()
    g.need(dll.frame_build(c.byref(fb),c.byref(frame_image))==0,'Frame binding failed')
    f=CountdownFlow(dll,consumer,record_image,frame_image,image,g.build());f.invoke(FRAME-CODE+frame_image.frame)
    expected=[(i,0x9000+f.resource_order[i]) for i in range(8)]
    g.need(f.allocations==expected and f.countdown_unwound,'Frame countdown did not assign eight distinct resources')
    g.need(f.lookups==list(range(0x1000,0x1008)) and f.lookup_results==[0xffffffff]*8,'Initial assignment lookup changed')
    g.need(f.resets==1 and all(f.read(MANAGER+0x12ee3+i*0x54,1)==b'\0' for i in range(2)),'Native timer reset was omitted')
    # After elapsed time, actual lookup must find all eight newly assigned rows.
    f.uc.reg_write(R('xmm1'),struct.unpack('<I',struct.pack('<f',3.0))[0])
    f.invoke(COUNTDOWN-CODE+image.update)
    g.need(f.allocations==expected and f.lookup_results[8:]==[v for _,v in expected],'Repeat countdown lost expanded assignments or allocated duplicates')
    g.need(f.free_checks==[v for _,v in expected]*2 and f.resets==2,'Resource scan stopped at four')
    g.need(f.read(MANAGER+0x11d18,4*0x4c)==b'\xa7'*(4*0x4c) and f.read(RESOURCES+8*0x4c,16)==b'\x7d'*16,'Resource storage boundary changed')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=SETUP
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),SYNC,FRAME,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,COUNTDOWN,SOURCE,CODE+0xe0000,CODE+0xf0000,resource_owner_source(),CODE+0x110000,CODE+0x120000,CODE+0x130000,CODE+0x140000,CODE+0x150000,CODE+0x160000,CODE+0x170000)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one frame/countdown resource allocation and repeat lookup flow',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
