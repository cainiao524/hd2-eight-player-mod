"""One admission/consume/deferred-accept flow using shared member banks.

Native acceptance, metadata update/receive, host update and registered insert
are executed together. Services, registry and settings are explicit fixtures;
no real packets, game access, installation or runtime activation is exercised.
"""
import argparse
import ctypes as C
import struct
import subprocess
from collections import deque
from pathlib import Path
from generate_loadout_lifecycle import PROJECT,need
from generate_host_accept import SOURCES
from validate_host_lifecycle import Addresses
from validate_host_pending import flow as admission
from validate_host_update import consume
from validate_host_removal import Image as RemovalImage
from validate_client_disconnect import Addresses as ClientAddresses
from validate_client_peers import Image as RegisteredImage
from unicorn import UcError,UC_HOOK_CODE
from unicorn import x86_const as x
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_REG_RIP


class AcceptAddresses(C.Structure):
    _fields_=[('host',Addresses)]+[(name,C.c_uint64) for name in ('metadata','remove_data','registered_insert')]


class AcceptImage(C.Structure):
    _fields_=[('bytes',C.c_uint32),('table_offset',C.c_uint32),('function_count',C.c_uint32),
              ('entry',C.c_uint32*3),('handler_offset',C.c_uint32),('data',C.c_uint8*4096)]


def accept(dll,f):
    u=f['u'];u.hook_del(f['hook_handle']);h=Addresses.from_buffer_copy(f['h']);h.code=0x1800a0000
    map_region,putq,putd,qword,dword=(f[name] for name in ('map_region','putq','putd','qword','dword'))
    owner,host,sp,stop=(f[name] for name in ('owner','host','sp','stop'))
    removal_h=Addresses.from_buffer_copy(h);removal_h.code=0x1800c0000;removal=RemovalImage()
    emit=dll.accept_removal_emit;emit.argtypes=[C.POINTER(Addresses),C.POINTER(RemovalImage)];emit.restype=C.c_int
    need(emit(C.byref(removal_h),C.byref(removal))==0,'Shared removal image')
    registered_a=ClientAddresses(h.game,0x1800b0000,h.client,h.confirmed,h.reject,h.capacity,0);registered=RegisteredImage()
    emit=dll.accept_registered_emit;emit.argtypes=[C.POINTER(ClientAddresses),C.POINTER(RegisteredImage)];emit.restype=C.c_int
    need(emit(C.byref(registered_a),C.byref(registered))==0,'Shared registered insertion image')
    a=AcceptAddresses(h,0x220060000,removal_h.code+removal.entry[1],registered_a.code);image=AcceptImage()
    emit=dll.accept_emit;emit.argtypes=[C.POINTER(AcceptAddresses),C.POINTER(AcceptImage)];emit.restype=C.c_int
    need(emit(C.byref(a),C.byref(image))==0,'Acceptance image')
    for address,data in ((h.code,image.data),(removal_h.code,removal.data),(registered_a.code,registered.data)):
        map_region(address,4096);u.mem_write(address,bytes(data))
    f['a'].accept_peer=h.code+image.entry[0]
    need(dll.update_emit(C.byref(f['a']),C.byref(f['image']))==0,'Caller acceptance binding')
    u.mem_write(f['h'].code,bytes(f['image'].data))
    capture=f['f']['capture'];globals_=f['globals_'];by_pc={};ins=[];registry=0x320000000
    for start,end in (*SOURCES,(0xb90b20,0xb90eab)):
        ins+=list(capture.md.disasm(capture.read(start,end-start),start))
    for i in ins:
        if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
            target=h.game+i.address+i.size+i.disp;map_region(target,64)
            if i.mnemonic=='mov':
                if i.address in (0xb90b37,0xb90be9):globals_[target]=registry
                if target not in globals_:globals_[target]=0x300000000+len(globals_)*0x1000000
                pointer=globals_[target];map_region(pointer,0x200000);putq(target,pointer);by_pc[i.address]=pointer
    putd(registry+0x6438,1);putq(registry+0x6440,h.client);putd(registry+0x6448,0xeb);putq(h.client,owner)
    services={i.operands[0].imm for i in ins if i.mnemonic=='call' and i.operands[0].type==X86_OP_IMM}
    services.add(0xb648c0)  # metadata receive's original tail-call
    for rva in services:map_region(h.game+rva,16);u.mem_write(h.game+rva,b'\xc3')
    members=f['members'];metadata=[(members[0],89,59)]+[(member,0 if i==7 else i,0 if i==7 else i+10) for i,member in enumerate(members[1:],1)]
    map_region(a.metadata,4096);putq(a.metadata,members[0]);u.mem_write(a.metadata+128,b'\xfa'*16)
    u.mem_write(h.client+0xd0,b'\xa6'*0xc0);u.mem_write(h.confirmed+256,b'\xfa'*16)
    putd(by_pc[0x1084e16]+0xddcdc,89);putd(by_pc[0x1084e16]+0xddce0,59)
    config=owner+0x164b8;putd(config+0x200,0x1234);putq(config+0x208,0x55667788)
    u.mem_write(config+0x210,bytes(range(12)));putd(config+0x21c,17)
    putq(host+0x908,0xaabb);putq(host+0x910,0xccdd);putd(host+0x1c,0)
    rpc=[];notifications=[];refresh=[];added=[];registered_calls=[];recent=deque(maxlen=12)
    def hook(cpu,address,size,data):
        recent.append(hex(address));need(address!=h.reject,'Acceptance rejection '+str(list(recent)))
        rcx=cpu.reg_read(x.UC_X86_REG_RCX);rdx=cpu.reg_read(x.UC_X86_REG_RDX);r8=cpu.reg_read(x.UC_X86_REG_R8);r9=cpu.reg_read(x.UC_X86_REG_R9)
        rsp=cpu.reg_read(x.UC_X86_REG_RSP);returned=f['returned'];rva=address-h.game
        if address==registered_a.code:registered_calls.append(rdx)
        if rva==0xbde430:
            fields=[]
            for index in range(r9):
                kind,width,pointer=struct.unpack('<IIQ',u.mem_read(r8+index*16,16))
                need((kind,width) in ((9,8),(1,4),(3,12),(5,0)),'Acceptance descriptor kind/width')
                value=pointer if kind==5 else bytes(u.mem_read(pointer,width)) if kind==3 else int.from_bytes(u.mem_read(pointer,width),'little')
                fields.append((kind,width,value))
            rpc.append((rcx,rdx,fields));returned();return
        if rva==0xbe4910:
            notifications.append((rcx,rdx,r8,r9,dword(rsp+0x28),u.mem_read(rsp+0x30,1)[0]));returned();return
        if rva==0x135ea10:returned(1);return
        if rva==0x1387910:refresh.append(rdx);returned();return
        if rva==0xb648c0:need(rcx in members,'Metadata refresh member');returned();return
        if rva==0xb5ea90:added.append(rcx);returned();return
        if rva in (0x1346e30,0xb5f140,0xb51de0):returned();return
        if rva==0x2088770:
            need(rcx==by_pc[0x108c776],'Acceptance/update shared cookie');returned();return
        if rva in services and rva!=0x1738300:raise RuntimeError('Unbound acceptance service '+hex(rva))
        f['hook'](cpu,address,size,data)
    u.hook_add(UC_HOOK_CODE,hook)
    def invoke(kind,rdx=0,r8=0,r9=0,fifth=0):
        putq(sp,stop);putq(sp+0x28,fifth);u.reg_write(x.UC_X86_REG_RSP,sp)
        for reg,value in zip((x.UC_X86_REG_RCX,x.UC_X86_REG_RDX,x.UC_X86_REG_R8,x.UC_X86_REG_R9),(host if kind==0 else h.client,rdx,r8,r9)):u.reg_write(reg,value)
        for reg,value in f['f']['nonvolatile']:u.reg_write(reg,value)
        try:u.emu_start(h.code+image.entry[kind],stop,count=100000)
        except UcError as error:raise RuntimeError(f'{error}; recent={list(recent)}') from error
        need(u.reg_read(x.UC_X86_REG_RIP)==stop and u.reg_read(x.UC_X86_REG_RSP)==sp+8,'Acceptance return ABI '+str(list(recent)))
        need(all(u.reg_read(reg)==value for reg,value in f['f']['nonvolatile']),'Acceptance nonvolatile restoration')
    invoke(2)
    for i,member in enumerate(members[1:],1):invoke(1,r8=member,r9=90 if i==7 else i,fifth=60 if i==7 else i+10)
    expected_metadata=b''.join(struct.pack('<QII',*row) for row in metadata)
    need(u.mem_read(a.metadata,128)==expected_metadata and refresh==members,'Eight metadata records and native range limits')
    need(rpc==[(0xe7f24551,0xfffffffffffffffe,[(1,4,89),(1,4,59)])],'Local metadata payload')
    rpc.clear();putd(config+0x220,2);putd(config+0x224,2)
    for i,member in enumerate(members[1:],1):
        invoke(0,member,0xf000+i,0xa000+i,100+i)
        need(dword(h.peers+i*56+0x20)==4 and qword(h.peers+i*56+0x28)==0xf000+i,'Native blocked-mode deferral')
    need(not rpc and not registered_calls and dword(h.client+0xc8)==1,'Deferred acceptance published membership')
    putd(config+0x220,1);putd(config+0x224,0)
    # The actual host-update body retries all seven deferred members through
    # the new entry; no direct acceptance call substitutes for this transition.
    f['tick']()
    need(registered_calls==members[1:] and added==members[1:] and dword(h.client+0xc8)==8,'Registered insertion did not fill eighth confirmed slot')
    expected_rpc=[];expected_notifications=[]
    for i,member in enumerate(members[1:],1):
        row=bytes(u.mem_read(h.confirmed+i*32,32))
        need(struct.unpack_from('<QQII',row)==(member,0xa000+i,100+i,i) and row[24:26]==b'\0\0','Confirmed metadata/index differs from accepted peer')
        need(dword(h.peers+i*56+0x20)==5 and u.mem_read(h.peers+i*56+0x28,16)==bytes(16),'Accepted peer state/key cleanup')
        expected_rpc += [(0x4bfb3315,member,[(9,8,0xf000+i)]),(0x1ab72826,member,[]),(0x9bf86d8c,member,[])]
        expected_rpc += [(0xbbe961c3,member,[(9,8,who),(1,4,first),(1,4,second)]) for who,first,second in metadata]
        expected_rpc += [(0xe25ac0a9,member,[(9,8,0xaabb),(9,8,0xccdd)]),
                         (0x62b8a2cd,member,[(9,8,0xf000+i),(5,0,config),(1,4,0x1234),(9,8,0x55667788),
                                           (3,12,bytes(range(12))),(1,4,1),(1,4,17),(1,4,0),(1,4,1)])]
        for j,other in enumerate(members[:i+1]):
            expected_notifications.append((member,other,0 if j==0 else 0xa000+j,0 if j==0 else 100+j,j,1 if j==0 else 0))
            if j:expected_notifications.append((other,member,0xa000+i,100+i,i,0))
    need(rpc==expected_rpc,'Acceptance payload ordering or original field count/width')
    need(notifications==expected_notifications,'Reciprocal membership messages lost metadata or eighth peer')
    need(u.mem_read(a.metadata,128)==expected_metadata and u.mem_read(h.client+0xd0,0xc0)==b'\xa6'*0xc0,'Metadata bank changed or inline client array touched')
    need(u.mem_read(host+0x20,0x908-0x20)==b'\xa5'*(0x908-0x20),'Inline host array touched')
    for bank,size in ((h.confirmed,256),(h.peers,448),(a.metadata,128)):
        need(u.mem_read(bank+size,16)==b'\xfa'*16,'Acceptance bank tail')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True);args=p.parse_args()
    folder=PROJECT.parent/'work/hellforge-host-accept';folder.mkdir(parents=True,exist_ok=True);out=folder/'host-accept.dll'
    sources=[PROJECT/'mod/src'/name for name in ('ep_host_pending.cpp','ep_host_update.cpp','ep_host_accept.cpp','ep_host_removal.cpp',
                                               'ep_client_peers.cpp','ep_client_update.cpp','ep_client_disconnect.cpp','ep_session_code.cpp')]
    sources += [PROJECT/'tests'/name for name in ('host_pending_dll.cpp','host_update_dll.cpp','host_accept_dll.cpp')]
    cmd=[args.zig.resolve(),'c++','-std=c++17','-shared','-O0','-g','-I',PROJECT/'mod/src','-I',args.upstream.resolve()/'native/mod-sdk',*sources,'-o',out]
    result=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);need(result.returncode==0,result.stdout+result.stderr)
    dll=C.CDLL(str(out));prepare=dll.accept_prepare_flow;prepare.restype=C.c_int
    need((rc:=prepare())==0,f'Acceptance preparation/unwind line {rc}')
    admission(dll,lambda f:consume(dll,f,lambda f:accept(dll,f)))
    print('PASS one admission/consume/deferred-accept flow: actual caller retry and registered insertion through eighth confirmed slot; eight-record metadata receive/local refresh/forwarding, original reciprocal and nine-field settings payloads, Windows unwind. game_access=false, hooks=0; services/settings are fixtures; runtime/UI/eight clients/decoder/activation unverified.')


if __name__=='__main__':main()
