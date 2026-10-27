"""One shared-bank flow for the four remaining prepared UI peer readers.

Prepare/seal/discard the real bound UI group, then emulate only its changed
lookup windows against owned memory. This does not run game/UI code in a game,
publish hooks, validate full UI functions, or certify multiplayer behavior.
"""
import argparse
import ctypes as c
import importlib
import struct
import subprocess
from pathlib import Path
import generate_loadout_lifecycle as g
from generate_loadout_links import MODULES,build as local_links
from validate_loadout_lifecycle import Addresses,Fixture,GAME,CODE,SCREEN,RECORDS,WIDGETS,REJECT,STACK,SP,R,U32,U64,u
from validate_loadout_consumers import Binding,Peers,MAPS,ROSTER,STORAGE,DESCS,PEER
from validate_loadout_setup import SetupAddresses,Placement,GroupAddresses,record_source,countdown_source,resource_owner_source

OWNER,BANK,SESSION=0x300000000,0x310000000,0x300020000
CLIENT=OWNER+0x162c8
ORDER=[3,7,0,6,1,5,2,4]


class ReaderFlow(Fixture):
    def __init__(self,images,bases):
        self.uc=u.Uc(u.UC_ARCH_X86,u.UC_MODE_64);self.pages=set();self.bank_reads=[]
        self.bases=bases;self.mapping={};self.stop=0
        for name in ('setup','records','mode','countdown'):
            artifact=importlib.import_module('generate_loadout_'+name).build(True)
            self.mapping[name]=artifact['mapping'];self.map(bases[name],len(images[name]));self.write(bases[name],images[name])
        for address,size in ((OWNER,0x17000),(BANK-16,0x120),(SESSION,0xb400),(ROSTER,0xe8),
                             (STORAGE,0x680),(DESCS,0x1000),(SCREEN,0x1000),(STACK,0x2000),(REJECT,1),
                             (GAME+0x3484888,4),(GAME+0x3483c34,4)):
            self.map(address,size)
        self.write(CLIENT,U64(SESSION));self.write(SESSION+0xb398,U64(PEER+7))
        self.write(CLIENT+0xc8,U32(8));self.write(CLIENT+0xd0,b'\xa5'*256)
        self.write(BANK-16,b'\x6b'*16);self.write(BANK+256,b'\x6b'*16)
        self.write(ROSTER+0x84,U32(8))
        self.write(GAME+0x3484888,U32(0xffffffff));self.write(GAME+0x3483c34,U32(0xffffffff))
        for ordinal,index in enumerate(ORDER):
            record=bytearray([0x30+ordinal]*32);struct.pack_into('<Q',record,0,PEER+ordinal)
            struct.pack_into('<I',record,0x14,index);self.write(BANK+ordinal*32,bytes(record))
            self.write(STORAGE+0x3c0+ordinal*0x38,U64(PEER+ordinal))
            self.write(STORAGE+ordinal*8,U64(DESCS+ordinal*32));self.write(DESCS+ordinal*32+8,U32(100+ordinal))
        self.uc.hook_add(u.UC_HOOK_CODE,self.step)
        self.uc.hook_add(u.UC_HOOK_MEM_READ|u.UC_HOOK_MEM_WRITE,self.memory)

    def memory(self,uc,access,address,size,value,user):
        g.need(not (address<CLIENT+0x1d0 and CLIENT+0xd0<address+size),'Read old inline confirmed-peer bank')
        if BANK-16<=address<BANK+272:
            g.need(access==u.UC_MEM_READ and BANK<=address and address+size<=BANK+256,'Shared peer bank modified or overrun')
            self.bank_reads.append((address,size))

    def step(self,uc,address,size,user):
        if address in (self.stop,REJECT):uc.emu_stop()

    def run(self,name,start,stop,**registers):
        self.stop=self.bases[name]+self.mapping[name][stop];self.bank_reads=[]
        for reg in ('rax','rbx','rcx','rdx','rsi','rdi','rbp','r8','r9','r10','r11','r12','r13','r14','r15'):
            self.uc.reg_write(R(reg),registers.get(reg,0))
        self.uc.reg_write(R('rsp'),SP)
        self.uc.emu_start(self.bases[name]+self.mapping[name][start],REJECT+1,count=3000)
        return self.value('rip')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path,default=g.PROJECT/'build/loadout_peer_readers_test.dll');args=p.parse_args()
    if args.zig:
        g.need(args.upstream is not None,'--upstream required');args.library.parent.mkdir(exist_ok=True,parents=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',g.PROJECT/'mod/src','-shared']
        command += [g.PROJECT/'mod/src'/name for name in ['ep_session_code.cpp','ep_loadout_group.cpp']+
                    ['ep_loadout_'+name+'.cpp' for name in MODULES]]
        command += [g.PROJECT/'tests/loadout_setup_dll.cpp','-o',args.library.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True);g.need(result.returncode==0,result.stdout+result.stderr)
    dll=c.CDLL(str(args.library.resolve()))
    dll.setup_group_peer_snapshot.argtypes=[c.POINTER(GroupAddresses),c.POINTER(Peers),c.POINTER(c.c_ubyte),c.c_uint32,c.POINTER(c.c_uint32),c.POINTER(c.c_uint64)]
    setup=SetupAddresses();setup.common=Binding(Addresses(GAME,CODE+0x30000,SCREEN,RECORDS,WIDGETS,REJECT,8,0),MAPS,MAPS+32,ROSTER,STORAGE)
    for i in range(8):setup.placements[i]=Placement(0,0,0.5,0.5,0.5,0)
    group=GroupAddresses(setup,CODE+0x40000,CODE,CODE+0x50000,CODE+0x60000,record_source(),CODE+0x70000,
        CODE+0x80000,CODE+0x90000,CODE+0xa0000,CODE+0xb0000,CODE+0xc0000,CODE+0xd0000,countdown_source(),
        CODE+0xe0000,CODE+0xf0000,resource_owner_source(),CODE+0x110000,CODE+0x120000,CODE+0x130000,
        CODE+0x140000,CODE+0x150000,CODE+0x160000,CODE+0x170000,CODE+0x180000)
    peers=Peers(CLIENT,BANK,8,0);stride=65536;raw=(c.c_ubyte*(len(MODULES)*stride))();sizes=(c.c_uint32*len(MODULES))();routes=(c.c_uint64*5)()
    result=dll.setup_group_peer_snapshot(c.byref(group),c.byref(peers),raw,stride,sizes,routes)
    g.need(result==0,f'Bound UI group preparation/seal/discard failed: {result}')
    images={name:bytes(raw[i*stride:i*stride+sizes[i]]) for i,name in enumerate(MODULES)}
    bases={name:setup.common.lifecycle.code if name=='setup' else getattr(group,name+'_code') for name in MODULES}
    # Verify actual group-patched displacements after the mode/countdown size changes.
    for source,target,offset,nxt,rva,entry in local_links(True):
        actual=bases[MODULES[source]]+nxt+struct.unpack_from('<i',images[MODULES[source]],offset)[0]
        g.need(actual==bases[MODULES[target]]+entry,'Group call points to stale entry/offset')
    f=ReaderFlow(images,bases)
    g.need(f.run('setup',0x1466f5d,0x14670b8,r8=OWNER,rdi=SCREEN)==f.stop and f.value('rcx')==ORDER[7],
           'Setup did not resolve eighth local peer through shared bank')
    # Simulate native swap-last removal consistently in the two owned banks.
    f.write(BANK,f.read(BANK+7*32,32));f.write(BANK+7*32,bytes(32));f.write(CLIENT+0xc8,U32(7))
    f.write(STORAGE+0x3c0,f.read(STORAGE+0x3c0+7*0x38,0x38));f.write(STORAGE,f.read(STORAGE+7*8,8));f.write(ROSTER+0x84,U32(7))
    before=f.read(BANK,256)
    g.need(f.run('records',0x146fd9f,0x146fde6,r8=OWNER,rsi=ROSTER)==f.stop and f.value('rbx')==ORDER[7],
           'Record sync confused compacted ordinal with network index')
    g.need(f.run('mode',0x14710ce,0x1471134,r10=OWNER,r9=PEER+7)==f.stop and f.value('r15')==ORDER[7],
           'Mode switch used the inline bank or wrong network index')
    g.need(f.run('countdown',0x146aa0f,0x146aa95,r11=OWNER,rdx=1,rbx=ROSTER)==f.stop and f.value('rdi')==7 and
           f.bank_reads==[(BANK+i*32,8) for i in range(7)],'Countdown did not scan all seven remaining peers')
    f.write(CLIENT+0xc8,U32(9))
    g.need(f.run('mode',0x14710ce,0x1471134,r10=OWNER,r9=PEER+7)==REJECT and not f.bank_reads,'Oversized peer count not rejected')
    # Deliberately unmapped foreign owner: identity must be rejected before dereference.
    g.need(f.run('mode',0x14710ce,0x1471134,r10=0x320000000,r9=PEER+7)==REJECT and not f.bank_reads,'Foreign owner not rejected')
    g.need(f.read(BANK,256)==before and f.read(BANK-16,16)==f.read(BANK+256,16)==b'\x6b'*16,'Reader modified shared bank/guards')
    print('PASS: shared peer lookup flow, compacted network indices, count/owner rejection; real bound group sealed/linked/discarded; game_access=false')


if __name__=='__main__':main()
