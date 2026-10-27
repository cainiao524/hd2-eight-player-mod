"""One append/compact/local-join shared-bank flow; no broad regression or game access."""
import argparse
import ctypes as c
import struct
import subprocess
from pathlib import Path
from validate_client_peers import Addresses,Image as OperationImage,need
from validate_player_join import Image
from generate_loadout_lifecycle import PROJECT,Capture
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn import x86_const as x


class Peers(c.Structure):
    _fields_=[('client',c.c_uint64),('bank',c.c_uint64),('capacity',c.c_uint32),('reserved',c.c_uint32)]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True)
    a=p.parse_args();library=(PROJECT/'build/peer_join_test.dll').resolve();library.parent.mkdir(exist_ok=True)
    # Only the changed roster-group/join path and its directly linked emitters.
    names=('player_join_image','client_peers','client_disconnect','session_code','roster_group','roster_gate',
           'roster_call','roster_owner','native_roster','property_gate','property_image','getter_image','mover_image',
           'insert_image','remove_image','classify_image','registry_image','departure_image','arrival_image')
    sources=[PROJECT/'mod/src'/('ep_'+name+'.cpp') for name in names]+[PROJECT/'tests/peer_join_dll.cpp']
    cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
         '-Wno-missing-field-initializers','-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*sources,'-o',library]
    result=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(library));group=dll.peer_join_group_fixture;group.restype=c.c_int;group.argtypes=[]
    need((rc:=group())==0,f'Owned join group/unwind: {rc}')
    emit=dll.peer_join_emit;emit.argtypes=[c.c_uint64]*5+[c.POINTER(Peers),c.POINTER(Image)];emit.restype=c.c_int
    operation=dll.peer_join_operation;operation.argtypes=[c.c_uint32,c.POINTER(Addresses),c.POINTER(OperationImage)];operation.restype=c.c_int
    game=0x140000000;code=0x180000000;owner=0x210000000;client=owner+0x162c8;bank=0x220000000;reject=0x1c0000000
    peers=Peers(client,bank,8,0);image=Image();need(emit(game,code,0x1c0100000,0x1c0100010,reject,c.byref(peers),c.byref(image))==0,'Join emission')
    mu=Uc(UC_ARCH_X86,UC_MODE_64);pages=set()
    def write(at,data):
        for page in range(at&~4095,(at+len(data)+4095)&~4095,4096):
            if page not in pages:mu.mem_map(page,4096);pages.add(page)
        mu.mem_write(at,data)
    def u32(at,v):write(at,struct.pack('<I',v))
    def u64(at,v):write(at,struct.pack('<Q',v))
    write(code,bytes(image.data[:image.bytes]));write(owner,bytes(0x20000));write(bank,bytes(256));write(reject,b'\xcc')
    stack=0x300008008;write(stack-0x4000,bytes(0x8000));stop=0x1c0200000;write(stop,b'\xcc')
    registry=0x230000000;session=0x240000000;timer=0x250000000
    write(registry,bytes(0x7000));write(session,bytes(0x40000));write(timer,bytes(0x1000))
    u64(game+0x347cef0,owner);u64(owner+0xb398,0x104);u64(client,owner);u64(owner+0xb3a8,0xabc)
    # Poison the obsolete inline records. A successful lookup must use bank.
    write(client+0xd0,b'\x5a'*128);u32(client+0xc8,4)
    for n in range(4):u64(bank+n*32,0x100+n);u32(bank+n*32+0x14,n)
    capture=Capture()
    for pc,target in ((0x1087363,registry),(0x108758b,registry),(0x1087572,session),(0x108778c,owner),(0x10877bd,timer)):
        ins=next(capture.md.disasm(capture.read(pc,15),pc));u64(game+pc+ins.size+ins.disp,target)
    for target in (0x1738300,0xb5ea90,0x1346e30,0xb5f140,0xb51de0):write(game+target,b'\xc3')
    ops={}
    for kind in (1,3):
        at=Addresses(game,code+kind*0x10000,client,bank,reject,8,0);im=OperationImage()
        need(operation(kind,c.byref(at),c.byref(im))==0,'Operation emission');write(at.code,bytes(im.data[:im.bytes]));ops[kind]=at.code
    base=code+32;start=0x1085d70;accepted=base+0x108646f-start;fallback=base+0x108624d-start
    def hook(uc,pc,size,user):
        if pc in (accepted,fallback,reject):uc.emu_stop()
    mu.hook_add(UC_HOOK_CODE,hook)
    def native(kind,peer):
        u64(stack,stop);u64(stack+0x28,0x44);u64(stack+0x30,7);u64(stack+0x38,1)
        for reg,value in ((x.UC_X86_REG_RSP,stack),(x.UC_X86_REG_RCX,client),(x.UC_X86_REG_RDX,0xabc),
                          (x.UC_X86_REG_R8,peer),(x.UC_X86_REG_R9,0x555)):
            mu.reg_write(reg,value)
        mu.emu_start(ops[kind],stop,count=2000);need(mu.reg_read(x.UC_X86_REG_RIP)==stop,'Native peer path rejected')
    def join(target):
        mu.reg_write(x.UC_X86_REG_R14,0);mu.reg_write(x.UC_X86_REG_RSP,stack-8)
        mu.emu_start(base+0x1086212-start,code+image.bytes,count=300)
        actual=mu.reg_read(x.UC_X86_REG_RIP)
        need(actual==target,f'Join used wrong peer/index/bank: pc={actual:#x}, expected={target:#x}, local={mu.reg_read(x.UC_X86_REG_R10):#x}, count={mu.reg_read(x.UC_X86_REG_R9)}, ordinal={mu.reg_read(x.UC_X86_REG_RCX)}')
    native(1,0x104);join(accepted) # fifth ordinal, but NETWORK INDEX seven
    need(struct.unpack('<I',mu.mem_read(bank+4*32+0x14,4))[0]==7,'Native index changed')
    native(3,0x100);join(accepted) # compaction moves the same peer to ordinal zero
    need(struct.unpack('<Q',mu.mem_read(bank,8))[0]==0x104,'Compaction did not move local peer')
    for index in (8,0xffffffff):u32(bank+0x14,index);join(fallback)
    u32(bank+0x14,7);u32(client+0xc8,9);join(reject)
    u32(client+0xc8,4);u64(game+0x347cef0,owner+0x80000);join(reject) # unmapped foreign owner, rejected before count
    need(bytes(mu.mem_read(client+0xd0,128))==b'\x5a'*128,'Legacy inline records changed')
    print('PASS one shared-bank append/compact/local-join flow: ordinal-independent network index, legacy inline ignored, sentinel/owner/count bounds, owned group/client guard and GP-only Windows unwind. Native services are fixtures; migration, remaining readers, actual creation/UI/multiplayer unverified. No game access.')


if __name__=='__main__':main()
