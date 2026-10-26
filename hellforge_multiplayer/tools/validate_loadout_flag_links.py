"""One frame -> list -> selected-player input flow with actual flag queries.

Owned emulator memory only. Unrelated engine services remain ABI stubs.
No game access, regression matrix, receipt or fingerprint generation.
"""
from validate_loadout_setup import countdown_source
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_consumers as consumers
import generate_loadout_control as control
from validate_loadout_prompt import (PromptFlow,Image,PROMPT,g,frame,records,mode,state,
    FrameAddresses,FrameImage,FRAME,RecordsAddresses,RecordsImage,ConsumerImage,Binding,
    Addresses,record_source,SetupAddresses,Placement,GroupAddresses,GAME,CODE,SCREEN,
    RECORDS,WIDGETS,REJECT,ENGINE,MAPS,ROSTER,STORAGE,PEER,SYNC,SETUP,SP,STOP,R,U32,U64,
    READY,BLOCKED,X86_OP_IMM,X86_OP_MEM,X86_REG_RIP)
from validate_loadout_control import ControlAddresses,Image as ControlImage,CONTROL,INPUT


class FlagFlow(PromptFlow):
    def __init__(self,dll,consumer,record_image,frame_image,prompt_image,control_image):
        super().__init__(dll,consumer,record_image,frame_image,prompt_image,g.build())
        self.queries=[];self.returns={};self.results=[];self.stage='frame'
        self.prompt_unwound=True # This change adds no native frames or stack saves.
        self.map(CONTROL,control_image.bytes);self.write(CONTROL,bytes(control_image.data[:control_image.bytes]))
        capture=g.Capture();seen=set()
        for art in (consumers.build(),frame.build(),g.build()):
            for source in art['sources']:
                for ins in capture.md.disasm(source['data'],source['start']):
                    if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in ins.operands):
                        seen.add(ins.address+ins.size+ins.disp)
        for source in control.build()['sources']:
            for ins in capture.md.disasm(source['data'],source['start']):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not any(b<=target<e for b,e in control.GROUPS):
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for op in ins.operands:
                    if op.type!=X86_OP_MEM or op.mem.base!=X86_REG_RIP:continue
                    target=ins.address+ins.size+ins.disp
                    if target in seen:continue
                    seen.add(target);self.map(GAME+target,16)
                    if ins.mnemonic!='lea':
                        self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        self.map(INPUT,0x1000);self.map(ENGINE,0x600000)
        self.write(SCREEN+0x2800,U64(PEER+7));self.write(SCREEN+0x273994,b'\x01')
        self.write(SCREEN+0x27fe,b'\0');self.write(SCREEN+8,U32(0))
        # Every original flag row disagrees with B. These are owned fixture bytes.
        for dense in range(8):self.write(ROSTER+0x3ac+dense*32,U32(4))
        self.old_flags=self.read(ROSTER+0x3ac,8*32)

    def step(self,uc,address,size,user):
        g.need(address not in (GAME+0x60b3b0,GAME+0x60b460),'Caller fell back to original flag storage')
        if address in (READY,BLOCKED):
            identity=self.value('rdx')&0xffffffff;ret=struct.unpack('<Q',self.read(self.value('rsp'),8))[0]
            g.need(0x1000<=identity<0x1008,f'Caller lost selected player: id={identity:X}, ret={ret:X}, peer={self.read(SCREEN+0x2800,8).hex()}')
            dense=identity-0x1000;flags=struct.unpack('<I',self.read(STORAGE+0x584+dense*32,4))[0]
            expected=(flags>>(1 if address==READY else 2))&1
            event=(self.stage,ret,address,identity,expected);self.queries.append(event);self.returns[ret]=event
        if address in self.returns:
            event=self.returns.pop(address)
            g.need(self.value('rax')&255==event[4] and self.value('rdx')&0xffffffff==event[3],
                   'Flag result or private EDX calling convention changed')
            self.results.append(event)
        rcx=self.value('rcx');super().step(uc,address,size,user)
        if address==GAME+0xfd9ba0:uc.reg_write(R('rax'),rcx)
        elif address==GAME+0x60b6c0:uc.reg_write(R('rax'),1) # external native phase predicate


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_flag_links_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        modules=('session_code','loadout_lifecycle','loadout_consumers','loadout_setup','loadout_group',
                 'loadout_interactions','loadout_refresh','loadout_records','loadout_frame',
                 'loadout_mode','loadout_control','loadout_state','loadout_prompt','loadout_countdown')
        command += [g.PROJECT/'mod/src'/('ep_'+n+'.cpp') for n in modules]
        command += [g.PROJECT/'tests'/('loadout_'+n+'_dll.cpp') for n in ('consumers','setup','records','frame','prompt','control')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()))
    dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.prompt_build.argtypes=[c.POINTER(Binding),c.POINTER(Image)]
    dll.records_build.argtypes=[c.POINTER(RecordsAddresses),c.POINTER(RecordsImage)]
    dll.frame_build.argtypes=[c.POINTER(FrameAddresses),c.POINTER(FrameImage)]
    dll.control_build.argtypes=[c.POINTER(ControlAddresses),c.POINTER(ControlImage)]
    dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    binding=Binding(Addresses(GAME,PROMPT,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    image=Image();g.need(dll.prompt_build(c.byref(binding),c.byref(image))==0,'Prompt binding failed')
    binding.lifecycle.code=CODE;consumer=ConsumerImage()
    g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer binding failed')
    binding.lifecycle.code=SYNC;rb=RecordsAddresses(binding,record_source());record_image=RecordsImage()
    g.need(dll.records_build(c.byref(rb),c.byref(record_image))==0,'Record binding failed')
    fb=FrameAddresses(rb,SYNC,CODE+consumer.update,CODE+consumer.lookup,CODE+0x90000+mode.build()['entries'][1],
                     CONTROL,CODE+0xb0000+state.build()['entries'][1],CODE+0xb0000,PROMPT+image.update,READY,BLOCKED,CODE+0xd0000)
    fb.records.common.lifecycle.code=FRAME;frame_image=FrameImage()
    g.need(dll.frame_build(c.byref(fb),c.byref(frame_image))==0,'Frame binding failed')
    binding.lifecycle.code=CONTROL;cb=ControlAddresses(binding,CODE+0x90000,CODE+0x50000,CODE+0x50010,CODE+0xb0000,READY,BLOCKED)
    control_image=ControlImage();g.need(dll.control_build(c.byref(cb),c.byref(control_image))==0,'Input binding failed')
    f=FlagFlow(dll,consumer,record_image,frame_image,image,control_image)
    f.operation(FRAME,frame_image.frame)
    frame_calls=[x for x in f.queries if FRAME<=x[1]<FRAME+frame_image.code_bytes]
    g.need([(x[2],x[3]) for x in frame_calls]==[(BLOCKED,0x1007),(READY,0x1007)],f'Frame missed selected queries: {f.queries}, flag={f.read(SCREEN+0x273994,1).hex()}, mode={f.read(SCREEN+8,4).hex()}')
    g.need(f.read(SCREEN+0x273994,1)==b'\0','Frame did not apply the shared ready result')
    ui_ids={x[3] for x in f.queries if CODE<=x[1]<CODE+consumer.code_bytes}
    g.need(0x1007 in ui_ids and len(ui_ids)>4,'List update did not use expanded ready queries')
    f.stage='input';f.write(SCREEN+0x2800,U64(PEER+7));f.write(SCREEN+8,U32(0));f.write(STORAGE+0x584+7*32,U32(0))
    for offset in (0x27f8,0x27f9,0x27fa,0x27fe):f.write(SCREEN+offset,b'\0')
    f.write(SCREEN+0x1d9bc,U32(1));f.write(ENGINE+0x190c,U32(1))
    f.uc.reg_write(R('r8'),0);f.invoke(CONTROL-CODE+control_image.screen_input,INPUT)
    selected=[(x[2],x[3],x[4]) for x in f.queries if x[0]=='input']
    g.need(selected==[(READY,0x1007,0),(BLOCKED,0x1007,0)],'Input did not follow the same eighth-player flag row')
    g.need(len(f.queries)==len(f.results),'Flag query did not return')
    g.need(f.read(ROSTER+0x3ac,8*32)==f.old_flags,'Flag readers wrote obsolete storage')
    for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
        g.need(f.read(SCREEN+begin,end-begin)==f.inline[begin:end],'Flow touched old player arrays/maps')
    g.need(f.read(WIDGETS+8*0x1ee18,16)==b'\x7c'*16 and f.read(RECORDS+8*0x9f0,16)==b'\x6b'*16,'Flow crossed player capacity')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=SETUP
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),SYNC,FRAME,CODE+0x90000,CONTROL,CODE+0xb0000,PROMPT,CODE+0xd0000,countdown_source())
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one frame/list/selected-input shared-flag flow and common preparation',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
