"""One focused host lifecycle flow in owned memory, at capacities five/eight.

Compile only this component and its code-page manager. Execute the real saved
lookup leaf and relocated reset/init windows; timer/memset are explicit service
fixtures. Full host methods, networking and gameplay are not verified here.
No game reads, hooks, full build/regression, hashes, receipts or packages.
"""
import argparse
import ctypes as C
import struct
import subprocess
import sys
from pathlib import Path
from generate_host_lifecycle import build,SOURCES
from generate_loadout_lifecycle import Capture,PROJECT,need
from host_task_layout import TASK_STRIDE,SECONDARY_COUNT,SECONDARY_START,PENDING_STRIDE
sys.path.insert(0,str(PROJECT.parent/'eight_player_candidate_20260927/.native-test-deps'))
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn import x86_const as x
from capstone.x86_const import X86_OP_MEM,X86_REG_RIP


class Addresses(C.Structure):
    _fields_=[(n,C.c_uint64) for n in ('game','code','client','confirmed','reject','peers','flags','large','pending')]+[('capacity',C.c_uint32),('reserved',C.c_uint32)]


class Image(C.Structure):
    _fields_=[(n,C.c_uint32) for n in ('bytes','table_offset','function_count','handler_offset','body_offset','source_rva')]+[('data',C.c_uint8*4096)]


def flow(dll,plans,capacity):
    a=Addresses(0x140000000,0x180000000,0x2100162c8,0x220000000,0x1c0000000,
                0x220010000,0x220020000,0x220030000,0x220040000,capacity,0)
    emit=dll.host_emit;emit.argtypes=[C.c_uint32,C.POINTER(Addresses),C.POINTER(Image)];emit.restype=C.c_int
    u=Uc(UC_ARCH_X86,UC_MODE_64);pages=set()
    def map_region(address,size):
        for page in range(address&~4095,(address+size+4095)&~4095,4096):
            if page not in pages:u.mem_map(page,4096);pages.add(page)
    owner=a.client-0x162c8;host=a.client-0x918;stack=0x230000000;stop=0x240000000
    for address,size in ((owner,0x30000),(stack,0x4000),(stop,4096),(a.reject,4096),
                         (a.confirmed,4096),(a.peers,4096),(a.flags,4096),(a.large,8*TASK_STRIDE+4096),(a.pending,4096)):
        map_region(address,size)
    code_bases=[]
    for kind in (1,2,3):
        a.code=0x180000000+0x10000*(kind-1);out=Image()
        need(emit(kind,C.byref(a),C.byref(out))==0,'Host emission');map_region(a.code,4096);u.mem_write(a.code,bytes(out.data));code_bases.append(a.code)
    capture=Capture();globals_={}
    for start,end in SOURCES[:2]:
        for i in capture.md.disasm(capture.read(start,end-start),start):
            if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
                target=a.game+i.address+i.size+i.disp
                if target not in globals_:
                    pointer=0x250000000+0x3000*len(globals_);globals_[target]=pointer
                    map_region(target,8);map_region(pointer,0x2000);u.mem_write(target,struct.pack('<Q',pointer));u.mem_write(pointer+4,struct.pack('<I',0x42))
    for rva in (0x12efab0,0x208aaa0):map_region(a.game+rva,16)
    u.mem_write(host,struct.pack('<Q',owner));u.mem_write(host+0x20,b'\xa5'*(0x918-0x20))
    u.mem_write(owner+0xb398,struct.pack('<QQ',0xaaa,0xbbb));u.mem_write(a.client+0xc8,struct.pack('<I',capacity))
    u.mem_write(a.client+0xd0,b'\xd5'*128)
    for i in range(capacity):
        row=bytearray(bytes((0x70+i,))*56);struct.pack_into('<Q',row,0,0x900+i);struct.pack_into('<I',row,0x20,3)
        u.mem_write(a.peers+56*i,bytes(row))
        row=bytearray(bytes((0xe0+i,))*32);struct.pack_into('<Q',row,0,0xaaa if i==1 else 0x100+i)
        struct.pack_into('<I',row,0x14,capacity-1 if i==1 else 1 if i==capacity-1 else i);u.mem_write(a.confirmed+32*i,bytes(row))
    u.mem_write(a.flags,b'\x7e'*(capacity+8));u.mem_write(a.large,b'\x5a'*(capacity*TASK_STRIDE+16));u.mem_write(a.pending,b'\x42'*(capacity*PENDING_STRIDE+16))
    rejected=[];services=[]
    def returned(cpu):
        sp=cpu.reg_read(x.UC_X86_REG_RSP);target=struct.unpack('<Q',cpu.mem_read(sp,8))[0]
        cpu.reg_write(x.UC_X86_REG_RSP,sp+8);cpu.reg_write(x.UC_X86_REG_RIP,target)
    def hook(cpu,address,size,data):
        if address==a.reject:rejected.append(True);cpu.emu_stop()
        elif address==a.game+0x12efab0:
            need(cpu.reg_read(x.UC_X86_REG_RCX)==owner+0xb400,'Timer receiver');services.append('timer')
            cpu.reg_write(x.UC_X86_REG_XMM0,struct.unpack('<I',struct.pack('<f',1.25))[0]);returned(cpu)
        elif address==a.game+0x208aaa0:
            need(cpu.reg_read(x.UC_X86_REG_RCX)==a.large and cpu.reg_read(x.UC_X86_REG_RDX)==0 and cpu.reg_read(x.UC_X86_REG_R8)==capacity*TASK_STRIDE,'Large reset extent')
            services.append('memset');cpu.mem_write(a.large,bytes(capacity*TASK_STRIDE));cpu.reg_write(x.UC_X86_REG_RAX,a.large);returned(cpu)
    u.hook_add(UC_HOOK_CODE,hook)
    def run(begin,finish):
        u.reg_write(x.UC_X86_REG_RSP,stack+0x1800);u.reg_write(x.UC_X86_REG_RBX,host);u.reg_write(x.UC_X86_REG_RDI,host)
        u.emu_start(begin,finish,count=2500)
        need(u.reg_read(x.UC_X86_REG_RIP)==finish and not rejected,'Host window did not complete')
    def lookup(peer):
        u.reg_write(x.UC_X86_REG_RCX,host);u.reg_write(x.UC_X86_REG_RDX,peer);u.reg_write(x.UC_X86_REG_RSP,stack+0x1808)
        u.mem_write(stack+0x1808,struct.pack('<Q',stop));u.emu_start(code_bases[2],stop,count=250)
        need(u.reg_read(x.UC_X86_REG_RIP)==stop and not rejected and u.reg_read(x.UC_X86_REG_R9)==host,'Lookup return/native host register');return u.reg_read(x.UC_X86_REG_RAX)
    need(lookup(0x900+capacity-1)==a.peers+56*(capacity-1) and lookup(0)==0,'Last/full host slot lookup')
    m=plans[1]['mapping'];before=bytes(u.mem_read(a.peers,capacity*56))
    run(code_bases[1]+m[0x1088ddb],code_bases[1]+m[0x1088eb4])
    expected=bytearray(before)
    for i in range(capacity):struct.pack_into('<Q',expected,i*56,0);struct.pack_into('<I',expected,i*56+0x20,0)
    struct.pack_into('<QQII',expected,0,0xaaa,0xbbb,0x42,capacity-1);struct.pack_into('<I',expected,0x20,9)
    flags=bytearray(capacity);flags[capacity-1]=1
    need(u.mem_read(a.peers,capacity*56)==expected and u.mem_read(a.flags,capacity+8)==bytes(flags)+b'\x7e'*8,'Resume opaque fields/index/flag bounds')
    need(u.reg_read(x.UC_X86_REG_R10)==owner and u.reg_read(x.UC_X86_REG_R11)==0,'Resume live owner/zero register')
    need(lookup(0xaaa)==a.peers and lookup(0)==a.peers+56,'Resume self/empty slot')
    # Preserve native -1 fallback, then exercise a real start-hosting reset.
    u.mem_write(a.confirmed+32+0x14,struct.pack('<I',0xffffffff))
    run(code_bases[1]+m[0x1088ddb],code_bases[1]+m[0x1088eb4])
    need(u.mem_read(a.peers+0x14,4)==bytes(4) and u.mem_read(a.flags,capacity)==b'\1'+bytes(capacity-1),'Native -1 fallback')
    m=plans[0]['mapping'];run(code_bases[0]+m[0x1088a78],code_bases[0]+m[0x1088bf4])
    expected=bytearray(capacity*56);struct.pack_into('<QQII',expected,0,0xaaa,0xbbb,0x42,0)
    struct.pack_into('<f',expected,0x18,1.25);struct.pack_into('<I',expected,0x20,9)
    need(u.mem_read(a.peers,capacity*56)==expected and u.mem_read(a.flags,capacity+8)==b'\1'+bytes(capacity-1)+b'\x7e'*8,'Start host records/flags')
    need(u.mem_read(a.large,capacity*TASK_STRIDE+16)==bytes(capacity*TASK_STRIDE)+b'\x5a'*16 and services==['timer','memset'],'Large reset and service order')
    need(u.mem_read(a.pending,capacity*PENDING_STRIDE+16)==b'\x42'*(capacity*PENDING_STRIDE+16),'Pending unexpectedly reset')
    need(u.mem_read(a.client+0xc8,4)==struct.pack('<I',1) and u.mem_read(a.confirmed,8)==struct.pack('<Q',0xaaa) and u.mem_read(a.confirmed+0x14,4)==bytes(4),'Shared confirmed self reset')
    need(u.mem_read(a.client+0xd0,128)==b'\xd5'*128 and u.mem_read(host+0x20,0x918-0x20)==b'\xa5'*(0x918-0x20),'Native banks/tail/sibling overwritten')
    # A malformed network index rejects before indexing the external flag bank.
    u.mem_write(a.confirmed+0x14,struct.pack('<I',capacity));flags_before=bytes(u.mem_read(a.flags,capacity+8))
    m=plans[1]['mapping'];u.reg_write(x.UC_X86_REG_RSP,stack+0x1800);u.reg_write(x.UC_X86_REG_RBX,host)
    u.emu_start(code_bases[1]+m[0x1088ddb],code_bases[1]+m[0x1088eb4],count=2500)
    need(rejected and u.mem_read(a.flags,capacity+8)==flags_before,'Malformed network index reached flags')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True);a=p.parse_args()
    library=PROJECT/'build/host_lifecycle_test.dll';library.parent.mkdir(exist_ok=True)
    sources=[PROJECT/'mod/src'/n for n in ('ep_host_lifecycle.cpp','ep_session_code.cpp')]+[PROJECT/'tests/host_lifecycle_dll.cpp']
    cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
         '-Wno-missing-field-initializers','-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*sources,'-o',library]
    result=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);need(result.returncode==0,result.stdout+result.stderr)
    dll=C.CDLL(str(library));prepare=dll.host_prepare_flow;prepare.argtypes=[];prepare.restype=C.c_int
    need((rc:=prepare())==0,f'Host prepare/unwind/cleanup line {rc}')
    plans=[build(k) for k in (1,2,3)]
    for capacity in (5,8):flow(dll,plans,capacity)
    print('PASS one host lifecycle flow: actual prepare/unwind/discard and saved start/resume/lookup windows at capacity 5/8; '
          'opaque records, network index, shared confirmed reset, bank extents. game_access=false, hooks=0; '
          'timer/memset are fixtures; full native services, host migration and gameplay unverified.')


if __name__=='__main__':main()
