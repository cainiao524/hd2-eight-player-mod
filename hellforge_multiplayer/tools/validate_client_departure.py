"""One post-creation join-readiness/send/ack/departure flow on saved code.

The original join continuation really calls the bound helpers. Creation,
transport, registry and entity services are explicit fixtures, not game tests.
No previous admission or full client regression is run.
"""
import argparse
import ctypes as C
import struct
import subprocess
from collections import deque
from pathlib import Path
from generate_loadout_lifecycle import Capture,PROJECT,need
from generate_client_departure import START,END
from generate_client_metadata import SOURCES
from validate_client_metadata import Addresses as MetadataAddresses,Image as MetadataImage
from validate_client_disconnect import Addresses as ClientAddresses
from unicorn import Uc,UcError,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn import x86_const as x
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_REG_RIP


class Addresses(C.Structure):
    _fields_=[('client',ClientAddresses)]+[(n,C.c_uint64) for n in ('ready','ids','history','metadata','slots','ready_finish')]


class Image(C.Structure):
    _fields_=[(n,C.c_uint32) for n in ('bytes','table_offset','function_count','body_offset')]+[('data',C.c_uint8*4096)]


class JoinPeers(C.Structure):
    _fields_=[('client',C.c_uint64),('bank',C.c_uint64),('capacity',C.c_uint32),('reserved',C.c_uint32)]


class JoinReadiness(C.Structure):
    _fields_=[(n,C.c_uint64) for n in ('client','bank','lookup','finish')]+[('capacity',C.c_uint32),('reserved',C.c_uint32)]


class JoinImage(C.Structure):
    _fields_=[(n,C.c_uint32) for n in ('bytes','table_offset','function_count','handler_offset','creation_target_offset')]+[('data',C.c_uint8*4096)]


def flow(dll):
    c=ClientAddresses(0x140000000,0x1800e0000,0x2100162c8,0x220000000,0x1c0000000,8,0)
    m=MetadataAddresses(c.game,0x1800d0000,c.client,0x220060000,0x220070000,c.reject,8,0);metadata=MetadataImage()
    emit=dll.departure_metadata_emit;emit.argtypes=[C.POINTER(MetadataAddresses),C.POINTER(MetadataImage)];emit.restype=C.c_int
    need(emit(C.byref(m),C.byref(metadata))==0,'Metadata helper emission')
    a=Addresses(c,m.ready,0x220050000,0x220080000,m.metadata,0x220090000,m.code+metadata.entry[3]);image=Image()
    emit=dll.departure_emit;emit.argtypes=[C.POINTER(Addresses),C.POINTER(Image)];emit.restype=C.c_int
    need(emit(C.byref(a),C.byref(image))==0,'Full departure emission')
    jp=JoinPeers(c.client,c.peers,8,0);jr=JoinReadiness(c.client,a.ready,m.code+metadata.entry[2],a.ready_finish,8,0)
    join=JoinImage();join_code=0x1800f0000;control=0x250000000;next_slot=control+8
    emit=dll.departure_join_emit;emit.argtypes=[C.c_uint64]*5+[C.POINTER(JoinPeers),C.POINTER(JoinReadiness),C.POINTER(JoinImage)];emit.restype=C.c_int
    need(emit(c.game,join_code,control,next_slot,c.reject,C.byref(jp),C.byref(jr),C.byref(join))==0,'Join readiness emission')
    u=Uc(UC_ARCH_X86,UC_MODE_64);pages=set();owner=c.client-0x162c8;stack=0x230000000;sp=stack+0x6008;stop=0x240000000
    callbacks={stop+0x100:'member',stop+0x110:'available',stop+0x120:'finished'}
    def mapped(address,size):
        page=address&~4095;end=(address+size+4095)&~4095
        while page<end:
            if page in pages:page+=4096;continue
            first=page
            while page<end and page not in pages:page+=4096
            u.mem_map(first,page-first);pages.update(range(first,page,4096))
    def putq(at,value):u.mem_write(at,struct.pack('<Q',value))
    def putd(at,value):u.mem_write(at,struct.pack('<I',value))
    def qword(at):return struct.unpack('<Q',u.mem_read(at,8))[0]
    def dword(at):return struct.unpack('<I',u.mem_read(at,4))[0]
    for address,size in ((owner,0x30000),(stack,0x10000),(stop,0x2000),(control,4096),(c.reject,4096)):
        mapped(address,size)
    for address,data in ((c.code,image.data),(m.code,metadata.data),(join_code,join.data)):
        mapped(address,4096);u.mem_write(address,bytes(data))
    banks=((c.peers,256),(a.ready,128),(a.ids,64),(a.history,128),(a.metadata,128),(a.slots,192))
    for bank,size in banks:mapped(bank,4096);u.mem_write(bank+size,b'\xfa'*16)
    putq(c.client,owner);members=list(range(0x500,0x508));host=members[1]
    putq(owner+0xb398,members[0]);putq(owner+0xb3a8,host);putd(c.client+0x1d0,3);u.mem_write(c.client+0x51d,b'\1')
    for offset in (0x10,0x80,0xc8):putd(c.client+offset,8)
    for offset,size in ((0x18,32),(0x40,64),(0x88,64),(0xd0,192)):u.mem_write(c.client+offset,b'\xa6'*size)
    confirmed=[struct.pack('<QQIIBB6s',p,0xa000+i,100+i,i,0,1,bytes((i,))*6) for i,p in enumerate(members)]
    history=[struct.pack('<QQ',p,0xabc000+i) for i,p in enumerate(members)]
    slots=[struct.pack('<QQQ',p,0xbbb000+i,0xccc000+i) for i,p in enumerate(members)]
    for bank,rows in ((c.peers,confirmed),(a.history,history),(a.slots,slots)):u.mem_write(bank,b''.join(rows))
    u.mem_write(a.ids,struct.pack('<8Q',*members))
    initial_metadata=b''.join(struct.pack('<QII',p,89,59) for p in members);u.mem_write(a.metadata,initial_metadata)
    capture=Capture();ins=[];globals_={};by_pc={}
    for start,end in ((START,END),*SOURCES[1:],(0x10863c0,0x108645c),(0x1085d8a,0x1085d91)):
        ins+=list(capture.md.disasm(capture.read(start,end-start),start))
    for i in ins:
        if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
            target=c.game+i.address+i.size+i.disp;mapped(target,64)
            if i.mnemonic=='mov':
                if target not in globals_:globals_[target]=0x280000000+len(globals_)*0x400000
                pointer=globals_[target];mapped(pointer,0x200000);putq(target,pointer);by_pc[i.address]=pointer
    api=by_pc[0x10863c0];table=stop+0x1000;putq(api+0x40,table);putq(table+0x58,stop+0x100);putq(table+0x68,stop+0x110)
    putq(by_pc[0x1086c3c]+0x10,table);putq(table+0x470,stop+0x120)
    for address in callbacks:u.mem_write(address,b'\xc3')
    putq(by_pc[0x10877bd]+0x18,0x8899);putd(owner+0x1f838,63)
    services={i.operands[0].imm for i in ins if i.mnemonic=='call' and i.operands[0].type==X86_OP_IMM}
    for rva in services:mapped(c.game+rva,128);u.mem_write(c.game+rva,b'\xc3')
    u.mem_write(c.game+0xbf23b0,capture.read(0xbf23b0,0xbf240e-0xbf23b0))
    recent=deque(maxlen=12);rpc=[];released=[];removed=[];events=[];lookups=[];finishes=[]
    def returned(value=0):
        rsp=u.reg_read(x.UC_X86_REG_RSP);u.reg_write(x.UC_X86_REG_RIP,qword(rsp));u.reg_write(x.UC_X86_REG_RSP,rsp+8);u.reg_write(x.UC_X86_REG_RAX,value)
    def hook(cpu,address,size,data):
        recent.append(hex(address));need(address!=c.reject,'Departure rejection '+str(list(recent)))
        rcx=cpu.reg_read(x.UC_X86_REG_RCX);rdx=cpu.reg_read(x.UC_X86_REG_RDX);r8=cpu.reg_read(x.UC_X86_REG_R8);r9=cpu.reg_read(x.UC_X86_REG_R9)
        if address==jr.lookup:lookups.append(rdx)
        if address==jr.finish:finishes.append(True)
        if address in callbacks:
            kind=callbacks[address]
            if kind=='member':need(rdx<8,'Join continuation member bound');returned(members[rdx])
            elif kind=='available':returned(1)
            else:events.append(True);returned()
            return
        rva=address-c.game;need(rva not in (0x1086920,0x1086b70),'Original inline readiness helper called')
        if rva not in services or rva==0xbf23b0:return
        if rva==0xbde430:
            fields=[]
            for i in range(r9):
                kind,width,pointer=struct.unpack('<IIQ',u.mem_read(r8+i*16,16));need(kind in (0,1) and width==4,'Readiness payload')
                fields.append((kind,width,u.mem_read(pointer,1)[0] if kind==0 else dword(pointer)))
            rpc.append((rcx,rdx,fields))
        elif rva==0xb5f140:released.append(rcx)
        elif rva==0xb51de0:removed.append((rcx,rdx))
        elif rva==0x2088770:need(rcx==by_pc[0x1085d8a],'Join continuation GS cookie')
        elif rva not in (0x1738300,0x1346e30):raise RuntimeError('Unexpected departure service '+hex(rva))
        returned()
    u.hook_add(UC_HOOK_CODE,hook)
    nonvolatile=((x.UC_X86_REG_RBX,0x33),(x.UC_X86_REG_RBP,0x55),(x.UC_X86_REG_RSI,0x66),(x.UC_X86_REG_RDI,0x77),
                 (x.UC_X86_REG_R12,0xcc),(x.UC_X86_REG_R13,0xdd),(x.UC_X86_REG_R14,0xee),(x.UC_X86_REG_R15,0xff))
    def run(at):
        try:u.emu_start(at,stop,count=40000)
        except UcError as error:raise RuntimeError(f'{error}; recent={list(recent)}') from error
        need(u.reg_read(x.UC_X86_REG_RIP)==stop and u.reg_read(x.UC_X86_REG_RSP)==sp+8,'Departure/join return ABI '+str(list(recent)))
        need(all(u.reg_read(reg)==value for reg,value in nonvolatile),'Nonvolatile restoration')
    def invoke(at,rdx=0,r8=0,r9=0):
        putq(sp,stop);u.reg_write(x.UC_X86_REG_RSP,sp)
        for reg,value in nonvolatile:u.reg_write(reg,value)
        for reg,value in zip((x.UC_X86_REG_RCX,x.UC_X86_REG_RDX,x.UC_X86_REG_R8,x.UC_X86_REG_R9),(c.client,rdx,r8,r9)):u.reg_write(reg,value)
        run(at)
    # Explicit post-creation frame fixture. Only the real final enumeration,
    # readiness calls and epilogue execute; no avatar creation is claimed.
    frame=sp-0x2b18;putq(sp,stop);putq(frame+0x40,host);putq(frame+0x2aa0,by_pc[0x1085d8a]^frame)
    for offset,value in ((0x2b00,0xff),(0x2b08,0x33),(0x2b10,0x55),(0x2b38,0xcc),(0x2af0,0xee),(0x2af8,0xdd),(0x2b30,0x77)):putq(frame+offset,value)
    for reg,value in nonvolatile:u.reg_write(reg,value)
    for reg,value in ((x.UC_X86_REG_RSP,frame),(x.UC_X86_REG_RBP,frame+0x100),(x.UC_X86_REG_R15,c.client),
                      (x.UC_X86_REG_R12,members[0]),(x.UC_X86_REG_R13,0x111),(x.UC_X86_REG_R14,0),(x.UC_X86_REG_RDI,8)):u.reg_write(reg,value)
    run(join_code+32+0x10863c0-0x1085d70)
    need(lookups==members[1:] and len(finishes)==1 and dword(c.client+0x38)==7 and not events,'Join did not use bound readiness helpers')
    for member in members[1:]:invoke(m.code+metadata.entry[1],member)
    need(dword(c.client+0x38)==7 and not events,'Send completed before acknowledgments')
    u.mem_write(a.ready+6*16+10,b'\x77'*6);last_ready=bytes(u.mem_read(a.ready+6*16,16))
    invoke(c.code,host,members[3],17)
    need(all(dword(c.client+offset)==7 for offset in (0x10,0x80,0xc8)) and dword(c.client+0x38)==6,'Interior departure counts')
    need(u.mem_read(c.peers+3*32,32)==confirmed[7] and qword(a.ids+3*8)==members[7] and
         u.mem_read(a.history+3*16,16)==history[7] and u.mem_read(a.ready+2*16,16)==last_ready,'Complete eighth-record swaps')
    need(u.mem_read(a.metadata,128)==initial_metadata,'Changed native conditional metadata cleanup')
    for member in members[1:3]+members[4:7]:invoke(m.code+metadata.entry[4],member)
    need(dword(c.client+0x38)==1 and qword(a.ready)==members[7] and not events,'Final peer did not defer readiness')
    invoke(c.code,host,members[7],23)
    need(dword(c.client+0x38)==0 and dword(c.client+0x1d0)==5 and events==[True],'Departure did not finish outstanding readiness')
    need(all(dword(c.client+offset)==6 for offset in (0x10,0x80,0xc8)),'Eighth member departure counts')
    remaining=[members[i] for i in (0,1,2,6,4,5)]
    for bank,stride in ((c.peers,32),(a.ids,8),(a.history,16)):need([qword(bank+i*stride) for i in range(6)]==remaining,'Diverged remaining-member order')
    need(u.mem_read(a.metadata,128)==initial_metadata[:112]+bytes(16),'Eighth fixed history/metadata slot not cleared')
    need(u.mem_read(a.slots,192)==b''.join(slots[:7])+bytes(8)+slots[7][8:],'Auxiliary slot ID/opaque bytes')
    need(released==[members[3],members[7]] and removed==[(members[3],17),(members[7],23)],'Native departure services')
    need(rpc[-1]==(0x37ff1aa7,host,[(0,4,1)]) and len(rpc)==15,'Final readiness notification')
    need(dword(owner+0x1f838)==1,'64-entry event ring wrap changed')
    for index,member,reason in ((63,members[3],17),(0,members[7],23)):
        at=owner+0x1f038+32*index
        need(dword(at)==3 and [qword(at+off) for off in (8,16,24)]==[member,reason,0x8899],'Native departure event record')
    for offset,size in ((0x18,32),(0x40,64),(0x88,64),(0xd0,192)):need(u.mem_read(c.client+offset,size)==b'\xa6'*size,'Native inline bank touched')
    for bank,size in banks:need(u.mem_read(bank+size,16)==b'\xfa'*16,'Departure bank boundary')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True);args=p.parse_args()
    folder=PROJECT.parent/'work/hellforge-client-departure';folder.mkdir(parents=True,exist_ok=True);out=folder/'client-departure.dll'
    sources=[PROJECT/'mod/src'/name for name in ('ep_client_departure.cpp','ep_client_metadata.cpp','ep_player_join_image.cpp','ep_session_code.cpp')]+[PROJECT/'tests/client_departure_dll.cpp']
    cmd=[args.zig.resolve(),'c++','-std=c++17','-shared','-O0','-g','-I',PROJECT/'mod/src','-I',args.upstream.resolve()/'native/mod-sdk',*sources,'-o',out]
    result=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);need(result.returncode==0,result.stdout+result.stderr)
    dll=C.CDLL(str(out));prepare=dll.departure_prepare_flow;prepare.restype=C.c_int
    need((rc:=prepare())==0,f'Departure preparation/unwind line {rc}');flow(dll)
    print('PASS one post-creation readiness/send/ack/departure flow: actual join continuation binds shared helpers, interior/eighth removal swaps whole member records, native conditional slot cleanup, final readiness completion and 64-entry event ring wrap; Windows unwind. game_access=false, hooks=0; creation/registry/transport/entity services are fixtures; coordinator/reset/runtime/UI/eight clients unverified.')


if __name__=='__main__':main()
