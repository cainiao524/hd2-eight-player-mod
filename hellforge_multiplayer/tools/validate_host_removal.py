"""One host remove/dispatch flow in owned memory, capacities five/eight.

Execute all three relocated functions, including the dispatcher's private
cleanup call. Native service callbacks record arguments only; no game access,
SDK hooks, network traffic, full regression, receipts, hashes or packages.
"""
import argparse
import ctypes as C
import struct
import subprocess
import sys
from collections import deque
from pathlib import Path
from generate_host_removal import SOURCES
from generate_loadout_lifecycle import Capture,PROJECT,need
from validate_host_lifecycle import Addresses
sys.path.insert(0,str(PROJECT.parent/'eight_player_candidate_20260927/.native-test-deps'))
from unicorn import Uc,UcError,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn import x86_const as x
from capstone.x86_const import X86_OP_MEM,X86_REG_RIP


class Image(C.Structure):
    _fields_=[('bytes',C.c_uint32),('table_offset',C.c_uint32),('function_count',C.c_uint32),('entry',C.c_uint32*3),('data',C.c_uint8*4096)]


def removed_large(source,peer):
    """Native swap-removal model; retain stale tail bytes and opaque fields."""
    out=bytearray(source)
    for base in range(0,len(out),448):
        for count_at,items,stride in ((8,16,8),(56,64,32)):
            count=struct.unpack_from('<I',out,base+count_at)[0];index=0
            while index<count:
                at=base+items+index*stride
                if struct.unpack_from('<Q',out,at)[0]==peer:
                    count-=1;struct.pack_into('<I',out,base+count_at,count)
                    last=base+items+count*stride;out[at:at+stride]=out[last:last+stride]
                else:index+=1
        if struct.unpack_from('<I',out,base+8)[0]==0:out[base:base+448]=bytes(448)
    return bytes(out)


def flow(dll,capacity):
    a=Addresses(0x140000000,0x180000000,0x2100162c8,0x220000000,0x1c0000000,
                0x220010000,0x220020000,0x220030000,0x220040000,capacity,0)
    emit=dll.host_removal_emit;emit.argtypes=[C.POINTER(Addresses),C.POINTER(Image)];emit.restype=C.c_int
    out=Image();need(emit(C.byref(a),C.byref(out))==0,'Removal emission')
    u=Uc(UC_ARCH_X86,UC_MODE_64);pages=set();owner=a.client-0x162c8;host=a.client-0x918
    stack,stop,stub=0x230000000,0x240000000,0x260000000;peer=0x500+capacity-1
    def map_region(address,size):
        for page in range(address&~4095,(address+size+4095)&~4095,4096):
            if page not in pages:u.mem_map(page,4096);pages.add(page)
    for address,size in ((a.code,4096),(owner,0x30000),(stack,0x5000),(stop,4096),(stub,4096),(a.reject,4096),
                         (a.confirmed,4096),(a.peers,4096),(a.flags,4096),(a.large,8192),(a.pending,4096)):
        map_region(address,size)
    u.mem_write(a.code,bytes(out.data));u.mem_write(host,struct.pack('<Q',owner));u.mem_write(host+0x20,b'\xa5'*(0x918-0x20))
    u.mem_write(owner+0xb390,struct.pack('<QQQQ',0x111,0x500,0x222,0x500));u.mem_write(a.client+0xc8,struct.pack('<I',capacity))
    u.mem_write(a.confirmed,b'\xc4'*(capacity*32));u.mem_write(a.pending,b'\xd4'*(capacity*64))
    u.mem_write(a.flags,b'\1'*capacity+b'\xfa'*8)
    original_peers=bytearray()
    for i in range(capacity):
        row=bytearray(bytes((0x70+i,))*56);struct.pack_into('<Q',row,0,0x500+i)
        struct.pack_into('<I',row,0x14,1 if i==capacity-1 else capacity-1 if i==1 else i)
        struct.pack_into('<I',row,0x20,9 if i==0 else 4 if i==2 else 6);original_peers+=row
    u.mem_write(a.peers,bytes(original_peers))
    original_large=bytearray()
    for i in range(capacity):
        row=bytearray(b'\xcc'*448);struct.pack_into('<Q',row,0,0x700+i)
        ids=[peer,0x777,peer,0x778,peer] if i==0 else [] if i==2 else [peer] if i==capacity-1 else [0x777,peer]
        struct.pack_into('<I',row,8,len(ids))
        for j,p in enumerate(ids):struct.pack_into('<Q',row,16+8*j,p)
        count=12 if i==1 else 3;struct.pack_into('<I',row,56,count)
        for j in range(count):
            item=bytearray(bytes((0x20+j,))*32);struct.pack_into('<Q',item,0,peer if j%3==1 else 0x800+j)
            row[64+32*j:96+32*j]=item
        original_large+=row
    u.mem_write(a.large,bytes(original_large)+b'\xfb'*16)
    capture=Capture();globals_={}
    for i in capture.md.disasm(capture.read(SOURCES[2][0],SOURCES[2][1]-SOURCES[2][0]),SOURCES[2][0]):
        if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
            target=a.game+i.address+i.size+i.disp;map_region(target,0x40)
            if i.mnemonic=='mov' and target not in globals_:
                pointer=0x250000000+0x1000*len(globals_);globals_[target]=pointer;map_region(pointer,4096)
                u.mem_write(target,struct.pack('<Q',pointer));u.mem_write(pointer+0x28,b'\1');u.mem_write(pointer+0x40,struct.pack('<Q',stub+0x800))
    u.mem_write(stub+0x808,struct.pack('<Q',stub))
    service_rvas=(0x1738300,0x1092ac0,0x1346f70,0x1089400,0xbde430,0xb90eb0,0x1360380,0x208aaa0)
    for rva in service_rvas:
        map_region(a.game+rva,16);u.mem_write(a.game+rva,b'\xc3')
    u.mem_write(stub,b'\xc3');u.mem_write(a.reject,b'\xcc')
    rejected=[];sent=[];events=[];local=[];private_calls=[];recent=deque(maxlen=8)
    def qword(p):return struct.unpack('<Q',u.mem_read(p,8))[0]
    def returned(value=0):
        sp=u.reg_read(x.UC_X86_REG_RSP);target=qword(sp);u.reg_write(x.UC_X86_REG_RSP,sp+8)
        u.reg_write(x.UC_X86_REG_RAX,value);u.reg_write(x.UC_X86_REG_RIP,target)
    def hook(cpu,address,size,data):
        recent.append(hex(address))
        if address==a.reject:rejected.append(True);cpu.emu_stop();return
        if address==a.code+out.entry[1]:private_calls.append(True);return
        if address==stub:returned(0);return
        if address-a.game not in service_rvas:return
        rva=address-a.game;rcx=cpu.reg_read(x.UC_X86_REG_RCX);rdx=cpu.reg_read(x.UC_X86_REG_RDX);r8=cpu.reg_read(x.UC_X86_REG_R8)
        if rva==0x208aaa0:
            need(stack<=rcx and rcx+448<=stack+0x5000 and rdx==0 and r8==448,'Native temporary clear')
            cpu.mem_write(rcx,bytes(448));returned(rcx);return
        if rva==0xbde430:
            need(rcx==0x1acfcdf1 and cpu.reg_read(x.UC_X86_REG_R9)==2,'Removal RPC identity')
            first=struct.unpack('<IIQ',cpu.mem_read(r8,16));second=struct.unpack('<IIQ',cpu.mem_read(r8+16,16))
            need(first[:2]==(9,8) and second[:2]==(1,4),'RPC field width changed with capacity')
            need(qword(first[2])==peer and struct.unpack('<I',cpu.mem_read(second[2],4))[0]==2,'RPC removed ID/reason')
            sent.append(rdx)
        if rva==0x1360380:events.append(rdx)
        if rva==0xb90eb0:local.append((rcx,rdx,r8))
        if rva==0x1089400:need((rcx,rdx,r8)==(host,peer,0x500),'Native host service arguments')
        returned(1 if rva==0x1092ac0 else 0)
    u.hook_add(UC_HOOK_CODE,hook)
    def call(entry,target):
        u.reg_write(x.UC_X86_REG_RCX,host);u.reg_write(x.UC_X86_REG_RDX,target);u.reg_write(x.UC_X86_REG_R8,2);u.reg_write(x.UC_X86_REG_R9,3)
        u.reg_write(x.UC_X86_REG_RSP,stack+0x2008);u.mem_write(stack+0x2008,struct.pack('<Q',stop))
        try:u.emu_start(a.code+out.entry[entry],stop,count=25000)
        except UcError as error:
            raise RuntimeError(f'{error}; RIP={u.reg_read(x.UC_X86_REG_RIP):x}; recent={list(recent)}') from error
        need(u.reg_read(x.UC_X86_REG_RIP)==stop and not rejected,'Removal call did not finish')
        return u.reg_read(x.UC_X86_REG_RAX)
    need(call(0,peer)==a.large and call(0,0x999)==0,'Large record lookup')
    call(2,peer)
    need(len(private_calls)==1,'Dispatcher did not use its private removal body')
    need(u.mem_read(a.large,capacity*448+16)==removed_large(original_large,peer)+b'\xfb'*16,'Full-bank native swap removal')
    expected=bytearray(original_peers);at=(capacity-1)*56
    struct.pack_into('<Q',expected,at,0);struct.pack_into('<I',expected,at+0x20,0);struct.pack_into('<I',expected,at+0x18,0)
    flags=bytearray(b'\1'*capacity);flags[1]=0
    need(u.mem_read(a.peers,capacity*56)==expected and u.mem_read(a.flags,capacity+8)==bytes(flags)+b'\xfa'*8,'Host record/network flag removal')
    need(sent==[0x500+i for i in range(1,capacity-1)] and events==[0x500+i for i in range(1,capacity-1) if i!=2] and local==[(0x500,peer,2)],'Native remaining-member notifications')
    need(call(0,peer)==0,'Removed peer still in a large record')
    need(u.mem_read(host+0x20,0x918-0x20)==b'\xa5'*(0x918-0x20) and u.mem_read(a.pending,capacity*64)==b'\xd4'*(capacity*64)
         and u.mem_read(a.confirmed,capacity*32)==b'\xc4'*(capacity*32),'Unrelated/native banks changed')
    # Lookup has only caller home space: reject without a misaligned call or
    # losing its saved nonvolatile registers when an inner count exceeds room.
    u.mem_write(a.large+8,struct.pack('<I',6));u.reg_write(x.UC_X86_REG_RCX,host);u.reg_write(x.UC_X86_REG_RDX,peer)
    u.reg_write(x.UC_X86_REG_RSP,stack+0x2008)
    for reg,value in ((x.UC_X86_REG_RBX,0x33),(x.UC_X86_REG_RBP,0x55),(x.UC_X86_REG_RSI,0x66),(x.UC_X86_REG_RDI,0x77)):u.reg_write(reg,value)
    u.emu_start(a.code+out.entry[0],stop,count=500)
    need(rejected and u.reg_read(x.UC_X86_REG_RSP)==stack+0x2008 and
         [u.reg_read(r) for r in (x.UC_X86_REG_RBX,x.UC_X86_REG_RBP,x.UC_X86_REG_RSI,x.UC_X86_REG_RDI)]==[0x33,0x55,0x66,0x77],'Home-space rejection unwind')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True);a=p.parse_args()
    library=PROJECT/'build/host_removal_test.dll';library.parent.mkdir(exist_ok=True)
    sources=[PROJECT/'mod/src'/n for n in ('ep_host_removal.cpp','ep_session_code.cpp')]+[PROJECT/'tests/host_removal_dll.cpp']
    cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
         '-Wno-missing-field-initializers','-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*sources,'-o',library]
    result=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);need(result.returncode==0,result.stdout+result.stderr)
    dll=C.CDLL(str(library));prepare=dll.host_removal_prepare_flow;prepare.argtypes=[];prepare.restype=C.c_int
    need((rc:=prepare())==0,f'Host removal prepare/unwind/cleanup line {rc}')
    for capacity in (5,8):flow(dll,capacity)
    print('PASS one host removal flow at capacity 5/8: actual saved lookup/private cleanup/dispatch, all large records, '
          'duplicate swap-removal, complete secondary entries, network-index flag, unchanged 4-byte reason and Windows unwind. '
          'game_access=false, hooks=0; native services are recording fixtures; migration/protocol/gameplay unverified.')


if __name__=='__main__':main()
