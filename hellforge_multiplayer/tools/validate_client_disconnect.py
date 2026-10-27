"""One focused relocated-peer cleanup flow; no full regression/game access."""
import argparse
import ctypes as c
import struct
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'eight_player_candidate_20260927/.native-test-deps'))
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn import x86_const as x
from generate_client_disconnect import PROJECT,START


def need(ok,message):
    if not ok:raise RuntimeError(message)


class Addresses(c.Structure):
    _fields_=[(n,c.c_uint64) for n in ('game','code','client','peers','reject')]+[('capacity',c.c_uint32),('reserved',c.c_uint32)]


class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','table_offset','function_count','handler_offset','body_offset','lookup_offset')]+[('data',c.c_uint8*4096)]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True)
    a=p.parse_args();library=(PROJECT/'build/client_disconnect_test.dll').resolve();library.parent.mkdir(exist_ok=True)
    sources=[PROJECT/'mod/src/ep_client_disconnect.cpp',PROJECT/'mod/src/ep_session_code.cpp',PROJECT/'tests/client_disconnect_dll.cpp']
    cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
         '-Wno-missing-field-initializers','-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*sources,'-o',library]
    r=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);need(r.returncode==0,r.stdout+r.stderr)
    dll=c.CDLL(str(library));emit=dll.client_disconnect_emit;emit.argtypes=[c.POINTER(Addresses),c.POINTER(Image)];emit.restype=c.c_int
    unwind=dll.client_disconnect_unwind;unwind.argtypes=[];unwind.restype=c.c_int
    addresses=Addresses(0x140000000,0x180000000,0x200000000,0x200010010,0x1c0000000,8,0);image=Image()
    need(emit(c.byref(addresses),c.byref(image))==0,'Emission failed')
    mu=Uc(UC_ARCH_X86,UC_MODE_64)
    for at,size in ((addresses.code,0x1000),(addresses.client,0x1000),(addresses.peers&~4095,0x1000),
                    (addresses.reject,0x1000),(addresses.game+0xb5f000,0x1000),(0x300000000,0x2000)):
        mu.mem_map(at,size)
    mu.mem_write(addresses.code,bytes(image.data[:image.bytes]));release=addresses.game+0xb5f140;mu.mem_write(release,b'\xc3')
    base=addresses.code+image.body_offset;after_clear=base+0x1084a2f-START;sp=0x300001000
    released=[];stops=[]
    def hook(uc,pc,size,user):
        if pc==release:released.append(uc.reg_read(x.UC_X86_REG_RCX))
        if pc in (base,addresses.reject,after_clear):stops.append(pc);uc.emu_stop()
    mu.hook_add(UC_HOOK_CODE,hook)
    # An unmapped foreign RCX must reach rejection without reading it. An
    # excessive count also stops before any original disconnect side effect.
    for client,count,target in ((addresses.client+0x8000,0,addresses.reject),(addresses.client,9,addresses.reject),
                                 (addresses.client,5,base)):
        mu.mem_write(addresses.client+0xc8,struct.pack('<I',count));mu.reg_write(x.UC_X86_REG_RCX,client)
        mu.reg_write(x.UC_X86_REG_RDX,3);mu.reg_write(x.UC_X86_REG_R8,2);mu.reg_write(x.UC_X86_REG_RSP,sp+8)
        mu.emu_start(addresses.code,addresses.code+image.bytes,count=30)
        need(stops[-1]==target and not released,'Incorrect entry guard')
        need(mu.reg_read(x.UC_X86_REG_RDX)==3 and mu.reg_read(x.UC_X86_REG_R8)==2,'Changed native reason/mode')
    # Five peers in an eight-slot bank: native B5F140 receives all five IDs;
    # unused slots clear too. Adjacent inline client state must remain intact.
    peers=[0x100+i for i in range(5)];data=bytearray(b'\xa5'*256)
    for i,peer in enumerate(peers):struct.pack_into('<Q',data,32*i,peer)
    mu.mem_write(addresses.peers-16,b'\x6c'*288);mu.mem_write(addresses.peers,bytes(data))
    mu.mem_write(addresses.client+0xd0,b'\x5a'*144)
    mu.reg_write(x.UC_X86_REG_RDI,addresses.client);mu.reg_write(x.UC_X86_REG_R12,0);mu.reg_write(x.UC_X86_REG_RSP,sp)
    mu.emu_start(base+0x10849ba-START,addresses.code+image.bytes,count=300)
    need(stops[-1]==after_clear and released==peers,'Dropped or wrong peer release')
    need(mu.mem_read(addresses.client+0xc8,4)==bytes(4) and mu.mem_read(addresses.peers,256)==bytes(256),'Incomplete reset')
    need(mu.mem_read(addresses.client+0xd0,144)==b'\x5a'*144,'Inline/neighbor overwrite')
    need(mu.mem_read(addresses.peers-16,16)==b'\x6c'*16 and mu.mem_read(addresses.peers+256,16)==b'\x6c'*16,'Bank boundary overwrite')
    # Model a count increase after the entry guard. No ninth peer read/callback;
    # rejection is called with Windows ABI alignment under the native frame.
    mu.reg_write(x.UC_X86_REG_RBX,8);mu.reg_write(x.UC_X86_REG_RSP,sp)
    mu.emu_start(base+0x10849d0-START,addresses.code+image.bytes,count=30)
    need(stops[-1]==addresses.reject and released==peers and mu.reg_read(x.UC_X86_REG_RSP)==sp-8,'Late bound/ABI failure')
    result=unwind();need(result==0,f'Windows metadata/unwind failed: {result}')
    print('PASS one focused disconnect peer-bank flow: five native-loop releases, eight-slot clear, inline neighbors preserved, bounded entry/late rejection, Windows unwind. Native services are fixtures; full disconnect/recovery/UI/multiplayer unverified. No game access.')


if __name__=='__main__':main()
