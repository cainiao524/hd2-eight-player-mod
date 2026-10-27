"""One linked eight-object update -> player/resource lookup -> widget close flow.

All objects share the real relocated update. Mixed current phases exercise
normal state changes, the native type switch and missing optional records.
The three saved caller CALL windows use the actual group-sealed bytes and full
owned callees, not the full unrelated screen/controller paths. External services
are ABI stubs. No game access or separate suite.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_resource_update as g
import generate_loadout_resource_owner as owner
import generate_loadout_links as links
from validate_loadout_resource_owner import (OwnerFlow,OwnerAddresses,Image as OwnerImage,
    ConsumerImage,Binding,Addresses,RecordsAddresses,record_source,countdown_source,SOURCE,
    OWNER,OWNER_CODE,SetupAddresses,Placement,GroupAddresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,
    REJECT,ENGINE,MAPS,ROSTER,STORAGE,SP,STOP,NAMES,R,U32,U64,READY)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

UPDATE_CODE=CODE+0x180000
COUNTDOWN=countdown_source();MANAGER=COUNTDOWN.manager;RESOURCES=COUNTDOWN.resources
CATALOG=OWNER+0x62000;CATALOG_HASH=OWNER+0x63000;CATALOG_ROWS=OWNER+0x64000
API_TABLE=ENGINE+0x50000;TRANSFORMS=ENGINE+0x51000
PROPERTY=GAME+0x3002000;TRANSFORM=GAME+0x3002010
ORDINALS=(3,0,6,2,1,7,4,5)
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','update')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class UpdateFlow(OwnerFlow):
    def __init__(self,dll,consumer,owner_image,image,artifact):
        super().__init__(dll,consumer,owner_image,owner.build())
        self.update_image=image;self.update_art=artifact;self.unwound=False
        self.notifications=[];self.transforms=[];self.property_calls=[];self.events=[];self.effects=[];self.switch_visits=0
        self.window_return=None;self.link_targets=set();self.link_visits=[];self.widget_closes=[]
        self.map(MANAGER,0x30000);self.map(UPDATE_CODE,image.bytes);self.write(UPDATE_CODE,bytes(image.data[:image.bytes]))
        capture=g.Capture()
        for source in artifact['sources']:
            for ins in capture.md.disasm(source['data'],source['start']):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not any(b<=target<e for b,e in g.GROUPS):
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for op in ins.operands:
                    if op.type!=X86_OP_MEM or op.mem.base!=X86_REG_RIP:continue
                    if ins.mnemonic=='lea':continue # address formation does not read the pointed-to data
                    target=ins.address+ins.size+ins.disp;self.map(GAME+target,16)
                    if target==0x263c018:
                        self.write(GAME+target,U32(0));continue # fixture CPU dispatch; not a saved process value
                    self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        for target,value in ((0x3326428,OWNER),(0x33265f0,MANAGER),(0x3326d88,CATALOG)):
            self.write(GAME+target,U64(value))
        self.write(ENGINE+0x18,U64(API_TABLE))
        self.write(API_TABLE+0x6d8,U64(PROPERTY));self.write(API_TABLE+0x90,U64(TRANSFORM))
        for target in (PROPERTY,TRANSFORM):
            self.external.add(target);self.map(target,1);self.write(target,b'\xc3')
        for i in range(8):
            self.write(self.object(i)+0x14,U32(1))
            self.write(TRANSFORMS+i*64,struct.pack('<16f',*(i*100+j+0.25 for j in range(16))))
            self.write(RESOURCES+i*0x4c,U32(0xffffffff)+bytes(64)+U64(0xd000+i))
        self.write(MANAGER+0x11d18,b'\xa7'*(4*0x4c));self.write(RESOURCES+8*0x4c,b'\x7d'*16)
        self.write(CATALOG+0x20,U64(CATALOG_HASH)+U32(16)+U32(0xffffffff)+U32(1))
        self.write(CATALOG+0x48,U64(CATALOG_ROWS));self.write(CATALOG_HASH,b'\xff'*128)
        # Catalog ordinal 9 is distinct from resource/player capacity 8.
        self.write(CATALOG_HASH+5*8,U32(0x9105)+U32(9));self.write(CATALOG_ROWS+9*100,U32(1))
        self.threshold=struct.unpack('<f',capture.read(0x23c72e8,4))[0]

    def step(self,uc,address,size,user):
        g.need(address!=GAME+0x66b090,'Update executed the old four-slot entry')
        g.need(address not in (GAME+0x146f3b0,GAME+0x606820,GAME+0x661fa0),'Group called an original four-slot callee')
        if address==self.window_return:self.stop=address;uc.emu_stop();return
        if address in self.link_targets:self.link_visits.append(address)
        rcx,rdx,r8,r9=(self.value(n) for n in ('rcx','rdx','r8','r9'))
        if address==GAME+0x189e2f0:self.widget_closes.append(rcx)
        if address==GAME+0x606630:g.need(r8==0x1007,'Resource lookup lost the selected eighth player')
        if address==UPDATE_CODE+self.update_art['mapping'][0x66b3b4] and not self.unwound:
            stack=(c.c_ubyte*0x200).from_buffer_copy(self.read(SP-0x100,0x200))
            status=self.dll.resource_update_unwind(c.byref(self.update_image),address-UPDATE_CODE,self.value('rsp')-SP,
                self.snapshot(),self.expected_registers,stack,STOP)
            g.need(status==0,f'Resource update unwind failed: {status}');self.unwound=True
        if address==UPDATE_CODE+self.update_art['mapping'][0x66b623]:self.switch_visits+=1
        if address==PROPERTY:
            g.need(0x3000<=rcx<0x3008 and rdx==0xe4a4586d,'Transform property query changed');self.property_calls.append(rcx-0x3000)
        elif address==TRANSFORM:
            g.need(0x3000<=rcx<0x3008 and rdx==0xa100+rcx-0x3000,'Transform service lost its descriptor')
            self.transforms.append(rcx-0x3000)
        elif address==GAME+0xfd97e0:
            ident=rcx-0x800;g.need(0<=ident<8 and rdx==0x82830aed and r8==SOURCE.states+ident*4,'State notification used an old bank or wrong object')
            self.notifications.append((ident,struct.unpack('<I',self.read(r8,4))[0]))
        elif address==GAME+0x635610:g.need(rdx==0x9106 and r8==3,'Blocked-state query changed')
        elif address==GAME+0x808810:
            g.need(r9==0 and self.read(self.value('rsp')+0x28,4)==U32(1),'Native state-event arguments changed')
            self.events.append((rdx,r8))
        elif address==GAME+0x843930:self.effects.append((rdx,r8))
        super().step(uc,address,size,user)
        if address==PROPERTY:uc.reg_write(R('rax'),0xa100+rcx-0x3000)
        elif address==TRANSFORM:uc.reg_write(R('rax'),TRANSFORMS+(rcx-0x3000)*64)
        elif address==GAME+0x606630:self.write(rdx,U32(0xa107))

    def update(self,entry=None):
        self.standalone_lookup=False;self.stop=None;self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP))
        for i,n in enumerate(NAMES):self.uc.reg_write(R(n),0x11110000+i*0x101)
        for i in range(6,9):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        self.expected_registers=self.snapshot()
        self.uc.reg_write(R('rcx'),OWNER);self.uc.reg_write(R('xmm1'),struct.unpack('<I',struct.pack('<f',0.25))[0])
        try:self.uc.emu_start(entry if entry is not None else UPDATE_CODE+self.update_image.update,0,count=30000)
        except Exception as error:
            rip=self.value('rip');source=max(((v,a) for a,v in self.update_art['mapping'].items() if UPDATE_CODE+v<=rip),default=(0,0))[1]
            raise RuntimeError(f'Resource update stop rip={rip:#x}, source={source:#x}') from error
        g.need(self.stop==STOP and self.value('rsp')==SP+8,'Resource update did not return normally')
        g.need(list(self.snapshot())==list(self.expected_registers),'Resource update corrupted nonvolatile state')

    def linked_queries_and_close(self,bases,routes):
        capture=g.Capture()
        for start,end in ((0x146f3b0,0x146f504),(0x606820,0x6068e5),(0x661fa0,0x6620c3)):
            for ins in capture.md.disasm(capture.read(start,end-start),start):
                if (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
                    target=ins.operands[0].imm
                    if not start<=target<end:
                        self.external.add(GAME+target);self.map(GAME+target,1);self.write(GAME+target,b'\xc3')
                for op in ins.operands:
                    if op.type!=X86_OP_MEM or op.mem.base!=X86_REG_RIP or ins.mnemonic=='lea':continue
                    target=ins.address+ins.size+ins.disp;self.map(GAME+target,16)
                    self.write(GAME+target,capture.read(target,op.size) if target<0x3000000 else U64(ENGINE) if op.size==8 else U32(0xffffffff))
        lookup_catalog=OWNER+0x65000;lookup_hash=OWNER+0x66000;lookup_rows=OWNER+0x67000
        for target,value in ((0x3326468,ROSTER),(0x33265f0,MANAGER),(0x3326d78,lookup_catalog)):
            self.write(GAME+target,U64(value))
        # The selected player, catalog ordinal and resource ordinal differ.
        self.write(ROSTER+0xd0,U64(ENGINE+0x60000)+U32(16)+U32(0xffffffff)+U32(1))
        self.write(ENGINE+0x60000,b'\xff'*128);self.write(ENGINE+0x60038,U32(0x1007)+U32(7))
        self.write(STORAGE+0x58c+7*32,U32(7))
        self.write(lookup_catalog+0x20,U64(lookup_hash)+U32(16)+U32(0xffffffff)+U32(1))
        self.write(lookup_catalog+0x48,U64(lookup_rows));self.write(lookup_hash,b'\xff'*128)
        self.write(lookup_hash+7*8,U32(0xa107)+U32(9));self.write(lookup_rows+9*64,U32(0x9105))
        self.write(SCREEN+0x273992,b'\0');self.write(SCREEN+0x260d05,b'\x01')
        bound={row[0]:row for row in links.build()};self.link_targets=set(routes[:3]);self.link_visits=[]
        for source,arguments in ((7,(ROSTER,0x1007,0)),(9,(MANAGER,OWNER+0x68000,0x1007)),(0,(SCREEN,0,0))):
            row=bound[source];_,target,offset,nxt,_,entry=row;site=bases[source]+offset-1
            relative=struct.unpack('<i',self.read(site+1,4))[0]
            g.need(site+5+relative==bases[target]+entry,'Prepared CALL does not reach its group callee')
            self.window_return=bases[source]+nxt;self.stop=None;self.uc.reg_write(R('rsp'),SP+8)
            expected=list(self.snapshot())
            for name,value in zip(('rcx','rdx','r8'),arguments):self.uc.reg_write(R(name),value)
            self.uc.emu_start(site,0,count=30000)
            g.need(self.stop==self.window_return and self.value('rsp')==SP+8,'Linked caller window did not return')
            g.need(list(self.snapshot())==expected,'Linked callee corrupted nonvolatile state')
            if source==7:g.need(self.value('rax')==7 and self.value('rdx')==0x1007,'Player-value private ABI changed')
            if source==9:g.need(self.read(OWNER+0x68000,4)==U32(0x9105),'State lookup missed resource row eight')
        g.need(self.link_visits==[routes[1],routes[2],routes[0]],'Caller windows missed shared entries')
        g.need(self.widget_closes==[WIDGETS+i*0x1ee18 for i in range(8)],'Transition close missed expanded widgets')
        for begin,end in ((0x10,0x27d0),(0x27d8,0x27f8),(0x53a78,0xcf2d8)):
            g.need(self.read(SCREEN+begin,end-begin)==self.inline[begin:end],'Linked close touched old inline player storage')
        g.need(self.read(WIDGETS+8*0x1ee18,16)==b'\x7c'*16,'Linked close crossed player capacity')
        self.window_return=None


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_resource_update_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        modules=('session_code','loadout_lifecycle','loadout_consumers','loadout_setup','loadout_group','loadout_interactions','loadout_refresh',
                 'loadout_records','loadout_frame','loadout_mode','loadout_control','loadout_state','loadout_prompt','loadout_countdown','loadout_resources',
                 'loadout_resource_owner','loadout_resource_tick','loadout_resource_events','loadout_resource_ownership','loadout_resource_sync',
                 'loadout_resource_signals','loadout_resource_actions','loadout_resource_main','loadout_resource_update')
        command += [g.PROJECT/'mod/src'/('ep_'+n+'.cpp') for n in modules]
        command += [g.PROJECT/'tests'/('loadout_'+n+'_dll.cpp') for n in ('consumers','setup','resource_owner','resource_update')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.setup_group_snapshot.argtypes=[c.POINTER(GroupAddresses),c.POINTER(c.c_ubyte),c.c_uint32,c.POINTER(c.c_uint32),c.POINTER(c.c_uint64)]
    dll.resource_owner_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(OwnerImage)]
    dll.resource_update_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(Image)]
    dll.resource_update_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer fixture binding failed')
    a=OwnerAddresses(RecordsAddresses(binding,record_source()),COUNTDOWN,SOURCE);a.records.common.lifecycle.code=OWNER_CODE
    owner_image=OwnerImage();g.need(dll.resource_owner_build(c.byref(a),c.byref(owner_image))==0,'Owner fixture binding failed')
    a.records.common.lifecycle.code=UPDATE_CODE;image=Image();g.need(dll.resource_update_build(c.byref(a),c.byref(image))==0,'Resource update binding failed')
    f=UpdateFlow(dll,consumer,owner_image,image,g.build())
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=CODE+0x30000
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),CODE+0x70000,CODE+0x80000,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,CODE+0xd0000,COUNTDOWN,CODE+0xe0000,OWNER_CODE,SOURCE,CODE+0x110000,CODE+0x120000,CODE+0x130000,CODE+0x140000,CODE+0x150000,CODE+0x160000,CODE+0x170000,UPDATE_CODE)
    data=(c.c_ubyte*(22*16384))();sizes=(c.c_uint32*22)();routes=(c.c_uint64*5)()
    status=dll.setup_group_snapshot(c.byref(group),data,16384,sizes,routes)
    g.need(status==0,f'Linked common READY/snapshot/discard failed: {status}')
    bases=[CODE+x for x in (0x40000,0,0x30000,0x50000,0x60000,0x70000,0x80000,0x90000,0xa0000,0xb0000,0xc0000,0xd0000,0xe0000,0xf0000,0x110000,0x120000,0x130000,0x140000,0x150000,0x160000,0x170000,0x180000)]
    for i,base in enumerate(bases):f.map(base,sizes[i]);f.write(base,bytes(data[i*16384:i*16384+sizes[i]]))
    g.need(routes[3]==routes[4]==UPDATE_CODE+image.update,'Group exposed distinct update bodies')
    expected_states=[]
    for ident,ordinal in enumerate(ORDINALS):
        f.call_owner(owner_image.insert,ident,active=True)
        phase=2 if ident>=5 else 1;state=4 if ident==6 else 1;flag=int(ident==6)
        timer=f.threshold;published_timer=42.0
        phases=U32(phase)+U32(flag)+struct.pack('<f',timer)
        rows=U32(state)+U32(ordinal)+bytes((1,flag,0,0))+struct.pack('<f',published_timer)+U32(0xa000+ident)
        f.write(SOURCE.phases+ident*12,phases);f.write(SOURCE.rows+ident*20,rows);f.write(SOURCE.states+ident*4,U32(state))
        next_state=4 if ident==6 else 3 if ident>=5 else 2;expected_states.append(next_state)
        f.payloads[ident]=(U32(phase)+U32(flag)+struct.pack('<f',timer if ident==6 else timer+0.25),
            U32(next_state)+U32(ordinal)+bytes((1,int(ident>=5),0,0))+struct.pack('<f',42.25 if ident==6 else 0)+U32(0xa000+ident),U32(next_state))
    f.update(CODE+0x110000) # exercise the sealed legacy tail entry, too
    f.expect(list(range(8)),(8,8,8,8))
    g.need(f.transforms==list(range(8)) and f.property_calls==list(range(8)),'Transform publication did not reach every resource object')
    g.need(f.notifications==[(i,state) for i,state in enumerate(expected_states) if i!=6],'State notifications lost object/state identity')
    g.need(f.events==[(0x9100+i,0xfa89b8eb if i>=5 else 0x6b9cab48) for i in range(8) if i!=6],'State event sequence changed')
    g.need(f.effects==[(0x9105,0x16aed43),(0x9107,0x16aed43)] and f.switch_visits==22,'Native type switch or missing-catalog cleanup changed')
    for ident,ordinal in enumerate(ORDINALS):
        expected=U32(0x9100+ident)+f.read(TRANSFORMS+ident*64,64)+U64(0xd000+ordinal)
        g.need(f.read(RESOURCES+ordinal*0x4c,0x4c)==expected,'Transform publication mixed object identity, ordinal or row tail')
    g.need(f.read(MANAGER+0x11d18,4*0x4c)==b'\xa7'*(4*0x4c) and f.read(RESOURCES+8*0x4c,16)==b'\x7d'*16,'Update touched old resource storage or crossed the shared bank')
    g.need(f.unwound,'Owned state unwind point not reached')
    f.linked_queries_and_close(bases,routes)
    print(json.dumps(dict(passed=True,scope='one linked update/query/close flow using saved caller windows',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
