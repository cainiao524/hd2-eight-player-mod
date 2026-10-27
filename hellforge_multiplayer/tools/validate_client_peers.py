"""One shared-bank native lifecycle flow, with explicit native-service fixtures.

No regression suite, receipt, hashes, installation, publication or game access.
"""
import argparse
import ctypes as c
import struct
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'eight_player_candidate_20260927/.native-test-deps'))
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn import x86_const as x
from generate_loadout_lifecycle import Capture,PROJECT
from generate_client_peers import SOURCES
from validate_client_disconnect import Addresses,Image as DisconnectImage,need


class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','table_offset','function_count','handler_offset','body_offset','source_rva')]+[('data',c.c_uint8*4096)]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True)
    a=p.parse_args();library=(PROJECT/'build/client_peers_test.dll').resolve();library.parent.mkdir(exist_ok=True)
    sources=[PROJECT/'mod/src'/name for name in ('ep_client_peers.cpp','ep_client_disconnect.cpp','ep_session_code.cpp')]+[PROJECT/'tests/client_peers_dll.cpp']
    cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
         '-Wno-missing-field-initializers','-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*sources,'-o',library]
    result=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(library));emit=dll.client_peer_emit;emit.argtypes=[c.c_uint32,c.POINTER(Addresses),c.POINTER(Image)];emit.restype=c.c_int
    disconnect=dll.client_peer_disconnect_emit;disconnect.argtypes=[c.POINTER(Addresses),c.POINTER(DisconnectImage)];disconnect.restype=c.c_int
    family=dll.client_peer_family_fixture;family.argtypes=[];family.restype=c.c_int
    need((rc:=family())==0,f'Family preparation/unwind: {rc}')
    mu=Uc(UC_ARCH_X86,UC_MODE_64);pages=set()
    def mapped(at,n):
        for page in range(at&~4095,(at+n+4095)&~4095,4096):
            if page not in pages:mu.mem_map(page,4096);pages.add(page)
    def write(at,data):mapped(at,len(data));mu.mem_write(at,data)
    def u32(at,v):write(at,struct.pack('<I',v))
    def u64(at,v):write(at,struct.pack('<Q',v))
    game=0x140000000;code=0x180000000;client=0x200000000;peers=0x200010010;reject=0x1c0000000
    registry=0x210000000;session=0x220000000;timer=0x230000000;stack=0x300008008;stop=0x1c0010000;host=0xabcdef
    mapped(client,0x1000);mapped(peers-16,288);mapped(registry,0x7000);mapped(session,0x40000);mapped(timer,0x1000);mapped(stack-0x4000,0x8000)
    write(reject,b'\xcc');write(stop,b'\xcc');capture=Capture();images=[]
    for k in range(1,5):
        at=Addresses(game,code+(k-1)*0x10000,client,peers,reject,8,0);im=Image()
        need(emit(k,c.byref(at),c.byref(im))==0,'Emission failed');write(at.code,bytes(im.data[:im.bytes]));images.append(im)
    at=Addresses(game,code+4*0x10000,client,peers,reject,8,0);di=DisconnectImage()
    need(disconnect(c.byref(at),c.byref(di))==0,'Disconnect emission failed');write(at.code,bytes(di.data[:di.bytes]))
    # Explicit fixtures for the saved global registries, clock and native calls.
    instructions={i.address:i for b,e in SOURCES for i in capture.md.disasm(capture.read(b,e-b),b)}
    for pc,target in ((0x1087363,registry),(0xb90b37,registry),(0xb90be9,registry),(0x108758b,registry),(0x1087093,registry),
                      (0x1087572,session),(0x108778c,session),(0x10877bd,timer)):
        ins=instructions[pc];u64(game+pc+ins.size+ins.disp,target)
    cookie=instructions[0x1087023];u64(game+cookie.address+cookie.size+cookie.disp,0x12345678)
    calls=(0x1738300,0xb5ea90,0x1346e30,0xb5f140,0xb51de0,0x2088770)
    for target in calls:write(game+target,b'\xc3')
    u64(client,session);u64(session+0xb3a8,host);u32(registry+0x6438,1);u64(registry+0x6440,client);u32(registry+0x6448,0xeb)
    u64(timer+0x18,1234);write(client+0xd0,b'\x5a'*144);write(peers-16,b'\x6c'*288);write(peers,b'\xa5'*256)
    original=[]
    for n in range(4):
        row=struct.pack('<QQIIBB6s',0x100+n,0x200+n,0x300+n,n,0,1,bytes((n,))*6)
        original.append(row);write(peers+n*32,row)
    u32(client+0xc8,4);released=[];added=[];stopped=[]
    after_clear=code+4*0x10000+di.body_offset+0x1084a2f-0x10845b0
    def hook(uc,pc,size,user):
        if pc==game+0xb5f140:released.append(uc.reg_read(x.UC_X86_REG_RCX))
        if pc==game+0xb5ea90:added.append(uc.reg_read(x.UC_X86_REG_RCX))
        if pc in (reject,stop,after_clear):stopped.append(pc);uc.emu_stop()
    mu.hook_add(UC_HOOK_CODE,hook)
    def invoke(kind,peer=0,index=0,expected=stop):
        for reg in (x.UC_X86_REG_RBX,x.UC_X86_REG_RBP,x.UC_X86_REG_RSI,x.UC_X86_REG_RDI,x.UC_X86_REG_R12,x.UC_X86_REG_R13,x.UC_X86_REG_R14,x.UC_X86_REG_R15):mu.reg_write(reg,0)
        mu.reg_write(x.UC_X86_REG_RSP,stack);u64(stack,stop)
        args=(host,peer,0x22222222,0x33333333) if kind==2 else (client,host,peer,0x22222222)
        if kind==3:args=(client,host,peer,2)
        for reg,value in zip((x.UC_X86_REG_RCX,x.UC_X86_REG_RDX,x.UC_X86_REG_R8,x.UC_X86_REG_R9),args):mu.reg_write(reg,value)
        if kind==2:u64(stack+0x28,index);u64(stack+0x30,1)
        else:u64(stack+0x28,0x33333333);u64(stack+0x30,index);u64(stack+0x38,1)
        stopped.clear();mu.emu_start(code+(kind-1)*0x10000,stop,count=4000)
        # Unicorn stops before invoking the stop hook when it reaches end.
        need(mu.reg_read(x.UC_X86_REG_RIP)==expected,'Unexpected native exit')
        if expected==stop:need(mu.reg_read(x.UC_X86_REG_RSP)==stack+8,'Changed native stack ABI')
    def count():return struct.unpack('<I',mu.mem_read(client+0xc8,4))[0]
    for n in range(4,8):
        invoke(1 if n%2==0 else 2,0x100+n,n)
        row=bytes(mu.mem_read(peers+32*n,32))
        need(count()==n+1 and struct.unpack_from('<QQII',row)==(0x100+n,0x22222222,0x33333333,n) and row[24:26]==b'\0\1','Wrong peer/metadata append')
    full=bytes(mu.mem_read(peers,256));invoke(2,0x107,7)
    need(count()==8 and bytes(mu.mem_read(peers,256))==full and added==list(range(0x104,0x108)),'Duplicate changed bank')
    for kind in (1,2):invoke(kind,0x108,8,reject)
    need(count()==8 and bytes(mu.mem_read(peers,256))==full,'Full append mutated bank')
    invoke(3,0x101)
    need(count()==7 and released==[0x101] and bytes(mu.mem_read(peers+32,32))==full[224:256],'Last peer/index not compacted as one record')
    invoke(1,0x101,1);need(count()==8 and struct.unpack('<Q',mu.mem_read(peers+224,8))[0]==0x101,'Rejoin failed')
    invoke(4);need(count()==0 and bytes(mu.mem_read(peers,256))==bytes(256),'Reset did not clear unused capacity')
    invoke(2,0x108,8);need(count()==1,'Append after reset failed')
    # Join the same bank to the prior native disconnect loop. Other disconnect
    # services are intentionally not exercised by this focused peer lifecycle.
    mu.reg_write(x.UC_X86_REG_RDI,client);mu.reg_write(x.UC_X86_REG_R12,0);mu.reg_write(x.UC_X86_REG_RSP,stack-8)
    begin=code+4*0x10000+di.body_offset+0x10849ba-0x10845b0
    mu.emu_start(begin,after_clear,count=200)
    need(mu.reg_read(x.UC_X86_REG_RIP)==after_clear and released==[0x101,0x108] and count()==0 and bytes(mu.mem_read(peers,256))==bytes(256),'Disconnect used a different bank')
    need(bytes(mu.mem_read(client+0xd0,144))==b'\x5a'*144,'Inline neighbor modified')
    need(bytes(mu.mem_read(peers-16,16))==b'\x6c'*16 and bytes(mu.mem_read(peers+256,16))==b'\x6c'*16,'Bank boundary overwrite')
    print('PASS one shared peer-bank flow: native direct/registered append through slot eight, duplicate/full bounds, complete swap-remove, rejoin, reset, disconnect clear; grouped preparation/cancel and Windows unwind. Native services are fixtures; other client arrays, actual recovery/UI/multiplayer unverified. No game access.')


if __name__=='__main__':main()
