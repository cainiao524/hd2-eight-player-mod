"""One screen input -> mode selection -> cancel -> leave/cleanup smoke flow.

Uses actual prepared control/mode/navigation bodies in owned emulator memory,
with ABI stubs for native services. One Windows unwind snapshot and common
READY/discard cycle. No game, regression suite, receipt or fingerprint access.
"""
import argparse
import ctypes as c
import json
import subprocess
from pathlib import Path
import generate_loadout_control as g
import generate_loadout_mode as mode
import generate_loadout_interactions as interaction
import generate_loadout_consumers as consumers
from validate_loadout_mode import (ModeFlow,Image as ModeImage,MODE,ConsumerImage,Binding,Addresses,
    GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,ENGINE,MAPS,ROSTER,STORAGE,PEER,SP,STOP,NAMES,R,U32,U64,
    SetupAddresses,Placement,GroupAddresses,SETUP,record_source)
from validate_loadout_consumers import Flow,DESCS
from validate_loadout_interactions import InteractionAddresses,Image as InteractionImage,INTERACTIONS,REFRESH
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

CONTROL=CODE+0xa0000
INPUT=ENGINE+0x800000
class ControlAddresses(c.Structure):
    _fields_=[('common',Binding)]+[(n,c.c_uint64) for n in ('mode','input','edit')]
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','leave','screen_input','reset_selection')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class ControlFlow(ModeFlow):
    def __init__(self,dll,consumer,mode_image,mode_art,image,artifact,interaction_image,interaction_art):
        super().__init__(dll,consumer,mode_image,mode_art)
        # This flow takes one control-frame snapshot, not the old standalone
        # mode snapshot (which has a different caller/stack depth).
        self.unwound=True;self.control_unwound=False;self.control_image=image;self.control_art=artifact
        self.choose=False;self.mode_calls=[];self.controls=[];self.input_calls=[]
        seen=set();capture=g.Capture()
        for a in (consumers.build(),mode_art):
            for source in a['sources']:
                for ins in capture.md.disasm(source['data'],source['start']):
                    if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in ins.operands):
                        seen.add(ins.address+ins.size+ins.disp)
        for base,im,art,groups in ((CONTROL,image,artifact,g.GROUPS),(INTERACTIONS,interaction_image,interaction_art,interaction.GROUPS)):
            self.map(base,im.bytes);self.write(base,bytes(im.data[:im.bytes]))
            for source in art['sources']:
                for ins in capture.md.disasm(source['data'],source['start']):
                    if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                        target=ins.operands[0].imm
                        if not any(b<=target<e for b,e in groups):
                            self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                    for op in ins.operands:
                        if op.type!=X86_OP_MEM or op.mem.base!=X86_REG_RIP:continue
                        target=ins.address+ins.size+ins.disp
                        if target in seen:continue
                        seen.add(target);self.map(GAME+target,16)
                        if ins.mnemonic=='lea':continue
                        self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        self.map(INPUT,0x1000);self.write(SCREEN+0x2800,U64(PEER+7))
        self.write(SCREEN+0x27fe,b'\0');self.write(SCREEN+0x2739c8,U32(7))
        self.write(SCREEN+0x1d9bc,U32(1));self.write(DESCS+0x14,U32(1));self.write(STORAGE+0x584,U32(8))
        self.write(ENGINE+0x190c,U32(1))
        for i in range(8):
            self.write(WIDGETS+i*0x1ee18+0x2098,U64(1))
            self.write(WIDGETS+i*0x1ee18+0x1ee0e,b'\x01')
        self.write(WIDGETS+0x1edfc,U32(0xffffffff))
        self.original_targets={GAME+a for a in (0x1470d90,0x146d9b0,0x146e0a0,0x1470700,0x146b190)}

    def step(self,uc,address,size,user):
        g.need(address not in self.original_targets,'Control used an original relocated callee')
        if address==MODE+self.mode_image.mode:self.mode_calls.append(self.value('rdx'))
        if address==CONTROL+self.control_art['mapping'][0x146d866] and not self.control_unwound:
            xmm=self.value('xmm6');values=[self.value(n) for n in NAMES]+[xmm&((1<<64)-1),xmm>>64]
            registers=(c.c_uint64*10)(*values);stack=(c.c_ubyte*0x400).from_buffer_copy(self.read(SP-0x300,0x400))
            result=self.dll.control_unwind(c.byref(self.control_image),address-CONTROL,self.value('rsp')-SP,registers,stack,STOP)
            g.need(result==0,f'Control unwind failed: {result}');self.control_unwound=True
        rcx,rdx,r8=self.value('rcx'),self.value('rdx'),self.value('r8')
        if address in (GAME+0x18a0fd0,GAME+0x60b3b0):self.controls.append((address-GAME,rcx,rdx))
        if address==GAME+0x189bdc0:self.input_calls.append(rcx)
        # The cancel handler emits a separate native event before mode-return.
        if address==GAME+0xbde430 and rcx==0x1d24bc8a:
            g.need(r8==0,'Cancel event payload changed');Flow.step(self,uc,address,size,user);return
        super().step(uc,address,size,user)
        if address==GAME+0xfd9ba0:uc.reg_write(R('rax'),rcx)
        elif address==GAME+0x17aa950:uc.reg_write(R('rax'),int(self.choose))
        elif address==GAME+0x585b80:uc.reg_write(R('rax'),1 if rcx==0x900000000 else 0)

    def operation(self,offset):
        self.uc.reg_write(R('xmm9'),0x66660009+(0xaaaa0009<<64));self.uc.reg_write(R('r8'),0)
        try:self.invoke(CONTROL-CODE+offset,INPUT)
        except Exception as error:
            address=self.value('rip');source=max(((v,k) for k,v in self.control_art['mapping'].items() if v<=address-CONTROL),default=(0,0))[1]
            regs={n:hex(self.value(n)) for n in ('rip','rax','rbx','rcx','rdx','rsi','rdi','r8','r9','r11','rsp')}
            raise AssertionError(f'Control source {source:X}, registers={regs}: {error}') from error


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_control_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        command += [g.PROJECT/'mod/src'/n for n in ('ep_session_code.cpp','ep_loadout_lifecycle.cpp','ep_loadout_consumers.cpp','ep_loadout_setup.cpp','ep_loadout_group.cpp','ep_loadout_interactions.cpp','ep_loadout_refresh.cpp','ep_loadout_records.cpp','ep_loadout_frame.cpp','ep_loadout_mode.cpp','ep_loadout_control.cpp')]
        command += [g.PROJECT/'tests'/n for n in ('loadout_consumers_dll.cpp','loadout_setup_dll.cpp','loadout_mode_dll.cpp','loadout_control_dll.cpp','loadout_interactions_dll.cpp')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage)]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.mode_build.argtypes=[c.POINTER(Binding),c.POINTER(ModeImage)]
    dll.control_build.argtypes=[c.POINTER(ControlAddresses),c.POINTER(Image)]
    dll.interaction_build.argtypes=[c.POINTER(InteractionAddresses),c.POINTER(InteractionImage)]
    dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.control_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer))==0,'Consumer binding failed')
    binding.lifecycle.code=MODE;mode_image=ModeImage();g.need(dll.mode_build(c.byref(binding),c.byref(mode_image))==0,'Mode binding failed')
    binding.lifecycle.code=INTERACTIONS;interaction_binding=InteractionAddresses(binding,REFRESH);interaction_image=InteractionImage()
    g.need(dll.interaction_build(c.byref(interaction_binding),c.byref(interaction_image))==0,'Interaction binding failed')
    binding.lifecycle.code=CONTROL;a=ControlAddresses(binding,MODE+mode_image.mode,INTERACTIONS+interaction_image.input,INTERACTIONS+interaction_image.edit)
    image=Image();g.need(dll.control_build(c.byref(a),c.byref(image))==0,'Control binding failed')
    f=ControlFlow(dll,consumer,mode_image,mode.build(),image,g.build(),interaction_image,interaction.build())
    f.operation(image.screen_input)
    g.need((0x60b3b0,ROSTER,0x1007) in f.controls,'Input peer scan did not resolve dense player seven')
    f.choose=True;f.write(SCREEN+0x27fe,b'\x01');f.operation(image.screen_input)
    g.need(f.read(SCREEN+8,4)==U32(1),'Native selector did not open mode')
    g.need([x[2] for x in f.observed if x[0]==0x139c970]==f.order,'Selector lost expanded notification identity')
    f.choose=False;f.write(INPUT+0x348,b'\x01');f.operation(image.screen_input)
    g.need(f.read(SCREEN+8,4)==U32(0) and f.control_unwound,'Cancel did not return through the cold unwind branch')
    g.need(f.input_calls==[WIDGETS+7*0x1ee18],'Screen input did not delegate to owned slot-seven navigation')
    g.need(f.read(WIDGETS+0x1ee14,4)==U32(0xbf800000),'Cancel reset the wrong selection timer')
    f.write(SCREEN+0x27398c,U32(1));f.write(SCREEN+0x27f9,b'\x01');f.operation(image.leave)
    g.need(f.mode_calls==[1,0,0] and f.read(STORAGE+0x584,4)==U32(10),'Leave failed to route mode or update local flags')
    f.write(SCREEN+0x27398c,U32(6));f.operation(image.leave)
    g.need([x[1] for x in f.controls if x[0]==0x18a0fd0]==[WIDGETS+i*0x1ee18+0x1fa8 for i in range(8)],'Leave omitted extra widget cleanup')
    for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
        g.need(f.read(SCREEN+begin,end-begin)==f.inline[begin:end],'Control touched old inline storage/maps')
    g.need(f.read(WIDGETS+8*0x1ee18,16)==b'\x7c'*16,'Control crossed widget capacity')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=SETUP
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,INTERACTIONS,REFRESH,record_source(),CODE+0x70000,CODE+0x80000,MODE,CONTROL)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one screen selection/cancel/leave flow and common preparation',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
