"""One mixed-ownership pending-settlement -> promote -> demote flow.

Native registration, ownership swaps and hash updates run in owned memory.
Only hash insertion and native scratch services are explicit ABI stubs.
One nested promotion unwind snapshot and common prepare/discard, no old suite.
"""
import argparse
import ctypes as c
import json
import struct
import subprocess
from pathlib import Path
import generate_loadout_resource_ownership as g
import generate_loadout_resource_owner as owner
from validate_loadout_resource_owner import (OwnerFlow,OwnerAddresses,Image as OwnerImage,
    ConsumerImage,Binding,Addresses,RecordsAddresses,record_source,countdown_source,SOURCE,
    OWNER,OWNER_CODE,TABLE,SetupAddresses,Placement,GroupAddresses,GAME,CODE,SCREEN,RECORDS,WIDGETS,
    REJECT,ENGINE,MAPS,ROSTER,STORAGE,SP,STOP,NAMES,R,U32,U64,READY)
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

OWNERSHIP_CODE=CODE+0x130000
SCRATCH=OWNER+0x62000;SCRATCH_CONTEXT=OWNER+0x63000
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count','settle','promote','demote')]+[('data',c.c_ubyte*g.MAX_IMAGE)]


class OwnershipFlow(OwnerFlow):
    def __init__(self,dll,consumer,owner_image,image,artifact):
        super().__init__(dll,consumer,owner_image,owner.build())
        self.ownership_image=image;self.ownership_art=artifact;self.promotion_unwound=False
        self.sizes=[];self.releases=0;self.scratch_size=0;self.promotions=[];self.demotions=[]
        self.map(OWNERSHIP_CODE,image.bytes);self.write(OWNERSHIP_CODE,bytes(image.data[:image.bytes]))
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
        self.write(GAME+0x3326428,U64(OWNER))
        for ident in range(8):self.write(self.object(ident)+0x14,U32(int(ident<2 or ident>=6)))

    def step(self,uc,address,size,user):
        g.need(address not in [GAME+b for b,e in g.GROUPS]+[GAME+0x66bc20],'Ownership path used an original relocated entry')
        rcx,rdx,r8=(self.value(n) for n in ('rcx','rdx','r8'))
        if address==OWNERSHIP_CODE+self.ownership_image.promote:
            self.promotion_sp=self.value('rsp');self.promotion_registers=self.snapshot()
            self.promotion_return=struct.unpack('<Q',self.read(self.promotion_sp,8))[0]
            self.promotions.append(struct.unpack('<I',self.read(rdx+8,4))[0])
        if address==OWNERSHIP_CODE+self.ownership_image.demote:self.demotions.append(struct.unpack('<I',self.read(rdx+8,4))[0])
        if address==OWNERSHIP_CODE+self.ownership_art['mapping'][0x66c43d] and not self.promotion_unwound:
            stack=(c.c_ubyte*0x200).from_buffer_copy(self.read(self.promotion_sp-0x100,0x200))
            status=self.dll.resource_ownership_unwind(c.byref(self.ownership_image),address-OWNERSHIP_CODE,self.value('rsp')-self.promotion_sp,
                self.snapshot(),self.promotion_registers,stack,self.promotion_return)
            g.need(status==0,f'Nested ownership unwind failed: {status}');self.promotion_unwound=True
        super().step(uc,address,size,user)
        if address==GAME+0x173b6f0:
            g.need(not self.scratch_size,'Scratch initialized while a prior allocation remained live')
            self.write(rcx,U64(SCRATCH_CONTEXT))
        elif address==GAME+0x173b8d0:
            g.need(rcx==SCRATCH_CONTEXT and rdx in (4,12,20) and r8==4 and not self.scratch_size,'Native scratch allocation ABI changed')
            self.scratch_size=rdx;self.sizes.append(rdx);self.write(SCRATCH,b'\xcc'*64);uc.reg_write(R('rax'),SCRATCH)
        elif address==GAME+0x173bc20:
            if self.scratch_size:
                g.need(self.read(SCRATCH+self.scratch_size,16)==b'\xcc'*16,'Native field swap overran scratch storage')
                self.scratch_size=0
            self.write(rcx,U64(0));self.releases+=1

    def call_ownership(self,entry,ident=0):
        self.standalone_lookup=False;self.stop=None;self.uc.reg_write(R('rsp'),SP);self.write(SP,U64(STOP))
        for i,n in enumerate(NAMES):self.uc.reg_write(R(n),0x11110000+i*0x101)
        for i in range(6,9):self.uc.reg_write(R(f'xmm{i}'),(0x66660000+i)|((0xaaaa0000+i)<<64))
        self.uc.reg_write(R('rcx'),OWNER);self.uc.reg_write(R('rdx'),self.object(ident))
        try:self.uc.emu_start(OWNERSHIP_CODE+entry,0,count=50000)
        except Exception as error:
            rip=self.value('rip');source=max(((v,a) for a,v in self.ownership_art['mapping'].items() if OWNERSHIP_CODE+v<=rip),default=(0,0))[1]
            raise RuntimeError(f'Ownership emulator stop rip={rip:#x}, source={source:#x}, '+repr({n:hex(self.value(n)) for n in ('rax','rbx','rcx','rdx','rsi','rdi','rbp','r8','r9','r10','r11','r12','r14','r15')})) from error
        g.need(self.stop==STOP and self.value('rsp')==SP+8,'Ownership callback did not return normally')
        for i,n in enumerate(NAMES):g.need(self.value(n)==0x11110000+i*0x101,'Ownership callback corrupted nonvolatile register')
        for i in range(6,9):g.need(self.value(f'xmm{i}')==(0x66660000+i)|((0xaaaa0000+i)<<64),'Ownership callback corrupted XMM state')

    def expect_ownership(self,ids,owned,phases):
        g.need(struct.unpack('<4I',self.read(OWNER,16))==(6,8,8,owned),'Ownership/publication counts changed')
        for index,ident in enumerate(ids):
            g.need(self.read(SOURCE.objects+index*8,8)==U64(self.object(ident)),'Pending or swapped object identity was lost')
            g.need(self.read(TABLE+ident*8,8)==U32(0x9100+ident)+U32(index),'Ownership change left a stale hash ordinal')
            g.need(self.read(SOURCE.rows+index*20,20)==self.payloads[ident][1] and self.read(SOURCE.states+index*4,4)==self.payloads[ident][2],'Ownership change mixed resource/replicated state')
            g.need(self.read(SOURCE.phases+index*12,12)==phases[index],'Owned phase reset or demotion phase swap changed')
            g.need((struct.unpack('<I',self.read(self.object(ident)+0x14,4))[0]&1)==int(index<owned),'Caller ownership flags disagree with the resulting prefix')
        g.need(self.read(OWNER+0x68,0xb0)==b'\xa7'*0xb0,'Ownership callback touched original four-slot banks')
        for base,stride in ((SOURCE.objects,8),(SOURCE.phases,12),(SOURCE.rows,20),(SOURCE.states,4)):
            g.need(self.read(base+8*stride,16)==b'\x7d'*16,'Ownership bank boundary crossed')


def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_resource_ownership_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        modules=('session_code','loadout_lifecycle','loadout_consumers','loadout_setup','loadout_group','loadout_interactions','loadout_refresh',
                 'loadout_records','loadout_frame','loadout_mode','loadout_control','loadout_state','loadout_prompt','loadout_countdown','loadout_resources','loadout_resource_owner','loadout_resource_tick','loadout_resource_events','loadout_resource_ownership')
        command += [g.PROJECT/'mod/src'/('ep_'+n+'.cpp') for n in modules]
        command += [g.PROJECT/'tests'/('loadout_'+n+'_dll.cpp') for n in ('consumers','setup','resource_owner','resource_ownership')]
        command += ['-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()));dll.ui_build.argtypes=[c.POINTER(Binding),c.POINTER(ConsumerImage),c.c_uint64]
    dll.ui_maps.argtypes=[c.POINTER(c.c_uint32)];dll.setup_group.argtypes=[c.POINTER(GroupAddresses)]
    dll.resource_owner_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(OwnerImage)]
    dll.resource_ownership_build.argtypes=[c.POINTER(OwnerAddresses),c.POINTER(Image)]
    dll.resource_ownership_unwind.argtypes=[c.POINTER(Image),c.c_uint32,c.c_int32,c.POINTER(c.c_uint64),c.POINTER(c.c_uint64),c.POINTER(c.c_ubyte),c.c_uint64]
    binding=Binding(Addresses(GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    consumer=ConsumerImage();g.need(dll.ui_build(c.byref(binding),c.byref(consumer),READY)==0,'Consumer fixture binding failed')
    a=OwnerAddresses(RecordsAddresses(binding,record_source()),countdown_source(),SOURCE);a.records.common.lifecycle.code=OWNER_CODE
    owner_image=OwnerImage();g.need(dll.resource_owner_build(c.byref(a),c.byref(owner_image))==0,'Owner fixture binding failed')
    a.records.common.lifecycle.code=OWNERSHIP_CODE;image=Image();g.need(dll.resource_ownership_build(c.byref(a),c.byref(image))==0,'Ownership binding failed')
    f=OwnershipFlow(dll,consumer,owner_image,image,g.build())
    for ident in range(6):f.call_owner(owner_image.insert,ident,active=ident<2);f.mark_record(ident)
    for ident in (6,7):f.call_owner(owner_image.enqueue,ident);f.mark_record(ident)
    # Distinct imported payloads are opaque here; this flow measures native
    # ownership movement, not state production or a physical pod lifecycle.
    g.need(struct.unpack('<4I',f.read(OWNER,16))==(6,8,6,2),'Queued registration fixture did not establish a mixed prefix')
    phases=[f.payloads[i][0] for i in range(8)]
    f.call_ownership(image.settle);phases[2]=phases[3]=bytes(12)
    f.expect_ownership([0,1,6,7,4,5,2,3],4,phases)
    f.write(f.object(3)+0x14,U32(1));f.call_ownership(image.promote,3);phases[4]=bytes(12)
    f.expect_ownership([0,1,6,7,3,5,2,4],5,phases)
    f.write(f.object(1)+0x14,U32(0));f.call_ownership(image.demote,1);phases[1],phases[4]=phases[4],phases[1]
    f.expect_ownership([0,3,6,7,1,5,2,4],4,phases)
    g.need(f.promotions==[0x9106,0x9107,0x9103] and f.demotions==[0x9101],'Pending settlement did not share the owned promotion entry')
    g.need(f.promotion_unwound and f.sizes==[20,4]*3+[12,20,4] and f.releases==18 and not f.scratch_size,'Native scratch swap/unwind sequence changed')
    setup=SetupAddresses();setup.common=binding;setup.common.lifecycle.code=CODE+0x30000
    for i in range(8):setup.placements[i]=Placement(i*3,111,0.5,0,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),CODE+0x70000,CODE+0x80000,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,CODE+0xd0000,countdown_source(),CODE+0xe0000,OWNER_CODE,SOURCE,CODE+0x110000,CODE+0x120000,OWNERSHIP_CODE)
    status=dll.setup_group(c.byref(group));g.need(status==0,f'Common READY/discard failed: {status}')
    print(json.dumps(dict(passed=True,scope='one mixed-ownership pending-settlement/promote/demote flow',game_access=False,runtime_verified=False)))


if __name__=='__main__':main()
