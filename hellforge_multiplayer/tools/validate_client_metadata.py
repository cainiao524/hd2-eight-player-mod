"""One local startup/send/readiness flow; no previous admission regression.

Executes saved constructor, metadata producers/serializer, send, lookup, both
readiness flags and swap removal. Object registry/transport/event service are
fixtures. This does not simulate eight independent game clients or activation.
"""
import argparse
import ctypes as C
import struct
import subprocess
from collections import deque
from pathlib import Path
from generate_loadout_lifecycle import Capture,PROJECT,need
from generate_client_metadata import SOURCES
from generate_host_accept import SOURCES as ACCEPT_SOURCES
from validate_host_accept import AcceptAddresses,AcceptImage
from validate_host_lifecycle import Addresses as HostAddresses
from unicorn import Uc,UcError,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn import x86_const as x
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_REG_RIP


class Addresses(C.Structure):
    _fields_=[(name,C.c_uint64) for name in ('game','code','client','metadata','ready','reject')]+[('capacity',C.c_uint32),('reserved',C.c_uint32)]


class Image(C.Structure):
    _fields_=[('bytes',C.c_uint32),('table_offset',C.c_uint32),('function_count',C.c_uint32),('entry',C.c_uint32*5),('data',C.c_uint8*4096)]


def flow(dll):
    a=Addresses(0x140000000,0x1800d0000,0x2100162c8,0x220060000,0x220070000,0x1c0000000,8,0);image=Image()
    emit=dll.metadata_emit;emit.argtypes=[C.POINTER(Addresses),C.POINTER(Image)];emit.restype=C.c_int
    need(emit(C.byref(a),C.byref(image))==0,'Metadata image')
    h=HostAddresses(a.game,0x1800a0000,a.client,0x220000000,a.reject,0x220010000,0x220020000,0x220030000,0x220040000,8,0)
    receive_a=AcceptAddresses(h,a.metadata,0x1800c0000,0x1800b0000);receive=AcceptImage()
    emit=dll.metadata_receive_emit;emit.argtypes=[C.POINTER(AcceptAddresses),C.POINTER(AcceptImage)];emit.restype=C.c_int
    need(emit(C.byref(receive_a),C.byref(receive))==0,'Shared metadata producer image')
    u=Uc(UC_ARCH_X86,UC_MODE_64);pages=set();owner=a.client-0x162c8;stack=0x230000000;sp=stack+0x4008;stop=0x240000000;callback=stop+0x100
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
    for address,size in ((a.code,4096),(h.code,4096),(owner,0x30000),(a.metadata,4096),(a.ready,4096),(stack,0x8000),(stop,4096),(a.reject,4096)):
        mapped(address,size)
    u.mem_write(a.code,bytes(image.data));u.mem_write(h.code,bytes(receive.data));u.mem_write(a.reject,b'\xcc');u.mem_write(callback,b'\xc3')
    members=list(range(0x500,0x508));putq(owner+0xb398,members[0]);putq(owner+0xb3a8,members[0])
    u.mem_write(a.client+0x40,b'\xa6'*128);u.mem_write(a.client+0xd0,b'\xa6'*192)
    for bank in (a.metadata,a.ready):u.mem_write(bank,b'\xa5'*128);u.mem_write(bank+128,b'\xfa'*16)
    capture=Capture();ins=[];globals_={};by_pc={}
    # Only the old family's metadata receive/local producers are called, never
    # its host acceptance or its unused removal/registered-insert bindings.
    for start,end in (*SOURCES,*ACCEPT_SOURCES[1:]):ins+=list(capture.md.disasm(capture.read(start,end-start),start))
    for i in ins:
        if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
            target=a.game+i.address+i.size+i.disp;mapped(target,64)
            if i.mnemonic=='mov':
                if target not in globals_:globals_[target]=0x280000000+len(globals_)*0x400000
                pointer=globals_[target];mapped(pointer,0x200000);putq(target,pointer);by_pc[i.address]=pointer
    settings=by_pc[0x1084e16];putd(settings+0xddcdc,89);putd(settings+0xddce0,59)
    event_table=stop+0x1000;mapped(event_table,4096);putq(by_pc[0x1086c3c]+0x10,event_table);putq(event_table+0x470,callback)
    internal={start for start,end in SOURCES}
    services={i.operands[0].imm for i in ins if i.mnemonic=='call' and i.operands[0].type==X86_OP_IMM}
    services.add(0xb648c0)
    for rva in services:mapped(a.game+rva,128);u.mem_write(a.game+rva,b'\xcc' if rva in internal else b'\xc3')
    # Execute the unchanged two-field native serializer, not a stub of it.
    serializer=capture.read(0xbf23b0,0xbf240e-0xbf23b0);u.mem_write(a.game+0xbf23b0,serializer)
    rpc=[];registered=[];refreshed=[];events=[];recent=deque(maxlen=10);rejected=[]
    def returned(value=0):
        rsp=u.reg_read(x.UC_X86_REG_RSP);u.reg_write(x.UC_X86_REG_RIP,qword(rsp));u.reg_write(x.UC_X86_REG_RSP,rsp+8);u.reg_write(x.UC_X86_REG_RAX,value)
    def hook(cpu,address,size,data):
        recent.append(hex(address))
        if address==a.reject:rejected.append(True);cpu.emu_stop();return
        if address==callback:events.append(True);returned();return
        rva=address-a.game;need(rva not in internal,'Escaped to original readiness bank')
        if rva not in services or rva==0xbf23b0:return
        rcx=cpu.reg_read(x.UC_X86_REG_RCX);rdx=cpu.reg_read(x.UC_X86_REG_RDX);r8=cpu.reg_read(x.UC_X86_REG_R8);r9=cpu.reg_read(x.UC_X86_REG_R9)
        if rva==0xb2abd0:
            need((rcx,rdx,r8)==(a.client,owner,a.client),'Base registration arguments');registered.append(rcx)
        elif rva==0xbde430:
            fields=[]
            for i in range(r9):
                kind,width,pointer=struct.unpack('<IIQ',u.mem_read(r8+i*16,16))
                need(width==4 and kind in (0,1),'Metadata/readiness field ABI')
                fields.append((kind,width,u.mem_read(pointer,1)[0] if kind==0 else dword(pointer)))
            rpc.append((rcx,rdx,fields))
        elif rva==0x1387910:refreshed.append(rdx)
        elif rva==0xb648c0:need(rcx in members,'Receive callback member')
        elif rva!=0x1738300:raise RuntimeError('Unexpected metadata service '+hex(rva))
        returned()
    u.hook_add(UC_HOOK_CODE,hook)
    nonvolatile=((x.UC_X86_REG_RBX,0x33),(x.UC_X86_REG_RBP,0x55),(x.UC_X86_REG_RSI,0x66),(x.UC_X86_REG_RDI,0x77),
                 (x.UC_X86_REG_R12,0xcc),(x.UC_X86_REG_R13,0xdd),(x.UC_X86_REG_R14,0xee),(x.UC_X86_REG_R15,0xff))
    def invoke(at,rdx=0,r8=0,r9=0,fifth=0,reject=False):
        putq(sp,stop);putq(sp+0x28,fifth);u.reg_write(x.UC_X86_REG_RSP,sp)
        for reg,value in zip((x.UC_X86_REG_RCX,x.UC_X86_REG_RDX,x.UC_X86_REG_R8,x.UC_X86_REG_R9),(a.client,rdx,r8,r9)):u.reg_write(reg,value)
        for reg,value in nonvolatile:u.reg_write(reg,value)
        rejected.clear()
        try:u.emu_start(at,stop,count=20000)
        except UcError as error:raise RuntimeError(f'{error}; recent={list(recent)}') from error
        need(bool(rejected)==reject,'Metadata rejection '+str(list(recent)))
        if not reject:
            need(u.reg_read(x.UC_X86_REG_RIP)==stop and u.reg_read(x.UC_X86_REG_RSP)==sp+8,'Metadata return ABI '+str(list(recent)))
            need(all(u.reg_read(reg)==value for reg,value in nonvolatile),'Metadata nonvolatile restoration')
        return u.reg_read(x.UC_X86_REG_RAX)
    invoke(a.code+image.entry[0],owner)
    need(registered==[a.client] and qword(a.client)==owner and dword(a.client+0x10)==dword(a.client+0x38)==dword(a.client+0xc8)==0,'Constructor identity/reset contract')
    need(u.mem_read(a.metadata,128)==b''.join(struct.pack('<Q',members[0] if i==0 else 0)+b'\xa5'*8 for i in range(8)),'Constructor did not initialize every ID/preserve fields')
    invoke(h.code+receive.entry[2])
    for i,member in enumerate(members[1:],1):invoke(h.code+receive.entry[1],r8=member,r9=i,fifth=i+10)
    need(refreshed==members,'Shared local/receive producer callbacks')
    expected_metadata=b''.join(struct.pack('<QII',member,89 if i==0 else i,59 if i==0 else i+10) for i,member in enumerate(members))
    need(u.mem_read(a.metadata,128)==expected_metadata,'Producers wrote different metadata bank')
    need(rpc==[(0xe7f24551,0xfffffffffffffffe,[(1,4,89),(1,4,59)])],'Local metadata two-field payload')
    rpc.clear();putd(a.client+0x1d0,3);u.mem_write(a.client+0x51d,b'\1')
    for i,member in enumerate(members):
        if i==7:putd(a.metadata+8,90);putd(a.metadata+12,60)
        invoke(a.code+image.entry[1],member)
        need(dword(a.client+0x38)==i+1 and qword(a.ready+i*16)==member and u.mem_read(a.ready+i*16+8,8)==b'\1'+bytes(7),'Send/readiness append')
    need(rpc==[record for i,member in enumerate(members) for record in
         ((0xf004b017,member,[]),(0xe7f24551,member,[(1,4,0 if i==7 else 89),(1,4,0 if i==7 else 59)]))] and not events,'Send ordering/limits or premature completion')
    full=bytes(u.mem_read(a.ready,128));invoke(a.code+image.entry[2],0x600,reject=True)
    need(dword(a.client+0x38)==8 and u.mem_read(a.ready,128)==full,'Full append changed readiness bank')
    need(invoke(a.code+image.entry[2],members[-1])==a.ready+7*16,'Existing eighth record not found at capacity')
    # Keep opaque bytes distinguishable when the last record replaces a hole.
    u.mem_write(a.ready+7*16+10,b'\x77'*6);last=bytes(u.mem_read(a.ready+7*16,16))
    rpc.clear();invoke(a.code+image.entry[4],members[3])
    need(dword(a.client+0x38)==7 and u.mem_read(a.ready+3*16,16)==last and not events,'Full-record swap removal')
    for member in members[:3]+members[4:]:invoke(a.code+image.entry[4],member)
    need(dword(a.client+0x38)==0 and dword(a.client+0x1d0)==5 and events==[True] and
         rpc==[(0x37ff1aa7,members[0],[(0,4,1)])],'Final acknowledgment/native completion transition')
    expected=bytearray(expected_metadata);expected[8:16]=bytes(8)
    need(u.mem_read(a.metadata,128)==expected,'Send mutated remote metadata')
    need(u.mem_read(a.client+0x40,128)==b'\xa6'*128 and u.mem_read(a.client+0xd0,192)==b'\xa6'*192,'Inline readiness/metadata touched')
    for bank in (a.metadata,a.ready):need(u.mem_read(bank+128,16)==b'\xfa'*16,'Metadata/readiness bank tail')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True);args=p.parse_args()
    folder=PROJECT.parent/'work/hellforge-client-metadata';folder.mkdir(parents=True,exist_ok=True);out=folder/'client-metadata.dll'
    sources=[PROJECT/'mod/src'/name for name in ('ep_client_metadata.cpp','ep_host_accept.cpp','ep_session_code.cpp')]+[PROJECT/'tests/client_metadata_dll.cpp']
    cmd=[args.zig.resolve(),'c++','-std=c++17','-shared','-O0','-g','-I',PROJECT/'mod/src','-I',args.upstream.resolve()/'native/mod-sdk',*sources,'-o',out]
    result=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);need(result.returncode==0,result.stdout+result.stderr)
    dll=C.CDLL(str(out));prepare=dll.metadata_prepare_flow;prepare.restype=C.c_int
    need((rc:=prepare())==0,f'Metadata preparation/unwind line {rc}');flow(dll)
    print('PASS one metadata startup/send/ack flow: constructor initializes eight IDs, shared producers, original two-DWORD serializer and range limits, bounded eighth readiness record, full rejection, complete swap removal and final native transition; Windows unwind. game_access=false, hooks=0; registry/transport/event services are fixtures; remaining routes/runtime/UI/eight clients unverified.')


if __name__=='__main__':main()
