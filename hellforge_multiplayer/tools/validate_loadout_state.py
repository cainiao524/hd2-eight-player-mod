"""One lifecycle -> timer -> context action -> return smoke flow.

Actual prepared bodies run only in owned emulator memory. Native resource
services remain ABI stubs. One Windows unwind point and one common READY/
discard cycle; no game access, old suites, fingerprints or receipts.
"""
from validate_loadout_consumers import READY,BLOCKED
from validate_loadout_setup import countdown_source
from validate_loadout_setup import resource_owner_source
import argparse
import ctypes as c
import json
import subprocess
from pathlib import Path
import generate_loadout_state as g
import generate_loadout_lifecycle as lifecycle
import generate_loadout_control as control
import generate_loadout_mode as mode
import generate_loadout_interactions as interaction
import generate_loadout_consumers as consumers
from validate_loadout_control import (ControlFlow,ControlAddresses,Image as ControlImage,CONTROL,
    ModeImage,MODE,ConsumerImage,Binding,Addresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,ENGINE,
    MAPS,ROSTER,STORAGE,SP,STOP,NAMES,R,U32,U64,SetupAddresses,Placement,GroupAddresses,SETUP,
    record_source,InteractionAddresses,InteractionImage,INTERACTIONS,REFRESH)
from validate_loadout_lifecycle import Image as LifecycleImage
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

STATE=CODE+0xb0000
LIFECYCLE=CODE+0x40000
class StateAddresses(c.Structure):
    _fields_=[('common',Binding),('open_mode',c.c_uint64),('leave',c.c_uint64)]
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','handler_offset','return_screen','change','context_action','tick')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class StateFlow(ControlFlow):
    def __init__(self,dll,consumer,mode_image,control_image,interaction_image,life_image,image,artifact):
        mode_art=mode.build();control_art=control.build();interaction_art=interaction.build()
        super().__init__(dll,consumer,mode_image,mode_art,control_image,control_art,interaction_image,interaction_art)
        self.control_unwound=True;self.state_unwound=False;self.state_image=image;self.state_art=artifact
        self.states=[];self.equipment=[];self.local_ids=[]
        capture=g.Capture();seen=set()
        for art in (consumers.build(),mode_art,control_art,interaction_art):
            for source in art['sources']:
                for ins in capture.md.disasm(source['data'],source['start']):
                    if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in ins.operands):seen.add(ins.address+ins.size+ins.disp)
        life_art=lifecycle.build()
        for base,im,art in ((STATE,image,artifact),(LIFECYCLE,life_image,life_art)):
            self.map(base,im.bytes);self.write(base,bytes(im.data[:im.bytes]))
            for source in art['sources']:
                for ins in capture.md.disasm(source['data'],source['start']):
                    if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                        target=ins.operands[0].imm
                        if not any(s['start']<=target<s['end'] for s in art['sources']):
                            self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                    for op in ins.operands:
                        if op.type!=X86_OP_MEM or op.mem.base!=X86_REG_RIP:continue
                        target=ins.address+ins.size+ins.disp
                        if target in seen:continue
                        seen.add(target);self.map(GAME+target,16)
                        if ins.mnemonic=='lea':continue
                        self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        self.original_targets.update(GAME+a for a in (0x146ac60,0x1470740,0x146abc0,0x146f510))
        self.write(SCREEN+0x27d0,U32(7))
        for offset,value in ((0,0x701),(0x60,0x703),(0xc0,0x704)):self.write(RECORDS+7*0x9f0+offset,U32(value))

    def step(self,uc,address,size,user):
        if address==STATE+self.state_image.change:self.states.append(self.value('rdx'))
        if address==STATE+self.state_art['mapping'][0x146afb2] and not self.state_unwound:
            values=[self.value(n) for n in NAMES]
            for i in (6,7):
                value=self.value(f'xmm{i}');values.extend((value&((1<<64)-1),value>>64))
            registers=(c.c_uint64*12)(*values);stack=(c.c_ubyte*0x400).from_buffer_copy(self.read(SP-0x300,0x400))
            result=self.dll.state_unwind(c.byref(self.state_image),address-STATE,self.value('rsp')-SP,registers,stack,STOP)
            g.need(result==0,f'State unwind failed: {result}');self.state_unwound=True
        rdx=self.value('rdx')
        if address==GAME+0x13656f0:self.equipment.append((rdx,self.value('r8'),self.value('r9')))
        if address==GAME+0x661fa0:self.local_ids.append(self.value('r8'))
        super().step(uc,address,size,user)
        if address==GAME+0x661fa0:self.write(rdx,U32(0x777))

    def operation(self,base,offset):
        self.uc.reg_write(R('xmm9'),0x66660009+(0xaaaa0009<<64));self.uc.reg_write(R('r8'),0)
        self.uc.reg_write(R('xmm1'),0x3f800000)
        try:self.invoke(base-CODE+offset)
        except Exception as error:
            regs={n:hex(self.value(n)) for n in ('rip','rax','rbx','rcx','rdx','rsi','rdi','r8','r9','r11','r14','rsp')}
            raise AssertionError(f'State flow registers={regs}: {error}') from error


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_state_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        command += [g.PROJECT/'mod/src'/n for n in ('ep_session_code.cpp','ep_loadout_lifecycle.cpp','ep_loadout_consumers.cpp','ep_loadout_setup.cpp','ep_loadout_group.cpp','ep_loadout_interactions.cpp','ep_loadout_refresh.cpp','ep_loadout_records.cpp','ep_loadout_frame.cpp','ep_loadout_mode.cpp','ep_loadout_control.cpp','ep_loadout_state.cpp','ep_loadout_prompt.cpp','ep_loadout_countdown.cpp','ep_loadout_resources.cpp','ep_loadout_resource_owner.cpp','ep_loadout_resource_tick.cpp')]
        command += [g.PROJECT/'tests'/n for n in ('loadout_consumers_dll.cpp','loadout_setup_dll.cpp','loadout_mode_dll.cpp','loadout_control_dll.cpp','loadout_interactions_dll.cpp','loadout_lifecycle_dll.cpp','loadout_state_dll.cpp')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.mode_build.argtypes=[c.POINTER(Binding),c.POINTER(ModeImage)]
    dll.control_build.argtypes=[c.POINTER(ControlAddresses),c.POINTER(ControlImage)]
    dll.interaction_build.argtypes=[c.POINTER(InteractionAddresses),c.POINTER(InteractionImage)]
    dll.state_build.argtypes=[c.POINTER(StateAddresses),c.POINTER(Image)]
    dll.loadout_build.argtypes=[c.POINTER(Addresses),c.c_uint64,c.POINTER(LifecycleImage)]
    dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.state_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer binding failed')
    binding.lifecycle.code=MODE;mode_image=ModeImage();g.need(dll.mode_build(c.byref(binding),c.byref(mode_image))==0,'Mode binding failed')
    binding.lifecycle.code=INTERACTIONS;ib=InteractionAddresses(binding,REFRESH);interaction_image=InteractionImage()
    g.need(dll.interaction_build(c.byref(ib),c.byref(interaction_image))==0,'Interaction binding failed')
    binding.lifecycle.code=STATE;a=StateAddresses(binding,MODE+mode_image.open,CONTROL);image=Image()
    g.need(dll.state_build(c.byref(a),c.byref(image))==0,'State binding failed')
    binding.lifecycle.code=CONTROL;cb=ControlAddresses(binding,MODE+mode_image.mode,INTERACTIONS+interaction_image.input,INTERACTIONS+interaction_image.edit,STATE+image.return_screen,READY,BLOCKED)
    control_image=ControlImage();g.need(dll.control_build(c.byref(cb),c.byref(control_image))==0,'Control binding failed')
    binding.lifecycle.code=LIFECYCLE;life_image=LifecycleImage()
    g.need(dll.loadout_build(c.byref(binding.lifecycle),STATE+image.change,c.byref(life_image))==0,'Lifecycle binding failed')
    f=StateFlow(dll,consumer,mode_image,control_image,interaction_image,life_image,image,g.build())
    f.operation(LIFECYCLE,life_image.transition)
    g.need(f.read(SCREEN+0x27398c,4)==U32(6) and f.read(SCREEN+0x273988,4)==U32(0x3e800000),'Lifecycle did not use native state-six delay')
    # Select the ordinary screen presentation before the timer expires;
    # clear both the lifecycle's presentation flag and fixture sentinels.
    for offset in (0x27fc,0x2808,0x2809,0x280e):f.write(SCREEN+offset,b'\0')
    f.operation(STATE,image.tick)
    g.need(f.read(SCREEN+0x27398c,4)==U32(0) and f.read(SCREEN+0x273988,4)==U32(0xbf800000) and f.state_unwound,'Timer did not leave then tail-call state zero')
    g.need([x[1] for x in f.controls if x[0]==0x18a0fd0]==[WIDGETS+i*0x1ee18+0x1fa8 for i in range(8)],'Timer leave omitted extra widgets')
    f.write(SCREEN+0x27fb,b'\x01');f.operation(STATE,image.context_action)
    g.need(f.read(SCREEN+8,4)==U32(1) and f.mode_calls==[1],'Context action did not use the owned mode-open wrapper')
    f.observed.clear();f.write(STORAGE+0x584,U32(10));f.operation(STATE,image.return_screen)
    g.need(f.states==[6,0,2] and f.read(SCREEN+0x27398c,4)==U32(2),'Return did not use the owned state switch')
    g.need([(x[1],x[2],x[3]) for x in f.observed if x[0]==0x189e080]==[(WIDGETS+i*0x1ee18,0,1) for i in range(8)],'State switch omitted extra widgets')
    g.need(f.equipment==[(1,1,0x701),(3,2,0x703),(4,4,0x704)],'Return selected the wrong records or widened equipment categories')
    g.need(f.local_ids==[0x1000]*3 and f.read(STORAGE+0x584,4)==U32(0),'State read/wrote stale local roster storage')
    for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
        g.need(f.read(SCREEN+begin,end-begin)==f.inline[begin:end],'State touched old inline storage/maps')
    g.need(f.read(WIDGETS+8*0x1ee18,16)==b'\x7c'*16 and f.read(RECORDS+8*0x9f0,16)==b'\x6b'*16,'State crossed player storage capacity')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=SETUP
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,LIFECYCLE,CODE,INTERACTIONS,REFRESH,record_source(),CODE+0x70000,CODE+0x80000,MODE,CONTROL,STATE,CODE+0xc0000,CODE+0xd0000,countdown_source(),CODE+0xe0000,CODE+0xf0000,resource_owner_source(),CODE+0x110000)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one lifecycle/timer/context/return flow and common preparation',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
