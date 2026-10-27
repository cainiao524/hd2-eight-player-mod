"""One owned-memory setup -> update -> action integration smoke flow.

ABI stubs do not render UI or verify layout. One setup unwind snapshot and
one all-image READY/discard cycle; no full regression or game access.
--attach-only instead runs one construct -> isolated attachment flow.
--replace-only runs construct -> map preflight/migration/native detach/attach.
"""
from validate_loadout_consumers import READY,BLOCKED
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_setup as g
import generate_loadout_lifecycle as lifecycle
from validate_loadout_lifecycle import Image as LifeImage,STATE_STUB
import generate_loadout_consumers as consumers
from validate_loadout_consumers import (Binding,Image as ConsumerImage,Flow,MAPS,ROSTER,STORAGE,PEER,
    Addresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,ENGINE,SP,NAMES,R,U64,U32,STOP)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

SETUP=CODE+0x30000
class Placement(c.Structure):
    _fields_=[(n,c.c_float) for n in ('offset_x','offset_y','anchor_x','anchor_y','pivot_x','pivot_y')]
class SetupAddresses(c.Structure):
    _fields_=[('common',Binding),('placements',Placement*8)]
class SetupImage(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','handler_offset','placements_offset','attach_widgets','replace_widgets')]+[('data',c.c_ubyte*g.MAX_IMAGE)]
class RecordSource(c.Structure):
    _fields_=[(n,c.c_uint64) for n in ('manager','actors','equipment','status')]

def record_source():return RecordSource(ENGINE,ENGINE+0x60000,ENGINE+0x61000,ENGINE+0x62000)

class CountdownSource(c.Structure):
    _fields_=[('manager',c.c_uint64),('resources',c.c_uint64)]

def countdown_source():return CountdownSource(0x2b0000000,0x2b0020000)

class ResourceOwnerSource(c.Structure):
    _fields_=[(n,c.c_uint64) for n in ('owner','objects','phases','rows','states')]
def resource_owner_source():return ResourceOwnerSource(0x2c0000000,0x2c0010000,0x2c0020000,0x2c0030000,0x2c0040000)

class GroupAddresses(c.Structure):
    _fields_=[('setup',SetupAddresses),('lifecycle_code',c.c_uint64),('consumers_code',c.c_uint64),('interactions_code',c.c_uint64),('refresh_code',c.c_uint64),('record_source',RecordSource),('records_code',c.c_uint64),('frame_code',c.c_uint64),('mode_code',c.c_uint64),('control_code',c.c_uint64),('state_code',c.c_uint64),('prompt_code',c.c_uint64),('countdown_code',c.c_uint64),('countdown_source',CountdownSource),('resources_code',c.c_uint64),('resource_owner_code',c.c_uint64),('resource_owner_source',ResourceOwnerSource),('resource_tick_code',c.c_uint64),('resource_events_code',c.c_uint64),('resource_ownership_code',c.c_uint64),('resource_sync_code',c.c_uint64),('resource_signals_code',c.c_uint64),('resource_actions_code',c.c_uint64),('resource_main_code',c.c_uint64),('resource_update_code',c.c_uint64)]


class SetupFlow(Flow):
    def __init__(self,artifact,dll,image,setup_artifact,setup_image):
        super().__init__(artifact,dll,image)
        self.points=set();self.setup_image=setup_image;self.setup_point=SETUP+setup_artifact['mapping'][0x1466af0]
        self.setup_unwound=False;self.setup_calls=[];self.attachments=[];self.constructed=[];self.cookie=0x6745ab23901f
        self.detachments=[];self.replacing=False
        capture=g.Capture()
        for ins in capture.md.disasm(setup_artifact['source'],g.START):
            if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                target=ins.operands[0].imm
                if not g.START<=target<g.END:
                    self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
            for op in ins.operands:
                if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                    target=ins.address+ins.size+ins.disp;self.map(GAME+target,max(16,op.size))
                    if target==0x263c010:data=U64(self.cookie)
                    elif target<0x3000000:data=capture.read(target,op.size)
                    else:data=U64(ENGINE) if op.size==8 else bytes(op.size)
                    self.write(GAME+target,data)
        self.map(SETUP,setup_image.bytes);self.write(SETUP,bytes(setup_image.data[:setup_image.bytes]))
        self.write(SCREEN,U64(ENGINE+0x70000))
        self.write(ENGINE+0x162c8,U64(ENGINE+0x60000));self.write(ENGINE+0x6b398,U64(PEER))
        self.map(ENGINE+0x55f000,0x1000)
        # Native menu-control capacity 16, independent of the player loop.
        self.write(SCREEN+0x1d9e0+0x36028,b'\xff'*64)
        # Force native setup to replace stale map contents, including slots 4..7.
        self.write(MAPS,b'\xa5'*64)

    def step(self,uc,address,size,user):
        if address==GAME+0x14aa5c0:self.constructed.append(self.value('rcx'))
        if address==GAME+0x144c5c0 and self.value('rcx')==SCREEN+0x2820 and WIDGETS<=self.value('rdx')<WIDGETS+8*0x1ee18:
            if self.replacing:g.need(len(self.detachments)==4,'Attached before all old roots were removed')
            self.attachments.append(self.value('rdx'))
        if self.replacing:
            g.need(address not in (GAME+0x144dd70,GAME+0x1446a90),'Replacement destroyed old resource ownership')
            if address==GAME+0x144c9f0:self.detachments.append((self.value('rcx'),self.value('rdx'),self.value('r8')))
        if address==self.setup_point and not self.setup_unwound:
            xmm=self.value('xmm6');values=(c.c_uint64*10)(*(self.value(n) for n in NAMES),xmm&((1<<64)-1),xmm>>64)
            stack=(c.c_ubyte*1024).from_buffer_copy(self.read(SP-512,1024))
            g.need(self.dll.setup_unwind(c.byref(self.setup_image),address-SETUP,self.value('rsp')-SP,values,stack,STOP)==0,'Setup unwind/cookie metadata mismatch')
            self.setup_unwound=True
        if address in self.external:
            rcx,rdx=self.value('rcx'),self.value('rdx')
            if address==GAME+0x2088770:g.need(rcx==self.cookie,'Native setup cookie check changed')
            if WIDGETS<=rcx<WIDGETS+8*0x1ee18 and (rcx-WIDGETS)%0x1ee18==0 and address-GAME in (0x189ae00,0x14476a0,0x144f160,0x144f0d0):
                self.setup_calls.append((address-GAME,(rcx-WIDGETS)//0x1ee18,rdx))
        super().step(uc,address,size,user)

    def setup(self,address=SETUP,expected=STOP):
        self.standalone_lookup=False;self.stop=None
        self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP))
        for i,n in enumerate(NAMES):self.uc.reg_write(R(n),0x11110000+i*0x101)
        for i in range(6,9):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        self.uc.reg_write(R('rcx'),SCREEN);self.uc.emu_start(address,0,count=100000)
        g.need(self.stop==expected and self.value('rsp')==SP+(8 if expected==STOP else 0),'Setup did not reach expected return/rejection')
        for i,n in enumerate(NAMES):g.need(self.value(n)==0x11110000+i*0x101,'Setup corrupted nonvolatile register')


def construct_and_attach(f,dll,setup_artifact,replace=False):
    # Use the actual isolated bank constructor and saved per-widget body in
    # this SAME emulator and buffers, followed by isolated setup. Resource
    # services remain ABI stubs; replacement below loads native hierarchy code.
    dll.loadout_build.argtypes=[c.POINTER(Addresses),c.c_uint64,c.POINTER(LifeImage)]
    code=CODE+0x40000;binding=Addresses(GAME,code,SCREEN,RECORDS,WIDGETS,REJECT,8,0)
    image=LifeImage();g.need(dll.loadout_build(c.byref(binding),STATE_STUB,c.byref(image))==0,'Constructor image rejected')
    f.map(code,image.bytes);f.write(code,bytes(image.data[:image.bytes]))
    capture=g.Capture();widget=capture.read(0x14aa5c0,0x26f)
    f.map(GAME+0x14aa5c0,len(widget));f.write(GAME+0x14aa5c0,widget)
    source=lifecycle.build()['sources'][0]
    for base,data in ((source['start'],source['data']),(0x14aa5c0,widget)):
        for ins in capture.md.disasm(data,base):
            if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                target=ins.operands[0].imm
                if not (base<=target<base+len(data) or 0x14aa5c0<=target<0x14aa82f):
                    f.external.add(GAME+target);f.map(GAME+target,1);f.write(GAME+target,b'\xc3')
            for operand in ins.operands:
                if operand.type==X86_OP_MEM and operand.mem.base==X86_REG_RIP:
                    target=ins.address+ins.size+ins.disp;f.map(GAME+target,max(16,operand.size))
                    value=U64(f.cookie) if target==0x263c010 else capture.read(target,operand.size) if target<0x3000000 else U64(ENGINE) if operand.size==8 else U32(0xffffffff)
                    f.write(GAME+target,value)
    # A ready parent with an existing child chain, but no old widgets still
    # attached. Identity maps are caller-owned state and must not be reset.
    maps=(c.c_uint32*16)();g.need(dll.ui_maps(maps)==1,'Map seed rejected');f.write(MAPS,bytes(maps))
    parent=SCREEN+0x2820;child=ENGINE+0x50000
    f.write(parent,U32(0x12340002));f.write(parent+0xe0,U64(child))
    f.write(child,U32(0x10000000));f.write(child+0xe8,U64(child+0x100))
    f.write(child+0x100,U32(0x80000000))
    if replace:
        # Execute saved native single-child removal, insertion and recursive
        # flag/dirty propagation; only rendering/resource services stay stubbed.
        for start,end in ((0x144c9f0,0x144cb9d),(0x144c5c0,0x144c739),
                          (0x144c2c0,0x144c317),(0x144d200,0x144d22d),
                          (0x144e760,0x144e7b8),(0x144cf40,0x144cf96),
                          (0x144e920,0x144e9a4)):
            f.map(GAME+start,end-start);f.write(GAME+start,capture.read(start,end-start))
            f.external.discard(GAME+start)
        old=[SCREEN+0x53a78+i*0x1ee18 for i in range(4)]
        other=[SCREEN+x for x in (0x40000,0x80000,0xe0000)]
        chain=sorted(old+other)
        f.write(parent+0xe0,U64(chain[0]));f.write(parent+0xf0,U64(0))
        f.write(parent,U32(0x12344002))
        for i,node in enumerate(chain):
            f.write(node,bytes(0x110))
            f.write(node,U32(0x1000 if node in old else 0x80000000))
            f.write(node+0xe8,U64(chain[i+1] if i+1<len(chain) else 0));f.write(node+0xf0,U64(parent))
        for i,node in enumerate(old):
            descendant=child+i*0x100;f.write(descendant,bytes(0x100));f.write(descendant,U32(0x1000))
            f.write(node+0xe0,U64(descendant));f.write(descendant+0xf0,U64(node))
        # The local player is network 2 in slot zero; network 1 has no UI slot,
        # but its inactive opaque record must still survive value migration.
        forward=[1,0xffffffff,0,2];inverse=[2,0,3,0xffffffff]
        f.write(SCREEN+0x27d0,U32(0xffffffff)+U32(2))
        f.write(SCREEN+0x27d8,struct.pack('<8I',*(forward+inverse)))
        for network in range(4):
            f.write(SCREEN+0x10+network*0x9f0,bytes([0x30+network])*0x9f0)
            f.write(SCREEN+0x10+network*0x9f0+0x9e8,U64(PEER+network))
    f.write(SCREEN+0x2739a4,b'\x53'*16)
    f.write(RECORDS,bytes(8*0x9f0));f.write(WIDGETS,bytes(8*0x1ee18))
    screen_before=f.read(SCREEN,0x2739d0);maps_before=f.read(MAPS,64)
    if replace:f.inline=screen_before
    f.setup(code+image.construct_banks)
    g.need(f.constructed==[WIDGETS+i*0x1ee18 for i in range(8)] and f.value('rax')==SCREEN,'Native construction sequence changed')
    g.need(f.read(SCREEN,len(screen_before))==screen_before,'Construction changed the existing screen')
    g.need(not f.attachments,'Construction attached widgets before setup')
    f.setup_calls.clear()
    records_before=f.read(RECORDS,8*0x9f0)
    f.setup_point=SETUP+(setup_artifact['replace_point'] if replace else setup_artifact['attach_mapping'][0x1466af0])
    f.replacing=replace
    if replace:
        # A mismatched reverse mapping must fail before migration or detach.
        f.write(SCREEN+0x27ec,U32(3))
        invalid_screen=f.read(SCREEN,0x2739d0);unattached=f.read(WIDGETS,8*0x1ee18)
        f.setup(SETUP+f.setup_image.replace_widgets,REJECT)
        g.need(f.read(SCREEN,0x2739d0)==invalid_screen and f.read(MAPS,64)==maps_before and
               f.read(RECORDS,len(records_before))==records_before and f.read(WIDGETS,len(unattached))==unattached and
               not f.detachments and not f.attachments,'Invalid maps caused partial migration')
        f.write(SCREEN+0x27ec,U32(0))
    f.setup(SETUP+(f.setup_image.replace_widgets if replace else f.setup_image.attach_widgets))
    # Expected screen changes are limited to the native hierarchy fields;
    # inline record values, maps and unrelated controls must remain intact.
    expected=bytearray(screen_before);struct.pack_into('<I',expected,0x2820,0x12344006 if replace else 0x12344002)
    if replace:
        g.need(f.detachments==[(parent,node,0) for node in old],'Wrong removal roots/cleanup mode')
        for node in old:
            struct.pack_into('<I',expected,node-SCREEN,0)
            struct.pack_into('<QQ',expected,node-SCREEN+0xe8,0,0)
        final=other+[WIDGETS+i*0x1ee18 for i in range(8)]
        for i,node in enumerate(other):struct.pack_into('<Q',expected,node-SCREEN+0xe8,final[i+1])
        for i,node in enumerate(final):
            g.need(f.read(node+0xe8,16)==U64(final[i+1] if i+1<len(final) else 0)+U64(parent),'Native child/sibling/parent links diverged')
        for i,node in enumerate(old):
            g.need(f.read(child+i*0x100,4)==U32(0) and f.read(child+i*0x100+0xf0,8)==U64(node),'Detached subtree was lost or left active')
    g.need(f.read(SCREEN,len(expected))==bytes(expected),'Attachment reset unrelated screen state')
    if replace:
        expected_maps=struct.pack('<16I',*(forward+[0xffffffff]*4+inverse+[0xffffffff]*4))
        expected_records=screen_before[0x10:0x27d0]+records_before[4*0x9f0:]
        g.need(f.read(MAPS,64)==expected_maps,'Migration lost local identity, reverse mapping, holes or new-slot sentinels')
        g.need(f.read(RECORDS,len(expected_records))==expected_records,'Migration reordered old records or overwrote initialized new rows')
    else:g.need(f.read(MAPS,64)==maps_before and f.read(RECORDS,len(records_before))==records_before,'Attachment changed identity maps or records')
    g.need(all(f.read(WIDGETS+i*0x1ee18+0x1ee12,1)==b'\1' for i in range(8)),'Native per-widget setup flags missing')
    g.need(f.read(RECORDS+8*0x9f0,16)==b'\x6b'*16 and f.read(WIDGETS+8*0x1ee18,16)==b'\x7c'*16,'Construct/attach exceeded owned banks')
    if replace:
        before=(f.read(SCREEN,0x2739d0),f.read(WIDGETS,8*0x1ee18),f.read(RECORDS,8*0x9f0),f.read(MAPS,64),len(f.detachments),len(f.attachments))
        f.setup(SETUP+f.setup_image.replace_widgets,REJECT)
        g.need(before==(f.read(SCREEN,0x2739d0),f.read(WIDGETS,8*0x1ee18),f.read(RECORDS,8*0x9f0),f.read(MAPS,64),len(f.detachments),len(f.attachments)),'Repeated switch mutated data or hierarchy')


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--attach-only',action='store_true',help='Only the construct/isolated attachment flow')
    mode.add_argument('--replace-only',action='store_true',help='Only construct/migration/native hierarchy replacement and preflight rejection')
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_setup_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        command += [g.PROJECT/'mod/src'/n for n in ('ep_session_code.cpp','ep_loadout_lifecycle.cpp','ep_loadout_consumers.cpp','ep_loadout_setup.cpp','ep_loadout_group.cpp','ep_loadout_interactions.cpp','ep_loadout_refresh.cpp','ep_loadout_records.cpp','ep_loadout_frame.cpp','ep_loadout_mode.cpp','ep_loadout_control.cpp','ep_loadout_state.cpp','ep_loadout_prompt.cpp','ep_loadout_countdown.cpp','ep_loadout_resources.cpp','ep_loadout_resource_owner.cpp','ep_loadout_resource_tick.cpp','ep_loadout_resource_events.cpp','ep_loadout_resource_ownership.cpp','ep_loadout_resource_sync.cpp','ep_loadout_resource_signals.cpp','ep_loadout_resource_actions.cpp','ep_loadout_resource_main.cpp','ep_loadout_resource_update.cpp')]
        command += [g.PROJECT/'tests/loadout_consumers_dll.cpp',g.PROJECT/'tests/loadout_setup_dll.cpp',g.PROJECT/'tests/loadout_lifecycle_dll.cpp','-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()))
    dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64];dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)]
    dll.setup_build.argtypes=[c.POINTER(SetupAddresses),c.POINTER(SetupImage)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.setup_unwind.argtypes=[c.POINTER(SetupImage),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    setup=SetupAddresses();setup.common=Binding.from_buffer_copy(binding);setup.common.lifecycle.code=SETUP
    # Synthetic distinct coordinates exercise the ABI, not screen fit.
    for i in range(8):setup.placements[i]=Placement(i*3,111+i*5,0.138+(i%4)*0.241,0.5*(i//4),0.5,0)
    image=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(image),READY)==0,'Consumer image rejected')
    si=SetupImage();g.need(dll.setup_build(c.byref(setup),c.byref(si))==0,'Setup image rejected')
    artifact=g.build();f=SetupFlow(consumers.build(),dll,image,artifact,si)
    if args.attach_only or args.replace_only:construct_and_attach(f,dll,artifact,args.replace_only)
    else:f.setup()
    expected=[]
    for i,placement in enumerate(setup.placements):
        pairs=struct.unpack('<3Q',bytes(placement));expected.extend([(0x189ae00,i,10)]+[(target,i,value) for target,value in zip((0x14476a0,0x144f160,0x144f0d0),pairs)])
    g.need(f.setup_calls==expected and f.attachments==[WIDGETS+i*0x1ee18 for i in range(8)],'Setup omitted/repositioned the wrong native widget')
    if not (args.attach_only or args.replace_only):
        forward=list(struct.unpack('<8I',f.read(MAPS,32)));inverse=list(struct.unpack('<8I',f.read(MAPS+32,32)))
        g.need(forward==[0xffffffff]*3+[0]+[0xffffffff]*4 and inverse==[3]+[0xffffffff]*7,'Native setup did not reset/bind all map slots')
        f.invoke(image.update);f.invoke(image.action,PEER+7,0x35)
        g.need(list(struct.unpack('<8I',f.read(MAPS+32,32)))==f.order and f.calls[-1]==(0x1893d40,WIDGETS+7*0x1ee18+0xe670,0x35),'Setup/update/action storage diverged')
    for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
        if args.replace_only and begin==0x53a78:continue # exact old-root changes checked above
        g.need(f.read(SCREEN+begin,end-begin)==f.inline[begin:end],'Setup or consumer touched old arrays/maps')
    g.need(f.setup_unwound,'Setup unwind point was missed')
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),CODE+0x70000,CODE+0x80000,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,CODE+0xd0000,countdown_source(),CODE+0xe0000,CODE+0xf0000,resource_owner_source(),CODE+0x110000,CODE+0x120000,CODE+0x130000,CODE+0x140000,CODE+0x150000,CODE+0x160000,CODE+0x170000,CODE+0x180000)
    g.need(dll.setup_group(c.byref(group))==0,'Shared READY/discard failed')
    scope='one construct/map preflight/migration/native hierarchy replacement flow' if args.replace_only else 'one construct/isolated attachment flow' if args.attach_only else 'one setup/update/action flow and shared READY group'
    print(json.dumps(dict(passed=True,scope=scope,game_access=False,layout_verified=False,runtime_verified=False)))


if __name__=='__main__':main()
