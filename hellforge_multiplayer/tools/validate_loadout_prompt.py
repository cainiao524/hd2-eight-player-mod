"""One main-frame -> selected-player prompt -> alternate prompt flow.

Uses owned emulator memory, native-service ABI stubs, one prompt unwind
snapshot and one common READY/discard. No game access or full regression.
"""
from validate_loadout_consumers import READY,BLOCKED
from validate_loadout_setup import countdown_source
from validate_loadout_setup import resource_owner_source
import argparse
import ctypes as c
import json
import subprocess
from pathlib import Path
import generate_loadout_prompt as g
import generate_loadout_frame as frame
import generate_loadout_records as records
import generate_loadout_mode as mode
import generate_loadout_state as state
from validate_loadout_frame import (FrameFlow,FrameAddresses,Image as FrameImage,FRAME,
    RecordsAddresses,RecordsImage,ConsumerImage,Binding,Addresses,record_source,SetupAddresses,
    Placement,GroupAddresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,ENGINE,MAPS,ROSTER,STORAGE,
    PEER,SYNC,SETUP,SP,STOP,NAMES,R,U32,U64)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

PROMPT=CODE+0xc0000
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','update','selection','active','ready_flag','blocked_flag')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class PromptFlow(FrameFlow):
    def __init__(self,dll,consumer,record_image,frame_image,image,artifact):
        super().__init__(dll,consumer,record_image,records.build(),frame_image,frame.build())
        self.frame_unwound=True;self.prompt_unwound=False;self.prompt_image=image;self.prompt_art=artifact
        self.prompt_entries=[];self.peer_checks=[];self.buttons=[];self.labels=[];self.bindings=[]
        self.external.difference_update((PROMPT,READY,BLOCKED));self.map(PROMPT,image.bytes);self.write(PROMPT,bytes(image.data[:image.bytes]))
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
        self.write(GAME+0x3326468,U64(ROSTER));self.write(STORAGE+0x584,U32(8))
        self.write(ROSTER+0x3ac,U32(0)) # old local flags deliberately disagree
        table=ROSTER+0x20000;self.map(table,128);self.write(table,b'\xff'*128)
        self.write(ROSTER+0xd0,U64(table)+U32(16)+U32(0xffffffff)+U32(1))
        for dense in range(8):self.write(table+dense*8,U32(0x1000+dense)+U32(dense))

    def step(self,uc,address,size,user):
        g.need(address not in (GAME+0x146b400,GAME+0x146b5a0,GAME+0x146b710),'Prompt used an original relocated callee')
        if address in [PROMPT+x for x in self.prompt_art['entries'][:3]]:self.prompt_entries.append(address)
        if address==PROMPT+self.prompt_art['mapping'][0x146b552] and not self.prompt_unwound:
            registers=(c.c_uint64*8)(*(self.value(n) for n in NAMES))
            stack=(c.c_ubyte*0x400).from_buffer_copy(self.read(SP-0x300,0x400))
            result=self.dll.prompt_unwind(c.byref(self.prompt_image),address-PROMPT,self.value('rsp')-SP,registers,stack,STOP)
            g.need(result==0,f'Prompt unwind failed: {result}');self.prompt_unwound=True
        rcx,rdx,r8=self.value('rcx'),self.value('rdx'),self.value('r8')
        if address==PROMPT+self.prompt_image.ready_flag:self.peer_checks.append((rcx,rdx))
        if rcx==SCREEN+0x1d9e0:
            if address==GAME+0x17ad840:self.buttons.append((rdx,r8&255))
            if address==GAME+0x17add20:self.labels.append((rdx,r8))
            if address==GAME+0x17ae090:self.bindings.append(r8)
        super().step(uc,address,size,user)

    def operation(self,base,offset):
        try:self.invoke(base-CODE+offset)
        except Exception as error:
            regs={n:hex(self.value(n)) for n in ('rip','rax','rcx','rdx','rsi','rdi','r8','r11','rsp')}
            raise AssertionError(f'Prompt flow registers={regs}: {error}') from error


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_prompt_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        modules=('ep_session_code','ep_loadout_lifecycle','ep_loadout_consumers','ep_loadout_setup','ep_loadout_group',
                 'ep_loadout_interactions','ep_loadout_refresh','ep_loadout_records','ep_loadout_frame',
                 'ep_loadout_mode','ep_loadout_control','ep_loadout_state','ep_loadout_prompt','ep_loadout_countdown')
        command += [g.PROJECT/'mod/src'/(n+'.cpp') for n in modules]
        command += [g.PROJECT/'tests'/n for n in ('loadout_consumers_dll.cpp','loadout_setup_dll.cpp','loadout_records_dll.cpp','loadout_frame_dll.cpp','loadout_prompt_dll.cpp')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.prompt_build.argtypes=[c.POINTER(Binding),c.POINTER(Image)]
    dll.records_build.argtypes=[c.POINTER(RecordsAddresses),c.POINTER(RecordsImage)]
    dll.frame_build.argtypes=[c.POINTER(FrameAddresses),c.POINTER(FrameImage)]
    dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.prompt_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer binding failed')
    binding.lifecycle.code=SYNC;rb=RecordsAddresses(binding,record_source());record_image=RecordsImage()
    g.need(dll.records_build(c.byref(rb),c.byref(record_image))==0,'Record binding failed')
    binding.lifecycle.code=PROMPT;image=Image();g.need(dll.prompt_build(c.byref(binding),c.byref(image))==0,'Prompt binding failed')
    fb=FrameAddresses(rb,SYNC,CODE+consumer.update,CODE+consumer.lookup,CODE+0x90000+mode.build()['entries'][1],
                     CODE+0xa0000,CODE+0xb0000+state.build()['entries'][1],CODE+0xb0000,PROMPT+image.update,READY,BLOCKED,CODE+0xd0000)
    fb.records.common.lifecycle.code=FRAME;frame_image=FrameImage()
    g.need(dll.frame_build(c.byref(fb),c.byref(frame_image))==0,'Frame binding failed')
    f=PromptFlow(dll,consumer,record_image,frame_image,image,g.build());f.operation(FRAME,frame_image.frame)
    g.need(f.prompt_entries==[PROMPT+image.update,PROMPT+image.active],'Main frame did not dispatch to the owned active panel')
    g.need((4,0x6d2030e8) in f.labels and 0x300000003 in f.bindings,'Active prompt used old local-ready flags')
    f.write(SCREEN+8,U32(0));f.write(SCREEN+0x280a,b'\x01');f.write(SCREEN+0x27fe,b'\0')
    f.write(SCREEN+0x280d,b'\x01');f.write(SCREEN+0x2800,U64(PEER+7))
    f.peer_checks.clear();f.labels.clear();f.buttons.clear();f.operation(PROMPT,image.update)
    g.need(f.peer_checks==[(ROSTER,0x1007)] and f.prompt_unwound,'Dispatcher lost the selected eighth peer')
    g.need(f.labels==[(0,0x6deb05dc)] and f.buttons==[(5,1),(4,0),(2,0),(0,1)],'Native selected-player prompt changed')
    f.operation(PROMPT,image.selection)
    g.need(f.peer_checks==[(ROSTER,0x1007)]*2 and f.labels==[(0,0x6deb05dc)]*2,'Alternate panel lost selected-player identity')
    for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
        g.need(f.read(SCREEN+begin,end-begin)==f.inline[begin:end],'Prompt touched old player arrays/maps')
    g.need(f.read(WIDGETS+8*0x1ee18,16)==b'\x7c'*16 and f.read(RECORDS+8*0x9f0,16)==b'\x6b'*16,'Prompt crossed player capacity')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=SETUP
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),SYNC,FRAME,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,PROMPT,CODE+0xd0000,countdown_source(),CODE+0xe0000,CODE+0xf0000,resource_owner_source(),CODE+0x110000,CODE+0x120000,CODE+0x130000,CODE+0x140000,CODE+0x150000)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one frame/selected-player/alternate prompt flow and common preparation',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
