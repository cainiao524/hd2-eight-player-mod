"""Focused join flow; --result-only skips emission/unwind checks. No game access or receipts."""
import argparse
import ctypes as c
import struct
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'eight_player_candidate_20260927/.native-test-deps'))
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_R14,UC_X86_REG_R8,UC_X86_REG_RIP
from unicorn import x86_const as xr
from generate_player_join import PROJECT,START,END,build,render,HEADER,need


class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','table_offset','function_count','handler_offset','creation_target_offset')]+[('data',c.c_uint8*4096)]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--library',type=Path);mode=p.add_mutually_exclusive_group()
    mode.add_argument('--creation-only',action='store_true');mode.add_argument('--result-only',action='store_true')
    a=p.parse_args();library=(a.library or PROJECT/('build/player_join_result_test.dll' if a.result_only else 'build/player_join_test.dll')).resolve()
    if a.zig:
        need(a.upstream is not None,'--upstream required');library.parent.mkdir(parents=True,exist_ok=True)
        cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
             '-Wno-missing-field-initializers','-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared']
        if not a.result_only:
            cmd += [PROJECT/'mod/src/ep_player_join_image.cpp',PROJECT/'mod/src/ep_session_code.cpp',PROJECT/'tests/player_join_dll.cpp']
        if a.creation_only or a.result_only:
            cmd += [PROJECT/'mod/src'/('ep_'+s+'.cpp') for s in ('player_join_call','roster_call','roster_owner','native_roster')]
            cmd += [PROJECT/'tests/player_join_creation_dll.cpp']
        cmd += ['-o',library]
        done=subprocess.run(list(map(str,cmd)),capture_output=True,text=True);need(done.returncode==0,done.stdout+done.stderr)
    dll=c.CDLL(str(library))
    if a.result_only:
        flow=dll.player_join_creation_flow;flow.argtypes=[];flow.restype=c.c_int
        need(flow()==0,'Owned join outcome delivery')
        print('PASS one focused join-result flow: OLD bypass, skipped creation, nested preflight rejection, cleaned failure, creation, fault and quarantined follow-up; sequenced notices and preserved caller return. Engine services are fixtures; native session recovery/UI/multiplayer unverified. No game access.')
        return
    emit=dll.player_join_emit;emit.restype=c.c_int
    emit.argtypes=[c.c_uint64]*4+[c.c_uint32,c.POINTER(Image)]
    native=dll.player_join_unwind;native.restype=c.c_int;native.argtypes=[]
    saved=build();need(HEADER.read_text(encoding='utf-8')==render(saved),'Generated template changed')
    game,code,control,next_slot=0x140000000,0x180000000,0x1c0000000,0x1c0000010
    image=Image();need(emit(game,code,control,next_slot,8,c.byref(image))==0,'Candidate emission')
    expected=bytearray(saved['blob']);expected[saved['capacity']]=8
    for offset,end,rva in saved['fixes']:struct.pack_into('<i',expected,offset,game+rva-(code+32+end))
    # Compare the entire emitted native instruction region, not metadata or a
    # hash: no instruction other than capacity/relocation may differ.
    need(bytes(image.data[32:32+saved['code_bytes']])==expected[:saved['code_bytes']],'Unexpected native body change')
    mu=Uc(UC_ARCH_X86,UC_MODE_64);mu.mem_map(code,0x2000);mu.mem_write(code,bytes(image.data[:image.bytes]))
    mu.mem_map(game+0x347c000,0x1000);state=0x200000000;mu.mem_map(state,0x20000)
    mu.mem_write(game+0x347cef0,struct.pack('<Q',state));mu.mem_write(state+0xb398,struct.pack('<Q',0xa11ce))
    mu.mem_write(state+0x16390,struct.pack('<I',2));mu.mem_write(state+0x16398,struct.pack('<Q',0xb0b))
    mu.mem_write(state+0x16398+32,struct.pack('<Q',0xa11ce)) # local peer at ordinal 1, deliberately not its network index
    if a.creation_only:
        # Execute the actual appended continuation. Failure must restore all
        # delayed registers and bypass both success helpers and client ready.
        stack=0x300000000;mu.mem_map(stack,0x10000);sp=stack+0x1000
        slots={'RSI':0x2b28,'R12':0x2b38,'R13':0x2af8,'R14':0x2af0,'RDI':0x2b30}
        for i,(name,at) in enumerate(slots.items()):mu.mem_write(sp+at,struct.pack('<Q',0x1100+i))
        for i in range(4):mu.mem_write(sp+0x2ae0-16*i,bytes([0xa6+i])*16)
        notify=game+0x13822e0;mu.mem_map(notify&~4095,4096);mu.mem_write(notify,b'\xc3')
        reached=[]
        def continuation(uc,address,size,unused):
            if address==notify:reached.append(address)
            if address in (code+32+0x1086441-START,code+32+0x10868e8-START):uc.emu_stop()
        mu.hook_add(UC_HOOK_CODE,continuation)
        for ok in (0,1):
            mu.reg_write(xr.UC_X86_REG_RSP,sp);mu.reg_write(xr.UC_X86_REG_RBP,sp+0x100);mu.reg_write(xr.UC_X86_REG_EAX,ok)
            mu.emu_start(code+32+saved['continuation'],code+image.bytes,count=50)
            need(mu.reg_read(UC_X86_REG_RIP)==code+32+(0x10868e8 if ok else 0x1086441)-START,'Incorrect creation continuation')
            if not ok:
                need(not reached,'Failure sent success notification')
                for i,name in enumerate(slots):need(mu.reg_read(getattr(xr,'UC_X86_REG_'+name))==0x1100+i,'Failed register restore '+name)
                for i in range(4):need(mu.reg_read(getattr(xr,'UC_X86_REG_XMM'+str(6+i)))==int.from_bytes(bytes([0xa6+i])*16,'little'),'Failed XMM restore')
        need(reached==[notify],'Success did not keep original notification')
        need(native()==0,'New continuation Windows unwind/GS rejection')
        flow=dll.player_join_creation_flow;flow.argtypes=[];flow.restype=c.c_int
        need(flow()==0,'Owned creation lifecycle')
        print('PASS one focused creation/result flow: rejection, native-failure cleanup, creation and fault reporting; emitted continuation and Windows unwind. Engine services are fixtures; no game access, native session recovery/UI/multiplayer unverified.')
        return
    accepted,fallback=(code+32+x-START for x in (0x108646f,0x108624d))
    def stop(uc,address,size,unused):
        if address in (accepted,fallback):uc.emu_stop()
    mu.hook_add(UC_HOOK_CODE,stop)
    for index,yes in ((4,True),(7,True),(8,False),(0xffffffff,False)):
        mu.mem_write(state+0x163ac+32,struct.pack('<I',index));mu.reg_write(UC_X86_REG_R14,0)
        mu.emu_start(code+32+0x1086212-START,code+image.bytes,count=60)
        need(mu.reg_read(UC_X86_REG_RIP)==(accepted if yes else fallback),f'Network index {index}')
        need(mu.reg_read(UC_X86_REG_R8)==state,'Wrong confirmed-peer source')
    need(native()==0,'Registered Windows join unwind/GS rejection')
    print('PASS one focused join flow: indices 4/7 accepted, 8/FFFFFFFF fallback; exact body relocation and Windows unwind. Game access: false; native creation/UI/group activation: unverified.')


if __name__=='__main__':main()
