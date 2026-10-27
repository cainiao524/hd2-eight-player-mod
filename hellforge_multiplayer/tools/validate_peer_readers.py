"""One fifth-peer lookup/flag/compaction flow, with owned native-service fixtures."""
import argparse
import ctypes as c
import struct
import subprocess
from pathlib import Path
from validate_client_peers import Addresses,Image,need
from generate_loadout_lifecycle import PROJECT,Capture
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn import x86_const as x


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True);a=p.parse_args()
    library=PROJECT/'build/peer_readers_test.dll';library.parent.mkdir(exist_ok=True)
    sources=[PROJECT/'mod/src'/name for name in ('ep_client_peers.cpp','ep_client_disconnect.cpp','ep_session_code.cpp')]+[PROJECT/'tests/client_peers_dll.cpp']
    cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
         '-Wno-missing-field-initializers','-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*sources,'-o',library]
    result=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(library));fixture=dll.client_peer_reader_fixture;fixture.argtypes=[];fixture.restype=c.c_int
    need((rc:=fixture())==0,f'Reader family/leaf unwind: {rc}')
    emit=dll.client_peer_emit;emit.argtypes=[c.c_uint32,c.POINTER(Addresses),c.POINTER(Image)];emit.restype=c.c_int
    game=0x140000000;code=0x180000000;client=0x200000000;bank=0x200010010;reject=0x1c0000000;stop=reject+0x10000
    owner=0x210000000;registry=0x220000000;session=0x230000000;timer=0x240000000;host=0xabcdef;stack=0x300008008
    mu=Uc(UC_ARCH_X86,UC_MODE_64);pages=set();images={}
    def write(at,data):
        for page in range(at&~4095,(at+len(data)+4095)&~4095,4096):
            if page not in pages:mu.mem_map(page,4096);pages.add(page)
        mu.mem_write(at,data)
    def u32(at,v):write(at,struct.pack('<I',v))
    def u64(at,v):write(at,struct.pack('<Q',v))
    for at,n in ((client,0x1000),(owner,0x20000),(registry,0x7000),(session,0x40000),(timer,0x1000),(stack-0x4000,0x8000)):write(at,bytes(n))
    write(bank-16,b'\x6c'*288);write(bank,bytes(256));write(client+0xd0,b'\x5a'*128);write(reject,b'\xcc');write(stop,b'\xcc')
    u64(client,owner);u64(owner+0xb3a8,host);u32(client+0xc8,4)
    for n in range(4):u64(bank+n*32,0x100+n);u32(bank+n*32+0x14,n)
    capture=Capture()
    for pc,target in ((0x1087363,registry),(0x108758b,registry),(0x1087572,session),(0x108778c,owner),(0x10877bd,timer)):
        ins=next(capture.md.disasm(capture.read(pc,15),pc));u64(game+pc+ins.size+ins.disp,target)
    for target in (0x1738300,0xb5ea90,0x1346e30,0xb5f140,0xb51de0):write(game+target,b'\xc3')
    for kind in (1,3,5,6,7):
        at=Addresses(game,code+kind*0x10000,client,bank,reject,8,0);im=Image();need(emit(kind,c.byref(at),c.byref(im))==0,'Reader emission')
        write(at.code,bytes(im.data[:im.bytes]));images[kind]=at.code
    mu.hook_add(UC_HOOK_CODE,lambda uc,pc,size,user:uc.emu_stop() if pc==reject else None)
    def call(kind,peer=0x104,selected=client,identity=host,expected=stop):
        u64(stack,stop);u64(stack+0x28,0x44);u64(stack+0x30,7);u64(stack+0x38,1)
        args=(selected,peer,0,0) if kind in (5,6) else (selected,identity,peer,0x555)
        for reg,value in zip((x.UC_X86_REG_RCX,x.UC_X86_REG_RDX,x.UC_X86_REG_R8,x.UC_X86_REG_R9),args):mu.reg_write(reg,value)
        mu.reg_write(x.UC_X86_REG_RSP,stack);mu.emu_start(images[kind],stop,count=2000)
        need(mu.reg_read(x.UC_X86_REG_RIP)==expected,f'Unexpected peer reader exit: {kind}')
        if expected==stop:need(mu.reg_read(x.UC_X86_REG_RSP)==stack+8,'Changed native stack ABI')
        return mu.reg_read(x.UC_X86_REG_RAX)
    call(1);need(call(5)==bank+128 and call(6)&255==1,'Fifth peer missing')
    write(bank+128+0x19,b'\0');before=bytes(mu.mem_read(bank,256));call(7,identity=host+1)
    need(bytes(mu.mem_read(bank,256))==before,'Foreign host changed flag')
    call(7);after=bytearray(before);after[128+0x19]=1
    need(bytes(mu.mem_read(bank,256))==after,'Flag setter changed other record bytes')
    call(3,peer=0x100);need(call(5)==bank and call(6)&255==1 and call(5,peer=0x100)==0 and call(6,peer=0x100)&255==0,'Compacted/absent peer lookup')
    need(struct.unpack('<I',mu.mem_read(bank+0x14,4))[0]==7,'Compaction lost network index')
    u32(client+0xc8,0);need(call(5)==0 and call(6)&255==0,'Empty lookup')
    u32(client+0xc8,9)
    for kind in (5,6,7):call(kind,expected=reject)
    u32(client+0xc8,4)
    for kind in (5,6,7):call(kind,selected=0x2f0000000,expected=reject) # unmapped, must reject before dereference
    need(bytes(mu.mem_read(client+0xd0,128))==b'\x5a'*128,'Inline records touched')
    need(bytes(mu.mem_read(bank-16,16))+bytes(mu.mem_read(bank+256,16))==b'\x6c'*32,'Bank boundary changed')
    print('PASS one fifth-peer reader/flag/compaction flow: actual shared record pointers, presence, native host condition, exact flag byte, empty/absent/bounded reads; eight-entry family cleanup and leaf Windows unwind. Native services are fixtures; remaining inline readers, activation and actual multiplayer unverified. No game access.')


if __name__=='__main__':main()
