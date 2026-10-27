"""One resource writer -> last free allocation -> local transform flow.

Only owned memory; external object/event services are explicit ABI stubs.
One writer unwind snapshot and common preparation/discard, no old suite runs.
"""
from validate_loadout_setup import resource_owner_source
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_resources as g
import generate_loadout_countdown as countdown
from validate_loadout_countdown import (CountdownFlow,CountdownAddresses,Image as CountdownImage,
    FrameAddresses,FrameImage,FRAME,RecordsAddresses,RecordsImage,ConsumerImage,Binding,Addresses,
    record_source,SetupAddresses,Placement,GroupAddresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,
    ENGINE,MAPS,ROSTER,STORAGE,PEER,SYNC,SETUP,SP,STOP,NAMES,R,U32,U64,READY,BLOCKED,
    COUNTDOWN,SOURCE,MANAGER,RESOURCES,state,mode)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

RESOURCE_CODE=CODE+0xe0000
class ResourcesAddresses(c.Structure):
    _fields_=[('records',RecordsAddresses),('source',type(SOURCE)),('resource_lookup',c.c_uint64)]
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','write','ordinal','transform','player_value','assign')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class ResourcesFlow(CountdownFlow):
    def __init__(self,dll,consumer,record_image,frame_image,countdown_image,image,artifact):
        super().__init__(dll,consumer,record_image,frame_image,countdown_image,countdown.build())
        self.resource_image=image;self.resource_art=artifact;self.writer_unwound=False;self.resource_entries=[]
        self.map(RESOURCE_CODE,image.bytes);self.write(RESOURCE_CODE,bytes(image.data[:image.bytes]))
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
                    if ins.mnemonic=='lea' or target in (0x3326468,0x33265f0,0x3326d78):continue
                    self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        self.property_id=GAME+0x3002000;self.property_data=GAME+0x3002010
        for target in (self.property_id,self.property_data):
            self.external.add(target);self.map(target,1);self.write(target,b'\xc3')
        self.write(GAME+0x3326308,U64(ENGINE));self.write(ENGINE+0x18,U64(ENGINE+0x71000))
        self.write(ENGINE+0x716d8,U64(self.property_id));self.write(ENGINE+0x71090,U64(self.property_data))
        self.write(ROSTER+0xd0,U64(MANAGER+0x56000)+U32(16)+U32(0xffffffff)+U32(1))
        self.write(MANAGER+0x56000,b'\xff'*128)
        self.transforms=[]
        for slot in range(8):
            self.write(MANAGER+0x56000+slot*8,U32(0x1000+slot)+U32(slot))
            self.write(STORAGE+0x58c+slot*32,U32(slot))
            self.write(MANAGER+0x53000+slot*32+12,U32(0x3000+slot))
            transform=bytes((slot*29+i)%256 for i in range(64));self.transforms.append(transform)
            self.write(MANAGER+0x54000+slot*64,transform)
        self.write(RESOURCES,b'\xa9'*(8*0x4c))

    def step(self,uc,address,size,user):
        g.need(address not in [GAME+b for b,e in g.GROUPS],'Resource path used an original moved callee')
        rcx,rdx=self.value('rcx'),self.value('rdx')
        entries=[RESOURCE_CODE+x for x in self.resource_art['entries']]
        if address in entries:self.resource_entries.append(entries.index(address))
        if address==entries[0]:
            self.writer_sp=self.value('rsp');self.writer_registers=self.saved_registers()
        if address==RESOURCE_CODE+self.resource_art['mapping'][0x65de70] and not self.writer_unwound:
            stack=(c.c_ubyte*0x200).from_buffer_copy(self.read(self.writer_sp-0x100,0x200))
            status=self.dll.resources_unwind(c.byref(self.resource_image),address-RESOURCE_CODE,self.value('rsp')-self.writer_sp,
                self.saved_registers(),self.writer_registers,stack,STOP)
            g.need(status==0,f'Resource writer unwind failed: {status}');self.writer_unwound=True
        super().step(uc,address,size,user)
        if address==self.property_id:
            g.need(rdx==0xe4a4586d and 0x3000<=rcx<0x3008,'Writer property identity changed')
            uc.reg_write(R('rax'),7)
        elif address==self.property_data:
            g.need(rdx==7 and 0x3000<=rcx<0x3008,'Writer property data identity changed')
            uc.reg_write(R('rax'),MANAGER+0x54000+(rcx-0x3000)*64)

    def call_resource(self,offset,rcx=MANAGER,rdx=0,r8=0,r9=0):
        self.standalone_lookup=False;self.stop=None;self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP))
        for i,n in enumerate(NAMES):self.uc.reg_write(R(n),0x11110000+i*0x101)
        for i in range(6,9):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        for n,v in (('rcx',rcx),('rdx',rdx),('r8',r8),('r9',r9)):self.uc.reg_write(R(n),v)
        try:self.uc.emu_start(RESOURCE_CODE+offset,0,count=30000)
        except Exception as error:
            rip=self.value('rip');source=max(((v,a) for a,v in self.resource_art['mapping'].items() if RESOURCE_CODE+v<=rip),default=(0,0))[1]
            raise RuntimeError(f'Resource emulator stop rip={rip:#x}, source={source:#x}, '+repr({n:hex(self.value(n)) for n in ('rax','rbx','rcx','rdx','rsi','rdi','rbp','r8','r9','r10','r11')})) from error
        g.need(self.stop==STOP and self.value('rsp')==SP+8,'Resource flow did not return normally')
        for i,n in enumerate(NAMES):g.need(self.value(n)==0x11110000+i*0x101,'Resource flow corrupted a nonvolatile register')
        for i in range(6,9):g.need(self.value(f'xmm{i}')==(0x66660000+i)|((0xaaaa0000+i)<<64),'Resource flow corrupted XMM state')


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_resources_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        modules=('session_code','loadout_lifecycle','loadout_consumers','loadout_setup','loadout_group',
                 'loadout_interactions','loadout_refresh','loadout_records','loadout_frame','loadout_mode',
                 'loadout_control','loadout_state','loadout_prompt','loadout_countdown','loadout_resources','loadout_resource_owner','loadout_resource_tick','loadout_resource_events','loadout_resource_ownership','loadout_resource_sync','loadout_resource_signals','loadout_resource_actions','loadout_resource_main')
        command += [g.PROJECT/'mod/src'/('ep_'+n+'.cpp') for n in modules]
        command += [g.PROJECT/'tests'/('loadout_'+n+'_dll.cpp') for n in ('consumers','setup','records','frame','countdown','resources')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.countdown_build.argtypes=[c.POINTER(CountdownAddresses),c.POINTER(CountdownImage)]
    dll.records_build.argtypes=[c.POINTER(RecordsAddresses),c.POINTER(RecordsImage)]
    dll.frame_build.argtypes=[c.POINTER(FrameAddresses),c.POINTER(FrameImage)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.resources_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    dll.resources_build.argtypes=[c.POINTER(ResourcesAddresses),c.POINTER(Image)]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer binding failed')
    binding.lifecycle.code=SYNC;rb=RecordsAddresses(binding,record_source());record_image=RecordsImage()
    g.need(dll.records_build(c.byref(rb),c.byref(record_image))==0,'Record binding failed')
    a=CountdownAddresses(rb,SOURCE,CODE+0xb0000+state.build()['entries'][2],CODE+0x40000)
    a.records.common.lifecycle.code=COUNTDOWN;countdown_image=CountdownImage()
    g.need(dll.countdown_build(c.byref(a),c.byref(countdown_image))==0,'Countdown binding failed')
    fb=FrameAddresses(rb,SYNC,CODE+consumer.update,CODE+consumer.lookup,CODE+0x90000+mode.build()['entries'][1],
                     CODE+0xa0000,CODE+0xb0000+state.build()['entries'][1],CODE+0xb0000,CODE+0xc0000,READY,BLOCKED,COUNTDOWN)
    fb.records.common.lifecycle.code=FRAME;frame_image=FrameImage()
    g.need(dll.frame_build(c.byref(fb),c.byref(frame_image))==0,'Frame binding failed')
    ra=ResourcesAddresses(rb,SOURCE,COUNTDOWN+countdown_image.resource_lookup);ra.records.common.lifecycle.code=RESOURCE_CODE
    image=Image();g.need(dll.resources_build(c.byref(ra),c.byref(image))==0,'Resource binding failed')
    f=ResourcesFlow(dll,consumer,record_image,frame_image,countdown_image,image,g.build())
    # Capture callback writes the IDs and all four transform vectors for eight slots.
    for slot in range(8):
        f.call_resource(image.write,rdx=0x9000+f.resource_order[slot],r8=MANAGER+0x53000+slot*32,r9=slot)
        g.need(f.read(RESOURCES+slot*0x4c,0x4c)==U32(0x9000+f.resource_order[slot])+f.transforms[slot]+b'\xa9'*8,'Writer lost a resource field or changed reserved bytes')
    # Seven players already occupy the first seven resources. Assign the last
    # free slot to the local player through the native alternate allocator.
    for dense in range(1,8):
        resource=0x9000+f.resource_order[dense-1];f.allocations.append((dense,resource));f.write(f.rows+dense*64,U32(resource))
    f.call_resource(image.assign)
    g.need(f.allocations==[(i,0x9000+f.resource_order[i-1]) for i in range(1,8)]+[(0,0x9000+f.resource_order[7])],'Last free resource assigned to the wrong identity')
    g.need(f.lookups==list(range(0x1000,0x1008)) and f.free_checks==[0x9000+i for i in f.resource_order],'Assignment still used four resources or bypassed shared lookup')
    # Category 5 obtains the local descriptor/value, calls ordinal lookup and
    # returns all 64 bytes from the eighth row through the owned switch table.
    output=MANAGER+0x55000;f.write(output,b'\xcc'*64);f.call_resource(image.transform,rdx=output,r8=5)
    g.need(f.value('rax')==output and f.read(output,64)==f.transforms[7],'Local transform did not read the eighth written resource')
    g.need(f.writer_unwound and set(f.resource_entries)==set(range(5)),'Resource call chain or writer unwind was omitted')
    g.need(f.read(MANAGER+0x11d18,4*0x4c)==b'\xa7'*(4*0x4c) and f.read(RESOURCES+8*0x4c,16)==b'\x7d'*16,'Resource storage boundary changed')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=SETUP
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),SYNC,FRAME,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,COUNTDOWN,SOURCE,CODE+0xe0000,CODE+0xf0000,resource_owner_source(),CODE+0x110000,CODE+0x120000,CODE+0x130000,CODE+0x140000,CODE+0x150000,CODE+0x160000,CODE+0x170000)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one writer/last-free-assignment/local-transform flow',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
