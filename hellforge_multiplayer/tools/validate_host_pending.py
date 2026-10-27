"""One native admission-to-queue flow in owned test memory, with service fixtures.

Seven incoming members join the host, filling eight slots, and use the last
pending row. Native capacity refusal follows; queue-full rejection is terminal.
This does not decode packets, execute the pending consumer or access a game.
"""
import argparse
import ctypes as C
import struct
import subprocess
from collections import deque
from pathlib import Path
from generate_loadout_lifecycle import Capture,PROJECT,need
from generate_host_pending import START,END
from host_task_layout import TASK_STRIDE,PENDING_STRIDE,PENDING_KEY
from validate_host_lifecycle import Addresses
from unicorn import Uc,UcError,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn import x86_const as x
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_REG_RIP


class PendingAddresses(C.Structure):
    _fields_=[('host',Addresses),('remove_data',C.c_uint64)]


class Image(C.Structure):
    _fields_=[(n,C.c_uint32) for n in ('bytes','table_offset','function_count','handler_offset','body_offset')]+[('data',C.c_uint8*8192)]


def flow(dll,after_admission=None):
    h=Addresses(0x140000000,0x180000000,0x2100162c8,0x220000000,0x1c0000000,
                0x220010000,0x220020000,0x220030000,0x220040000,8,0)
    a=PendingAddresses(h,0x180020000);image=Image();emit=dll.pending_emit
    emit.argtypes=[C.POINTER(PendingAddresses),C.POINTER(Image)];emit.restype=C.c_int
    need(emit(C.byref(a),C.byref(image))==0,'Pending image')
    u=Uc(UC_ARCH_X86,UC_MODE_64);pages=set();owner=h.client-0x162c8;host=h.client-0x918
    stack,stop,stub,payload=0x230000000,0x240000000,0x260000000,0x270000000
    def map_region(address,size):
        # Preserve mapped pages while avoiding thousands of separate regions
        # that make Unicorn allocation and teardown needlessly slow.
        page=address&~4095;end=(address+size+4095)&~4095
        while page<end:
            if page in pages:page+=4096;continue
            first=page
            while page<end and page not in pages:page+=4096
            u.mem_map(first,page-first);pages.update(range(first,page,4096))
    def qword(p):return struct.unpack('<Q',u.mem_read(p,8))[0]
    def dword(p):return struct.unpack('<I',u.mem_read(p,4))[0]
    def putq(p,v):u.mem_write(p,struct.pack('<Q',v))
    def putd(p,v):u.mem_write(p,struct.pack('<I',v))
    for address,size in ((h.code,8192),(owner,0x30000),(stack,0x8000),(stop,4096),(stub,0x2000),(payload,4096),(h.reject,4096)):
        map_region(address,size)
    for address in (h.confirmed,h.peers,h.flags,h.large,h.pending):map_region(address,8*TASK_STRIDE+4096)
    u.mem_write(h.code,bytes(image.data));putq(host,owner);putd(host+0x18,1)
    u.mem_write(host+0x20,b'\xa5'*(0x918-0x20));putd(h.client+0xc8,1);putq(h.confirmed,0x500)
    putq(h.peers,0x500);putd(h.peers+0x20,9);u.mem_write(h.flags,b'\1')
    u.mem_write(h.pending,b'\xab'*(7*PENDING_STRIDE));u.mem_write(h.pending+7*PENDING_STRIDE,bytes(PENDING_STRIDE))
    for bank,size in ((h.peers,8*56),(h.flags,8),(h.pending,8*PENDING_STRIDE)):u.mem_write(bank+size,b'\xfa'*16)
    putq(owner+0xb390,0x111);putq(owner+0xb398,0x500);putq(owner+0xb3a8,0x500);putd(owner+0x166d8,1)
    incoming=list(range(0x501,0x508));reserved=0x76543210;opaque=0xfedcba9876543210
    u.mem_write(payload,struct.pack('<II8Q',7,reserved,*incoming,0))
    capture=Capture();ins=list(capture.md.disasm(capture.read(START,END-START),START));globals_={};by_pc={}
    owner_global=next(i.address+i.size+i.disp for i in ins if i.address==0x108bcc6)
    for i in ins:
        if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
            target=h.game+i.address+i.size+i.disp;map_region(target,64)
            if i.mnemonic=='mov':
                if target not in globals_:
                    pointer=owner if target==h.game+owner_global else 0x280000000+len(globals_)*0x400000
                    globals_[target]=pointer;map_region(pointer,0x30000 if pointer==owner else 0x200000);putq(target,pointer)
                by_pc[i.address]=globals_[target]
    api=by_pc[0x108c21f];putq(api+0x40,stub+0x1000);putq(stub+0x1008,stub);u.mem_write(stub,b'\xc3')
    services={i.operands[0].imm for i in ins if i.mnemonic=='call' and i.operands[0].type==X86_OP_IMM}
    for rva in services:map_region(h.game+rva,16);u.mem_write(h.game+rva,b'\xc3')
    u.mem_write(h.reject,b'\xcc');recent=deque(maxlen=10);rejected=[];replies=[];cookies=[]
    def returned(value=0):
        sp=u.reg_read(x.UC_X86_REG_RSP);target=qword(sp);u.reg_write(x.UC_X86_REG_RSP,sp+8)
        u.reg_write(x.UC_X86_REG_RAX,value);u.reg_write(x.UC_X86_REG_RIP,target)
    def hook(cpu,address,size,data):
        recent.append(hex(address))
        if address==h.reject:rejected.append(True);cpu.emu_stop();return
        if address==stub:returned();return
        rva=address-h.game
        if rva not in services:return
        rcx=cpu.reg_read(x.UC_X86_REG_RCX);rdx=cpu.reg_read(x.UC_X86_REG_RDX);r8=cpu.reg_read(x.UC_X86_REG_R8);r9=cpu.reg_read(x.UC_X86_REG_R9)
        if rva==0x1092950:need(rcx==owner+0x1d470 and rdx==0x13,'Native policy ABI');returned(3);return
        if rva==0x13efea0:returned(1);return
        if rva==0x12be5a0:putq(rdx,opaque);returned(1);return
        if rva==0x2088770:need(rcx==by_pc[0x108bc82],'Native cookie');cookies.append(True)
        elif rva==0xbe3cf0:replies.append((rcx,rdx,r8,r9))
        elif rva not in (0x13eff30,0x1738300,0x17383e0):raise RuntimeError('Unexpected native service '+hex(rva))
        returned()
    hook_handle=u.hook_add(UC_HOOK_CODE,hook);sp=stack+0x4008
    nonvolatile=((x.UC_X86_REG_RBX,0x33),(x.UC_X86_REG_RBP,0x55),(x.UC_X86_REG_RSI,0x66),(x.UC_X86_REG_RDI,0x77),
                 (x.UC_X86_REG_R12,0xcc),(x.UC_X86_REG_R13,0xdd),(x.UC_X86_REG_R14,0xee),(x.UC_X86_REG_R15,0xff))
    def invoke(sender,task,reject=False):
        putq(sp,stop);putq(sp+0x28,by_pc[0x108c0f8]);putq(sp+0x30,0xa6c7100b0fc9528);putq(sp+0x38,0);putq(sp+0x40,0)
        u.reg_write(x.UC_X86_REG_RSP,sp);u.reg_write(x.UC_X86_REG_RCX,host);u.reg_write(x.UC_X86_REG_RDX,sender)
        u.reg_write(x.UC_X86_REG_R8,task);u.reg_write(x.UC_X86_REG_R9,payload)
        for reg,value in nonvolatile:u.reg_write(reg,value)
        try:u.emu_start(h.code,stop,count=100000)
        except UcError as error:raise RuntimeError(f'{error}; recent={list(recent)}') from error
        need(bool(rejected)==reject and (reject or u.reg_read(x.UC_X86_REG_RIP)==stop),'Request result '+str(list(recent)))
        if not reject:need(all(u.reg_read(reg)==value for reg,value in nonvolatile),'Native nonvolatile restore')
    invoke(incoming[0],0x900f)
    need(not replies and len(cookies)==1,'Accepted request used error path')
    for i,p in enumerate(incoming,1):
        row=h.peers+i*56
        need(qword(row)==p and dword(row+0x20)==1 and dword(row+0x14)==i and dword(row+0x1c)==0x41a00000,'Expanded peer allocation')
    row=bytearray(PENDING_STRIDE);struct.pack_into('<QII7Q',row,0,0x900f,7,reserved,*incoming);struct.pack_into('<Q',row,PENDING_KEY,opaque)
    need(u.mem_read(h.pending,8*PENDING_STRIDE)==b'\xab'*(7*PENDING_STRIDE)+row,'Last pending row/counted copy/key')
    need(u.mem_read(h.flags,8)==b'\1'*8 and qword(owner+0x248)==opaque and dword(owner+0x348)==1,'Flags/key ring')
    if after_admission:
        after_admission(locals());return
    def banks():return tuple(bytes(u.mem_read(bank,size)) for bank,size in ((h.peers,8*56),(h.flags,8),(h.pending,8*PENDING_STRIDE)))
    before=banks();u.mem_write(payload,struct.pack('<II8Q',1,reserved,0x600,*([0]*7)))
    invoke(0x600,0x9010)
    need(replies==[(0x600,0x9010,4,0)] and banks()==before and len(cookies)==2,'Native full-host refusal')
    # Model a completed departure only in owned fixture memory. The still-full
    # queue must reject before the newly free peer slot or flag is changed.
    u.mem_write(h.peers+56,bytes(56));u.mem_write(h.flags+1,b'\0');before=banks()
    invoke(0x600,0x9010,reject=True)
    need(banks()==before and replies==[(0x600,0x9010,4,0)],'Full pending queue changed member banks')
    need(u.mem_read(host+0x20,0x918-0x20)==b'\xa5'*(0x918-0x20),'Native host banks changed')
    for bank,size in ((h.peers,8*56),(h.flags,8),(h.pending,8*PENDING_STRIDE)):need(u.mem_read(bank+size,16)==b'\xfa'*16,'Bank tail')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True);args=p.parse_args()
    build=PROJECT.parent/'work/hellforge-host-pending';build.mkdir(parents=True,exist_ok=True);out=build/'host-pending.dll'
    cmd=[str(args.zig.resolve()),'c++','-std=c++17','-shared','-O0','-g','-I'+str(PROJECT/'mod/src'),'-I'+str(args.upstream.resolve()/'native/mod-sdk'),
         str(PROJECT/'tests/host_pending_dll.cpp'),str(PROJECT/'mod/src/ep_host_pending.cpp'),str(PROJECT/'mod/src/ep_session_code.cpp'),'-o',str(out)]
    subprocess.run(cmd,check=True)
    dll=C.CDLL(str(out));prepare=dll.pending_prepare_flow;prepare.restype=C.c_int
    need((rc:=prepare())==0,f'Pending preparation/unwind line {rc}');flow(dll)
    print('PASS one request-to-pending flow: seven incoming members plus host, eighth queue row, full-host native refusal, '
          'queue-full rejection before writes, original cookie/nonvolatile registers and Windows unwind. '
          'game_access=false, hooks=0; services are fixtures; packet decoder/consumer/runtime/multiplayer unverified.')


if __name__=='__main__':main()
