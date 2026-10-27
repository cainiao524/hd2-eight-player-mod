"""One admission/consumption/completion/phase flow on saved code and fixtures.

Execute the actual expanded lookup and both mutually calling phase bodies.
Native transport, resource catalogs and flow credit are explicit fixtures;
no game access, real resource service, packet decoder or activation is tested.
"""
import argparse
import ctypes as C
import struct
import subprocess
from collections import deque
from pathlib import Path
from generate_loadout_lifecycle import PROJECT,need
from generate_host_phase import SOURCES
from host_task_layout import TASK_STRIDE,SECONDARY_COUNT,SECONDARY_START,PENDING_STRIDE
from validate_host_lifecycle import Addresses
from validate_host_pending import flow as admission
from validate_host_update import consume
from validate_host_removal import Image as LookupImage
from unicorn import UcError,UC_HOOK_CODE
from unicorn import x86_const as x
from capstone.x86_const import X86_OP_MEM,X86_OP_IMM,X86_REG_RIP


class PhaseAddresses(C.Structure):
    _fields_=[('host',Addresses),('task_lookup',C.c_uint64)]


class PhaseImage(C.Structure):
    _fields_=[('bytes',C.c_uint32),('table_offset',C.c_uint32),('function_count',C.c_uint32),
              ('entry',C.c_uint32*2),('handler_offset',C.c_uint32),('data',C.c_uint8*4096)]


def finish(dll,f):
    u=f['u'];u.hook_del(f['hook_handle']);h=Addresses.from_buffer_copy(f['h']);h.code=0x180080000
    map_region,putq,putd,qword,dword=(f[name] for name in ('map_region','putq','putd','qword','dword'))
    owner,host,sp,stop,stub=(f[name] for name in ('owner','host','sp','stop','stub'))
    lookup_h=Addresses.from_buffer_copy(h);lookup_h.code=0x180090000;lookup=LookupImage()
    emit=dll.lookup_emit;emit.argtypes=[C.POINTER(Addresses),C.POINTER(LookupImage)];emit.restype=C.c_int
    need(emit(C.byref(lookup_h),C.byref(lookup))==0,'Shared task lookup image')
    a=PhaseAddresses(h,lookup_h.code+lookup.entry[0]);image=PhaseImage();emit=dll.phase_emit
    emit.argtypes=[C.POINTER(PhaseAddresses),C.POINTER(PhaseImage)];emit.restype=C.c_int
    need(emit(C.byref(a),C.byref(image))==0,'Phase image')
    for address,data in ((h.code,image.data),(lookup_h.code,lookup.data)):
        map_region(address,4096);u.mem_write(address,bytes(data))
    # Use the two entries as the real caller's bindings as well; generation
    # must accept these retained helpers, not addresses in the original game.
    f['a'].complete_peer=h.code+image.entry[1];f['a'].advance_phase=h.code+image.entry[0]
    need(dll.update_emit(C.byref(f['a']),C.byref(f['image']))==0,'Caller phase bindings')
    u.mem_write(f['h'].code,bytes(f['image'].data))
    capture=f['f']['capture'];globals_=f['globals_'];by_pc={};ins=[];pool=0x310000000
    for start,end in SOURCES:ins+=list(capture.md.disasm(capture.read(start,end-start),start))
    for i in ins:
        if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in i.operands):
            target=h.game+i.address+i.size+i.disp;map_region(target,64)
            if i.mnemonic=='mov':
                if i.address in (0x108daef,0x108dc52):globals_[target]=pool
                if target not in globals_:globals_[target]=0x300000000+len(globals_)*0x1000000
                pointer=globals_[target];map_region(pointer,0x490000 if pointer==pool else 0x200000);putq(target,pointer);by_pc[i.address]=pointer
            elif i.address==0x108db06:putd(target,0x3f800000)  # fixture credit threshold = 1.0
    api=by_pc[0x108dda5];table=stub+0x1000;connection=stub+0x1800;event_table=stub+0x2000
    map_region(event_table,4096);putq(api+0x40,table);putq(api+0x38,connection);putq(api+0x10,event_table)
    callbacks={stub+0x500:'connected',stub+0x510:'finish',stub+0x520:'credit',stub+0x530:'event'}
    putq(table+8,stub+0x500);putq(table+0x50,stub+0x510);putq(connection+0xe0,stub+0x520);putq(event_table+0x548,stub+0x530)
    for address in callbacks:u.mem_write(address,b'\xc3')
    services={i.operands[0].imm for i in ins if i.mnemonic=='call' and i.operands[0].type==X86_OP_IMM}
    for rva in services:map_region(h.game+rva,16);u.mem_write(h.game+rva,b'\xc3')
    members=f['members'];target=members[-1];peer=h.peers+7*56;task=f['task']
    for index in range(8):putd(h.peers+index*56+0x20,9 if index==0 else 7)
    putd(peer+0x20,5);putd(owner+0x166dc,17);putd(peer+0x28,17);putd(peer+0x2c,0);putd(peer+0x30,0)
    putd(host+0x1c,0);putd(task+SECONDARY_COUNT,56);u.mem_write(task+SECONDARY_START,bytes(56*32))
    last=task+SECONDARY_START+55*32;u.mem_write(last,struct.pack('<QQIIII',members[6],target,2,0,77,0))
    # The eighth request from actual admission/consumption remains the task
    # being looked up; it contains the seven incoming member IDs, including #8.
    need(qword(task)==0x900f and dword(task+8)==7,'Lost producer task identity')
    putd(pool+0x2800e0,65);putd(pool+0x4801e0,2)
    stream0=[(i<<32)|(1000+i) for i in range(65)];stream1=[((200+i)<<32)|(300+i) for i in range(2)]
    for offset,items in ((0x800e0,stream0),(0x2801e0,stream1)):
        u.mem_write(pool+offset,b''.join(struct.pack('<II',v>>32,v&0xffffffff) for v in items))
    batches=[];rpc=[];completed=[];recent=deque(maxlen=12);credit_calls=[];events=[]
    def hook(cpu,address,size,data):
        recent.append(hex(address));need(address!=h.reject,'Phase rejected '+str(list(recent)))
        rcx=cpu.reg_read(x.UC_X86_REG_RCX);rdx=cpu.reg_read(x.UC_X86_REG_RDX);r8=cpu.reg_read(x.UC_X86_REG_R8);r9=cpu.reg_read(x.UC_X86_REG_R9)
        returned=f['returned']
        if address in callbacks:
            name=callbacks[address]
            if name=='connected':returned(1)
            elif name=='finish':completed.append(rdx);returned()
            elif name=='event':need(rcx==host+0x908,'Native event destination');putq(rcx,0xaabb);putq(rcx+8,0xccdd);returned()
            else:
                credit_calls.append(rcx);cpu.reg_write(x.UC_X86_REG_XMM0,0x40000000 if len(credit_calls)==1 else 0);returned()
            return
        rva=address-h.game
        if rva==0x208aaa0:u.mem_write(rcx,bytes((rdx&255,))*r8);returned(rcx);return
        if rva==0xbe1dd0:
            count=dword(rdx);need(rcx==target and count<=64 and r8 in (0,1),'Resource batch ABI')
            batches.append((r8,[qword(rdx+8+i*8) for i in range(count)]));returned();return
        if rva==0xb62210:events.append(True);returned();return
        if rva==0xbde430:
            fields=[]
            for index in range(r9):
                kind,width,pointer=struct.unpack('<IIQ',u.mem_read(r8+index*16,16))
                need((kind,width) in ((9,8),(1,4)),'Phase descriptor kind/width')
                fields.append((kind,width,int.from_bytes(u.mem_read(pointer,width),'little')))
            rpc.append((rcx,rdx,fields));returned();return
        if rva in services and rva not in (0x2088770,0x1738300):raise RuntimeError('Unbound phase service '+hex(rva))
        f['hook'](cpu,address,size,data)
    u.hook_add(UC_HOOK_CODE,hook)
    def advance(phase,member):
        putq(sp,stop);u.reg_write(x.UC_X86_REG_RSP,sp);u.reg_write(x.UC_X86_REG_RCX,host)
        u.reg_write(x.UC_X86_REG_RDX,phase);u.reg_write(x.UC_X86_REG_R8,member)
        for reg,value in f['f']['nonvolatile']:u.reg_write(reg,value)
        u.reg_write(x.UC_X86_REG_XMM6,(0x7777<<64)|0x6666)
        try:u.emu_start(h.code+image.entry[0],stop,count=150000)
        except UcError as error:raise RuntimeError(f'{error}; recent={list(recent)}') from error
        need(u.reg_read(x.UC_X86_REG_RIP)==stop,'Phase failed to return '+str(list(recent)))
        need(all(u.reg_read(reg)==value for reg,value in f['f']['nonvolatile']) and u.reg_read(x.UC_X86_REG_XMM6)==(0x7777<<64)|0x6666,'Phase nonvolatile restoration')
        return u.reg_read(x.UC_X86_REG_RAX)
    need(advance(2,target)==0 and not batches and not completed and dword(peer+0x20)==5,'Last ordered pair did not defer completion')
    putd(last+16,3)  # fixture acknowledgment resolves the final dependency
    need(advance(2,target)==0 and batches==[(0,stream0[:64])] and dword(peer+0x2c)==64 and dword(peer+0x20)==5,'Resource credit did not preserve cursor')
    need(advance(2,target)==0 and batches==[(0,stream0[:64]),(0,stream0[64:]),(1,stream1)] and completed==[target],'Resumed completion duplicated/lost resource data')
    need(dword(peer+0x20)==7 and u.mem_read(peer+0x28,16)==bytes(16),'Eighth peer completion state/cleanup')
    need(rpc==[(0xa497a2dd,target,[]),(0x8fe70196,0xfffffffffffffffd,[(9,8,target)])],'Completion notification ABI')
    for index in range(8):putd(h.peers+index*56+0x20,8)  # fixture ready acknowledgments
    rpc.clear();need(advance(0,0)==1 and advance(1,0)==2,'Native phase progression values')
    need(rpc==[(0xf3ed1929,member,[(1,4,phase)]) for phase in (1,2) for member in members],'Eight scalar phase notifications')
    rpc.clear();need(advance(2,0)==0,'Native final phase result')
    need(events==[True] and rpc==[record for member in members for record in
         ((0xe25ac0a9,member,[(9,8,0xaabb),(9,8,0xccdd)]),(0x6f30f4a,member,[]))],'Eight final notifications: field count must remain two')
    need(u.mem_read(host+0x20,0x908-0x20)==b'\xa5'*(0x908-0x20),'Inline four-slot storage touched')
    for bank,size in ((h.peers,8*56),(h.large,8*TASK_STRIDE),(h.pending,8*PENDING_STRIDE)):
        need(u.mem_read(bank+size,16)==b'\xfa'*16,'Phase bank tail')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True);args=p.parse_args()
    folder=PROJECT.parent/'work/hellforge-host-phase';folder.mkdir(parents=True,exist_ok=True);out=folder/'host-phase.dll'
    sources=[PROJECT/'mod/src'/name for name in ('ep_host_pending.cpp','ep_host_update.cpp','ep_host_phase.cpp','ep_host_removal.cpp','ep_session_code.cpp')]
    sources += [PROJECT/'tests'/name for name in ('host_pending_dll.cpp','host_update_dll.cpp','host_phase_dll.cpp')]
    cmd=[args.zig.resolve(),'c++','-std=c++17','-shared','-O0','-g','-I',PROJECT/'mod/src','-I',args.upstream.resolve()/'native/mod-sdk',*sources,'-o',out]
    result=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);need(result.returncode==0,result.stdout+result.stderr)
    dll=C.CDLL(str(out));prepare=dll.phase_prepare_flow;prepare.restype=C.c_int
    need((rc:=prepare())==0,f'Phase preparation/unwind line {rc}')
    admission(dll,lambda a:consume(dll,a,lambda f:finish(dll,f)))
    print('PASS one admission/consume/phase flow: last ordered-pair dependency, eighth-peer two-stream credit/resume, eight-member phase payloads, original field widths/counts and Windows unwind. game_access=false, hooks=0; services/acknowledgments are fixtures; runtime/decoder/activation/multiplayer unverified.')


if __name__=='__main__':main()
