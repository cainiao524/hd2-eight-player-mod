"""One eight-member migration flow, only in allocated test memory.

Execute the complete saved migration caller, private lookup and removal bodies.
Game services are explicit fixtures recording their ABI; network, metadata
refresh, real automatic migration, pending tasks and UI remain unverified.
No game access, hooks, broad regression, receipts, fingerprints or packages.
"""
import argparse
import ctypes as C
import struct
import subprocess
from collections import deque
from pathlib import Path
from generate_host_migration import START,CODE_END
from generate_loadout_lifecycle import Capture,PROJECT,need
from validate_host_lifecycle import Addresses,Image as LookupImage
from validate_host_removal import Image as RemovalImage
from unicorn import Uc,UcError,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn import x86_const as x
from capstone.x86_const import X86_OP_MEM,X86_REG_RIP


class MigrationAddresses(C.Structure):
    _fields_=[('host',Addresses)]+[(n,C.c_uint64) for n in ('ids','pairs','history','timers','lookup','remove_dispatch')]


class Image(C.Structure):
    _fields_=[(n,C.c_uint32) for n in ('bytes','table_offset','function_count','body_offset')]+[('data',C.c_uint8*8192)]


def flow(dll):
    h=Addresses(0x140000000,0x180000000,0x2100162c8,0x220000000,0x1c0000000,
                0x220010000,0x220020000,0x220030000,0x220040000,8,0)
    a=MigrationAddresses(h,0x220050000,0x220060000,0x220070000,0x220080000,0x180010000,0x180020000)
    removal_base=a.remove_dispatch
    def emit(name,addresses,output):
        fn=getattr(dll,name);fn.argtypes=[C.POINTER(type(addresses)),C.POINTER(type(output))];fn.restype=C.c_int
        need(fn(C.byref(addresses),C.byref(output))==0,name)
        return output
    lookup_addresses=Addresses.from_buffer_copy(h);lookup_addresses.code=a.lookup
    lookup=emit('lookup_emit',lookup_addresses,LookupImage())
    removal_addresses=Addresses.from_buffer_copy(h);removal_addresses.code=removal_base
    removal=emit('removal_emit',removal_addresses,RemovalImage());a.remove_dispatch+=removal.entry[2]
    image=emit('migration_emit',a,Image())
    u=Uc(UC_ARCH_X86,UC_MODE_64);pages=set();owner=h.client-0x162c8;host=h.client-0x918
    stack,stop,stub,engine=0x230000000,0x240000000,0x260000000,0x270000000
    self_id,old_host=0x500,0x999;all_ids=list(range(0x500,0x508));confirmed_ids=all_ids[1:]+[self_id]
    def map_region(address,size):
        for page in range(address&~4095,(address+size+4095)&~4095,4096):
            if page not in pages:u.mem_map(page,4096);pages.add(page)
    def qword(p):return struct.unpack('<Q',u.mem_read(p,8))[0]
    def dword(p):return struct.unpack('<I',u.mem_read(p,4))[0]
    def putq(p,v):u.mem_write(p,struct.pack('<Q',v))
    def putd(p,v):u.mem_write(p,struct.pack('<I',v))
    for address,size in ((h.code,8192),(a.lookup,4096),(removal_base,4096),(owner,0x30000),
                         (stack,0x8000),(stop,4096),(stub,0x4000),(engine,0xad000),(h.reject,4096)):
        map_region(address,size)
    for address in (h.confirmed,h.peers,h.flags,h.large,h.pending,a.ids,a.pairs,a.history,a.timers):map_region(address,8192)
    u.mem_write(h.code,bytes(image.data));u.mem_write(a.lookup,bytes(lookup.data));u.mem_write(removal_base,bytes(removal.data))
    u.mem_write(host+0x20,b'\xa5'*(0x918-0x20));putq(host,owner);putq(host+8,engine)
    for off,length in ((0x18,32),(0x40,64),(0x88,64),(0xd0,128),(0x190,64)):u.mem_write(h.client+off,b'\xa6'*length)
    for off,count in ((0x10,8),(0x38,1),(0x80,8),(0xc8,8)):putd(h.client+off,count)
    for i,p in enumerate(confirmed_ids):
        u.mem_write(h.confirmed+i*32,b'\xc4'*32);putq(h.confirmed+i*32,p);putd(h.confirmed+i*32+20,(i+2)%8)
    u.mem_write(h.peers,b'\xc5'*(8*56));u.mem_write(h.flags,b'\xc6'*8)
    u.mem_write(h.large,b'\xc7'*(8*448));u.mem_write(h.pending,b'\xc8'*(8*64))
    for address,length in ((h.peers,8*56),(h.flags,8),(h.large,8*448),(h.pending,8*64)):
        u.mem_write(address+length,b'\xfa'*16)
    ids_bytes=struct.pack('<8Q',*all_ids);u.mem_write(a.ids,ids_bytes)
    pair_head=struct.pack('<QQ',0x501,0xfedcba9876);u.mem_write(a.pairs,pair_head+b'\xd5'*(7*16))
    history_bytes=b''.join(struct.pack('<QQ',0x700+i,0x1000+i) for i in range(8));u.mem_write(a.history,history_bytes)
    timer_bytes=b''.join(struct.pack('<QII',p,0x100+i,0xcdef) for i,p in enumerate(reversed(all_ids)));u.mem_write(a.timers,timer_bytes)
    timers={p:0x100+i for i,p in enumerate(reversed(all_ids))}
    putq(owner+0xb390,0x111);putq(owner+0xb398,self_id);putq(owner+0xb3a0,0x600);putq(owner+0xb3a8,old_host)
    putd(owner+0x164ac,0x1234)
    capture=Capture();instructions=[];globals_={};globals_by_instruction={}
    for begin,end in ((START,CODE_END),(0x108d190,0x108d3b0)):
        instructions+=list(capture.md.disasm(capture.read(begin,end-begin),begin))
    owner_global=next(i.address+i.size+i.disp for i in instructions if i.address==0x1089753)
    for i in instructions:
        if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
            target=h.game+i.address+i.size+i.disp;map_region(target,0x40)
            if i.mnemonic=='mov':
                if target not in globals_:
                    pointer=owner if target==h.game+owner_global else 0x280000000+len(globals_)*0x400000
                    globals_[target]=pointer;map_region(pointer,0x200000 if pointer!=owner else 0x30000);putq(target,pointer)
                globals_by_instruction[i.address]=globals_[target]
    api=globals_by_instruction[0x1089bfc];putq(api+0x40,stub+0x1000);putq(api+0x10,stub+0x2000)
    callbacks={0x10:'old_host',0x38:'provider_update',0x8:'known',0x68:'remote_state',0xf8:'provider_remove'}
    addresses={}
    for index,(offset,name) in enumerate(callbacks.items()):
        at=stub+0x100+index*16;putq(stub+0x1000+offset,at);addresses[at]=name;u.mem_write(at,b'\xc3')
    for offset,name in ((0x290,'time'),(0x480,'owner_event')):
        at=stub+0x300+len(addresses)*16;putq(stub+0x2000+offset,at);addresses[at]=name;u.mem_write(at,b'\xc3')
    u.mem_write(globals_by_instruction[0x108d22a]+0x28,b'\1')
    putq(globals_by_instruction[0x1089c60]+0x1f8078,self_id)
    services=(0x1738300,0x17384c0,0x208aaa0,0x13ecfd0,0x12e72e0,0xbde430,0x13ed0f0,0xb942a0,0x1089400,
              0xbe4910,0xb90940,0xb92b50,0x10926a0,0xb5f320,0x1092ac0,0x1346f70,0xb90eb0,0x1360380)
    for rva in services:map_region(h.game+rva,16);u.mem_write(h.game+rva,b'\xc3')
    u.mem_write(h.reject,b'\xcc');recent=deque(maxlen=8);rejected=[];seen_lookup=[];seen_remove=[];sync=[];history=[];relations=[];rpc=[]
    def returned(value=0):
        sp=u.reg_read(x.UC_X86_REG_RSP);target=qword(sp);u.reg_write(x.UC_X86_REG_RSP,sp+8)
        u.reg_write(x.UC_X86_REG_RAX,value);u.reg_write(x.UC_X86_REG_RIP,target)
    def hook(cpu,address,size,data):
        recent.append(hex(address))
        if address==h.reject:rejected.append(True);cpu.emu_stop();return
        if address==a.lookup:seen_lookup.append(True);return
        if address==a.remove_dispatch:seen_remove.append(True);return
        rcx=cpu.reg_read(x.UC_X86_REG_RCX);rdx=cpu.reg_read(x.UC_X86_REG_RDX);r8=cpu.reg_read(x.UC_X86_REG_R8);r9=cpu.reg_read(x.UC_X86_REG_R9)
        if address in addresses:
            name=addresses[address]
            returned(old_host if name=='old_host' else 1 if name=='known' else int(rdx!=self_id) if name=='remote_state' else 0x900 if name=='time' else 0);return
        rva=address-h.game
        if rva not in services:return
        if rva==0x208aaa0:cpu.mem_write(rcx,bytes((rdx&255,))*r8);returned(rcx);return
        if rva==0xbe4910:sync.append((rcx,rdx,r8,r9,dword(cpu.reg_read(x.UC_X86_REG_RSP)+0x28)))
        if rva==0xb90940:relations.append((rcx,rdx))
        if rva==0xb92b50:history.append((rcx,rdx,r8))
        if rva==0xbde430:
            fields=[]
            for i in range(r9):
                kind,width,pointer=struct.unpack('<IIQ',cpu.mem_read(r8+i*16,16))
                need(width in (4,8),'Migration field width changed');fields.append((kind,width,int.from_bytes(cpu.mem_read(pointer,width),'little')))
            rpc.append((rcx,rdx,fields))
        returned(1 if rva==0x1092ac0 else 0)
    u.hook_add(UC_HOOK_CODE,hook);sp=stack+0x6008;putq(sp,stop);u.reg_write(x.UC_X86_REG_RSP,sp);u.reg_write(x.UC_X86_REG_RCX,host)
    try:u.emu_start(h.code,stop,count=100000)
    except UcError as error:raise RuntimeError(f'{error}; RIP={u.reg_read(x.UC_X86_REG_RIP):x}; recent={list(recent)}') from error
    need(not rejected and u.reg_read(x.UC_X86_REG_RIP)==stop,'Migration did not finish: '+str(list(recent)))
    need(len(seen_lookup)==7 and len(seen_remove)==1,'Private lookup/removal routing')
    for i,p in enumerate(all_ids):
        at=h.peers+i*56;ordinal=confirmed_ids.index(p)
        need(qword(at)==p and dword(at+20)==(ordinal+2)%8 and dword(at+24)==timers[p],'Peer identity/index/timer mismatch')
        need(dword(at+32)==(9 if p==self_id else 7),'Native peer-state rebuild')
    need(u.mem_read(h.flags,8)==b'\1'*8 and u.mem_read(h.large,8*448)==bytes(8*448),'Expanded migration reset')
    need(u.mem_read(a.pairs,7*16)==pair_head+b''.join(struct.pack('<QQ',p,0) for p in all_ids[2:]),'Native pair append did not use bound bank')
    need(u.mem_read(a.ids,64)==ids_bytes and u.mem_read(a.history,128)==history_bytes and u.mem_read(a.timers,128)==timer_bytes,'Auxiliary source changed')
    need(len(sync)==56 and {row[0] for row in sync}==set(all_ids[1:]) and {row[1] for row in sync}==set(all_ids),'Eight-member state fanout')
    need(len(history)==8 and {row[1] for row in history}==set(range(0x700,0x708)),'History did not include eighth entry')
    reason=[fields for event,p,fields in rpc if event==0x1acfcdf1]
    need(len(reason)==7 and all(fields[1]==(1,4,3) for fields in reason),'Removal RPC four-byte reason')
    need(sum(event==0xf92099c1 for event,p,fields in rpc)==56,'History target fanout')
    need(qword(owner+0xb3a8)==self_id and dword(host+0x1c)==0x1234,'Native host metadata')
    need(u.mem_read(host+0x20,0x918-0x20)==b'\xa5'*(0x918-0x20),'Original host slots changed')
    for off,length in ((0x18,32),(0x40,64),(0x88,64),(0xd0,128),(0x190,64)):
        need(u.mem_read(h.client+off,length)==b'\xa6'*length,'Original auxiliary slots changed')
    need(u.mem_read(h.pending,8*64)==b'\xc8'*(8*64),'Pending records changed')
    for address,length in ((h.peers,8*56),(h.flags,8),(h.large,8*448),(h.pending,8*64)):
        need(u.mem_read(address+length,16)==b'\xfa'*16,'Bank tail overwritten')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True);a=p.parse_args()
    library=PROJECT/'build/host_migration_test.dll';library.parent.mkdir(exist_ok=True)
    sources=[PROJECT/'mod/src'/n for n in ('ep_host_migration.cpp','ep_host_lifecycle.cpp','ep_host_removal.cpp','ep_session_code.cpp')]+[PROJECT/'tests/host_migration_dll.cpp']
    cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
         '-Wno-missing-field-initializers','-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*sources,'-o',library]
    result=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);need(result.returncode==0,result.stdout+result.stderr)
    dll=C.CDLL(str(library));prepare=dll.migration_prepare_flow;prepare.argtypes=[];prepare.restype=C.c_int
    need((rc:=prepare())==0,f'Migration preparation/unwind line {rc}');flow(dll)
    print('PASS one eight-member migration flow: saved caller with private lookup/removal, identity/index/timers, '
          'auxiliary append/history, full state notifications, preserved RPC widths, bank tails and Windows unwind. '
          'game_access=false, hooks=0; native services are fixtures; real migration/UI/multiplayer unverified.')


if __name__=='__main__':main()
