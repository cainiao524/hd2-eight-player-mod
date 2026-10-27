"""One admission -> deferred pending -> periodic payload -> task-consumption flow.

Only saved code and owned test allocations. External services are explicit
fixtures; unknown state-transition helpers must not be called on this path.
No packet decoder, transport, activation or real multiplayer is exercised.
"""
import argparse
import ctypes as C
import struct
import subprocess
from collections import deque
from pathlib import Path
from generate_loadout_lifecycle import PROJECT,need
from generate_host_update import START,END,FRAME
from host_task_layout import TASK_STRIDE,PENDING_STRIDE
from validate_host_lifecycle import Addresses
from validate_host_pending import Image,flow as admission
from unicorn import UcError,UC_HOOK_CODE
from unicorn import x86_const as x
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_REG_RIP


class UpdateAddresses(C.Structure):
    _fields_=[('host',Addresses)]+[(name,C.c_uint64) for name in ('ids','remove_data','remove_dispatch','begin_peer','accept_peer','complete_peer','advance_phase')]


def consume(dll,f,after_consumption=None):
    u=f['u'];u.hook_del(f['hook_handle']);h=Addresses.from_buffer_copy(f['h']);h.code=0x180010000
    a=UpdateAddresses(h,0x220050000,*[0x180020000+i*0x10000 for i in range(6)]);image=Image()
    emit=dll.update_emit;emit.argtypes=[C.POINTER(UpdateAddresses),C.POINTER(Image)];emit.restype=C.c_int
    need(emit(C.byref(a),C.byref(image))==0,'Host update image')
    map_region,putq,putd,qword,dword=(f[name] for name in ('map_region','putq','putd','qword','dword'))
    owner,host,sp,stop=f['owner'],f['host'],f['sp'],f['stop'];stub=f['stub'];arena=0x2f0000000
    map_region(h.code,8192);map_region(a.ids,4096);map_region(arena,0x10000);u.mem_write(h.code,bytes(image.data))
    members=[0x500]+f['incoming'];u.mem_write(a.ids,struct.pack('<8Q',*members));putd(h.client+0x10,8)
    for i in range(8):
        putq(h.large+i*TASK_STRIDE,0xa000+i);putd(h.peers+i*56+0x18,0x100+i)
    # Release the fixture's seven reservation markers; keep the producer's
    # actual eighth request byte-for-byte for consumption by the saved caller.
    u.mem_write(h.pending,bytes(7*PENDING_STRIDE));pending=bytes(u.mem_read(h.pending,8*PENDING_STRIDE))
    u.mem_write(h.large+8*TASK_STRIDE,b'\xfa'*16);u.mem_write(a.ids+64,b'\xfa'*16)
    ins=list(f['capture'].md.disasm(f['capture'].read(START,END-START),START));globals_=f['globals_'];by_pc={}
    for i in ins:
        if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
            target=h.game+i.address+i.size+i.disp;map_region(target,64)
            if i.mnemonic=='mov':
                if target not in globals_:
                    pointer=0x280000000+len(globals_)*0x400000;globals_[target]=pointer;map_region(pointer,0x200000);putq(target,pointer)
                by_pc[i.address]=globals_[target]
    api=by_pc[0x108a480];table=stub+0x1000;putq(api+0x40,table)
    callbacks={stub+0x100:'unavailable',stub+0x110:'empty_event',stub+0x120:'connected',stub+0x130:'healthy'}
    putq(table+0x18,stub+0x100)
    for offset in (0x118,0x120,0x128):putq(table+offset,stub+0x110)
    putq(api+0x38,stub+0x1800);putq(stub+0x1800+0x78,stub+0x120);putq(stub+0x1800+0xd8,stub+0x130)
    for address in callbacks:u.mem_write(address,b'\xc3')
    services={i.operands[0].imm for i in ins if i.mnemonic=='call' and i.operands[0].type==X86_OP_IMM}
    for rva in services:map_region(h.game+rva,16);u.mem_write(h.game+rva,b'\xc3')
    helpers=[getattr(a,name) for name in ('remove_data','remove_dispatch','begin_peer','accept_peer','complete_peer','advance_phase')]
    for address in helpers:map_region(address,16);u.mem_write(address,b'\xcc')
    # Tick delta is a fixture zero; the first expired periodic timer executes,
    # while the following tick still has the native ten-second reset value.
    putd(by_pc[0x108ab34],0);putd(host+0x14,0)
    recent=deque(maxlen=12);rpc=[];pings=[];released=[];cookies=[]
    def returned(value=0):
        rsp=u.reg_read(x.UC_X86_REG_RSP);target=qword(rsp);u.reg_write(x.UC_X86_REG_RSP,rsp+8)
        u.reg_write(x.UC_X86_REG_RAX,value);u.reg_write(x.UC_X86_REG_RIP,target)
    def fields(at,count):
        result=[]
        for _ in range(count):
            kind,size,value=struct.unpack('<IIQ',u.mem_read(at,16));at+=16
            if kind==10:
                items=[]
                for _ in range(value):
                    child,width,pointer=struct.unpack('<IIQ',u.mem_read(at,16));at+=16
                    need((child,width) in ((9,8),(2,4)),'Changed array element ABI')
                    items.append(int.from_bytes(u.mem_read(pointer,width),'little'))
                result.append(items)
            else:
                need(kind==9 and size==8,'Changed scalar ABI');result.append(qword(value))
        return result
    def hook(cpu,address,size,data):
        recent.append(hex(address));need(address!=h.reject and address not in helpers,'Unexpected rejection/helper '+str(list(recent)))
        rcx=cpu.reg_read(x.UC_X86_REG_RCX);rdx=cpu.reg_read(x.UC_X86_REG_RDX);r8=cpu.reg_read(x.UC_X86_REG_R8);r9=cpu.reg_read(x.UC_X86_REG_R9)
        if address in callbacks:
            name=callbacks[address]
            if name=='empty_event':u.mem_write(rcx,bytes(16));returned(rcx)
            else:returned(1 if name=='connected' else 0)
            return
        rva=address-h.game
        if rva not in services:return
        if rva==0x2088770:need(rcx==by_pc[0x108a455],'Expanded frame cookie');cookies.append(True)
        elif rva==0x173b6f0:
            u.mem_write(rcx,struct.pack('<QQQ',arena,arena+0x100,0));putq(arena,arena+0x100);putq(arena+0x100,0)
        elif rva==0x173b8d0:
            need(rcx==arena and rdx==0x4000 and r8==4,'Native descriptor allocation size/alignment')
            u.mem_write(arena+0x200,b'\xcd'*0x4000);returned(arena+0x200);return
        elif rva==0xbde430:
            if rcx==0x36334d22:need(r8==r9==0,'Ping fields');pings.append(rdx)
            else:rpc.append((rcx,rdx,r9,fields(r8,r9)))
        elif rva==0x10925d0:need(rcx==owner+0x1d470 and rdx==4 and r8==1,'Capacity confused with metadata field selector')
        elif rva==0x12d59d0:need(r8==0xffffffff,'Release mode');released.append(rdx)
        elif rva not in (0x1738300,0xfdc780):raise RuntimeError('Unexpected native service '+hex(rva))
        returned()
    hook_handle=u.hook_add(UC_HOOK_CODE,hook)
    def tick():
        putq(sp,stop);u.reg_write(x.UC_X86_REG_RSP,sp);u.reg_write(x.UC_X86_REG_RCX,host)
        for reg,value in f['nonvolatile']:u.reg_write(reg,value)
        u.reg_write(x.UC_X86_REG_XMM6,(0x7777<<64)|0x6666)
        tail=sp-(FRAME+32)+0x420;u.mem_write(tail,b'\xfa'*16)
        try:u.emu_start(h.code,stop,count=150000)
        except UcError as error:raise RuntimeError(f'{error}; recent={list(recent)}') from error
        need(u.reg_read(x.UC_X86_REG_RIP)==stop,'Host update did not return '+str(list(recent)))
        need(all(u.reg_read(reg)==value for reg,value in f['nonvolatile']) and u.reg_read(x.UC_X86_REG_XMM6)==(0x7777<<64)|0x6666,'Expanded frame register preservation')
        need(u.mem_read(tail,16)==b'\xfa'*16,'Expanded stack scratch tail')
    tick()
    need(u.mem_read(h.pending,8*PENDING_STRIDE)==pending and not released,'Full task bank lost pending request')
    need(pings==members and rpc==[(0x709c1e3c,0xfffffffffffffffe,2,[members,list(range(0x100,0x108))])],'Eight member/timer counted arrays')
    # Model a completed task in fixture memory, including stale bytes to prove
    # full expanded-record initialization when the deferred request is retried.
    task=h.large+7*TASK_STRIDE;u.mem_write(task,b'\xab'*TASK_STRIDE);putq(task,0)
    tick()
    expected=bytearray(TASK_STRIDE);expected[:72]=pending[7*PENDING_STRIDE:7*PENDING_STRIDE+72]
    need(u.mem_read(task,TASK_STRIDE)==expected,'Expanded task transfer/clear')
    need(rpc[-1]==(0x50c79002,f['opaque'],2,[0x900f,f['incoming']]) and len(rpc)==2,'Pending member payload')
    need(u.mem_read(h.pending,8*PENDING_STRIDE)==bytes(8*PENDING_STRIDE) and released==[f['opaque']] and len(cookies)==2,'Pending release/clear/return')
    need(u.mem_read(host+0x20,0x918-0x20)==b'\xa5'*(0x918-0x20),'Native inline host touched')
    for bank,size in ((h.peers,8*56),(h.flags,8),(h.large,8*TASK_STRIDE),(h.pending,8*PENDING_STRIDE),(a.ids,64)):
        need(u.mem_read(bank+size,16)==b'\xfa'*16,'Host update bank tail')
    if after_consumption:after_consumption(locals())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True);args=p.parse_args()
    folder=PROJECT.parent/'work/hellforge-host-update';folder.mkdir(parents=True,exist_ok=True);out=folder/'host-update.dll'
    sources=[PROJECT/'mod/src'/name for name in ('ep_host_pending.cpp','ep_host_update.cpp','ep_session_code.cpp')]
    sources += [PROJECT/'tests'/name for name in ('host_pending_dll.cpp','host_update_dll.cpp')]
    cmd=[args.zig.resolve(),'c++','-std=c++17','-shared','-O0','-g','-I',PROJECT/'mod/src','-I',args.upstream.resolve()/'native/mod-sdk',*sources,'-o',out]
    result=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);need(result.returncode==0,result.stdout+result.stderr)
    dll=C.CDLL(str(out));prepare=dll.update_prepare_flow;prepare.restype=C.c_int
    need((rc:=prepare())==0,f'Update preparation/unwind line {rc}');admission(dll,lambda f:consume(dll,f))
    print('PASS one admission/defer/consume flow: eight member and timer payloads, retained full-bank request, '
          'complete task transfer, pending clear/release, enlarged frame cookie/registers/Windows unwind. '
          'game_access=false, hooks=0; services are fixtures; helper transitions/packet decoder/runtime/multiplayer unverified.')


if __name__=='__main__':main()
